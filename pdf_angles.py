"""The angles of the brief PDF: each reason to call, the proof beside it, and its evidence.

A card has two bands, as on the page. The first is the pitch: the angle and
what Alkira does about it on the left, the proof on the right, on a plate
no taller than what it says. The second
is the evidence, in columns across the whole card. A card moves to the next
page whole when one can hold it; a longer one may be cut between rows of
evidence, and inside the pitch or the proof only when those alone are longer
than a page.
"""

from typing import Sequence

from fpdf import FPDF
from fpdf.pattern import LinearGradient

import export_content
import pdf_canvas as canvas
import pdf_fonts
import pdf_parts as parts
import pdf_theme as theme
from brief_doc import Angle, EvidenceLine
from export_content import Proof
from pdf_canvas import Part
from pdf_flow import Block
from pdf_parts import Context
from pdf_text import Run

# The proof sits close to the card's edge, as a plate set into it.
PLATE_SHARE = 0.38
PLATE_INSET = 2.0
PLATE_PAD = 5.0
PLATE_LABEL_GAP = 4.0
PLATE_GLOW_REACH = 58.0
HATCH_STEP = 2.2
HATCH_SHARE = 0.55
# A pending or completed deal marks its card with a warm wash from the top.
WASH_HEIGHT = 22.0
QUOTE_RULE_W = 0.6
QUOTE_INDENT = 3.0
# Evidence: the mark, then the fact indented beside it.
FACT_INDENT = 4.6
DOT_X = 1.3
COLUMN_GAP = 7.0
ROW_GAP = 3.0
MAX_COLUMNS = 3
FIRST_CARD_GAP = 3.2


def evidence_columns(count: int) -> int:
    """How many columns an angle's evidence is set in: one fact alone, pairs for two and four, else threes."""
    if count <= 1:
        return 1
    return 2 if count % MAX_COLUMNS and count % 2 == 0 else MAX_COLUMNS


# ── The pitch ────────────────────────────────────────────────────────────────

def _tags(ctx: Context, number: int, angle: Angle, room: float) -> Part:
    """The angle's number and use case, and for an M&A angle its deal's status and date."""
    status, when = export_content.deal_parts(angle, ctx.labels, ctx.language)
    is_pending = angle["deal_status"] == "pending"
    tone = theme.WARNING if is_pending else theme.ACCENT
    runs = [
        Run(f"{number:02d}", theme.toned(theme.NUMBER, theme.SURFACE), chip=theme.pill(theme.INK)),
        Run(" ", theme.PILL),
        parts.pill(export_content.use_case_name(angle["use_case"], ctx.labels), theme.INK_2,
                   theme.SURFACE if status else theme.SUNKEN, theme.LINE if status else None),
    ]
    if status:
        tint = theme.WARNING_TINT if is_pending else theme.ACCENT_TINT
        runs += [Run(" ", theme.PILL), parts.pill(status, tone, tint)]
    if when:
        runs += [Run("  ", theme.PILL), Run(when, theme.toned(theme.STAMP, tone))]
    return canvas.text(runs, room)


def _quote(angle: Angle, room: float) -> Part:
    """For a pending deal, the source's own words on timing, behind an amber rule."""
    quote = angle["deal_pending_quote"].strip()
    if not quote:
        return canvas.EMPTY
    words = canvas.words(f"“{quote}”", theme.toned(theme.SMALL, theme.INK_2), room - QUOTE_INDENT)

    def rule(pdf: FPDF, x: float, y: float, height: float) -> None:
        canvas.fill_round(pdf, x, y + 0.5, QUOTE_RULE_W, height - 1.0, QUOTE_RULE_W / 2, theme.WARNING_FILL)

    return canvas.behind(canvas.inset(words, left=QUOTE_INDENT), rule)


def _pitch(ctx: Context, number: int, angle: Angle, room: float) -> Part:
    # A card is never left without a name: its number stands in for a missing title.
    title = angle["title"].strip() or f"{ctx.labels['angle']} {number}"
    answer = angle["alkira"].strip()
    return canvas.stack(
        (0, _tags(ctx, number, angle, room)),
        (2.8, canvas.words(title, theme.ANGLE_TITLE, room)),
        (2.0, _quote(angle, room)),
        (3.6, canvas.label(ctx.labels["alkira_answer"], theme.MICRO_ACCENT, room) if answer else canvas.EMPTY),
        (1.6, canvas.words(answer, theme.BODY, room)),
    )


# ── The proof plate ──────────────────────────────────────────────────────────

def _story_statement(proof: Proof, room: float) -> Part:
    """A named customer's result: the name the largest type in the card, its numbers picked out."""
    result = [
        Run(piece, theme.RESULT_NUMBER if is_number else theme.RESULT)
        for piece, is_number in export_content.emphasise_numbers(pdf_fonts.clean(proof.result))
    ]
    return canvas.stack(
        (0, canvas.words(proof.customer, theme.CUSTOMER, room)),
        (1.2, canvas.words(proof.qualifier, theme.QUALIFIER, room)),
        (2.6, canvas.text(result, room)),
    )


def _metric_statement(proof: Proof, room: float) -> Part:
    """A knowledge-base figure: the number large, what it measures, and that no customer is behind it."""
    return canvas.stack(
        (0, canvas.words(proof.figure, theme.FIGURE, room)),
        (2.6, canvas.words(proof.name, theme.BODY_MEDIUM, room)),
        (0.8 if proof.figure else 0, canvas.words(proof.result, theme.BODY if not proof.figure else theme.SMALL, room)),
        (2.4, canvas.words(proof.note, theme.SMALL, room)),
    )


def _hatch(pdf: FPDF, x: float, y: float, w: float, h: float) -> None:
    """Fine diagonal lines over the right of a metric plate: a figure, set apart from a customer's story."""
    pdf.set_draw_color(*theme.HATCH)
    pdf.set_line_width(0.12)
    left = x + w * (1 - HATCH_SHARE)
    with pdf.rect_clip(left, y + theme.INNER_RADIUS, w * HATCH_SHARE - theme.INNER_RADIUS, h - 2 * theme.INNER_RADIUS):
        offset = 0.0
        while offset < w * HATCH_SHARE + h:
            pdf.line(left + offset, y, left + offset - h, y + h)
            offset += HATCH_STEP


def _plate(proof: Proof, width: float) -> Part:
    """The proof, as tall as what it holds: its label, then its statement directly under it."""
    room = width - 2 * PLATE_PAD
    is_story = proof.kind == "story"
    statement = _story_statement(proof, room) if is_story else _metric_statement(proof, room)
    name = canvas.label(proof.label, theme.EYEBROW if is_story else theme.MICRO, room)
    height = name.height + PLATE_LABEL_GAP + statement.height + 2 * PLATE_PAD

    def paint(pdf: FPDF, x: float, y: float) -> None:
        canvas.fill_round(pdf, x, y, width, height, theme.INNER_RADIUS, theme.AMBIENT if is_story else theme.SUNKEN)
        if is_story:
            canvas.glow(pdf, (x, y, width, height), theme.INNER_RADIUS, (x + width, y), PLATE_GLOW_REACH,
                        theme.AMBIENT_GLOW, theme.AMBIENT)
        else:
            _hatch(pdf, x, y, width, height)
        name.paint(pdf, x + PLATE_PAD, y + PLATE_PAD)
        statement.paint(pdf, x + PLATE_PAD, y + PLATE_PAD + name.height + PLATE_LABEL_GAP)

    return Part(height, paint)


# ── The evidence ─────────────────────────────────────────────────────────────

def _fact(ctx: Context, line: EvidenceLine, room: float) -> Part:
    """One fact: when its source is dated and the sources it rests on, then the fact."""
    date = export_content.evidence_date(line, ctx.doc["references"], ctx.labels, ctx.language)
    dated = parts.stamp(date)
    chips = parts.source_chips(line["sources"], ctx)
    lead = [*dated, *([Run(parts.MARK_GAP, theme.NUMBER)] if dated and chips else []), *chips]
    body = canvas.stack(
        (0, canvas.text(lead, room - FACT_INDENT)),
        (0.9, canvas.words(line["text"], theme.FACT, room - FACT_INDENT)),
    )
    return canvas.behind(
        canvas.inset(body, left=FACT_INDENT),
        lambda pdf, x, y, height: parts.date_dot(pdf, x + DOT_X, y + 1.9, date.kind),
    )


def _evidence_rows(ctx: Context, evidence: Sequence[EvidenceLine], room: float) -> list[Part]:
    """The facts as rows of two or three across the card, so a long list adds little height."""
    columns = evidence_columns(len(evidence))
    column_w = (room - (columns - 1) * COLUMN_GAP) / columns
    facts = [_fact(ctx, line, column_w) for line in evidence if line["text"].strip()]
    step = column_w + COLUMN_GAP
    return [
        canvas.beside(*((index * step, fact) for index, fact in enumerate(facts[start:start + columns])))
        for start in range(0, len(facts), columns)
    ]


# ── The card ─────────────────────────────────────────────────────────────────

def _wash(pdf: FPDF, x: float, y: float, w: float) -> None:
    """A warm wash down from the top of a card: the angle with a clock on it."""
    warm = theme.mix(theme.WARNING_TINT, theme.SURFACE, 0.9)
    fade = LinearGradient(x, y, x, y + WASH_HEIGHT, colors=[warm, theme.SURFACE])
    with pdf.use_pattern(fade):
        pdf.rect(x, y, w, WASH_HEIGHT, style="F", round_corners=True, corner_radius=theme.CARD_RADIUS)


def _card(ctx: Context, number: int, angle: Angle, space_before: float) -> Block:
    proof = export_content.proof(angle["story"], ctx.labels)
    plate_w = (theme.CONTENT_W - 2 * PLATE_INSET) * PLATE_SHARE if proof else 0.0
    pitch_w = theme.CONTENT_W - 2 * theme.CARD_PAD - (plate_w + PLATE_INSET if proof else 0.0)
    pitch = _pitch(ctx, number, angle, pitch_w)
    plate = _plate(proof, plate_w) if proof else canvas.EMPTY
    band_h = max(pitch.height + 2 * theme.CARD_PAD, plate.height + 2 * PLATE_INSET)
    rows = _evidence_rows(ctx, angle["evidence"], theme.CONTENT_W - 2 * theme.CARD_PAD)
    name = canvas.label(ctx.labels["evidence"], theme.MICRO, theme.CONTENT_W)
    listed = canvas.placed([(0, name), (2.4, rows[0]), *((ROW_GAP, row) for row in rows[1:])]) if rows else []
    evidence_h = (listed[-1][0] + listed[-1][1].height + 2 * theme.CARD_PAD) if listed else 0.0
    height = band_h + evidence_h
    has_deal = angle["deal_status"] in ("pending", "completed")
    link = ctx.angle_links.get(number)

    def paint(pdf: FPDF, y: float) -> None:
        x, w = theme.MARGIN_X, theme.CONTENT_W
        canvas.card(pdf, x, y, w, height)
        if has_deal:
            _wash(pdf, x + 0.2, y + 0.2, w - 0.4)
        if link is not None:
            pdf.anchor(link, y)
        pitch.paint(pdf, x + theme.CARD_PAD, y + theme.CARD_PAD)
        plate.paint(pdf, x + w - PLATE_INSET - plate_w, y + PLATE_INSET)
        if listed:
            canvas.rule(pdf, x, y + band_h, w)
        for offset, part in listed:
            part.paint(pdf, x + theme.CARD_PAD, y + band_h + theme.CARD_PAD + offset)

    # Between the pitch and the evidence, then between rows of evidence, half-way down the gap.
    breaks = (band_h, *(band_h + theme.CARD_PAD + offset - ROW_GAP / 2 for offset, _ in listed[2:]))
    return Block(height, paint, space_before, breaks=breaks if listed else ())


def blocks(ctx: Context) -> list[Block]:
    """The section heading, then a card for every angle the brief has."""
    heading = canvas.words(ctx.labels["why_now"], theme.SECTION, theme.CONTENT_W)
    cards = [
        _card(ctx, number, angle, FIRST_CARD_GAP if number == 1 else theme.CARD_GAP)
        for number, angle in enumerate(ctx.doc["angles"], start=1)
    ]
    return [parts.block(heading, theme.SECTION_GAP, keep_with_next=True), *cards]
