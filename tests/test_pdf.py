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


def test_filename_empty_company():
    """Empty input falls back to 'Company' sentinel — no double underscore."""
    assert build_filename("", "2026-04") == "AlkiraBrief_Company_2026-04.pdf"


def test_filename_all_punctuation():
    """All-punctuation input falls back to 'Company' sentinel."""
    assert build_filename("!!!@@@###", "2026-04") == "AlkiraBrief_Company_2026-04.pdf"


def test_filename_whitespace_only():
    """Whitespace-only input falls back to 'Company' sentinel."""
    assert build_filename("   ", "2026-04") == "AlkiraBrief_Company_2026-04.pdf"


def test_filename_strips_unicode():
    """Non-ASCII letters are stripped to keep filename HTTP-safe."""
    out = build_filename("Naïve Café Société", "2026-04")
    assert out == "AlkiraBrief_Nave-Caf-Socit_2026-04.pdf"


def test_filename_strips_underscores():
    """Underscores in input are stripped — they're our delimiter."""
    out = build_filename("Foo_Bar Baz", "2026-04")
    assert out == "AlkiraBrief_FooBar-Baz_2026-04.pdf"


def test_generate_brief_pdf_returns_pdf_bytes():
    """Stub returns valid PDF bytes (locks the contract for Tasks 6-13)."""
    from pdf import generate_brief_pdf
    out = generate_brief_pdf("# Test", "TestCo", 3)
    assert isinstance(out, bytes)
    assert out.startswith(b"%PDF-")
    assert len(out) > 100
