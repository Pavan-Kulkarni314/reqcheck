"""Data model: requirements, tests and findings."""

from __future__ import annotations

from dataclasses import dataclass, field

REQUIREMENT_TYPES = ("stakeholder", "system", "component")
TEST_TYPE = "test"
ALL_TYPES = REQUIREMENT_TYPES + (TEST_TYPE,)

SEVERITIES = ("error", "warning", "info")

# Used when an input file has no type column: the ID prefix decides the type.
DEFAULT_PREFIX_TYPES = {
    "STK": "stakeholder",
    "SYS": "system",
    "CMP": "component",
    "TC": "test",
}


@dataclass
class Item:
    """A requirement (stakeholder, system or component) or a test case."""

    id: str
    type: str
    text: str = ""
    derived_from: list[str] = field(default_factory=list)
    verified_by: list[str] = field(default_factory=list)  # on requirements
    verifies: list[str] = field(default_factory=list)  # on tests
    method: str = ""  # verification method, for tests
    source: str = ""  # where the item came from, e.g. "file.csv:12"

    @property
    def is_requirement(self) -> bool:
        return self.type in REQUIREMENT_TYPES

    @property
    def is_test(self) -> bool:
        return self.type == TEST_TYPE


@dataclass
class Finding:
    """One problem found by a quality rule or a traceability check."""

    rule: str
    severity: str
    item_id: str
    message: str
    excerpt: str = ""


@dataclass
class Project:
    """All items loaded from one input file."""

    items: list[Item]
    name: str = ""

    def by_id(self) -> dict[str, Item]:
        return {item.id: item for item in self.items}

    @property
    def requirements(self) -> list[Item]:
        return [item for item in self.items if item.is_requirement]

    @property
    def tests(self) -> list[Item]:
        return [item for item in self.items if item.is_test]

    def of_type(self, item_type: str) -> list[Item]:
        return [item for item in self.items if item.type == item_type]


def infer_type(item_id: str, prefixes: dict[str, str] | None = None) -> str:
    """Returns the item type from its ID prefix (e.g. "SYS-01" -> "system"), or "" if unknown."""
    prefixes = prefixes or DEFAULT_PREFIX_TYPES
    head = item_id.split("-")[0].upper()
    return prefixes.get(head, "")
