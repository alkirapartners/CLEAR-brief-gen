"""Headquarters, revenue and headcount are kept only when the evidence states them.

Each of the three is checked against the facts that are about it, never
against the evidence as a whole: twelve stores opened is not twelve billion
in revenue. A value that does not trace is left empty.
"""

import re
from typing import Sequence

from brief_doc import Stats
from evidence import EvidenceItem, Source

# What a fact has to mention to be a fact about revenue, or about headcount.
_ABOUT: dict[str, re.Pattern[str]] = {
    "revenue": re.compile(r"revenue|sales|turnover|ingresos|ventas|facturaci", re.IGNORECASE),
    "employees": re.compile(
        r"employ|team members|workforce|staff|associates|headcount|empleados|colaboradores|plantilla",
        re.IGNORECASE,
    ),
}
# A place name is checked by its words of at least this many letters.
MIN_PLACE_WORD_CHARS = 3
# The language whose thousands are written with a point: "5.200".
POINT_THOUSANDS_LANGUAGE = "es"
_FIGURE = re.compile(r"\d[\d,]*(?:\.\d+)?")
_POINT_THOUSANDS = re.compile(r"(?<=\d)\.(?=\d{3}(?!\d))")
_YEAR = re.compile(r"^(?:19|20)\d{2}$")
_WORD = re.compile(r"[^\W\d_]+")


def _plain_number(written: str) -> str:
    """One figure as a plain number: "1,400" is 1400 and "10.0" is 10, never 100."""
    number = written.replace(",", "")
    return number.rstrip("0").rstrip(".") if "." in number else number


def figures(text: str) -> frozenset[str]:
    """Every figure in the text as a plain number. A year is a label, not a figure."""
    plain = (_plain_number(found) for found in _FIGURE.findall(text))
    return frozenset(number for number in plain if number and not _YEAR.match(number))


def _stated(item: EvidenceItem) -> str:
    """What one fact says: the researcher's sentence and the page wording under it."""
    return f"{item.fact}\n{item.quote}"


def _traced_figure(value: str, facts: Sequence[str], language: str) -> str:
    """The value, or nothing unless a fact about that basic gives each of its figures."""
    known = frozenset().union(*(figures(fact) for fact in facts)) if facts else frozenset()
    readings = [figures(value)]
    if language == POINT_THOUSANDS_LANGUAGE:
        readings.append(figures(_POINT_THOUSANDS.sub("", value)))
    return value if any(wanted and wanted <= known for wanted in readings) else ""


def _traced_place(value: str, facts: Sequence[str]) -> str:
    """The value, or nothing unless one fact names the place before its first comma."""
    place = [w.casefold() for w in _WORD.findall(value.split(",")[0]) if len(w) >= MIN_PLACE_WORD_CHARS]
    if not place:
        return ""
    for fact in facts:
        words = {word.casefold() for word in _WORD.findall(fact)}
        if all(word in words for word in place):
            return value
    return ""


def traced(stats: Stats, sources: Sequence[Source], language: str) -> Stats:
    """The basics with headquarters, revenue and headcount as the evidence gives them, or empty.

    The other basics are the writer's own summary of the evidence.
    """
    facts = [_stated(item) for source in sources for item in source.facts]
    checked = {
        key: _traced_figure(stats[key].strip(), [fact for fact in facts if about.search(fact)], language)
        for key, about in _ABOUT.items()
    }
    return {**stats, **checked, "hq": _traced_place(stats["hq"].strip(), facts)}
