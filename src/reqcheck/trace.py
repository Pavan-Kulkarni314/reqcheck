"""Traceability checks: links between needs, requirements and tests."""

from __future__ import annotations

from dataclasses import dataclass, field

from .model import Finding, Item, Project

# Which item types may be the parent of which (derived_from targets).
ALLOWED_PARENTS = {
    "system": {"stakeholder"},
    "component": {"system", "component"},
}


@dataclass
class TraceRow:
    item: Item
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    tests: list[str] = field(default_factory=list)


@dataclass
class Coverage:
    """Share of items that have the required links (0-100 %)."""

    needs_with_requirements: float
    requirements_with_parent: float
    requirements_verified: float

    @staticmethod
    def percent(part: int, whole: int) -> float:
        return 100.0 if whole == 0 else round(100.0 * part / whole, 1)


@dataclass
class TraceResult:
    findings: list[Finding]
    rows: list[TraceRow]
    coverage: Coverage


def analyse(project: Project) -> TraceResult:
    findings: list[Finding] = []
    index: dict[str, Item] = {}

    for item in project.items:
        if item.id in index:
            findings.append(Finding("DUPLICATE_ID", "error", item.id,
                                    f"ID used more than once ({index[item.id].source} and {item.source})."))
        else:
            index[item.id] = item

    rows = {item.id: TraceRow(item) for item in index.values() if item.is_requirement}

    # Derivation links (child -> parent)
    for item in index.values():
        for parent_id in item.derived_from:
            parent = index.get(parent_id)
            if parent is None:
                findings.append(Finding("DANGLING_LINK", "error", item.id,
                                        f"'derived_from' points to unknown ID '{parent_id}'."))
                continue
            allowed = ALLOWED_PARENTS.get(item.type, set())
            if parent.type not in allowed:
                findings.append(Finding("WRONG_LINK_TYPE", "warning", item.id,
                                        f"A {item.type} requirement should not derive from a {parent.type} item ('{parent_id}')."))
            if item.id in rows:
                rows[item.id].parents.append(parent_id)
            if parent_id in rows:
                rows[parent_id].children.append(item.id)

    # Verification links: from requirements (verified_by) and from tests (verifies)
    pairs: set[tuple[str, str]] = set()
    for item in index.values():
        if item.is_requirement:
            for test_id in item.verified_by:
                test = index.get(test_id)
                if test is None:
                    findings.append(Finding("DANGLING_LINK", "error", item.id,
                                            f"'verified_by' points to unknown ID '{test_id}'."))
                elif not test.is_test:
                    findings.append(Finding("WRONG_LINK_TYPE", "warning", item.id,
                                            f"'verified_by' points to '{test_id}', which is not a test."))
                else:
                    pairs.add((item.id, test_id))
        if item.is_test:
            for req_id in item.verifies:
                req = index.get(req_id)
                if req is None:
                    findings.append(Finding("DANGLING_LINK", "error", item.id,
                                            f"'verifies' points to unknown ID '{req_id}'."))
                elif not req.is_requirement:
                    findings.append(Finding("WRONG_LINK_TYPE", "warning", item.id,
                                            f"'verifies' points to '{req_id}', which is not a requirement."))
                else:
                    pairs.add((req_id, item.id))

    for req_id, test_id in sorted(pairs):
        rows[req_id].tests.append(test_id)

    # Coverage gaps
    for row in rows.values():
        item = row.item
        if item.type in ("system", "component") and not row.parents:
            findings.append(Finding("NO_PARENT", "error", item.id,
                                    "Not derived from any stakeholder need or higher-level requirement."))
        if item.type == "stakeholder" and not row.children:
            findings.append(Finding("NO_CHILD", "warning", item.id,
                                    "No system requirement is derived from this stakeholder need."))
        if item.type in ("system", "component") and not row.tests:
            severity = "error" if item.type == "system" else "warning"
            findings.append(Finding("NOT_VERIFIED", severity, item.id, "No test case verifies this requirement."))

    verified_tests = {test_id for _, test_id in pairs}
    for test in (i for i in index.values() if i.is_test):
        if test.id not in verified_tests:
            findings.append(Finding("ORPHAN_TEST", "warning", test.id, "This test case does not verify any requirement."))

    needs = [r for r in rows.values() if r.item.type == "stakeholder"]
    reqs = [r for r in rows.values() if r.item.type in ("system", "component")]
    coverage = Coverage(
        needs_with_requirements=Coverage.percent(sum(1 for r in needs if r.children), len(needs)),
        requirements_with_parent=Coverage.percent(sum(1 for r in reqs if r.parents), len(reqs)),
        requirements_verified=Coverage.percent(sum(1 for r in reqs if r.tests), len(reqs)),
    )
    return TraceResult(findings, list(rows.values()), coverage)
