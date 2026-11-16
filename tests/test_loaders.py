from pathlib import Path

import pytest

from reqcheck.loaders import LoadError, load
from reqcheck.writers import write

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_yaml_example_loads():
    p = load(EXAMPLES / "acc_requirements.yaml")
    assert p.name == "Adaptive Cruise Control (ACC)"
    assert len(p.of_type("stakeholder")) == 6
    assert len(p.of_type("system")) == 12
    assert len(p.of_type("component")) == 6
    assert len(p.tests) == 14
    sys02 = p.by_id()["SYS-02"]
    assert sys02.derived_from == ["STK-01"]
    assert sys02.text.startswith("While no vehicle is ahead")


def test_csv_example_loads_lists_and_types():
    p = load(EXAMPLES / "draft_lka_requirements.csv")
    items = p.by_id()
    assert items["SYS-101"].verified_by == ["TC-101"]
    assert items["TC-106"].method == "demonstration"
    assert items["STK-10"].type == "stakeholder"


def test_type_is_inferred_from_prefix(tmp_path):
    f = tmp_path / "r.csv"
    f.write_text("id,text,derived_from\nSTK-1,need,\nSYS-1,The system shall work.,STK-1\nTC-1,test,\n")
    p = load(f)
    assert [i.type for i in p.items] == ["stakeholder", "system", "test"]


def test_unknown_type_is_an_error(tmp_path):
    f = tmp_path / "r.csv"
    f.write_text("id,type,text\nX-1,wish,text\n")
    with pytest.raises(LoadError):
        load(f)


def test_unsupported_suffix(tmp_path):
    f = tmp_path / "r.docx"
    f.write_text("")
    with pytest.raises(LoadError):
        load(f)


@pytest.mark.parametrize("suffix", [".reqif", ".csv", ".yaml"])
def test_round_trip_keeps_items_and_links(tmp_path, suffix):
    original = load(EXAMPLES / "acc_requirements.yaml")
    out = tmp_path / f"acc{suffix}"
    write(original, out)
    again = load(out)

    def links(project):
        return {
            (i.id, i.type, i.text, tuple(sorted(i.derived_from)), tuple(sorted(i.verifies + i.verified_by)))
            for i in project.items
        }

    assert links(again) == links(original)


def test_reqif_with_xhtml_text_and_tool_specific_names(tmp_path):
    reqif = """<?xml version="1.0" encoding="UTF-8"?>
<REQ-IF xmlns="http://www.omg.org/spec/ReqIF/20110401/reqif.xsd" xmlns:xhtml="http://www.w3.org/1999/xhtml">
 <CORE-CONTENT><REQ-IF-CONTENT>
  <SPEC-TYPES>
   <SPEC-OBJECT-TYPE IDENTIFIER="T1" LAST-CHANGE="2026-01-01T00:00:00Z"><SPEC-ATTRIBUTES>
     <ATTRIBUTE-DEFINITION-STRING IDENTIFIER="A-ID" LONG-NAME="Object Identifier" LAST-CHANGE="2026-01-01T00:00:00Z"/>
     <ATTRIBUTE-DEFINITION-XHTML IDENTIFIER="A-TXT" LONG-NAME="Object Text" LAST-CHANGE="2026-01-01T00:00:00Z"/>
   </SPEC-ATTRIBUTES></SPEC-OBJECT-TYPE>
   <SPEC-RELATION-TYPE IDENTIFIER="R1" LONG-NAME="Refines" LAST-CHANGE="2026-01-01T00:00:00Z"/>
  </SPEC-TYPES>
  <SPEC-OBJECTS>
   <SPEC-OBJECT IDENTIFIER="o1" LAST-CHANGE="2026-01-01T00:00:00Z"><VALUES>
     <ATTRIBUTE-VALUE-STRING THE-VALUE="STK-7"><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>A-ID</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>
     <ATTRIBUTE-VALUE-XHTML><DEFINITION><ATTRIBUTE-DEFINITION-XHTML-REF>A-TXT</ATTRIBUTE-DEFINITION-XHTML-REF></DEFINITION>
       <THE-VALUE><xhtml:div>The driver needs <xhtml:b>help</xhtml:b>.</xhtml:div></THE-VALUE></ATTRIBUTE-VALUE-XHTML>
   </VALUES><TYPE><SPEC-OBJECT-TYPE-REF>T1</SPEC-OBJECT-TYPE-REF></TYPE></SPEC-OBJECT>
   <SPEC-OBJECT IDENTIFIER="o2" LAST-CHANGE="2026-01-01T00:00:00Z"><VALUES>
     <ATTRIBUTE-VALUE-STRING THE-VALUE="SYS-7"><DEFINITION><ATTRIBUTE-DEFINITION-STRING-REF>A-ID</ATTRIBUTE-DEFINITION-STRING-REF></DEFINITION></ATTRIBUTE-VALUE-STRING>
   </VALUES><TYPE><SPEC-OBJECT-TYPE-REF>T1</SPEC-OBJECT-TYPE-REF></TYPE></SPEC-OBJECT>
  </SPEC-OBJECTS>
  <SPEC-RELATIONS>
   <SPEC-RELATION IDENTIFIER="r1" LAST-CHANGE="2026-01-01T00:00:00Z"><TYPE><SPEC-RELATION-TYPE-REF>R1</SPEC-RELATION-TYPE-REF></TYPE>
     <SOURCE><SPEC-OBJECT-REF>o2</SPEC-OBJECT-REF></SOURCE><TARGET><SPEC-OBJECT-REF>o1</SPEC-OBJECT-REF></TARGET></SPEC-RELATION>
  </SPEC-RELATIONS>
 </REQ-IF-CONTENT></CORE-CONTENT>
</REQ-IF>"""
    f = tmp_path / "tool_export.reqif"
    f.write_text(reqif, encoding="utf-8")
    items = load(f).by_id()
    assert items["STK-7"].text == "The driver needs help."
    assert items["STK-7"].type == "stakeholder"
    assert items["SYS-7"].derived_from == ["STK-7"]
