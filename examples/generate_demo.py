"""Rebuild the public synthetic campaign using only Python's standard library."""

import csv
import json
from pathlib import Path

DESTINATION = Path(__file__).resolve().parent / "demo"


def cyclic(targets, residuals, modulus):
    """Prescribe loading/unloading branches with known unload endpoint strain."""
    points = [(0.0, 4.0)]
    for target, residual in zip(targets, residuals, strict=True):
        start, floor = points[-1]
        for step in range(1, 81):
            strain = start + (target - start) * step / 80
            relative = strain - start
            stress = (
                floor
                + modulus * 10 * min(relative, 0.25)
                + modulus * 6.7 * max(relative - 0.25, 0)
            )
            points.append((strain, stress))
        peak = points[-1][1]
        for step in range(1, 71):
            remaining = 1 - step / 70
            strain = residual + (target - residual) * remaining
            stress = floor + (peak - floor) * remaining**1.32
            points.append((strain, stress))
    return points


def write_record(filename, points, area, gauge):
    with (DESTINATION / filename).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(
            ("time_s", "extension_mm", "force_N", "strain_pct", "stress_MPa")
        )
        for i, (strain, stress) in enumerate(points):
            writer.writerow(
                [
                    f"{x:.8f}"
                    for x in (
                        i * 0.2,
                        gauge * strain / 100,
                        area * stress,
                        strain,
                        stress,
                    )
                ]
            )


def main():
    DESTINATION.mkdir(exist_ok=True)
    notes = {
        "batch_note": "Synthetic demonstration. All inputs are prescribed numerical examples.",
        "records": {},
    }
    for file, name, seq, targets, residuals, modulus in [
        (
            "cyclic-a.csv",
            "Cyclic A",
            1,
            [0.45, 0.85, 1.25, 1.65, 2.05, 2.45],
            [0.004, 0.012, 0.021, 0.028, 0.061, 0.12],
            52,
        ),
        ("resumed-b1.csv", "Resumed B", 1, [0.5, 0.9, 1.3], [0.006, 0.014, 0.023], 67),
        ("resumed-b2.csv", "Resumed B", 2, [1.3, 1.7, 2.1], [0.022, 0.042, 0.09], 67),
    ]:
        write_record(file, cyclic(targets, residuals, modulus), 2.8, 24)
        notes["records"][file] = {
            "sample": name,
            "sequence": seq,
            "history": "cyclic",
            "plot_role": "main",
            "targets": [
                {"axis": "strain_pct", "target": target, "lower_MPa": 4}
                for target in targets
            ],
        }
    tensile = [
        (i / 100, 580 * min(i / 100, 0.55) + 33 * max(i / 100 - 0.55, 0))
        for i in range(301)
    ]
    write_record("tensile-c.csv", tensile + [(3.01, 2.5), (3.02, 1.5)], 3.2, 30)
    notes["records"]["tensile-c.csv"] = {
        "sample": "Tensile C",
        "history": "tension",
        "fractured": True,
    }
    (DESTINATION / "notes.json").write_text(
        json.dumps(notes, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


if __name__ == "__main__":
    main()
