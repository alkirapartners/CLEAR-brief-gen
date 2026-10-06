"""The fonts the brief PDF embeds: the site's own Inter and JetBrains Mono.

fpdf2 embeds one static TrueType file per weight. The files under
assets/fonts/ are cut from the web page's variable fonts by
scripts/build_export_fonts.py, so the PDF and the page are set in the same
type. Each face is its own fpdf2 family, named here.

The files are read with fontTools, which fpdf2 itself depends on and reads
fonts with, so it is always installed where the PDF is drawn.
"""

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from fontTools.ttLib import TTFont

FONT_DIR = Path(__file__).parent / "assets" / "fonts"

INTER_SOURCE = "Inter-Variable.woff2"
MONO_SOURCE = "JetBrainsMono-Variable.woff2"
# Inter's optical-size axis: 14 is drawn for text, 32 for headlines.
TEXT_SIZE = 14.0
DISPLAY_SIZE = 32.0


@dataclass(frozen=True)
class Face:
    """One weight of one typeface: its fpdf2 family name, its file, and what it is cut from."""

    family: str
    file: str
    source: str
    weight: int
    optical_size: float = TEXT_SIZE


REGULAR = Face("inter", "Inter-Regular.ttf", INTER_SOURCE, 400)
MEDIUM = Face("inter-medium", "Inter-Medium.ttf", INTER_SOURCE, 500)
SEMIBOLD = Face("inter-semibold", "Inter-SemiBold.ttf", INTER_SOURCE, 600)
DISPLAY_MEDIUM = Face("inter-display-medium", "InterDisplay-Medium.ttf", INTER_SOURCE, 500, DISPLAY_SIZE)
DISPLAY = Face("inter-display", "InterDisplay-SemiBold.ttf", INTER_SOURCE, 600, DISPLAY_SIZE)
MONO = Face("mono", "JetBrainsMono-Regular.ttf", MONO_SOURCE, 400)
MONO_MEDIUM = Face("mono-medium", "JetBrainsMono-Medium.ttf", MONO_SOURCE, 500)

FACES: tuple[Face, ...] = (REGULAR, MEDIUM, SEMIBOLD, DISPLAY_MEDIUM, DISPLAY, MONO, MONO_MEDIUM)


# ── Metrics: read once per process ───────────────────────────────────────────

@dataclass(frozen=True)
class FaceMetrics:
    """What laying out text needs from a face, in ems: glyph widths and the line's shape."""

    advances: Mapping[int, float]
    default_advance: float
    ascender: float
    descender: float
    cap_height: float

    def advance(self, char: str) -> float:
        return self.advances.get(ord(char), self.default_advance)


def path(face: Face) -> Path:
    return FONT_DIR / face.file


@lru_cache(maxsize=None)
def metrics(face: Face) -> FaceMetrics:
    """The face's metrics. The file is read the first time and never again in this process."""
    font = TTFont(path(face), lazy=True)
    try:
        em = float(font["head"].unitsPerEm)
        widths = font["hmtx"].metrics
        advances = {code: widths[glyph][0] / em for code, glyph in font.getBestCmap().items()}
        return FaceMetrics(
            advances=MappingProxyType(advances),
            default_advance=widths[".notdef"][0] / em,
            ascender=font["hhea"].ascent / em,
            descender=font["hhea"].descent / em,
            cap_height=font["OS/2"].sCapHeight / em,
        )
    finally:
        font.close()


NO_BREAK_SPACE = "\u00a0"


def _can_be_set(code: int) -> bool:
    """A printing character that needs no help from its neighbours: not a control, not a combining mark."""
    char = chr(code)
    return (char.isprintable() or char == NO_BREAK_SPACE) and not unicodedata.combining(char)


@lru_cache(maxsize=1)
def supported() -> frozenset[int]:
    """The characters every face can set, so a run never changes shape with its font."""
    shared = set.intersection(*(set(metrics(face).advances) for face in FACES))
    return frozenset(code for code in shared if _can_be_set(code))


# ── Text the fonts cannot set ────────────────────────────────────────────────

# Printed in place of a value of which nothing could be set: a name wholly in another script.
OMISSION = "[…]"
# What stands in for a character the fonts lack, where plain text says the same thing.
STAND_INS: dict[str, str] = {
    "→": "->", "←": "<-", "↔": "<->", "⇒": "=>", "≥": ">=", "≤": "<=", "≠": "!=", "≈": "~", "∼": "~",
    "\u2010": "-", "\u2011": "-", "‒": "–", "―": "—", "⁃": "-",
    "‛": "‘", "‟": "“", "∙": "·", "‧": "·", "●": "•", "◦": "•", "▪": "•", "■": "•",
    "Ł": "L", "ł": "l", "Đ": "D", "đ": "d", "₤": "£",
    "\t": " ", "\n": " ", "\r": " ",
}
_SPACES = "\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000"
# Stands where characters were left out while the text around them is tidied. It is never printed.
_GAP = chr(0)
_SEPARATORS = re.escape(",;:·/|–—•-")
# What was left out, with any separator on either side of it. This and the patterns below run
# after repeated spaces are made one, so each looks at most one space either way.
_LEFT_OUT = re.compile(
    rf"(?P<before> ?[{_SEPARATORS}] ?)?{_GAP}(?: ?[{_SEPARATORS}]? ?{_GAP})*(?P<after> ?[{_SEPARATORS}] ?)?"
)
_OPENS = "([{¿¡"
_CLOSES = ")]}.!?"
_EMPTY_BRACKETS = re.compile(r" ?[(\[{] ?[)\]}]")
_SPACE_BEFORE_STOP = re.compile(r" ([,.;:!?])")
_REPEATED_SPACES = re.compile(r" {2,}")


def _stand_in(char: str, can_set: frozenset[int]) -> str:
    """What to print for one character the fonts lack. A gap when there is nothing to print for it."""
    if char in STAND_INS:
        return STAND_INS[char]
    if char in _SPACES:
        return " "
    return "".join(part for part in unicodedata.normalize("NFKD", char) if ord(part) in can_set) or _GAP


def _neighbour(text: str, index: int, step: int) -> str:
    """The nearest character that is not a space, one way or the other. Spaces are single by now."""
    index += step
    if 0 <= index < len(text) and text[index] == " ":
        index += step
    return text[index] if 0 <= index < len(text) else ""


def _close_gaps(text: str) -> str:
    """The text with what was left out closed up, and no separator left dangling where it stood.

    "Anker, 安克, Shenzhen" keeps one comma. At the start or the end of the
    text, or just inside a bracket, the separator goes with what it joined.
    """
    def close(match: re.Match[str]) -> str:
        before, after = match.group("before") or "", match.group("after") or ""
        ahead, behind = _neighbour(text, match.end() - 1, 1), _neighbour(text, match.start(), -1)
        if not behind or behind in _OPENS or not ahead or ahead in _CLOSES:
            return " " if before.startswith(" ") or after.endswith(" ") else ""
        return before or after

    return _LEFT_OUT.sub(close, text)


def _tidy(text: str) -> str:
    """What is left once the gaps are closed: no emptied brackets, no doubled or stranded spaces."""
    closed = _close_gaps(_REPEATED_SPACES.sub(" ", text))
    closed = _EMPTY_BRACKETS.sub("", _REPEATED_SPACES.sub(" ", closed))
    return _REPEATED_SPACES.sub(" ", _SPACE_BEFORE_STOP.sub(r"\1", closed)).strip(" ")


def clean(text: str) -> str:
    """Text the embedded fonts can set, whatever was written.

    The fonts cover western European text and typographic punctuation, as
    the brief page's do. A character outside them never reaches fpdf2. It
    is replaced by plain text that says the same ("→" becomes "->", "Č"
    becomes "C"), or left out, and what it leaves behind is tidied: no
    empty brackets, no doubled spaces, no separator with nothing after it.
    "Gong Yin (龚银)" prints as "Gong Yin". Only a value of which nothing is
    left prints the omission mark. Never raises.

    A space at either end is kept: a sentence is laid out in pieces, and
    the space between two of them belongs to one of them.
    """
    can_set = supported()
    composed = unicodedata.normalize("NFC", text)
    lacking = [char for char in composed if ord(char) not in can_set]
    if not lacking:
        return composed
    shown = _tidy("".join(char if ord(char) in can_set else _stand_in(char, can_set) for char in composed))
    lost_words = any(char.isalnum() and _stand_in(char, can_set) == _GAP for char in lacking)
    if lost_words and not any(char.isalnum() for char in shown):
        shown = OMISSION
    lead = " " if composed[:1].isspace() else ""
    tail = " " if composed[-1:].isspace() else ""
    if not shown:
        return " " if lead or tail else ""
    return f"{lead}{shown}{tail}"
