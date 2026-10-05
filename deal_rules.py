"""When an M&A event is a reason to engage.

The rule is the owner's: an M&A event (an acquisition, a merger, a
divestiture, a carve-out or a separation, announced or completed) counts
when it happened in the last three months, or when the deal is announced
and not yet completed. An older deal that is already completed is history:
it is not an angle, it cannot lead a brief and it cannot raise the score.

The rule is checked on data the angle carries (the event's date and whether
the deal is pending or completed), never on the writer's wording. The date
has to be one a cited first-hand page gives: the page's own date, or a date
in the wording quoted from it.
"""

import calendar
import re
from datetime import date
from typing import Mapping, Sequence

import i18n
import quotes
from brief_doc import Angle, Reference
from evidence import FIRST_HAND, clean_date, parse_date

M_AND_A = "m_and_a"
PENDING = "pending"
COMPLETED = "completed"
NO_DEAL = "none"

# An M&A event counts when it happened within this many months of the day
# the brief is generated.
DEAL_WINDOW_MONTHS = 3
# A deal that is announced and not yet completed counts whatever its date.
# This one switch turns that off.
PENDING_DEALS_COUNT = True
# A deal still called pending this long after it was announced is not believed.
MAX_PENDING_DEAL_DAYS = 730
# A source dated only by its year does not date an event in that year.
_MONTH_PRECISION_CHARS = len("2026-07")
_WORD_OR_NUMBER = re.compile(r"[^\W\d_]+|\d+")
# Wording that says a deal has yet to complete: an expected completion, a
# condition still to be met, or a plain statement that it has not closed.
_SAYS_PENDING = re.compile(
    r"(?:expected|intended|anticipated|scheduled) to (?:be )?(?:close|complete|execute|finali[sz]e|occur)"
    r"|expects? (?:to|the \w+ to) (?:close|complete)"
    r"|subject to (?:\w+,? ){0,5}(?:approvals?|conditions?|ruling|clearance|registration|consents?)"
    r"|(?:has|have) not (?:yet )?(?:closed|been completed)|not yet (?:closed|completed?)|remains? pending"
    r"|will (?:close|be completed|be executed|be separated)|plans? to (?:pursue|separate|spin|divest|sell|acquire)"
    r"|over the next \d|targeted? (?:for )?(?:completion|closing)"
    r"|se espera que|sujet[ao] a |a[uú]n no se ha (?:completado|cerrado)|prev[eé] (?:completar|cerrar)",
    re.IGNORECASE,
)


def is_deal(angle: Angle) -> bool:
    return angle["use_case"] == M_AND_A


def window_start(today: date) -> date:
    """The first day an M&A event may have happened on and still count."""
    months = today.year * 12 + (today.month - 1) - DEAL_WINDOW_MONTHS
    year, month = months // 12, months % 12 + 1
    return date(year, month, min(today.day, calendar.monthrange(year, month)[1]))


def _same_date(first: str, second: str) -> bool:
    """True when two dates agree as far as the less exact one goes, to the month at least."""
    shorter, longer = sorted((first, second), key=len)
    return len(shorter) >= _MONTH_PRECISION_CHARS and longer.startswith(shorter)


def _stated_in(stored_date: str, wording: str) -> bool:
    """True when page wording gives the date: its year, its month and its day."""
    year, _, rest = stored_date.partition("-")
    month, _, day = rest.partition("-")
    words = {word.casefold() for word in _WORD_OR_NUMBER.findall(wording)}
    if year not in words or not month:
        return False
    names = [table[int(month) - 1].casefold() for table in i18n.SHORT_MONTHS.values()]
    by_name = any(word.startswith(name) for name in names for word in words)
    if not by_name and f"{year}-{month}" not in wording:
        return False
    return not day or str(int(day)) in words or day in words


def _dated_by_first_hand(
    angle: Angle, references: Sequence[Reference], wording: Mapping[int, str],
) -> bool:
    """True when a first-hand page the angle cites gives the event's date."""
    event = clean_date(angle["deal_date"])
    cited = set(_first_hand_cited(angle, references))
    for reference in references:
        if reference["n"] not in cited:
            continue
        if reference["date"] and _same_date(event, reference["date"]):
            return True
        if _stated_in(event, wording.get(reference["n"], "")):
            return True
    return False


def _first_hand_cited(angle: Angle, references: Sequence[Reference]) -> list[int]:
    cited = {number for line in angle["evidence"] for number in line["sources"]}
    return [ref["n"] for ref in references if ref["n"] in cited and ref["source_type"] == FIRST_HAND]


def status(angle: Angle, references: Sequence[Reference], wording: Mapping[int, str]) -> str:
    """Whether a deal is pending or completed, on the page's word and not the writer's.

    "Pending" stands only when the angle quotes a first-hand page it cites
    saying the deal has yet to complete. The quote is checked against the
    wording recorded from that page. Without it the deal is treated as
    completed on the date it gives.
    """
    if angle["deal_status"] != PENDING:
        return angle["deal_status"]
    quote = angle["deal_pending_quote"]
    stated = _SAYS_PENDING.search(quote) and any(
        quotes.is_on_page(quote, wording.get(number, "")) for number in _first_hand_cited(angle, references)
    )
    return PENDING if stated else COMPLETED


def qualifies(
    angle: Angle, references: Sequence[Reference], today: date, wording: Mapping[int, str],
) -> bool:
    """True when an M&A angle's event is recent enough, or still pending, to be a reason to engage.

    ``wording`` is the text quoted from each source's page, by source number.
    The angle's status is taken as given: pass it through ``status`` first.
    """
    if not is_deal(angle) or angle["deal_status"] not in (PENDING, COMPLETED):
        return False
    day = parse_date(angle["deal_date"])
    if day is None or day > today or not _dated_by_first_hand(angle, references, wording):
        return False
    if day >= window_start(today):
        return True
    still_open = angle["deal_status"] == PENDING and (today - day).days <= MAX_PENDING_DEAL_DAYS
    return PENDING_DEALS_COUNT and still_open
