"""The fonts the brief PDF embeds: the site's own Inter and JetBrains Mono.

fpdf2 embeds one static TrueType file per weight. The files under
assets/fonts/ are cut from the web page's variable fonts by
scripts/build_export_fonts.py, so the PDF and the page are set in the same
type. Each face is its own fpdf2 family, named here.
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

# Printed where letters of a script the fonts lack were left out.
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
_INVISIBLE = "\u00ad\u200b\u200c\u200d\u2060\ufeff\ufe0e\ufe0f"
_OMITTED_RUN = re.compile(rf"{re.escape(OMISSION)}(?:\s*{re.escape(OMISSION)})+")
# A bracket left holding nothing, or only the mark of what was left out.
_EMPTY_BRACKETS = re.compile(rf"\s*[(\[]\s*(?:{re.escape(OMISSION)})?\s*[)\]]")
_SPACE_BEFORE_STOP = re.compile(r" +([,.;:!?])")
_REPEATED_SPACES = re.compile(r" {2,}")


def _stand_in(char: str, can_set: frozenset[int]) -> str:
    """What to print for one character the fonts lack."""
    if char in STAND_INS:
        return STAND_INS[char]
    if char in _SPACES:
        return " "
    if char in _INVISIBLE or not char.isprintable():
        return ""
    plain = "".join(part for part in unicodedata.normalize("NFKD", char) if ord(part) in can_set)
    if plain:
        return plain
    return OMISSION if char.isalnum() else ""


def clean(text: str) -> str:
    """Text the embedded fonts can set, whatever was written.

    The fonts cover western European text and typographic punctuation, as
    the brief page's do. A character outside them never reaches fpdf2: it
    is replaced by plain text that says the same ("→" becomes "->", "Č"
    becomes "C"), dropped when it is decoration (an emoji), or marked as
    left out when it is a word in another script. Never raises.
    """
    can_set = supported()
    composed = unicodedata.normalize("NFC", text)
    if all(ord(char) in can_set for char in composed):
        return composed
    shown = "".join(char if ord(char) in can_set else _stand_in(char, can_set) for char in composed)
    shown = _OMITTED_RUN.sub(OMISSION, shown)
    shown = _EMPTY_BRACKETS.sub("", shown)
    return _REPEATED_SPACES.sub(" ", _SPACE_BEFORE_STOP.sub(r"\1", shown)).strip()
