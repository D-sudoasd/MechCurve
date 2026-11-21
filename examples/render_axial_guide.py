"""Render the README figures from the analyzed public axial demo.

Usage: python examples/render_axial_guide.py RUN_DIRECTORY OUTPUT_DIRECTORY
"""

import argparse
import json
from pathlib import Path
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np


INK = "#1d3441"
TEAL = "#006d77"
RUST = "#ae552f"
MUTED = "#516773"
PAPER = "#faf9f5"


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def canvas():
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(10.8, 3.72),
        layout="constrained",
        gridspec_kw={"width_ratios": [1.2, 1]},
    )
    fig.set_facecolor(PAPER)
    for ax in axes:
        ax.set_facecolor(PAPER)
        ax.grid(axis="y", lw=0.6, color="#d5dcda")
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["bottom", "left"]].set_color("#8d9d9f")
        ax.xaxis.set_major_locator(MaxNLocator(6))
        ax.yaxis.set_major_locator(MaxNLocator(5))
    return fig, axes


def headings(ax, title, x, y):
    ax.set_title(title, loc="left", pad=10, weight="bold", fontsize=13)
    ax.set_xlabel(x)
    ax.set_ylabel(y)


def note(ax, x, y, label, color, dx, dy):
    ax.annotate(
        label,
        (x, y),
        xytext=(dx, dy),
        textcoords="offset points",
        ha="right" if dx < 0 else "left",
        va="center",
        fontsize=8.5,
        color=color,
        arrowprops={"arrowstyle": "-", "color": color, "lw": 0.8},
    )


def render(run, dest):
    dest.mkdir(parents=True, exist_ok=True)
    records = read(run / "results.json")["records"]
    summaries = read(run / "axial-summary.json")

    def record(name):
        r = next(r for r in records if r["sample"] == name)
        return r, read(run / r["record_json"])["points"]

    def save(fig, name):
        fig.savefig(
            dest / (name + ".png"),
            dpi=165,
            facecolor=fig.get_facecolor(),
            metadata={"Software": "MechCurve"},
        )
        plt.close(fig)

    cyclic, pts = record("Cyclic A")
    lookup = {p["source_row"]: i for i, p in enumerate(pts)}
    complete = [c for c in cyclic["cycles"] if c["status"] == "complete"]
    fig, (a, b) = canvas()
    colors = plt.get_cmap("viridis")(np.linspace(0.12, 0.8, len(complete)))
    for color, c in zip(colors, complete):
        i, j, k = (lookup[c[key]] for key in ("start_row", "turn_row", "end_row"))
        for block, style in [(pts[i : j + 1], "-"), (pts[j : k + 1], "--")]:
            a.plot(
                [p["strain_pct"] for p in block],
                [p["stress_MPa"] for p in block],
                style,
                color=color,
                lw=1.4,
            )
        a.scatter(pts[j]["strain_pct"], pts[j]["stress_MPa"], color=color, s=18)
        b.scatter(
            c["total_strain_pp"],
            c["residual_segment_pp"],
            s=37,
            marker="D",
            color=color,
            zorder=3,
        )
    headings(a, "Successive cycles", "Applied strain (%)", "Engineering stress (MPa)")
    headings(b, "Residual at unload", "Applied strain (%)", "Segment residual (pp)")
    threshold = complete[0]["residual_threshold_pp"]
    b.axhline(threshold, color=RUST, ls="--", lw=1.1)
    b.text(
        0.025,
        threshold + 0.003,
        f"{threshold:g} pp",
        transform=b.get_yaxis_transform(),
        color=RUST,
        fontsize=8,
    )
    decision = summaries["Cyclic A"]["recovery"]
    for c, dx, dy in [
        (decision["highest_qualifying"][0], -7, 22),
        (decision["first_nonqualifying"], -10, 14),
    ]:
        note(
            b,
            c["applied_pct"],
            c["residual_pp"],
            f"C{c['cycle']}  {c['residual_pp']:.3f} pp",
            INK,
            dx,
            dy,
        )
    save(fig, "guide-cycles")
    t, pts = record("Tensile C")
    ev = t["event"]
    props = t["tensile"]
    peak = t["peak_stress"]
    fig, (a, b) = canvas()
    pre = [p for p in pts if p["source_row"] <= ev["source_row"]]
    a.plot(
        [p["strain_pct"] for p in pre], [p["stress_MPa"] for p in pre], color=TEAL, lw=2
    )
    hi = (peak["strain_pct"], peak["stress_MPa"])
    proof = (props["rp02_strain_pct"], props["rp02_MPa"])
    a.scatter(*proof, marker="D", s=34, color=RUST, zorder=3)
    a.scatter(*hi, marker="^", s=48, color=INK, zorder=3)
    note(a, *proof, "0.2% proof", RUST, 14, -20)
    note(a, *hi, "Peak stress", INK, -18, -23)
    a.scatter(
        pre[-1]["strain_pct"],
        pre[-1]["stress_MPa"],
        s=43,
        facecolor=PAPER,
        edgecolor=RUST,
        zorder=3,
    )
    headings(
        a, "Tensile response", "Engineering strain (%)", "Engineering stress (MPa)"
    )
    zoom = [p for p in pts if p["source_row"] >= ev["source_row"] - 10]
    b.plot(
        [p["source_row"] for p in zoom],
        [p["force_N"] for p in zoom],
        ".-",
        color=TEAL,
        lw=1.6,
    )
    b.axvspan(ev["source_row"], ev["after_row"], color="#ebd7bf", alpha=0.7)
    for row, dx, dy in [(ev["source_row"], -12, -28), (ev["after_row"], -42, 23)]:
        p = next(p for p in pts if p["source_row"] == row)
        b.scatter(row, p["force_N"], s=33, color=RUST, zorder=4)
        note(b, row, p["force_N"], f"Row {row}", RUST, dx, dy)
    headings(b, "Terminal load interval", "Source CSV row", "Force (N)")
    save(fig, "guide-fracture")
    fig, (a, b) = canvas()
    br = cyclic["cycle_branches"]
    x = np.array([c["local_cycle"] for c in br])
    a.bar(
        x - 0.19,
        [c["loading_work_MJ_m3"] for c in br],
        0.37,
        color=TEAL,
        label="Loading",
    )
    a.bar(
        x + 0.19,
        [c["returned_work_MJ_m3"] for c in br],
        0.37,
        color="#d29b64",
        label="Returned",
    )
    a.legend(frameon=False, fontsize=8, loc="upper left")
    headings(a, "Work along measured branches", "Cycle", "Work density (MJ/m³)")
    b.plot(
        x,
        [c["loading_secant_GPa"] for c in br],
        "o-",
        color=TEAL,
        ms=4,
        label="Loading secant",
    )
    b.plot(
        x,
        [c["unloading_secant_GPa"] for c in br],
        "s--",
        color=RUST,
        ms=4,
        label="Unloading secant",
    )
    b.legend(frameon=False, fontsize=8, loc="best")
    headings(b, "Endpoint secants", "Cycle", "Secant (GPa)")
    save(fig, "guide-branches")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    with plt.rc_context(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "text.color": INK,
            "axes.labelcolor": MUTED,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.titlecolor": INK,
        }
    ):
        render(args.run, args.output)
