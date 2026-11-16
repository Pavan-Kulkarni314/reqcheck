import pytest

from reqcheck.model import Item
from reqcheck.rules import check_item, ears_pattern


def rules_for(text: str, item_type: str = "system") -> set[str]:
    return {f.rule for f in check_item(Item(id="SYS-1", type=item_type, text=text))}


GOOD = "The ACC system shall not request a vehicle deceleration greater than 3.5 m/s²."


def test_good_requirement_has_no_findings():
    assert rules_for(GOOD) == set()


@pytest.mark.parametrize(
    "text, rule",
    [
        ("The system should keep the vehicle in the lane.", "MISSING_SHALL"),
        ("The system should keep the vehicle in the lane.", "WEAK_MODAL"),
        ("The LKA system shall display the status and shall play a sound.", "MULTIPLE_SHALL"),
        ("The LKA system shall detect lane markings quickly.", "VAGUE_TERM"),
        ("If possible, the LKA system shall switch off.", "ESCAPE_CLAUSE"),
        ("The LKA system shall work in rain, snow, fog etc.", "OPEN_ENDED"),
        ("The LKA system shall limit the torque to TBD Nm.", "PLACEHOLDER"),
        ("The LKA system shall warn the driver and/or steer.", "AND_OR"),
        ("The LKA system shall always detect the lane.", "ABSOLUTE"),
        ("The steering torque shall be limited to 3 Nm.", "PASSIVE_VOICE"),
        ("The LKA system shall react within a short time.", "UNQUANTIFIED"),
        ("The LKA system shall react after it detects a departure.", "PRONOUN"),
        ("Lane departures shall trigger a warning tone of 2 s.", "NOT_EARS"),
        ("The system shall " + "do one more thing " * 10 + "now.", "TOO_LONG"),
        ("", "EMPTY_TEXT"),
    ],
)
def test_rule_detects_problem(text, rule):
    assert rule in rules_for(text)


def test_number_within_three_words_is_accepted():
    assert "UNQUANTIFIED" not in rules_for("The front radar shall detect vehicles up to at least 150 m.")


def test_vague_word_inside_other_word_is_not_flagged():
    # "slowest" contains "slow" but is a different word
    assert "VAGUE_TERM" not in rules_for("The ACC system shall follow the slowest vehicle ahead within 0.2 s.")


def test_stakeholder_needs_skip_shall_rules():
    assert rules_for("The driver needs a smooth ride.", item_type="stakeholder") == set()


def test_tests_are_not_checked():
    assert rules_for("Drive quickly and check etc.", item_type="test") == set()


def test_disabled_rule_is_skipped():
    item = Item(id="SYS-1", type="system", text="The system shall react quickly.")
    assert "VAGUE_TERM" not in {f.rule for f in check_item(item, disabled={"VAGUE_TERM"})}


@pytest.mark.parametrize(
    "text, pattern",
    [
        ("The ACC system shall offer 3 time gaps.", "ubiquitous"),
        ("When the driver presses the brake pedal, the ACC system shall switch to standby within 100 ms.", "event-driven"),
        ("While the accelerator is pressed, the ACC system shall not request any deceleration.", "state-driven"),
        ("If the radar is blocked, then the ACC system shall switch to the fault state.", "unwanted behaviour"),
        ("Where a stop-and-go option is fitted, the ACC system shall follow the target to standstill.", "optional feature"),
        ("Deceleration shall be limited.", ""),
    ],
)
def test_ears_patterns(text, pattern):
    assert ears_pattern(text) == pattern
