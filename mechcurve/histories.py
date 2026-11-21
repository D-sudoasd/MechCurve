"""Observed time-domain holds and complete peak-to-peak fatigue excursions."""

from collections import deque
import statistics
from .mechanics import contiguous, reversals


def whole_hold(points, control, response):
    if len(points) < 6 or any(
        p.get(k) is None for p in points for k in (control, response, "time_s")
    ):
        return False
    if any(
        b["time_s"] <= a["time_s"] or b["source_row"] != a["source_row"] + 1
        for a, b in zip(points, points[1:])
    ):
        return False
    ctrl = [p[control] for p in points]
    if (
        not max(ctrl) - min(ctrl) <= 0.005 * abs(statistics.median(ctrl))
        or statistics.median(ctrl) == 0
    ):
        return False
    ys = [p[response] for p in points]
    net = ys[-1] - ys[0]
    travel = sum(abs(b - a) for a, b in zip(ys, ys[1:]))
    return (
        travel > 0 and abs(net) >= 0.9 * travel and abs(net) > 0.02 * max(map(abs, ys))
    )


def measured_hold(points, control, x, y):
    """Find the longest uninterrupted nonzero plateau; break ties by acquisition order."""
    low, high = deque(), deque()
    start = 0
    best = None
    duration = 0
    for i, p in enumerate(points):
        if any(p.get(k) is None for k in (x, y, control)):
            start = i + 1
            low.clear()
            high.clear()
            continue
        if i > start and (
            p[x] <= points[i - 1][x]
            or p["source_row"] != points[i - 1]["source_row"] + 1
        ):
            start = i
            low.clear()
            high.clear()
        v = p[control]
        while low and points[low[-1]][control] >= v:
            low.pop()
        while high and points[high[-1]][control] <= v:
            high.pop()
        low.append(i)
        high.append(i)
        while start < i:
            lo, hi = points[low[0]][control], points[high[0]][control]
            if hi - lo <= 0.02 * min(abs(lo), abs(hi)) and lo * hi > 0:
                break
            if low[0] == start:
                low.popleft()
            if high[0] == start:
                high.popleft()
            start += 1
        if i - start >= 5 and p[x] - points[start][x] > duration and v != 0:
            duration = p[x] - points[start][x]
            best = (start, i)
    if best is None:
        return None
    # Avoid interpreting a short locally flat portion of an ordinary ramp as a hold.
    ts = [p[x] for p in points if p.get(x) is not None]
    return (
        points[best[0] : best[1] + 1] if duration >= 0.2 * (max(ts) - min(ts)) else None
    )


def fatigue_cycles(points, y, threshold=None):
    cycles = []
    for lo, hi in contiguous(points, y):
        values = [p[y] for p in points[lo : hi + 1]]
        span = max(values) - min(values)
        if span == 0:
            continue
        turns = reversals(
            points, y, lo, hi, threshold if threshold is not None else 0.02 * span
        )
        for (a, valley), (b, _) in zip(turns, turns[1:]):
            if not a < valley < b:
                continue
            peak, trough = points[a][y], points[valley][y]
            cycles.append(
                {
                    "cycle": len(cycles) + 1,
                    "peak_row": points[a]["source_row"],
                    "valley_row": points[valley]["source_row"],
                    "next_peak_row": points[b]["source_row"],
                    "maximum": peak,
                    "minimum": trough,
                    "amplitude": (peak - trough) / 2,
                    "mean_extrema": (peak + trough) / 2,
                    "load_ratio": trough / peak if peak != 0 else None,
                }
            )
    return cycles
