# Reading a MechCurve report · 如何读报告

A report follows the recorded physical specimen. A CSV identifies an acquisition. When one specimen resumes in another acquisition, give the two records the same `sample` and explicit `sequence` in the notes. Each original row keeps its own acquisition ID, units and strain reference. Target repetition at a boundary contributes two observations. [Example notes](../examples/demo/notes.json)

## Inputs and units

MechCurve reads CSV, semicolon- or tab-delimited data, including UTF-8, UTF-16 and GB18030 exports. Canonical headers are `time_s`, `extension_mm`, `force_N`, `strain_pct` and `stress_MPa`. Named channels can carry units in their header or a units row. Discovery can associate Bluehill XML metadata and track companion binary files. Numerical samples come from the delimited export. A supplied cross-sectional area in mm² allows conversion between force in N and engineering stress in MPa. Missing observations remain empty. An unavailable strain channel limits which properties can be calculated.

## What each number means

| Quantity | Measured reference and unit |
| --- | --- |
| Peak force | Maximum force on the loading branch, N. Stress and strain at peak force use that same row. |
| Peak stress / maximum strain | Each channel's own observed maximum on that loading branch, with its own row. |
| Applied or total strain | Reversal strain minus the acquisition segment's reference strain, percentage points. |
| Loading increment | Reversal strain minus this cycle's start strain, percentage points. |
| Recoverable strain | Reversal strain minus strain at the measured unload endpoint, percentage points. |
| Residual strain | Unload endpoint strain minus the segment reference. A separate column gives the increment relative to the cycle start. |
| First-loading modulus | Ordinary least squares with intercept on the first formal loading branch at 0.05%–0.15% strain increment. Engineering stress in MPa is fitted against fractional strain, then the slope is converted to GPa. |
| Maximum fully recoverable applied strain | Largest observed applied strain among complete cycles with finite signed segment residual **strictly below 0.03 percentage points**. Exact equality fails. Tied cycles are retained. |

The cutoff is an operational criterion for this workflow. Read the unload stress alongside the residual. A signed negative residual is retained and passes the stated one-sided test. On a resumed specimen the segment zero may change. An estimate of the specimen's cumulative permanent elongation across a reset requires an independent common reference. A gap, a partial unloading branch or an unlocated fracture can leave derived metrics unavailable. The report displays the observed facts and available source rows.

Fit diagnostics include point count, R² and the measured fit rows. A window with inadequate coverage, too few distinct strain values or a nonpositive slope cannot supply the reported modulus. A weakly linear window retains its quality flag. Load drops can establish candidates. A break annotation or instrument record supplies independent evidence. Post-break elongation requires initial and final gauge lengths. Read the detailed report for the rows and basis behind each event.

## Plots and preliminary trials

Color identifies the cycle. Loading is solid and unloading dashed. Short series use distinct colors, longer histories use a sequential colormap. In the recovery panel circles indicate recovered strain and diamonds indicate residual strain. Resumed observations use open markers. Where residuals are small relative to the applied range, the sheet adds a dedicated residual panel with the same horizontal scale. [Matplotlib colormap guidance](https://matplotlib.org/stable/users/explain/colors/colormaps.html) · [Matplotlib line styles](https://matplotlib.org/stable/gallery/lines_bars_and_markers/linestyles.html)

Initial test acquisitions are excluded from formal plots when the selection rule finds a short, incomplete initial run followed by a longer cyclic acquisition in the same package. A fracture candidate is retained for inspection. Override `plot_role` with `"main"` or `"preliminary"` when the experimental record establishes the intended role. Both roles retain source points and a detailed report. Independent specimens need explicit replicate groups for between-specimen statistics. A repeat visit within one specimen keeps its occurrence number.

## 中文读图提示

第一步，读页首两个红色数值。模量取首个正式采集段第一加载支，在相对于段起点的 0.05%–0.15% 应变窗口内拟合。循环样品的第二个数值表示已观测完整循环中达到恢复判据的最大施加应变。

第二步，核对回线、散点图与逐周表。峰值力处的应力和应变取自峰值力所在行，加载换向和卸载端点各有独立行号。应变差以百分点表示。总应变等于相对于本段参考点的换向应变，可恢复应变等于换向到卸载端点的应变差，残余应变等于端点相对本段参考点的应变差。

第三步，结合卸载应力检查恢复判定。完整循环按有符号残余严格小于 0.03 个百分点判定；恰好等于阈值归为未达标。续测时保留分段参考点和重复目标。拉断判读应结合载荷骤降、位移或应变行为及独立的仪器标记或实验者备注。
