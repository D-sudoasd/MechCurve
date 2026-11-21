"""English report catalog keyed by the established Chinese display text."""

EN = {
    "     ·     {0}达到最大值": "    ·    maximum at {0}",
    "   /   段 {0}": "   /   segment {0}",
    "   /   采集段 {0}": "   /   segment {0}",
    "   ·   {0} 个完整周次": "   ·   {0} complete cycles",
    " · 合并回线": " · resumed history",
    " 周": "",
    " 在较高载荷的加载途中结束，优先核对原始实验日志。采样曲线未出现可据以定位拉断的载荷骤降。": " ended under load. Check the experiment log; the sampled load "
    "history has no uniquely attributable break row.",
    " 拟合行 {0}–{1}，R² = {2:.5f}。": " Fit rows {0}–{1}, R² = {2:.5f}.",
    " 本记录保留逐点和逐周指标，正式样品比较采用后续采集。": " Point and cycle data are retained. Specimen comparisons use the subsequent "
    "formal acquisition.",
    "* 为未完成段。": "* Incomplete cycle. ",
    "0.2% 偏移线": "0.2% offset",
    "{0}   ·   {1} 段正式采集": "{0}   ·   Segments: {1}",
    "{0} 个周次": "{0} cycles",
    "{0} 条采集，{1:,} 点，{2} 个完整周次，{3} 个未完成段。主图覆盖 {4} 条记录、{5} 个样品报告单元和 {6} 个完整周次。": "{0} acquisitions; {1:,} points; {2} "
    "complete cycles; {3} partial "
    "segments. Formal plots cover {4} "
    "records, {5} specimens and {6} "
    "complete cycles.",
    "{0} 段加载程序，详见逐周表。": "{0} loading segments; see the cycle table.",
    "、": ", ",
    "。": ". ",
    "。各段应变沿用本段起点。": ". Each segment retains its own reference.",
    "〔{0}，原始行 {1}〕": " [{0}, row {1}]",
    "下限 MPa": "Floor (MPa)",
    "下限应力": "Floor stress",
    "主循环卸载换向后存在小幅载荷调整，逐点表保留这一段并标注 low_load_excursion。": "A small excursion follows the main unloading reversal. Its "
    "samples carry the low_load_excursion label in the point "
    "table.",
    "事件前原始第 {0} 行，力 {1} N，应力 {2} MPa，应变 {3}%。": "Pre-event row {0}: force {1} N, stress {2} MPa, strain {3}%. ",
    "位移 (mm)": "Extension (mm)",
    "低载荷调整": "Low-load adjustment",
    "保留断裂事件判读图": "Fracture evidence retained",
    "全记录": "Full acquisition",
    "共同加载目标下的实测响应": "Matched-target measurements",
    "共同目标比较.csv": "target-comparisons.csv",
    "出现次序": "Occurrence",
    "初测实心   ·   续测空心": "First: filled   ·   resumed: open",
    "力 (N)": "Force (N)",
    "力学曲线分析": "Mechanical response",
    "力学试验分析   /   样品结果": "Mechanical testing   /   specimen results",
    "力峰行": "Peak row",
    "力目标": "force target",
    "加载": "Loading",
    "加载–卸载回线": "Loading and unloading",
    "加载增量": "Load increment",
    "加载峰与最大应变": "Force peak and maximum strain",
    "加载换向": "Reversal",
    "加载未完成": "Partial load",
    "单调拉伸": "Monotonic tension",
    "卸载": "Unloading",
    "卸载下限": "Unload floor",
    "卸载下限\n(MPa)": "Unload floor\n(MPa)",
    "卸载下限 (MPa)": "Unload floor (MPa)",
    "卸载下限 (N)": "Unload floor (N)",
    "卸载未完成": "Partial unload",
    "卸载端点": "Unload end",
    "原始行": "Source rows",
    "原始行  {0}–{1}": "Source rows  {0}–{1}",
    "可恢复": "Recovered",
    "可恢复\n(百分点)": "Recovered\n(pp)",
    "可恢复与残余应变随施加应变的变化": "Recovered and residual strain",
    "可恢复应变": "Recovered strain",
    "可恢复应变 (百分点)": "Recovered strain (pp)",
    "各正式采集段的末个完整周": "Last complete cycle per acquisition",
    "各段沿用导出应变零点，按实际加载顺序连续编号。": "Strain references follow their acquisition segments. Cycles follow loading order.",
    "各面板使用相同坐标范围。颜色表示周次，实线为加载，虚线为卸载，灰色表示未完成段或低载荷调整。": "Common scales across panels. Color indicates cycle; solid "
    "curves show loading and dashed curves show unloading. Gray "
    "traces mark incomplete or low-load excursions.",
    "合并回线.": "resumed-history.",
    "合并逐周.csv": "merged-cycles.csv",
    "合并逐点.csv": "merged-points.csv",
    "同一加载目标下的样品比较": "Responses at shared targets",
    "同一物理样品续测分段显示；S 编号来自仪器采集记录。": "Resumed specimens appear by acquisition segment. Specimen indices come from the "
    "instrument export.",
    "同一试样在第 {0} 和第 {1} 周均加载至段内目标应变 {2:g}%。两周实测峰值应力分别为 {3} 和 {4} MPa，卸载下限分别为 {5} 和 {6} MPa。各自加载换向至卸载端点的恢复量为 {7} 和 {8} 个百分点。": "Cycles "
    "{0} "
    "and "
    "{1} "
    "on "
    "the "
    "same "
    "specimen "
    "share "
    "a "
    "{2:g}% "
    "segment "
    "target. "
    "Peak "
    "stresses: "
    "{3} "
    "and "
    "{4} "
    "MPa. "
    "Unload "
    "floors: "
    "{5} "
    "and "
    "{6} "
    "MPa. "
    "Recovered "
    "strains: "
    "{7} "
    "and "
    "{8} "
    "pp.",
    "同试验包 S{0} 随后完成多周加载；本条仅 {1} 点、{2} 个完整周，终止于加载途中。疑似初始试运行。": "Later acquisition S{0} completed multiple cycles. "
    "This record has {1} points and {2} complete cycles "
    "and stops under load. Possible preliminary run.",
    "周次": "Cycle",
    "在共同目标 {0:g}{1} 下，实测峰值应力范围为 {2:.1f}–{3:.1f} MPa。实测卸载下限见逐项比较表。": "At the shared target of {0:g}{1}, peak stresses "
    "range from {2:.1f} to {3:.1f} MPa. See "
    "individual unload floors below.",
    "在本段实测卸载下限，段内残余应变 < {0:g}% 判为完全可恢复。满足判据 {1} / {2} 周。": "At the observed unload floor, a residual below {0:g}% "
    "qualifies. {1} of {2} assessed cycles passed. ",
    "在首加载支 0.05%–0.15% 相对应变窗口内进行含截距线性拟合，模量为 {0} GPa。实测点数 {1}，R² = {2}。{3}。": "Fit with a free intercept over "
    "0.05%–0.15% relative strain: {0} GPa "
    "from {1} points (R² = {2}). {3}.",
    "均值": "Mean",
    "完全可恢复": "Fully recoverable",
    "完全可恢复  {0} / {1} 周": "Fully recoverable  {0} / {1}",
    "完全可恢复周次": "Fully recoverable cycles",
    "完整": "Complete",
    "完整周": "Full cycles",
    "实测加载": "measured load",
    "实测卸载端点段内残余 < {0:g}% 判为完全可恢复。页首最大值取达标周的最高实测施加应变。": "Full recovery: unload residual < {0:g}%. Header maximum = "
    "highest measured applied strain among passing cycles.",
    "实测完整周次 {0} 个。首末完整周的峰值应力分别为 {1} 和 {2} MPa。最后完整周总应变 {3}，可恢复 {4}，段内残余 {5} 个百分点，本周新增残余 {6} 个百分点。该周实测卸载下限 {7} MPa。": "{0} "
    "complete "
    "cycles. "
    "Peak "
    "stress "
    "changed "
    "from "
    "{1} "
    "to "
    "{2} "
    "MPa. "
    "The "
    "final "
    "complete "
    "cycle "
    "reached "
    "{3} "
    "pp "
    "total "
    "strain, "
    "with "
    "{4} "
    "pp "
    "recovered, "
    "{5} "
    "pp "
    "segment "
    "residual "
    "and "
    "{6} "
    "pp "
    "additional "
    "residual. "
    "Unload "
    "floor: "
    "{7} "
    "MPa.",
    "实测应力 (MPa)": "Measured stress (MPa)",
    "实测最高应力 {0} MPa，位于原始第 {1} 行。": "Highest observed stress: {0} MPa at row {1}. ",
    "实测点": "Measured points",
    "实测点数  {0}": "Measured points  {0}",
    "实测窗口 (%)": "Fit range (%)",
    "实验备注": "Experiment notes",
    "实验备注指定断裂前最后有效行": "The experiment note identifies the final pre-break row",
    "实验备注指定用途": "Role specified in experiment notes",
    "对应应力": "Stress at peak",
    "对应应变": "Strain at peak",
    "峰值 MPa": "Peak (MPa)",
    "峰值力": "Peak force",
    "峰值力\n(N)": "Peak force\n(N)",
    "峰值力 (N)": "Peak force (N)",
    "峰值力与加载换向分别定位。可恢复应变取加载换向应变减实际卸载端点应变。总应变和段内残余使用各采集段的起始参考值。": "Peak force and reversal are located independently. "
    "Recovered strain runs from reversal to the observed "
    "unloading endpoint. Total and residual strain use "
    "the acquisition's starting reference.",
    "峰值力处应力\n(MPa)": "Peak-force σ\n(MPa)",
    "峰值应力 (MPa)": "Peak stress (MPa)",
    "已定位断裂前采样行 {0} 条，曲线候选 {1} 条。正式记录附载荷与应变时间图和终止区间放大图。": "Confirmed break rows: {0}. Signal candidates: {1}. Formal "
    "records include time histories and an endpoint close-up.",
    "应力 (MPa)": "Stress (MPa)",
    "应力单位 MPa，力单位 N，应变单位 %。原始行号在相应采集段内有效。": "Stress in MPa, force in N and strain in %. Source rows refer to the "
    "corresponding acquisition.",
    "应力单位 MPa，力单位 N，最大加载应变单位 %。总应变、可恢复量及段内残余以百分点计。": "Stress in MPa, force in N and maximum strain in %. Total, "
    "recovered and residual strain in pp.",
    "应力目标": "stress target",
    "应变 (%)": "Strain (%)",
    "应变 (百分点)": "Strain (pp)",
    "应变分解": "Strain decomposition",
    "应变回退并离开拟合窗口": "Strain reversed out of the fit window",
    "应变差 (百分点)": "Strain change (pp)",
    "应变差单位为百分点，恢复率单位为 %。段内残余以本段参考点为基准。": "Strain changes in percentage points (pp); recovery ratio in %. Residual "
    "strain uses the segment reference.",
    "应变目标": "strain target",
    "循环响应": "Cyclic response",
    "循环拉伸": "Cyclic tension",
    "总应变": "Total",
    "总应变\n(百分点)": "Total\n(pp)",
    "恢复判定": "Assessment",
    "恢复率": "Recovery (%)",
    "打开分析结果.html": "open-results.html",
    "批次报告   /   循环加载与拉伸": "Campaign report   /   cyclic and tensile tests",
    "批次报告.pdf": "campaign-report.pdf",
    "抗拉强度 (MPa)": "UTS (MPa)",
    "抗拉强度 {0} MPa，初始模量 {1} GPa，Rp0.2 {2} MPa，断后伸长率 {3}%。{4}。": "UTS {0} MPa; modulus {1} GPa; Rp0.2 {2} MPa; "
    "elongation after break {3}%. {4}.",
    "报告索引.html": "report-index.html",
    "拉伸应力 (MPa)": "Tensile stress (MPa)",
    "拉伸应变 (%)": "Tensile strain (%)",
    "拉伸弹性模量": "Tensile modulus",
    "拉伸性能": "Tensile properties",
    "拉伸曲线": "Tensile curve",
    "拟合窗口  0.05%–0.15%": "Fit window  0.05%–0.15%",
    "拟合窗口跨越时钟复位": "Clock reset inside the fit window",
    "指标": "Metric",
    "按方法目标选择完整周次。每个点对应一次实际观测，纵轴为峰值应力或端点应变差。": "Complete cycles are matched by programmed target. Each marker is one "
    "observation.",
    "按独立样品、共同目标及卸载程序分组，标准差采用 n−1。": "Group by independent specimen, common target and unloading program. Sample SD "
    "uses n−1.",
    "换向行": "Turn row",
    "数据检查": "Data checks",
    "断后伸长率 (%)": "Elongation at break (%)",
    "断裂候选段": "Break candidate",
    "断裂判读": "Fracture evidence",
    "断裂终止": "Fracture",
    "断裂行定位": "Break evidence",
    "新增残余": "Residual gain",
    "施加应变 (%)": "Applied strain (%)",
    "无达标周": "No passing cycle",
    "时间 (s)": "Time (s)",
    "曲线": "response",
    "曲线候选": "Candidate",
    "最大力 (N)": "Max force (N)",
    "最大加载应变 (%)": "Maximum applied strain (%)",
    "最大完全可恢复应变": "Max fully recoverable strain",
    "最大应变": "Max strain",
    "最大应变\n(%)": "Max strain\n(%)",
    "最高应力 (MPa)": "Max stress (MPa)",
    "最高达标实测施加应变为 {0}%。": "Highest passing applied strain: {0}%.",
    "最高达标施加应变 (%)": "Max passing strain (%)",
    "有独立断裂记录": "independent break evidence supplied",
    "有试样级断裂记录，采样点尚未定位": "Break confirmed for the specimen; exact row unresolved",
    "未完成段": "Incomplete segment",
    "未提供可确认的独立重复样品组。比较表逐样品列示实测响应，统计表保留分组字段以便补充试验记录。": "No independent replicate groups were supplied. Individual "
    "responses remain available in the comparison table.",
    "未检出可唯一归属的断裂采样点": "No uniquely attributable break row",
    "未测得": "Unavailable",
    "未解析记录": "Records requiring attention",
    "未达标": "At/above limit",
    "标准差": "SD",
    "样品": "Specimen",
    "样品 / 记录": "Specimen / record",
    "样品单页.pdf": "specimen-sheet.pdf",
    "样品弹性模量.csv": "specimen-moduli.csv",
    "样品报告.pdf": "specimen-report.pdf",
    "样品汇总.csv": "specimen-summary.csv",
    "模量拟合    0.05%–0.15%    ·    {0} 个点    ·    R² = {1}": "Modulus fit    0.05%–0.15%    ·    {0} points    ·    R² "
    "= {1}",
    "模量拟合窗口": "Modulus fit window",
    "模量窗口为 0.05%–0.15%。完全可恢复按实测卸载端点的段内残余应变 < {0:g}% 判定。": "Modulus window: 0.05%–0.15%. Full recovery requires a "
    "segment residual below {0:g}% at the measured unload "
    "floor.",
    "正式": "Formal",
    "正式回线总览_{0:02d}.{1}": "formal-histories-{0:02d}.{1}",
    "正式记录": "Formal record",
    "正式采集的应力–应变回线": "Stress–strain histories",
    "残余 (百分点)": "Residual (pp)",
    "残余判定线 {0:g}%": "Residual limit {0:g}%",
    "残余局部放大": "Residual detail",
    "段": "Segment",
    "段 / 周": "Seg. / cycle",
    "段{0:02d}_{1}.{2}": "segment-{0:02d}-{1}.{2}",
    "段{0:02d}_论文单图.{1}": "segment-{0:02d}-paper.{1}",
    "段内残余": "Residual",
    "段内残余\n(百分点)": "Residual\n(pp)",
    "段内残余应变": "Residual strain",
    "每个样品一页.pdf": "specimen-sheets.pdf",
    "点数": "Points",
    "状态": "Status",
    "独立样品重复性": "Independent replicates",
    "用途": "Role",
    "疑似初始试运行": "Possible preliminary run",
    "疑似试运行": "Preliminary",
    "目标": "Target",
    "目标力 (N)": "Target force (N)",
    "目标应力 (MPa)": "Target stress (MPa)",
    "目标应变 (%)": "Target strain (%)",
    "目标按试验方法匹配。目标单位见样品方法，卸载下限逐项显示。应变差以百分点计。": "Targets follow the experiment method. Each row retains its unloading "
    "floor. Strain changes in pp.",
    "相对首加载起点的应变 (%)": "Strain from first loading origin (%)",
    "窗口内不同应变点不足三个或应力无变化": "Too few distinct strains or constant stress in the fit window",
    "窗口拟合完成": "Fit complete",
    "窗口斜率为非正值": "Nonpositive fit slope",
    "窗口线性较弱，需结合拟合点判读": "Weak linearity; inspect the fit points",
    "端点行": "End row",
    "第 ": "Cycle ",
    "第 {0} 周": "Cycle {0}",
    "第 {0} 周，力在 {1}% 应变处达到 {2} N（原始行 {3}），之后应变继续增至 {4}%（原始行 {5}）。": "Cycle {0} reached {2} N at {1}% strain (row "
    "{3}); strain subsequently reached {4}% (row "
    "{5}).",
    "第 {0}–{1} 周 · {2}": "Cycles {0}–{1} · {2}",
    "第 {0}、{1} 周": "Cycles {0}, {1}",
    "线性拟合": "Linear fit",
    "组别": "Group",
    "终止判读": "Termination",
    "终止区间放大": "End of acquisition",
    "终止原因待核实": "Unresolved termination",
    "续测与参考点": "Resumed testing",
    "续测交界处的重复加载": "Repeated target at the segment boundary",
    "缺少可配对的加载换向和卸载应变。": "No paired reversal and unloading strain.",
    "缺少独立断裂标记": "no independent break marker",
    "行级确认": "Row confirmed",
    "补充解释 · ": "Interpretation · ",
    "表列代表周次，完整指标见逐周 CSV。": "Selected cycles shown; see the cycle CSV for all rows. ",
    "计算口径": "Definitions",
    "记录包含加载或卸载未完成的区间。表中保留已测极值，缺少完整卸载端点的恢复量与残余量显示为 —。": "Loading or unloading stopped before completion. Measured "
    "extrema remain available. Recovery and residual entries "
    "require an observed unload endpoint.",
    "记录总览": "Acquisition inventory",
    "记录级确认": "Record confirmed",
    "载荷骤降并保持低位，位移或应变未同步卸载": "Load drops and remains low without reverse motion",
    "达标 / 可评价": "Pass / tested",
    "连续有效块 {0} 个。截面校核相对误差 {1}。": "Valid continuous blocks: {0}. Relative section check error: {1}. ",
    "逐周峰值与取点": "Cycle peaks and source rows",
    "逐周性能": "Cycle metrics",
    "逐周指标.csv": "cycles.csv",
    "逐点分段.csv": "points.csv",
    "采样点未定位": "Unlocated",
    "采集与覆盖": "Acquisition coverage",
    "采集在较高载荷的加载途中终止，终止原因未记录": "Recording stopped under load; the cause is unrecorded",
    "采集段 {0}   ·   应力–应变与逐周响应": "Segment {0}   ·   stress–strain and cycle metrics",
    "采集段 {0}   ·   载荷历程与终止区间": "Segment {0}   ·   load history and endpoint",
    "采集段 {0} · {1} 个采样点": "Segment {0} · {1} samples",
    "采集段按试验顺序排列，周次连续编号。应变差分别相对于本段起点计算，跨段累计值缺少共同零点。": "Cycles follow acquisition order. Each segment retains its "
    "measured reference strain; a cumulative residual across resets "
    "requires a shared reference.",
    "采集段缺少共同的物理通道，分段曲线见详细报告": "No shared channel. See the acquisition plots.",
    "重复性": "Repeatability",
    "重复样品统计.csv": "replicate-statistics.csv",
    "阶段": "Status",
    "需要中文字体，请通过 MECHCURVE_FONT 指定本地字体文件": "Set MECHCURVE_FONT to a CJK font file.",
    "首加载拉伸弹性模量": "Initial tensile modulus",
    "首加载拉伸模量   /   拟合取点复核": "First loading branch   /   fit evidence",
    "首加载支未覆盖完整应变窗口": "First branch does not cover the full fit window",
    "首加载模量与完全可恢复周次": "Initial modulus and recoverable cycles",
    "首加载段存在缺失采样": "Missing samples on first loading branch",
    "首加载起点应变或采样依据缺失": "Missing first loading reference",
    "首周拉伸弹性模量": "First-cycle modulus",
    "原始序号缺少对应 XML 试样条目": "No XML specimen entry matches the acquisition index",
    "指定的断裂前行号缺少有效载荷或超出原始表": "The specified pre-break row is outside the record or has no valid load",
    "截面积必须为正值": "Cross-sectional area must be positive",
    "主力学通道没有有限采样": "The primary mechanical channel has no finite samples",
    "无采样行": "No samples",
    "需要有单位的时间与力或应力通道": "A time channel and a force or stress channel with units are required",
    "采样记录为空": "Empty acquisition",
    "无法识别表头、编码或分隔符": "Unrecognized header, encoding or delimiter",
}
