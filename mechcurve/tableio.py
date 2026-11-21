"""Read a tabular acquisition while preserving source row IDs and channel units."""

import csv
import io
import math
import re
from zipfile import BadZipFile
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from .channels import AXIAL, COLUMNS

TABLE_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx"}


def finite(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def workbook(path):
    try:
        return load_workbook(path, read_only=True, data_only=True)
    except (BadZipFile, OSError, InvalidFileException, KeyError, SyntaxError) as exc:
        raise ValueError(f"Cannot read workbook {path.name}: {exc}") from exc


def table_rows(path, sheet=None):
    if path.suffix.lower() == ".xlsx":
        book = workbook(path)
        try:
            for row, cells in enumerate(book[sheet].values, 1):
                yield row, [str(v).strip() if v is not None else "" for v in cells]
        except (BadZipFile, SyntaxError, InvalidFileException, KeyError) as exc:
            raise ValueError(f"Cannot read worksheet {sheet}: {exc}") from exc
        finally:
            book.close()
        return
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            text = raw.decode(encoding)
        except UnicodeError:
            continue
        if "\0" not in text:
            break
    else:
        raise ValueError("Unknown text encoding")
    # Inspect several lines so an instrument preamble can precede the header.
    candidates = text.splitlines()[:100]
    sep = max((",", "\t", ";"), key=lambda s: sum(line.count(s) for line in candidates))
    reader = csv.reader(io.StringIO(text), delimiter=sep)
    for row in reader:
        yield reader.line_num, [v.strip() for v in row]


def split_header(s):
    m = re.fullmatch(r"(.*?)\s*[\[(]([^\])]+)[\])]\s*", s)
    return (m[1].strip(), m[2].strip()) if m else (s, "")


def read_table(path, sheet=None, opts=None, *, preserve_native=False):
    opts = opts or {}
    rows = list(table_rows(path, sheet))
    axes = opts.get("axes", {})
    start = opts.get("header_row")
    if start is None:
        # Instrument preambles are frequently one cell or blank. A tabular
        # preamble can be disambiguated with header_row in the specimen notes.
        start = next((i for i, row in rows if sum(bool(v) for v in row) >= 2), None)
    if (
        start is None
        and len(rows) > 1
        and all(len(row) == 1 for _, row in rows if any(row))
    ):
        start = next((i for i, row in rows if any(row)), None)
    idx = next((n for n, (i, _) in enumerate(rows) if i == start), None)
    if idx is None:
        raise ValueError("No header with two columns; specify header_row")
    header = rows[idx][1]
    samples = rows[idx + 1 :]
    if all(finite(v) is not None for v in header if v) and any(header):
        samples = rows[idx:]
        header = [f"Column {j}" for j in range(1, len(header) + 1)]
    first = samples[0][1] if samples else []
    units_set = {u for _, units in COLUMNS.values() for u in units if u}
    unit_line = bool(
        any(first)
        and any(finite(v) is None for v in first if v)
        and all(
            not v or v.startswith(("(", "[")) or v.lower() in units_set for v in first
        )
    )
    if unit_line:
        samples = samples[1:]
    if not samples:
        raise ValueError("No observations below the header")
    lookup = {
        alias.lower(): key
        for key, (aliases, _) in COLUMNS.items()
        for alias in (key, *aliases)
    }
    mapping = {}
    labels = {}
    raw_keys = {}
    for j, name in enumerate(header):
        if not name:
            continue
        label, unit = split_header(name)
        unit = unit or (first[j].strip(" ()[]") if unit_line and j < len(first) else "")
        key = lookup.get(label.lower())
        native = False
        if (
            key
            and preserve_native
            and label.lower() != key.lower()
            and unit.lower() not in COLUMNS[key][1]
        ):
            native = True
            key = None
        if key:
            units = COLUMNS[key][1]
            current = (
                unit.lower()
                if unit or label.lower() != key.lower()
                else next(iter(units))
            )
            if current not in units:
                raise ValueError(f"Unsupported or absent unit for {name}: {unit}")
            scale = units[current]
            if key == "force_N" and unit == "MN":
                scale = 1e6
            if (
                key
                in (
                    "stress_MPa",
                    "shear_stress_MPa",
                    "flexural_stress_MPa",
                    "amplitude_MPa",
                )
                and unit == "mPa"
            ):
                scale = 1e-9
        else:
            if not any(
                j < len(row) and finite(row[j]) is not None for _, row in samples
            ):
                continue
            key = f"column_{j + 1}"
            scale = 1
        if key in mapping or name in raw_keys:
            raise ValueError(f"Duplicate channel {name}")
        mapping[key] = (j, scale)
        labels[key] = {
            "header": name,
            "label": label,
            "unit": unit,
            "scale_to_canonical": scale,
        }
        if native:
            labels[key]["unconverted"] = True
        raw_keys[name] = key
    if not mapping:
        raise ValueError("No numerical channels")
    selected = {}
    for axis, name in axes.items():
        key = raw_keys.get(name, name)
        if key not in mapping:
            raise ValueError(f"Axis {axis} does not match a column: {name}")
        selected[axis] = key
    if selected and selected["x"] == selected["y"]:
        raise ValueError("x and y must be different columns")
    points = []
    for i, row in samples:
        if not any(row):
            continue
        pt = dict.fromkeys(AXIAL)
        pt["source_row"] = i
        for key, (j, scale) in mapping.items():
            val = finite(row[j]) if j < len(row) else None
            pt[key] = finite(val * scale) if val is not None else None
        points.append(pt)
    if not points:
        raise ValueError("No observations below the header")
    return points, list(mapping), labels, selected
