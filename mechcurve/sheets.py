"""A printable performance sheet for one physical specimen, including resumed runs."""

from .locale import tr, diagnosis, language

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
import numpy as np

from .mechanics import RESIDUAL_THRESHOLD_PP, recovery_summary
from .figures import (
    history_figure,
    ACCENT,
    INK,
    MUTED,
    MODULUS_COLOR,
    RECOVERY_LABEL,
    fmt,
    fmt_residual,
    plot_axis,
)


def segment_caption(records):
    captions = []
    for record in records:
        complete = [c for c in record["cycles"] if c["status"] == "complete"]
        if not complete:
            continue
        modes = {c["target_axis"] for c in complete if c["target_axis"]}
        mode = {
            "stress_MPa": tr("应力目标"),
            "strain_pct": tr("应变目标"),
            "force_N": tr("力目标"),
        }.get(next(iter(modes)) if len(modes) == 1 else None, tr("实测加载"))
        captions.append(
            tr("第 {0}–{1} 周 · {2}", complete[0]["cycle"], complete[-1]["cycle"], mode)
        )
    if len(captions) > 3:
        return tr("{0} 段加载程序，详见逐周表。", len(captions))
    return "     /     ".join(captions)


STRAIN_SERIES = (
    ("recoverable_pp", "可恢复应变", "o", "#21649d"),
    ("residual_segment_pp", "段内残余应变", "D", "#b85118"),
)


def strain_response(fig, records):
    """Plot complete, paired observations at their measured reversal strain."""
    groups = [
        [
            c
            for c in r["cycles"]
            if c["status"] == "complete"
            and all(
                c[k] is not None
                for k in ("total_strain_pp", "recoverable_pp", "residual_segment_pp")
            )
        ]
        for r in records
    ]
    valid = [c for group in groups for c in group]
    if not valid:
        fig.text(
            0.12, 0.42, tr("缺少可配对的加载换向和卸载应变。"), color=MUTED, fontsize=10
        )
        return
    zoom = max(abs(c["residual_segment_pp"]) for c in valid) < 0.10 * max(
        c["total_strain_pp"] for c in valid
    )
    ax = fig.add_axes([0.115, 0.347, 0.48 if zoom else 0.79, 0.147])
    detail = fig.add_axes([0.704, 0.347, 0.202, 0.147], sharex=ax) if zoom else None
    for segment, group in enumerate(groups):
        if not group:
            continue
        xs = [c["total_strain_pp"] for c in group]
        for field, label, marker, color in STRAIN_SERIES:
            ys = [c[field] for c in group]
            axes = (
                (ax, detail)
                if detail is not None and field == "residual_segment_pp"
                else (ax,)
            )
            for target in axes:
                target.scatter(
                    xs,
                    ys,
                    marker=marker,
                    s=36 if segment else 17,
                    facecolors="none" if segment else color,
                    edgecolors=color,
                    linewidths=0.9,
                    label=tr(label),
                    zorder=3,
                )
    for index, (previous, current) in enumerate(zip(groups, groups[1:])):
        if (
            previous
            and current
            and previous[-1]["total_strain_pp"] == current[0]["total_strain_pp"]
            and index < 3
        ):
            a, b = previous[-1], current[0]
            ax.annotate(
                tr("第 {0}、{1} 周", a["cycle"], b["cycle"]),
                xy=(a["total_strain_pp"], a["recoverable_pp"]),
                xytext=(-8, 9),
                textcoords="offset points",
                arrowprops={
                    "arrowstyle": "-",
                    "color": MUTED,
                    "lw": 0.55,
                    "shrinkA": 1,
                    "shrinkB": 3,
                },
                fontsize=7.5,
                ha="right",
                color=INK,
            )
    for target in (ax, detail):
        if target is None:
            continue
        plot_axis(
            target,
            tr("施加应变 (%)"),
            tr("应变 (百分点)") if target is ax else tr("残余 (百分点)"),
        )
        target.axhline(0, color="#88989e", lw=0.65, zorder=0)
        target.axhline(
            RESIDUAL_THRESHOLD_PP, color="#8e563c", lw=1.0, ls=(0, (5, 3)), zorder=1
        )
        target.tick_params(labelsize=8)
        target.xaxis.set_major_locator(MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10]))
        target.yaxis.set_major_locator(MaxNLocator(nbins=4))
    if detail is not None:
        detail.set_title(tr("残余局部放大"), loc="left", fontsize=8, color=MUTED, pad=4)
        lo, hi = detail.get_ylim()
        ticks = MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]).tick_values(lo, hi)
        detail.set_yticks(ticks)
        detail.set_ylim(ticks[0], ticks[-1])
    handles = [
        Line2D([], [], ls="", marker=m, color=color, label=tr(label), markersize=5)
        for _, label, m, color in STRAIN_SERIES
    ]
    handles.append(
        Line2D(
            [],
            [],
            ls=(0, (5, 3)),
            lw=1.1,
            color="#8e563c",
            label=tr("残余判定线 {0:g}%", RESIDUAL_THRESHOLD_PP),
        )
    )
    ax.legend(
        handles=handles,
        loc="upper left",
        frameon=False,
        fontsize=8,
        handlelength=1.5,
        borderpad=0.2,
    )


def sample_sheet(destination, name, records):
    first = records[0]
    fit = first["initial_loading_fit"]
    cycles = [(r, c) for r in records for c in r["cycles"]]
    completed = [(r, c) for r, c in cycles if c["status"] == "complete"]
    summary = recovery_summary(c for _, c in cycles)
    fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
    fig.text(0.075, 0.966, name, fontsize=22, weight="bold", color=INK, va="top")
    program = tr("循环拉伸") if cycles else tr("单调拉伸")
    description = tr("{0}   ·   {1} 段正式采集", program, len(records))
    if cycles:
        description += tr("   ·   {0} 个完整周次", len(completed))
    fig.text(0.077, 0.917, description, fontsize=10, color=MUTED)
    highlights = [
        (
            tr("首周拉伸弹性模量") if cycles else tr("首加载拉伸弹性模量"),
            fmt(fit["modulus_GPa"], 2) + " GPa"
            if fit["modulus_GPa"] is not None
            else tr("未测得"),
        )
    ]
    if cycles:
        highest = summary["max_fully_recoverable_applied_pct"]
        if highest is not None:
            displayed = f"{highest:.3f}%"
        elif (
            summary["recovery_assessed_cycles"]
            and not summary["fully_recoverable_cycles"]
        ):
            displayed = tr("无达标周")
        else:
            displayed = tr("未测得")
        highlights.append((tr("最大完全可恢复应变"), displayed))
    for (label, value), y in zip(highlights, (0.951, 0.906)):
        fig.text(
            0.690 if language() == "en" else 0.716,
            y,
            label,
            ha="right",
            va="center",
            fontsize=9.5,
            color=MUTED,
        )
        fig.text(
            0.928,
            y,
            value,
            ha="right",
            va="center",
            fontsize=22,
            weight="bold",
            color=MODULUS_COLOR,
        )
    quality = tr(
        "模量拟合    0.05%–0.15%    ·    {0} 个点    ·    R² = {1}",
        fit["n"],
        fmt(fit["r2"], 5),
    )
    if fit["modulus_GPa"] is None or fit["r2"] is not None and fit["r2"] < 0.995:
        quality += "    ·    " + diagnosis(fit["reason"])
    fig.text(0.077, 0.893, quality, fontsize=9, color=MUTED)
    fig.add_artist(
        Line2D(
            [0.077, 0.932],
            [0.875, 0.875],
            transform=fig.transFigure,
            color=ACCENT,
            lw=1,
        )
    )
    fig.text(
        0.077,
        0.849,
        tr("加载–卸载回线") if cycles else tr("拉伸曲线"),
        fontsize=12.5,
        weight="bold",
    )
    if completed:
        fig.text(0.416, 0.849, tr("周次"), fontsize=8, color=MUTED)
    ax = fig.add_axes(
        [0.115, 0.614 if cycles else 0.510, 0.79, 0.194 if cycles else 0.300]
    )
    history_figure(fig, ax, records, [0.478, 0.856, 0.425, 0.007])
    caption = segment_caption(records)
    if len(records) > 1:
        caption += tr("。各段应变沿用本段起点。")
    if caption:
        fig.text(0.110, 0.559, caption, fontsize=8.2, color=MUTED)
    if cycles:
        fig.text(
            0.077,
            0.528,
            tr("可恢复与残余应变随施加应变的变化"),
            fontsize=12.5,
            weight="bold",
        )
        if len(records) > 1:
            fig.text(
                0.924,
                0.529,
                tr("初测实心   ·   续测空心"),
                ha="right",
                color=MUTED,
                fontsize=8,
            )
        strain_response(fig, records)
    elif first["tensile"].get("fit_reason"):
        fig.text(
            0.110,
            0.450,
            diagnosis(first["event"]["basis"]) + tr("。"),
            fontsize=9,
            color=MUTED,
        )
    fig.text(
        0.077,
        0.282 if cycles else 0.394,
        tr("逐周性能") if cycles else tr("拉伸性能"),
        fontsize=12.5,
        weight="bold",
    )
    if cycles:
        if summary["recovery_assessed_cycles"]:
            stats = tr(
                "完全可恢复  {0} / {1} 周",
                summary["fully_recoverable_cycles"],
                summary["recovery_assessed_cycles"],
            )
            peak_cycles = summary["max_fully_recoverable_cycle_numbers"]
            if peak_cycles:
                where = (
                    tr("第 ") + tr("、").join(map(str, peak_cycles)) + tr(" 周")
                    if len(peak_cycles) <= 3
                    else tr("{0} 个周次", len(peak_cycles))
                )
                stats += tr("     ·     {0}达到最大值", where)
            fig.text(
                0.928,
                0.283,
                stats,
                ha="right",
                fontsize=8.5,
                color=ACCENT,
                weight="bold",
            )
        labels = [
            tr("段 / 周"),
            tr("峰值力\n(N)"),
            tr("峰值力处应力\n(MPa)"),
            tr("最大应变\n(%)"),
            tr("总应变\n(百分点)"),
            tr("可恢复\n(百分点)"),
            tr("段内残余\n(百分点)"),
            tr("卸载下限\n(MPa)"),
            tr("恢复判定"),
        ]
        selected = (
            cycles
            if len(cycles) <= 14
            else [cycles[i] for i in np.linspace(0, len(cycles) - 1, 14, dtype=int)]
        )
        rows = [
            [
                f"{r['sequence']} / {c['cycle']}"
                + (" *" if c["status"] != "complete" else ""),
                *[
                    fmt_residual(c[k])
                    if k == "residual_segment_pp"
                    else fmt(
                        c[k], 1 if k in ("peak_force_N", "stress_at_peak_MPa") else 3
                    )
                    for k in (
                        "peak_force_N",
                        "stress_at_peak_MPa",
                        "max_strain_pct",
                        "total_strain_pp",
                        "recoverable_pp",
                        "residual_segment_pp",
                        "end_stress_MPa",
                    )
                ],
                tr(RECOVERY_LABEL[c["fully_recoverable"]]),
            ]
            for r, c in selected
        ]
        note = (
            tr("* 为未完成段。")
            if any(c["status"] != "complete" for _, c in selected)
            else ""
        )
        note += (
            tr("表列代表周次，完整指标见逐周 CSV。")
            if len(selected) < len(cycles)
            else ""
        )
        note += tr(
            "实测卸载端点段内残余 < {0:g}% 判为完全可恢复。页首最大值取达标周的最高实测施加应变。",
            RESIDUAL_THRESHOLD_PP,
        )
    else:
        t = first["tensile"]
        peak = first["peak_observed"] or {}
        labels = [
            tr("最大力 (N)"),
            tr("最高应力 (MPa)"),
            tr("抗拉强度 (MPa)"),
            "Rp0.2 (MPa)",
            tr("断后伸长率 (%)"),
        ]
        rows = [
            [
                fmt(v)
                for v in (
                    peak.get("force_N"),
                    (first["peak_stress"] or {}).get("stress_MPa"),
                    t.get("uts_MPa"),
                    t.get("rp02_MPa"),
                    t.get("elongation_after_break_pct"),
                )
            ]
        ]
        note = diagnosis(first["event"]["basis"]) + tr("。")
    height = min(0.223, 0.028 + 0.0150 * len(rows))
    ta = fig.add_axes([0.074, (0.266 if cycles else 0.374) - height, 0.858, height])
    ta.axis("off")
    table = ta.table(
        cellText=rows,
        colLabels=labels,
        cellLoc="center",
        bbox=[0, 0, 1, 1],
        colWidths=(
            [0.086, 0.104, 0.118, 0.107, 0.1, 0.103, 0.103, 0.12, 0.159]
            if cycles and language() == "en"
            else None
        ),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7.3)
    for (i, col), cell in table.get_celld().items():
        cell.set_edgecolor("white")
        cell.set_facecolor(ACCENT if i == 0 else "#ecf3f3" if i % 2 else "#f7f9f9")
        if i == 0:
            cell.set_text_props(color="white", weight="bold")
            cell.set_height(cell.get_height() * 1.60)
        elif (
            cycles
            and col == len(labels) - 1
            and rows[i - 1][-1] == tr(RECOVERY_LABEL[True])
        ):
            cell.set_text_props(color=ACCENT, weight="bold")
    fig.text(0.078, 0.025, note, fontsize=8, color=MUTED)
    fig.savefig(destination / tr("样品单页.pdf"))
    plt.close(fig)
