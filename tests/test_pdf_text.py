"""Laying out text for the PDF: measuring, wrapping, breaking what has no spaces."""

import pytest

import pdf_fonts
import pdf_text
from pdf_text import Chip, Run, Style

BODY = Style(pdf_fonts.REGULAR, 9, (20, 20, 20))
MONO = Style(pdf_fonts.MONO, 7, (95, 102, 115))
CHIP = Chip(fill=(239, 239, 237))
NO_BREAK_SPACE = chr(0xA0)


def _texts(paragraph):
    return [" ".join(piece.run.text for piece in line) for line in paragraph.lines]


def test_width_grows_with_the_text_its_size_and_its_tracking():
    assert pdf_text.width("", BODY) == 0
    assert pdf_text.width("Alkira Alkira", BODY) > pdf_text.width("Alkira", BODY) > 0
    bigger = Style(pdf_fonts.REGULAR, 18, (0, 0, 0))
    assert pdf_text.width("Alkira", bigger) == pytest.approx(2 * pdf_text.width("Alkira", BODY))
    tracked = Style(pdf_fonts.REGULAR, 9, (0, 0, 0), tracking=0.09)
    assert pdf_text.width("ALKIRA", tracked) > pdf_text.width("ALKIRA", BODY)


def test_text_that_fits_stays_on_one_line():
    paragraph = pdf_text.layout([Run("A short line.", BODY)], 100)
    assert _texts(paragraph) == ["A short line."]
    assert paragraph.height == pytest.approx(paragraph.line_height)


def test_text_wraps_at_spaces_and_no_line_is_wider_than_the_column():
    paragraph = pdf_text.layout([Run("one two three four five six seven eight nine ten " * 4, BODY)], 40)
    assert len(paragraph.lines) > 3
    assert paragraph.width <= 40
    assert " ".join(_texts(paragraph)).split() == ("one two three four five six seven eight nine ten " * 4).split()
    assert paragraph.height == pytest.approx(len(paragraph.lines) * paragraph.line_height)


def test_runs_of_whitespace_collapse_and_empty_text_takes_no_room():
    assert _texts(pdf_text.layout([Run("  spaced \n\t out   text ", BODY)], 100)) == ["spaced out text"]
    empty = pdf_text.layout([Run("   ", BODY)], 100)
    assert empty.lines == () and empty.height == 0


def test_a_word_longer_than_the_column_is_broken_and_nothing_is_lost():
    address = "https://example.com/" + "a" * 300
    paragraph = pdf_text.layout([Run(address, BODY)], 50)
    assert len(paragraph.lines) > 3
    assert paragraph.width <= 50
    assert "".join(piece.run.text for line in paragraph.lines for piece in line) == address


def test_a_no_break_space_never_ends_a_line():
    text = f"wrap here but keep 12{NO_BREAK_SPACE}months together"
    paragraph = pdf_text.layout([Run(text, BODY)], pdf_text.width("wrap here but keep 12", BODY) + 0.5)
    assert _texts(paragraph) == ["wrap here but keep", f"12{NO_BREAK_SPACE}months together"]


def test_a_chip_is_never_split_and_punctuation_stays_with_the_chip_before_it():
    runs = [Run("Runs over", BODY), Run(" ", BODY), Run("Azure Virtual WAN", MONO, chip=CHIP), Run(", today.", BODY)]
    # Room for the chip and what follows it, but not for the words before it as well.
    room = pdf_text.width("Azure Virtual WAN", MONO) + 2 * CHIP.pad + pdf_text.width(", today.", BODY) + 0.5
    paragraph = pdf_text.layout(runs, room)
    assert _texts(paragraph) == ["Runs over", "Azure Virtual WAN , today."]
    chip, comma = paragraph.lines[1][0], paragraph.lines[1][1]
    assert chip.run.chip is CHIP
    assert comma.x == pytest.approx(chip.x + chip.width)  # no space between the chip and its comma


def test_a_chip_is_wider_than_its_text_by_its_padding():
    plain = pdf_text.layout([Run("BGP", MONO)], 100).lines[0][0]
    chip = pdf_text.layout([Run("BGP", MONO, chip=CHIP)], 100).lines[0][0]
    assert chip.width == pytest.approx(plain.width + 2 * CHIP.pad)


def test_a_link_stays_on_each_piece_of_the_run_it_was_given_to():
    paragraph = pdf_text.layout([Run("northwind.example/a/long/path/that/wraps/over/lines", BODY, link="https://x.example")], 30)
    assert len(paragraph.lines) > 1
    assert all(piece.run.link == "https://x.example" for line in paragraph.lines for piece in line)


def test_text_past_the_line_limit_is_cut_with_an_ellipsis():
    paragraph = pdf_text.layout([Run("word " * 200, BODY)], 40, max_lines=2)
    assert len(paragraph.lines) == 2
    assert _texts(paragraph)[-1].endswith("…")
    assert paragraph.width <= 40


def test_the_line_is_as_tall_as_its_largest_text_asks():
    headline = Style(pdf_fonts.DISPLAY, 20, (0, 0, 0), leading=1.1)
    paragraph = pdf_text.layout([Run("Big", headline), Run(" small", BODY)], 100)
    assert paragraph.line_height == pytest.approx(20 * 1.1 / pdf_text.PT_PER_MM)
    assert 0 < paragraph.baseline < paragraph.line_height


def test_text_the_fonts_lack_is_cleaned_before_it_is_measured():
    paragraph = pdf_text.layout([Run("Anker 安克创新 → 🚀", BODY)], 100)
    assert _texts(paragraph) == ["Anker […] ->"]


def test_the_space_between_two_runs_survives_when_one_of_them_is_cleaned():
    strong = Style(pdf_fonts.SEMIBOLD, 9, (20, 20, 20))
    runs = [Run("Cut firewalls from", BODY), Run(" 120 ", strong), Run("→", BODY), Run(" 12 ", strong), Run("in a year.", BODY)]
    paragraph = pdf_text.layout(runs, 200)
    assert _texts(paragraph) == ["Cut firewalls from 120 -> 12 in a year."]
    gaps = [after.x - (before.x + before.width) for before, after in zip(paragraph.lines[0], paragraph.lines[0][1:])]
    assert all(gap > 0.5 for gap in gaps)  # a real space between every pair of pieces


def test_no_runs_and_no_lines_allowed_both_lay_out_as_nothing():
    assert pdf_text.layout([], 100).lines == ()
    assert pdf_text.layout([Run("Some words here", BODY)], 100, max_lines=0).lines == ()


def test_a_chip_cut_short_by_the_line_limit_still_fits_with_its_padding():
    runs = [Run("word " * 30, BODY), Run("Azure Virtual WAN hub-and-spoke", MONO, chip=CHIP)]
    paragraph = pdf_text.layout(runs, 60, max_lines=1)
    assert paragraph.width <= 60


def test_only_the_lines_that_show_are_drawn():
    drawn = []

    class _Page:
        def set_font(self, *args, **kwargs): pass
        def set_text_color(self, *args): pass
        def set_char_spacing(self, *args): pass
        def text(self, x, y, text): drawn.append(text)

    paragraph = pdf_text.layout([Run("one two three four five six seven eight nine ten", BODY)], 20)
    assert len(paragraph.lines) >= 4
    height = paragraph.line_height
    # A band covering the second and third lines only.
    pdf_text.draw(_Page(), paragraph, 0, 0, shows=lambda top, bottom: top < 3 * height and bottom > height)
    assert drawn == [" ".join(piece.run.text for piece in line) for line in paragraph.lines[1:3]]
