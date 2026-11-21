import numpy as np
import pytest

from mechcurve.inputs import read_points
from mechcurve.mechanics import analyze_record, fully_recoverable, recovery_summary
from mechcurve.pipeline import replicate_statistics


def points(strain, stress):
    return [
        dict(
            source_row=i + 2,
            time_s=float(i),
            extension_mm=float(x) * 100,
            strain_pct=float(x) * 100,
            stress_MPa=float(y),
            force_N=float(y) * 2,
        )
        for i, (x, y) in enumerate(zip(strain, stress))
    ]


def test_strict_residual_threshold_and_observed_maximum():
    cases = [
        ("complete", -0.012, 1.75, True),
        ("complete", 0.029, 1.75, True),
        ("complete", 0.030, 2.0, False),
        ("complete", 0.031, 2.1, False),
        ("partial_unload", 0.0, 2.5, None),
        ("complete", None, 2.6, None),
        ("complete", float("nan"), 2.7, None),
    ]
    cycles = []
    for i, (status, residual, applied, expected) in enumerate(cases, 1):
        decision = fully_recoverable(status, residual)
        assert decision is expected
        cycles.append(
            dict(cycle=i, fully_recoverable=decision, total_strain_pp=applied)
        )
    summary = recovery_summary(cycles)
    assert (
        summary["fully_recoverable_cycles"],
        summary["recovery_assessed_cycles"],
    ) == (2, 4)
    assert summary["max_fully_recoverable_applied_pct"] == 1.75
    assert summary["max_fully_recoverable_cycle_numbers"] == [1, 2]
    assert recovery_summary(cycles[2:])["max_fully_recoverable_applied_pct"] is None


def tensile_fixture():
    x = np.linspace(0, 0.028, 281)
    y = np.where(x <= 0.005, 60000 * x, 300 + 2000 * (x - 0.005))
    return points(np.r_[x, 0.0281, 0.0282], np.r_[y, 2, 1])


def test_fracture_fit_and_reference_lengths():
    ps = tensile_fixture()
    r = analyze_record(
        ps,
        list(ps[0]),
        {},
        {"fractured": True, "original_gauge_mm": 10, "final_gauge_mm": 11},
    )
    assert r["event"]["status"] == "confirmed_row"
    assert r["event"]["source_row"] == 282
    assert r["history"] == "tension"
    t = r["tensile"]
    assert t["modulus_GPa"] == pytest.approx(60)
    assert t["rp02_MPa"] == pytest.approx(304.137931, abs=0.00001)
    assert t["uts_MPa"] == pytest.approx(346)
    assert t["elongation_after_break_pct"] == 10


def test_signal_alone_is_candidate_and_stop_is_not_break():
    ps = tensile_fixture()
    a = analyze_record(ps, list(ps[0]), {}, {})
    assert a["event"]["status"] == "candidate" and a["tensile"]["uts_MPa"] is None
    ps = ps[:100]
    b = analyze_record(ps, list(ps[0]), {}, {})
    assert b["event"]["status"] == "unlocated" and b["tensile"]["uts_MPa"] is None


def test_first_loading_modulus_uses_relative_window_and_free_intercept():
    eps = [
        -0.4,
        -0.38,
        -0.35,
        -0.325,
        -0.30,
        -0.275,
        -0.25,
        -0.20,
        -0.30,
        -0.39,
        -0.25,
        -0.12,
    ]
    stress = [30, 35, 81, 101, 121, 141, 161, 190, 90, 31, 91, 160]
    ps = points(np.array(eps) / 100, stress)
    result = analyze_record(ps, list(ps[0]), {}, {"history": "cyclic"})
    fit = result["initial_loading_fit"]
    assert fit["source_rows"] == [4, 5, 6, 7, 8]
    assert fit["modulus_GPa"] == pytest.approx(80)
    assert fit["r2"] == pytest.approx(1)
    assert fit["measured_min_pct"] == 0.05 and fit["measured_max_pct"] == 0.15


def test_cannot_borrow_points_from_second_cycle_for_first_loading_modulus():
    ps = points(
        [0, 0.0005, 0.001, 0.0003, 0, 0.0005, 0.001, 0.0015, 0.002],
        [2, 30, 60, 20, 2, 20, 40, 60, 80],
    )
    fit = analyze_record(ps, list(ps[0]), {}, {"history": "cyclic"})[
        "initial_loading_fit"
    ]
    assert fit["modulus_GPa"] is None
    assert max(fit["source_rows"]) == 4


def test_cycle_then_break_keeps_both_events():
    x = [0, 0.001, 0.002, 0.0013, 0.0005, 0.0015, 0.003, 0.004, 0.0041, 0.0042]
    y = [2, 21, 40, 25, 3, 30, 60, 80, 1, 0]
    p = points(x, y)
    r = analyze_record(p, list(p[0]), {}, {"history": "cyclic", "fractured": True})
    assert [c["status"] for c in r["cycles"]] == ["complete", "fracture_confirmed"]
    assert r["cycles"][0]["recoverable_pp"] == pytest.approx(0.15)
    assert r["cycles"][1]["end_row"] is None
    assert r["event"]["before"]["stress_MPa"] == 80


def test_interrupted_unload_and_missing_sample():
    p = points([0, 0.001, 0.002, 0.0019, 0.0018, 0.0017], [0, 20, 40, 38, 35, 33])
    r = analyze_record(p, list(p[0]), {}, {"history": "cyclic"})
    assert r["cycles"][0]["status"] == "partial_unload"
    assert r["cycles"][0]["recoverable_pp"] is None
    p[2]["force_N"] = None
    r = analyze_record(p, list(p[0]), {}, {"history": "cyclic"})
    assert r["blocks"] == 2 and p[2]["phase"] == "unclassified"


def test_generic_units_duplicate_timestamps_and_missing_strain(tmp_path):
    f = tmp_path / "load.csv"
    f.write_text("Time [ms],Force [kN],Extension [mm]\n0,0,0\n250,.5,1\n250,.51,1\n")
    p, cols = read_points(f)
    r = analyze_record(p, cols, {}, {"area_mm2": 2})
    assert [q["time_s"] for q in p] == [0, 0.25, 0.25]
    assert [q["source_row"] for q in p] == [2, 3, 4]
    assert p[-1]["stress_MPa"] == 255 and p[-1]["strain_pct"] is None
    assert r["tensile"]["modulus_GPa"] is None
    f.write_text("Time [s],Force [unrecognized]\n0,1\n")
    with pytest.raises(ValueError):
        read_points(f)


def test_group_statistics_do_not_pool_repeat_cycles():
    cs = [
        dict(
            sample=name,
            replicate_group="A",
            target_axis="strain_pct",
            target_value=1,
            target_lower_MPa=10,
            max_stress_MPa=v,
            max_strain_pct=1,
            recoverable_pp=0.9,
            residual_segment_pp=0.1,
        )
        for name, v in [("a", 100), ("a", 90), ("b", 120)]
    ]
    stats = [s for s in replicate_statistics(cs) if s["metric"] == "max_stress_MPa"]
    assert [(s["occurrence"], s["n"], s["mean"]) for s in stats] == [
        (1, 2, 110),
        (2, 1, 90),
    ]
    assert stats[0]["sd"] == pytest.approx(14.1421356) and stats[1]["sd"] is None
