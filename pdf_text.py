"""Text layout for the brief PDF: measure, wrap, then draw.

fpdf2 can wrap a paragraph in one font. The brief needs more: a run of
mono inside a sentence, a tinted chip that must not split, a link on part
of a line, an address with no spaces that has to break anywhere, and the
height of all of it before a page is chosen. So text is laid out here from
the fonts' own widths (pdf_fonts.metrics) and drawn with fpdf2's simplest
call. Lengths are millimetres; type sizes are points.
"""

import re
from dataclasses import dataclass, replace
from typing import Iterator, Sequence

from fpdf import FPDF

import pdf_fonts
from pdf_fonts import Face

Color = tuple[int, int, int]
PT_PER_MM = 72 / 25.4
ELLIPSIS = "…"
# Where a line may break. A no-break space is not among them.
_BREAKING_SPACE = re.compile(r"[ \t\n\r]+")


@dataclass(frozen=True)
class Style:
    """How a run of text is set. ``tracking`` is letter-spacing in ems, ``leading`` the line height in sizes."""

    face: Face
    size: float
    color: Color
    tracking: float = 0.0
    leading: float = 1.5


@dataclass(frozen=True)
class Chip:
    """A rounded tint behind a run that is kept whole: a pill, a source marker, a mono term."""

    fill: Color
    pad: float = 1.1
    height: float = 3.7


@dataclass(frozen=True)
class Run:
    """Text in one style. ``link`` is a web address, or the number fpdf2 gave an internal link."""

    text: str
    style: Style
    link: str | int | None = None
    chip: Chip | None = None


@dataclass(frozen=True)
class Piece:
    """A run's text as it sits on one line, measured from the line's left edge."""

    x: float
    width: float
    run: Run


@dataclass(frozen=True)
class Paragraph:
    """Text laid out in a column: its lines, and where on each line the baseline sits."""

    lines: tuple[tuple[Piece, ...], ...]
    line_height: float
    baseline: float
    # From the top of a line to the middle of a capital letter, where a chip is centred.
    middle: float

    @property
    def height(self) -> float:
        return len(self.lines) * self.line_height

    @property
    def width(self) -> float:
        return max((line[-1].x + line[-1].width for line in self.lines if line), default=0.0)


@dataclass(frozen=True)
class _Atom:
    """The smallest thing a line holds: a word, a piece of one, or a whole chip."""

    run: Run
    width: float
    space_before: bool


def width(text: str, style: Style) -> float:
    """How wide the text sets in a style, in millimetres."""
    metrics = pdf_fonts.metrics(style.face)
    ems = sum(metrics.advance(char) for char in text) + style.tracking * len(text)
    return ems * style.size / PT_PER_MM


def _atom(run: Run, text: str, space_before: bool) -> _Atom:
    padding = 2 * run.chip.pad if run.chip else 0.0
    return _Atom(replace(run, text=text), width(text, run.style) + padding, space_before)


def _atoms(runs: Sequence[Run]) -> list[_Atom]:
    """Every word and chip in order, each knowing whether a space came before it."""
    atoms: list[_Atom] = []
    space_pending = False
    for run in runs:
        text = pdf_fonts.clean(run.text)
        # A chip is one atom whatever it holds; other text is cut at its spaces.
        words = [text.strip()] if run.chip else _BREAKING_SPACE.split(text)
        if run.chip and text != text.lstrip():
            space_pending = True
        for index, word in enumerate(words):
            space_pending = space_pending or index > 0
            if word:
                atoms.append(_atom(run, word, space_pending and bool(atoms)))
                space_pending = False
        if run.chip and text != text.rstrip():
            space_pending = True
    return atoms


def _words(atoms: Sequence[_Atom]) -> Iterator[list[_Atom]]:
    """Atoms grouped into what must stay on one line: a break is only allowed at a space."""
    word: list[_Atom] = []
    for atom in atoms:
        if atom.space_before and word:
            yield word
            word = []
        word.append(atom)
    if word:
        yield word


def _space(atom: _Atom) -> float:
    return width(" ", atom.run.style)


def _cut(atom: _Atom, first_room: float, room: float) -> list[_Atom]:
    """An atom too wide for a line, as pieces that fit: the first in what is left of this line."""
    if atom.run.chip is not None:
        return [atom]
    pieces: list[_Atom] = []
    text, available = "", first_room
    for char in atom.run.text:
        if text and width(text + char, atom.run.style) > available:
            pieces.append(_atom(atom.run, text, atom.space_before and not pieces))
            text, available = "", room
        text += char
    return [*pieces, _atom(atom.run, text, atom.space_before and not pieces)]


def _break(atoms: Sequence[_Atom], room: float) -> list[list[_Atom]]:
    """The atoms as lines, each filled as far as it goes."""
    lines: list[list[_Atom]] = [[]]
    used = 0.0
    for word in _words(atoms):
        gap = _space(word[0]) if lines[-1] else 0.0
        if lines[-1] and used + gap + sum(atom.width for atom in word) > room:
            lines.append([])
            used, gap = 0.0, 0.0
        for atom in word:
            # Only a word wider than a whole line is ever broken inside.
            parts = _cut(atom, room - used - gap, room) if used + gap + atom.width > room else [atom]
            for index, part in enumerate(parts):
                if index > 0 or (lines[-1] and not atom.space_before and used + part.width > room):
                    lines.append([])
                    used, gap = 0.0, 0.0
                lines[-1].append(part)
                used += gap + part.width
                gap = 0.0
    return [line for line in lines if line]


def _same_setting(first: Run, second: Run) -> bool:
    return first.style == second.style and first.link == second.link and first.chip is None and second.chip is None


def _pieces(line: Sequence[_Atom]) -> tuple[Piece, ...]:
    """A line's atoms placed left to right. Neighbours set the same way are joined into one piece."""
    pieces: list[Piece] = []
    x = 0.0
    for index, atom in enumerate(line):
        gap = _space(atom) if atom.space_before and index > 0 else 0.0
        last = pieces[-1] if pieces else None
        if last is not None and _same_setting(last.run, atom.run):
            joined = last.run.text + (" " if gap else "") + atom.run.text
            pieces[-1] = Piece(last.x, last.width + gap + atom.width, replace(last.run, text=joined))
        else:
            pieces.append(Piece(x + gap, atom.width, atom.run))
        x += gap + atom.width
    return tuple(pieces)


def _clamp(lines: list[tuple[Piece, ...]], max_lines: int, room: float) -> list[tuple[Piece, ...]]:
    """The first lines only, the last one ending in an ellipsis that still fits."""
    kept = lines[:max_lines]
    *head, last = kept[-1]
    text = last.run.text
    while text and last.x + width(text + ELLIPSIS, last.run.style) > room:
        text = text[:-1]
    shown = text.rstrip() + ELLIPSIS
    cut = Piece(last.x, width(shown, last.run.style), replace(last.run, text=shown))
    return [*kept[:-1], (*head, cut)]


def layout(runs: Sequence[Run], room: float, max_lines: int | None = None) -> Paragraph:
    """The runs wrapped into a column ``room`` millimetres wide.

    Text the fonts cannot set is cleaned first (pdf_fonts.clean), so nothing
    measured or drawn here can upset fpdf2. A line is as tall as its largest
    text asks.
    """
    lead = max(runs, key=lambda run: run.style.size).style
    metrics = pdf_fonts.metrics(lead.face)
    size = lead.size / PT_PER_MM
    line_height = size * lead.leading
    baseline = (line_height - (metrics.ascender - metrics.descender) * size) / 2 + metrics.ascender * size
    lines = [_pieces(line) for line in _break(_atoms(runs), room)]
    if max_lines is not None and len(lines) > max_lines:
        lines = _clamp(lines, max_lines, room)
    return Paragraph(tuple(lines), line_height, baseline, baseline - metrics.cap_height * size / 2)


def _shift(paragraph: Paragraph, line: Sequence[Piece], room: float, align: str) -> float:
    """How far a line moves right to be centred or set against the right edge."""
    slack = room - (line[-1].x + line[-1].width)
    return {"C": slack / 2, "R": slack}.get(align, 0.0)


def _draw_piece(pdf: FPDF, piece: Piece, x: float, top: float, paragraph: Paragraph) -> None:
    run, style = piece.run, piece.run.style
    text_x = x
    if run.chip is not None:
        chip_top = top + paragraph.middle - run.chip.height / 2
        pdf.set_fill_color(*run.chip.fill)
        pdf.rect(x, chip_top, piece.width, run.chip.height, style="F", round_corners=True,
                 corner_radius=run.chip.height / 2)
        text_x = x + run.chip.pad
    pdf.set_font(style.face.family, size=style.size)
    pdf.set_text_color(*style.color)
    pdf.set_char_spacing(style.tracking * style.size)
    pdf.text(text_x, top + paragraph.baseline, run.text)
    if run.link is not None:
        pdf.link(x, top, piece.width, paragraph.line_height, run.link)


def draw(pdf: FPDF, paragraph: Paragraph, x: float, y: float, room: float = 0.0, align: str = "L") -> None:
    """Draw a laid-out paragraph with its top-left corner at (x, y)."""
    for index, line in enumerate(paragraph.lines):
        top = y + index * paragraph.line_height
        shift = _shift(paragraph, line, room, align) if room else 0.0
        for piece in line:
            _draw_piece(pdf, piece, x + shift + piece.x, top, paragraph)
    pdf.set_char_spacing(0)
