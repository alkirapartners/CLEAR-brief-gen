"""Tests for the PDF generator."""

from pdf import build_filename, ALKIRA_BLUE


def test_filename_basic():
    assert build_filename("PepsiCo", "2026-04") == "AlkiraBrief_PepsiCo_2026-04.pdf"


def test_filename_with_spaces_and_punctuation():
    assert build_filename("McKesson Corporation, Inc.", "2026-04") == \
        "AlkiraBrief_McKesson-Corporation-Inc_2026-04.pdf"


def test_filename_truncates_long_company():
    long_name = "Some Extremely Long Holding Company Group International Limited Partnership"
    out = build_filename(long_name, "2026-04")
    # Company portion (between AlkiraBrief_ and _2026-04) should be at most 40 chars
    company_part = out.replace("AlkiraBrief_", "").replace("_2026-04.pdf", "")
    assert len(company_part) <= 40


def test_constants_match_brand_palette():
    assert ALKIRA_BLUE == (45, 88, 242)
