"""The fonts the brief PDF embeds: the site's own Inter and JetBrains Mono.

fpdf2 embeds one static TrueType file per weight. The files under
assets/fonts/ are cut from the web page's variable fonts by
scripts/build_export_fonts.py, so the PDF and the page are set in the same
type. Each face is its own fpdf2 family, named here.
"""

from dataclasses import dataclass
from pathlib import Path

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
