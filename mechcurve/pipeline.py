"""Run a versioned analysis, reuse verified artifacts, and publish atomically."""

import csv
import hashlib
import json
import os
import re
import shutil
import statistics
import tempfile
from collections import Counter, defaultdict
from importlib.metadata import version
from pathlib import Path

from . import __version__
from .inputs import (
    acquisition_notes,
    discover,
    digest,
    link_continuations,
    locate_inputs,
    metadata,
)
from . import protocol_reports as views
from .protocols import record_analysis, TITLES
from .index import write_index, publish_index
from .mechanics import recovery_summary
from time import perf_counter
from pypdf import PdfReader, PdfWriter
from .locale import render_context, tr, language
from .figures import configure, font_files, merged_figure, render_segment, segment_files
from .reports import batch_report, sample_report
from .sheets import sample_sheet


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2),
        encoding="utf-8",
    )


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_table(path, rows, default_columns):
    keys = list(dict.fromkeys(k for row in rows for k in row)) or default_columns
    with path.open("w", encoding="utf-8-sig", newline="") as fp:
        writer = csv.DictWriter(fp, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def slug(value):
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")[:65]
    return (name or "sample") + "_" + fingerprint(value)[:6]


def status(folder, deep=True):
    receipt = read_json(folder / "run.json")
    lang = receipt.get("language", "zh")
    if deep:
        for name, expected in receipt["artifacts"].items():
            path = folder / name
            if not path.is_file() or digest(path) != expected:
                raise ValueError(f"结果文件校验失败 {name}")
    return {
        "run": str(folder.resolve()),
        "status": receipt["status"],
        **receipt["counts"],
        "report": str((folder / tr("批次报告.pdf", lang=lang)).resolve()),
        **(
            {"index": str((folder / tr("报告索引.html", lang=lang)).resolve())}
            if tr("报告索引.html", lang=lang) in receipt["artifacts"]
            else {}
        ),
        "sample_reports": receipt["sample_reports"],
        **(
            {
                "sample_sheet_report": str(
                    (folder / tr("每个样品一页.pdf", lang=lang)).resolve()
                )
            }
            if receipt.get("one_page_reports")
            else {}
        ),
        "failed_records": receipt["errors"],
        "reuse": receipt["reuse"],
        "language": lang,
        "stage_metrics": receipt.get("stage_metrics", {}),
    }


def previous_runs(out):
    runs = []
    for p in out.glob("run-*/run.json"):
        try:
            runs.append((p.parent, read_json(p)))
        except (OSError, ValueError):
            continue
    return runs


def reuse(previous, kind, key, stage, destination):
    for old, receipt in previous:
        paths = receipt.get("cache", {}).get(kind, {}).get(key, [])
        if not paths or any(
            not (old / p).is_file() or digest(old / p) != receipt["artifacts"].get(p)
            for p in paths
        ):
            continue
        for p in paths:
            dest = stage / destination / Path(p).name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old / p, dest)
        return True
    return False


def replicate_statistics(comparisons):
    buckets = defaultdict(dict)
    occurrences = defaultdict(int)
    for c in comparisons:
        if not c["replicate_group"]:
            continue
        bucket = (
            c["replicate_group"],
            c["target_axis"],
            c["target_value"],
            c["target_lower_MPa"],
        )
        occurrences[c["sample"], bucket] += 1
        order = occurrences[c["sample"], bucket]
        for k in (
            "max_stress_MPa",
            "max_strain_pct",
            "recoverable_pp",
            "residual_segment_pp",
        ):
            if c[k] is not None:
                buckets[*bucket, order, k][c["sample"]] = c[k]
    rows = []
    for (group, axis, target, lower, order, metric), values in buckets.items():
        rows.append(
            {
                "group": group,
                "target_axis": axis,
                "target_value": target,
                "lower_MPa": lower,
                "occurrence": order,
                "metric": metric,
                "n": len(values),
                "mean": statistics.mean(values.values()),
                "sd": statistics.stdev(values.values()) if len(values) > 1 else None,
            }
        )
    return rows


def validate_notes(options, record_ids):
    if set(options) - {"records", "batch_note", "batch_interpretation"}:
        raise ValueError("备注含未知顶层字段")
    allowed = {
        "test_type",
        "axes",
        "geometry",
        "header_row",
        "hold_rows",
        "fit_rows",
        "sample",
        "sequence",
        "replicate_group",
        "plot_role",
        "area_mm2",
        "history",
        "complete",
        "fractured",
        "break_before_row",
        "original_gauge_mm",
        "final_gauge_mm",
        "fit_fraction",
        "reversal_threshold",
        "targets",
        "interpretation",
    }
    overrides = options.get("records", {})
    for rid, fields in overrides.items():
        if rid not in record_ids or set(fields) - allowed:
            raise ValueError(f"无效记录或未知备注字段 {rid}")
        if "sequence" in fields and (
            type(fields["sequence"]) is not int or fields["sequence"] < 1
        ):
            raise ValueError("sequence must be a positive integer")
        if "test_type" in fields and fields["test_type"] not in TITLES:
            raise ValueError(f"Unknown test_type for {rid}: {fields['test_type']}")
        if (
            "history" in fields
            and fields.get("test_type", fields["history"]) != fields["history"]
        ):
            raise ValueError(f"Conflicting history and test_type for {rid}")
        if "axes" in fields and (
            not isinstance(fields["axes"], dict)
            or set(fields["axes"]) != {"x", "y"}
            or not all(isinstance(v, str) and v for v in fields["axes"].values())
        ):
            raise ValueError("axes requires x and y column names")
        if "geometry" in fields and not isinstance(fields["geometry"], dict):
            raise ValueError("geometry must be an object")
        if "header_row" in fields and (
            type(fields["header_row"]) is not int or fields["header_row"] < 1
        ):
            raise ValueError("header_row must be a positive integer")
        for window in ("hold_rows", "fit_rows"):
            if window not in fields:
                continue
            bounds = fields[window]
            if (
                not isinstance(bounds, list)
                or len(bounds) != 2
                or any(type(i) is not int or i < 1 for i in bounds)
                or bounds[1] <= bounds[0]
            ):
                raise ValueError(f"{window} requires two increasing source row numbers")
        if "history" in fields and fields["history"] not in ("cyclic", "tension"):
            raise ValueError("history 必须为 cyclic 或 tension")
        if fields.get("plot_role", "main") not in ("main", "preliminary"):
            raise ValueError("plot_role 必须为 main 或 preliminary")
        for s in fields.get("targets", []):
            if s.get("axis") not in (
                "strain_pct",
                "stress_MPa",
                "force_N",
            ) or not isinstance(s.get("target"), (int, float)):
                raise ValueError("targets 需要物理通道与数值目标")
            s.setdefault("lower_MPa", None)
    claims = [
        *options.get("batch_interpretation", []),
        *(a for fields in overrides.values() for a in fields.get("interpretation", [])),
    ]
    for a in claims:
        if (
            not a.get("heading")
            or not a.get("text")
            or a.get("record") not in record_ids
            or not isinstance(a.get("row"), int)
        ):
            raise ValueError("报告补充解释需要 heading、text、record 和原始 row")
    return claims


def select_figures(records, overrides):
    for r in records:
        role = overrides.get(r["record"], {}).get("plot_role")
        r["plot_role"] = "main"
        r["plot_reason"] = "正式记录"
        if r["event"]["status"] != "unlocated":
            r["plot_reason"] = "保留断裂事件判读图"
            continue
        if role:
            r.update(plot_role=role, plot_reason="实验备注指定用途")
            continue
        parent = Path(r["record"]).parent
        idx = r["metadata"].get("specimen_index")
        complete = sum(c["status"] == "complete" for c in r["cycles"])
        if idx is None or complete > 1 or not r["event"]["ends_under_load"]:
            continue
        for other in records:
            other_idx = other["metadata"].get("specimen_index")
            if (
                Path(other["record"]).parent != parent
                or other_idx is None
                or other_idx <= idx
            ):
                continue
            if (
                r["metadata"].get("steps") != other["metadata"].get("steps")
                or r["area_mm2"] != other["area_mm2"]
            ):
                continue
            if (
                len(r["points"]) <= 0.1 * len(other["points"])
                and sum(c["status"] == "complete" for c in other["cycles"]) >= 3
            ):
                r.update(
                    plot_role="preliminary",
                    plot_reason=f"同试验包 S{other_idx} 随后完成多周加载；本条仅 {len(r['points'])} 点、{complete} 个完整周，终止于加载途中。疑似初始试运行。",
                )
                break


def analyze(source, output=None, notes=None, lang="zh"):
    with render_context(lang):
        return _analyze(source, output, notes)


def _analyze(source, output, notes):
    requested = Path(source).resolve(strict=True)
    source, files = locate_inputs(requested)
    scope = requested if requested.is_file() else source
    default_output = scope.with_name(scope.name + "_MechCurve")
    out = Path(output).resolve() if output else default_output
    if out == scope or scope in out.parents or out in scope.parents:
        raise ValueError("结果目录与输入目录必须分开存放")
    options = acquisition_notes(scope, notes)
    records = discover(source, files)
    if not records:
        raise ValueError("目录内没有 CSV 采样记录")
    link_continuations(records)
    overrides = options.get("records", {})
    claims = validate_notes(options, {r["record"] for r in records})
    hashes = {p.relative_to(source).as_posix(): digest(p) for p in sorted(files)}
    code_dir = Path(__file__).parent
    code = {p.name: digest(p) for p in sorted(code_dir.glob("*.py"))}
    runtime = {n: version(n) for n in ("numpy", "matplotlib", "pypdf", "openpyxl")}
    face = configure()
    fonts = {weight: digest(path) for weight, path in font_files(face).items()}
    key = fingerprint(
        [str(source), hashes, options, code, runtime, face, fonts, language()]
    )
    out.mkdir(parents=True, exist_ok=True)
    previous = previous_runs(out)
    final = out / ("run-" + key[:12])
    if final.exists():
        try:
            checked_run = status(final)
        except (OSError, ValueError, KeyError):
            final = out / ("run-" + key[:12] + "-repair-" + os.urandom(3).hex())
        else:
            return publish_index(final, checked_run)
    with tempfile.TemporaryDirectory(prefix=".pending-", dir=out) as temp:
        stage = Path(temp) / "delivery"
        stage.mkdir()
        errors = []
        analyzed = []
        cache = {
            kind: {} for kind in ("record", "segment", "detail", "sheet", "merged")
        }
        metrics = {kind: {"reused": 0, "built": 0, "seconds": 0.0} for kind in cache}
        render_style = [
            language(),
            face,
            fonts,
            runtime,
            code["figures.py"],
            code["locale.py"],
            code["translations.py"],
        ]

        def materialize(kind, signature, dest, filenames, build):
            start = perf_counter()
            key = fingerprint([signature, render_style])
            hit = reuse(previous, kind, key, stage, dest)
            if not hit:
                build()
            cache[kind][key] = [(dest / f).as_posix() for f in filenames]
            metrics[kind]["reused" if hit else "built"] += 1
            metrics[kind]["seconds"] += perf_counter() - start
            return hit

        reused = {"records": 0, "samples": 0}
        for desc in records:
            start = perf_counter()
            rid = desc["record"]
            opts = overrides.get(rid, {})
            deps = {
                p.relative_to(source).as_posix(): hashes[
                    p.relative_to(source).as_posix()
                ]
                for p in (desc["path"], desc["xml"], desc["binary"])
                if p is not None
            }
            physics = {
                k: v
                for k, v in opts.items()
                if k
                not in (
                    "sample",
                    "sequence",
                    "replicate_group",
                    "interpretation",
                    "plot_role",
                )
            }
            rk = fingerprint(
                [
                    rid,
                    deps,
                    physics,
                    code["inputs.py"],
                    code["mechanics.py"],
                    code["channels.py"],
                    code["tableio.py"],
                    code["protocols.py"],
                    code["histories.py"],
                    runtime["openpyxl"] if desc.get("sheet") else None,
                    runtime["numpy"],
                ]
            )
            datafile = Path("records") / (rk + ".json")
            try:
                if reuse(previous, "record", rk, stage, datafile.parent):
                    result = read_json(stage / datafile)
                    reused["records"] += 1
                    metrics["record"]["reused"] += 1
                else:
                    try:
                        meta = metadata(desc["xml"], desc["index"])
                    except (
                        ValueError,
                        OSError,
                        SyntaxError,
                        AttributeError,
                        IndexError,
                    ) as exc:
                        meta = {"metadata_warning": "XML 解析失败 " + str(exc)}
                    result = record_analysis(desc, meta, physics)
                    write_json(stage / datafile, result)
                    metrics["record"]["built"] += 1
                cache["record"][rk] = [datafile.as_posix()]
                result.update(
                    record=rid,
                    sample=opts.get("sample", desc["sample"]),
                    cache_key=rk,
                    record_json=datafile.as_posix(),
                    replicate_group=opts.get("replicate_group"),
                    interpretation=opts.get("interpretation", []),
                    order=opts.get("sequence"),
                    continuation=desc.get("continuation", False),
                )
                analyzed.append(result)
            except (ValueError, OSError, IndexError, TypeError) as exc:
                errors.append({"record": rid, "reason": str(exc)})
            finally:
                metrics["record"]["seconds"] += perf_counter() - start
        analyzed.sort(
            key=lambda r: (
                r["sample"],
                r["order"]
                if r["order"] is not None
                else r["metadata"].get("acquisition_time")
                or (1 if r["continuation"] else 0),
                r["record"],
            )
        )
        axial = [r for r in analyzed if "curve" not in r]
        select_figures(axial, overrides)
        for r in analyzed:
            if "curve" in r:
                r["plot_role"] = overrides.get(r["record"], {}).get("plot_role", "main")
                r["plot_reason"] = (
                    "实验备注指定用途"
                    if r["plot_role"] == "preliminary"
                    else "正式记录"
                )
        if claims:
            row_ids = {
                r["record"]: {p["source_row"] for p in r["points"]} for r in analyzed
            }
            if any(a["row"] not in row_ids.get(a["record"], set()) for a in claims):
                raise ValueError("报告补充解释引用的采样行不存在")
        groups = defaultdict(list)
        for r in analyzed:
            groups[r["sample"]].append(r)
        comparisons = []
        cycle_rows = []
        point_rows = []
        summaries = []
        reports = {}
        one_pages = {}
        moduli = []
        recovery_by_sample = {}
        profile_metrics = []
        multi_protocol = len(axial) != len(analyzed)
        for name, items in groups.items():
            formal = [r for r in items if r["plot_role"] == "main"]
            profile_view = any("curve" in r for r in items)
            axial_formal = [r for r in formal if "curve" not in r]
            fit = {}
            if axial_formal:
                fit = {
                    "sample": name,
                    "record": axial_formal[0]["record"],
                    **axial_formal[0]["initial_loading_fit"],
                }
                moduli.append(fit)
            first_point, first_cycle = len(point_rows), len(cycle_rows)
            cycle_offset = 0
            for seq, r in enumerate(items, 1):
                r["sequence"] = seq
                ident = {
                    "sample": name,
                    "record": r["record"],
                    "segment": seq,
                    "plot_role": r["plot_role"],
                }
                for c in r["cycles"]:
                    c["cycle"] = cycle_offset + c["local_cycle"]
                    row = {**ident, **c}
                    cycle_rows.append(row)
                    if (
                        r["plot_role"] == "main"
                        and c["status"] == "complete"
                        and c["target_axis"]
                    ):
                        comparisons.append(
                            {**row, "replicate_group": r["replicate_group"]}
                        )
                r["recovery_summary"] = recovery_summary(r["cycles"])
                for p in r["points"]:
                    point_rows.append(
                        {
                            **ident,
                            **p,
                            "cycle": cycle_offset + p["local_cycle"]
                            if p["local_cycle"]
                            else None,
                        }
                    )
                cycle_offset += len(r["cycles"])
                if "curve" in r:
                    summaries.append(
                        {
                            **ident,
                            "history": r["history"],
                            "test_type": r["test_type"],
                            "classification": r["classification"],
                            "profile_view": True,
                            "points": len(r["points"]),
                            "complete_cycles": 0,
                            "plot_reason": r["plot_reason"],
                        }
                    )
                    continue
                peak = r["peak_observed"] or {}
                t = r["tensile"]
                event = r["event"]
                before = event["before"] or {}
                last = next(
                    (c for c in reversed(r["cycles"]) if c["status"] == "complete"), {}
                )
                summaries.append(
                    {
                        **ident,
                        **(
                            {
                                "test_type": r["test_type"],
                                "classification": r["classification"],
                                "profile_view": profile_view,
                            }
                            if multi_protocol
                            else {}
                        ),
                        "last_complete_cycle": last.get("cycle"),
                        **r["recovery_summary"],
                        **{
                            "last_" + field: last.get(field)
                            for field in (
                                "peak_force_N",
                                "stress_at_peak_MPa",
                                "strain_at_peak_pct",
                                "max_strain_pct",
                                "total_strain_pp",
                                "recoverable_pp",
                                "residual_segment_pp",
                                "residual_increment_pp",
                                "end_stress_MPa",
                                "peak_force_row",
                                "turn_row",
                                "end_row",
                            )
                        },
                        "points": len(r["points"]),
                        "complete_cycles": sum(
                            c["status"] == "complete" for c in r["cycles"]
                        ),
                        "history": r["history"],
                        "plot_reason": r["plot_reason"],
                        "terminal_phase": r["points"][-1]["phase"],
                        "break_status": event["status"],
                        "break_before_row": event["source_row"],
                        "break_force_N": before.get("force_N"),
                        "break_stress_MPa": before.get("stress_MPa"),
                        "break_strain_pct": before.get("strain_pct"),
                        "peak_observed_force_N": peak.get("force_N"),
                        "peak_row": peak.get("source_row"),
                        "max_stress_MPa": (r["peak_stress"] or {}).get("stress_MPa"),
                        "area_mm2": r["area_mm2"],
                        "area_crosscheck_relative_error": r["area_relative_error"],
                        "uts_MPa": t.get("uts_MPa"),
                        "modulus_GPa": fit.get("modulus_GPa")
                        if r["plot_role"] == "main"
                        else None,
                        "modulus_source_record": fit.get("record")
                        if r["plot_role"] == "main"
                        else None,
                        "rp02_MPa": t.get("rp02_MPa"),
                        "elongation_after_break_pct": t.get(
                            "elongation_after_break_pct"
                        ),
                    }
                )
                if r["plot_role"] == "main":
                    r["sample_modulus"] = fit
            annotations = [a for r in items for a in r["interpretation"]]
            if axial_formal:
                recovery_by_sample[name] = recovery_summary(
                    c for r in formal for c in r["cycles"]
                )
            dest = Path("specimens" if language() == "en" else "样品") / slug(name)
            folder = stage / dest
            folder.mkdir(parents=True, exist_ok=True)
            identity = [
                (r["cache_key"], r["sequence"], r["plot_role"], r["plot_reason"])
                for r in items
            ]
            reports[name] = (dest / tr("样品报告.pdf")).as_posix()
            if formal:
                one_pages[name] = (dest / tr("样品单页.pdf")).as_posix()
            if multi_protocol:
                for r in items:
                    for m in views.curve_of(r)["metrics"]:
                        profile_metrics.append(
                            {
                                "sample": name,
                                "record": r["record"],
                                "test_type": r["test_type"],
                                "plot_role": r["plot_role"],
                                **m,
                            }
                        )
            if len(formal) > 1:
                merged_points = [
                    p for p in point_rows[first_point:] if p["plot_role"] == "main"
                ]
                merged_cycles = [
                    c for c in cycle_rows[first_cycle:] if c["plot_role"] == "main"
                ]
                merged_points = [
                    dict(sample_point_1based=i, **p)
                    for i, p in enumerate(merged_points, 1)
                ]
                write_table(
                    stage / dest / tr("合并逐点.csv"),
                    merged_points,
                    ["record", "source_row"],
                )
                write_table(
                    stage / dest / tr("合并逐周.csv"),
                    merged_cycles,
                    ["record", "cycle"],
                )
            if profile_view:
                signature = [name, identity, code["protocol_reports.py"]]
                hits = []
                for r in formal:
                    seq = r["sequence"]
                    hits.append(
                        materialize(
                            "segment",
                            [
                                name,
                                r["cache_key"],
                                seq,
                                [c["cycle"] for c in r["cycles"]],
                                code["protocol_reports.py"],
                            ],
                            dest,
                            views.record_asset_paths(seq),
                            lambda: views.record_figure(folder, name, r),
                        )
                    )
                hits.append(
                    materialize(
                        "detail",
                        [signature, annotations, code["reports.py"]],
                        dest,
                        [tr("样品报告.pdf")],
                        lambda: views.specimen_detail(folder, name, items),
                    )
                )
                if formal:
                    hits.append(
                        materialize(
                            "sheet",
                            signature,
                            dest,
                            [tr("样品单页.pdf")],
                            lambda: views.specimen_sheet(folder, name, formal),
                        )
                    )
                reused["samples"] += int(all(hits))
                continue
            max_cycle = max(
                (
                    c["cycle"]
                    for r in formal
                    for c in r["cycles"]
                    if c["status"] == "complete"
                ),
                default=1,
            )
            hits = []
            for r in formal:
                seq = r["sequence"]
                signature = [
                    name,
                    r["cache_key"],
                    seq,
                    [c["cycle"] for c in r["cycles"]],
                    max_cycle,
                    r.get("sample_modulus"),
                ]
                hits.append(
                    materialize(
                        "segment",
                        signature,
                        dest,
                        segment_files(seq),
                        lambda: render_segment(folder, name, r, seq, max_cycle),
                    )
                )
            hits.append(
                materialize(
                    "detail",
                    [name, identity, annotations, code["reports.py"]],
                    dest,
                    [tr("样品报告.pdf")],
                    lambda: sample_report(folder, name, items, annotations),
                )
            )
            if formal:
                hits.append(
                    materialize(
                        "sheet",
                        [name, identity, code["sheets.py"]],
                        dest,
                        [tr("样品单页.pdf")],
                        lambda: sample_sheet(folder, name, formal),
                    )
                )
            if len(formal) > 1:
                hits.append(
                    materialize(
                        "merged",
                        [name, identity],
                        dest,
                        [tr("合并回线.") + ext for ext in ("pdf", "png", "svg")],
                        lambda: merged_figure(folder, name, formal),
                    )
                )
            reused["samples"] += int(all(hits))
        comparisons.sort(
            key=lambda r: (r["target_axis"], r["target_value"], r["sample"], r["cycle"])
        )
        stats = replicate_statistics(comparisons)
        for filename, rows, columns in [
            (
                "样品弹性模量.csv",
                moduli,
                ["sample", "record", "modulus_GPa", "n", "r2"],
            ),
            ("逐点分段.csv", point_rows, ["sample", "record", "source_row", "phase"]),
            ("逐周指标.csv", cycle_rows, ["sample", "record", "cycle", "status"]),
            ("样品汇总.csv", summaries, ["sample", "record", "history"]),
            (
                "共同目标比较.csv",
                comparisons,
                ["sample", "target_axis", "target_value"],
            ),
            (
                "重复样品统计.csv",
                stats,
                ["group", "target_axis", "target_value", "metric", "n", "mean", "sd"],
            ),
        ]:
            write_table(stage / tr(filename), rows, columns)
        batch_start = perf_counter()
        if multi_protocol:
            waves = [
                {
                    "sample": r["sample"],
                    "record": r["record"],
                    "unit": r["curve"]["y"]["unit"],
                    "plot_role": r["plot_role"],
                    **c,
                }
                for r in analyzed
                if "curve" in r
                for c in r["curve"].get("fatigue_cycles", [])
            ]
            if waves:
                write_table(
                    stage / "fatigue-cycles.csv", waves, ["sample", "record", "cycle"]
                )
            write_table(
                stage / "protocol-metrics.csv",
                profile_metrics,
                [
                    "sample",
                    "record",
                    "test_type",
                    "metric",
                    "value",
                    "unit",
                    "source_rows",
                ],
            )
            views.campaign_pages(stage / tr("批次报告.pdf"), analyzed, errors, options)
            if axial:
                # Keep the established axial comparison and repeatability appendix.
                with tempfile.TemporaryDirectory(dir=stage) as tmp:
                    subset = Path(tmp)
                    batch_report(
                        subset,
                        axial,
                        comparisons,
                        stats,
                        options,
                        [],
                        [r for r in summaries if r["history"] in ("tension", "cyclic")],
                        moduli,
                        recovery_by_sample,
                    )
                    combined = PdfWriter()
                    combined.append(stage / tr("批次报告.pdf"))
                    combined.append(subset / tr("批次报告.pdf"))
                    combined.write(subset / "combined.pdf")
                    os.replace(subset / "combined.pdf", stage / tr("批次报告.pdf"))
        else:
            batch_report(
                stage,
                analyzed,
                comparisons,
                stats,
                options,
                errors,
                summaries,
                moduli,
                recovery_by_sample,
            )
        if one_pages:
            combined = PdfWriter()
            for index, (name, relative) in enumerate(one_pages.items()):
                pages = PdfReader(stage / relative).pages
                if len(pages) != 1:
                    raise ValueError(f"Expected one specimen page in {relative}")
                combined.add_page(pages[0])
                combined.add_outline_item(name, index)
            combined.write(stage / tr("每个样品一页.pdf"))
        metrics["batch"] = {"seconds": perf_counter() - batch_start}
        verify_start = perf_counter()
        write_index(stage, scope.name, summaries, reports, errors, recovery_by_sample)
        write_json(
            stage / "results.json",
            {
                "schema_version": 2,
                "records": [
                    {k: v for k, v in r.items() if k != "points"} for r in analyzed
                ],
                "statistics": stats,
                "sample_moduli": moduli,
                "recovery_by_sample": recovery_by_sample,
                "errors": errors,
                "notes": options,
            },
        )
        checked = {}
        pdfs = [
            stage / tr("批次报告.pdf"),
            *[stage / p for p in reports.values()],
            *[stage / p for p in one_pages.values()],
        ]
        if one_pages:
            pdfs.append(stage / tr("每个样品一页.pdf"))
        for pdf in pdfs:
            with pdf.open("rb") as stream:
                texts = [page.extract_text() or "" for page in PdfReader(stream).pages]
                if not texts or any(len(t.strip()) < 8 or "\ufffd" in t for t in texts):
                    raise ValueError(f"PDF 文本校验失败 {pdf.name}")
                checked[pdf.relative_to(stage).as_posix()] = len(texts)
        if any(digest(source / k) != h for k, h in hashes.items()):
            raise RuntimeError("分析期间输入文件发生变化，请基于稳定导出重跑")
        counts = {
            "records": len(analyzed),
            **(
                {
                    "protocol_counts": dict(Counter(r["test_type"] for r in analyzed)),
                    "fatigue_waveform_cycles": sum(
                        len(r.get("curve", {}).get("fatigue_cycles", []))
                        for r in analyzed
                        if r["plot_role"] == "main"
                    ),
                }
                if multi_protocol
                else {}
            ),
            "samples": len(groups),
            "points": len(point_rows),
            "plotted_records": sum(r["plot_role"] == "main" for r in analyzed),
            "formal_recovery_assessed_cycles": sum(
                s["recovery_assessed_cycles"] for s in recovery_by_sample.values()
            ),
            "formal_fully_recoverable_cycles": sum(
                s["fully_recoverable_cycles"] for s in recovery_by_sample.values()
            ),
            "plotted_samples": len(
                {r["sample"] for r in analyzed if r["plot_role"] == "main"}
            ),
            "plotted_complete_cycles": sum(
                c["plot_role"] == "main" and c["status"] == "complete"
                for c in cycle_rows
            ),
            "complete_cycles": sum(c["status"] == "complete" for c in cycle_rows),
            "partial_segments": sum(c["status"] != "complete" for c in cycle_rows),
        }
        artifacts = {
            p.relative_to(stage).as_posix(): digest(p)
            for p in stage.rglob("*")
            if p.is_file()
        }
        metrics["verification"] = {"seconds": perf_counter() - verify_start}
        write_json(
            stage / "run.json",
            {
                "schema_version": 2,
                "version": __version__,
                "fingerprint": key,
                "source": str(source),
                "requested_input": str(scope),
                "source_sha256": hashes,
                "code": code,
                "runtime": runtime,
                "font": face,
                "font_sha256": fonts,
                "language": language(),
                "stage_metrics": metrics,
                "pdf_pages": checked,
                "counts": counts,
                "status": "partial" if errors else "complete",
                "errors": errors,
                "artifacts": artifacts,
                "sample_reports": reports,
                "one_page_reports": one_pages,
                "cache": cache,
                "reuse": reused,
            },
        )
        try:
            stage.rename(final)
        except OSError:
            if not final.is_dir():
                raise
        return publish_index(final, status(final))


def query(run, record, cycle=None, row=None, radius=3):
    folder = Path(run)
    data = read_json(folder / "results.json")
    r = next((r for r in data["records"] if r["record"] == record), None)
    if not r:
        raise ValueError("未知采集记录")
    if row is not None:
        if not 0 <= radius <= 200:
            raise ValueError("radius 范围为 0–200")
        points = read_json(folder / r["record_json"])["points"]
        index = next((i for i, p in enumerate(points) if p["source_row"] == row), None)
        if index is None:
            raise ValueError("未知采样行")
        return {
            "sample": r["sample"],
            "record": record,
            "points": points[max(0, index - radius) : index + radius + 1],
        }
    if cycle is not None:
        found = next(
            (
                c
                for c in (r.get("curve", {}).get("fatigue_cycles") or r["cycles"])
                if c["cycle"] == cycle
            ),
            None,
        )
        if found is None:
            raise ValueError("该采集段无此周次")
        return found
    return r
