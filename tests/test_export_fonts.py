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


# ── Text the fonts cannot set ────────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "“Anker” — not Ankercloud…",
    "¿Qué operación está pendiente? Año: 2026 · 80% · €5 × 3",
    "Plain ASCII, with (brackets) and [1] markers.",
])
def test_spanish_and_typographic_punctuation_are_kept_as_written(text):
    assert pdf_fonts.clean(text) == text


@pytest.mark.parametrize(("written", "shown"), [
    ("Anker Innovations 安克创新", "Anker Innovations […]"),
    ("龚银", "[…]"),
    ("CIO 龚 银 said so", "CIO […] said so"),
    ("Gong Yin (龚银), CIO", "Gong Yin, CIO"),
    ("Launch 🚀 day 🎉", "Launch day"),
    ("Łukasz Čapek of Škoda", "Lukasz Capek of Skoda"),
    ("A → B, where B ≥ 5", "A -> B, where B >= 5"),
    ("cafe\u0301", "café"),
    ("non\u2011breaking\u00a0and\u200bzero\u2009width", "non-breaking\u00a0andzero width"),
    ("tab\there\nand\x00control", "tab here andcontrol"),
    ("", ""),
])
def test_text_the_fonts_lack_is_replaced_dropped_or_marked_as_left_out(written, shown):
    assert pdf_fonts.clean(written) == shown


def test_cleaned_text_holds_only_characters_every_face_can_set():
    supported = pdf_fonts.supported()
    cleaned = pdf_fonts.clean("Ελληνικά, Кириллица, 日本語, العربية, emoji 😀, ﬁgure ½ № 5 ‰")
    assert all(ord(char) in supported for char in cleaned)


def test_every_face_reports_its_metrics_once():
    metrics = pdf_fonts.metrics(pdf_fonts.REGULAR)
    assert metrics is pdf_fonts.metrics(pdf_fonts.REGULAR)
    assert 0.5 < metrics.advance("M") < 1.0 and metrics.advance("i") < metrics.advance("M")
    assert metrics.ascender > 0 > metrics.descender
    mono = pdf_fonts.metrics(pdf_fonts.MONO)
    assert mono.advance("i") == mono.advance("M")
