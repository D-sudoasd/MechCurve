"""Generate small, independently checkable mechanical curves for a mixed campaign."""

import argparse
import csv
import json
import math
from pathlib import Path


def generate(folder):
    folder.mkdir(parents=True, exist_ok=True)
    records = {}

    def save(name, labels, rows, **notes):
        path = folder / name
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.writer(
                f, delimiter="\t" if path.suffix == ".tsv" else ",", lineterminator="\n"
            )
            writer.writerow(labels)
            writer.writerows([[f"{v:.9g}" for v in row] for row in rows])
        if notes:
            records[name] = notes

    save(
        "compression.csv",
        ["Compressive strain (%)", "Compressive stress (MPa)"],
        [
            (-i / 100, -600 * min(i / 100, 0.4) - 70 * max(i / 100 - 0.4, 0))
            for i in range(91)
        ],
    )
    save(
        "beam.tsv",
        ["Deflection (mm)", "Force (N)"],
        [(i / 20, min(20 * i / 20, 12 + 4 * i / 20)) for i in range(41)],
        geometry={
            "fixture": "three_point_rectangular",
            "width_mm": 8,
            "thickness_mm": 2,
            "span_mm": 40,
        },
    )
    save(
        "torsion.csv",
        ["Twist (rad)", "Torque (N·mm)"],
        [(i * 0.001, 120 * i) for i in range(41)],
        geometry={"fixture": "solid_circular", "diameter_mm": 5},
    )
    save(
        "shear.csv",
        ["Shear strain (%)", "Shear stress (MPa)"],
        [(i * 0.02, 10 * min(i, 12) + 3 * max(0, i - 12)) for i in range(41)],
    )
    save(
        "creep.csv",
        ["Time (min)", "Stress (MPa)", "Creep strain (%)"],
        [(i, 50, 0.4 + 0.01 * i) for i in range(31)],
    )
    save(
        "relaxation.csv",
        ["Time (s)", "Strain (%)", "Relaxation stress (MPa)"],
        [(i, 1, 120 + 60 * math.exp(-i / 10)) for i in range(41)],
    )
    save(
        "fatigue.csv",
        ["Cycle count", "Stress amplitude (MPa)"],
        [(1000, 350), (8000, 300), (40000, 260), (200000, 220)],
    )
    save(
        "indentation.csv",
        ["Indentation depth (um)", "Load (mN)"],
        [(i * 0.1, 0.004 * i * i) for i in range(26)]
        + [(1.5 + i * 0.04, 2.5 * (i / 25) ** 1.5) for i in range(24, -1, -1)],
    )
    save(
        "peel.csv",
        ["Peel displacement (mm)", "Peel force (N)"],
        [(i / 2, 8 * (1 - math.exp(-i / 6)) + 0.2 * math.sin(i)) for i in range(41)],
        geometry={"width_mm": 10},
    )
    save(
        "custom.csv",
        ["Opening (mm)", "Bridge signal (mV)"],
        [(i / 20, 1.5 + 4 * math.tanh(i / 15)) for i in range(31)],
    )
    save(
        "fatigue-wave.csv",
        ["Time (s)", "Stress (MPa)"],
        [(i / 20, 15 + 45 * math.sin(math.pi * i / 10)) for i in range(101)],
    )
    save(
        "multi-channel.tsv",
        ["Time (s)", "Bridge A (mV)", "Bridge B (mV)", "Temperature (K)"],
        [(i * 0.2, 2 + 0.3 * i, 4 + 0.075 * i, 295 + 0.02 * i) for i in range(21)],
        test_type="generic",
        fit_rows=[2, 12],
    )
    notes = {
        "batch_note": "Synthetic mixed-protocol demonstration.",
        "records": records,
    }
    (folder / "notes.json").write_text(
        json.dumps(notes, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "destination",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent / "protocols",
    )
    generate(parser.parse_args().destination)
