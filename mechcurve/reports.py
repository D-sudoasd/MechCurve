"""Specimen details and campaign reports."""

from io import BytesIO
import matplotlib
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pypdf import PdfReader, PdfWriter
from .locale import tr, diagnosis
from .mechanics import RESIDUAL_THRESHOLD_PP
from .figures import (
    ACCENT,
    EVENT,
    MODULUS_COLOR,
    MUTED,
    RECOVERY_LABEL,
    STATUS,
    cycle_color,
    fmt,
    fmt_residual,
    footer,
    page,
    plot_axis,
    table_pages,
    text_pages,
    trace_axes,
)


def sample_blocks(records, annotations):
    blocks = []
    formal = next((r for r in records if r["plot_role"] == "main"), None)
    if formal:
        fit = formal["sample_modulus"]
        blocks.append(
            (
                tr("首加载拉伸弹性模量"),
                tr(
                    "在首加载支 0.05%–0.15% 相对应变窗口内进行含截距线性拟合，模量为 {0} GPa。实测点数 {1}，R² = {2}。{3}。",
                    fmt(fit["modulus_GPa"], 2),
                    fit["n"],
                    fmt(fit["r2"], 5),
                    diagnosis(fit["reason"]),
                ),
            )
        )
    if len(records) > 1:
        blocks.append(
            (
                tr("续测与参考点"),
                tr(
                    "采集段按试验顺序排列，周次连续编号。应变差分别相对于本段起点计算，跨段累计值缺少共同零点。"
                ),
            )
        )
        for earlier, later in zip(records, records[1:]):
            if earlier["plot_role"] != "main" or later["plot_role"] != "main":
                continue
            last = next(
                (c for c in reversed(earlier["cycles"]) if c["status"] == "complete"),
                None,
            )
            first = next(
                (c for c in later["cycles"] if c["status"] == "complete"), None
            )
            if (
                not last
                or not first
                or last["target_axis"] != "strain_pct"
                or first["target_axis"] != "strain_pct"
            ):
                continue
            if (
                last["target_value"] != first["target_value"]
                or last["target_lower_MPa"] != first["target_lower_MPa"]
            ):
                continue
            blocks.append(
                (
                    tr("续测交界处的重复加载"),
                    tr(
                        "同一试样在第 {0} 和第 {1} 周均加载至段内目标应变 {2:g}%。两周实测峰值应力分别为 {3} 和 {4} MPa，卸载下限分别为 {5} 和 {6} MPa。各自加载换向至卸载端点的恢复量为 {7} 和 {8} 个百分点。",
                        last["cycle"],
                        first["cycle"],
                        first["target_value"],
                        fmt(last["max_stress_MPa"]),
                        fmt(first["max_stress_MPa"]),
                        fmt(last["end_stress_MPa"]),
                        fmt(first["end_stress_MPa"]),
                        fmt(last["recoverable_pp"]),
                        fmt(first["recoverable_pp"]),
                    ),
                )
            )
    for i, r in enumerate(records, 1):
        cs = [c for c in r["cycles"] if c["status"] == "complete"]
        high = r["peak_stress"]
        ev = r["event"]
        blocks.append(
            (tr("采集段 {0} · {1} 个采样点", i, len(r["points"])), r["record"])
        )
        if r["plot_role"] == "preliminary":
            blocks.append(
                (
                    tr("疑似初始试运行"),
                    diagnosis(r["plot_reason"])
                    + tr(" 本记录保留逐点和逐周指标，正式样品比较采用后续采集。"),
                )
            )
        if cs:
            a, b = cs[0], cs[-1]
            decision = r["recovery_summary"]
            blocks.append(
                (
                    tr("完全可恢复周次"),
                    tr(
                        "在本段实测卸载下限，段内残余应变 < {0:g}% 判为完全可恢复。满足判据 {1} / {2} 周。",
                        RESIDUAL_THRESHOLD_PP,
                        decision["fully_recoverable_cycles"],
                        decision["recovery_assessed_cycles"],
                    )
                    + (
                        tr(
                            "最高达标实测施加应变为 {0}%。",
                            fmt(decision["max_fully_recoverable_applied_pct"]),
                        )
                        if decision["max_fully_recoverable_applied_pct"] is not None
                        else ""
                    ),
                )
            )
            blocks.append(
                (
                    tr("循环响应"),
                    tr(
                        "实测完整周次 {0} 个。首末完整周的峰值应力分别为 {1} 和 {2} MPa。最后完整周总应变 {3}，可恢复 {4}，段内残余 {5} 个百分点，本周新增残余 {6} 个百分点。该周实测卸载下限 {7} MPa。",
                        len(cs),
                        fmt(a["max_stress_MPa"]),
                        fmt(b["max_stress_MPa"]),
                        fmt(b["total_strain_pp"]),
                        fmt(b["recoverable_pp"]),
                        fmt(b["residual_segment_pp"]),
                        fmt(b["residual_increment_pp"]),
                        fmt(b["end_stress_MPa"]),
                    ),
                )
            )
            distinct = [
                c
                for c in cs
                if c["strain_at_peak_pct"] is not None
                and c["max_strain_pct"] is not None
                and c["max_strain_pct"] - c["strain_at_peak_pct"] >= 0.01
            ]
            if distinct:
                c = distinct[-1]
                blocks.append(
                    (
                        tr("加载峰与最大应变"),
                        tr(
                            "第 {0} 周，力在 {1}% 应变处达到 {2} N（原始行 {3}），之后应变继续增至 {4}%（原始行 {5}）。",
                            c["cycle"],
                            fmt(c["strain_at_peak_pct"]),
                            fmt(c["peak_force_N"]),
                            c["peak_force_row"],
                            fmt(c["max_strain_pct"]),
                            c["max_strain_row"],
                        ),
                    )
                )
        if r["cycles"] and any(c["status"] != "complete" for c in r["cycles"]):
            blocks.append(
                (
                    tr("未完成段"),
                    tr(
                        "记录包含加载或卸载未完成的区间。表中保留已测极值，缺少完整卸载端点的恢复量与残余量显示为 —。"
                    ),
                )
            )
        if any(p["phase"] == "low_load_excursion" for p in r["points"]):
            blocks.append(
                (
                    tr("低载荷调整"),
                    tr(
                        "主循环卸载换向后存在小幅载荷调整，逐点表保留这一段并标注 low_load_excursion。"
                    ),
                )
            )
        if r["tensile"]:
            t = r["tensile"]
            fit = t["fit"]
            blocks.append(
                (
                    tr("单调拉伸"),
                    tr(
                        "抗拉强度 {0} MPa，初始模量 {1} GPa，Rp0.2 {2} MPa，断后伸长率 {3}%。{4}。",
                        fmt(t["uts_MPa"]),
                        fmt(t["modulus_GPa"]),
                        fmt(t["rp02_MPa"]),
                        fmt(t["elongation_after_break_pct"]),
                        diagnosis(t["fit_reason"]),
                    )
                    + (
                        tr(
                            " 拟合行 {0}–{1}，R² = {2:.5f}。",
                            fit["first_row"],
                            fit["last_row"],
                            fit["r2"],
                        )
                        if fit
                        else ""
                    ),
                )
            )
        detail = (
            tr(
                "实测最高应力 {0} MPa，位于原始第 {1} 行。",
                fmt(high["stress_MPa"]),
                high["source_row"],
            )
            if high
            else ""
        )
        if ev["before"]:
            b = ev["before"]
            detail += tr(
                "事件前原始第 {0} 行，力 {1} N，应力 {2} MPa，应变 {3}%。",
                ev["source_row"],
                fmt(b["force_N"]),
                fmt(b["stress_MPa"]),
                fmt(b["strain_pct"]),
            )
        blocks.append((tr("终止判读"), detail + diagnosis(ev["basis"]) + tr("。")))
        if (
            r["blocks"] != 1
            or (r["area_relative_error"] or 0) > 0.02
            or r["metadata"].get("metadata_warning")
        ):
            blocks.append(
                (
                    tr("数据检查"),
                    tr(
                        "连续有效块 {0} 个。截面校核相对误差 {1}。",
                        r["blocks"],
                        fmt(r["area_relative_error"], 5),
                    )
                    + diagnosis(r["metadata"].get("metadata_warning", "")),
                )
            )
    return blocks + [
        (
            tr("补充解释 · ") + a["heading"],
            a["text"] + tr("〔{0}，原始行 {1}〕", a["record"], a["row"]),
        )
        for a in annotations
    ]


def modulus_detail(record, name):
    fit = record["initial_loading_fit"]
    fig = page(name, tr("首加载拉伸模量   /   拟合取点复核"))
    ax = fig.add_axes([0.105, 0.205, 0.49, 0.515])
    row_ids = set(fit["source_rows"])
    points = [p for p in record["points"] if p["source_row"] in row_ids]
    if points:
        xs = np.array([p["strain_pct"] - fit["reference_strain_pct"] for p in points])
        ax.scatter(
            xs,
            [p["stress_MPa"] for p in points],
            s=30,
            color=ACCENT,
            label=tr("实测点"),
            zorder=3,
        )
        if fit["slope_MPa"] is not None:
            ends = np.array([min(xs), max(xs)])
            stress = (
                fit["slope_MPa"] * (ends + fit["reference_strain_pct"]) / 100
                + fit["intercept_MPa"]
            )
            ax.plot(ends, stress, color="#b85118", lw=1.5, label=tr("线性拟合"))
        ax.legend(frameon=False)
    ax.set_xlim(0.045, 0.155)
    plot_axis(ax, tr("相对首加载起点的应变 (%)"), tr("实测应力 (MPa)"))
    fig.text(0.66, 0.66, tr("拉伸弹性模量"), fontsize=13, color=MUTED)
    fig.text(
        0.66,
        0.58,
        fmt(fit["modulus_GPa"], 2) + " GPa",
        fontsize=23,
        weight="bold",
        color=MODULUS_COLOR,
    )
    for i, line in enumerate(
        [
            tr("拟合窗口  0.05%–0.15%"),
            tr("实测点数  {0}", fit["n"]),
            f"R²  {fmt(fit['r2'], 5)}",
            tr("原始行  {0}–{1}", fit["first_row"] or "—", fit["last_row"] or "—"),
            diagnosis(fit["reason"]),
        ]
    ):
        fig.text(0.66, 0.495 - i * 0.055, line, fontsize=11)
    fig.text(0.082, 0.10, record["record"], fontsize=9, color=MUTED, wrap=True)
    return fig


def sample_report(folder, name, records, annotations):
    folder.mkdir(parents=True, exist_ok=True)
    cycles = [c for r in records if r["plot_role"] == "main" for c in r["cycles"]]
    body = BytesIO()
    with PdfPages(body) as pdf:
        n = text_pages(
            pdf,
            name,
            tr("力学试验分析   /   样品结果"),
            sample_blocks(records, annotations),
            name,
            1,
        )
        first_formal = next((r for r in records if r["plot_role"] == "main"), None)
        if first_formal is not None:
            fit_fig = modulus_detail(first_formal, name)
            footer(fit_fig, name, n)
            pdf.savefig(fit_fig)
            plt.close(fit_fig)
            n += 1
        head_count = n - 1
        figure_pages = [
            folder / tr("段{0:02d}_{1}.{2}", seq, tr(kind), "pdf")
            for seq, record in enumerate(records, 1)
            if record["plot_role"] == "main"
            for kind in ("曲线", "终止判读")
        ]
        n += len(figure_pages)
        if cycles:
            rows = [
                [
                    c["cycle"],
                    tr(STATUS[c["status"]]),
                    fmt(c["peak_force_N"]),
                    fmt(c["stress_at_peak_MPa"]),
                    fmt(c["strain_at_peak_pct"]),
                    fmt(c["max_strain_pct"]),
                    fmt(c["end_stress_MPa"]),
                    c["peak_force_row"] or "—",
                    c["turn_row"] or "—",
                    c["end_row"] or "—",
                ]
                for c in cycles
            ]
            n = table_pages(
                pdf,
                tr("逐周峰值与取点"),
                tr("应力单位 MPa，力单位 N，应变单位 %。原始行号在相应采集段内有效。"),
                [
                    tr("周次"),
                    tr("状态"),
                    tr("峰值力"),
                    tr("对应应力"),
                    tr("对应应变"),
                    tr("最大应变"),
                    tr("下限应力"),
                    tr("力峰行"),
                    tr("换向行"),
                    tr("端点行"),
                ],
                rows,
                [0.06, 0.126, 0.116, 0.11, 0.10, 0.10, 0.104, 0.096, 0.096, 0.096],
                name,
                n,
            )
            table_pages(
                pdf,
                tr("应变分解"),
                tr("应变差单位为百分点，恢复率单位为 %。段内残余以本段参考点为基准。"),
                [
                    tr("周次"),
                    tr("阶段"),
                    tr("总应变"),
                    tr("加载增量"),
                    tr("可恢复"),
                    tr("段内残余"),
                    tr("新增残余"),
                    tr("恢复率"),
                    tr("恢复判定"),
                ],
                [
                    [
                        c["cycle"],
                        tr(STATUS[c["status"]]),
                        *[
                            fmt_residual(c[f])
                            if f == "residual_segment_pp"
                            else fmt(c[f])
                            for f in (
                                "total_strain_pp",
                                "loading_increment_pp",
                                "recoverable_pp",
                                "residual_segment_pp",
                                "residual_increment_pp",
                                "recovery_pct",
                            )
                        ],
                        tr(RECOVERY_LABEL[c["fully_recoverable"]]),
                    ]
                    for c in cycles
                ],
                [0.06, 0.14, 0.11, 0.11, 0.11, 0.12, 0.11, 0.10, 0.14],
                name,
                n,
            )

    reader = PdfReader(body)
    writer = PdfWriter()
    for pg in reader.pages[:head_count]:
        writer.add_page(pg)
    for path in figure_pages:
        writer.append(path, import_outline=False)
    for pg in reader.pages[head_count:]:
        writer.add_page(pg)
    writer.write(folder / tr("样品报告.pdf"))


def batch_report(
    folder,
    records,
    comparisons,
    stats,
    notes,
    errors,
    summaries,
    moduli,
    recovery_by_sample,
):
    complete = sum(c["status"] == "complete" for r in records for c in r["cycles"])
    partial = sum(c["status"] != "complete" for r in records for c in r["cycles"])
    formal = [r for r in records if r["plot_role"] == "main"]
    formal_cycles = sum(c["status"] == "complete" for r in formal for c in r["cycles"])
    blocks = [
        (
            tr("采集与覆盖"),
            tr(
                "{0} 条采集，{1:,} 点，{2} 个完整周次，{3} 个未完成段。主图覆盖 {4} 条记录、{5} 个样品报告单元和 {6} 个完整周次。",
                len(records),
                sum((len(r["points"]) for r in records)),
                complete,
                partial,
                len(formal),
                len({r["sample"] for r in formal}),
                formal_cycles,
            ),
        ),
        (
            tr("计算口径"),
            tr(
                "峰值力与加载换向分别定位。可恢复应变取加载换向应变减实际卸载端点应变。总应变和段内残余使用各采集段的起始参考值。"
            ),
        ),
        (
            tr("断裂判读"),
            tr(
                "已定位断裂前采样行 {0} 条，曲线候选 {1} 条。正式记录附载荷与应变时间图和终止区间放大图。",
                sum((r["event"]["status"] == "confirmed_row" for r in records)),
                sum((r["event"]["status"] == "candidate" for r in records)),
            ),
        ),
    ]
    if notes.get("batch_note"):
        blocks.append((tr("实验备注"), notes["batch_note"]))
    unusual = [
        r["sample"]
        for r in records
        if r["event"]["ends_under_load"] and r["event"]["status"] == "unlocated"
    ]
    if unusual:
        blocks.append(
            (
                tr("终止原因待核实"),
                tr("、").join(unusual)
                + tr(
                    " 在较高载荷的加载途中结束，优先核对原始实验日志。采样曲线未出现可据以定位拉断的载荷骤降。"
                ),
            )
        )
    if not stats:
        blocks.append(
            (
                tr("重复性"),
                tr(
                    "未提供可确认的独立重复样品组。比较表逐样品列示实测响应，统计表保留分组字段以便补充试验记录。"
                ),
            )
        )
    blocks += [
        (
            tr("补充解释 · ") + a["heading"],
            a["text"] + tr("〔{0}，原始行 {1}〕", a["record"], a["row"]),
        )
        for a in notes.get("batch_interpretation", [])
    ]
    blocks += [
        (tr("未解析记录"), f"{x['record']} · {diagnosis(x['reason'])}") for x in errors
    ]
    with PdfPages(folder / tr("批次报告.pdf")) as pdf:
        n = text_pages(
            pdf,
            tr("力学曲线分析"),
            tr("批次报告   /   循环加载与拉伸"),
            blocks,
            "MechCurve",
            1,
        )
        if moduli:
            n = table_pages(
                pdf,
                tr("首加载模量与完全可恢复周次"),
                tr(
                    "模量窗口为 0.05%–0.15%。完全可恢复按实测卸载端点的段内残余应变 < {0:g}% 判定。",
                    RESIDUAL_THRESHOLD_PP,
                ),
                [
                    tr("样品"),
                    "E (GPa)",
                    tr("实测窗口 (%)"),
                    tr("点数"),
                    "R²",
                    tr("原始行"),
                    tr("达标 / 可评价"),
                    tr("最高达标施加应变 (%)"),
                ],
                [
                    [
                        f["sample"],
                        fmt(f["modulus_GPa"], 2),
                        fmt(f["measured_min_pct"]) + "–" + fmt(f["measured_max_pct"]),
                        f["n"],
                        fmt(f["r2"], 5),
                        str(f["first_row"] or "—") + "–" + str(f["last_row"] or "—"),
                        f"{recovery_by_sample[f['sample']]['fully_recoverable_cycles']} / {recovery_by_sample[f['sample']]['recovery_assessed_cycles']}"
                        if recovery_by_sample[f["sample"]]["recovery_assessed_cycles"]
                        else "—",
                        fmt(
                            recovery_by_sample[f["sample"]][
                                "max_fully_recoverable_applied_pct"
                            ]
                        ),
                    ]
                    for f in moduli
                ],
                [0.235, 0.10, 0.15, 0.06, 0.10, 0.08, 0.115, 0.16],
                "MechCurve",
                n,
            )
        endpoints = [
            r
            for r in summaries
            if r["plot_role"] == "main" and r["last_complete_cycle"] is not None
        ]
        if endpoints:
            fields = [
                "peak_force_N",
                "stress_at_peak_MPa",
                "max_strain_pct",
                "total_strain_pp",
                "recoverable_pp",
                "residual_segment_pp",
                "end_stress_MPa",
            ]
            rows = [
                [
                    r["sample"],
                    r["segment"],
                    r["last_complete_cycle"],
                    *(fmt(r["last_" + key]) for key in fields),
                ]
                for r in endpoints
            ]
            n = table_pages(
                pdf,
                tr("各正式采集段的末个完整周"),
                tr(
                    "应力单位 MPa，力单位 N，最大加载应变单位 %。总应变、可恢复量及段内残余以百分点计。"
                ),
                [
                    tr("样品"),
                    tr("段"),
                    tr("周次"),
                    tr("峰值力"),
                    tr("对应应力"),
                    tr("最大应变"),
                    tr("总应变"),
                    tr("可恢复"),
                    tr("段内残余"),
                    tr("卸载下限"),
                ],
                rows,
                [0.21, 0.045, 0.055, 0.105, 0.10, 0.10, 0.095, 0.095, 0.095, 0.10],
                "MechCurve",
                n,
            )
        rows = [
            [
                r["sample"],
                tr("疑似试运行") if r["plot_role"] == "preliminary" else tr("正式"),
                r["sequence"],
                len(r["points"]),
                sum(c["status"] == "complete" for c in r["cycles"]),
                fmt(r["peak_stress"]["stress_MPa"] if r["peak_stress"] else None),
                tr(EVENT[r["event"]["status"]]),
            ]
            for r in records
        ]
        n = table_pages(
            pdf,
            tr("记录总览"),
            tr("同一物理样品续测分段显示；S 编号来自仪器采集记录。"),
            [
                tr("样品 / 记录"),
                tr("用途"),
                tr("段"),
                tr("点数"),
                tr("完整周"),
                tr("最高应力 (MPa)"),
                tr("断裂行定位"),
            ],
            rows,
            [0.26, 0.135, 0.06, 0.105, 0.10, 0.17, 0.17],
            "MechCurve",
            n,
        )
        views = [
            r
            for r in formal
            if any(
                p["strain_pct"] is not None and p["stress_MPa"] is not None
                for p in r["points"]
            )
        ]
        if len(views) >= 2:
            bounds = {}
            for key in ("strain_pct", "stress_MPa"):
                finite = [
                    p[key] for r in views for p in r["points"] if p[key] is not None
                ]
                low, high = min(min(finite), 0), max(finite)
                pad = 0.04 * max(high - low, 1e-6)
                bounds[key] = (low - pad, high + pad)
            count = max(
                (
                    c["cycle"]
                    for r in views
                    for c in r["cycles"]
                    if c["status"] == "complete"
                ),
                default=1,
            )
            for pos in range(0, len(views), 6):
                fig = page(
                    tr("正式采集的应力–应变回线"),
                    tr(
                        "各面板使用相同坐标范围。颜色表示周次，实线为加载，虚线为卸载，灰色表示未完成段或低载荷调整。"
                    ),
                )
                for j, r in enumerate(views[pos : pos + 6]):
                    row, col = divmod(j, 3)
                    ax = fig.add_axes(
                        [0.089 + 0.304 * col, 0.525 - 0.336 * row, 0.235, 0.222]
                    )
                    trace_axes(ax, r, count, False)
                    ax.set_xlim(bounds["strain_pct"])
                    ax.set_ylim(bounds["stress_MPa"])
                    ax.set_title(
                        r["sample"] + tr("   /   段 {0}", r["sequence"]),
                        loc="left",
                        fontsize=10,
                        weight="bold",
                    )
                    ax.set_xlabel(tr("应变 (%)"), fontsize=9)
                    ax.set_ylabel(tr("应力 (MPa)") if col == 0 else "", fontsize=9)
                    ax.tick_params(labelsize=8)
                    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=5))
                cmap = matplotlib.colors.ListedColormap(
                    [cycle_color(k, count) for k in range(1, count + 1)]
                )
                bar = fig.colorbar(
                    plt.cm.ScalarMappable(
                        norm=plt.Normalize(0.5, count + 0.5), cmap=cmap
                    ),
                    cax=fig.add_axes([0.3, 0.082, 0.46, 0.011]),
                    orientation="horizontal",
                )
                bar.set_ticks(list(range(1, count + 1, max(1, math.ceil(count / 15)))))
                bar.ax.tick_params(labelsize=7, length=2, pad=1)
                bar.outline.set_visible(False)
                fig.text(0.245, 0.081, tr("周次"), fontsize=8)
                for ext in ("pdf", "svg", "png"):
                    fig.savefig(
                        folder / tr("正式回线总览_{0:02d}.{1}", pos // 6 + 1, ext),
                        dpi=300,
                    )
                footer(fig, "MechCurve", n)
                pdf.savefig(fig)
                plt.close(fig)
                n += 1
        by_target = {}
        for c in comparisons:
            by_target.setdefault((c["target_axis"], c["target_value"]), set()).add(
                c["sample"]
            )
        common = [
            c
            for c in comparisons
            if len(by_target[c["target_axis"], c["target_value"]]) >= 2
        ]
        if common:
            unit = {"strain_pct": "%", "stress_MPa": " MPa", "force_N": " N"}
            for axis in sorted({c["target_axis"] for c in common}):
                subset = [c for c in common if c["target_axis"] == axis]
                fig = page(
                    tr("同一加载目标下的样品比较"),
                    tr(
                        "按方法目标选择完整周次。每个点对应一次实际观测，纵轴为峰值应力或端点应变差。"
                    ),
                )
                left = fig.add_axes([0.09, 0.25, 0.36, 0.48])
                right = fig.add_axes([0.565, 0.25, 0.36, 0.48])
                names = sorted({c["sample"] for c in subset})
                for i, name in enumerate(names):
                    vals = [c for c in subset if c["sample"] == name]
                    col = plt.get_cmap("tab10")(i % 10)
                    x = [c["target_value"] for c in vals]
                    left.scatter(
                        x,
                        [
                            np.nan
                            if c["max_stress_MPa"] is None
                            else c["max_stress_MPa"]
                            for c in vals
                        ],
                        color=col,
                        s=28,
                        label=name,
                    )
                    right.scatter(
                        x,
                        [
                            np.nan
                            if c["recoverable_pp"] is None
                            else c["recoverable_pp"]
                            for c in vals
                        ],
                        color=col,
                        s=28,
                    )
                xlabel = {
                    "strain_pct": tr("目标应变 (%)"),
                    "stress_MPa": tr("目标应力 (MPa)"),
                    "force_N": tr("目标力 (N)"),
                }[axis]
                plot_axis(left, xlabel, tr("峰值应力 (MPa)"))
                plot_axis(right, xlabel, tr("可恢复应变 (百分点)"))
                fig.legend(
                    *left.get_legend_handles_labels(),
                    loc="lower center",
                    bbox_to_anchor=(0.5, 0.065),
                    ncol=3,
                    frameon=False,
                    fontsize=8,
                )
                greatest = max(c["target_value"] for c in subset)
                hits = [
                    c
                    for c in subset
                    if c["target_value"] == greatest and c["max_stress_MPa"] is not None
                ]
                if hits:
                    fig.text(
                        0.09,
                        0.785,
                        tr(
                            "在共同目标 {0:g}{1} 下，实测峰值应力范围为 {2:.1f}–{3:.1f} MPa。实测卸载下限见逐项比较表。",
                            greatest,
                            unit[axis],
                            min((c["max_stress_MPa"] for c in hits)),
                            max((c["max_stress_MPa"] for c in hits)),
                        ),
                        fontsize=10,
                    )
                footer(fig, "MechCurve", n)
                pdf.savefig(fig)
                plt.close(fig)
                n += 1
            rows = [
                [
                    c["sample"],
                    c["cycle"],
                    fmt(c["target_value"], 2) + unit[c["target_axis"]],
                    fmt(c["max_stress_MPa"]),
                    fmt(c["end_stress_MPa"]),
                    fmt(c["recoverable_pp"]),
                    fmt(c["residual_segment_pp"]),
                ]
                for c in common
            ]
            n = table_pages(
                pdf,
                tr("共同加载目标下的实测响应"),
                tr(
                    "目标按试验方法匹配。目标单位见样品方法，卸载下限逐项显示。应变差以百分点计。"
                ),
                [
                    tr("样品"),
                    tr("周次"),
                    tr("目标"),
                    tr("峰值 MPa"),
                    tr("下限 MPa"),
                    tr("可恢复"),
                    tr("段内残余"),
                ],
                rows,
                [0.28, 0.08, 0.1, 0.14, 0.14, 0.13, 0.13],
                "MechCurve",
                n,
            )
        if stats:
            n = table_pages(
                pdf,
                tr("独立样品重复性"),
                tr("按独立样品、共同目标及卸载程序分组，标准差采用 n−1。"),
                [
                    tr("组别"),
                    tr("目标"),
                    tr("出现次序"),
                    tr("指标"),
                    "n",
                    tr("均值"),
                    tr("标准差"),
                ],
                [
                    [
                        s["group"],
                        str(s["target_value"]),
                        s["occurrence"],
                        s["metric"],
                        s["n"],
                        fmt(s["mean"]),
                        fmt(s["sd"]),
                    ]
                    for s in stats
                ],
                [0.16, 0.12, 0.12, 0.25, 0.08, 0.14, 0.13],
                "MechCurve",
                n,
            )
