"""PDF for a brief stored as a JSON document.

The legacy renderer in pdf.py lays out markdown sections in fixed tiles.
A brief document has one to three angles and sections of any length, so
this renderer flows down the page instead, reusing pdf.py's page chrome,
palette and text sanitizer.
"""

from datetime import datetime

import brief_compat
import i18n
from brief_doc import Angle, BriefDoc
from pdf import (
    ALKIRA_BLUE, ALKIRA_INK, ALKIRA_MUTED, ALKIRA_ORANGE, ALKIRA_WHITE, _BriefPDF, _safe_text,
)

LEFT = 12.7
CONTENT_W = 190.5
SCORE_TILE_W = 30.0
SCORE_TILE_H = 24.0
SNAPSHOT_LABEL_W = 42.0
BULLET_INDENT = 4.0
SNAPSHOT_KEYS = (
    "clouds", "cloud_connectivity", "wan", "firewalls", "data_centers", "plant_networks",
)
Color = tuple[int, int, int]


def _text(
    pdf: _BriefPDF, text: str, size: float = 9, style: str = "",
    color: Color = ALKIRA_INK, indent: float = 0.0,
) -> None:
    """One left-aligned paragraph across the content width, below the last one."""
    if not text.strip():
        return
    pdf.set_font("Helvetica", style, size)
    pdf.set_text_color(*color)
    pdf.set_x(LEFT + indent)
    pdf.multi_cell(
        CONTENT_W - indent, size * 0.5, _safe_text(text),
        align="L", new_x="LMARGIN", new_y="NEXT",
    )


def _heading(pdf: _BriefPDF, label: str) -> None:
    pdf.ln(4)
    _text(pdf, label.upper(), size=8, style="B", color=ALKIRA_BLUE)
    pdf.ln(1)


def _bullets(pdf: _BriefPDF, items: list[str], size: float = 9) -> None:
    for item in items:
        _text(pdf, f"- {item}", size=size, indent=BULLET_INDENT)


def _hero(pdf: _BriefPDF, doc: BriefDoc) -> None:
    labels = pdf.labels
    _text(pdf, doc["company"]["name"] or "Untitled Brief", size=22, style="B")
    pdf.ln(1)
    _text(pdf, brief_compat.stats_line(doc, labels), size=9, color=ALKIRA_MUTED)
    note = doc["company"]["identity_note"].strip()
    if note:
        _text(pdf, f"{labels['identity']}: {note}", size=8, style="I", color=ALKIRA_MUTED)
    pdf.ln(3)


def _fit(pdf: _BriefPDF, doc: BriefDoc) -> None:
    """The score in a blue tile, with the verdict and the lead line beside it."""
    labels = pdf.labels
    top = pdf.get_y()
    pdf.set_fill_color(*ALKIRA_BLUE)
    pdf.rect(LEFT, top, SCORE_TILE_W, SCORE_TILE_H, style="F")
    pdf.set_text_color(*ALKIRA_WHITE)
    pdf.set_font("Helvetica", "B", 7)
    pdf.set_xy(LEFT + 3, top + 3)
    pdf.cell(SCORE_TILE_W - 6, 3.5, _safe_text(labels["alkira_fit"].upper()))
    pdf.set_font("Helvetica", "B", 26)
    pdf.set_xy(LEFT + 3, top + 9)
    pdf.cell(SCORE_TILE_W - 6, 11, f"{doc['fit']['score']} / 5")

    beside = SCORE_TILE_W + 5
    pdf.set_y(top)
    _text(pdf, doc["fit"]["verdict"], size=11, style="B", indent=beside)
    lead = doc["fit"]["lead"].strip()
    if lead:
        pdf.ln(1)
        _text(pdf, f"{labels['lead']}: {lead}", size=9, indent=beside)
    pdf.set_y(max(pdf.get_y(), top + SCORE_TILE_H) + 2)


def _angle(pdf: _BriefPDF, number: int, angle: Angle) -> None:
    labels = pdf.labels
    pdf.ln(2)
    _text(pdf, f"{labels['angle'].upper()} {number:02d}", size=7, style="B", color=ALKIRA_ORANGE)
    _text(pdf, angle["title"], size=11, style="B")
    _bullets(pdf, [brief_compat.evidence_text(line, pdf.labels, pdf.language) for line in angle["evidence"]])
    _text(pdf, f"{labels['alkira_answer']}: {angle['alkira']}", size=9)
    proof = brief_compat.proof_text(angle["story"])
    if proof:
        label = "proof_point" if brief_compat.is_proof_point(angle["story"]) else "customer_story"
        _text(pdf, f"{labels[label]}: {proof}", size=9, color=ALKIRA_MUTED)


def _angles(pdf: _BriefPDF, doc: BriefDoc) -> None:
    if not doc["angles"]:
        return
    _heading(pdf, pdf.labels["why_now"])
    for number, angle in enumerate(doc["angles"], start=1):
        _angle(pdf, number, angle)


def _snapshot(pdf: _BriefPDF, doc: BriefDoc) -> None:
    labels = pdf.labels
    _heading(pdf, labels["technical_snapshot"])
    for key in SNAPSHOT_KEYS:
        top = pdf.get_y()
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*ALKIRA_BLUE)
        pdf.set_xy(LEFT, top)
        pdf.cell(SNAPSHOT_LABEL_W, 4.5, _safe_text(labels["snap_" + key]))
        pdf.set_y(top)
        line = doc["snapshot"][key]
        color = ALKIRA_INK if line["text"] else ALKIRA_MUTED
        _text(pdf, brief_compat.snapshot_text(line, labels), size=9, color=color, indent=SNAPSHOT_LABEL_W)
        pdf.ln(0.5)


def _people(pdf: _BriefPDF, doc: BriefDoc) -> None:
    if not doc["people"]:
        return
    _heading(pdf, pdf.labels["who_to_talk_to"])
    lines = []
    for person in doc["people"]:
        who = brief_compat.person_text(person)
        note = f": {person['note']}" if person["note"].strip() else ""
        lines.append(f"{who}{note}{brief_compat.cite(person['sources'])}")
    _bullets(pdf, lines)


def _questions(pdf: _BriefPDF, doc: BriefDoc) -> None:
    if not doc["questions"]:
        return
    labels = pdf.labels
    _heading(pdf, labels["questions"])
    for number, item in enumerate(doc["questions"], start=1):
        _text(pdf, f"{number}. {item['question']}", size=9, style="B")
        _text(pdf, f"{labels['listen_for']}: {item['listen_for']}", size=8, color=ALKIRA_MUTED, indent=BULLET_INDENT)
        _text(pdf, f"{labels['alkira_angle']}: {item['alkira_angle']}", size=8, color=ALKIRA_MUTED, indent=BULLET_INDENT)
        pdf.ln(1)


def _notes(pdf: _BriefPDF, doc: BriefDoc) -> None:
    for key in ("unconfirmed", "raise_score"):
        if doc[key]:
            _heading(pdf, pdf.labels[key])
            _bullets(pdf, doc[key])


def _references(pdf: _BriefPDF, doc: BriefDoc) -> None:
    if not doc["references"]:
        return
    _heading(pdf, pdf.labels["references"])
    for reference in doc["references"]:
        _text(pdf, brief_compat.reference_text(reference, pdf.labels), size=8)


def render(doc: BriefDoc, generated_at: datetime, language: str | None = None) -> bytes:
    """The brief document as PDF bytes, in the document's own language by default."""
    code = i18n.normalize(language or doc["language"])
    pdf = _BriefPDF(generated_at=generated_at, language=code)
    pdf.add_page()
    for section in (_hero, _fit, _angles, _snapshot, _people, _questions, _notes, _references):
        section(pdf, doc)
    return bytes(pdf.output())
