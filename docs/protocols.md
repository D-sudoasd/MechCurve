# Mechanical test protocols · 力学试验类型

Run `mechcurve protocols` for the machine-readable catalog. A dataset can mix test methods, specimens and file formats in one campaign. Each formal specimen receives one sheet. Its detailed report includes the individual acquisitions, units, measurements and evidence rows. The public examples are synthetic. [Input files](../examples/protocols) · [Generator](../examples/generate_protocols.py)

| Test type in notes | Useful coordinates | Quantities and conditions |
| --- | --- | --- |
| `tension`, `cyclic` | Engineering stress–strain or force–travel | Established first-loading fit, conditional tensile properties, cycle events and residual/recoverable strain. Each event retains its observed row. [Axial methods](methods.md) |
| `compression` | Signed stress–strain or force–travel | Measured peak compressive stress magnitude. The fit uses the first loading branch through 0.05%–0.15% compressive strain increment. Source signs remain available. Force and known `area_mm2` supply nominal stress. |
| `flexure` | Deflection and total applied force, or measured flexural strain and stress | Load–deflection extrema. A rectangular beam with an explicitly specified fixture can produce nominal peak outer-fiber stress. |
| `shear` | Shear strain and stress or force–travel | Observed peak shear stress magnitude where a stress channel is available. |
| `torsion` | Twist and torque | Peak torque. A declared solid circular section enables nominal surface shear stress. |
| `creep` | Time and strain or displacement | Hold duration, signed endpoint change and interval-average rate. Strain changes are percentage points. |
| `relaxation` | Time and stress or force | Signed initial-minus-final response and final/initial response at the hold endpoints. |
| `fatigue` | Time and stress or force, or cycle count and response | Waveform extrema, half-range, midrange and minimum/maximum ratio for complete observed peak-to-peak excursions. Cycle-indexed tables show the observed range and highest recorded cycle. |
| `indentation` | Depth and indentation force | Peak force magnitude and maximum measured depth. Contact hardness and contact modulus require additional calibration and modelling. |
| `peel` | Travel and peel force | Peak measured force per width when `geometry.width_mm` is supplied. This peak describes an extreme, independently of a steady-state peel average. |
| `generic` | Native column pair or multiple recorded channels | Minimum and maximum paired responses and their source rows. A user-selected linear interval can give a slope in the measured axis units. |

## Inspect, select, analyze

```sh
mechcurve inspect examples/protocols --notes examples/protocols/notes.json
mechcurve analyze examples/protocols --notes examples/protocols/notes.json --lang en
mechcurve analyze examples/protocols/beam.tsv --lang zh
```

CSV, TSV and delimited TXT exports can declare units in the header or on a units row. XLSX uses each visible worksheet as an acquisition, identified by `filename.xlsx#sheet`; evidence rows are Excel row numbers. Spreadsheet formulas need saved numerical results. A single acquisition file can be passed directly. Its default delivery directory is a sibling named `filename.ext_MechCurve`. Explicit `--notes` takes precedence. Directory input also recognizes `mechcurve.json` in the input directory, and a file can have an adjacent `filename.ext.mechcurve.json`. The existing Chinese notes filename in the default results directory remains supported.

The router records how it selected a method. It considers explicit notes, loading programs, specialized channels, channel names, acquisition names, and observable control/sign patterns. Axial data with positive engineering stress and strain can be consistent with more than one test method. Use a record note when the fixture or control history resolves that ambiguity. `inspect` reports normalized channel keys, source headers and scale factors. An `axial` candidate resolves to tension or cyclic loading after event analysis.

Unknown two-column curves retain their native coordinates. A wider general table uses a known physical pair where available, then elapsed time or the physical source row. Additional signals appear separately in the detailed report. Headerless numeric tables retain the first observation. A single signal is plotted against the source row. For nonstandard headers, supply exact header text in `axes`. A missing time channel uses acquisition order for axial event localization. Time-based rates and dwell durations require a measured clock.

```json
{
  "records": {
    "instrument.xlsx#Run 2": {
      "sample": "Coupon B",
      "sequence": 2,
      "test_type": "generic",
      "header_row": 5,
      "axes": {"x": "Opening (mm)", "y": "Bridge (mV)"},
      "fit_rows": [12, 24]
    }
  }
}
```

## Numerical conventions

- **Hold behavior.** Supply inclusive `hold_rows` when the experimental log identifies the interval. A measured control channel must be nonzero and stable within a 2% full-range tolerance relative to its median. When a ramp is present, the automatic search retains the longest uninterrupted plateau with at least six points and at least 20% of the recorded time span. A confirmed whole-record hold can also be evaluated from its endpoints. Missing observations, source-row gaps and clock reversals are excluded from a hold. The reported rate is the endpoint change divided by elapsed time over that interval. It does not establish a steady-state constitutive rate.
- **Fatigue.** A waveform excursion runs from a confirmed upper reversal through a lower reversal to the next confirmed upper reversal within one continuous block. The default reversal hysteresis is 2% of the block range. Override it in response units with `reversal_threshold`. The exported half-range is `(max − min)/2`, midrange is `(max + min)/2`, and ratio is `min/max` when the denominator is nonzero. Excursion numbers in `fatigue-cycles.csv` are local to the acquisition. A cycle-index table alone cannot establish failure or an endurance limit. [Fatemi, constant-amplitude loading](https://efatigue.com/training/Chapter_4.pdf)
- **Beam and torsion geometry.** For a simply supported, rectangular small-deflection beam the nominal surface stress magnitude is `3 |F| (L − l) / (2 b h²)`. Use `geometry.fixture = three_point_rectangular` with `span_mm`, `width_mm`, `thickness_mm`, or `four_point_rectangular` with the additional inner loading span `inner_span_mm`. Three-point loading has `l = 0`. For a solid circular shaft under nominal elastic torsion, `16 |T| / (π d³)` uses torque in N·mm and diameter in mm. Set `fixture = solid_circular` and `diameter_mm`. The reported quantities are nominal beam/shaft estimates. [Instron flexural fixtures](https://www.instron.com/en/resources/literature/5kn-flexure-fixture-reference-manual/) · [Roylance, Shear and Torsion](https://eng.libretexts.org/Bookshelves/Mechanical_Engineering/Mechanics_of_Materials_%28Roylance%29/02%3A_Simple_Tensile_and_Shear_Structures/2.03%3A_Shear_and_Torsion)
- **Selected slope and signed integral.** `fit_rows` selects both endpoints by physical row. The linear fit includes an intercept and requires a single monotonic branch, at least three distinct abscissae and finite paired observations. The report includes the fit rows and R². For complete force–travel or torque–twist paths the signed trapezoidal integral is exported in joules; twist is converted to radians. Its interpretation depends on fixture compliance and the instrument sign convention.

## 中文操作

先用 `mechcurve inspect` 查看表头、单位换算与类型判据。物理样品有续测时，在各段备注中填写相同的 `sample` 和真实的 `sequence`。无法从记录区分压缩、弯曲或剪切时，按实验记录填写 `test_type`。没有独立时间列时，图表可显示原始行序；蠕变速率和松弛时长需要实测时间。未知曲线可以通过 `axes` 指定任意两列，并用 `fit_rows` 指定需要拟合的原始行区间。

结果页提供单页 PDF、样品详报、批次报告、每段独立的 PDF/SVG/PNG 及数据表。多类型批次的 `protocol-metrics.csv` 列出指标、单位和原始行号，疲劳波形另导出 `fatigue-cycles.csv`。单页可容纳四个采集段的图，更多采集段及逐项结果在详报中连续展示。解析失败的文件会单独列出，其他可用样品继续交付。
