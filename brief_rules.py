"""Rules the code enforces on a brief, whatever the model wrote.

The writer is asked to follow these rules. This module makes sure of it:
evidence must point at a page that was opened and carries that page's date,
lines that are never evidence are removed (angle_rules.py), an angle with
no dated fact left is removed, a customer story is one from the knowledge
base that fits the angle, basics trace to the evidence, and the score
cannot claim more than the sources of the surviving angles support
(fit_score.py).
"""

import logging
import re
from datetime import date
from typing import Any, Iterable, Mapping, Sequence

import angle_rules
import case_studies
import fit_score
import i18n
import ticker
from brief_doc import (
    FORMAT_VERSION, SNAPSHOT_KEYS, Angle, BriefDoc, Company, EvidenceLine, Fit, Person, Question,
    Reference, ResearchNote, Snapshot, SnapshotLine, Stats, Story, WriterOutput,
)
from evidence import FIRST_HAND, Source, clean_date, parse_date, safe_url, to_references

logger = logging.getLogger(__name__)

MAX_ANGLES = 3
MAX_QUESTIONS = 4
# The scoring table: a 1 or 2 presents no angle at all. How high the angles
# that are presented let the score go is worked out in fit_score.py.
MAX_SCORE_WITHOUT_ANGLES = fit_score.MAX_SCORE_WITHOUT_ANGLES
# The language the story table is written in.
TABLE_LANGUAGE = "en"
PLANT_NETWORKS = "plant_networks"
# Basics that are figures: every figure in them has to be in the evidence.
FIGURE_STATS: tuple[str, ...] = ("revenue", "employees")
# A place name is checked by its words of at least this many letters.
MIN_PLACE_WORD_CHARS = 3


# The brief shows no links of the model's own making. Sources are cited by
# number and listed by the code; the website is checked on its own.
_MARKDOWN_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_BARE_URL = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_NOT_PROSE = frozenset({"website"})


def _plain(text: str) -> str:
    """Text with markdown links reduced to their words and web addresses removed."""
    unlinked = _MARKDOWN_LINK.sub(r"\1", text)
    return " ".join(_BARE_URL.sub("", unlinked).split())


def _scrub(value: Any) -> Any:
    """A copy of the writer's output with every string made plain, at any depth."""
    if isinstance(value, str):
        return _plain(value)
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    if isinstance(value, dict):
        return {key: item if key in _NOT_PROSE else _scrub(item) for key, item in value.items()}
    return value


def _known(numbers: Iterable[int], valid: frozenset[int]) -> list[int]:
    """Source numbers that exist, once each, in the order given."""
    kept: list[int] = []
    for number in numbers:
        if number in valid and number not in kept:
            kept.append(number)
    return kept


# The date each source gives for itself, by source number. Empty when it gives none.
Dates = Mapping[int, str]


def _line_date(written: str, sources: Sequence[int], dates: Dates, today: date) -> str:
    """The date an evidence line carries: always one its own sources give.

    The writer's date is kept when a cited source gives exactly that date.
    Otherwise the newest date among the cited sources is used, and a line
    whose sources give none is undated. A date after today dates nothing.
    """
    days = {text: parse_date(text) for text in (dates.get(n, "") for n in sources)}
    usable = {text: day for text, day in days.items() if day is not None and day <= today}
    if clean_date(written) in usable:
        return clean_date(written)
    return max(usable, key=usable.__getitem__, default="")


def _evidence(
    lines: Sequence[EvidenceLine], dates: Dates, today: date,
) -> list[EvidenceLine]:
    """Lines that still cite an opened page, each dated by the pages it cites."""
    checked: list[EvidenceLine] = []
    for line in lines:
        sources = _known(line["sources"], frozenset(dates))
        if sources and line["text"].strip():
            checked.append({**line, "sources": sources, "date": _line_date(line["date"], sources, dates, today)})
    return checked


_NUMBER = re.compile(r"\d[\d.,]*\d|\d")


def _numbers(text: str) -> frozenset[str]:
    """Every figure in the text as bare digits, so 1,400 and 1.400 are the same."""
    return frozenset(re.sub(r"[.,]", "", number) for number in _NUMBER.findall(text))


_NO_STORY: Story = {"id": case_studies.NO_STORY, "customer": "", "result": ""}


def _story(story: Story, use_case: str, told: frozenset[str], language: str) -> Story:
    """The story as the knowledge base has it. Proof is never the model's own.

    A story is kept only when the table tags it with the angle's use case
    and no earlier angle in this brief has told it. The customer name always
    comes from the story table. So does the result for a brief in English.
    In another language the model's translation of the result is kept only
    when it carries exactly the table's figures. Otherwise the table's
    wording is used.
    """
    known = case_studies.story_by_id(story["id"])
    if known is None or use_case not in known.situations or known.id in told:
        return {**_NO_STORY}
    translated = story["result"].strip() if language != TABLE_LANGUAGE else ""
    if _numbers(translated) != _numbers(known.result):
        translated = ""  # a translation may change the words, never the figures
    return {"id": known.id, "customer": known.customer, "result": translated or known.result}


def _angles(angles: Sequence[Angle], dates: Dates, language: str, today: date) -> list[Angle]:
    """Angles that still stand on their evidence, strongest first as written, three at most.

    Lines that are never evidence are removed first. An angle then needs a
    dated fact about the right thing (angle_rules.stands) to be kept.
    """
    checked = [
        {**angle, "evidence": angle_rules.kept_lines(_evidence(angle["evidence"], dates, today))}
        for angle in angles
    ]
    kept: list[Angle] = []
    told: frozenset[str] = frozenset()
    for angle in [angle for angle in checked if angle_rules.stands(angle)][:MAX_ANGLES]:
        story = _story(angle["story"], angle["use_case"], told, language)
        told = told | ({story["id"]} - {case_studies.NO_STORY})
        kept.append({**angle, "story": story})
    return kept


def _snapshot_line(line: SnapshotLine, valid: frozenset[int]) -> SnapshotLine:
    """A sourced line, or an empty one. An empty line prints as "not found"."""
    sources = _known(line["sources"], valid)
    text = line["text"].strip()
    if not sources or not text:
        return {"text": "", "sources": []}
    return {"text": text, "sources": sources}


def _snapshot(snapshot: Snapshot, valid: frozenset[int]) -> Snapshot:
    lines = {key: _snapshot_line(snapshot[key], valid) for key in SNAPSHOT_KEYS}
    if not angle_rules.is_plant_network(lines[PLANT_NETWORKS]["text"]):
        # Scanners, readers and shop Wi-Fi are not industrial control systems.
        lines[PLANT_NETWORKS] = {"text": "", "sources": []}
    return lines


def _people(people: Sequence[Person], valid: frozenset[int], first_hand: frozenset[int]) -> list[Person]:
    """A name needs a first-hand source, and anything said about the person needs a source.

    A person named only by trade press or a data broker is listed by role.
    """
    checked: list[Person] = []
    for person in people:
        sources = _known(person["sources"], valid)
        name = person["name"].strip() if first_hand.intersection(sources) else ""
        note = person["note"].strip() if sources else ""
        if name or person["role"].strip():
            checked.append({**person, "name": name, "note": note, "sources": sources})
    return checked


_WORD = re.compile(r"[^\W\d_]+")


def _words(text: str) -> frozenset[str]:
    return frozenset(word.casefold() for word in _WORD.findall(text))


def _stated(sources: Sequence[Source]) -> str:
    """Everything the evidence says: each fact and the page wording under it."""
    return "\n".join(f"{fact.fact}\n{fact.quote}" for source in sources for fact in source.facts)


def _traced_figure(value: str, figures: frozenset[str]) -> str:
    """The value, or nothing unless every figure in it is a figure in the evidence."""
    wanted = _numbers(value)
    return value if wanted and wanted <= figures else ""


def _traced_place(value: str, words: frozenset[str]) -> str:
    """The value, or nothing unless the evidence names the place before its first comma."""
    place = [w for w in _words(value.split(",")[0]) if len(w) >= MIN_PLACE_WORD_CHARS]
    return value if place and all(word in words for word in place) else ""


def _stats(stats: Stats, stated: str) -> Stats:
    """Headquarters, revenue and headcount as the evidence gives them, or empty.

    The other basics are the writer's own summary of the evidence.
    """
    figures = _numbers(stated)
    traced = {key: _traced_figure(stats[key].strip(), figures) for key in FIGURE_STATS}
    return {**stats, **traced, "hq": _traced_place(stats["hq"].strip(), _words(stated))}


def _questions(questions: Sequence[Question]) -> list[Question]:
    return [q for q in questions if q["question"].strip()][:MAX_QUESTIONS]


def _fit(fit: Fit, ceiling: fit_score.Ceiling, language: str) -> Fit:
    """The fit as written, or lowered to what the sources support, with the reason added."""
    if fit["score"] <= ceiling.score:
        return fit
    reason = i18n.labels(language)[ceiling.reason].format(score=ceiling.score) if ceiling.reason else ""
    return {**fit, "score": ceiling.score, "verdict": f"{fit['verdict'].strip()} {reason}".strip()}


def _cited(angles: Sequence[Angle], snapshot: Snapshot, people: Sequence[Person]) -> list[int]:
    """Every source number the brief cites, in order of first appearance."""
    numbers = [n for angle in angles for line in angle["evidence"] for n in line["sources"]]
    numbers += [n for key in SNAPSHOT_KEYS for n in snapshot[key]["sources"]]
    numbers += [n for person in people for n in person["sources"]]
    return list(dict.fromkeys(numbers))


def _renumber(numbers: Sequence[int], order: dict[int, int]) -> list[int]:
    return [order[number] for number in numbers]


def _references(candidates: Sequence[Reference], order: dict[int, int]) -> list[Reference]:
    by_number = {ref["n"]: ref for ref in candidates}
    return [{**by_number[old], "n": new} for old, new in order.items()]


def _company(company: Company) -> Company:
    """The company as written, with the website checked and the ticker stated one way."""
    return {
        **company,
        "website": safe_url(company["website"]) or "",
        "ticker": ticker.normalise(company["ticker"]),
    }


def _renumbered_angle(angle: Angle, order: dict[int, int]) -> Angle:
    lines = [{**line, "sources": _renumber(line["sources"], order)} for line in angle["evidence"]]
    return {**angle, "evidence": lines}


def _log_adjustment(output: WriterOutput, angles: Sequence[Angle], score: int) -> None:
    if len(angles) == len(output["angles"]) and score == output["fit"]["score"]:
        return
    logger.warning(
        "Brief for %s adjusted: angles %d -> %d, score %d -> %d",
        output["company"]["name"], len(output["angles"]), len(angles),
        output["fit"]["score"], score,
    )


def finalize(
    output: WriterOutput,
    sources: Sequence[Source],
    language: str,
    today: date,
    research: ResearchNote,
) -> BriefDoc:
    """Turn the writer's output into the document that is stored.

    ``sources`` are the pages that were opened, numbered as the writer saw
    them, with the facts recorded from each. Only the ones the brief cites
    become its references, and they are renumbered from 1 in the order the
    brief cites them.
    """
    output = _scrub(output)
    candidates = to_references(sources)
    valid = frozenset(ref["n"] for ref in candidates)
    dates = {ref["n"]: ref["date"] for ref in candidates}
    wanted = output["angles"] if output["fit"]["score"] > MAX_SCORE_WITHOUT_ANGLES else []
    angles = _angles(wanted, dates, language, today)
    snapshot = _snapshot(output["snapshot"], valid)
    first_hand = frozenset(ref["n"] for ref in candidates if ref["source_type"] == FIRST_HAND)
    people = _people(output["people"], valid, first_hand)
    fit = _fit(output["fit"], fit_score.ceiling(angles, candidates, today), language)
    _log_adjustment(output, angles, fit["score"])
    order = {old: new for new, old in enumerate(_cited(angles, snapshot, people), start=1)}
    return {
        "format": FORMAT_VERSION,
        "language": language,
        "generated": today.isoformat(),
        "company": _company(output["company"]),
        "stats": _stats(output["stats"], _stated(sources)),
        "fit": fit,
        "angles": [_renumbered_angle(angle, order) for angle in angles],
        "snapshot": {
            key: {**snapshot[key], "sources": _renumber(snapshot[key]["sources"], order)}
            for key in SNAPSHOT_KEYS
        },
        "people": [{**p, "sources": _renumber(p["sources"], order)} for p in people],
        "questions": _questions(output["questions"]),
        "unconfirmed": [item.strip() for item in output["unconfirmed"] if item.strip()],
        "raise_score": [item.strip() for item in output["raise_score"] if item.strip()],
        "references": _references(candidates, order),
        "research": research,
    }
