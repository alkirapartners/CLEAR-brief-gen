"""Putting a brief on pages.

The renderer first builds every part of the brief as a ``Block``: something
that already knows its height and how to paint itself at a given place.
Only then are pages chosen, here, so a break never lands in the wrong spot:

- a block moves to the next page whole when it does not fit and a page can hold it;
- a block marked ``keep_with_next`` (a heading) goes with what follows it;
- a block that ``splits_freely`` (a list of rows) is cut at the last of its ``breaks`` that fits;
- a block taller than a whole page is cut at its breaks too, or at the foot of the page when it has none.

A cut block is painted once on each page it touches, inside a window the
height of its slice: the document clips the drawing to it and drops any
link that falls outside it (``BriefPDF.window``).
"""

from dataclasses import dataclass
from itertools import groupby
from typing import Callable, Sequence

from fpdf import FPDF

# Lengths are sums of many small ones; this much overflow is rounding, not content.
TOLERANCE = 0.01


@dataclass(frozen=True)
class Block:
    """A part of the brief, measured. ``paint`` draws it with its top edge at the given height."""

    height: float
    paint: Callable[[FPDF, float], None]
    space_before: float = 0.0
    keep_with_next: bool = False
    # Distances from the top at which the block may be cut.
    breaks: tuple[float, ...] = ()
    splits_freely: bool = False


@dataclass(frozen=True)
class PageFrame:
    """Where content may sit on a page, from the top edge. The first page can start lower."""

    first_top: float
    top: float
    bottom: float

    @property
    def room(self) -> float:
        return self.bottom - self.top


@dataclass(frozen=True)
class Slice:
    """A block, or the part of one between two of its breaks, placed on a page."""

    block: Block
    page: int
    y: float
    start: float
    end: float

    @property
    def is_whole(self) -> bool:
        return self.start == 0 and self.end == self.block.height


def _opening(block: Block, frame: PageFrame) -> float:
    """How much of a block has to fit where it starts: all of it, or its part before the first break."""
    may_be_cut = block.splits_freely or block.height > frame.room + TOLERANCE
    if not may_be_cut:
        return block.height
    return min(block.breaks[0] if block.breaks else frame.room, block.height, frame.room)


def _needed(blocks: Sequence[Block], index: int, frame: PageFrame) -> float:
    """The room a block needs below it to start here, counting what it must be kept with."""
    block = blocks[index]
    following = next((later for later in blocks[index + 1:] if later.height > 0), None)
    if not block.keep_with_next or following is None:
        return _opening(block, frame)
    return block.height + following.space_before + _opening(following, frame)


def _cut(block: Block, start: float, room: float) -> float:
    """Where to end a slice that begins at ``start`` and has ``room`` below it."""
    fitting = [mark for mark in block.breaks if start < mark <= start + room + TOLERANCE]
    return max(fitting) if fitting else start + room


def paginate(blocks: Sequence[Block], frame: PageFrame) -> list[Slice]:
    """Every block placed on a page, cut only where the rules above allow. Empty blocks are dropped."""
    slices: list[Slice] = []
    page, y = 0, frame.first_top
    tied = False
    for index, block in enumerate(blocks):
        if block.height <= 0:
            continue
        at_top = not any(piece.page == page for piece in slices)
        gap = 0.0 if at_top else block.space_before
        # A block tied to the heading above it stays under it: the heading already chose the page.
        moves = not at_top and not tied and y + gap + _needed(blocks, index, frame) > frame.bottom + TOLERANCE
        tied = block.keep_with_next
        if moves:
            page, y, gap = page + 1, frame.top, 0.0
        y += gap
        start = 0.0
        while block.height - start > frame.bottom - y + TOLERANCE:
            end = _cut(block, start, frame.bottom - y)
            if end > start:  # always, unless the page is already full
                slices.append(Slice(block, page, y, start, end))
            page, y, start = page + 1, frame.top, max(start, end)
        slices.append(Slice(block, page, y, start, block.height))
        y += block.height - start
    return slices


def page_count(slices: Sequence[Slice]) -> int:
    return max((piece.page for piece in slices), default=0) + 1


def paint(pdf: FPDF, slices: Sequence[Slice]) -> None:
    """Paint the placed blocks, one page after another. Needs at least one page's worth of slices or none."""
    by_page = {page: list(pieces) for page, pieces in groupby(slices, key=lambda piece: piece.page)}
    for page in range(page_count(slices)):
        pdf.add_page()
        for piece in by_page.get(page, []):
            if piece.is_whole:
                piece.block.paint(pdf, piece.y)
                continue
            with pdf.window(piece.y, piece.end - piece.start):
                piece.block.paint(pdf, piece.y - piece.start)
