"""The fonts the PDF embeds: static cuts of the site's own Inter and JetBrains Mono."""

from pathlib import Path

import pytest
from fontTools.ttLib import TTFont

import pdf_fonts

FONT_DIR = Path(__file__).parent.parent / "assets" / "fonts"
# Every face together. They are committed, so they stay small.
MAX_TOTAL_BYTES = 600_000
SPANISH = "áéíóúüñÁÉÍÓÚÜÑ¿¡"
TYPOGRAPHIC = "–—‘’“”…•€·×"


@pytest.mark.parametrize("face", pdf_fonts.FACES, ids=lambda face: face.file)
def test_every_face_is_a_static_truetype_file_of_its_weight(face):
    font = TTFont(FONT_DIR / face.file)
    assert "fvar" not in font, "a variable font: fpdf2 needs one file per weight"
    assert "glyf" in font
    assert font["OS/2"].usWeightClass == face.weight


@pytest.mark.parametrize("face", pdf_fonts.FACES, ids=lambda face: face.file)
def test_every_face_covers_spanish_and_typographic_punctuation(face):
    covered = set(TTFont(FONT_DIR / face.file).getBestCmap())
    missing = [char for char in SPANISH + TYPOGRAPHIC if ord(char) not in covered]
    assert not missing


def test_both_licences_are_kept_beside_the_fonts():
    for name in ("Inter-LICENSE.txt", "JetBrainsMono-LICENSE.txt"):
        assert "SIL OPEN FONT LICENSE" in (FONT_DIR / name).read_text(encoding="utf-8").upper()


def test_the_committed_fonts_stay_small():
    assert sum(path.stat().st_size for path in FONT_DIR.glob("*.ttf")) < MAX_TOTAL_BYTES


def test_no_font_file_is_committed_that_the_renderer_does_not_use():
    assert {path.name for path in FONT_DIR.glob("*.ttf")} == {face.file for face in pdf_fonts.FACES}
