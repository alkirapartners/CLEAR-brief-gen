"""How high the evidence in a brief lets its fit score go.

The writer proposes a score. This module works out a ceiling for it from
facts the code holds: which sources each angle cites, whether each source
is first-hand, and how it is dated. A score above the ceiling is lowered.
"""

from dataclasses import dataclass
from datetime import date
from itertools import combinations
from typing import Sequence

from brief_doc import Angle, Reference
from evidence import FIRST_HAND, parse_date

# "Current" in the scoring table: dated within about the last two years.
CURRENT_EVIDENCE_DAYS = 730
MAX_SCORE = 5
MAX_SCORE_WITHOUT_ANGLES = 2
MAX_SCORE_WITHOUT_CURRENT_FIRST_HAND = 3
MAX_SCORE_WITH_ONE_USE_CASE = 4
# Label keys (i18n) for the sentence that says why a score was held down.
HELD_BY_EVIDENCE = "score_held_evidence"
HELD_BY_USE_CASES = "score_held_use_cases"


@dataclass(frozen=True)
class Ceiling:
    """The highest score allowed, and the label that says what holds it there."""

    score: int
    reason: str = ""


def is_current(date_text: str, today: date) -> bool:
    """True for a real date no later than today and no older than the window."""
    day = parse_date(date_text)
    return day is not None and 0 <= (today - day).days <= CURRENT_EVIDENCE_DAYS


def _cited(angle: Angle) -> frozenset[int]:
    return frozenset(number for line in angle["evidence"] for number in line["sources"])


def _independent(first: frozenset[int], second: frozenset[int], current: frozenset[int]) -> bool:
    """Two angles each have a first-hand source of their own, one of the two currently dated."""
    return any(a != b and (a in current or b in current) for a in first for b in second)


def ceiling(angles: Sequence[Angle], references: Sequence[Reference], today: date) -> Ceiling:
    """The highest score these angles support.

    Above 2 takes an angle. Above 3 takes an angle citing a first-hand source
    dated within the window: trade press, an undated page or an old one
    cannot do it. A 5 takes two different use cases, each citing a
    first-hand source the other does not depend on, one of them dated
    within the window.
    """
    if not angles:
        return Ceiling(MAX_SCORE_WITHOUT_ANGLES)
    first_hand = frozenset(ref["n"] for ref in references if ref["source_type"] == FIRST_HAND)
    current = frozenset(ref["n"] for ref in references if ref["n"] in first_hand and is_current(ref["date"], today))
    backed = [(angle["use_case"], _cited(angle) & first_hand) for angle in angles]
    if not any(sources & current for _, sources in backed):
        return Ceiling(MAX_SCORE_WITHOUT_CURRENT_FIRST_HAND, HELD_BY_EVIDENCE)
    for (use_case, sources), (other_case, other_sources) in combinations(backed, 2):
        if use_case != other_case and _independent(sources, other_sources, current):
            return Ceiling(MAX_SCORE)
    return Ceiling(MAX_SCORE_WITH_ONE_USE_CASE, HELD_BY_USE_CASES)
