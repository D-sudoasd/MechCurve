"""Discover records and decode physical channels without modifying acquisition files."""

import csv
import hashlib
import io
import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

COLUMNS = {
    "time_s": (
        ("time", "时间", "elapsed time"),
        {"s": 1, "sec": 1, "ms": 0.001, "min": 60},
    ),
    "extension_mm": (
        ("extension", "displacement", "位移", "横梁位移"),
        {"mm": 1, "um": 0.001, "µm": 0.001, "m": 1000},
    ),
    "force_N": (("load", "force", "力", "载荷", "加载力"), {"n": 1, "kn": 1000}),
    "strain_pct": (
        ("tensile strain", "engineering strain", "strain", "应变", "工程应变"),
        {"%": 1, "％": 1, "1": 100, "-": 100, "mm/mm": 100},
    ),
    "stress_MPa": (
        ("tensile stress", "engineering stress", "stress", "应力", "工程应力"),
        {"mpa": 1, "n/mm2": 1, "n/mm²": 1, "gpa": 1000, "kpa": 0.001, "pa": 1e-6},
    ),
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def number(text):
    try:
        value = float(text)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def read_points(path):
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "gb18030"):
        try:
            text = raw.decode(encoding)
            if "\x00" in text or not any(
                x in text.splitlines()[0] for x in (",", ";", "\t")
            ):
                continue
            break
        except (UnicodeError, IndexError):
            continue
    else:
        raise ValueError("无法识别表头、编码或分隔符")
    sep = max((",", ";", "\t"), key=text.splitlines()[0].count)
    reader = csv.reader(io.StringIO(text), delimiter=sep)
    rows = [
        (reader.line_num, row) for row in reader if any(cell.strip() for cell in row)
    ]
    if len(rows) < 2:
        raise ValueError("采样记录为空")
    header = rows[0][1]
    unit_line = all(
        not cell.strip()
        or cell.strip().startswith(("(", "["))
        or cell.strip().lower() in {u for _, units in COLUMNS.values() for u in units}
        for cell in rows[1][1]
    ) and any(number(cell) is None for cell in rows[1][1])
    mapping = {}
    for i, name in enumerate(header):
        parts = re.fullmatch(r"(.*?)\s*[\[(]([^\])]+)[\])]\s*", name.strip())
        label = (parts[1] if parts else name).strip().lower()
        units_row = rows[1][1]
        unit = (
            (
                parts[2]
                if parts
                else units_row[i]
                if unit_line and i < len(units_row)
                else ""
            )
            .strip(" ()[]")
            .lower()
        )
        for key, (aliases, units) in COLUMNS.items():
            if label == key.lower():
                unit = unit or next(iter(units))
            elif label not in aliases:
                continue
            if unit not in units or key in mapping:
                raise ValueError(f"通道单位无法识别或存在重名列 {name} [{unit}]")
            mapping[key] = (i, units[unit])
    if "time_s" not in mapping or not {"force_N", "stress_MPa"} & mapping.keys():
        raise ValueError("需要有单位的时间与力或应力通道")
    points = []
    for row_number, row in rows[2 if unit_line else 1 :]:
        point = dict.fromkeys(COLUMNS)
        point["source_row"] = row_number
        for key, (idx, scale) in mapping.items():
            value = number(row[idx]) if idx < len(row) else None
            if value is not None:
                point[key] = value * scale
        points.append(point)
    if not points:
        raise ValueError("无采样行")
    return points, list(mapping)


def waveform(node):
    def val(field, leaf="ValueItem"):
        return node.findtext(f"WAVEFORM_{field}/Value/{leaf}")

    unit = val("MAX_VALUE", "UnitType")
    axis = {"4": "strain_pct", "46": "stress_MPa", "27": "force_N"}.get(unit)
    target = number(val("MAX_VALUE"))
    if axis is None or target is None:
        return None
    return {
        "axis": axis,
        "target": target * (100 if unit == "4" else 1),
        "lower_MPa": number(val("MIN_VALUE"))
        if val("MIN_VALUE", "UnitType") == "46"
        else None,
    }


def metadata(xml, idx):
    if not xml:
        return {}
    root = ET.parse(xml).getroot()
    specimen = root.find(f"Specimens/Specimen[@index='{idx}']")
    if specimen is None:
        return {"metadata_warning": "原始序号缺少对应 XML 试样条目"}
    props = specimen.find("SpecimenProperties")
    if props is None:
        return {"metadata_warning": "缺少试样属性"}
    diameter = number(props.findtext("Diameter/Value"))
    # In the observed Bluehill export Geometry=1 selects a circular section.
    area = (
        math.pi * diameter**2 / 4
        if (
            props.findtext("Geometry") == "1"
            and props.findtext("Diameter/Units") == "23"
            and diameter
            and diameter > 0
        )
        else None
    )
    method = list(root.find("Method").iter("WAVEFORM"))
    spec_waves = list(specimen.iter("WAVEFORM"))
    steps = []
    for i, m in enumerate(method):
        name = m.findtext("WAVEFORM_STEP_NAME/Value/ValueItem") or ""
        observed = waveform(spec_waves[i]) if i < len(spec_waves) else None
        step = observed or waveform(m)
        if step:
            step["name"] = name
            steps.append(step)
    return {
        "specimen_index": idx,
        "specimen_guid": props.findtext("UniqueIdentifier"),
        "acquisition_time": number(props.findtext("StartDate")),
        "diameter_mm": diameter if area else None,
        "area_mm2": area,
        "steps": steps,
        "instrument_break_valid": props.findtext("ControllerLoadAtBreakValid")
        == "true",
        "instrument_break_load": number(props.findtext("ControllerLoadAtBreak/Value"))
        if props.findtext("ControllerLoadAtBreakValid") == "true"
        and props.findtext("ControllerLoadAtBreak/Units") == "27"
        else None,
    }


def output_folder(path):
    if path.name.endswith("_MechCurve") and path.name != "_MechCurve":
        sibling = path.with_name(path.name.removesuffix("_MechCurve"))
        if sibling.is_dir():
            return True
    return path.name.startswith("run-") and (path / "run.json").is_file()


def locate_inputs(requested):
    root = Path(requested).resolve(strict=True)
    if not root.is_dir() or any(output_folder(path) for path in (root, *root.parents)):
        raise ValueError("请选择实验目录或其上层目录")

    def raise_walk_error(exc):
        raise exc

    files = []
    for directory, subdirs, names in os.walk(root, onerror=raise_walk_error):
        folder = Path(directory)
        subdirs[:] = [d for d in subdirs if not output_folder(folder / d)]
        files.extend(
            folder / name
            for name in names
            if Path(name).suffix.lower() in {".csv", ".id_tcyclic", ".is_tcyclic"}
        )
    branches = {p.relative_to(root).parts[0] for p in files}
    if len(branches) == 1:
        child = root / branches.pop()
        if child.is_dir() and (
            child.with_name(child.name + "_MechCurve").is_dir()
            or re.fullmatch(r"\d{8}", child.name)
            and any(p.suffix == ".is_tcyclic" for p in files)
        ):
            root = child
    return root, sorted(files, key=lambda p: p.as_posix().casefold())


def discover(folder, files=None):
    if files is None:
        folder, files = locate_inputs(folder)
    records = []
    for csv_path in files:
        if csv_path.suffix.lower() != ".csv":
            continue
        relative = csv_path.relative_to(folder).as_posix()
        match = re.fullmatch(r"Specimen_RawData_(\d+)", csv_path.stem, re.I)
        bluehill = match and csv_path.parent.name.endswith(".is_tcyclic_RawData")
        xml = binary = None
        group = csv_path.stem
        idx = None
        if bluehill:
            idx = int(match[1])
            group = csv_path.parent.name.removesuffix(".is_tcyclic_RawData")
            xml = csv_path.parent.parent / (group + ".is_tcyclic")
            binary = xml.with_suffix(".id_tcyclic")
        prefix = (
            csv_path.parent.parent.relative_to(folder)
            if bluehill
            else csv_path.parent.relative_to(folder)
        )
        identity = (prefix / (f"{group} · S{idx}" if bluehill else group)).as_posix()
        records.append(
            {
                "record": relative,
                "path": csv_path,
                "xml": xml if xml and xml.exists() else None,
                "binary": binary if binary and binary.exists() else None,
                "index": idx,
                "group": group,
                "sample": identity,
            }
        )
    return records


def link_continuations(records):
    for current in records:
        name = current["group"]
        if not re.search(r"[（(].*(同一|相同)样品.*[)）]", name):
            continue
        stem = re.split("[（(]", name)[0]
        matches = [
            other
            for other in records
            if other is not current
            and other["path"].parent.parent == current["path"].parent.parent
            and other["index"] == current["index"]
            and re.fullmatch(re.escape(stem) + r"\d*", other["group"])
        ]
        if len(matches) == 1:
            current["sample"] = matches[0]["sample"]
            current["continuation"] = True
