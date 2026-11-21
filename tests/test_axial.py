import json

import pytest

from mechcurve.axial import (
    branch_work,
    cycle_branches,
    cycle_landmarks,
    representative_cycles,
)
from mechcurve.mechanics import analyze_record
from mechcurve.protocols import record_analysis
from mechcurve.pipeline import axial_summary


def points(stress, strain, times=None):
    if times is None:
        times = range(len(stress))
    return [
        dict(
            source_row=i + 2,
            time_s=t,
            force_N=2 * s,
            stress_MPa=s,
            strain_pct=e,
            extension_mm=e / 4,
        )
        for i, (s, e, t) in enumerate(zip(stress, strain, times, strict=True))
    ]


def test_multistep_fracture_and_false_positives():
    p = points(
        [0, 50, 100, 78, 51, 19, 2, 1], [0, 0.1, 0.2, 0.21, 0.22, 0.23, 0.24, 0.25]
    )

    def result(pts, opts):
        return analyze_record([v.copy() for v in pts], list(pts[0]), {}, opts)

    r = result(p, {})
    e = r["event"]
    assert (e["status"], e["source_row"], e["after_row"], e["low_tail_points"]) == (
        "candidate",
        4,
        7,
        3,
    )
    assert e["drop_fraction"] == pytest.approx(0.81) and e["after"]["stress_MPa"] == 19
    assert r["tensile"]["uts_MPa"] is None
    assert result(p, {"fractured": True})["event"]["status"] == "confirmed_row"
    assert result(p, {"break_before_row": 3})["event"]["after_row"] is None
    for kind in ("unload", "clock_reset", "row_gap", "reload"):
        q = [v.copy() for v in p]
        if kind == "unload":
            for item in q[3:]:
                item["extension_mm"] = 0.001
        elif kind == "clock_reset":
            q[3]["time_s"] = -1
        elif kind == "row_gap":
            for item in q[3:]:
                item["source_row"] += 1
        else:
            q[-1].update(force_N=150, stress_MPa=75)
        event = result(q, {})["event"]
        if kind in ("clock_reset", "row_gap", "unload"):
            # A later measured decline can only refer to its own continuous interval.
            assert event["source_row"] != 4
        else:
            assert event["status"] == "unlocated"


def test_no_gauge_elongation_from_completion_alone():
    p = points([0, 50, 100], [0, 0.1, 0.2])
    opts = dict(complete=True, original_gauge_mm=10, final_gauge_mm=12)
    r = analyze_record(p, list(p[0]), {}, opts)
    assert (
        r["tensile"]["uts_MPa"] == 100
        and r["tensile"]["elongation_after_break_pct"] is None
    )


def test_signed_work_secants_gaps_and_open_path():
    p = points([0, 100, 0], [0, 1, 0.2])
    c = dict(status="complete", local_cycle=1, start_row=2, turn_row=3, end_row=4)
    b = cycle_branches(p, [c])[0]
    assert b["loading_secant_GPa"] == 10 and b["unloading_secant_GPa"] == 12.5
    assert (
        b["loading_work_MJ_m3"],
        b["returned_work_MJ_m3"],
        b["net_work_MJ_m3"],
    ) == pytest.approx((0.5, 0.4, 0.1))
    p[1]["stress_MPa"] = None
    assert (
        branch_work(p) is None and cycle_branches(p, [c])[0]["net_work_MJ_m3"] is None
    )
    assert cycle_branches(p, [{**c, "status": "partial_unload"}]) == []


def test_gauge_signal_derivation_and_precedence(tmp_path):
    p = tmp_path / "拉断.csv"
    p.write_text(
        "Extensometer extension (mm),Tensile load (N)\n0,0\n.01,100\n.02,200\n.03,300\n",
        encoding="utf8",
    )
    desc = {"record": p.name, "path": p}
    g = {"fixture": "rectangular_section", "width_mm": 2, "thickness_mm": 1}
    r = record_analysis(desc, {}, {"geometry": g, "original_gauge_mm": 20})
    assert r["test_type"] == "tension" and r["initial_loading_fit"][
        "modulus_GPa"
    ] == pytest.approx(100)
    assert (
        r["points"][2]["strain_pct"] == pytest.approx(0.1)
        and r["points"][2]["stress_MPa"] == 100
    )
    assert r["axial_derivation"]["strain_source"] == "gauge_extension_mm"
    p.write_text("Displacement (mm),Tensile load (N)\n0,0\n.01,100\n.02,200\n")
    r = record_analysis(desc, {}, {"geometry": g, "original_gauge_mm": 20})
    assert all(v["strain_pct"] is None for v in r["points"])
    p.write_text(
        "strain_pct,stress_MPa,force_N,gauge_extension_mm\n0,0,0,0\n.1,30,500,.5\n.2,55,900,.8\n"
    )
    r = record_analysis(desc, {}, {"geometry": g, "original_gauge_mm": 20})
    assert r["points"][-1]["stress_MPa"] == 55 and r["points"][-1]["strain_pct"] == 0.2
    assert (
        "stress_source" not in r["axial_derivation"]
        and "strain_source" not in r["axial_derivation"]
    )


def test_representative_table_keeps_ties_failed_and_incomplete():
    records = [{"record": "a", "cycles": []}, {"record": "b", "cycles": []}]
    pairs = []
    for i in range(1, 41):
        rec = records[i > 18]
        c = dict(
            cycle=i,
            status="complete" if i < 40 else "partial_loading",
            fully_recoverable=i in (2, 7, 19) if i < 40 else None,
            total_strain_pp=1.5 if i in (7, 19) else 0.8,
            residual_segment_pp=0.028 if i in (2, 7, 19) else 0.04,
            end_stress_MPa=5,
            turn_row=3,
            end_row=6,
        )
        rec["cycles"].append(c)
        pairs.append((rec, c))
    out = cycle_landmarks(records)
    assert out["first_nonqualifying"]["cycle"] == 1
    assert [(c["record"], c["cycle"]) for c in out["highest_qualifying"]] == [
        ("a", 7),
        ("b", 19),
    ]
    shown = [c["cycle"] for _, c in representative_cycles(pairs, 11)]
    assert {1, 7, 19, 40} <= set(shown) and len(shown) == 11


def test_legacy_summary_excludes_trials(tmp_path):
    fake = {
        "sample": "S",
        "record": "s.csv",
        "plot_role": "main",
        "history": "cyclic",
        "cycles": [],
        "initial_loading_fit": {"modulus_GPa": 40},
        "event": {"status": "unlocated"},
        "tensile": {},
        "peak_stress": None,
    }
    (tmp_path / "results.json").write_text(
        json.dumps(
            {
                "records": [
                    fake,
                    {**fake, "record": "trial.csv", "plot_role": "preliminary"},
                ]
            }
        )
    )
    s = axial_summary(tmp_path, "S")
    assert s["formal_records"] == ["s.csv"] and s["preliminary_records"] == [
        "trial.csv"
    ]


def test_demo_matched_target_and_distinct_fracture_landmarks():
    from pathlib import Path
    from mechcurve.axial import specimen_axial_summary

    base = Path(__file__).resolve().parents[1] / "examples/demo"
    notes = json.loads((base / "notes.json").read_text(encoding="utf8"))["records"]

    def records(names):
        group = []
        offset = 0
        for name in names:
            r = record_analysis({"record": name, "path": base / name}, {}, notes[name])
            r.update(record=name, plot_role="main")
            for c in r["cycles"]:
                c["cycle"] = offset + c["local_cycle"]
            offset += len(r["cycles"])
            group.append(r)
        return group

    repeated = specimen_axial_summary(records(["resumed-b1.csv", "resumed-b2.csv"]))[
        "repeated_targets"
    ]
    assert len(repeated) == 1 and (
        repeated[0]["earlier"]["cycle"],
        repeated[0]["later"]["cycle"],
    ) == (3, 4)
    assert (
        repeated[0]["residual_change_pp"] is None
        and repeated[0]["peak_stress_change_MPa"] is not None
    )
    t = specimen_axial_summary(records(["tensile-c.csv"]))["terminal_records"][0]
    assert t["peak_stress_row"] < t["before_row"] < t["after_row"]
    assert t["uts_MPa"] == pytest.approx(399.85) and t[
        "strain_at_peak_stress_pct"
    ] == pytest.approx(3)
    assert t["before"]["strain_pct"] == pytest.approx(3.45) and t[
        "elongation_after_break_pct"
    ] == pytest.approx(2.9)
    assert t["rp02_strain_pct"] == pytest.approx(t["rp02_MPa"] / 580 + 0.2)
