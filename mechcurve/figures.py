"""Vector figures and shared report layout from source-linked event tables."""

import math
from .locale import tr, language
from pathlib import Path
import os
import unicodedata

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.colors import ListedColormap, Normalize
from matplotlib.lines import Line2D
import numpy as np
from .mechanics import RESIDUAL_THRESHOLD_PP

INK, MUTED, ACCENT = "#182e3e", "#546b78", "#006d77"
MODULUS_COLOR = "#922b37"
RECOVERY_LABEL = {True: "完全可恢复", False: "未达标", None: "—"}
SIZE = (11.69, 8.27)
STATUS = {
    "complete": "完整",
    "partial_loading": "加载未完成",
    "partial_unload": "卸载未完成",
    "fracture_candidate": "断裂候选段",
    "fracture_confirmed": "断裂终止",
}
EVENT = {
    "unlocated": "采样点未定位",
    "candidate": "曲线候选",
    "confirmed_record": "记录级确认",
    "confirmed_row": "行级确认",
}


def configure():
    preferred = os.environ.get("MECHCURVE_FONT")
    if preferred:
        font_manager.fontManager.addfont(preferred)
        # Common open font families ship regular and bold as separate files.
        regular = Path(preferred)
        bold = regular.with_name(regular.name.replace("-Regular.", "-Bold."))
        if bold != regular and bold.is_file():
            font_manager.fontManager.addfont(bold)
        face = font_manager.FontProperties(fname=preferred).get_name()
    else:
        installed = {f.name for f in font_manager.fontManager.ttflist}
        face = next(
            (
                f
                for f in (
                    "Microsoft YaHei",
                    "DengXian",
                    "SimHei",
                    "Noto Sans CJK SC",
                    "Noto Sans SC",
                    "WenQuanYi Zen Hei",
                    "PingFang SC",
                )
                if f in installed
            ),
            None,
        )
    if not face and language() == "en":
        face = "DejaVu Sans"
    if not face:
        raise RuntimeError(tr("需要中文字体，请通过 MECHCURVE_FONT 指定本地字体文件"))
    plt.rcParams.update(
        {
            "font.family": face,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "axes.unicode_minus": False,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#81949b",
            "text.color": INK,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.labelsize": 11,
            "font.size": 10,
        }
    )
    return face


def font_files(family):
    return {
        weight: Path(
            font_manager.findfont(
                font_manager.FontProperties(family=family, weight=weight)
            )
        )
        for weight in ("normal", "bold")
    }


def fmt(x, digits=3):
    return "—" if x is None else f"{x:.{digits}f}"


def fmt_residual(value):
    text = fmt(value)
    if (
        value is not None
        and value != RESIDUAL_THRESHOLD_PP
        and text == fmt(RESIDUAL_THRESHOLD_PP)
    ):
        return str(value)
    return text


def page(title, subtitle=""):
    fig = plt.figure(figsize=SIZE, facecolor="white")
    fig.text(0.065, 0.925, title, fontsize=23, weight="bold", va="top")
    fig.text(0.067, 0.856, subtitle, fontsize=11, color=MUTED, va="top")
    fig.add_artist(
        Line2D(
            [0.067, 0.935],
            [0.824, 0.824],
            transform=fig.transFigure,
            color=ACCENT,
            lw=1.2,
        )
    )
    return fig


def footer(fig, name, number):
    fig.text(0.066, 0.032, name, color=MUTED, fontsize=8)
    fig.text(0.932, 0.032, str(number), color=MUTED, ha="right", fontsize=8)


def wrapped(s, width=100):
    lines, line, n = [], "", 0
    for c in s:
        w = 2 if unicodedata.east_asian_width(c) in "WF" else 1
        if c == "\n" or n + w > width:
            lines.append(line)
            line, n = "", 0
        if c != "\n":
            line += c
            n += w
    return lines + [line]


def text_pages(pdf, title, subtitle, blocks, label, counter):
    fig = page(title, subtitle)
    y = 0.766
    for heading, body in blocks:
        lines = wrapped(body, 123)
        if y - 0.044 - 0.034 * (min(2, len(lines)) - 1) <= 0.105:
            footer(fig, label, counter)
            pdf.savefig(fig)
            plt.close(fig)
            counter += 1
            fig, y = page(title, subtitle), 0.766
        for i, line in enumerate([heading, *lines]):
            if y <= 0.105:
                footer(fig, label, counter)
                pdf.savefig(fig)
                plt.close(fig)
                counter += 1
                fig, y = page(title, subtitle), 0.766
            fig.text(
                0.069,
                y,
                line,
                va="top",
                fontsize=13 if i == 0 else 11,
                color=ACCENT if i == 0 else INK,
                weight="bold" if i == 0 else "normal",
            )
            y -= 0.044 if i == 0 else 0.034
        y -= 0.014
    footer(fig, label, counter)
    pdf.savefig(fig)
    plt.close(fig)
    return counter + 1


def table_pages(pdf, title, subtitle, columns, rows, widths, label, counter):
    for start in range(0, len(rows) or 1, 14):
        chunk = rows[start : start + 14] or [["—"] * len(columns)]
        fig = page(title, subtitle)
        ax = fig.add_axes([0.063, 0.11, 0.878, 0.65])
        ax.axis("off")
        height = min(0.98, (len(chunk) + 1) * 0.068)
        table = ax.table(
            cellText=chunk,
            colLabels=columns,
            cellLoc="center",
            colWidths=widths,
            bbox=[0, 1 - height, 1, height],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        for (r, c), cell in table.get_celld().items():
            cell.set_edgecolor("white")
            cell.set_facecolor(ACCENT if r == 0 else "#eef4f4" if r % 2 else "#f8fafa")
            if r == 0:
                cell.set_text_props(color="white", weight="bold")
        footer(fig, label, counter)
        pdf.savefig(fig)
        plt.close(fig)
        counter += 1
    return counter


def plot_axis(ax, xlabel, ylabel):
    ax.set(xlabel=xlabel, ylabel=ylabel)
    ax.tick_params(direction="out", length=3.2, width=0.75, pad=3)
    ax.spines[["left", "bottom"]].set(linewidth=0.8, color="#38444c")
    ax.margins(x=0.04, y=0.08)


def note_segments(points):
    start = 0
    for i in range(1, len(points) + 1):
        if (
            i == len(points)
            or points[i]["phase"] != points[start]["phase"]
            or (
                points[i]["time_s"] is not None
                and points[i - 1]["time_s"] is not None
                and points[i]["time_s"] < points[i - 1]["time_s"]
            )
        ):
            yield points[start]["phase"], points[start:i]
            start = i


def axes_values(points, key):
    return np.array([np.nan if p[key] is None else p[key] for p in points])


def cycle_color(n, max_cycle):
    palette = ["#1665a1", "#c75a17", "#168373", "#85548d", "#956631", "#54758e"]
    return (
        palette[(n - 1) % 6]
        if max_cycle <= 6
        else plt.get_cmap("viridis")(0.12 + 0.66 * (n - 1) / (max_cycle - 1))
    )


def trace_axes(ax, record, max_cycle, markers, axes_keys=None):
    ps, cs = record["points"], record["cycles"]
    xkey = (
        "strain_pct"
        if any(p["strain_pct"] is not None for p in ps)
        else "extension_mm"
        if any(p["extension_mm"] is not None for p in ps)
        else "time_s"
    )
    ykey = "stress_MPa" if any(p["stress_MPa"] is not None for p in ps) else "force_N"
    if axes_keys is not None:
        xkey, ykey = axes_keys
    xlabel = {
        "strain_pct": tr("拉伸应变 (%)"),
        "extension_mm": tr("位移 (mm)"),
        "time_s": tr("时间 (s)"),
    }[xkey]
    ylabel = {"stress_MPa": tr("拉伸应力 (MPa)"), "force_N": tr("力 (N)")}[ykey]
    plot_axis(ax, xlabel, ylabel)
    idx = {p["source_row"]: i for i, p in enumerate(ps)}
    if not cs:
        for _, block in note_segments(ps):
            ax.plot(
                axes_values(block, xkey), axes_values(block, ykey), lw=1.6, color=ACCENT
            )
    for c in cs:
        first, stop = idx[c["start_row"]], idx[c["observed_end_row"]]
        turn = idx.get(c["turn_row"], stop)
        col = (
            cycle_color(c["cycle"], max_cycle)
            if c["status"] == "complete"
            else "#6d7783"
        )
        for block, style in [(ps[first : turn + 1], "-"), (ps[turn : stop + 1], "--")]:
            ax.plot(
                axes_values(block, xkey),
                axes_values(block, ykey),
                style,
                color=col,
                lw=1.5 if markers else 1.15,
                solid_capstyle="round",
                dash_capstyle="round",
            )
        for key, m, size in [
            ("turn_row", "s", 52),
            ("peak_force_row", "^", 24),
            ("end_row", "o", 22),
        ]:
            if markers and c[key] in idx:
                p = ps[idx[c[key]]]
                if p[xkey] is not None and p[ykey] is not None:
                    ax.scatter(
                        p[xkey],
                        p[ykey],
                        marker=m,
                        s=size,
                        facecolors="none",
                        edgecolors=col,
                        lw=1,
                        zorder=4,
                    )
    for phase, block in note_segments(ps):
        if phase in ("low_load_excursion", "after_event", "unclassified"):
            ax.plot(
                axes_values(block, xkey),
                axes_values(block, ykey),
                color="#758087",
                lw=1,
                ls=":",
            )
    return xkey, ykey, xlabel, ylabel, idx


def paper_curve(record, name, seq, max_cycle):
    from matplotlib.transforms import blended_transform_factory

    fig = plt.figure(figsize=(4.65, 3.95))
    fig.text(
        0.16,
        0.96,
        name + (tr("   /   采集段 {0}", seq) if seq > 1 else ""),
        fontsize=10,
        weight="bold",
        va="top",
    )
    ax = fig.add_axes([0.16, 0.285, 0.795, 0.47])
    xkey, ykey, _, _, idx = trace_axes(ax, record, max_cycle, False)
    ax.set_xlabel(
        {
            "strain_pct": "Tensile strain (%)",
            "extension_mm": "Extension (mm)",
            "time_s": "Time (s)",
        }[xkey],
        fontsize=9,
    )
    ax.set_ylabel(
        "Tensile stress (MPa)" if ykey == "stress_MPa" else "Force (N)", fontsize=9
    )
    ax.tick_params(labelsize=8)
    cs = [c for c in record["cycles"] if c["status"] == "complete"]
    keys = []
    if cs:
        keys = [
            Line2D([], [], color=INK, lw=1.0, ls=style, label=title)
            for style, title in (("-", "Loading"), ("--", "Unloading"))
        ]
    if cs and len(cs) != len(record["cycles"]):
        keys.append(Line2D([], [], color="#6d7783", lw=1.0, label="Unfinished"))
    event = record["event"]
    if event["source_row"] in idx:
        point = record["points"][idx[event["source_row"]]]
        if point[xkey] is not None and point[ykey] is not None:
            marker = ax.scatter(
                point[xkey],
                point[ykey],
                marker="x",
                color=INK,
                s=28,
                zorder=5,
                label="Fracture"
                if event["status"] == "confirmed_row"
                else "Fracture candidate",
            )
            keys.append(marker)
    if keys:
        ax.legend(
            handles=keys, loc="best", frameon=False, fontsize=6.5, handlelength=2.0
        )
    if cs:
        nums = [c["cycle"] for c in cs]
        if len(nums) <= 6:
            handles = [
                Line2D([], [], color=cycle_color(n, max_cycle), label=str(n), lw=2.2)
                for n in nums
            ]
            fig.legend(
                handles=handles,
                title="Cycle",
                loc="upper left",
                bbox_to_anchor=(0.145, 0.906),
                ncol=len(nums),
                frameon=False,
                fontsize=7,
                title_fontsize=7,
                handlelength=1.25,
                columnspacing=0.95,
            )
        else:
            cmap = matplotlib.colors.ListedColormap(
                [cycle_color(n, max_cycle) for n in nums]
            )
            bar = fig.colorbar(
                plt.cm.ScalarMappable(
                    norm=plt.Normalize(nums[0] - 0.5, nums[-1] + 0.5), cmap=cmap
                ),
                cax=fig.add_axes([0.28, 0.86, 0.66, 0.014]),
                orientation="horizontal",
            )
            bar.set_ticks(
                nums if len(nums) <= 12 else nums[:: math.ceil(len(nums) / 10)]
            )
            bar.ax.tick_params(labelsize=6.5, length=2, pad=1)
            bar.outline.set_visible(False)
            fig.text(0.16, 0.867, "Cycle", fontsize=7.5, va="center")
        last = cs[-1]
        if (
            xkey == "strain_pct"
            and last["recoverable_pp"] is not None
            and last["recoverable_pp"] > 0
        ):
            transform = blended_transform_factory(ax.transData, fig.transFigure)
            lo, hi = last["end_strain_pct"], last["turn_strain_pct"]
            ax.annotate(
                "",
                xy=(hi, 0.106),
                xytext=(lo, 0.106),
                xycoords=transform,
                textcoords=transform,
                arrowprops={
                    "arrowstyle": "<->",
                    "lw": 0.8,
                    "color": INK,
                    "shrinkA": 0,
                    "shrinkB": 0,
                },
                annotation_clip=False,
            )
            floor = (
                fmt(last["end_stress_MPa"], 1) + " MPa"
                if last["end_stress_MPa"] is not None
                else fmt(last["end_force_N"], 1) + " N"
            )
            fig.text(
                0.55,
                0.044,
                f"Cycle {last['cycle']} recovery   {last['recoverable_pp']:.3f} pp   at   {floor}",
                ha="center",
                fontsize=7.8,
            )
    return fig


def acquisition_axis(record):
    if "time_s" in record["channels"]:
        return "time_s", tr("时间 (s)")
    return "source_row", "Source row" if language() == "en" else "原始行"


def curve_page(record, name, seq, max_cycle):
    ps, cs = (
        record["points"],
        [c for c in record["cycles"] if c["status"] == "complete"],
    )
    fig = page(name, tr("采集段 {0}   ·   应力–应变与逐周响应", seq))
    ax = fig.add_axes([0.085, 0.195, 0.49, 0.535])
    side = fig.add_axes([0.675, 0.475, 0.24, 0.25])
    lower = fig.add_axes([0.675, 0.155, 0.24, 0.215])
    xkey, ykey, xlabel, ylabel, idx = trace_axes(ax, record, max_cycle, True)

    def color(n):
        return cycle_color(n, max_cycle)

    for axis, letter in ((ax, "a"), (side, "b"), (lower, "c")):
        axis.text(
            -0.13, 1.055, letter, transform=axis.transAxes, weight="bold", fontsize=12
        )
    if cs:
        marks = [
            Line2D([], [], marker=m, ls="none", mfc="none", mec=INK, label=label)
            for m, label in [
                ("^", tr("峰值力")),
                ("s", tr("加载换向")),
                ("o", tr("卸载端点")),
            ]
        ]
        marks += [
            Line2D([], [], color=MUTED, ls=s, label=label)
            for s, label in [("-", tr("加载")), ("--", tr("卸载"))]
        ]
        ax.legend(
            handles=marks,
            loc="lower left",
            bbox_to_anchor=(-0.02, -0.245),
            ncol=5,
            fontsize=8,
            frameon=False,
        )
        nums = [c["cycle"] for c in cs]
        if max_cycle > 6:
            cmap = matplotlib.colors.ListedColormap(
                [color(n) for n in range(1, max_cycle + 1)]
            )
            bar = fig.colorbar(
                plt.cm.ScalarMappable(
                    norm=plt.Normalize(0.5, max_cycle + 0.5), cmap=cmap
                ),
                cax=fig.add_axes([0.105, 0.771, 0.445, 0.015]),
                orientation="horizontal",
            )
            ticks = list(range(1, max_cycle + 1, max(1, math.ceil(max_cycle / 17))))
            bar.set_ticks(ticks)
            bar.ax.tick_params(labelsize=7, pad=0)
            bar.outline.set_visible(False)
        else:
            handles = [
                Line2D([], [], color=color(n), lw=2.5, label=tr("第 {0} 周", n))
                for n in nums
            ]
            ax.legend_ = ax.get_legend()
            ax.add_artist(ax.legend_)
            ax.legend(
                handles=handles,
                ncol=6,
                loc="lower left",
                bbox_to_anchor=(0, 1.02),
                frameon=False,
                fontsize=8,
            )
        vals = [
            c["max_stress_MPa"] if ykey == "stress_MPa" else c["peak_force_N"]
            for c in cs
        ]
        side.scatter(
            [np.nan if c["max_strain_pct"] is None else c["max_strain_pct"] for c in cs]
            if xkey == "strain_pct"
            else nums,
            [np.nan if v is None else v for v in vals],
            c=[color(n) for n in nums],
            s=26,
        )
        plot_axis(
            side,
            tr("最大加载应变 (%)") if xkey == "strain_pct" else tr("周次"),
            tr("峰值应力 (MPa)") if ykey == "stress_MPa" else tr("峰值力 (N)"),
        )
        for field, label, col in [
            ("total_strain_pp", tr("总应变"), "#4565a6"),
            ("recoverable_pp", tr("可恢复"), "#008860"),
            ("residual_segment_pp", tr("段内残余"), "#D55E00"),
        ]:
            lower.plot(
                nums,
                [np.nan if c[field] is None else c[field] for c in cs],
                ".-",
                label=label,
                color=col,
            )
        plot_axis(lower, tr("周次"), tr("应变差 (百分点)"))
        lower.xaxis.set_major_locator(
            matplotlib.ticker.MaxNLocator(integer=True, nbins=7)
        )
        lower.legend(
            loc="lower left",
            bbox_to_anchor=(0, 1.01),
            ncol=3,
            fontsize=7,
            frameon=False,
        )
        if xkey != "strain_pct":
            lower.clear()
            field = "end_stress_MPa" if ykey == "stress_MPa" else "end_force_N"
            lower.plot(
                nums,
                [np.nan if c[field] is None else c[field] for c in cs],
                "o-",
                color=ACCENT,
            )
            plot_axis(
                lower,
                tr("周次"),
                tr("卸载下限 (MPa)") if ykey == "stress_MPa" else tr("卸载下限 (N)"),
            )
    else:
        order_key, order_label = acquisition_axis(record)
        for small, key, lab in [(side, ykey, ylabel), (lower, xkey, xlabel)]:
            small.plot(
                axes_values(ps, order_key), axes_values(ps, key), lw=1.4, color=ACCENT
            )
            plot_axis(small, order_label, lab)
        fit = record["tensile"].get("fit")
        if fit and xkey == "strain_pct" and ykey == "stress_MPa":
            window = ps[idx[fit["first_row"]] : idx[fit["last_row"]] + 1]
            ax.plot(
                axes_values(window, xkey),
                axes_values(window, ykey),
                lw=3,
                color="#d55e00",
                label=tr("模量拟合窗口"),
            )
            if record["tensile"].get("rp02_rows"):
                proof_fit = record["tensile"].get("proof_fit", fit)
                hi = idx[record["tensile"]["rp02_rows"][-1]]
                strain = np.array([window[0][xkey] + 0.2, ps[hi][xkey]])
                ax.plot(
                    strain,
                    proof_fit["slope_MPa"] * (strain / 100 - 0.002)
                    + proof_fit["intercept_MPa"],
                    ":",
                    color=MUTED,
                    label=tr("0.2% 偏移线"),
                )
            ax.legend(frameon=False)
    return fig


def diagnostic(record, name, seq):
    ps = record["points"]
    order_key, order_label = acquisition_axis(record)
    event = record["event"]
    fig = page(name, tr("采集段 {0}   ·   载荷历程与终止区间", seq))
    for col in (0, 1):
        center = event["index"] if event["index"] is not None else len(ps) - 1
        block = (
            ps
            if col == 0
            else ps[
                max(0, center - max(12, round(len(ps) * 0.07))) : min(
                    len(ps), center + max(12, round(len(ps) * 0.04))
                )
            ]
        )
        for row, key in enumerate(
            [
                "force_N" if "force_N" in record["channels"] else "stress_MPa",
                "strain_pct" if "strain_pct" in record["channels"] else "extension_mm",
            ]
        ):
            ax = fig.add_axes([0.09 + 0.48 * col, 0.49 - 0.335 * row, 0.365, 0.24])
            ax.plot(
                axes_values(block, order_key),
                axes_values(block, key),
                color=ACCENT if row == 0 else "#4565a6",
                lw=1.4,
            )
            plot_axis(
                ax,
                order_label,
                {
                    "force_N": tr("力 (N)"),
                    "strain_pct": tr("应变 (%)"),
                    "stress_MPa": tr("应力 (MPa)"),
                    "extension_mm": tr("位移 (mm)"),
                }[key],
            )
            if row == 0:
                ax.set_title(
                    tr("全记录") if col == 0 else tr("终止区间放大"), fontsize=11
                )
            if event["index"] is not None and ps[center][order_key] is not None:
                ax.axvline(ps[center][order_key], ls="--", color="#c85835")
    return fig


def history_figure(fig, ax, records, colorbar_bounds):
    points = [r["points"] for r in records]

    def shared(keys):
        return next(
            (
                k
                for k in keys
                if all(any(p[k] is not None for p in block) for block in points)
            ),
            None,
        )

    axes_keys = (
        shared(("strain_pct", "extension_mm", "time_s")),
        shared(("stress_MPa", "force_N")),
    )
    if None in axes_keys:
        ax.set_axis_off()
        ax.text(
            0.5,
            0.5,
            tr("采集段缺少共同的物理通道，分段曲线见详细报告"),
            ha="center",
            transform=ax.transAxes,
        )
        return
    complete = [
        c["cycle"] for r in records for c in r["cycles"] if c["status"] == "complete"
    ]
    max_cycle = max(complete, default=1)
    for record in records:
        trace_axes(ax, record, max_cycle, False, axes_keys)
    if complete:
        colors = ListedColormap(
            [cycle_color(i, max_cycle) for i in range(1, max_cycle + 1)]
        )
        bar = fig.colorbar(
            plt.cm.ScalarMappable(norm=Normalize(0.5, max_cycle + 0.5), cmap=colors),
            cax=fig.add_axes(colorbar_bounds),
            orientation="horizontal",
        )
        step = max(1, math.ceil(max_cycle / 14))
        bar.set_ticks(sorted(set([*range(1, max_cycle + 1, step), max_cycle])))
        bar.ax.tick_params(labelsize=7, length=2, pad=1)
        bar.outline.set_visible(False)
        ax.legend(
            handles=[
                Line2D([], [], color=INK, ls=style, lw=1.3, label=text)
                for style, text in [("-", tr("加载")), ("--", tr("卸载"))]
            ],
            loc="best",
            frameon=False,
            fontsize=8,
        )


def merged_figure(destination, name, records):
    fig = plt.figure(figsize=(6.4, 4.7))
    fig.text(0.10, 0.935, name + tr(" · 合并回线"), fontsize=14, weight="bold")
    fig.text(0.105, 0.865, tr("周次"), fontsize=8)
    ax = fig.add_axes([0.14, 0.16, 0.80, 0.60])
    history_figure(fig, ax, records, [0.19, 0.875, 0.70, 0.014])
    fig.text(
        0.14,
        0.027,
        tr("各段沿用导出应变零点，按实际加载顺序连续编号。"),
        fontsize=8,
        color=MUTED,
    )
    for extension in ("pdf", "png", "svg"):
        fig.savefig(destination / (tr("合并回线.") + extension), dpi=300)
    plt.close(fig)


def segment_files(seq):
    return [
        tr("段{0:02d}_论文单图.{1}", seq, ext)
        if kind is None
        else tr("段{0:02d}_{1}.{2}", seq, tr(kind), ext)
        for kind in (None, "曲线", "终止判读")
        for ext in ("pdf", "svg", "png")
    ]


def render_segment(folder, name, record, seq, max_cycle):
    files = iter(segment_files(seq))
    for make in (
        lambda: paper_curve(record, name, seq, max_cycle),
        lambda: curve_page(record, name, seq, max_cycle),
        lambda: diagnostic(record, name, seq),
    ):
        fig = make()
        try:
            for _ in range(3):
                fig.savefig(folder / next(files), dpi=300)
        finally:
            plt.close(fig)
