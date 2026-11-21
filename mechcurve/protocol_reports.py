"""Specimen and campaign views for mixed protocols, with row-linked metrics."""

from collections import Counter
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
from .figures import (
    ACCENT,
    INK,
    MUTED,
    MODULUS_COLOR,
    plot_axis,
    table_pages,
    text_pages,
)
from .locale import language, tr
from .protocols import TITLES, axis_info

METRICS = {
    "window_slope": ("指定窗口斜率", "Selected-window slope"),
    "signed_path_integral": ("有符号载荷–行程积分", "Signed load–travel integral"),
    "peak_compressive_stress": ("最大压应力幅值", "Peak compressive stress magnitude"),
    "compression_modulus": ("首加载压缩模量", "Initial compression modulus"),
    "nominal_flexural_stress": (
        "名义外纤维弯曲应力峰值",
        "Peak nominal outer-fiber stress",
    ),
    "peak_torque": ("峰值扭矩幅值", "Peak torque magnitude"),
    "nominal_surface_shear": (
        "名义表面切应力峰值",
        "Peak nominal surface shear stress",
    ),
    "peak_shear_stress": ("峰值剪切应力幅值", "Peak shear stress magnitude"),
    "maximum_depth": ("最大压入深度", "Maximum depth"),
    "peak_peel_force_per_width": ("单位宽度峰值剥离力", "Peak peel force per width"),
    "highest_observed_cycle": ("最高观测周次", "Highest observed cycle"),
    "hold_duration": ("保持时长", "Hold duration"),
    "creep_change": ("保持期间的变化量", "Change during hold"),
    "mean_hold_rate": ("保持期间的平均变化率", "Mean rate over hold"),
    "relaxation_drop": ("保持期间的响应降幅", "Response drop during hold"),
    "retained_response": ("保持结束时的响应比例", "Retained response"),
    "maximum_response": ("纵坐标最大值", "Maximum response"),
    "minimum_response": ("纵坐标最小值", "Minimum response"),
    "x_at_maximum_response": (
        "纵坐标最大值处的横坐标",
        "Coordinate at maximum response",
    ),
    "modulus_GPa": ("首加载拉伸模量", "First-loading tensile modulus"),
    "max_fully_recoverable_applied_pct": (
        "最大完全可恢复应变",
        "Max fully recoverable applied strain",
    ),
    "peak_to_peak_amplitude": ("最大观测周期幅值", "Largest observed cycle amplitude"),
    "mean_extrema": ("峰谷中值", "Midrange of extrema"),
    "max_indentation_force": ("最大压入力幅值", "Peak indentation force magnitude"),
}
WARN = {
    "torsion_geometry": (
        "缺少截面直径，保留实测扭矩。",
        "Shaft diameter is required for nominal surface stress.",
    ),
    "integral_gap": (
        "数据存在间断，无法积分全程。",
        "A gap prevents full-path integration.",
    ),
    "window_unusable": (
        "所选窗口缺测、跨换向或有效点不足。",
        "Selected window is incomplete, reverses, or lacks distinct observations.",
    ),
    "fatigue_no_cycle": (
        "未观测到完整峰到峰周期。",
        "No complete peak-to-peak excursion observed.",
    ),
    "hold_unconfirmed": (
        "缺保持控制通道或保持行区间。",
        "Supply a control channel or confirm the hold rows.",
    ),
    "hold_varies": (
        "控制通道在选定范围内变化超过 2% 或中值为零，请核对保持区间。",
        "Control varies by more than 2% or has zero median. Review hold rows.",
    ),
    "hold_discontinuous": (
        "保持区间内有缺测、行间断或时间未递增。",
        "Hold contains a gap, missing observation or non-increasing time.",
    ),
    "fit_unavailable": (
        "首加载拟合窗口不可用。",
        "First-loading fit window unavailable.",
    ),
    "flexure_geometry": (
        "未给出梁截面及夹具几何，保留实测响应。",
        "Beam section and fixture geometry are required for nominal flexural stress.",
    ),
}
BASIS = {
    "native_units": ("保留原始单位", "original instrument units"),
    "constant_control": (
        "近恒定控制通道及单向响应",
        "near-constant control and directional response",
    ),
    "notes": ("实验备注", "record notes"),
    "loading_program": ("加载程序", "loading program"),
    "channels": ("专用物理通道", "protocol channels"),
    "channel_names": ("表头", "channel names"),
    "record_name": ("采集名称", "acquisition name"),
    "signed_axes": ("应力与应变符号", "signed stress and strain"),
    "axial_channels": ("轴向通道", "axial channels"),
    "mapped_axes": ("指定坐标", "specified axes"),
    "measured_axes": ("实测坐标", "measured coordinates"),
    "ambiguous": ("试验类型待确认", "method requires confirmation"),
}


def local(zh, en):
    return en if language() == "en" else zh


def title(mode):
    return local(*TITLES[mode])


def displayed_axis(axis):
    label = axis[language()]
    return f"{label} ({axis['unit']})" if axis["unit"] else label


def curve_of(record):
    if "curve" in record:
        return record["curve"]
    pts = record["points"]
    x = next(
        k
        for k in ("strain_pct", "extension_mm", "time_s", "source_row")
        if any(p.get(k) is not None for p in pts)
    )
    y = next(
        k for k in ("stress_MPa", "force_N") if any(p.get(k) is not None for p in pts)
    )
    fit = record["initial_loading_fit"]
    metrics = []
    if fit.get("modulus_GPa") is not None:
        metrics.append(
            dict(
                metric="modulus_GPa",
                value=fit["modulus_GPa"],
                unit="GPa",
                source_rows=fit["source_rows"],
            )
        )
    recovery = record.get("recovery_summary", {})
    highest = recovery.get("max_fully_recoverable_applied_pct")
    if highest is not None:
        rows = [
            c["turn_row"]
            for c in record["cycles"]
            if c["cycle"] in recovery["max_fully_recoverable_cycle_numbers"]
        ]
        metrics.append(
            dict(
                metric="max_fully_recoverable_applied_pct",
                value=highest,
                unit="%",
                source_rows=rows,
            )
        )
    return dict(x=axis_info(x, {}), y=axis_info(y, {}), metrics=metrics, warnings=[])


def series(ax, r, axis=None):
    curve = curve_of(r)
    if axis is not None:
        curve = {**curve, "y": axis}
    x, y = curve["x"]["key"], curve["y"]["key"]
    if "curve" not in r and r["cycles"] and x != "source_row":
        from .figures import trace_axes

        trace_axes(ax, r, max(c["cycle"] for c in r["cycles"]), False, (x, y))
        return
    xs = []
    ys = []
    prev = None
    for p in r["points"]:
        t = p.get("time_s")
        if prev and (
            p["source_row"] != prev["source_row"] + 1
            or (t is not None and prev.get("time_s") is not None and t < prev["time_s"])
        ):
            xs.append(np.nan)
            ys.append(np.nan)
        xs.append(p.get(x))
        ys.append(p.get(y))
        prev = p
    # Cycle-index tables can contain observations on independent specimens.
    scatter = r["test_type"] == "fatigue" and x == "cycle_count"
    ax.plot(
        xs,
        ys,
        ls="none" if scatter else "-",
        marker="o" if scatter or len(xs) < 4 else None,
        markersize=4,
        lw=1.6,
        color=ACCENT,
    )
    if curve.get("coordinate_fit") and axis is None:
        fit = curve["coordinate_fit"]
        rows = set(fit["source_rows"])
        xx = np.array([p[x] for p in r["points"] if p["source_row"] in rows])
        ax.plot(
            xx,
            xx * fit["slope"] + fit["intercept"],
            "--",
            color=MODULUS_COLOR,
            label=local("窗口拟合", "Window fit"),
        )
        ax.legend(loc="best", frameon=False, fontsize=8)
    if curve.get("hold"):
        ax.text(
            0.98,
            0.95,
            local("保持区间", "Hold interval"),
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=8,
            color=ACCENT,
        )
        ends = set(curve["hold"]["source_rows"])
        xends = [p[x] for p in r["points"] if p["source_row"] in ends]
        ax.axvspan(*xends, color="#488569", alpha=0.12)
    plot_axis(ax, displayed_axis(curve["x"]), displayed_axis(curve["y"]))
    ax.grid(axis="y", alpha=0.16)


def record_asset_paths(seq):
    return [f"curve-{seq:02d}.{ext}" for ext in ("pdf", "svg", "png")]


def record_figure(folder, name, r):
    fig, ax = plt.subplots(figsize=(7.4, 4.8), layout="constrained")
    ax.set_title(
        name + "   ·   " + title(r["test_type"]), loc="left", fontsize=15, color=INK
    )
    series(ax, r)
    for f in record_asset_paths(r["sequence"]):
        fig.savefig(folder / f, dpi=200)
    plt.close(fig)


def evidence(row_ids):
    if not row_ids:
        return "—"
    if len(row_ids) <= 4:
        return ", ".join(map(str, row_ids))
    return f"{row_ids[0]}–{row_ids[-1]}  (n={len(row_ids)})"


def specimen_sheet(folder, name, records):
    fig = plt.figure(figsize=(8.27, 11.69), facecolor="white")
    fig.text(0.08, 0.955, name, fontsize=21, weight="bold", color=INK, va="top")
    kinds = list(dict.fromkeys(title(r["test_type"]) for r in records))
    fig.text(0.08, 0.91, " / ".join(kinds), fontsize=12, color=ACCENT)
    fig.text(
        0.08,
        0.872,
        local("采集段", "Acquisitions") + f"   {len(records)}",
        fontsize=10,
        color=MUTED,
    )
    lead_order = {
        "compression": "compression_modulus",
        "creep": "mean_hold_rate",
        "relaxation": "retained_response",
        "generic": "window_slope",
    }
    if len(records) == 1:
        r = records[0]
        ms = curve_of(r)["metrics"]
        main = next(
            (m for m in ms if m["metric"] == lead_order.get(r["test_type"])),
            next(iter(ms), None),
        )
        if main:
            fig.text(
                0.93,
                0.944,
                local(*METRICS[main["metric"]]),
                ha="right",
                fontsize=9,
                color=MUTED,
            )
            fig.text(
                0.93,
                0.895,
                f"{main['value']:.5g} {main['unit']}",
                ha="right",
                fontsize=20,
                weight="bold",
                color=MODULUS_COLOR,
            )
    visible = records[:4]
    n = len(visible)
    for i, r in enumerate(visible):
        if n == 1:
            pos = [0.13, 0.50, 0.79, 0.30]
        elif n == 2:
            pos = [0.13, 0.635 - 0.21 * i, 0.79, 0.145]
        else:
            pos = [0.12 + 0.47 * (i % 2), 0.65 - 0.22 * (i // 2), 0.34, 0.13]
        ax = fig.add_axes(pos)
        series(ax, r)
        ax.tick_params(labelsize=8)
        ax.set_title(
            f"{r['sequence']:02d}   {title(r['test_type'])}", loc="left", fontsize=9
        )
    fig.text(
        0.08,
        0.371,
        local("观测指标", "Observed metrics"),
        weight="bold",
        fontsize=14,
        color=INK,
    )
    candidates = [(r, m) for r in records for m in curve_of(r)["metrics"]]
    # Each acquisition gets a representative metric before showing extra quantities.
    first = [(r, curve_of(r)["metrics"][0]) for r in records if curve_of(r)["metrics"]]
    featured = {(r["record"], m["metric"]) for r, m in first}
    selection = (
        first
        + [(r, m) for r, m in candidates if (r["record"], m["metric"]) not in featured]
    )[:7]
    for i, (r, m) in enumerate(selection):
        yy = 0.333 - i * 0.034
        fig.text(
            0.08,
            yy,
            f"{r['sequence']:02d}   " + local(*METRICS[m["metric"]]),
            fontsize=9,
        )
        fig.text(
            0.77,
            yy,
            f"{m['value']:.5g} {m['unit']}",
            ha="right",
            weight="bold",
            color=MODULUS_COLOR,
            fontsize=11,
        )
        fig.text(
            0.935, yy, evidence(m["source_rows"]), ha="right", color=MUTED, fontsize=8
        )
    fig.text(
        0.935,
        0.373,
        local("原始行", "Source rows"),
        ha="right",
        fontsize=9,
        color=MUTED,
    )
    warnings = list(dict.fromkeys(w for r in records for w in curve_of(r)["warnings"]))
    if warnings:
        fig.text(0.08, 0.083, local(*WARN[warnings[0]]), fontsize=8, color=MUTED)
    fig.text(
        0.08,
        0.045,
        local(
            "全部采集、单位、取点依据及判定条件见样品详报。",
            "See the specimen report for all acquisitions, units, source rows and conditions.",
        ),
        fontsize=9,
        color=MUTED,
    )
    fig.savefig(folder / tr("样品单页.pdf"))
    plt.close(fig)


def specimen_detail(folder, name, records):
    with PdfPages(folder / tr("样品报告.pdf")) as pdf:
        n = 1
        for r in records:
            curve = curve_of(r)
            subtitle = (
                title(r["test_type"]) + "   ·   " + local(*BASIS[r["classification"]])
            )
            blocks = [
                (local("采集记录", "Acquisition"), r["record"]),
                (
                    local("坐标", "Coordinates"),
                    displayed_axis(curve["x"]) + " × " + displayed_axis(curve["y"]),
                ),
            ]
            if r["plot_role"] == "preliminary":
                blocks.append(
                    (local("用途", "Role"), local("试运行", "Preliminary acquisition"))
                )
            if curve.get("hold"):
                blocks.append(
                    (
                        local("保持区间原始行", "Hold endpoint rows"),
                        evidence(curve["hold"]["source_rows"]),
                    )
                )
            if curve.get("modulus_fit"):
                fit = curve["modulus_fit"]
                blocks.append(
                    (
                        local("压缩模量拟合", "Compression modulus fit"),
                        f"0.05%–0.15%   ·   n={fit['n']}   ·   R²={fit['r2'] if fit['r2'] is not None else '—'}",
                    )
                )
            blocks.extend(
                (local("说明", "Condition"), local(*WARN[w])) for w in curve["warnings"]
            )
            blocks.extend(
                (a["heading"], f"{a['text']}   [{a['record']}, {a['row']}]")
                for a in r["interpretation"]
            )
            n = text_pages(pdf, name, subtitle, blocks, name, n)
            if r["plot_role"] == "main":
                fig, ax = plt.subplots(figsize=(9, 5.5), layout="constrained")
                series(ax, r)
                ax.set_title(name + " · " + title(r["test_type"]), loc="left")
                pdf.savefig(fig)
                plt.close(fig)
                n += 1
            if "curve" not in r and r["plot_role"] == "main":
                from .reports import modulus_detail, sample_blocks

                n = text_pages(pdf, name, subtitle, sample_blocks([r], []), name, n)
                fig = modulus_detail(r, name)
                pdf.savefig(fig)
                plt.close(fig)
                n += 1
            if curve.get("coordinate_fit"):
                fit = curve["coordinate_fit"]
                blocks = [
                    (
                        local("拟合点与质量", "Linear fit diagnostics"),
                        f"n={len(fit['source_rows'])}   R²={fit['r2']:.6g}   intercept={fit['intercept']:.6g} {curve['y']['unit']}",
                    )
                ]
                n = text_pages(pdf, name, subtitle, blocks, name, n)
            waves = curve.get("fatigue_cycles", [])
            if waves:
                shown = waves if len(waves) <= 12 else waves[:6] + waves[-6:]
                wave_rows = [
                    [
                        c["cycle"],
                        f"{c['amplitude']:.5g}",
                        f"{c['mean_extrema']:.5g}",
                        f"{c['load_ratio']:.4g}"
                        if c["load_ratio"] is not None
                        else "—",
                        c["peak_row"],
                        c["valley_row"],
                        c["next_peak_row"],
                    ]
                    for c in shown
                ]
                n = table_pages(
                    pdf,
                    local("实测峰到峰周期", "Measured peak-to-peak excursions"),
                    f"{len(waves)} "
                    + local(
                        "个周期；完整明细见 fatigue-cycles.csv",
                        "cycles · full list in fatigue-cycles.csv",
                    )
                    + "   /   "
                    + curve["y"]["unit"],
                    [
                        local("周次", "Cycle"),
                        local("幅值", "Amplitude"),
                        local("中值", "Midrange"),
                        "R",
                        local("峰值行", "Peak row"),
                        local("谷值行", "Valley row"),
                        local("下一峰行", "Next peak"),
                    ],
                    wave_rows,
                    [0.10, 0.15, 0.15, 0.10, 0.16, 0.16, 0.18],
                    name,
                    n,
                )
            signals = (
                curve.get("additional_signals", []) if r["plot_role"] == "main" else []
            )
            for begin in range(0, len(signals), 4):
                fig, axs = plt.subplots(
                    2, 2, figsize=(10, 7), layout="constrained", squeeze=False
                )
                fig.suptitle(
                    name + " · " + local("其他实测通道", "Additional measured channels")
                )
                for ax in axs.flat:
                    ax.set_visible(False)
                for ax, signal in zip(axs.flat, signals[begin : begin + 4]):
                    ax.set_visible(True)
                    series(ax, r, signal["axis"])
                    ax.set_title(
                        local("极值原始行", "Min / max rows")
                        + f"  {signal['minimum_row']} / {signal['maximum_row']}",
                        fontsize=9,
                    )
                pdf.savefig(fig)
                plt.close(fig)
                n += 1
            rows = [
                [
                    local(*METRICS[m["metric"]]),
                    f"{m['value']:.7g}",
                    m["unit"],
                    evidence(m["source_rows"]),
                ]
                for m in curve["metrics"]
            ]
            n = table_pages(
                pdf,
                name,
                subtitle,
                [
                    local("观测指标", "Metric"),
                    local("数值", "Value"),
                    local("单位", "Unit"),
                    local("原始行", "Source rows"),
                ],
                rows,
                [0.45, 0.17, 0.14, 0.24],
                name,
                n,
            )


def campaign_pages(path, records, errors, notes):
    with PdfPages(path) as pdf:
        counts = Counter(r["test_type"] for r in records)
        heading = local("多类型力学试验", "Mechanical tests by protocol")
        blocks = [
            (
                local("试验类型与采集数", "Protocols and acquisition counts"),
                "   /   ".join(f"{title(k)} × {v}" for k, v in counts.items()),
            )
        ]
        if notes.get("batch_note"):
            blocks.append((local("批次备注", "Campaign notes"), notes["batch_note"]))
        blocks.extend(
            (a["heading"], f"{a['text']}   [{a['record']}, {a['row']}]")
            for a in notes.get("batch_interpretation", [])
        )
        blocks.extend(
            (local("未解析记录", "Unparsed record"), e["record"] + " · " + e["reason"])
            for e in errors
        )
        n = text_pages(
            pdf,
            heading,
            local(
                "实测坐标、逐项指标与原始行",
                "Measured coordinates, quantities and original source rows",
            ),
            blocks,
            "MechCurve",
            1,
        )
        rows = []
        for r in records:
            c = curve_of(r)
            lead = next(iter(c["metrics"]), None)
            rows.append(
                [
                    r["sample"],
                    title(r["test_type"]),
                    r["sequence"],
                    local(*METRICS[lead["metric"]]) if lead else "—",
                    f"{lead['value']:.5g} {lead['unit']}" if lead else "—",
                    r["plot_role"],
                ]
            )
        table_pages(
            pdf,
            heading,
            local("逐段结果", "Acquisition results"),
            [
                local("样品", "Specimen"),
                local("试验", "Protocol"),
                local("段", "Seg."),
                local("指标", "Quantity"),
                local("数值", "Value"),
                local("用途", "Role"),
            ],
            rows,
            [0.17, 0.16, 0.06, 0.30, 0.19, 0.12],
            "MechCurve",
            n,
        )
