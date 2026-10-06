"""PDF for a brief stored as a JSON document, laid out like the brief page.

A designed US Letter document in the site's own type and colours, in the
page's order: whose brief it is, the verdict on the dark panel, the angles
with their proof and evidence, what to ask, the engineer's spec sheet, who
to call, what is still unknown, and the sources. Legacy markdown briefs are
not drawn here: pdf.py still lays those out in its fixed tiles.

How it is put together:

- export_content.py says what the brief says (shared with the Word export);
- each section builds ``Block``s, measured before anything is drawn
  (pdf_opening, pdf_angles, pdf_sections, pdf_closing);
- pdf_flow.py chooses the page breaks, then every block paints itself.
"""

from datetime import datetime
from typing import Callable, Iterable

import export_content
import i18n
import pdf_angles
import pdf_closing
import pdf_flow
import pdf_opening
import pdf_sections
import pdf_theme as theme
from brief_doc import BriefDoc
from pdf_canvas import BriefPDF, Chrome
from pdf_flow import Block, PageFrame
from pdf_parts import Context

FRAME = PageFrame(first_top=theme.CONTENT_TOP, top=theme.CONTENT_TOP, bottom=theme.CONTENT_BOTTOM)
SectionBuilder = Callable[[Context], list[Block]]
FIRST_PAGE = 1


def _raise_score_alone(ctx: Context) -> list[Block]:
    """What would raise the score shares a block with what could not be confirmed, when the brief has both."""
    return [] if ctx.doc["unconfirmed"] else pdf_closing.open_questions(ctx)


# How each section of export_content.outline is drawn.
BUILDERS: dict[str, SectionBuilder] = {
    "fit": pdf_opening.verdict,
    "why_now": pdf_angles.blocks,
    "ask_this": pdf_sections.questions,
    "for_engineer": pdf_sections.engineer_sheet,
    "who_to_talk_to": pdf_closing.people,
    "unconfirmed": pdf_closing.open_questions,
    "raise_score": _raise_score_alone,
    "references": pdf_closing.references,
}


def _blocks(ctx: Context) -> list[Block]:
    """Everything in the brief, top to bottom, measured and not yet placed."""
    blocks = [pdf_opening.masthead(ctx)]
    for section in export_content.outline(ctx.doc, ctx.labels):
        blocks += BUILDERS[section.key](ctx)
    return [*blocks, pdf_closing.colophon(ctx)]


def title(doc: BriefDoc, labels: dict[str, str]) -> str:
    """What the document is called in a viewer's title bar: the company, then what this is."""
    company = doc["company"]["name"].strip()
    return f"{company}: {labels['brief_title']}" if company else labels["brief_title"]


def _chrome(doc: BriefDoc, generated_at: datetime, labels: dict[str, str], language: str) -> Chrome:
    made = i18n.readable_date(generated_at.strftime("%Y-%m-%d"), language)
    return Chrome(
        confidential=labels["confidential"],
        company=doc["company"]["name"].strip(),
        generated=labels["generated_on"].format(date=made),
        page_label=labels["page_of"],
    )


def _links(pdf: BriefPDF, numbers: Iterable[int]) -> dict[int, int]:
    """An internal link for each number, to be pointed at its target when the target is drawn.

    fpdf2 will not draw a link that has no page yet, so each starts out at
    the top of the first page.
    """
    return {number: pdf.add_link(page=FIRST_PAGE) for number in dict.fromkeys(numbers)}


def render(doc: BriefDoc, generated_at: datetime, language: str | None = None) -> bytes:
    """The brief document as PDF bytes, in the document's own language by default."""
    code = i18n.normalize(language or doc["language"])
    labels = i18n.labels(code)
    pdf = BriefPDF(_chrome(doc, generated_at, labels, code))
    pdf.set_title(title(doc, labels))
    pdf.set_lang(code)
    ctx = Context(
        doc=doc, labels=labels, language=code,
        reference_links=_links(pdf, (reference["n"] for reference in doc["references"])),
        angle_links=_links(pdf, range(1, len(doc["angles"]) + 1)),
    )
    slices = pdf_flow.paginate(_blocks(ctx), FRAME)
    pdf.page_total = pdf_flow.page_count(slices)
    pdf_flow.paint(pdf, slices)
    return bytes(pdf.output())
