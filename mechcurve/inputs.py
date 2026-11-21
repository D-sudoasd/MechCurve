"""Discover records and decode physical channels without modifying acquisition files."""

from collections import Counter
import json
import hashlib
import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .channels import COLUMNS as COLUMNS
from .tableio import TABLE_SUFFIXES, read_table, workbook


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
    points, channels, _, _ = read_table(path)
    return points, channels


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


def acquisition_notes(scope, notes):
    if notes is not None:
        return notes
    config = (
        scope.with_name(scope.name + ".mechcurve.json")
        if scope.is_file()
        else scope / "mechcurve.json"
    )
    legacy = scope.with_name(scope.name + "_MechCurve") / "实验备注.json"
    selected = next((p for p in (config, legacy) if p.is_file()), None)
    return json.loads(selected.read_text(encoding="utf-8-sig")) if selected else {}


def output_folder(path):
    if path.name.endswith("_MechCurve") and path.name != "_MechCurve":
        sibling = path.with_name(path.name.removesuffix("_MechCurve"))
        if sibling.exists():
            return True
    return path.name.startswith("run-") and (path / "run.json").is_file()


def locate_inputs(requested):
    root = Path(requested).resolve(strict=True)
    if any(output_folder(path) for path in (root, *root.parents)):
        raise ValueError("Select a source acquisition or experimental directory")
    if root.is_file():
        if root.suffix.lower() not in TABLE_SUFFIXES:
            raise ValueError(f"Unsupported acquisition file: {root.suffix}")
        files = [root]
        if root.parent.name.endswith(".is_tcyclic_RawData") and re.fullmatch(
            r"Specimen_RawData_\d+", root.stem, re.I
        ):
            folder = root.parent.parent
            xml = folder / root.parent.name.removesuffix("_RawData")
            files.extend(
                p for p in (xml, xml.with_suffix(".id_tcyclic")) if p.is_file()
            )
            return folder, files
        return root.parent, files
    if not root.is_dir():
        raise ValueError("Expected an acquisition file or directory")

    def raise_walk_error(exc):
        raise exc

    files = []
    for directory, subdirs, names in os.walk(root, onerror=raise_walk_error):
        folder = Path(directory)
        subdirs[:] = [d for d in subdirs if not output_folder(folder / d)]
        files.extend(
            folder / name
            for name in names
            if not name.startswith("~$")
            and Path(name).suffix.lower()
            in TABLE_SUFFIXES | {".id_tcyclic", ".is_tcyclic"}
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
        if csv_path.suffix.lower() not in TABLE_SUFFIXES:
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
        desc = {
            "record": relative,
            "path": csv_path,
            "xml": xml if xml and xml.exists() else None,
            "binary": binary if binary and binary.exists() else None,
            "index": idx,
            "group": group,
            "sample": identity,
        }
        if csv_path.suffix.lower() != ".xlsx":
            records.append(desc)
            continue
        try:
            book = workbook(csv_path)
            try:
                sheets = [
                    s.title for s in book.worksheets if s.sheet_state == "visible"
                ]
            finally:
                book.close()
            if not sheets:
                raise ValueError("Workbook has no visible worksheets")
        except ValueError as exc:
            records.append({**desc, "input_error": str(exc)})
        else:
            for sheet in sheets:
                records.append(
                    {
                        **desc,
                        "record": relative + "#" + sheet,
                        "sheet": sheet,
                        "sample": identity + " · " + sheet,
                    }
                )
    # A shared stem in different formats is not proof of specimen identity.
    counts = Counter(r["sample"] for r in records)
    for r in records:
        if counts[r["sample"]] > 1:
            r["sample"] = r["record"]
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
