"""Protocol discovery shared by CLI and stdio agent hosts."""

from pathlib import Path
from .inputs import acquisition_notes, discover, locate_inputs, metadata
from .protocols import TITLES, PAIRS, classify, choose_coordinates
from .tableio import read_table


def catalog():
    return {
        key: {
            "en": name[1],
            "zh": name[0],
            "coordinate_pairs": PAIRS.get(
                key,
                [(("strain_pct", "extension_mm", "time_s"), ("stress_MPa", "force_N"))],
            ),
        }
        for key, name in TITLES.items()
    }


def inspect_records(folder, notes=None):
    requested = Path(folder).resolve(strict=True)
    source, files = locate_inputs(requested)
    options = acquisition_notes(
        requested if requested.is_file() else source, notes
    ).get("records", {})
    results = []
    for desc in discover(source, files):
        item = {
            "record": desc["record"],
            "has_xml": bool(desc["xml"]),
            "has_binary": bool(desc["binary"]),
        }
        opts = options.get(desc["record"], {})
        try:
            if desc.get("input_error"):
                raise ValueError(desc["input_error"])
            points, cols, labels, selected = read_table(
                desc["path"], desc.get("sheet"), opts, preserve_native=True
            )
            try:
                meta = metadata(desc["xml"], desc["index"])
            except (OSError, ValueError, SyntaxError, AttributeError, IndexError):
                meta = {}
            mode, basis = classify(desc["record"], cols, labels, points, meta, opts)
            item.update(
                test_type=mode,
                classification=basis,
                source_columns=labels,
                observations=len(points),
            )
            if mode not in ("axial", "cyclic", "tension"):
                mode, basis, x, y = choose_coordinates(
                    mode, basis, cols, selected, opts
                )
                item.update(test_type=mode, classification=basis, axes={"x": x, "y": y})
        except (OSError, ValueError) as exc:
            item["intake_issue"] = str(exc)
        results.append(item)
    return results
