"""Rules the code enforces on a brief, whatever the model wrote.

The writer is asked to follow these rules. This module makes sure of it:
evidence must point at a page that was opened, an angle with no evidence
left is removed, a customer story is one from the knowledge base, and the
score cannot claim more than the angles that survive support.
"""

import logging
import re
from datetime import date
from typing import Any, Iterable, Sequence

import case_studies
from brief_doc import (
    FORMAT_VERSION, SNAPSHOT_KEYS, Angle, BriefDoc, EvidenceLine, Person, Question,
    Reference, ResearchNote, Snapshot, SnapshotLine, Story, WriterOutput,
)
from evidence import safe_url

logger = logging.getLogger(__name__)

MAX_ANGLES = 3
MAX_QUESTIONS = 4
# The scoring table: 3 and up need an evidenced use case, 5 needs two.
MAX_SCORE_WITHOUT_ANGLES = 2
MAX_SCORE_WITH_ONE_ANGLE = 4
# The language the story table is written in.
TABLE_LANGUAGE = "en"


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


def _evidence(lines: Sequence[EvidenceLine], valid: frozenset[int]) -> list[EvidenceLine]:
    checked = [{**line, "sources": _known(line["sources"], valid)} for line in lines]
    return [line for line in checked if line["sources"] and line["text"].strip()]


_NUMBER = re.compile(r"\d[\d.,]*\d|\d")


def _numbers(text: str) -> frozenset[str]:
    """Every figure in the text as bare digits, so 1,400 and 1.400 are the same."""
    return frozenset(re.sub(r"[.,]", "", number) for number in _NUMBER.findall(text))


def _story(story: Story, language: str) -> Story:
    """The story as the knowledge base has it. Proof is never the model's own.

    The customer name always comes from the story table. So does the result
    for a brief in English. In another language the model's translation of
    the result is kept only when it carries exactly the table's figures.
    Otherwise the table's wording is used.
    """
    known = case_studies.story_by_id(story["id"])
    if known is None:
        return {"id": case_studies.NO_STORY, "customer": "", "result": ""}
    translated = story["result"].strip() if language != TABLE_LANGUAGE else ""
    if _numbers(translated) != _numbers(known.result):
        translated = ""  # a translation may change the words, never the figures
    return {"id": known.id, "customer": known.customer, "result": translated or known.result}


def _angles(angles: Sequence[Angle], valid: frozenset[int], language: str) -> list[Angle]:
    """Angles that still have evidence, strongest first as written, three at most."""
    checked = [
        {
            **angle,
            "evidence": _evidence(angle["evidence"], valid),
            "story": _story(angle["story"], language),
        }
        for angle in angles
    ]
    return [angle for angle in checked if angle["evidence"]][:MAX_ANGLES]


def _snapshot_line(line: SnapshotLine, valid: frozenset[int]) -> SnapshotLine:
    """A sourced line, or an empty one. An empty line prints as "not found"."""
    sources = _known(line["sources"], valid)
    text = line["text"].strip()
    if not sources or not text:
        return {"text": "", "sources": []}
    return {"text": text, "sources": sources}


def _snapshot(snapshot: Snapshot, valid: frozenset[int]) -> Snapshot:
    return {key: _snapshot_line(snapshot[key], valid) for key in SNAPSHOT_KEYS}


def _people(people: Sequence[Person], valid: frozenset[int]) -> list[Person]:
    """A name needs a source. Without one the person is listed by role only."""
    checked: list[Person] = []
    for person in people:
        sources = _known(person["sources"], valid)
        name = person["name"].strip() if sources else ""
        if name or person["role"].strip():
            checked.append({**person, "name": name, "sources": sources})
    return checked


def _questions(questions: Sequence[Question]) -> list[Question]:
    return [q for q in questions if q["question"].strip()][:MAX_QUESTIONS]


def _score(score: int, angle_count: int) -> int:
    if angle_count == 0:
        return min(score, MAX_SCORE_WITHOUT_ANGLES)
    if angle_count == 1:
        return min(score, MAX_SCORE_WITH_ONE_ANGLE)
    return score


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


def finalize(
    output: WriterOutput,
    candidates: Sequence[Reference],
    language: str,
    today: date,
    research: ResearchNote,
) -> BriefDoc:
    """Turn the writer's output into the document that is stored.

    ``candidates`` are the pages that were opened, numbered as the writer
    saw them. Only the ones the brief cites become its references, and they
    are renumbered from 1 in the order the brief cites them.
    """
    output = _scrub(output)
    valid = frozenset(ref["n"] for ref in candidates)
    angles = _angles(output["angles"], valid, language)
    snapshot = _snapshot(output["snapshot"], valid)
    people = _people(output["people"], valid)
    score = _score(output["fit"]["score"], len(angles))
    if len(angles) != len(output["angles"]) or score != output["fit"]["score"]:
        logger.warning(
            "Brief for %s adjusted: angles %d -> %d, score %d -> %d",
            output["company"]["name"], len(output["angles"]), len(angles),
            output["fit"]["score"], score,
        )
    order = {old: new for new, old in enumerate(_cited(angles, snapshot, people), start=1)}
    return {
        "format": FORMAT_VERSION,
        "language": language,
        "generated": today.isoformat(),
        "company": {**output["company"], "website": safe_url(output["company"]["website"]) or ""},
        "stats": output["stats"],
        "fit": {**output["fit"], "score": score},
        "angles": [
            {**angle, "evidence": [
                {**line, "sources": _renumber(line["sources"], order)} for line in angle["evidence"]
            ]}
            for angle in angles
        ],
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
