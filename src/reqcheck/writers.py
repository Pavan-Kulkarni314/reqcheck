"""Writers for exporting a project to ReqIF, CSV or YAML."""

from __future__ import annotations

import csv
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .model import Project

REQIF_NS = "http://www.omg.org/spec/ReqIF/20110401/reqif.xsd"


def write(project: Project, path: str | Path) -> None:
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".reqif":
        write_reqif(project, path)
    elif suffix == ".csv":
        write_csv(project, path)
    elif suffix in (".yaml", ".yml"):
        write_yaml(project, path)
    else:
        raise ValueError(f"Unsupported output type '{suffix}'. Use .reqif, .csv or .yaml.")


def write_csv(project: Project, path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "type", "text", "derived_from", "verified_by", "verifies", "method"])
        for i in project.items:
            w.writerow([i.id, i.type, i.text, "; ".join(i.derived_from), "; ".join(i.verified_by),
                        "; ".join(i.verifies), i.method])


def write_yaml(project: Project, path: Path) -> None:
    def clean(d):
        return {k: v for k, v in d.items() if v not in ("", [], None)}

    data = {
        "project": project.name,
        "requirements": [clean({"id": i.id, "type": i.type, "text": i.text, "derived_from": i.derived_from,
                                "verified_by": i.verified_by}) for i in project.requirements],
        "tests": [clean({"id": t.id, "method": t.method, "text": t.text, "verifies": t.verifies})
                  for t in project.tests],
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True, width=100)


def write_reqif(project: Project, path: Path) -> None:
    """Writes a ReqIF 1.0 file that requirements tools such as DOORS Next or Polarion can import."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ET.register_namespace("", REQIF_NS)

    def el(parent, tag, **attrs):
        return ET.SubElement(parent, f"{{{REQIF_NS}}}{tag}", {k.replace("_", "-"): v for k, v in attrs.items()})

    def ref(parent, tag, text):
        el(parent, tag).text = text

    root = ET.Element(f"{{{REQIF_NS}}}REQ-IF")
    header = el(el(root, "THE-HEADER"), "REQ-IF-HEADER", IDENTIFIER=f"_{uuid.uuid4()}")
    for tag, text in [("CREATION-TIME", now), ("REQ-IF-TOOL-ID", "reqcheck"), ("REQ-IF-VERSION", "1.0"),
                      ("SOURCE-TOOL-ID", "reqcheck"), ("TITLE", project.name or "Requirements")]:
        el(header, tag).text = text

    content = el(el(root, "CORE-CONTENT"), "REQ-IF-CONTENT")
    el(el(content, "DATATYPES"), "DATATYPE-DEFINITION-STRING",
       IDENTIFIER="DT-STRING", LONG_NAME="String", MAX_LENGTH="4000", LAST_CHANGE=now)

    spec_types = el(content, "SPEC-TYPES")
    object_type = el(spec_types, "SPEC-OBJECT-TYPE", IDENTIFIER="SOT-ITEM", LONG_NAME="Requirement or Test", LAST_CHANGE=now)
    attributes = el(object_type, "SPEC-ATTRIBUTES")
    attribute_defs = [("AD-ID", "ReqIF.ForeignID"), ("AD-TEXT", "ReqIF.Text"),
                      ("AD-TYPE", "Type"), ("AD-METHOD", "Verification Method")]
    for ident, name in attribute_defs:
        ad = el(attributes, "ATTRIBUTE-DEFINITION-STRING", IDENTIFIER=ident, LONG_NAME=name, LAST_CHANGE=now)
        ref(el(ad, "TYPE"), "DATATYPE-DEFINITION-STRING-REF", "DT-STRING")
    el(spec_types, "SPEC-RELATION-TYPE", IDENTIFIER="SRT-DERIVED", LONG_NAME="derived from", LAST_CHANGE=now)
    el(spec_types, "SPEC-RELATION-TYPE", IDENTIFIER="SRT-VERIFIES", LONG_NAME="verifies", LAST_CHANGE=now)
    el(spec_types, "SPECIFICATION-TYPE", IDENTIFIER="ST-SPEC", LONG_NAME="Specification", LAST_CHANGE=now)

    objects = el(content, "SPEC-OBJECTS")
    object_ids = {}
    for item in project.items:
        oid = f"SO-{item.id}"
        object_ids[item.id] = oid
        so = el(objects, "SPEC-OBJECT", IDENTIFIER=oid, LAST_CHANGE=now)
        values = el(so, "VALUES")
        for ident, value in [("AD-ID", item.id), ("AD-TEXT", item.text), ("AD-TYPE", item.type),
                             ("AD-METHOD", item.method)]:
            if not value:
                continue
            av = el(values, "ATTRIBUTE-VALUE-STRING", THE_VALUE=value)
            ref(el(av, "DEFINITION"), "ATTRIBUTE-DEFINITION-STRING-REF", ident)
        ref(el(so, "TYPE"), "SPEC-OBJECT-TYPE-REF", "SOT-ITEM")

    relations = el(content, "SPEC-RELATIONS")
    count = 0

    def relation(type_ref, source, target):
        nonlocal count
        if source not in object_ids or target not in object_ids:
            return
        count += 1
        r = el(relations, "SPEC-RELATION", IDENTIFIER=f"SR-{count}", LAST_CHANGE=now)
        ref(el(r, "TYPE"), "SPEC-RELATION-TYPE-REF", type_ref)
        ref(el(r, "SOURCE"), "SPEC-OBJECT-REF", object_ids[source])
        ref(el(r, "TARGET"), "SPEC-OBJECT-REF", object_ids[target])

    for item in project.items:
        for parent in item.derived_from:
            relation("SRT-DERIVED", item.id, parent)
        for req in item.verifies:
            relation("SRT-VERIFIES", item.id, req)
        for test in item.verified_by:
            relation("SRT-VERIFIES", test, item.id)

    spec = el(el(content, "SPECIFICATIONS"), "SPECIFICATION", IDENTIFIER="SPEC-1",
              LONG_NAME=project.name or "Requirements", LAST_CHANGE=now)
    ref(el(spec, "TYPE"), "SPECIFICATION-TYPE-REF", "ST-SPEC")
    children = el(spec, "CHILDREN")
    for n, item in enumerate(project.items, start=1):
        hierarchy = el(children, "SPEC-HIERARCHY", IDENTIFIER=f"SH-{n}", LAST_CHANGE=now)
        ref(el(hierarchy, "OBJECT"), "SPEC-OBJECT-REF", object_ids[item.id])

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="UTF-8", xml_declaration=True)
