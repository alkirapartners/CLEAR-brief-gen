"""A JSON brief in the shape the current front end already reads.

The page shows a company, stat pills, a score with its rationale, four
infrastructure cells, signals, up to three entry points, conversation
starters and references. These functions fill every one of those from a
brief document, so the page keeps working until it learns the new layout.
The page gets plain sentences: no citation markers, dates in words, and
nothing said twice. The short stat pills are in stat_pills.py.

The PDF and the text rendering share the helpers at the top (evidence
lines with their markers, the full stats line, people, stories).
"""

import re

import i18n
import proof_points
import ticker
from brief_doc import Angle, BriefDoc, EvidenceLine, Person, Question, SnapshotLine, Story

SNIPPET_CHARS = 120
Labels = dict[str, str]
_ENDS_A_SENTENCE = (".", "!", "?")


def cite(sources: list[int]) -> str:
    """Reference markers for a line: `` [1] [3]``, or nothing."""
    return "".join(f" [{number}]" for number in sources)


# A sentence that carries its own date or period: a year, a quarter, a half,
# a fiscal year, a month. Its source's date is then left off, because
# "in the first quarter of 2026 (31 Dec 2025)" reads as a contradiction.
_OWN_PERIOD = re.compile(
    r"\b(?:19|20)\d{2}\b|\bFY\s?\d{2,4}\b|\b[QH][1-4]\b"
    r"|\b(?:first|second|third|fourth|last|next|this)\s+(?:quarter|half|year)\b|\byear[- ]end\b"
    r"|\b(?:primer|segundo|tercer|cuarto|[uú]ltimo|pr[oó]ximo|este)\s+(?:trimestre|semestre|a[nñ]o)\b"
    r"|\b(?:january|february|march|april|june|july|august|september|october|november|december)\b"
    r"|\b(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b",
    re.IGNORECASE,
)


def source_date_note(line: EvidenceLine, labels: Labels, language: str | None) -> str:
    """What to say about when a line's source is dated, or "" when the line dates itself.

    "source dated 31 Dec 2025" when the source gives a date, so it is never
    read as the date of what the line describes.
    """
    if _OWN_PERIOD.search(line["text"]):
        return ""
    when = i18n.readable_date(line["date"], language)
    return labels["source_dated"].format(date=when) if when else ""


def evidence_text(line: EvidenceLine, labels: Labels, language: str | None = None) -> str:
    """An evidence line for the PDF and the text: its source's date, then its citations.

    A line whose source gives no date says so.
    """
    note = source_date_note(line, labels, language) if line["date"].strip() else labels["undated"]
    return f"{line['text']}{f' ({note})' if note else ''}{cite(line['sources'])}"


def snapshot_text(line: SnapshotLine, labels: Labels) -> str:
    if not line["text"]:
        return labels["not_found"]
    return f"{line['text']}{cite(line['sources'])}"


def is_proof_point(story: Story) -> bool:
    """True for a knowledge-base figure standing in where no customer story fits."""
    return story["id"] == proof_points.METRIC


def proof_text(story: Story) -> str:
    if story["customer"] and story["result"]:
        return f"{story['customer']}: {story['result']}"
    return story["customer"] or story["result"]


def person_text(person: Person) -> str:
    if person["name"] and person["role"]:
        return f"{person['role']} ({person['name']})"
    return person["name"] or person["role"]


def entity_text(doc: BriefDoc) -> str:
    """The legal entity with its ticker, when the research resolved one."""
    legal_name = doc["company"]["legal_name"].strip()
    listing = ticker.normalise(doc["company"]["ticker"])
    return f"{legal_name} ({listing})" if legal_name and listing else legal_name


def stat_pairs(doc: BriefDoc, labels: Labels) -> list[tuple[str, str]]:
    """Label and full value for each stat that was found, for the PDF and the text.

    The current page shows short pills instead: see stat_pills.py.
    """
    stats = doc["stats"]
    pairs = [
        (labels["stat_entity"], entity_text(doc)),
        (labels["stat_hq"], stats["hq"]),
        (labels["stat_revenue"], stats["revenue"]),
        (labels["stat_employees"], stats["employees"]),
        (labels["stat_industry"], stats["industry"]),
        (labels["stat_ownership"], stats["ownership"]),
        (labels["stat_cloud_network"], stats["cloud_network"]),
    ]
    return [(label, value.strip()) for label, value in pairs if value.strip()]


def stats_line(doc: BriefDoc, labels: Labels) -> str:
    return " | ".join(f"{label}: {value}" for label, value in stat_pairs(doc, labels))


def score_rationale(doc: BriefDoc) -> str:
    return f"{doc['fit']['verdict']} {doc['fit']['lead']}".strip()


def snippet(doc: BriefDoc, max_chars: int = SNIPPET_CHARS) -> str:
    text = doc["fit"]["verdict"].strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


# Which snapshot lines each of the page's four infrastructure cells holds.
INFRA_CELLS: dict[str, tuple[str, ...]] = {
    "cloudPlatforms": ("clouds",),
    "onPrem": ("data_centers", "plant_networks"),
    "deployment": ("cloud_connectivity",),
    "complexity": ("wan", "firewalls"),
}


def infra_cells(doc: BriefDoc, labels: Labels) -> dict[str, str]:
    """The six snapshot lines as the four cells the page has, each written as sentences.

    A line that was not found is left out of a cell that has something to
    say. A cell with nothing says so once. When nothing at all was found
    every cell is empty, and the page leaves the block out.
    """
    snapshot = doc["snapshot"]
    cells = {
        cell: " ".join(_sentence(snapshot[key]["text"]) for key in keys if snapshot[key]["text"].strip())
        for cell, keys in INFRA_CELLS.items()
    }
    if not any(cells.values()):
        return cells
    return {cell: text or labels["not_found_public"] for cell, text in cells.items()}


# ── The current page: plain sentences, no citation markers ──────────────────

def _sentence(text: str) -> str:
    """The text ending in a full stop, so sentences set side by side stay apart."""
    clean = text.strip()
    return clean if not clean or clean.endswith(_ENDS_A_SENTENCE) else f"{clean}."


def _page_sentence(line: EvidenceLine, labels: Labels, language: str) -> str:
    """An evidence line as the page shows it: one sentence, then when its source is dated."""
    note = source_date_note(line, labels, language)
    text = line["text"].strip()
    return f"{text.rstrip('.')} ({note})." if note else _sentence(text)


def _trigger(angle: Angle) -> EvidenceLine | None:
    """The fact an angle shows under Signals & Timing: its first dated line, else its first."""
    lines = angle["evidence"]
    return next((line for line in lines if line["date"].strip()), lines[0] if lines else None)


def signals(doc: BriefDoc, labels: Labels) -> list[str]:
    """One dated fact per angle, each said once on the page."""
    triggers = [_trigger(angle) for angle in doc["angles"]]
    return [_page_sentence(line, labels, doc["language"]) for line in triggers if line is not None]


def entry_points(doc: BriefDoc, labels: Labels) -> list[dict[str, str]]:
    """One entry point per angle: as many as the brief has, never padded.

    Every entry point has all three rows, because the page drops the row
    labels from a card that has only one. The signal is the angle's
    evidence other than the fact already shown under Signals & Timing, so
    nothing is printed twice; an angle with a single fact repeats it. The
    proof is the angle's story, or the headline figure for its use case
    when it has none.
    """
    language = i18n.normalize(doc["language"])
    points: list[dict[str, str]] = []
    for angle in doc["angles"]:
        trigger = _trigger(angle)
        rest = [line for line in angle["evidence"] if line is not trigger] or angle["evidence"]
        proof = proof_text(angle["story"]) or proof_points.fallback(angle["use_case"], language)["result"]
        points.append({
            "heading": angle["title"],
            "signal": " ".join(_page_sentence(line, labels, doc["language"]) for line in rest),
            "solution": angle["alkira"],
            "proof": proof,
        })
    return points


# Between stakeholders. A comma would not do: a role can hold one. The
# space before the dot does not break, so the dot never starts a line.
STAKEHOLDER_SEPARATOR = "\u00a0· "
# The older briefs asked for two or three things to validate early.
MAX_VALIDATE_EARLY = 3


def _question_lines(number: int, item: Question, labels: Labels) -> list[str]:
    """A question and its two notes. The page joins the notes, so each ends in a full stop."""
    return [
        "",
        f'{number}. "{item["question"]}"',
        f"   *({labels['listen_for']}: {_sentence(item['listen_for'])})*",
        f"   *({labels['alkira_angle']}: {_sentence(item['alkira_angle'])})*",
    ]


def starters_md(doc: BriefDoc, labels: Labels) -> str:
    """The conversation starters as the page reads them.

    Who to talk to, which question to lead with, the questions with their
    notes, then what to validate early: the first things the brief could
    not confirm. What would raise the score is left to the document.
    """
    lines: list[str] = []
    people = [person_text(person) for person in doc["people"]]
    if people:
        lines.append(f"**{labels['stakeholders']}:** {STAKEHOLDER_SEPARATOR.join(people)}")
    if doc["questions"]:
        # The lead itself is in the score rationale. Here the page is pointed at the question.
        lines.append(f"**{labels['best_first_question']}:** {labels['lead_with_first_question']}")
    for number, item in enumerate(doc["questions"], start=1):
        lines += _question_lines(number, item, labels)
    to_validate = [_sentence(item) for item in doc["unconfirmed"][:MAX_VALIDATE_EARLY]]
    if to_validate:
        lines += ["", f"**{labels['validate_early']}:**", *[f"- {item}" for item in to_validate]]
    return "\n".join(lines).strip()


# The label printed after a reference that is not first-hand.
_SOURCE_TYPE_LABELS: dict[str, str] = {
    "second_hand": "source_second_hand",
    "last_resort": "source_last_resort",
}


def reference_text(reference: dict, labels: Labels) -> str:
    """A reference line. Anything short of first-hand says what it is."""
    label = _SOURCE_TYPE_LABELS.get(reference["source_type"])
    kind = f" ({labels[label]})" if label else ""
    return f"[{reference['n']}] {reference['title']}{kind} — {reference['url']}"


def references_md(doc: BriefDoc, labels: Labels) -> str:
    return "\n".join(reference_text(reference, labels) for reference in doc["references"])
