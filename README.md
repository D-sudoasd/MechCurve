# MechCurve

[简体中文](README.zh-CN.md) · [Specimen sheets (PDF)](assets/showcase/specimen-sheets.en.pdf) · [Methods](docs/methods.md) · [Illustrated gallery](docs/gallery.md)

<img src="assets/gallery/01-cover-preview.webp" alt="Concept illustration of a tensile coupon held between aligned wedge grips" width="100%">

**One physical specimen, one performance sheet.** Give a local agent a folder of tensile or cyclic-loading exports. MechCurve finds the measured reversals, fits the first-loading modulus, and writes a printable PDF with the stress–strain history, recovery scatter and cycle metrics. Each reported event points back to its acquisition and original CSV row.

### See what the software produces

<img src="assets/showcase/sheet-overview.webp" alt="Actual software output for synthetic Cyclic A, Resumed B and Tensile C, one page per specimen" width="100%">

The bundled campaign contains three synthetic specimens. **Cyclic A** returns 52.00 GPa from its first loading branch. At 1.65% applied strain the residual is 0.028 percentage points. At 2.05% it is 0.061. The sheet therefore highlights **1.650%** as the highest observed applied strain meeting the 0.03-point criterion. **Resumed B** retains two acquisitions and both visits to the same target on one page. **Tensile C** carries an explicit synthetic fracture note and a source-row-linked load drop.

[Open all three specimen pages](assets/showcase/specimen-sheets.en.pdf) · [Read the campaign report](assets/showcase/campaign-report.en.pdf) · [Inspect six software-generated figures](docs/gallery.md#software-output)

### Run the demo

Python 3.11 or later. From a clone of this repository:

```sh
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
# .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[agent]"
mechcurve inspect examples/demo
mechcurve analyze examples/demo --notes examples/demo/notes.json --lang en
```

Open **examples/demo_MechCurve/open-results.html**. The offline index links the specimen sheets, detailed reports, vector figures, CSV tables and JSON. The CLI returns the verified run path. Use it in place of `RUN_DIRECTORY` to inspect the two visits to Resumed B's 1.3% target:

```sh
mechcurve cycles RUN_DIRECTORY --record resumed-b1.csv --cycle 3
mechcurve cycles RUN_DIRECTORY --record resumed-b2.csv --cycle 4
mechcurve verify RUN_DIRECTORY
```

### Bring your own experiment

| You supply | MechCurve delivers |
| --- | --- |
| CSV with time, force or stress and available strain or extension channels | Unit-normalized points, observed peaks, load/unload phase and source rows |
| Cyclic history with measurable unload endpoints | Cycle colors, peak-force rows, reversal rows, applied, recovered and residual strain |
| Specimen identity and acquisition order for a resumed test | One page per specimen, continuous cycle numbers and separate measured segment references |
| Monotonic tension and independent break evidence when available | First-loading modulus, eligible tensile metrics and a termination diagnostic |
| A folder with preliminary acquisitions | Formal plots, retained trial rows, recorded selection reasons and optional role overrides |

Call `mechcurve analyze INPUT_FOLDER --notes NOTES.json --output OUTPUT_FOLDER --lang en`. Keep output outside the source tree. Chinese reports use `--lang zh` (default) and a local CJK font. An English report can retain Chinese sample names when rendered with a CJK font. Install Noto Sans CJK SC or set `MECHCURVE_FONT` to a suitable font file. [Input and metric definitions](docs/methods.md) · [Runnable specimen notes](examples/demo/notes.json)

### Use from an agent

The optional stdio MCP server exposes inspection, analysis, source-row lookup, cycle lookup and delivery verification. Calculations run locally in Python. The host agent supplies any interpretation and cites the acquisition and source row. Existing run receipts support verified reuse of numerical records, segment figures, detailed reports, specimen sheets and merged histories. [MCP setup and tool calls](docs/agent.md)

### Reproduce and develop

```sh
python examples/generate_demo.py
python -m pip install -e ".[agent,test]"
python -m pytest -q
```

The generator prescribes all public stress–strain data. The gallery includes software output and twelve original conceptual illustrations. [Gallery and artwork provenance](docs/gallery.md) · [MIT license](LICENSE)
