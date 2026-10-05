"""A JSON brief in the shape the current front end already reads.

The page shows a company, a stats line, a score with its rationale, four
infrastructure cells, signals, up to three entry points, conversation
starters and references. These functions fill every one of those from a
brief document, so the page keeps working until it learns the new layout.
"""

import re

import i18n
import ticker
from brief_doc import Angle, BriefDoc, EvidenceLine, Person, SnapshotLine, Story

SNIPPET_CHARS = 120
Labels = dict[str, str]
_ENDS_A_SENTENCE = (".", "!", "?")
_WORD_OR_NUMBER = re.compile(r"[^\W\d_]+|\d+")


def cite(sources: list[int]) -> str:
    """Reference markers for a line: `` [1] [3]``, or nothing."""
    return "".join(f" [{number}]" for number in sources)


def evidence_text(line: EvidenceLine, labels: Labels) -> str:
    """An evidence line with its date, or with the word that says it has none."""
    dated = line["date"].strip() or labels["undated"]
    return f"{line['text']} ({dated}){cite(line['sources'])}"


def snapshot_text(line: SnapshotLine, labels: Labels) -> str:
    if not line["text"]:
        return labels["not_found"]
    return f"{line['text']}{cite(line['sources'])}"


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


def _already_says(text: str, stored_date: str, language: str) -> bool:
    """True when the sentence itself gives the date: its year, its month and its day."""
    year, _, rest = stored_date.partition("-")
    month, _, day = rest.partition("-")
    words = {word.casefold() for word in _WORD_OR_NUMBER.findall(text)}
    if year not in words:
        return False
    if month and not any(
        word.startswith(names[int(month) - 1].casefold()) for names in i18n.SHORT_MONTHS.values() for word in words
    ):
        return False
    return not day or str(int(day)) in words


def _page_sentence(line: EvidenceLine, language: str) -> str:
    """An evidence line as the page shows it: one sentence, its date in words at the end."""
    when = i18n.readable_date(line["date"], language)
    text = line["text"].strip()
    if not when or _already_says(text, line["date"].strip(), language):
        return _sentence(text)
    return f"{text.rstrip('.')} ({when})."


def _trigger(angle: Angle) -> EvidenceLine | None:
    """The fact an angle shows under Signals & Timing: its first dated line, else its first."""
    lines = angle["evidence"]
    return next((line for line in lines if line["date"].strip()), lines[0] if lines else None)


def signals(doc: BriefDoc) -> list[str]:
    """One dated fact per angle, each said once on the page."""
    triggers = [_trigger(angle) for angle in doc["angles"]]
    return [_page_sentence(line, doc["language"]) for line in triggers if line is not None]


def entry_points(doc: BriefDoc) -> list[dict[str, str]]:
    """One entry point per angle: as many as the brief has, never padded.

    The signal is the angle's evidence other than the fact already shown
    under Signals & Timing, so nothing is printed twice. An angle with a
    single fact has an empty signal and the page leaves that row out.
    """
    points: list[dict[str, str]] = []
    for angle in doc["angles"]:
        trigger = _trigger(angle)
        rest = [line for line in angle["evidence"] if line is not trigger]
        points.append({
            "heading": angle["title"],
            "signal": " ".join(_page_sentence(line, doc["language"]) for line in rest),
            "solution": angle["alkira"],
            "proof": proof_text(angle["story"]),
        })
    return points


def _bullets(title: str, items: list[str]) -> list[str]:
    if not items:
        return []
    return ["", f"**{title}:**", *[f"- {item}" for item in items]]


def starters_md(doc: BriefDoc, labels: Labels) -> str:
    lines: list[str] = []
    people = [person_text(person) for person in doc["people"]]
    if people:
        lines.append(f"**{labels['stakeholders']}:** {', '.join(people)}")
    if doc["questions"]:
        # The lead itself is in the score rationale. Here the page is pointed at the question.
        lines.append(f"**{labels['best_first_question']}:** {labels['lead_with_first_question']}")
    for number, item in enumerate(doc["questions"], start=1):
        note = f"{labels['listen_for']}: {item['listen_for']} {labels['alkira_angle']}: {item['alkira_angle']}"
        lines += ["", f'{number}. "{item["question"]}"', f"   *({note})*"]
    lines += _bullets(labels["unconfirmed"], doc["unconfirmed"])
    lines += _bullets(labels["raise_score"], doc["raise_score"])
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
