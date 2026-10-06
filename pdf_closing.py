"""The end of the brief PDF: who to call, what is still unknown, and the sources."""

from typing import Sequence

from fpdf import FPDF

import brief_compat
import export_content
import pdf_canvas as canvas
import pdf_fonts
import pdf_parts as parts
import pdf_text
import pdf_theme as theme
from brief_doc import Person, Reference
from pdf_canvas import Part
from pdf_flow import Block
from pdf_parts import Context
from pdf_text import Color, Run

INNER_W = theme.CONTENT_W - 2 * theme.CARD_PAD
# Who to talk to: who on the left, why them on the right.
AVATAR = 7.8
AVATAR_GAP = 3.4
WHO_SHARE = 0.42
PERSON_PAD = 2.9
# What is still unknown: a dashed outline on the canvas, not a card, so it does not look settled.
OPEN_PAD = 5.4
UNCONFIRMED_SHARE = 7 / 12
MARK_W = 5.4
ITEM_GAP = 2.0
# Side by side while both lists are short; one under the other when either runs long.
MAX_SIDE_BY_SIDE = 110.0
SMALL_TICK = (1.1, 3.9)
SMALL_TICK_GAP = 0.85
# References: number, then title over address, then what kind of source and how it is dated.
NUMBER_W = 9.0
KIND_W = 31.0
DATE_W = 37.0
META_GAP = 6.0
REFERENCE_PAD = 2.9
MAX_ADDRESS_LINES = 1
KIND_TONE: dict[str, tuple[Color, Color]] = {
    "first_hand": (theme.POSITIVE, theme.POSITIVE_TINT),
    "second_hand": (theme.WARNING, theme.WARNING_TINT),
    "last_resort": (theme.NEGATIVE, theme.NEGATIVE_TINT),
}
NOTE_STYLE = theme.toned(theme.BODY, theme.INK_2)
INITIALS_STYLE = pdf_text.Style(theme.NAME.face, 7.4, theme.ACCENT, leading=1.0)


# ── Who to talk to ───────────────────────────────────────────────────────────

def _avatar(pdf: FPDF, x: float, y: float, name: str) -> None:
    """Initials for a person a source names; a dashed outline for a role nobody is named for yet."""
    centre = (x + AVATAR / 2, y + AVATAR / 2)
    if not name:
        canvas.ring(pdf, *centre, AVATAR / 2 - 0.2, theme.INK_3, dashed=True)
        _figure(pdf, *centre)
        return
    canvas.disc(pdf, *centre, AVATAR / 2, theme.ACCENT_TINT)
    letters = canvas.text([Run(export_content.initials(name), INITIALS_STYLE)], AVATAR, align="C")
    letters.paint(pdf, x, y + (AVATAR - letters.height) / 2)


def _figure(pdf: FPDF, cx: float, cy: float) -> None:
    """A small head and shoulders: somebody, not yet named."""
    canvas.ring(pdf, cx, cy - 0.95, 0.95, theme.INK_2)
    pdf.set_draw_color(*theme.INK_2)
    pdf.set_line_width(0.3)
    pdf.arc(cx - 1.8, cy + 0.55, 3.6, 180, 360, b=3.0)


def _person(ctx: Context, person: Person) -> Part:
    name, role, note = person["name"].strip(), person["role"].strip(), person["note"].strip()
    who_w = INNER_W * WHO_SHARE - AVATAR - AVATAR_GAP
    why_w = INNER_W * (1 - WHO_SHARE) - AVATAR_GAP
    who = canvas.stack(
        (0, canvas.words(name, theme.NAME, who_w)),
        (0.5, canvas.words(role, theme.SMALL if name else theme.BODY_MEDIUM, who_w)),
    )
    why = canvas.text(parts.with_chips([Run(note, NOTE_STYLE)] if note else [], person["sources"], ctx), why_w)
    height = max(AVATAR, who.height, why.height)
    # A name the fonts cannot set has no initials to show: it gets the outline of a role with no name.
    printed_name = pdf_fonts.clean(name).strip()
    printed_name = "" if printed_name == pdf_fonts.OMISSION else printed_name

    def paint(pdf: FPDF, x: float, y: float) -> None:
        _avatar(pdf, x, y + (height - AVATAR) / 2, printed_name)
        who.paint(pdf, x + AVATAR + AVATAR_GAP, y + (height - who.height) / 2)
        why.paint(pdf, x + INNER_W * WHO_SHARE + AVATAR_GAP, y + (height - why.height) / 2)

    return parts.ruled(Part(height, paint), INNER_W, pad_top=PERSON_PAD, pad_bottom=PERSON_PAD)


def people(ctx: Context) -> list[Block]:
    listed = [person for person in ctx.doc["people"] if brief_compat.person_text(person).strip()]
    rows = [(0.0, canvas.words(ctx.labels["who_to_talk_to"], theme.HEADING, INNER_W))]
    rows += [(3.6 if index == 0 else 0.0, _person(ctx, person)) for index, person in enumerate(listed)]
    body = canvas.stack(*rows)
    trimmed = Part(body.height - (PERSON_PAD if listed else 0.0), body.paint)
    breaks = parts.row_breaks([offset for offset, _ in canvas.placed(rows)[1:]])
    return [parts.card_block(trimmed, theme.CARD_GAP, breaks=breaks, splits_freely=bool(breaks))]


# ── What we couldn't confirm, and what would raise the score ─────────────────

def _open_mark(pdf: FPDF, x: float, y: float, raises: bool) -> None:
    """A question mark for something unknown; a rising arrow for something that would lift the score."""
    centre = (x + 1.75, y + 2.35)
    glyph, color = ("↑", theme.ACCENT) if raises else ("?", theme.INK_2)
    if raises:
        canvas.disc(pdf, *centre, 1.75, theme.mix(theme.ACCENT, theme.CANVAS, 0.12))
    else:
        canvas.ring(pdf, *centre, 1.6, theme.INK_3)
    mark = canvas.text([Run(glyph, pdf_text.Style(theme.NAME.face, 6.0, color, leading=1.0))], 3.5, align="C")
    mark.paint(pdf, x, centre[1] - mark.height / 2)


def _open_items(items: Sequence[str], room: float, raises: bool) -> list[Part]:
    return [
        canvas.behind(
            canvas.inset(canvas.words(item, theme.BODY, room - MARK_W), left=MARK_W),
            lambda pdf, x, y, height: _open_mark(pdf, x, y, raises),
        )
        for item in items if item.strip()
    ]


def _open_heading(ctx: Context, key: str, room: float) -> Part:
    """The list's heading. The one about the score carries the score's meter at its right."""
    heading = canvas.words(ctx.labels[key], theme.HEADING, room - (12.0 if key == "raise_score" else 0.0))
    if key != "raise_score":
        return heading
    score = ctx.doc["fit"]["score"]
    fill = theme.ACCENT if score >= export_content.STRONG_FROM else (
        theme.WARNING_FILL if score >= export_content.MODERATE_FROM else theme.INK_3
    )

    def paint(pdf: FPDF, x: float, y: float) -> None:
        heading.paint(pdf, x, y)
        meter_w = canvas.METER_TICKS * SMALL_TICK[0] + (canvas.METER_TICKS - 1) * SMALL_TICK_GAP
        canvas.meter(pdf, x + room - meter_w, y + 0.9, score, SMALL_TICK, SMALL_TICK_GAP, fill, theme.TRACK_ON_CANVAS)

    return Part(heading.height, paint)


def _open_rows(ctx: Context, key: str, room: float) -> list[tuple[float, Part]]:
    items = _open_items(ctx.doc[key], room, raises=key == "raise_score")
    if not items:
        return []
    return [(0.0, _open_heading(ctx, key, room)), (3.6, items[0]), *((ITEM_GAP, item) for item in items[1:])]


def _dashed_block(body: Part, breaks: Sequence[float], divider_x: float | None = None) -> Block:
    height = body.height + 2 * OPEN_PAD

    def paint(pdf: FPDF, y: float) -> None:
        canvas.outline_round(pdf, theme.MARGIN_X, y, theme.CONTENT_W, height, theme.CARD_RADIUS,
                             theme.DASH_ON_CANVAS, dashed=True)
        if divider_x is not None:
            canvas.upright(pdf, theme.MARGIN_X + divider_x, y, height, theme.DASH_ON_CANVAS, dashed=True)
        body.paint(pdf, theme.MARGIN_X + OPEN_PAD, y + OPEN_PAD)

    return Block(height, paint, theme.CARD_GAP, breaks=tuple(OPEN_PAD + mark for mark in breaks),
                 splits_freely=bool(breaks))


def open_questions(ctx: Context) -> list[Block]:
    """What the brief does not know and what would change its mind, in one dashed outline.

    The two lists sit side by side while both are short. When either runs
    long they are set one under the other, so the block can run over a page.
    """
    inner = theme.CONTENT_W - 2 * OPEN_PAD
    has_both = bool(ctx.doc["unconfirmed"]) and bool(ctx.doc["raise_score"])
    left_w = inner * UNCONFIRMED_SHARE - OPEN_PAD
    right_w = inner * (1 - UNCONFIRMED_SHARE) - OPEN_PAD
    left = canvas.stack(*_open_rows(ctx, "unconfirmed", left_w))
    right = canvas.stack(*_open_rows(ctx, "raise_score", right_w))
    if has_both and max(left.height, right.height) <= MAX_SIDE_BY_SIDE:
        divider = OPEN_PAD + inner * UNCONFIRMED_SHARE
        return [_dashed_block(canvas.beside((0, left), (divider, right)), (), divider_x=divider)]
    lists = [_open_rows(ctx, key, inner) for key in ("unconfirmed", "raise_score")]
    rows = [*lists[0], *((2 * OPEN_PAD if index == 0 and lists[0] else space, part)
                         for index, (space, part) in enumerate(lists[1]))]
    # A cut may fall above any row but the first item of a list, so a heading keeps its first item.
    headings = {0, len(lists[0])}
    breaks = [
        offset - space / 2
        for index, ((space, _), (offset, _)) in enumerate(zip(rows, canvas.placed(rows)))
        if index > 0 and index - 1 not in headings
    ]
    return [_dashed_block(canvas.stack(*rows), breaks)]


# ── References ───────────────────────────────────────────────────────────────

def _reference(ctx: Context, reference: Reference, is_anchor: bool) -> Part:
    """One source: its number, title and address, then how close it is to the company and how it is dated."""
    text_w = theme.CONTENT_W - NUMBER_W - KIND_W - DATE_W - 2 * META_GAP
    target = export_content.link_target(reference["url"])
    title = export_content.reference_title(reference, ctx.labels).strip()
    source = canvas.stack(
        (0, canvas.words(title, theme.BODY_MEDIUM, text_w)),
        (0.7, canvas.words(export_content.display_url(reference["url"]), theme.SMALL, text_w, MAX_ADDRESS_LINES)),
    )
    color, tint = KIND_TONE.get(reference["source_type"], KIND_TONE["second_hand"])
    kind = canvas.text([parts.pill(export_content.source_type_label(reference, ctx.labels), color, tint)], KIND_W)
    dated = canvas.text(parts.stamp(export_content.reference_date(reference, ctx.labels, ctx.language)), DATE_W)
    number = canvas.words(f"{reference['n']:02d}", theme.NUMBER, NUMBER_W)
    link = ctx.reference_links.get(reference["n"]) if is_anchor else None
    kind_x = NUMBER_W + text_w + META_GAP

    def paint(pdf: FPDF, x: float, y: float) -> None:
        if link is not None:
            pdf.anchor(link, y)
        number.paint(pdf, x, y + 0.75)
        source.paint(pdf, x + NUMBER_W, y)
        if target is not None and source.height:
            pdf.link(x + NUMBER_W, y, text_w, source.height, target)
        kind.paint(pdf, x + kind_x, y + 0.1)
        dated.paint(pdf, x + kind_x + KIND_W + META_GAP, y + 0.55)

    row = Part(max(source.height, kind.height, dated.height, number.height), paint)
    return parts.ruled(
        row, theme.CONTENT_W, pad_top=REFERENCE_PAD, pad_bottom=REFERENCE_PAD, color=theme.LINE_ON_CANVAS,
    )


def references(ctx: Context) -> list[Block]:
    """The sources, numbered as the markers above cite them. A marker jumps to the first row with its number."""
    listed = ctx.doc["references"]
    first_with = {reference["n"]: index for index, reference in reversed(list(enumerate(listed)))}
    rows = [(0.0, canvas.words(ctx.labels["references"], theme.HEADING, theme.CONTENT_W))]
    rows += [
        (3.4 if index == 0 else 0.0, _reference(ctx, reference, is_anchor=first_with[reference["n"]] == index))
        for index, reference in enumerate(listed)
    ]
    body = canvas.stack(*rows)
    # The list runs on over a page between rows. Its heading keeps its first two rows.
    starts = [offset for offset, _ in canvas.placed(rows)[1:]]
    breaks = tuple(parts.row_breaks(starts, keep_at_end=1))

    def paint(pdf: FPDF, y: float) -> None:
        body.paint(pdf, theme.MARGIN_X, y)
        canvas.rule(pdf, theme.MARGIN_X, y + body.height, theme.CONTENT_W, theme.LINE_ON_CANVAS)

    return [Block(body.height, paint, theme.SECTION_GAP, breaks=breaks, splits_freely=bool(breaks))]


def colophon(ctx: Context) -> Block:
    """How much research stands behind the brief, centred under everything else."""
    note = f"{export_content.research_note(ctx.doc, ctx.labels)}."
    line = canvas.text([Run(note, theme.SMALL)], theme.CONTENT_W, align="C")
    return parts.block(line, space_before=7.0)
