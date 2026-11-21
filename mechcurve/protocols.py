"""Route acquisitions by evidence and calculate measured protocol-specific quantities."""

import math
import re
from pathlib import Path
import numpy as np
from .histories import fatigue_cycles, measured_hold, whole_hold
from .channels import AXIAL
from .mechanics import analyze_record, initial_loading_fit
from .tableio import read_table

TITLES = {
    "tension": ("拉伸", "Tension"),
    "cyclic": ("循环加载", "Cyclic loading"),
    "compression": ("压缩", "Compression"),
    "flexure": ("弯曲", "Flexure"),
    "shear": ("剪切", "Shear"),
    "torsion": ("扭转", "Torsion"),
    "creep": ("蠕变", "Creep"),
    "relaxation": ("应力松弛", "Stress relaxation"),
    "fatigue": ("疲劳", "Fatigue"),
    "indentation": ("压入", "Indentation"),
    "peel": ("剥离", "Peel"),
    "generic": ("通用曲线", "General curve"),
}
HINTS = {
    "compression": r"compressi(?:on|ve)|压缩",
    "flexure": r"bend(?:ing)?|flexur(?:al|e)|弯曲|挠度",
    "shear": r"shear|剪切",
    "torsion": r"torsion|扭转",
    "creep": r"creep|蠕变",
    "relaxation": r"relaxation|松弛",
    "fatigue": r"fatigue|疲劳",
    "indentation": r"indentation|压入|压痕",
    "peel": r"peel|剥离",
    "tension": r"tensile|tension|拉伸|拉断",
    "cyclic": r"cyclic|循环加载|循环拉伸",
}
# Priority-ordered coordinate pairs. A time series alone never establishes the method.
DISP = ("extension_mm", "strain_pct")
LOAD = ("force_N", "stress_MPa")
PAIRS = {
    "compression": [
        (("strain_pct",), ("stress_MPa",)),
        (DISP, LOAD),
        (("time_s",), LOAD),
    ],
    "flexure": [
        (("flexural_strain_pct",), ("flexural_stress_MPa",)),
        (("deflection_mm", "extension_mm"), ("force_N", "flexural_stress_MPa")),
    ],
    "shear": [
        (("shear_strain_pct", "strain_pct"), ("shear_stress_MPa", "stress_MPa")),
        (DISP, ("force_N",)),
    ],
    "torsion": [
        (("angle_deg",), ("torque_Nm",)),
        (("shear_strain_pct",), ("shear_stress_MPa",)),
    ],
    "creep": [(("time_s",), ("strain_pct", "extension_mm"))],
    "relaxation": [(("time_s",), ("stress_MPa", "force_N"))],
    "fatigue": [
        (
            ("cycle_count",),
            ("amplitude_MPa", "stiffness_N_mm", "stress_MPa", "force_N", "strain_pct"),
        ),
        (("time_s",), ("stress_MPa", "force_N")),
    ],
    "indentation": [(("depth_mm", "extension_mm"), ("force_N",))],
    "peel": [(("peel_mm", "extension_mm", "time_s"), ("force_N",))],
    "generic": [
        (("strain_pct", "extension_mm"), ("stress_MPa", "force_N")),
        (("time_s",), ("force_N", "stress_MPa", "strain_pct", "extension_mm")),
    ],
}
NAMES = {
    "source_row": ("原始行", "Source row", ""),
    "time_s": ("时间", "Time", "s"),
    "extension_mm": ("位移", "Displacement", "mm"),
    "force_N": ("力", "Force", "N"),
    "strain_pct": ("应变", "Strain", "%"),
    "stress_MPa": ("应力", "Stress", "MPa"),
    "deflection_mm": ("挠度", "Deflection", "mm"),
    "flexural_stress_MPa": ("弯曲应力", "Flexural stress", "MPa"),
    "flexural_strain_pct": ("弯曲应变", "Flexural strain", "%"),
    "shear_stress_MPa": ("剪切应力", "Shear stress", "MPa"),
    "shear_strain_pct": ("剪切应变", "Shear strain", "%"),
    "torque_Nm": ("扭矩", "Torque", "N·m"),
    "angle_deg": ("转角", "Twist", "°"),
    "depth_mm": ("压入深度", "Depth", "mm"),
    "cycle_count": ("周次", "Cycle", "cycles"),
    "amplitude_MPa": ("应力幅", "Stress amplitude", "MPa"),
    "stiffness_N_mm": ("刚度", "Stiffness", "N/mm"),
    "peel_mm": ("剥离位移", "Peel travel", "mm"),
}


def classify(record, channels, labels, points, meta, opts):
    if opts.get("test_type") or opts.get("history"):
        return opts.get("test_type") or opts["history"], "notes"
    if any(v.get("unconverted") for v in labels.values()):
        return "generic", "native_units"
    if opts.get("axes"):
        return "generic", "mapped_axes"
    if meta.get("steps") or opts.get("targets"):
        return "cyclic", "loading_program"
    if "torque_Nm" in channels:
        return "torsion", "channels"
    for mode, keys in (
        ("fatigue", ("cycle_count", "amplitude_MPa")),
        ("flexure", ("deflection_mm", "flexural_stress_MPa", "flexural_strain_pct")),
        ("indentation", ("depth_mm",)),
        ("peel", ("peel_mm",)),
    ):
        if set(channels).intersection(keys):
            return mode, "channels"
    headers = " ".join(v["label"] for v in labels.values())
    name = Path(record).name
    for text, basis in ((headers, "channel_names"), (name, "record_name")):
        matches = [
            mode for mode, pattern in HINTS.items() if re.search(pattern, text, re.I)
        ]
        special = [m for m in matches if m not in ("tension", "cyclic")]
        if len(special) == 1:
            return special[0], basis
        if len(special) > 1:
            return "generic", "ambiguous"
        if basis == "channel_names" and matches == ["tension"]:
            # Instrument axes called "tensile stress" also appear on cyclic exports.
            continue
        if matches:
            return ("axial" if "cyclic" not in matches else "cyclic"), basis
    if {"shear_strain_pct", "shear_stress_MPa"} <= set(channels):
        return "shear", "channels"
    if {"time_s", "stress_MPa", "strain_pct"} <= set(channels):
        if whole_hold(points, "stress_MPa", "strain_pct"):
            return "creep", "constant_control"
        if whole_hold(points, "strain_pct", "stress_MPa"):
            return "relaxation", "constant_control"
    if "gauge_extension_mm" in channels and set(LOAD).intersection(channels):
        return "axial", "axial_channels"
    if (
        re.search(r"tensile|拉伸", headers, re.I)
        and set(LOAD).intersection(channels)
        and set(DISP).intersection(channels)
    ):
        return "axial", "channel_names"
    if {"stress_MPa", "strain_pct"} <= set(channels):
        strain = [p["strain_pct"] for p in points if p["strain_pct"] is not None]
        stress = [p["stress_MPa"] for p in points if p["stress_MPa"] is not None]
        if (
            strain
            and stress
            and min(strain) < 0
            and min(stress) < 0
            and max(strain) <= 0.02 * abs(min(strain))
            and max(stress) <= 0.02 * abs(min(stress))
        ):
            return "compression", "signed_axes"
        if strain and min(strain) < -0.1 * max(strain):
            return "generic", "ambiguous"
        return "axial", "axial_channels"
    if opts.get("fractured") and set(channels).intersection(LOAD):
        return "axial", "notes"
    return "generic", "measured_axes"


def axes_for(mode, channels, selected):
    if selected:
        return selected["x"], selected["y"]
    for xs, ys in PAIRS.get(mode, []):
        x = next((k for k in xs if k in channels), None)
        y = next((k for k in ys if k in channels), None)
        if x and y:
            return x, y
    if mode == "generic":
        if len(channels) == 1:
            return "source_row", channels[0]
        if "time_s" in channels:
            return "time_s", next(k for k in channels if k != "time_s")
        if len(channels) == 2:
            return tuple(channels)
        return "source_row", channels[0]
    raise ValueError(
        f"No unique usable axes for {mode}: {', '.join(channels)}. Set axes.x and axes.y in the record notes."
    )


def choose_coordinates(mode, basis, channels, selected, opts):
    try:
        x, y = axes_for(mode, channels, selected)
    except ValueError:
        if opts.get("test_type") or opts.get("history"):
            raise
        mode, basis = "generic", "ambiguous"
        x, y = axes_for(mode, channels, selected)
    if (
        selected
        and mode != "generic"
        and not any(x in xs and y in ys for xs, ys in PAIRS[mode])
    ):
        raise ValueError(
            f"Selected coordinates are incompatible with {mode}; use generic to plot custom axes"
        )
    return mode, basis, x, y


def axis_info(key, labels):
    if key in NAMES:
        zh, en, unit = NAMES[key]
    else:
        zh = en = labels[key]["label"]
        unit = labels[key]["unit"]
    return dict(key=key, zh=zh, en=en, unit=unit)


def record_analysis(desc, meta, opts):
    if desc.get("input_error"):
        raise ValueError(desc["input_error"])
    points, channels, labels, selected = read_table(
        desc["path"], desc.get("sheet"), opts, preserve_native=True
    )
    mode, basis = classify(desc["record"], channels, labels, points, meta, opts)
    if (
        mode in ("axial", "tension", "cyclic")
        and not (
            set(LOAD).intersection(channels)
            and set((*DISP, "gauge_extension_mm", "time_s")).intersection(channels)
        )
        and not (opts.get("test_type") or opts.get("history"))
    ):
        mode, basis = "generic", "ambiguous"
    if mode in ("axial", "tension", "cyclic"):
        if "fit_rows" in opts:
            raise ValueError(
                "Use test_type generic for an explicit coordinate-window fit; axial modulus uses the first-loading window"
            )
        if not set(LOAD).intersection(channels):
            raise ValueError("Axial response requires force or stress")
        if not set((*DISP, "gauge_extension_mm", "time_s")).intersection(channels):
            raise ValueError("Axial response requires strain, displacement or time")
        if selected:
            raise ValueError(
                "Custom coordinates require test_type generic or a supported protocol pair"
            )
        axial_opts = dict(opts)
        if mode in ("tension", "cyclic"):
            axial_opts["history"] = mode
        axial_channels = [k for k in channels if k in AXIAL]
        derivation = {}
        if "gauge_extension_mm" in channels:
            if "extension_mm" not in channels:
                for p in points:
                    p["extension_mm"] = p["gauge_extension_mm"]
                axial_channels.append("extension_mm")
                derivation["extension_source"] = "gauge_extension_mm"
            if (
                "strain_pct" not in channels
                and opts.get("original_gauge_mm") is not None
            ):
                gauge = positive(opts, "original_gauge_mm")
                for p in points:
                    delta = p["gauge_extension_mm"]
                    p["strain_pct"] = 100 * delta / gauge if delta is not None else None
                axial_channels.append("strain_pct")
                derivation.update(
                    strain_source="gauge_extension_mm", original_gauge_mm=gauge
                )
        geometry = opts.get("geometry", {})
        area = opts.get("area_mm2", meta.get("area_mm2"))
        if (
            area is None
            and geometry.get("fixture") == "solid_circular"
            and geometry.get("diameter_mm") is not None
        ):
            area = math.pi * positive(geometry, "diameter_mm") ** 2 / 4
        if (
            area is None
            and geometry.get("fixture") == "rectangular_section"
            and all(geometry.get(k) is not None for k in ("width_mm", "thickness_mm"))
        ):
            area = positive(geometry, "width_mm") * positive(geometry, "thickness_mm")
        if area is not None:
            axial_opts["area_mm2"] = area
            if "stress_MPa" not in channels and "force_N" in channels:
                derivation.update(stress_source="force_N", area_mm2=area)
        keys = [*AXIAL, "source_row"]
        if "gauge_extension_mm" in channels:
            keys.append("gauge_extension_mm")
        pts = [{k: p[k] for k in keys} for p in points]
        result = analyze_record(pts, axial_channels, meta, axial_opts)
        return {
            **result,
            "test_type": result["history"],
            "classification": basis,
            "axial_derivation": derivation,
            "source_columns": labels,
        }
    if (
        mode == "compression"
        and "force_N" in channels
        and "stress_MPa" not in channels
        and opts.get("area_mm2") is not None
    ):
        area = positive(opts, "area_mm2")
        for p in points:
            p["stress_MPa"] = p["force_N"] / area if p["force_N"] is not None else None
        channels = [*channels, "stress_MPa"]
    mode, basis, x, y = choose_coordinates(mode, basis, channels, selected, opts)
    paired = [p for p in points if p.get(x) is not None and p.get(y) is not None]
    if len(paired) < 2 and mode == "generic" and not selected:
        fallback = next(
            (k for k in channels if sum(p.get(k) is not None for p in points) >= 2),
            None,
        )
        if fallback:
            x, y = "source_row", fallback
            paired = [p for p in points if p.get(y) is not None]
    if len(paired) < 2:
        raise ValueError(f"Fewer than two finite paired observations for {x}, {y}")
    axes = [axis_info(key, labels) for key in (x, y)]
    curve = {
        "x": axes[0],
        "y": axes[1],
        "metrics": [],
        "valid_pairs": len(paired),
        "warnings": [],
    }

    if mode == "generic" and not selected:
        signals = []
        for key in channels:
            if key in (x, y):
                continue
            obs = [p for p in points if p.get(x) is not None and p.get(key) is not None]
            if not obs:
                continue
            low = min(obs, key=lambda p: p[key])
            high = max(obs, key=lambda p: p[key])
            signals.append(
                {
                    "axis": axis_info(key, labels),
                    "paired_points": len(obs),
                    "minimum": low[key],
                    "minimum_row": low["source_row"],
                    "maximum": high[key],
                    "maximum_row": high["source_row"],
                }
            )
        curve["additional_signals"] = signals

    def measure(key, value, unit, *rows):
        if not math.isfinite(value):
            raise ValueError(f"Non-finite derived metric: {key}")
        curve["metrics"].append(
            dict(metric=key, value=float(value), unit=unit, source_rows=list(rows))
        )

    hi = max(paired, key=lambda p: p[y])
    lo = min(paired, key=lambda p: p[y])
    extreme = max(paired, key=lambda p: abs(p[y]))
    yu = axes[1]["unit"]
    if "fit_rows" in opts:
        start, end = opts["fit_rows"]
        rows = [p for p in points if start <= p["source_row"] <= end]
        if not rows or [rows[0]["source_row"], rows[-1]["source_row"]] != [start, end]:
            raise ValueError("fit_rows must identify actual endpoint rows")
        fit = coordinate_fit(rows, x, y)
        if fit is None:
            curve["warnings"].append("window_unusable")
        else:
            curve["coordinate_fit"] = fit
            measure(
                "window_slope",
                fit["slope"],
                (yu or "1") + "/" + (axes[0]["unit"] or "1"),
                *fit["source_rows"],
            )
    if mode == "compression" and y == "stress_MPa":
        measure(
            "peak_compressive_stress", abs(extreme[y]), "MPa", extreme["source_row"]
        )
        if x == "strain_pct":
            fit = compression_fit(points, extreme, channels)
            curve["modulus_fit"] = fit
            if fit["modulus_GPa"] is not None:
                measure(
                    "compression_modulus",
                    fit["modulus_GPa"],
                    "GPa",
                    *fit["source_rows"],
                )
            else:
                curve["warnings"].append("fit_unavailable")
    if mode in ("creep", "relaxation"):
        hold_metrics(mode, points, channels, x, y, yu, opts, curve, measure)
    if mode == "flexure" and y == "force_N":
        g = opts.get("geometry", {})
        needed = ["width_mm", "thickness_mm", "span_mm"]
        if g.get("fixture") == "four_point_rectangular":
            needed.append("inner_span_mm")
        if g.get("fixture") in (
            "three_point_rectangular",
            "four_point_rectangular",
        ) and all(g.get(k) is not None for k in needed):
            width, thick, span = (
                positive(g, k) for k in ("width_mm", "thickness_mm", "span_mm")
            )
            inner = (
                positive(g, "inner_span_mm")
                if g["fixture"] == "four_point_rectangular"
                else 0
            )
            if inner >= span:
                raise ValueError(
                    "Inner loading span must be less than the support span"
                )
            measure(
                "nominal_flexural_stress",
                1.5 * abs(extreme[y]) * (span - inner) / (width * thick**2),
                "MPa",
                extreme["source_row"],
            )
        else:
            curve["warnings"].append("flexure_geometry")
    if mode == "torsion" and y == "torque_Nm":
        measure("peak_torque", abs(extreme[y]), yu, extreme["source_row"])
        g = opts.get("geometry", {})
        if g.get("fixture") == "solid_circular" and g.get("diameter_mm") is None:
            curve["warnings"].append("torsion_geometry")
        if g.get("fixture") == "solid_circular" and g.get("diameter_mm") is not None:
            diameter = positive(g, "diameter_mm")
            measure(
                "nominal_surface_shear",
                16 * 1000 * abs(extreme[y]) / (math.pi * diameter**3),
                "MPa",
                extreme["source_row"],
            )
    if mode == "shear" and y in ("shear_stress_MPa", "stress_MPa"):
        measure("peak_shear_stress", abs(extreme[y]), "MPa", extreme["source_row"])
    if mode == "indentation":
        measure("max_indentation_force", abs(extreme[y]), yu, extreme["source_row"])
        deepest = max(paired, key=lambda p: p[x])
        measure("maximum_depth", deepest[x], axes[0]["unit"], deepest["source_row"])
    if mode == "peel" and opts.get("geometry", {}).get("width_mm") is not None:
        measure(
            "peak_peel_force_per_width",
            abs(extreme[y]) / positive(opts["geometry"], "width_mm"),
            "N/mm",
            extreme["source_row"],
        )
    if mode == "fatigue" and x == "time_s":
        threshold = (
            positive(opts, "reversal_threshold")
            if "reversal_threshold" in opts
            else None
        )
        cycles = fatigue_cycles(points, y, threshold)
        curve["fatigue_cycles"] = cycles
        if cycles:
            high_cycle = max(cycles, key=lambda c: c["amplitude"])
            measure(
                "peak_to_peak_amplitude",
                high_cycle["amplitude"],
                yu,
                high_cycle["peak_row"],
                high_cycle["valley_row"],
            )
            measure(
                "mean_extrema",
                high_cycle["mean_extrema"],
                yu,
                high_cycle["peak_row"],
                high_cycle["valley_row"],
            )
        else:
            curve["warnings"].append("fatigue_no_cycle")
    if mode == "fatigue" and x == "cycle_count":
        if any(p[x] < 0 or not p[x].is_integer() for p in paired):
            raise ValueError("Cycle counts must be non-negative integers")
        last = max(paired, key=lambda p: p[x])
        measure("highest_observed_cycle", last[x], "cycles", last["source_row"])
    if (
        x in ("deflection_mm", "extension_mm", "depth_mm", "peel_mm") and y == "force_N"
    ) or (x, y) == ("angle_deg", "torque_Nm"):
        if len(paired) == len(points) and all(
            b["source_row"] == a["source_row"] + 1
            and (
                "time_s" not in channels
                or (
                    a["time_s"] is not None
                    and b["time_s"] is not None
                    and b["time_s"] >= a["time_s"]
                )
            )
            for a, b in zip(points, points[1:])
        ):
            scale = math.pi / 180 if x == "angle_deg" else 0.001
            integral = math.fsum(
                0.5 * (a[y] + b[y]) * (b[x] - a[x]) * scale
                for a, b in zip(points, points[1:])
            )
            measure(
                "signed_path_integral",
                integral,
                "J",
                points[0]["source_row"],
                points[-1]["source_row"],
            )
        else:
            curve["warnings"].append("integral_gap")
    measure("maximum_response", hi[y], yu, hi["source_row"])
    measure("minimum_response", lo[y], yu, lo["source_row"])
    measure("x_at_maximum_response", hi[x], axes[0]["unit"], hi["source_row"])
    for p in points:
        p.update(
            local_cycle=None,
            phase="measured"
            if p.get(x) is not None and p.get(y) is not None
            else "missing_pair",
        )
    return dict(
        source_columns=labels,
        conditions={
            k: opts[k]
            for k in (
                "geometry",
                "area_mm2",
                "hold_rows",
                "fit_rows",
                "reversal_threshold",
            )
            if k in opts
        },
        test_type=mode,
        history=mode,
        classification=basis,
        curve=curve,
        channels=channels,
        metadata=meta,
        cycles=[],
        points=points,
    )


def positive(fields, key):
    value = fields.get(key)
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{key} must be a finite positive number")
    return value


def compression_fit(points, peak, channels):
    # Preserve measured signs in the record. Project the first branch into
    # positive compression coordinates solely for the documented window fit.
    part = points[: points.index(peak) + 1]
    signs = {}
    for key in ("strain_pct", "stress_MPa"):
        a, b = part[0].get(key), peak.get(key)
        signs[key] = -1 if a is not None and b is not None and b < a else 1
    branch = [
        dict(
            p,
            phase="loading",
            **{
                k: (p[k] * sign if p[k] is not None else None)
                for k, sign in signs.items()
            },
        )
        for p in part
    ]
    stress = [p["stress_MPa"] for p in branch if p["stress_MPa"] is not None]
    if stress:
        tol = max(1e-9, 0.015 * (max(stress) - min(stress)))
        top = None
        for i, p in enumerate(branch):
            v = p["stress_MPa"]
            if v is None:
                break
            if top is None or v >= branch[top]["stress_MPa"]:
                top = i
            elif branch[top]["stress_MPa"] - v >= tol:
                branch = branch[: top + 1]
                break
    return initial_loading_fit(
        branch, [], len(branch) - 1, ordered_only="time_s" not in channels
    )


def hold_metrics(mode, points, channels, x, y, unit, opts, curve, measure):
    """A measured hold or user-identified hold interval, in physical input rows."""
    controls = (
        ("stress_MPa", "force_N") if mode == "creep" else ("strain_pct", "extension_mm")
    )
    control = next((k for k in controls if k in channels), None)
    bounds = opts.get("hold_rows")
    window = points
    if bounds:
        start, end = bounds
        window = [p for p in points if start <= p["source_row"] <= end]
        if not window or (window[0]["source_row"], window[-1]["source_row"]) != (
            start,
            end,
        ):
            raise ValueError("hold_rows must identify actual endpoint rows")
    elif control is None:
        curve["warnings"].append("hold_unconfirmed")
        return
    if control and not bounds:
        stable = measured_hold(points, control, x, y)
        if stable is not None:
            window = stable
    if (
        len(window) < 2
        or any(
            p.get(x) is None or p.get(y) is None or (control and p.get(control) is None)
            for p in window
        )
        or any(
            b[x] <= a[x] or b["source_row"] != a["source_row"] + 1
            for a, b in zip(window, window[1:])
        )
    ):
        curve["warnings"].append("hold_discontinuous")
        return
    if control:
        values = [p[control] for p in window]
        level = float(np.median(values))
        if level == 0 or max(values) - min(values) > abs(level) * 0.02 + 1e-12:
            curve["warnings"].append("hold_varies")
            return
    a, b = window[0], window[-1]
    rows = (a["source_row"], b["source_row"])
    curve["hold"] = {
        "source_rows": list(rows),
        "control_channel": control,
        "basis": "notes" if bounds else "measured_control",
    }
    dt = b[x] - a[x]
    measure("hold_duration", dt, "s", *rows)
    delta = b[y] - a[y]
    if mode == "creep":
        if unit == "%":
            unit = "pp"
        measure("creep_change", delta, unit, *rows)
        measure("mean_hold_rate", delta / dt, unit + "/s", *rows)
    else:
        measure("relaxation_drop", a[y] - b[y], unit, *rows)
        if a[y] != 0:
            measure("retained_response", 100 * b[y] / a[y], "%", *rows)


def coordinate_fit(rows, x, y):
    if any(p.get(x) is None or p.get(y) is None for p in rows):
        return None
    if any(
        b["source_row"] != a["source_row"] + 1
        or (
            a.get("time_s") is not None
            and b.get("time_s") is not None
            and b["time_s"] < a["time_s"]
        )
        for a, b in zip(rows, rows[1:])
    ):
        return None
    xs = np.array([p[x] for p in rows])
    ys = np.array([p[y] for p in rows])
    if len(np.unique(xs)) < 3 or np.ptp(ys) == 0:
        return None
    steps = np.diff(xs)
    if np.any(steps > 0) and np.any(steps < 0):
        return None
    slope, intercept = np.polyfit(xs, ys, 1)
    r2 = 1 - np.sum((ys - (slope * xs + intercept)) ** 2) / np.sum(
        (ys - ys.mean()) ** 2
    )
    return {
        "slope": float(slope),
        "intercept": float(intercept),
        "r2": float(r2),
        "source_rows": [p["source_row"] for p in rows],
    }
