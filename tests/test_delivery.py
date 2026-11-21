import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote

import numpy as np
import pytest

from mechcurve.inputs import digest, discover, locate_inputs
from mechcurve.pipeline import analyze, query, status


class LocalLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.targets = []

    def handle_starttag(self, tag, attrs):
        self.targets.extend(
            unquote(value) for name, value in attrs if name in ("href", "src")
        )


def test_moved_experiment_and_interrupted_output(tmp_path):
    root = tmp_path / "campaigns"
    raw = root / "20300114"
    raw.mkdir(parents=True)
    (raw / "wire.csv").write_text("time_s,force_N\n0,2\n1,4\n")
    output = raw.with_name("20300114_MechCurve")
    stale = output / ".transfer-old" / "old copy"
    stale.mkdir(parents=True)
    (stale / "逐周指标.csv").write_text("time_s,force_N\n0,2\n1,4\n")
    assert locate_inputs(root)[0] == raw
    assert [r["record"] for r in discover(root)] == ["wire.csv"]
    with pytest.raises(ValueError):
        discover(stale)
    (root / "additional.csv").write_text("time_s,force_N\n0,0\n1,3\n")
    assert locate_inputs(root)[0] == root
    assert {r["record"] for r in discover(root)} == {
        "additional.csv",
        "20300114/wire.csv",
    }


def test_cli_mcp_and_incremental_delivery(tmp_path, monkeypatch):
    mcp = pytest.importorskip("mcp")
    from mcp.client.stdio import stdio_client

    source = tmp_path / "raw"
    source.mkdir()
    x = np.linspace(0, 0.028, 281)
    stress = np.where(x <= 0.005, 60000 * x, 300 + 2000 * (x - 0.005))
    raw = source / "tensile.csv"
    raw.write_text(
        "time_s,force_N,strain_pct,stress_MPa\n"
        + "\n".join(
            f"{i},{2 * y},{100 * e},{y}"
            for i, (e, y) in enumerate(
                zip(np.r_[x, 0.0281, 0.0282], np.r_[stress, 2.0, 1.0])
            )
        )
    )
    output = tmp_path / "results"
    notes = {"records": {"tensile.csv": {"fractured": True}}}
    note_path = tmp_path / "notes.json"
    note_path.write_text(json.dumps(notes))
    initial_hash = digest(raw)
    command = [
        sys.executable,
        "-m",
        "mechcurve",
        "analyze",
        str(source),
        "--output",
        str(output),
        "--notes",
        str(note_path),
    ]
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    response = subprocess.run(
        command, capture_output=True, encoding="utf-8", env=env, check=True
    )
    cli = json.loads(response.stdout)
    run = Path(cli["run"])
    assert cli["status"] == "complete"
    from pypdf import PdfReader

    pages = PdfReader(cli["sample_sheet_report"]).pages
    assert len(pages) == 1 and "60.00 GPa" in pages[0].extract_text()
    links = LocalLinks()
    links.feed(Path(cli["index"]).read_text(encoding="utf-8"))
    assert links.targets and all((run / path).is_file() for path in links.targets)
    assert run.name in Path(cli["entry"]).read_text(encoding="utf-8")
    assert list(run.glob("样品/*/*论文单图.svg"))
    expected = query(run, "tensile.csv")
    assert expected["tensile"]["modulus_GPa"] == pytest.approx(60.0)

    async def check_protocol():
        params = mcp.StdioServerParameters(
            command=sys.executable, args=["-m", "mechcurve.server"], env=env
        )
        async with (
            stdio_client(params) as (rd, wr),
            mcp.ClientSession(rd, wr) as session,
        ):
            await session.initialize()
            tools = await session.list_tools()
            assert {t.name for t in tools.tools} == {
                "analyze_directory",
                "inspect_directory",
                "list_protocols",
                "summarize_axial",
                "read_cycles",
                "review_rows",
                "verify_delivery",
            }

            async def call(name, arguments):
                reply = await session.call_tool(name, arguments)
                assert not reply.isError, reply.content
                return json.loads(reply.content[0].text)

            assert "torsion" in await call("list_protocols", {})
            twist = tmp_path / "twist.tsv"
            twist.write_text("angle_deg\ttorque_Nm\n0\t0\n1\t2\n")
            inspected = await session.call_tool(
                "inspect_directory", {"input_dir": str(twist)}
            )
            assert not inspected.isError and "torsion" in inspected.content[0].text
            multi = await call(
                "analyze_directory", {"input_dir": str(twist), "lang": "en"}
            )
            observed = await call(
                "read_cycles", {"run": multi["run"], "record": twist.name}
            )
            assert observed["test_type"] == "torsion"
            assert observed["curve"]["metrics"][0]["value"] == 2
            assert (await call("verify_delivery", {"run": multi["run"]}))[
                "status"
            ] == "complete"
            compact = await call(
                "summarize_axial", {"run": str(run), "sample": expected["sample"]}
            )
            assert (
                compact["terminal_records"][0]["before_row"]
                == expected["event"]["source_row"]
            )
            same = await call(
                "analyze_directory",
                {"input_dir": str(source), "output_dir": str(output), "notes": notes},
            )
            assert same == cli
            summary = await call(
                "read_cycles", {"run": str(run), "record": "tensile.csv"}
            )
            assert (
                summary["tensile"] == expected["tensile"]
                and summary["event"]["source_row"] == 282
            )
            window = await call(
                "review_rows",
                {"run": str(run), "record": "tensile.csv", "row": 282, "radius": 1},
            )
            assert [p["source_row"] for p in window["points"]] == [281, 282, 283]
            assert (await call("verify_delivery", {"run": str(run)}))[
                "status"
            ] == "complete"

    asyncio.run(check_protocol())
    amended = analyze(source, output, {**notes, "batch_note": "独立实验者确认事件。"})
    assert amended["run"] != cli["run"] and amended["reuse"] == {
        "records": 1,
        "samples": 1,
    }
    assert digest(raw) == initial_hash
    assert status(run)["status"] == "complete"
    assert Path(amended["run"]).name in Path(amended["entry"]).read_text(
        encoding="utf-8"
    )

    english = analyze(source, output, notes, lang="en")
    en_run = Path(english["run"])
    assert english["stage_metrics"]["record"]["reused"] == 1
    assert query(en_run, "tensile.csv") == expected
    en_sheet = PdfReader(english["sample_sheet_report"])
    assert len(en_sheet.pages) == 1 and "60.00 GPa" in en_sheet.pages[0].extract_text()
    assert "Tensile" in en_sheet.pages[0].extract_text()
    links = LocalLinks()
    links.feed(Path(english["index"]).read_text(encoding="utf-8"))
    assert links.targets and all((en_run / path).is_file() for path in links.targets)

    # A changed sheet renderer should not force numerical work or segment exports.
    import mechcurve.pipeline as pipeline

    sheet_source = Path(pipeline.__file__).with_name("sheets.py")
    monkeypatch.setattr(
        pipeline,
        "digest",
        lambda path: "sheet-revision" if path == sheet_source else digest(path),
    )
    refreshed = analyze(source, output, notes, lang="en")
    metrics = refreshed["stage_metrics"]
    assert metrics["sheet"]["built"] == 1
    assert all(
        metrics[layer]["reused"] == 1 for layer in ("record", "segment", "detail")
    )
