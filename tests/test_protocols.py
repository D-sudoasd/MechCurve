import json
import math
from pathlib import Path
from urllib.parse import unquote
from html.parser import HTMLParser

import pytest
from openpyxl import Workbook
from pypdf import PdfReader

from mechcurve.inputs import discover
from mechcurve.intake import inspect_records
from mechcurve.pipeline import analyze, query, status
from mechcurve.protocols import record_analysis

DEMO = Path(__file__).resolve().parents[1] / "examples" / "protocols"


def analysis(name, opts=None):
    path = DEMO / name
    settings = json.loads((DEMO / "notes.json").read_text())["records"].get(name, {})
    return record_analysis(
        {"record": name, "path": path}, {}, settings if opts is None else opts
    )


def measured(record):
    return {m["metric"]: m for m in record["curve"]["metrics"]}


@pytest.mark.parametrize(
    "filename,kind,key,expected",
    [
        ("compression.csv", "compression", "compression_modulus", 60),
        ("beam.tsv", "flexure", "nominal_flexural_stress", 37.5),
        ("shear.csv", "shear", "peak_shear_stress", 204),
        (
            "torsion.csv",
            "torsion",
            "nominal_surface_shear",
            16 * 4800 / (math.pi * 125),
        ),
        ("creep.csv", "creep", "mean_hold_rate", 0.01 / 60),
        ("relaxation.csv", "relaxation", "relaxation_drop", 60 * (1 - math.exp(-4))),
        ("fatigue.csv", "fatigue", "highest_observed_cycle", 200000),
        ("fatigue-wave.csv", "fatigue", "peak_to_peak_amplitude", 45),
        ("indentation.csv", "indentation", "maximum_depth", 0.0025),
        ("peel.csv", "peel", "peak_peel_force_per_width", None),
        ("custom.csv", "generic", "minimum_response", 1.5),
    ],
)
def test_protocol_physics(filename, kind, key, expected):
    r = analysis(filename)
    assert r["test_type"] == kind
    m = measured(r)[key]
    if expected is None:
        expected = max(p["force_N"] for p in r["points"]) / 10
    assert m["value"] == pytest.approx(expected, rel=2e-7)
    assert set(m["source_rows"]) <= {p["source_row"] for p in r["points"]}
    if kind == "compression":
        assert measured(r)["minimum_response"]["value"] < 0
        assert r["curve"]["modulus_fit"]["r2"] == pytest.approx(1)
    if kind == "torsion":
        assert r["points"][-1]["angle_deg"] == pytest.approx(math.degrees(0.04))


def test_geometries_hold_and_fatigue_evidence(tmp_path):
    assert "nominal_flexural_stress" not in measured(analysis("beam.tsv", {}))
    for partial in (
        {"fixture": "three_point_rectangular", "span_mm": 40},
        {
            "fixture": "four_point_rectangular",
            "width_mm": 8,
            "thickness_mm": 2,
            "span_mm": 40,
        },
    ):
        raw = analysis("beam.tsv", {"geometry": partial})
        assert (
            "flexure_geometry" in raw["curve"]["warnings"] and len(raw["points"]) == 41
        )
    geom = {
        "fixture": "four_point_rectangular",
        "span_mm": 40,
        "inner_span_mm": 20,
        "width_mm": 8,
        "thickness_mm": 2,
    }
    assert measured(analysis("beam.tsv", {"geometry": geom}))[
        "nominal_flexural_stress"
    ]["value"] == pytest.approx(18.75)
    with pytest.raises(ValueError):
        analysis("beam.tsv", {"geometry": {**geom, "inner_span_mm": 40}})
    r = analysis("fatigue-wave.csv")
    assert len(r["curve"]["fatigue_cycles"]) == 4
    c = r["curve"]["fatigue_cycles"][0]
    assert (c["peak_row"], c["valley_row"], c["next_peak_row"]) == (7, 17, 27)
    assert (c["amplitude"], c["mean_extrema"], c["load_ratio"]) == pytest.approx(
        (45, 15, -0.5)
    )
    file = tmp_path / "creep.csv"

    def run(data, opts=None):
        file.write_text(data)
        return record_analysis({"path": file, "record": file.name}, {}, opts or {})

    r = run("time_s,strain_pct\n0,1\n5,1.1\n10,1.2\n")
    assert "hold_duration" not in measured(r)
    r = run(file.read_text(), {"hold_rows": [2, 4]})
    assert measured(r)["mean_hold_rate"]["source_rows"] == [2, 4]
    assert "mean_hold_rate" not in measured(
        run("time_s,strain_pct\n0,1\n5,\n10,1.2\n", {"hold_rows": [2, 4]})
    )
    r = run(
        "time_s,strain_pct,stress_MPa\n"
        + "\n".join(f"{i},{0.1 + i * 0.01},{min(i * 10, 50)}" for i in range(20))
    )
    assert r["curve"]["hold"]["source_rows"] == [7, 21]
    file = tmp_path / "plain.csv"
    r = run(
        "Time (s),Stress (MPa),Strain (%)\n"
        + "\n".join(f"{i},50,{0.1 + 0.01 * i}" for i in range(15))
    )
    assert (r["test_type"], r["classification"]) == ("creep", "constant_control")


def test_units_custom_mapping_and_headerless(tmp_path):
    f = tmp_path / "observations.txt"

    def run(text, opts=None):
        f.write_text(text, encoding="utf8")
        return record_analysis({"record": f.name, "path": f}, {}, opts or {})

    r = run("1;2\n2;4\n3;6\n")
    assert [p["source_row"] for p in r["points"]] == [1, 2, 3]
    assert r["curve"]["y"]["unit"] == ""
    r = run("notes preamble\nu (mm);v (mV);w (K)\n1;2;3\n2;4;5\n")
    assert r["curve"]["x"]["key"] == "source_row"
    assert [s["axis"]["unit"] for s in r["curve"]["additional_signals"]] == ["mV", "K"]
    r = run(f.read_text(), {"axes": {"x": "u (mm)", "y": "w (K)"}})
    assert r["curve"]["y"]["unit"] == "K" and r["classification"] == "mapped_axes"
    r = run("Time [s],Force [instrument counts]\n0,10\n1,9\n")
    assert (
        r["curve"]["y"]["unit"] == "instrument counts"
        and r["classification"] == "native_units"
    )
    r = run("Displacement (in),Force (lbf)\n0,0\n1,1\n")
    assert r["points"][-1]["extension_mm"] == pytest.approx(25.4)
    assert r["points"][-1]["force_N"] == pytest.approx(4.4482216152605)
    with pytest.raises(ValueError):
        run("Time (s),Torque (Nm)\n0,0\n1,3", {"test_type": "torsion"})


def test_missing_clock_retains_axial_cycles_and_fit(tmp_path):
    original = Path(__file__).resolve().parents[1] / "examples/demo/cyclic-a.csv"
    text = "\n".join(l.split(",", 1)[1] for l in original.read_text().splitlines())
    f = tmp_path / "axial.csv"
    f.write_text(text)
    settings = json.loads((original.parent / "notes.json").read_text())["records"][
        original.name
    ]
    r = record_analysis({"record": f.name, "path": f}, {}, settings)
    assert len(r["cycles"]) == 6 and all(c["status"] == "complete" for c in r["cycles"])
    assert r["initial_loading_fit"]["modulus_GPa"] == pytest.approx(52)
    assert all(p["time_s"] is None for p in r["points"])
    assert all(c["peak_time_s"] is None for c in r["cycles"])


def test_mixed_campaign_xlsx_partial_and_stable_cache(tmp_path):
    root = tmp_path / "raw"
    root.mkdir()
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Twist"
    sheet.append(["Angle (deg)", "Torque (N·mm)"])
    sheet.append([0, 0])
    sheet.append([1, 1250])
    second = wb.create_sheet("Axial")
    second.append(["strain_pct", "stress_MPa"])
    for i in range(31):
        second.append([i * 0.01, i * 5.5])
    wb.save(root / "runs.xlsx")
    (root / "bad.csv").write_text("no data\n")
    (root / "fatigue-wave.csv").write_bytes((DEMO / "fatigue-wave.csv").read_bytes())
    notes = {
        "records": {
            "runs.xlsx#Twist": {"sample": "Combined", "sequence": 2},
            "runs.xlsx#Axial": {
                "sample": "Combined",
                "sequence": 1,
                "test_type": "tension",
            },
        }
    }
    ids = {d["record"] for d in discover(root)}
    assert ids == {"bad.csv", "runs.xlsx#Twist", "runs.xlsx#Axial", "fatigue-wave.csv"}
    ix = {r["record"]: r for r in inspect_records(root, notes)}
    assert (
        ix["runs.xlsx#Twist"]["test_type"] == "torsion"
        and "intake_issue" in ix["bad.csv"]
    )
    result = analyze(root, tmp_path / "result", notes, lang="en")
    run = Path(result["run"])
    assert result["status"] == "partial" and result["plotted_samples"] == 2
    assert [r["record"] for r in result["failed_records"]] == ["bad.csv"]
    assert len(PdfReader(result["sample_sheet_report"]).outline) == 2
    assert all((run / name).is_file() for name in result["sample_reports"].values())
    assert query(run, "runs.xlsx#Twist", row=3)["points"][-1]["torque_Nm"] == 1.25
    assert query(run, "fatigue-wave.csv", cycle=2)["amplitude"] == 45
    assert query(run, "runs.xlsx#Axial")["initial_loading_fit"][
        "modulus_GPa"
    ] == pytest.approx(55)
    assert (run / "fatigue-cycles.csv").is_file() and (
        run / "protocol-metrics.csv"
    ).is_file()

    class Links(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for k, v in attrs:
                if k in ("href", "src"):
                    assert (run / unquote(v)).is_file()

    Links().feed(Path(result["index"]).read_text(encoding="utf8"))
    assert status(run)["status"] == "partial"
    amended = analyze(
        root, tmp_path / "result", {**notes, "batch_note": "Second reading"}, lang="en"
    )
    assert amended["reuse"] == {"records": 3, "samples": 2}


def test_general_calibrated_fit_and_path_integral(tmp_path):
    r = analysis("multi-channel.tsv")
    fit = r["curve"]["coordinate_fit"]
    assert fit["source_rows"] == list(range(2, 13)) and fit["r2"] == pytest.approx(1)
    assert measured(r)["window_slope"]["value"] == pytest.approx(1.5)
    assert measured(r)["window_slope"]["unit"] == "mV/s"
    assert len(r["curve"]["additional_signals"]) == 2
    r = analysis("torsion.csv")
    assert measured(r)["signed_path_integral"]["value"] == pytest.approx(
        0.5 * 4.8 * 0.04
    )
    f = tmp_path / "signal.txt"
    f.write_text("Bridge signal (mV)\n2\n5\n8\n")
    r = record_analysis({"path": f, "record": f.name}, {}, {})
    assert (
        r["curve"]["x"]["key"] == "source_row"
        and measured(r)["maximum_response"]["value"] == 8
    )
    f = tmp_path / "bending.csv"
    f.write_text("deflection_mm,force_N\n0,0\n1,2\n2,\n3,6\n")
    r = record_analysis({"path": f, "record": f.name}, {}, {"fit_rows": [2, 5]})
    assert "window_slope" not in measured(r) and "signed_path_integral" not in measured(
        r
    )
    assert set(r["curve"]["warnings"]) >= {"window_unusable", "integral_gap"}


def test_single_file_sidecar_and_sibling_isolation(tmp_path):
    f = tmp_path / "specimen.tsv"
    f.write_text("Depth (um)\tForce (mN)\n1\t2\n4\t12\n")
    (tmp_path / "unrelated.csv").write_text("broken acquisition")
    f.with_name(f.name + ".mechcurve.json").write_text(
        json.dumps({"records": {f.name: {"sample": "Tip A"}}})
    )
    run = analyze(f, lang="en")
    assert run["status"] == "complete" and run["records"] == 1
    assert (
        "Tip A" in run["sample_reports"]
        and Path(run["run"]).parent.name == "specimen.tsv_MechCurve"
    )
    assert {r["record"] for r in discover(tmp_path)} == {
        "specimen.tsv",
        "unrelated.csv",
    }
    assert (
        query(run["run"], f.name)["source_columns"]["force_N"]["scale_to_canonical"]
        == 0.001
    )
