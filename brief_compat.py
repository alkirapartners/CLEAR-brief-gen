"""A JSON brief in the shape the current front end already reads.

The page shows a company, a stats line, a score with its rationale, four
infrastructure cells, signals, up to three entry points, conversation
starters and references. These functions fill every one of those from a
brief document, so the page keeps working until it learns the new layout.
"""

from brief_doc import BriefDoc, EvidenceLine, Person, SnapshotLine, Story

MAX_LEGACY_SIGNALS = 6
SNIPPET_CHARS = 120
Labels = dict[str, str]


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
    ticker = doc["company"]["ticker"].strip()
    return f"{legal_name} ({ticker})" if legal_name and ticker else legal_name


def stat_pairs(doc: BriefDoc, labels: Labels) -> list[tuple[str, str]]:
    """Label and value for each stat that was found, in display order."""
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


def infra_cells(doc: BriefDoc, labels: Labels) -> dict[str, str]:
    """The six snapshot lines folded into the four cells the page has."""
    snapshot = doc["snapshot"]

    def labelled(key: str) -> str:
        return f"{labels['snap_' + key]}: {snapshot_text(snapshot[key], labels)}"

    return {
        "cloudPlatforms": snapshot_text(snapshot["clouds"], labels),
        "onPrem": f"{labelled('data_centers')} {labelled('plant_networks')}",
        "deployment": snapshot_text(snapshot["cloud_connectivity"], labels),
        "complexity": f"{labelled('wan')} {labelled('firewalls')}",
    }


def signals(doc: BriefDoc, labels: Labels) -> list[str]:
    lines = [evidence_text(line, labels) for angle in doc["angles"] for line in angle["evidence"]]
    return lines[:MAX_LEGACY_SIGNALS]


def entry_points(doc: BriefDoc, labels: Labels) -> list[dict[str, str]]:
    """One entry point per angle: as many as the brief has, never padded."""
    return [
        {
            "heading": angle["title"],
            "signal": " ".join(evidence_text(line, labels) for line in angle["evidence"]),
            "solution": angle["alkira"],
            "proof": proof_text(angle["story"]),
        }
        for angle in doc["angles"]
    ]


def _bullets(title: str, items: list[str]) -> list[str]:
    if not items:
        return []
    return ["", f"**{title}:**", *[f"- {item}" for item in items]]


def starters_md(doc: BriefDoc, labels: Labels) -> str:
    lines: list[str] = []
    people = [person_text(person) for person in doc["people"]]
    if people:
        lines.append(f"**{labels['stakeholders']}:** {', '.join(people)}")
    if doc["fit"]["lead"].strip():
        lines.append(f"**{labels['best_first_question']}:** {doc['fit']['lead'].strip()}")
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
