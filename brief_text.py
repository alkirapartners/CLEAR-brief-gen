"""A brief document as plain readable text, for the command line and for review.

The web page and the PDF are how partners read a brief. This is for a
person comparing a generated brief with one written by hand.
"""

import brief_compat
import i18n
from brief_doc import SNAPSHOT_KEYS, BriefDoc


def _section(title: str, lines: list[str]) -> list[str]:
    return ["", f"## {title}", *lines] if lines else []


def _angles(doc: BriefDoc, labels: dict[str, str]) -> list[str]:
    lines: list[str] = []
    for number, angle in enumerate(doc["angles"], start=1):
        lines += [f"### {number}. {angle['title']} ({angle['use_case']})"]
        lines += [f"- {brief_compat.evidence_text(line)}" for line in angle["evidence"]]
        lines += [f"{labels['alkira_answer']}: {angle['alkira']}"]
        proof = brief_compat.proof_text(angle["story"])
        if proof:
            lines += [f"{labels['customer_story']}: {proof}"]
        lines += [""]
    return lines[:-1]


def _people(doc: BriefDoc) -> list[str]:
    lines = []
    for person in doc["people"]:
        note = f": {person['note']}" if person["note"].strip() else ""
        lines.append(f"- {brief_compat.person_text(person)}{note}{brief_compat.cite(person['sources'])}")
    return lines


def _questions(doc: BriefDoc, labels: dict[str, str]) -> list[str]:
    lines = []
    for number, item in enumerate(doc["questions"], start=1):
        lines += [
            f"{number}. {item['question']}",
            f"   {labels['listen_for']}: {item['listen_for']}",
            f"   {labels['alkira_angle']}: {item['alkira_angle']}",
        ]
    return lines


def render(doc: BriefDoc) -> str:
    """The whole brief as markdown-flavoured text in the brief's own language."""
    labels = i18n.labels(doc["language"])
    fit = doc["fit"]
    research = doc["research"]
    lines = [f"# {doc['company']['name']}", brief_compat.stats_line(doc, labels)]
    if doc["company"]["identity_note"].strip():
        lines.append(f"{labels['identity']}: {doc['company']['identity_note'].strip()}")
    lines += ["", f"## {labels['alkira_fit']}: {fit['score']} / 5", fit["verdict"]]
    if fit["lead"].strip():
        lines.append(f"{labels['lead']}: {fit['lead'].strip()}")
    lines += _section(labels["why_now"], _angles(doc, labels))
    lines += _section(labels["technical_snapshot"], [
        f"- {labels['snap_' + key]}: {brief_compat.snapshot_text(doc['snapshot'][key], labels)}"
        for key in SNAPSHOT_KEYS
    ])
    lines += _section(labels["who_to_talk_to"], _people(doc))
    lines += _section(labels["questions"], _questions(doc, labels))
    lines += _section(labels["unconfirmed"], [f"- {item}" for item in doc["unconfirmed"]])
    lines += _section(labels["raise_score"], [f"- {item}" for item in doc["raise_score"]])
    lines += _section(labels["references"], [
        brief_compat.reference_text(reference, labels) for reference in doc["references"]
    ])
    lines += ["", (
        f"Research: {research['searches']} searches, {research['pages']} pages opened, "
        f"{research['seconds']} s, stopped by {research['stopped_by']}. Generated {doc['generated']}."
    )]
    return "\n".join(lines) + "\n"
