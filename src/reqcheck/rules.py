"""Quality rules for single requirement statements.

The rules are inspired by the INCOSE Guide to Writing Requirements and by the
EARS patterns (Easy Approach to Requirements Syntax). They are heuristics: a
finding means "a reviewer should look at this", not "this is definitely wrong".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable

from .model import Finding, Item

# Word lists ------------------------------------------------------------------
VAGUE_TERMS = [
    "adequate", "appropriate", "approximately", "as required", "as soon as possible",
    "bad", "easy", "easily", "efficient", "fast", "flexible", "good", "high", "intuitive",
    "low", "many", "minimal", "normal", "optimal", "quick", "quickly", "reasonable",
    "reliable", "reliably", "robust", "seamless", "several", "short", "significant",
    "simple", "slow", "some", "state-of-the-art", "sufficient", "typical", "user-friendly",
]
ESCAPE_CLAUSES = [
    "if possible", "as far as possible", "where possible", "where applicable",
    "if necessary", "as appropriate", "to the extent", "unless otherwise", "if practical",
]
OPEN_ENDED = ["etc", "and so on", "including but not limited to", "such as", "and more"]
PLACEHOLDERS = ["tbd", "tbc", "tba", "to be defined", "to be determined", "xxx", "???"]
WEAK_MODALS = ["should", "may", "might", "could", "will", "must", "can"]
ABSOLUTES = ["always", "never", "under all conditions", "in all conditions", "all weather conditions", "100%", "100 %"]
PRONOUNS = ["it", "its", "they", "them", "their", "this", "these", "those"]
COMPARATIVES = ["within", "at least", "at most", "up to", "less than", "more than",
                "greater than", "smaller than", "no more than", "no later than", "below", "above"]

# EARS patterns (checked on requirements that contain "shall") -----------------
EARS_PATTERNS = {
    "ubiquitous": re.compile(r"^the\s.+?\sshall\s", re.I),
    "event-driven": re.compile(r"^when\s.+?,\s*the\s.+?\sshall\s", re.I),
    "state-driven": re.compile(r"^while\s.+?,\s*the\s.+?\sshall\s", re.I),
    "unwanted behaviour": re.compile(r"^if\s.+?,\s*then\s+the\s.+?\sshall\s", re.I),
    "optional feature": re.compile(r"^where\s.+?,\s*the\s.+?\sshall\s", re.I),
}


def _find_terms(text: str, terms: list[str]) -> list[str]:
    found = []
    for term in terms:
        pattern = r"(?<![\w-])" + re.escape(term) + r"(?![\w-])"
        m = re.search(pattern, text, re.I)
        if m:
            found.append(m.group(0))  # as written in the text, e.g. "TBD"
    return found


def ears_pattern(text: str) -> str:
    """Returns the EARS pattern name of a requirement, or "" if none matches."""
    for name, pattern in EARS_PATTERNS.items():
        if pattern.search(text.strip()):
            return name
    return ""


@dataclass
class Rule:
    id: str
    severity: str
    description: str
    check: Callable[[Item], list[str]]  # returns one message per problem
    applies_to: tuple[str, ...] = ("system", "component")


# Rule functions ----------------------------------------------------------------
def _missing_shall(item: Item) -> list[str]:
    if not re.search(r"\bshall\b", item.text, re.I):
        return ["No 'shall' found. A requirement should state one binding obligation with 'shall'."]
    return []


def _multiple_shall(item: Item) -> list[str]:
    count = len(re.findall(r"\bshall\b", item.text, re.I))
    if count > 1:
        return [f"{count} 'shall' statements. Split into separate requirements so each can be verified on its own."]
    return []


def _weak_modal(item: Item) -> list[str]:
    found = _find_terms(item.text, WEAK_MODALS)
    return [f"Uses '{w}' instead of 'shall'." for w in found]


def _vague(item: Item) -> list[str]:
    return [f"Vague term '{t}'. Replace it with a measurable value." for t in _find_terms(item.text, VAGUE_TERMS)]


def _escape(item: Item) -> list[str]:
    return [f"Escape clause '{t}' makes the requirement impossible to fail." for t in _find_terms(item.text, ESCAPE_CLAUSES)]


def _open_ended(item: Item) -> list[str]:
    return [f"Open-ended list ('{t}'). List every case explicitly." for t in _find_terms(item.text, OPEN_ENDED)]


def _placeholder(item: Item) -> list[str]:
    return [f"Placeholder '{t}' left in the text." for t in _find_terms(item.text, PLACEHOLDERS)]


def _and_or(item: Item) -> list[str]:
    if re.search(r"\band\s*/\s*or\b", item.text, re.I):
        return ["'and/or' is ambiguous. State whether both or either is required."]
    return []


def _absolute(item: Item) -> list[str]:
    return [f"Absolute '{t}' cannot be verified completely. State the conditions instead." for t in _find_terms(item.text, ABSOLUTES)]


def _pronoun(item: Item) -> list[str]:
    found = _find_terms(item.text, PRONOUNS)
    return [f"Pronoun '{p}' may be unclear. Repeat the noun it refers to." for p in found]


def _passive(item: Item) -> list[str]:
    m = re.search(r"\bshall\s+(?:not\s+)?be\s+(\w+(?:ed|en))\b", item.text, re.I)
    if m:
        return [f"Passive voice ('shall be {m.group(1)}') hides who is responsible. Name the system or component as the subject."]
    return []


NUMBER_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"}


def _unquantified(item: Item) -> list[str]:
    messages = []
    for word in COMPARATIVES:
        for m in re.finditer(r"(?<![\w-])" + re.escape(word) + r"((?:\s+\S+){1,3})", item.text, re.I):
            following = m.group(1).split()
            # Accept a number within the next three words, e.g. "up to at least 150 m".
            if any(re.match(r"[-+±]?\d", w) or w.lower() in NUMBER_WORDS for w in following):
                continue
            messages.append(f"'{word} {' '.join(following)}' has no number. Add a value with a unit.")
    return messages


def _ears(item: Item) -> list[str]:
    if re.search(r"\bshall\b", item.text, re.I) and not ears_pattern(item.text):
        return ["Does not follow an EARS pattern (The.../When.../While.../If..., then.../Where...)."]
    return []


def _too_long(item: Item) -> list[str]:
    words = len(item.text.split())
    if words > 40:
        return [f"{words} words. Long requirements are hard to review; consider splitting."]
    return []


def _empty_text(item: Item) -> list[str]:
    return [] if item.text.strip() else ["The requirement has no text."]


RULES: list[Rule] = [
    Rule("EMPTY_TEXT", "error", "Requirement text is empty.", _empty_text, ("stakeholder", "system", "component")),
    Rule("MISSING_SHALL", "error", "No 'shall' in a system or component requirement.", _missing_shall),
    Rule("MULTIPLE_SHALL", "warning", "More than one 'shall' (requirement is not singular).", _multiple_shall),
    Rule("WEAK_MODAL", "warning", "Uses should/may/will/must/can instead of shall.", _weak_modal),
    Rule("VAGUE_TERM", "warning", "Contains a vague, unmeasurable word.", _vague),
    Rule("ESCAPE_CLAUSE", "error", "Contains an escape clause such as 'if possible'.", _escape),
    Rule("OPEN_ENDED", "warning", "Contains an open-ended list such as 'etc.'.", _open_ended),
    Rule("PLACEHOLDER", "error", "Contains TBD/TBC or a similar placeholder.", _placeholder),
    Rule("AND_OR", "warning", "Contains 'and/or'.", _and_or),
    Rule("ABSOLUTE", "warning", "Contains an absolute such as 'always' or 'never'.", _absolute),
    Rule("PRONOUN", "info", "Contains a pronoun that may be unclear.", _pronoun),
    Rule("PASSIVE_VOICE", "warning", "Uses passive voice ('shall be ...ed').", _passive),
    Rule("UNQUANTIFIED", "warning", "Comparison word (within, at least, ...) without a number.", _unquantified),
    Rule("NOT_EARS", "info", "Does not follow an EARS sentence pattern.", _ears),
    Rule("TOO_LONG", "info", "More than 40 words.", _too_long),
]


def check_item(item: Item, disabled: set[str] | None = None) -> list[Finding]:
    """Runs every enabled rule that applies to the item's type."""
    disabled = disabled or set()
    findings = []
    for rule in RULES:
        if rule.id in disabled or item.type not in rule.applies_to:
            continue
        for message in rule.check(item):
            findings.append(Finding(rule.id, rule.severity, item.id, message, item.text))
    return findings
