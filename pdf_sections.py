"""The middle of the brief PDF: what to ask, and what an engineer wants to know."""

from fpdf import FPDF

import export_content
import pdf_canvas as canvas
import pdf_parts as parts
import pdf_theme as theme
import tech_terms
from brief_doc import SNAPSHOT_KEYS, Question, SnapshotLine
from pdf_canvas import Part
from pdf_flow import Block
from pdf_parts import Context
from pdf_text import Color, Run

INNER_W = theme.CONTENT_W - 2 * theme.CARD_PAD
# A question: its number in the margin, then the question and its two notes.
NUMBER_W = 8.6
QUESTION_PAD = 4.2
NOTE_LABEL_W = 30.0
NOTE_PAD_X = 3.6
NOTE_PAD_Y = 2.1
NOTE_SEAM = 0.35
# The spec sheet: what each line is, then what was found, with a mark that says whether it was.
SHEET_LABEL_W = 44.0
LABEL_INDENT = 5.0
LABEL_DROP = 1.0
MARK_X = 1.3
MARK_Y = 2.1
MARK_RADIUS = 1.05
ROW_PAD = 2.25


# ── Ask this ─────────────────────────────────────────────────────────────────

def _note(name: str, content: str, room: float, accent: bool) -> Part:
    """One labelled row under a question: the label in its own column, so the two rows line up."""
    style = theme.MICRO_ACCENT if accent else theme.MICRO
    words = canvas.words(content, theme.BODY, room - NOTE_LABEL_W - 2 * NOTE_PAD_X)
    if not words.height:
        return canvas.EMPTY
    row = canvas.beside(
        (NOTE_PAD_X, canvas.inset(canvas.label(name, style, NOTE_LABEL_W), top=1.3)),
        (NOTE_PAD_X + NOTE_LABEL_W, words),
    )
    return canvas.inset(row, top=NOTE_PAD_Y, bottom=NOTE_PAD_Y)


def _notes(ctx: Context, item: Question, room: float) -> Part:
    """What to listen for on a neutral tint and Alkira's angle on a blue one, as one rounded box."""
    listen = _note(ctx.labels["listen_for"], item["listen_for"], room, accent=False)
    angle = _note(ctx.labels["alkira_angle"], item["alkira_angle"], room, accent=True)
    rows = [(row, fill) for row, fill in ((listen, theme.SUNKEN), (angle, theme.ACCENT_WASH)) if row.height]
    height = sum(row.height for row, _ in rows) + NOTE_SEAM * (len(rows) - 1)

    def paint(pdf: FPDF, x: float, y: float) -> None:
        top = y
        for index, (row, fill) in enumerate(rows):
            _tinted_row(pdf, x, top, room, row.height, fill, is_first=index == 0, is_last=index == len(rows) - 1)
            row.paint(pdf, x, top)
            top += row.height + NOTE_SEAM

    return Part(height if rows else 0.0, paint)


def _tinted_row(
    pdf: FPDF, x: float, y: float, w: float, h: float, fill: Color, is_first: bool, is_last: bool,
) -> None:
    """A band of the notes box: rounded where it is the box's top or foot, square where it meets the other."""
    canvas.fill_round(pdf, x, y, w, h, theme.INNER_RADIUS, fill)
    pdf.set_fill_color(*fill)
    half = h / 2
    if not is_first:
        pdf.rect(x, y, w, half, style="F")
    if not is_last:
        pdf.rect(x, y + half, w, half, style="F")


def _angle_tag(ctx: Context, item: Question, room: float) -> Part:
    """Which angle a question is about: its use case, jumping up to the angle's card."""
    number = item["angle"]
    if not 0 < number <= len(ctx.doc["angles"]):
        return canvas.EMPTY
    name = export_content.use_case_name(ctx.doc["angles"][number - 1]["use_case"], ctx.labels)
    tag = Run(name, theme.PILL, link=ctx.angle_links.get(number), chip=theme.pill(theme.SUNKEN))
    return canvas.text([tag], room)


def _question(ctx: Context, number: int, item: Question) -> Part:
    room = INNER_W - NUMBER_W
    body = canvas.stack(
        (0, canvas.words(item["question"], theme.QUESTION, room)),
        (2.0, _angle_tag(ctx, item, room)),
        (2.6, _notes(ctx, item, room)),
    )
    count = canvas.words(f"{number:02d}", theme.toned(theme.NUMBER, theme.ACCENT), NUMBER_W)
    row = canvas.beside((0, canvas.inset(count, top=1.15)), (NUMBER_W, body))
    return parts.ruled(row, INNER_W, pad_top=QUESTION_PAD, pad_bottom=QUESTION_PAD)


def questions(ctx: Context) -> list[Block]:
    """The questions to ask, each kept whole on a page, in one card that may run on to the next."""
    rows = [(0.0, canvas.words(ctx.labels["ask_this"], theme.HEADING, INNER_W))]
    rows += [
        (3.6 if number == 1 else 0.0, _question(ctx, number, item))
        for number, item in enumerate(export_content.asked(ctx.doc), start=1)
    ]
    places = canvas.placed(rows)
    body = canvas.stack(*rows)
    # The last question's padding is the card's own, so it is taken back.
    trimmed = Part(body.height - QUESTION_PAD, body.paint)
    return [parts.card_block(trimmed, theme.CARD_GAP, breaks=[offset for offset, _ in places[2:]], splits_freely=True)]


# ── For the engineer ─────────────────────────────────────────────────────────

def _value(ctx: Context, line: SnapshotLine, room: float) -> Part:
    """A snapshot line with its products, vendors and protocols in mono, then its sources."""
    content = line["text"].strip()
    if not content:
        return canvas.words(ctx.labels["not_found_public"], theme.BODY_MUTED, room)
    runs = [
        Run(piece, theme.TERM, chip=theme.TERM_CHIP) if is_term else Run(piece, theme.BODY)
        for piece, is_term in tech_terms.tokenize(content)
    ]
    return canvas.text(parts.with_chips(runs, line["sources"], ctx), room)


def _found_mark(pdf: FPDF, x: float, y: float, is_found: bool) -> None:
    """A solid dot for a line the research found, a hollow one for a gap: the marks the evidence uses."""
    if is_found:
        canvas.disc(pdf, x + MARK_X, y + MARK_Y, MARK_RADIUS, theme.ACCENT)
    else:
        canvas.ring(pdf, x + MARK_X, y + MARK_Y, MARK_RADIUS, theme.INK_3, dashed=True)


def _sheet_row(ctx: Context, key: str) -> Part:
    """One line of the sheet: what it is on the left, what the research found on the right."""
    line = ctx.doc["snapshot"][key]
    is_found = bool(line["text"].strip())
    name = canvas.label(ctx.labels[f"snap_{key}"], theme.MICRO, SHEET_LABEL_W - LABEL_INDENT)
    row = canvas.beside(
        (LABEL_INDENT, canvas.inset(name, top=LABEL_DROP)),
        (SHEET_LABEL_W, _value(ctx, line, INNER_W - SHEET_LABEL_W)),
    )
    marked = canvas.behind(row, lambda pdf, x, y, height: _found_mark(pdf, x, y, is_found))
    return parts.ruled(marked, INNER_W, pad_top=ROW_PAD, pad_bottom=ROW_PAD)


def engineer_sheet(ctx: Context) -> list[Block]:
    """The technical snapshot as a spec sheet. Every line is listed: a known gap is useful too."""
    rows = [
        (0.0, canvas.label(ctx.labels["technical_snapshot"], theme.MICRO, INNER_W)),
        (1.6, canvas.words(ctx.labels["for_engineer"], theme.HEADING, INNER_W)),
        *((3.6 if index == 0 else 0.0, _sheet_row(ctx, key)) for index, key in enumerate(SNAPSHOT_KEYS)),
    ]
    body = canvas.stack(*rows)
    trimmed = Part(body.height - ROW_PAD, body.paint)
    starts = [offset for offset, _ in canvas.placed(rows)[2:]]
    return [parts.card_block(trimmed, theme.CARD_GAP, breaks=parts.row_breaks(starts), splits_freely=True)]
