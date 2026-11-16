from reqcheck.model import Item, Project
from reqcheck.trace import analyse


def project(*items: Item) -> Project:
    return Project(items=list(items))


def rules(result) -> set[tuple[str, str]]:
    return {(f.rule, f.item_id) for f in result.findings}


STK = Item("STK-1", "stakeholder", "The driver needs a set speed.")
SYS = Item("SYS-1", "system", "The ACC system shall hold the set speed.", derived_from=["STK-1"])
TC = Item("TC-1", "test", "Drive at 100 km/h.", verifies=["SYS-1"])


def test_complete_chain_has_no_findings_and_full_coverage():
    result = analyse(project(STK, SYS, TC))
    assert result.findings == []
    c = result.coverage
    assert (c.needs_with_requirements, c.requirements_with_parent, c.requirements_verified) == (100.0, 100.0, 100.0)


def test_verified_by_on_requirement_counts_like_verifies_on_test():
    sys = Item("SYS-1", "system", "x", derived_from=["STK-1"], verified_by=["TC-1"])
    tc = Item("TC-1", "test", "y")
    result = analyse(project(STK, sys, tc))
    assert result.findings == []
    assert result.rows[1].tests == ["TC-1"]


def test_missing_links_are_reported():
    lonely_sys = Item("SYS-2", "system", "The ACC system shall beep.")
    lonely_need = Item("STK-2", "stakeholder", "The driver needs coffee.")
    orphan_test = Item("TC-2", "test", "Do something.")
    result = analyse(project(STK, SYS, TC, lonely_sys, lonely_need, orphan_test))
    assert {("NO_PARENT", "SYS-2"), ("NOT_VERIFIED", "SYS-2"),
            ("NO_CHILD", "STK-2"), ("ORPHAN_TEST", "TC-2")} <= rules(result)
    assert result.coverage.requirements_verified == 50.0


def test_dangling_and_duplicate_ids_are_errors():
    bad = Item("SYS-1", "system", "dup", derived_from=["STK-99"])
    result = analyse(project(STK, SYS, TC, bad))
    found = {(f.rule, f.severity) for f in result.findings}
    assert ("DUPLICATE_ID", "error") in found


def test_dangling_link():
    sys = Item("SYS-2", "system", "x", derived_from=["STK-99"], verified_by=["TC-99"])
    result = analyse(project(STK, SYS, TC, sys))
    assert sum(1 for f in result.findings if f.rule == "DANGLING_LINK") == 2


def test_wrong_link_type():
    cmp = Item("CMP-1", "component", "x", derived_from=["STK-1"], verified_by=["TC-1"])
    result = analyse(project(STK, SYS, TC, cmp))
    assert ("WRONG_LINK_TYPE", "CMP-1") in rules(result)


def test_unverified_component_is_only_a_warning():
    cmp = Item("CMP-1", "component", "x", derived_from=["SYS-1"])
    result = analyse(project(STK, SYS, TC, cmp))
    severities = {f.severity for f in result.findings if f.item_id == "CMP-1"}
    assert severities == {"warning"}
