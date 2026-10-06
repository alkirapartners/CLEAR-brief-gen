"""The sheet a brief is drawn on, and the few shapes every section uses.

``BriefPDF`` is the fpdf2 document: the embedded fonts, the warm canvas, the
running header and footer. A ``Part`` is something with a height that can
paint itself at a place; sections are built by stacking parts and setting
them side by side, so their height is known before a page is chosen.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Sequence

from fpdf import FPDF
from fpdf.pattern import RadialGradient

import pdf_fonts
import pdf_text
import pdf_theme as theme
from pdf_text import Color, Run, Style

LOGO_PATH = Path(__file__).parent / "assets" / "alkira-logo.svg"
AUTHOR = "Alkira"
DASH = (0.9, 0.7)
METER_TICKS = 5
GLOW_STEPS = 6
# An internal link lands this far above its target.
ANCHOR_LEAD = 8.0
BAND_TOLERANCE = 0.01


@dataclass(frozen=True)
class Chrome:
    """What repeats on every page: the confidentiality mark, whose brief it is, and when it was made."""

    confidential: str
    company: str
    generated: str
    # "Page {page} of {pages}", in the brief's language.
    page_label: str


class BriefPDF(FPDF):
    """A US Letter document set in the site's fonts, with the brief's running header and footer."""

    def __init__(self, chrome: Chrome) -> None:
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.set_auto_page_break(False)
        self.set_margins(0, 0, 0)
        # fpdf2 subsets a font object in place when it writes the document, so
        # each document registers its own. Their widths are read once per
        # process, in pdf_fonts.metrics, and that is what layout measures with.
        for face in pdf_fonts.FACES:
            self.add_font(face.family, "", pdf_fonts.path(face))
        self.chrome = chrome
        self.page_total = 1
        self._band: tuple[float, float] | None = None
        self.set_author(AUTHOR)
        self.set_creator(AUTHOR)

    @contextmanager
    def window(self, top: float, height: float) -> Iterator[None]:
        """Draw only inside a band of the page: one slice of a block that runs over a page break.

        The block paints all of itself; what falls outside the band is
        clipped away, and a link or anchor out there is not made at all.
        """
        self._band = (top, top + height)
        try:
            with self.rect_clip(0, top, self.w, height):
                yield
        finally:
            self._band = None

    def _shows(self, y: float) -> bool:
        return self._band is None or self._band[0] - BAND_TOLERANCE <= y < self._band[1]

    def link(self, x: float, y: float, w: float, h: float, link: str | int, **kwargs: Any) -> Any:
        """A link over a rectangle, unless it lies outside the band being drawn."""
        if not self._shows(y + h / 2):
            return None
        return super().link(x, y, w, h, link, **kwargs)

    def anchor(self, link: int, y: float) -> None:
        """Make an internal link land here, a little above ``y`` so the target is not at the very edge."""
        if self._shows(y):
            self.set_link(link, y=max(0.0, y - ANCHOR_LEAD))

    def header(self) -> None:  # fpdf2 calls this as each page starts
        self.set_fill_color(*theme.CANVAS)
        self.rect(0, 0, theme.PAGE_W, theme.PAGE_H, style="F")
        self.image(LOGO_PATH, x=theme.MARGIN_X, y=theme.HEADER_Y, h=theme.LOGO_H)
        runs = [Run(self.chrome.confidential.upper(), theme.MICRO)]
        if self.page_no() > 1 and pdf_fonts.clean(self.chrome.company):
            whose = Run(self.chrome.company, theme.toned(theme.STAMP, theme.INK))
            runs = [whose, Run(" · ", theme.toned(theme.STAMP, theme.INK_3)), *runs]
        mark = pdf_text.layout(runs, theme.CONTENT_W / 2, max_lines=1)
        middle = theme.HEADER_Y + theme.LOGO_H * 0.42
        pdf_text.draw(self, mark, theme.PAGE_W / 2, middle - mark.line_height / 2, theme.CONTENT_W / 2, align="R")

    def footer(self) -> None:  # and this as each page ends
        made = pdf_text.layout([Run(self.chrome.generated, theme.CHROME)], theme.CONTENT_W / 2, max_lines=1)
        label = self.chrome.page_label.format(page=self.page_no(), pages=self.page_total)
        count = pdf_text.layout([Run(label, theme.CHROME)], theme.CONTENT_W / 2, max_lines=1)
        pdf_text.draw(self, made, theme.MARGIN_X, theme.FOOTER_Y)
        pdf_text.draw(self, count, theme.PAGE_W / 2, theme.FOOTER_Y, theme.CONTENT_W / 2, align="R")


# ── Shapes ───────────────────────────────────────────────────────────────────

def _radius(radius: float, w: float, h: float) -> float:
    """The corner radius fpdf2 is given. At half the short side or more it draws almost none, so stay under."""
    return max(0.0, min(radius, min(w, h) * pdf_text.FULL_ROUND))


def fill_round(pdf: FPDF, x: float, y: float, w: float, h: float, radius: float, color: Color) -> None:
    pdf.set_fill_color(*color)
    pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=_radius(radius, w, h))


def outline_round(
    pdf: FPDF, x: float, y: float, w: float, h: float, radius: float, color: Color, dashed: bool = False,
) -> None:
    pdf.set_draw_color(*color)
    pdf.set_line_width(theme.HAIRLINE)
    if dashed:
        pdf.set_dash_pattern(*DASH)
    pdf.rect(x, y, w, h, style="D", round_corners=True, corner_radius=_radius(radius, w, h))
    pdf.set_dash_pattern()


def card(pdf: FPDF, x: float, y: float, w: float, h: float) -> None:
    """A white card on the canvas, with the hairline that gives it an edge in print."""
    fill_round(pdf, x, y, w, h, theme.CARD_RADIUS, theme.SURFACE)
    outline_round(pdf, x, y, w, h, theme.CARD_RADIUS, theme.LINE_ON_CANVAS)


def rule(pdf: FPDF, x: float, y: float, w: float, color: Color = theme.LINE, dashed: bool = False) -> None:
    """A horizontal hairline."""
    _stroke(pdf, x, y, x + w, y, color, dashed)


def upright(pdf: FPDF, x: float, y: float, h: float, color: Color = theme.LINE, dashed: bool = False) -> None:
    """A vertical hairline."""
    _stroke(pdf, x, y, x, y + h, color, dashed)


def _stroke(pdf: FPDF, x1: float, y1: float, x2: float, y2: float, color: Color, dashed: bool) -> None:
    pdf.set_draw_color(*color)
    pdf.set_line_width(theme.HAIRLINE)
    if dashed:
        pdf.set_dash_pattern(*DASH)
    pdf.line(x1, y1, x2, y2)
    pdf.set_dash_pattern()


def disc(pdf: FPDF, cx: float, cy: float, radius: float, color: Color) -> None:
    pdf.set_fill_color(*color)
    pdf.circle(cx, cy, radius, style="F")


def ring(pdf: FPDF, cx: float, cy: float, radius: float, color: Color, dashed: bool = False) -> None:
    pdf.set_draw_color(*color)
    pdf.set_line_width(0.3)
    if dashed:
        pdf.set_dash_pattern(0.7, 0.55)
    pdf.circle(cx, cy, radius, style="D")
    pdf.set_dash_pattern()


def glow(
    pdf: FPDF, box: tuple[float, float, float, float], radius: float,
    centre: tuple[float, float], reach: float, color: Color, base: Color,
) -> None:
    """A soft light inside a rounded box: ``color`` at the centre, fading to the box's own ``base``."""
    x, y, w, h = box
    cx, cy = centre
    # The light falls off as a curve, not a straight line, so it has no visible edge where it ends.
    fade = [theme.mix(color, base, (1 - step / GLOW_STEPS) ** 2) for step in range(GLOW_STEPS + 1)]
    light = RadialGradient(cx, cy, 0, cx, cy, reach, colors=fade)
    with pdf.use_pattern(light):
        pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=_radius(radius, w, h))


def meter(
    pdf: FPDF, x: float, y: float, score: int, tick: tuple[float, float], gap: float, fill: Color, track: Color,
) -> float:
    """The score as five upright ticks, the first ``score`` of them filled. Returns the meter's width."""
    tick_w, tick_h = tick
    for index in range(METER_TICKS):
        color = fill if index < score else track
        fill_round(pdf, x + index * (tick_w + gap), y, tick_w, tick_h, tick_w / 2, color)
    return METER_TICKS * tick_w + (METER_TICKS - 1) * gap


# ── Parts ────────────────────────────────────────────────────────────────────

Painter = Callable[[FPDF, float, float], None]


def _nothing(pdf: FPDF, x: float, y: float) -> None:
    """Paints an empty part."""


@dataclass(frozen=True)
class Part:
    """A piece of a section: how tall it is, how wide its content came out, and how to paint it at (x, y)."""

    height: float
    paint: Painter = _nothing
    width: float = 0.0


EMPTY = Part(0.0)


def text(runs: Sequence[Run], room: float, max_lines: int | None = None, align: str = "L") -> Part:
    """Runs wrapped into a column. Empty text is an empty part, so a stack closes up around it."""
    if not any(run.text.strip() for run in runs):
        return EMPTY
    paragraph = pdf_text.layout(runs, room, max_lines)
    aligned_room = room if align != "L" else 0.0

    def paint(pdf: FPDF, x: float, y: float) -> None:
        pdf_text.draw(pdf, paragraph, x, y, aligned_room, align)

    return Part(paragraph.height, paint, paragraph.width)


def words(content: str, style: Style, room: float, max_lines: int | None = None) -> Part:
    """One string in one style."""
    return text([Run(content, style)], room, max_lines)


def label(content: str, style: Style, room: float) -> Part:
    """An uppercase micro-label."""
    return words(content.upper(), style, room)


def placed(rows: Sequence[tuple[float, Part]]) -> list[tuple[float, Part]]:
    """Where each row of a stack starts. ``rows`` pair a part with the space above it.

    An empty part takes neither room nor space, and the first part's space is not used.
    """
    result: list[tuple[float, Part]] = []
    y = 0.0
    for space, part in rows:
        if part.height <= 0:
            continue
        y += space if result else 0.0
        result.append((y, part))
        y += part.height
    return result


def stack(*rows: tuple[float, Part]) -> Part:
    """Parts one under another, each with the space above it."""
    places = placed(rows)
    if not places:
        return EMPTY

    def paint(pdf: FPDF, x: float, y: float) -> None:
        for offset, part in places:
            part.paint(pdf, x, y + offset)

    last_offset, last = places[-1]
    return Part(last_offset + last.height, paint, max(part.width for _, part in places))


def beside(*columns: tuple[float, Part]) -> Part:
    """Parts side by side, each at its distance from the left edge. As tall as the tallest."""
    def paint(pdf: FPDF, x: float, y: float) -> None:
        for offset, part in columns:
            part.paint(pdf, x + offset, y)

    return Part(max((part.height for _, part in columns), default=0.0), paint)


def inset(part: Part, left: float = 0.0, top: float = 0.0, bottom: float = 0.0) -> Part:
    """A part with room around it."""
    def paint(pdf: FPDF, x: float, y: float) -> None:
        part.paint(pdf, x + left, y + top)

    return Part(part.height + top + bottom, paint, part.width)


def behind(part: Part, backdrop: Callable[[FPDF, float, float, float], None]) -> Part:
    """A part with something drawn under it first. The backdrop is told the part's height."""
    def paint(pdf: FPDF, x: float, y: float) -> None:
        backdrop(pdf, x, y, part.height)
        part.paint(pdf, x, y)

    return Part(part.height, paint, part.width)
