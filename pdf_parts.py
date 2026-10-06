"""Small pieces the sections of the brief PDF share: source markers, pills, date stamps, cards."""

from dataclasses import dataclass
from typing import Mapping, Sequence

from fpdf import FPDF

import pdf_canvas as canvas
import pdf_theme as theme
from brief_doc import BriefDoc
from export_content import DateNote
from pdf_canvas import Part
from pdf_flow import Block
from pdf_text import Color, Run

Labels = dict[str, str]

# A fact's date reads in the colour of what it means; the words carry the meaning too.
DATE_COLOR: dict[str, Color] = {"dated": theme.INK_2, "open": theme.POSITIVE, "undated": theme.WARNING}
MARK_GAP = "  "
CAPSULE_HEIGHT = 5.6
CAPSULE_PAD = 2.4
MIN_ROWS_TOGETHER = 2


@dataclass(frozen=True)
class Context:
    """What every section is drawn from: the brief, its language, and where its links land."""

    doc: BriefDoc
    labels: Labels
    language: str
    # fpdf2's internal link for each reference number and each angle number.
    reference_links: Mapping[int, int]
    angle_links: Mapping[int, int]


def source_chips(sources: Sequence[int], ctx: Context) -> list[Run]:
    """One numbered marker per source. A marker whose reference exists jumps to it."""
    runs: list[Run] = []
    for number in sources:
        if runs:
            runs.append(Run(" ", theme.NUMBER))
        runs.append(Run(str(number), theme.NUMBER, link=ctx.reference_links.get(number), chip=theme.SOURCE_CHIP))
    return runs


def with_chips(runs: Sequence[Run], sources: Sequence[int], ctx: Context) -> list[Run]:
    """Text followed by its source markers, when it has any."""
    chips = source_chips(sources, ctx)
    return [*runs, Run(MARK_GAP, theme.NUMBER), *chips] if chips else list(runs)


def pill(content: str, color: Color, fill: Color, border: Color | None = None) -> Run:
    return Run(content, theme.toned(theme.PILL, color), chip=theme.pill(fill, border))


def stamp(date: DateNote) -> list[Run]:
    """When a fact's source is dated, as a short label. Nothing when the fact says so itself."""
    return [Run(date.stamp, theme.toned(theme.STAMP, DATE_COLOR[date.kind]))] if date.stamp else []


def date_dot(pdf: FPDF, cx: float, cy: float, kind: str) -> None:
    """The mark beside a fact: solid for a dated one, haloed for a live posting, hollow for no date."""
    if kind == "open":
        canvas.disc(pdf, cx, cy, 2.0, theme.POSITIVE_HALO)
        canvas.disc(pdf, cx, cy, 1.05, theme.POSITIVE)
    elif kind == "dated":
        canvas.disc(pdf, cx, cy, 1.05, theme.ACCENT)
    else:
        canvas.ring(pdf, cx, cy, 1.05, theme.INK_3, dashed=True)


def capsule(runs: Sequence[Run], room: float) -> Part:
    """A white pill holding a short line in more than one style, such as a stat's label and value."""
    line = canvas.text(runs, room - 2 * CAPSULE_PAD, max_lines=1)
    width = line.width + 2 * CAPSULE_PAD

    def paint(pdf: FPDF, x: float, y: float) -> None:
        canvas.fill_round(pdf, x, y, width, CAPSULE_HEIGHT, CAPSULE_HEIGHT / 2, theme.SURFACE)
        canvas.outline_round(pdf, x, y, width, CAPSULE_HEIGHT, CAPSULE_HEIGHT / 2, theme.LINE_ON_CANVAS)
        line.paint(pdf, x + CAPSULE_PAD, y + (CAPSULE_HEIGHT - line.height) / 2)

    return Part(CAPSULE_HEIGHT, paint, width)


def flow(parts: Sequence[Part], room: float, gap_x: float, gap_y: float) -> Part:
    """Parts set left to right by their own width, starting a new row when one does not fit."""
    places: list[tuple[float, float, Part]] = []
    x = y = row_height = 0.0
    for part in parts:
        if x > 0 and x + part.width > room:
            x, y, row_height = 0.0, y + row_height + gap_y, 0.0
        places.append((x, y, part))
        x += part.width + gap_x
        row_height = max(row_height, part.height)

    def paint(pdf: FPDF, left: float, top: float) -> None:
        for offset_x, offset_y, part in places:
            part.paint(pdf, left + offset_x, top + offset_y)

    return Part(y + row_height if places else 0.0, paint)


def card_block(
    body: Part, space_before: float, breaks: Sequence[float] = (), splits_freely: bool = False,
) -> Block:
    """A white card across the page holding ``body``. ``breaks`` are measured from the top of the body."""
    height = body.height + 2 * theme.CARD_PAD

    def paint(pdf: FPDF, y: float) -> None:
        canvas.card(pdf, theme.MARGIN_X, y, theme.CONTENT_W, height)
        body.paint(pdf, theme.MARGIN_X + theme.CARD_PAD, y + theme.CARD_PAD)

    return Block(
        height, paint, space_before,
        breaks=tuple(theme.CARD_PAD + mark for mark in breaks), splits_freely=splits_freely,
    )


def block(part: Part, space_before: float, keep_with_next: bool = False) -> Block:
    """A part set at the left margin as a block of its own."""
    def paint(pdf: FPDF, y: float) -> None:
        part.paint(pdf, theme.MARGIN_X, y)

    return Block(part.height, paint, space_before, keep_with_next=keep_with_next)


def ruled(part: Part, room: float, pad_top: float, pad_bottom: float = 0.0, color: Color = theme.LINE) -> Part:
    """A part under a hairline, as a row of a list."""
    return canvas.behind(
        canvas.inset(part, top=pad_top, bottom=pad_bottom),
        lambda pdf, x, y, height: canvas.rule(pdf, x, y, room, color),
    )


def row_breaks(
    starts: Sequence[float], keep: int = MIN_ROWS_TOGETHER, keep_at_end: int = MIN_ROWS_TOGETHER,
) -> list[float]:
    """Where a list may be cut, given where each of its rows starts.

    A cut always leaves at least ``keep`` rows above it, so a page never
    ends on a list's heading and first row alone, and at least
    ``keep_at_end`` rows below it.
    """
    return list(starts[keep:len(starts) - keep_at_end + 1])
