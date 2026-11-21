"""Measured axial branch properties, terminal transitions and compact specimen evidence."""

import math


def terminal_transition(points, channel, ordered_only):
    """Bracket one terminal load collapse. Keep acquisition gaps and clock resets separate."""
    loads = [p[channel] for p in points if p[channel] is not None]
    if len(loads) < 2:
        return None
    floor = min(loads)
    span = max(loads) - floor
    if span <= 0:
        return None
    low_tail = len(points)
    while (
        low_tail
        and points[low_tail - 1][channel] is not None
        and points[low_tail - 1][channel] <= floor + 0.30 * span
    ):
        low_tail -= 1
    if low_tail == 0 or low_tail == len(points):
        return None
    after = next(
        (
            i
            for i in range(low_tail, min(len(points), low_tail + 4))
            if points[i][channel] <= floor + 0.25 * span
        ),
        None,
    )
    if after is None:
        return None

    def adjacent(a, b):
        return b["source_row"] == a["source_row"] + 1 and (
            ordered_only
            or (
                a["time_s"] is not None
                and b["time_s"] is not None
                and b["time_s"] >= a["time_s"]
            )
        )

    if any(not adjacent(a, b) for a, b in zip(points[after:], points[after + 1 :])):
        return None
    start = after
    # A substantial decline on each included step avoids extending the bracket
    # backwards into the preceding gradual softening or a hold.
    while start > 0 and after - start < 4:
        a, b = points[start - 1 : start + 1]
        if (
            a[channel] is None
            or not adjacent(a, b)
            or a[channel] - b[channel] < 0.04 * span
        ):
            break
        start -= 1
    a, b = points[start], points[after]
    if start == after or a[channel] - b[channel] < 0.35 * span:
        return None
    if not ordered_only and b["time_s"] <= a["time_s"]:
        return None
    window = points[start : after + 1]
    motion = next(
        (
            k
            for k in ("extension_mm", "strain_pct")
            if all(p[k] is not None for p in window)
        ),
        None,
    )
    if not motion or any(v[motion] < u[motion] for u, v in zip(window, window[1:])):
        return None
    return start, after, motion


def branch_work(points):
    """Integral of engineering stress against dimensionless strain (MJ per m³)."""
    if len(points) < 2 or any(
        p["stress_MPa"] is None or p["strain_pct"] is None for p in points
    ):
        return None
    if any(
        b["source_row"] != a["source_row"] + 1
        or (
            a["time_s"] is not None
            and b["time_s"] is not None
            and b["time_s"] < a["time_s"]
        )
        for a, b in zip(points, points[1:])
    ):
        return None
    return math.fsum(
        0.005
        * (a["stress_MPa"] + b["stress_MPa"])
        * (b["strain_pct"] - a["strain_pct"])
        for a, b in zip(points, points[1:])
    )


def secant(a, b):
    if any(p[k] is None for p in (a, b) for k in ("stress_MPa", "strain_pct")):
        return None
    strain = b["strain_pct"] - a["strain_pct"]
    return 0.1 * (b["stress_MPa"] - a["stress_MPa"]) / strain if strain > 0 else None


def cycle_branches(points, cycles):
    loc = {p["source_row"]: i for i, p in enumerate(points)}
    result = []
    for c in cycles:
        if c["status"] != "complete":
            continue
        i, j, k = (loc[c[field]] for field in ("start_row", "turn_row", "end_row"))
        up = branch_work(points[i : j + 1])
        down = branch_work(points[j : k + 1])
        result.append(
            {
                "local_cycle": c["local_cycle"],
                "start_row": c["start_row"],
                "turn_row": c["turn_row"],
                "end_row": c["end_row"],
                "loading_secant_GPa": secant(points[i], points[j]),
                "unloading_secant_GPa": secant(points[k], points[j]),
                "loading_work_MJ_m3": up,
                "returned_work_MJ_m3": -down if down is not None else None,
                "net_work_MJ_m3": up + down
                if up is not None and down is not None
                else None,
            }
        )
    return result


def cycle_landmarks(records):
    """Measured qualifying maximum (all ties) and first nonqualifying complete cycle."""
    passed = []
    first_fail = None
    maximum = None
    count = 0
    assessed = 0
    for r in records:
        for c in r["cycles"]:
            if c["status"] != "complete" or c["fully_recoverable"] is None:
                continue
            assessed += 1
            item = {
                "record": r["record"],
                "cycle": c["cycle"],
                "applied_pct": c["total_strain_pp"],
                "residual_pp": c["residual_segment_pp"],
                "unload_stress_MPa": c["end_stress_MPa"],
                "turn_row": c["turn_row"],
                "end_row": c["end_row"],
            }
            if c["fully_recoverable"]:
                count += 1
                x = item["applied_pct"]
                if x is None:
                    continue
                if maximum is None or x > maximum:
                    maximum = x
                    passed = []
                if x == maximum:
                    passed.append(item)
            elif first_fail is None:
                first_fail = item
    return {
        "assessed_cycles": assessed,
        "qualifying_cycles": count,
        "highest_qualifying": passed,
        "first_nonqualifying": first_fail,
    }


def repeated_targets(records):
    """Pair consecutive visits to identical programmed targets within one specimen."""
    previous = {}
    matches = []
    for r in records:
        for c in r["cycles"]:
            if c["status"] != "complete" or c.get("target_axis") is None:
                continue
            key = (c["target_axis"], c["target_value"], c["target_lower_MPa"])
            obs = {
                "record": r["record"],
                "cycle": c["cycle"],
                "peak_stress_MPa": c["max_stress_MPa"],
                "peak_stress_row": c["max_stress_row"],
                "applied_pct": c["total_strain_pp"],
                "residual_pp": c["residual_segment_pp"],
                "end_stress_MPa": c["end_stress_MPa"],
                "turn_row": c["turn_row"],
                "end_row": c["end_row"],
                "reference_row": c["reference_row"],
            }
            prior = previous.get(key)
            if prior:
                delta = None
                if (
                    prior["peak_stress_MPa"] is not None
                    and obs["peak_stress_MPa"] is not None
                ):
                    delta = obs["peak_stress_MPa"] - prior["peak_stress_MPa"]
                dr = None
                if (
                    prior["record"] == obs["record"]
                    and prior["reference_row"] == obs["reference_row"]
                    and prior["residual_pp"] is not None
                    and obs["residual_pp"] is not None
                ):
                    dr = obs["residual_pp"] - prior["residual_pp"]
                matches.append(
                    {
                        "target_axis": key[0],
                        "target_value": key[1],
                        "target_lower_MPa": key[2],
                        "earlier": prior,
                        "later": obs,
                        "peak_stress_change_MPa": delta,
                        "residual_change_pp": dr,
                    }
                )
            previous[key] = obs
    return matches


def specimen_axial_summary(records):
    formal = [
        r
        for r in records
        if r["plot_role"] == "main" and r["history"] in ("cyclic", "tension")
    ]
    if not formal:
        return None
    first = formal[0]
    events = []
    for r in formal:
        e = r["event"]
        t = r["tensile"]
        peak = r["peak_stress"] or {}
        if not t and e["status"] == "unlocated" and not e.get("ends_under_load"):
            continue
        events.append(
            {
                "record": r["record"],
                "status": e["status"],
                "basis": e["basis"],
                "ends_under_load": e.get("ends_under_load", False),
                "before_row": e["source_row"],
                "before": e["before"],
                "after_row": e.get("after_row"),
                "after": e.get("after"),
                "drop_fraction": e.get("drop_fraction"),
                "low_tail_points": e.get("low_tail_points"),
                "drop_channel": e.get("drop_channel"),
                "motion_channel": e.get("motion_channel"),
                "observed_peak_stress_MPa": peak.get("stress_MPa"),
                "peak_stress_row": peak.get("source_row"),
                "strain_at_peak_stress_pct": peak.get("strain_pct"),
                "uts_MPa": t.get("uts_MPa"),
                "rp02_MPa": t.get("rp02_MPa"),
                "rp02_strain_pct": t.get("rp02_strain_pct"),
                "rp02_rows": t.get("rp02_rows"),
                "elongation_after_break_pct": t.get("elongation_after_break_pct"),
            }
        )
    return {
        "formal_records": [r["record"] for r in formal],
        "preliminary_records": [
            r["record"] for r in records if r["plot_role"] == "preliminary"
        ],
        "modulus_record": first["record"],
        "initial_loading_fit": first["initial_loading_fit"],
        "recovery": cycle_landmarks(formal),
        "repeated_targets": repeated_targets(formal),
        "terminal_records": events,
    }


def representative_cycles(cycles, limit=14):
    if len(cycles) <= limit:
        return cycles
    selected = {0, len(cycles) - 1}
    passed = [
        (i, c["total_strain_pp"])
        for i, (_, c) in enumerate(cycles)
        if c["fully_recoverable"] and c["total_strain_pp"] is not None
    ]
    if passed:
        maximum = max(x for _, x in passed)
        tied = [i for i, x in passed if x == maximum]
        selected.update([tied[0], tied[-1]])
    first_fail = next(
        (i for i, (_, c) in enumerate(cycles) if c["fully_recoverable"] is False), None
    )
    if first_fail is not None:
        selected.add(first_fail)
    priority = [i for i, (_, c) in enumerate(cycles) if c["status"] != "complete"]
    priority.extend(
        i for i in range(1, len(cycles)) if cycles[i - 1][0] is not cycles[i][0]
    )
    for i in priority:
        if len(selected) >= limit:
            break
        selected.add(i)
    # Fill the widest unrepresented intervals in test order.
    while len(selected) < limit:
        edges = sorted(selected)
        a, b = max(zip(edges, edges[1:]), key=lambda pair: pair[1] - pair[0])
        selected.add((a + b) // 2)
    return [cycles[i] for i in sorted(selected)]
