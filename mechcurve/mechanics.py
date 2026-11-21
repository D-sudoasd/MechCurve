"""Mechanical events refer to original row indices. Strain differences are percentage points."""

import math
from statistics import median

import numpy as np


RESIDUAL_THRESHOLD_PP = 0.03


def fully_recoverable(status, residual_pp):
    if status != "complete" or residual_pp is None or not math.isfinite(residual_pp):
        return None
    return residual_pp < RESIDUAL_THRESHOLD_PP


def recovery_summary(cycles):
    assessed = [c for c in cycles if c["fully_recoverable"] is not None]
    passed = [c for c in assessed if c["fully_recoverable"]]
    highest = max(
        (c["total_strain_pp"] for c in passed if c["total_strain_pp"] is not None),
        default=None,
    )
    return {
        "residual_threshold_pp": RESIDUAL_THRESHOLD_PP,
        "recovery_assessed_cycles": len(assessed),
        "fully_recoverable_cycles": len(passed),
        "max_fully_recoverable_applied_pct": highest,
        "max_fully_recoverable_cycle_numbers": [
            c["cycle"]
            for c in passed
            if highest is not None and c["total_strain_pp"] == highest
        ],
    }


def difference(a, b):
    return None if a is None or b is None else round(a - b, 12)


def maximum(points, key, begin, end):
    valid = [i for i in range(begin, end + 1) if points[i][key] is not None]
    return max(valid, key=lambda i: points[i][key]) if valid else None


def contiguous(points, channel, ordered_only=False):
    start = None
    previous = None
    for i, point in enumerate(points):
        time = point["source_row"] if ordered_only else point["time_s"]
        valid = time is not None and point[channel] is not None
        if start is not None and (
            not valid
            or previous is not None
            and (
                time < previous or point["source_row"] > points[i - 1]["source_row"] + 1
            )
        ):
            yield start, i - 1
            start = None
        if valid and start is None:
            start = i
        previous = time if valid else None
    if start is not None:
        yield start, len(points) - 1


def finish_event(points, channel, meta, opts, ordered_only=False):
    order = "source_row" if ordered_only else "time_s"
    row = opts.get("break_before_row")
    if row is not None:
        idx = next((i for i, p in enumerate(points) if p["source_row"] == row), None)
        if idx is None or points[idx][channel] is None:
            raise ValueError("指定的断裂前行号缺少有效载荷或超出原始表")
        return {
            "status": "confirmed_row",
            "index": idx,
            "basis": "实验备注指定断裂前最后有效行",
        }
    ys = [p[channel] for p in points if p[channel] is not None]
    span = max(ys) - min(ys) if ys else 0
    candidates = []
    for i in range(len(points) - 1):
        a, b = points[i : i + 2]
        if (
            None in (a[channel], b[channel], a[order], b[order])
            or b[order] <= a[order]
            or b["source_row"] != a["source_row"] + 1
        ):
            continue
        if (
            a[channel] - b[channel] < 0.35 * span
            or span <= 0
            or b[channel] > min(ys) + 0.25 * span
        ):
            continue
        motion = next(
            (
                k
                for k in ("extension_mm", "strain_pct")
                if a[k] is not None and b[k] is not None
            ),
            None,
        )
        if (
            motion
            and b[motion] >= a[motion]
            and all(
                p[channel] is not None and p[channel] <= min(ys) + 0.3 * span
                for p in points[i + 1 :]
            )
        ):
            candidates.append(i)
    marked = meta.get("instrument_break_valid") or opts.get("fractured") is True
    if len(candidates) == 1:
        return {
            "status": "confirmed_row" if marked else "candidate",
            "index": candidates[0],
            "basis": "载荷骤降并保持低位，位移或应变未同步卸载"
            + ("；有独立断裂记录" if marked else "；缺少独立断裂标记"),
        }
    return {
        "status": "confirmed_record" if marked else "unlocated",
        "index": None,
        "basis": "有试样级断裂记录，采样点尚未定位"
        if marked
        else "未检出可唯一归属的断裂采样点",
    }


def reversals(points, ch, lo, hi, threshold):
    """Hysteresis confirms reversals, returns measured maxima and following minima."""
    idx = lo
    high = None
    loading = True
    pairs = []
    for i in range(lo + 1, hi + 1):
        y = points[i][ch]
        extreme = points[idx][ch]
        if loading:
            if y >= extreme:
                idx = i
            elif extreme - y >= threshold:
                high, idx, loading = idx, i, False
        elif y <= extreme:
            idx = i
        elif y - extreme >= threshold:
            pairs.append((high, idx))
            idx, loading = i, True
    if not loading:
        pairs.append((high, idx))
    return pairs


def metric(
    points,
    start,
    turn,
    end,
    observed_end,
    origin,
    status,
    local,
    meta,
    target_allowed=True,
):
    stop = turn if turn is not None else observed_end
    peak = maximum(points, "force_N", start, stop)
    high = maximum(points, "stress_MPa", start, stop)
    top = maximum(points, "strain_pct", start, stop)

    def value(i, key):
        return None if i is None else points[i][key]

    e_start, e_turn, e_end = (value(i, "strain_pct") for i in (start, turn, end))
    inc = difference(e_turn, e_start)
    recovery = difference(e_turn, e_end)
    residual = difference(e_end, value(origin, "strain_pct"))
    target = None
    if target_allowed and turn is not None:
        matches = []
        for step in meta.get("steps", []):
            measured = value(turn, step["axis"])
            dist = abs(measured - step["target"]) if measured is not None else math.inf
            if dist <= max(1e-8, 0.02 * abs(step["target"])):
                matches.append((dist, step))
        if matches:
            target = min(matches, key=lambda item: item[0])[1]
    return {
        "local_cycle": local,
        "status": status,
        "start_row": value(start, "source_row"),
        "turn_row": value(turn, "source_row"),
        "end_row": value(end, "source_row"),
        "observed_end_row": value(observed_end, "source_row"),
        "peak_force_row": value(peak, "source_row"),
        "peak_force_N": value(peak, "force_N"),
        "peak_time_s": value(peak, "time_s"),
        "stress_at_peak_MPa": value(peak, "stress_MPa"),
        "strain_at_peak_pct": value(peak, "strain_pct"),
        "max_stress_MPa": value(high, "stress_MPa"),
        "max_stress_row": value(high, "source_row"),
        "max_strain_pct": value(top, "strain_pct"),
        "max_strain_row": value(top, "source_row"),
        "reference_row": value(origin, "source_row"),
        "reference_strain_pct": value(origin, "strain_pct"),
        "start_stress_MPa": value(start, "stress_MPa"),
        "start_strain_pct": e_start,
        "turn_strain_pct": e_turn,
        "end_force_N": value(end, "force_N"),
        "end_stress_MPa": value(end, "stress_MPa"),
        "end_strain_pct": e_end,
        "total_strain_pp": difference(e_turn, value(origin, "strain_pct")),
        "loading_increment_pp": inc,
        "recoverable_pp": recovery,
        "residual_segment_pp": residual,
        "residual_threshold_pp": RESIDUAL_THRESHOLD_PP,
        "fully_recoverable": fully_recoverable(status, residual),
        "residual_increment_pp": difference(e_end, e_start),
        "recovery_pct": 100 * recovery / inc
        if recovery is not None and inc is not None and inc > 1e-8
        else None,
        "target_axis": target["axis"] if target else None,
        "target_value": target["target"] if target else None,
        "target_lower_MPa": target["lower_MPa"] if target else None,
    }


def segment(points, channel, opts, meta, event, ordered_only=False):
    cycles = []
    blocks = list(contiguous(points, channel, ordered_only))
    expected = opts.get("history") == "cyclic" or (
        opts.get("history") is None and bool(meta.get("steps"))
    )
    for p in points:
        p.update(local_cycle=None, phase="unclassified")
    for lo, hi in blocks:
        if event["index"] is not None:
            hi = min(hi, event["index"])
        if hi < lo:
            continue
        ys = np.array([points[k][channel] for k in range(lo, hi + 1)])
        span = np.ptp(ys)
        tol = opts.get("reversal_threshold", max(float(span) * 0.015, 1e-9))
        if not math.isfinite(tol) or tol <= 0:
            raise ValueError("reversal_threshold 必须为正值")
        pairs = (
            []
            if opts.get("history") == "tension"
            else reversals(points, channel, lo, hi, tol)
        )
        start = lo
        motion = next(
            (
                key
                for key in ("extension_mm", "strain_pct")
                if all(points[k][key] is not None for k in range(lo, hi + 1))
            ),
            None,
        )
        for peak, valley in pairs:
            if (
                valley <= peak
                or peak < start
                or points[peak][channel] - points[start][channel] < tol
            ):
                continue
            turn = peak
            if motion:
                # The grip can continue moving past the load maximum. Use the latest travel
                # maximum before reverse travel starts, even when a specimen strain plateaus.
                turn = max(
                    range(peak, valley + 1), key=lambda k: (points[k][motion], k)
                )
                if turn == valley:
                    continue
            elif not expected and valley == hi:
                continue
            ref = points[start][channel]
            lower = [
                s["lower_MPa"]
                for s in meta.get("steps", [])
                if s["lower_MPa"] is not None
            ]
            at_program_floor = (
                lower
                and points[valley]["stress_MPa"] is not None
                and any(
                    abs(points[valley]["stress_MPa"] - y) <= max(0.5, 0.01 * abs(y))
                    for y in lower
                )
            )
            rise_after_valley = (
                max(points[i][channel] for i in range(valley, hi + 1))
                - points[valley][channel]
            )
            closed = (
                rise_after_valley >= tol
                or at_program_floor
                or points[valley][channel] <= ref + tol
            )
            if event["index"] == valley:
                closed = False
            end = valley if closed else None
            ordinal = len(cycles) + 1
            cycle = metric(
                points,
                start,
                turn,
                end,
                valley,
                lo,
                "complete" if closed else "partial_unload",
                ordinal,
                meta,
            )
            # A small settling excursion at the unload floor is measured, but does
            # not attain any scheduled loading level. Retain its rows separately.
            if (
                cycles
                and meta.get("steps")
                and cycle["target_axis"] is None
                and valley == hi
                and points[peak][channel] - ref < 0.1 * span
            ):
                for k in range(start + 1, valley + 1):
                    points[k].update(local_cycle=None, phase="low_load_excursion")
                start = valley
                continue
            cycles.append(cycle)
            for k in range(start, valley + 1):
                points[k].update(
                    local_cycle=ordinal,
                    phase="loading"
                    if k < turn
                    else "turn"
                    if k == turn
                    else "unloading",
                )
            points[valley]["phase"] = "lower_turn" if closed else "partial_unload"
            start = valley
        if start < hi or start == lo and not pairs:
            ordinal = len(cycles) + 1
            active = expected or bool(cycles)
            if active:
                status = (
                    (
                        "fracture_confirmed"
                        if event["status"] == "confirmed_row"
                        else "fracture_candidate"
                    )
                    if event["index"] == hi
                    else "partial_loading"
                )
                cycles.append(
                    metric(points, start, None, None, hi, lo, status, ordinal, meta)
                )
            for k in range(start + (start != lo), hi + 1):
                points[k].update(
                    local_cycle=ordinal if active else None,
                    phase="loading" if active else "tension",
                )
        # Mark sustained dwell only; equal-time event rows alone do not establish a hold.
        k = lo
        while k < hi:
            stop = k
            while (
                stop < hi
                and abs(points[stop + 1][channel] - points[k][channel]) <= tol * 0.01
                and (
                    not motion
                    or abs(points[stop + 1][motion] - points[k][motion]) < 1e-7
                )
            ):
                stop += 1
            if (
                not ordered_only
                and stop >= k + 2
                and points[stop]["time_s"] > points[k]["time_s"]
            ):
                for n in range(k + 1, stop):
                    if points[n]["phase"] in ("loading", "unloading", "tension"):
                        points[n]["phase"] = "hold"
            k = stop + 1
    if event["index"] is not None:
        for p in points[event["index"] + 1 :]:
            p["phase"] = "after_event"
    return cycles, len(blocks)


def initial_loading_fit(points, cycles, last, ordered_only=False):
    """OLS with intercept on the first traversal of the specified strain window."""
    lower, upper = 0.05, 0.15
    origin = points[0]["strain_pct"]
    result = {
        "modulus_GPa": None,
        "window_min_pct": lower,
        "window_max_pct": upper,
        "reference_strain_pct": origin,
        "reference_row": points[0]["source_row"],
        "n": 0,
        "r2": None,
        "source_rows": [],
        "first_row": None,
        "last_row": None,
        "measured_min_pct": None,
        "measured_max_pct": None,
        "slope_MPa": None,
        "intercept_MPa": None,
        "reason": "首加载支未覆盖完整应变窗口",
    }
    if origin is None or cycles and cycles[0]["start_row"] != points[0]["source_row"]:
        return {**result, "reason": "首加载起点应变或采样依据缺失"}
    stop_row = (
        (cycles[0]["turn_row"] or cycles[0]["observed_end_row"])
        if cycles
        else points[last]["source_row"]
    )
    selected = []
    previous_time = None
    covered = False
    previous_row = None
    for point in points[: last + 1]:
        if point["source_row"] > stop_row:
            break
        if (
            any(point[k] is None for k in ("strain_pct", "stress_MPa"))
            or (not ordered_only and point["time_s"] is None)
            or point["phase"] == "unclassified"
        ):
            return {**result, "reason": "首加载段存在缺失采样"}
        if previous_row is not None and point["source_row"] != previous_row + 1:
            return {**result, "reason": "首加载段存在缺失采样"}
        previous_row = point["source_row"]
        if previous_time is not None and point["time_s"] < previous_time:
            return {**result, "reason": "拟合窗口跨越时钟复位"}
        previous_time = point["time_s"]
        increment = difference(point["strain_pct"], origin)
        if increment < lower and selected:
            return {**result, "reason": "应变回退并离开拟合窗口"}
        if lower <= increment <= upper:
            selected.append(point)
        if increment >= upper:
            covered = True
            break
    if selected:
        result.update(
            n=len(selected),
            source_rows=[p["source_row"] for p in selected],
            first_row=selected[0]["source_row"],
            last_row=selected[-1]["source_row"],
            measured_min_pct=min(difference(p["strain_pct"], origin) for p in selected),
            measured_max_pct=max(difference(p["strain_pct"], origin) for p in selected),
        )
    if not covered:
        return result
    x = np.array([p["strain_pct"] / 100 for p in selected])
    y = np.array([p["stress_MPa"] for p in selected])
    if len(np.unique(x)) < 3 or np.ptp(y) == 0:
        return {**result, "reason": "窗口内不同应变点不足三个或应力无变化"}
    slope, intercept = np.polyfit(x, y, 1)
    r2 = 1 - np.sum((y - slope * x - intercept) ** 2) / np.sum((y - y.mean()) ** 2)
    result.update(slope_MPa=float(slope), intercept_MPa=float(intercept), r2=float(r2))
    if slope <= 0:
        return {**result, "reason": "窗口斜率为非正值"}
    return {
        **result,
        "modulus_GPa": float(slope / 1000),
        "reason": "窗口拟合完成" if r2 >= 0.995 else "窗口线性较弱，需结合拟合点判读",
    }


def tensile(points, last, complete, opts, fit_allowed, initial_fit):
    p = points[: last + 1]
    high = maximum(p, "stress_MPa", 0, last)
    result = {
        "uts_MPa": None,
        "modulus_GPa": initial_fit["modulus_GPa"],
        "rp02_MPa": None,
        "fit": initial_fit if initial_fit["slope_MPa"] is not None else None,
        "elongation_after_break_pct": None,
        "fit_reason": initial_fit["reason"],
    }
    l0, lf = opts.get("original_gauge_mm"), opts.get("final_gauge_mm")
    if complete and l0 and lf and l0 > 0 and lf >= l0:
        result["elongation_after_break_pct"] = 100 * (lf - l0) / l0
    if high is None:
        return result
    if complete:
        result["uts_MPa"] = p[high]["stress_MPa"]
    if (
        not fit_allowed
        or high < 6
        or any(
            q[k] is None for q in p[: high + 1] for k in ("stress_MPa", "strain_pct")
        )
    ):
        return result
    x = np.array([q["strain_pct"] / 100 for q in p[: high + 1]])
    y = np.array([q["stress_MPa"] for q in p[: high + 1]])
    if "fit_fraction" not in opts:
        if initial_fit["modulus_GPa"] is None or initial_fit["r2"] < 0.995:
            return result
        fit_end = next(
            (
                i
                for i, q in enumerate(p[: high + 1])
                if q["source_row"] == initial_fit["last_row"]
            ),
            None,
        )
        if fit_end is not None:
            offset_yield(
                result,
                p,
                x,
                y,
                initial_fit["slope_MPa"],
                initial_fit["intercept_MPa"],
                fit_end,
            )
        return result
    a, b = opts.get("fit_fraction", [0.1, 0.35])
    if not (0 <= a < b <= 1):
        raise ValueError("弹性拟合窗口比例必须在 0 至 1 之间并递增")
    mask = (y >= y[0] + a * (y.max() - y[0])) & (y <= y[0] + b * (y.max() - y[0]))
    ix = np.flatnonzero(mask)
    if (
        len(ix) < 6
        or np.ptp(x[ix]) < 1e-6
        or np.ptp(y[ix]) == 0
        or np.any(np.diff(ix) != 1)
    ):
        return result
    slope, intercept = np.polyfit(x[ix], y[ix], 1)
    r2 = 1 - np.sum((y[ix] - slope * x[ix] - intercept) ** 2) / np.sum(
        (y[ix] - y[ix].mean()) ** 2
    )
    result["proof_fit"] = {
        "first_row": p[ix[0]]["source_row"],
        "last_row": p[ix[-1]]["source_row"],
        "n": len(ix),
        "r2": float(r2),
        "slope_MPa": float(slope),
        "intercept_MPa": float(intercept),
    }
    if slope <= 0 or r2 < 0.995:
        return result
    offset_yield(result, p, x, y, slope, intercept, ix[-1])
    return result


def offset_yield(result, p, x, y, slope, intercept, fit_end):
    distances = y - (slope * (x - 0.002) + intercept)
    for i in range(fit_end + 1, len(x)):
        if distances[i - 1] > 0 >= distances[i] and x[i] > x[i - 1]:
            w = distances[i - 1] / (distances[i - 1] - distances[i])
            result.update(
                rp02_MPa=float(y[i - 1] + w * (y[i] - y[i - 1])),
                rp02_rows=[p[i - 1]["source_row"], p[i]["source_row"]],
            )
            break


def analyze_record(points, channels, meta, opts):
    if "targets" in opts:
        meta = {**meta, "steps": opts["targets"]}
    area = opts.get("area_mm2", meta.get("area_mm2"))
    if area is not None and (not math.isfinite(area) or area <= 0):
        raise ValueError("截面积必须为正值")
    if area and "stress_MPa" not in channels and "force_N" in channels:
        for p in points:
            p["stress_MPa"] = p["force_N"] / area if p["force_N"] is not None else None
    channel = "force_N" if "force_N" in channels else "stress_MPa"
    if not any(p[channel] is not None for p in points):
        raise ValueError("主力学通道没有有限采样")
    ordered_only = "time_s" not in channels
    event = finish_event(points, channel, meta, opts, ordered_only)
    cycles, block_count = segment(points, channel, opts, meta, event, ordered_only)
    last = event["index"] if event["index"] is not None else len(points) - 1
    history = "cyclic" if cycles else "tension"
    peak = maximum(points, channel, 0, last)
    high = maximum(points, "stress_MPa", 0, last)
    ratios = [
        p["force_N"] / p["stress_MPa"]
        for p in points
        if p["force_N"] is not None
        and p["stress_MPa"] is not None
        and abs(p["stress_MPa"]) > 1
    ]
    initial_fit = initial_loading_fit(points, cycles, last, ordered_only)
    metrics = (
        tensile(
            points,
            last,
            event["status"].startswith("confirmed") or opts.get("complete") is True,
            opts,
            block_count == 1
            and (ordered_only or all(p["time_s"] is not None for p in points)),
            initial_fit,
        )
        if history == "tension"
        else {}
    )
    event["source_row"] = (
        points[event["index"]]["source_row"] if event["index"] is not None else None
    )
    event["before"] = (
        {
            k: points[event["index"]][k]
            for k in ("time_s", "force_N", "stress_MPa", "strain_pct")
        }
        if event["index"] is not None
        else None
    )
    values = [p[channel] for p in points if p[channel] is not None]
    terminal = points[-1][channel]
    fraction = (
        (terminal - min(values)) / (max(values) - min(values))
        if terminal is not None and max(values) > min(values)
        else None
    )
    event["last_row"] = points[-1]["source_row"]
    event["end_fraction_of_range"] = fraction
    event["ends_under_load"] = bool(
        fraction is not None
        and fraction >= 0.25
        and points[-1]["phase"] in ("loading", "tension")
    )
    if event["status"] == "unlocated" and event["ends_under_load"]:
        event["basis"] += "。采集在较高载荷的加载途中终止，终止原因未记录"
    return {
        "channels": channels,
        "control_channel": channel,
        "metadata": meta,
        "area_mm2": area,
        "inferred_area_mm2": median(ratios) if ratios else None,
        "area_relative_error": abs(median(ratios) / area - 1)
        if ratios and area
        else None,
        "blocks": block_count,
        "history": history,
        "event": event,
        "cycles": cycles,
        "points": points,
        "peak_observed": points[peak] if peak is not None else None,
        "peak_stress": points[high] if high is not None else None,
        "tensile": metrics,
        "initial_loading_fit": initial_fit,
    }
