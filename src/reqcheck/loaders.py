"""Readers for YAML, CSV and ReqIF requirement files."""

from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from .model import ALL_TYPES, Item, Project, infer_type


class LoadError(Exception):
    """Raised when an input file cannot be read or is incomplete."""


def load(path: str | Path) -> Project:
    """Loads a project from a .yaml/.yml, .csv or .reqif file."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        project = load_yaml(path)
    elif suffix == ".csv":
        project = load_csv(path)
    elif suffix == ".reqif":
        project = load_reqif(path)
    else:
        raise LoadError(f"Unsupported file type '{suffix}'. Use .yaml, .csv or .reqif.")
    project.name = project.name or path.stem
    return project


def _as_list(value) -> list[str]:
    """Turns "A; B", "A, B", ["A", "B"] or None into ["A", "B"]."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in re.split(r"[;,]", str(value)) if part.strip()]


def _make_item(raw: dict, source: str, default_type: str = "") -> Item:
    item_id = str(raw.get("id") or "").strip()
    if not item_id:
        raise LoadError(f"{source}: item without an 'id'.")
    item_type = str(raw.get("type") or default_type or infer_type(item_id)).strip().lower()
    if item_type not in ALL_TYPES:
        raise LoadError(
            f"{source}: item '{item_id}' has unknown type '{item_type}'. "
            f"Use one of: {', '.join(ALL_TYPES)}."
        )
    return Item(
        id=item_id,
        type=item_type,
        text=" ".join(str(raw.get("text") or raw.get("title") or "").split()),
        derived_from=_as_list(raw.get("derived_from")),
        verified_by=_as_list(raw.get("verified_by")),
        verifies=_as_list(raw.get("verifies")),
        method=str(raw.get("method") or "").strip().lower(),
        source=source,
    )


def load_yaml(path: Path) -> Project:
    """Reads a YAML file with a 'requirements' list and an optional 'tests' list."""
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise LoadError(f"{path}: expected a mapping with 'requirements' and 'tests'.")
    items = []
    for i, raw in enumerate(data.get("requirements") or [], start=1):
        items.append(_make_item(raw, f"{path.name}:requirements[{i}]"))
    for i, raw in enumerate(data.get("tests") or [], start=1):
        items.append(_make_item(raw, f"{path.name}:tests[{i}]", default_type="test"))
    return Project(items=items, name=str(data.get("project") or ""))


def load_csv(path: Path) -> Project:
    """Reads a CSV file with columns id, type, text, derived_from, verified_by, verifies, method."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        if not reader.fieldnames or "id" not in [n.strip().lower() for n in reader.fieldnames]:
            raise LoadError(f"{path}: the CSV file needs an 'id' column.")
        items = []
        for line_no, row in enumerate(reader, start=2):
            row = {(k or "").strip().lower(): v for k, v in row.items()}
            if not any((v or "").strip() for v in row.values()):
                continue
            items.append(_make_item(row, f"{path.name}:{line_no}"))
    return Project(items=items)


# --------------------------------------------------------------------------
# ReqIF
# --------------------------------------------------------------------------
_FIELD_NAMES = {
    "id": {"reqif.foreignid", "id", "identifier", "req id", "object identifier", "foreignid"},
    "text": {"reqif.text", "text", "object text", "description", "reqif.description"},
    "type": {"type", "category", "reqif.category", "requirement type"},
    "method": {"verification method", "verificationmethod", "method"},
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(elem: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in elem.iter() if _local(c.tag) == name]


def _first_text(elem: ET.Element, name: str) -> str:
    for c in _children(elem, name):
        if c.text and c.text.strip():
            return c.text.strip()
    return ""


def load_reqif(path: Path) -> Project:
    """Reads requirements, tests and their relations from a ReqIF 1.x file.

    Attribute names are matched loosely (e.g. "ReqIF.ForeignID" or "ID" for the
    identifier) so that exports from different tools can be read. Relations whose
    type name contains "deriv", "refine" or "trace" become derived_from links
    (source = child, target = parent); names containing "verif" become verifies
    links (source = test, target = requirement).
    """
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        raise LoadError(f"{path}: not valid XML ({e}).") from e

    attr_names = {}
    for elem in root.iter():
        if _local(elem.tag).startswith("ATTRIBUTE-DEFINITION-"):
            attr_names[elem.get("IDENTIFIER")] = (elem.get("LONG-NAME") or "").strip().lower()

    relation_type_names = {
        e.get("IDENTIFIER"): (e.get("LONG-NAME") or "").lower()
        for e in _children(root, "SPEC-RELATION-TYPE")
    }

    objects: dict[str, dict] = {}
    for so in _children(root, "SPEC-OBJECT"):
        values = {}
        for value in so.iter():
            tag = _local(value.tag)
            if not tag.startswith("ATTRIBUTE-VALUE-"):
                continue
            definition = ""
            for ref in value.iter():
                if _local(ref.tag).startswith("ATTRIBUTE-DEFINITION-") and _local(ref.tag).endswith("-REF"):
                    definition = (ref.text or "").strip()
            name = attr_names.get(definition, "")
            if tag == "ATTRIBUTE-VALUE-XHTML":
                the_value = [c for c in value if _local(c.tag) == "THE-VALUE"]
                text = " ".join("".join(the_value[0].itertext()).split()) if the_value else ""
            else:
                text = value.get("THE-VALUE", "")
            for field_name, aliases in _FIELD_NAMES.items():
                if name in aliases:
                    values[field_name] = text
        objects[so.get("IDENTIFIER")] = values

    items_by_ref: dict[str, Item] = {}
    for ref, values in objects.items():
        values.setdefault("id", ref)
        items_by_ref[ref] = _make_item(values, f"{path.name}:{ref}")

    for rel in _children(root, "SPEC-RELATION"):
        type_ref = _first_text(rel, "SPEC-RELATION-TYPE-REF")
        type_name = relation_type_names.get(type_ref, "")
        source = next((_first_text(s, "SPEC-OBJECT-REF") for s in _children(rel, "SOURCE")), "")
        target = next((_first_text(t, "SPEC-OBJECT-REF") for t in _children(rel, "TARGET")), "")
        if source not in items_by_ref or target not in items_by_ref:
            continue
        child, parent = items_by_ref[source], items_by_ref[target]
        if "verif" in type_name:
            child.verifies.append(parent.id)
        elif any(word in type_name for word in ("deriv", "refine", "trace")):
            child.derived_from.append(parent.id)

    title = _first_text(root, "TITLE")
    return Project(items=list(items_by_ref.values()), name=title)
