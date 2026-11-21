"""Portable, offline navigation for a verified delivery."""

from html import escape
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote
from .locale import language, tr, diagnosis
from .mechanics import RESIDUAL_THRESHOLD_PP


STYLE = """
*{box-sizing:border-box} body{margin:0;color:#172d39;background:#f5f7f7;font:16px/1.6 "Source Sans 3","Microsoft YaHei",sans-serif}
main{max-width:1080px;margin:0 auto;padding:32px clamp(16px,4vw,48px) 56px;background:white} h1,h2{line-height:1.25} h1{font-size:32px} h2{font-size:21px;margin:32px 0 12px}
a{color:#07576b;text-underline-offset:3px} a:focus-visible{outline:2px solid #155d8a;outline-offset:2px}
nav{display:flex;gap:12px 24px;flex-wrap:wrap;border-block:1px solid #cad7d8;padding:14px 0} img{width:100%;height:auto}
.scroll{overflow-x:auto} table{border-collapse:collapse;width:100%;font-size:14px} th,td{padding:9px 10px;text-align:left;border-bottom:1px solid #dde4e6}
th{background:#edf4f4} td a{display:inline-block;margin-right:10px} small{color:#465b64}
strong{color:#922b37}"""


def link(path, label):
    return f'<a href="{quote(Path(path).as_posix(), safe="/")}">{escape(label)}</a>'


def write_index(stage, batch, summaries, reports, errors, recovery_by_sample):
    main = [r for r in summaries if r["plot_role"] == "main"]
    trials = [r for r in summaries if r["plot_role"] == "preliminary"]

    def label(zh, en):
        return en if language() == "en" else zh

    def header(zh, en):
        return "<h2>" + label(zh, en) + "</h2>"

    def table(columns):
        return (
            '<div class="scroll"><table><thead><tr>'
            + "".join("<th>" + label(*col) + "</th>" for col in columns)
            + "</tr></thead><tbody>"
        )

    title = escape(batch) + " · " + label("力学试验报告", "Mechanical test reports")
    parts = [
        f'<!doctype html><html lang="{language()}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{title}</title><style>{STYLE}</style></head><body><main><h1>{title}</h1>"
    ]
    count = sum(r["complete_cycles"] for r in main)
    parts.append(
        "<p>"
        + label(
            f"正式采集 {len(main)} 段，完整周次 {count} 个。疑似试运行 {len(trials)} 段。",
            f"{len(main)} formal acquisitions · {count} complete cycles · {len(trials)} preliminary acquisitions.",
        )
        + "</p>"
    )
    nav = [
        ("每个样品一页.pdf", "每个样品一页", "Specimen sheets"),
        ("样品弹性模量.csv", "弹性模量", "First-loading modulus"),
        ("批次报告.pdf", "批次 PDF", "Campaign report"),
        ("逐周指标.csv", "逐周指标", "Cycle metrics"),
        ("样品汇总.csv", "样品汇总", "Specimen summary"),
        ("逐点分段.csv", "逐点数据", "Source points"),
        ("共同目标比较.csv", "共同加载目标", "Matched targets"),
        ("results.json", "Agent 结果", "Agent results"),
    ]
    parts.append(
        "<nav>"
        + "".join(
            link(tr(p), label(zh, en))
            for p, zh, en in nav
            if (stage / tr(p)).is_file() or p == "results.json"
        )
        + "</nav>"
    )
    overview = sorted(stage.glob(label("正式回线总览_*.png", "formal-histories-*.png")))
    if overview:
        parts.append(header("正式试验回线", "Formal loading histories"))
        for image in overview:
            alt = label("各采集段的力学响应", "Measured response for each acquisition")
            parts.append(
                f'<a href="{quote(image.with_suffix(".pdf").name)}"><img src="{quote(image.name)}" alt="{alt}"></a>'
            )
    profile_rows = [r for r in main if r.get("profile_view")]
    if profile_rows:
        from .protocol_reports import title as protocol_title, record_asset_paths

        if (stage / "fatigue-cycles.csv").is_file():
            parts.append(
                link(
                    "fatigue-cycles.csv",
                    label("疲劳逐周幅值与取点", "Fatigue cycles and extrema (CSV)"),
                )
            )
        parts.append(header("各类试验结果", "Protocol results"))
        parts.append(
            link(
                "protocol-metrics.csv",
                label("指标、单位及原始行 CSV", "Metrics, units and source rows (CSV)"),
            )
        )
        parts.append(
            table(
                [
                    ("样品单页", "Specimen sheet"),
                    ("试验类型", "Protocol"),
                    ("详报", "Details"),
                    ("实测曲线", "Measured curve"),
                ]
            )
        )
        for r in profile_rows:
            folder = Path(reports[r["sample"]]).parent
            plotlinks = " ".join(
                link(folder / f, Path(f).suffix[1:].upper())
                for f in record_asset_paths(r["segment"])
            )
            vals = [
                link(folder / tr("样品单页.pdf"), r["sample"]),
                escape(protocol_title(r["test_type"])),
                link(reports[r["sample"]], r["record"]),
                plotlinks,
            ]
            parts.append("<tr>" + "".join("<td>" + v + "</td>" for v in vals) + "</tr>")
        parts.append("</tbody></table></div>")
        main = [r for r in main if not r.get("profile_view")]
    if main:
        parts.append(header("样品单页", "Specimen sheets"))
        parts.append(
            "<p>"
            + label(
                f"按实测卸载端点判定，段内残余应变 &lt; {RESIDUAL_THRESHOLD_PP:g}% 的完整周次计为完全可恢复。",
                f"A complete cycle qualifies when its segment-referenced residual strain is below {RESIDUAL_THRESHOLD_PP:g} percentage points at the measured unload endpoint.",
            )
            + "</p>"
        )
        parts.append(
            table(
                [
                    ("样品", "Specimen"),
                    ("首加载模量 (GPa)", "First-loading E (GPa)"),
                    ("完全可恢复 / 可评价", "Qualified / assessed"),
                    ("最高达标施加应变 (%)", "Max qualifying applied strain (%)"),
                    ("续测合并", "Resumed data"),
                ]
            )
        )
        for name in dict.fromkeys(r["sample"] for r in main):
            folder = Path(reports[name]).parent
            fit = next(r["modulus_GPa"] for r in main if r["sample"] == name)
            recovery = recovery_by_sample[name]
            maximum = recovery["max_fully_recoverable_applied_pct"]
            count = recovery["recovery_assessed_cycles"]
            vals = [
                link(folder / tr("样品单页.pdf"), name),
                f"<strong>{fit:.2f}</strong>" if fit is not None else "—",
                f"{recovery['fully_recoverable_cycles']} / {count}" if count else "—",
                f"<strong>{maximum:.3f}</strong>" if maximum is not None else "—",
                "".join(
                    link(folder / f, label(zh, en))
                    for f, zh, en in [
                        (tr("合并回线.") + "pdf", "曲线", "History"),
                        (tr("合并逐点.csv"), "逐点 CSV", "Points CSV"),
                        (tr("合并逐周.csv"), "逐周 CSV", "Cycles CSV"),
                    ]
                    if (stage / folder / f).is_file()
                ),
            ]
            parts.append("<tr>" + "".join("<td>" + v + "</td>" for v in vals) + "</tr>")
        parts.append(
            "</tbody></table></div>"
            + header("分段取点与详细报告", "Detailed reports and source figures")
        )
        parts.append(
            table(
                [
                    ("样品", "Specimen"),
                    ("段", "Segment"),
                    ("完整周次", "Complete cycles"),
                    ("论文单图", "Paper figure"),
                    ("时间历程", "Time history"),
                ]
            )
        )
        for r in main:
            pdf = Path(reports[r["sample"]])
            seq = r["segment"]
            paper = "".join(
                link(pdf.parent / tr("段{0:02d}_论文单图.{1}", seq, ext), ext.upper())
                for ext in ("pdf", "svg", "png")
            )
            diagnostic = link(
                pdf.parent / tr("段{0:02d}_{1}.{2}", seq, tr("终止判读"), "pdf"),
                label("判读图", "Diagnostics"),
            )
            parts.append(
                f"<tr><td>{link(pdf, r['sample'])}</td><td>{seq}</td><td>{r['complete_cycles']}</td><td>{paper}</td><td>{diagnostic}</td></tr>"
            )
        parts.append("</tbody></table></div>")
    if trials:
        parts.append(header("疑似试运行", "Preliminary acquisitions") + "<ul>")
        for r in trials:
            parts.append(
                f"<li>{link(reports[r['sample']], r['sample'])} · {escape(diagnosis(r['plot_reason']))}</li>"
            )
        parts.append("</ul>")
    if errors:
        parts.append(
            header("未解析的记录", "Unparsed records")
            + "<ul>"
            + "".join(
                f"<li>{escape(e['record'])} · {escape(diagnosis(e['reason']))}</li>"
                for e in errors
            )
            + "</ul>"
        )
    parts.append("</main></body></html>")
    (stage / tr("报告索引.html")).write_text("\n".join(parts), encoding="utf-8")


def publish_index(run, checked):
    """Atomically point the stable entry to the delivery that just passed readback."""
    lang = checked.get("language", "zh")
    name = tr("打开分析结果.html", lang=lang)
    entry = run.parent / name
    marker = "<!-- MechCurve delivery index -->"
    target = quote(run.name + "/" + tr("报告索引.html", lang=lang))
    title = "Open current results" if lang == "en" else "打开当前力学分析结果"
    html = f'<!doctype html>{marker}<html lang="{lang}"><meta charset="utf-8"><title>{title}</title><meta http-equiv="refresh" content="0; url={target}"><p><a href="{target}">{title}</a></p></html>'
    current = (
        entry.read_text(encoding="utf-8-sig", errors="replace")
        if entry.exists()
        else None
    )
    if current is not None and marker not in current:
        return checked
    if html != current:
        with NamedTemporaryFile(
            "w", dir=run.parent, encoding="utf-8", delete=False
        ) as handle:
            handle.write(html)
            temporary = Path(handle.name)
        try:
            os.replace(temporary, entry)
        finally:
            temporary.unlink(missing_ok=True)
    return {**checked, "entry": str(entry.resolve())}
