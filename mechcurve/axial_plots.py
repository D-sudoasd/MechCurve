"""Axial landmark overlays and the measured terminal interval."""

from .figures import (
    ACCENT,
    MODULUS_COLOR,
    MUTED,
    EVENT,
    fmt,
    plot_axis,
    acquisition_axis,
)
from .locale import language, tr


def words(zh, en):
    return en if language() == "en" else zh


def terminal_record(records):
    rank = {"confirmed_row": 3, "confirmed_record": 2, "candidate": 1, "unlocated": 0}
    return max(records, key=lambda r: (rank[r["event"]["status"]], r["sequence"]))


def mark_tension(ax, r, axes):
    if axes is None:
        return
    x, y = axes
    pts = {p["source_row"]: p for p in r["points"]}
    t = r["tensile"]
    peak = r["peak_stress"] if y == "stress_MPa" else r["peak_observed"]
    marks = []
    if peak:
        marks.append(
            (peak.get(x), peak.get(y), "^", ACCENT, words("实测峰值", "Measured peak"))
        )
    if axes == ("strain_pct", "stress_MPa") and t.get("rp02_strain_pct") is not None:
        marks.append((t["rp02_strain_pct"], t["rp02_MPa"], "D", "#a96b16", "Rp0.2"))
    point = pts.get(r["event"]["source_row"])
    if point:
        marks.append(
            (point[x], point[y], "o", MODULUS_COLOR, words("事件前", "Pre-event"))
        )
    handles = []
    for xx, yy, marker, color, label in marks:
        if xx is not None and yy is not None:
            handles.append(
                ax.scatter(
                    xx,
                    yy,
                    s=45 if marker == "o" else 25,
                    marker=marker,
                    facecolors="none" if marker == "o" else color,
                    edgecolors=color,
                    lw=1.2,
                    zorder=5,
                    label=label,
                )
            )
    if handles:
        ax.legend(
            handles=handles, frameon=False, fontsize=7.4, loc="best", ncol=len(handles)
        )


def terminal_panel(fig, r):
    event = r["event"]
    points = r["points"]
    x, xlabel = acquisition_axis(r)
    y = r["control_channel"]
    center = event["index"] if event["index"] is not None else len(points) - 1
    block = points[max(0, center - 12) : min(len(points), center + 13)]
    ax = fig.add_axes([0.125, 0.105, 0.445, 0.155])
    xs = []
    ys = []
    prev = None
    for p in block:
        if prev and (
            p["source_row"] != prev["source_row"] + 1
            or (
                x == "time_s"
                and p[x] is not None
                and prev[x] is not None
                and p[x] < prev[x]
            )
        ):
            xs.append(None)
            ys.append(None)
        xs.append(p[x])
        ys.append(p[y])
        prev = p
    ax.plot(xs, ys, ".-", color=ACCENT, ms=3, lw=1.1)
    selected = {event["source_row"]: MODULUS_COLOR, event["after_row"]: "#a96b16"}
    for p in block:
        if p["source_row"] in selected and p[x] is not None and p[y] is not None:
            ax.scatter(p[x], p[y], color=selected[p["source_row"]], s=23, zorder=4)
    plot_axis(
        ax,
        xlabel,
        words("力 (N)", "Force (N)")
        if y == "force_N"
        else words("应力 (MPa)", "Stress (MPa)"),
    )
    ax.tick_params(labelsize=7.5)
    fig.text(
        0.082,
        0.288,
        words("终止区间", "Terminal interval"),
        weight="bold",
        fontsize=12,
        color=ACCENT,
    )
    fig.text(
        0.64,
        0.251,
        tr(EVENT[event["status"]]),
        fontsize=12,
        weight="bold",
        color=MODULUS_COLOR,
    )
    before = event["before"] or {}
    lines = [
        (words("采集段", "Acquisition"), str(r["sequence"])),
        (
            words("事件前行 / 低载行", "Pre-event / low row"),
            f"{event['source_row'] or '—'} / {event['after_row'] or '—'}",
        ),
        (
            words("事件前应变", "Pre-event strain"),
            fmt(before.get("strain_pct")) + " %"
            if before.get("strain_pct") is not None
            else "—",
        ),
        (
            words("载荷降幅", "Signal drop"),
            fmt(100 * event["drop_fraction"], 1) + " %"
            if event["drop_fraction"] is not None
            else "—",
        ),
    ]
    for i, (label, value) in enumerate(lines):
        fig.text(0.64, 0.215 - 0.027 * i, label, fontsize=8, color=MUTED)
        fig.text(0.935, 0.215 - 0.027 * i, value, fontsize=8, ha="right")


def format_landmark(label, item):
    if not item:
        return label + "   —"
    return (
        label
        + f"   #{item['cycle']}  ·  {fmt(item['applied_pct'])}%  ·  "
        + words("残余 ", "residual ")
        + fmt(item["residual_pp"])
        + " pp"
    )
