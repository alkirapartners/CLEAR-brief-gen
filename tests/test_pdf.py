"""Tests for the PDF generator."""

from datetime import datetime

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


def test_pdf_has_pages_after_header_footer():
    """Smoke test: rendering a PDF with header+footer produces valid PDF bytes."""
    from pdf import generate_brief_pdf
    out = generate_brief_pdf(
        brief_md="# ALKIRA OPPORTUNITY BRIEF\n## TestCo\nSample.",
        company="TestCo",
        score=3,
        generated_at=datetime(2026, 5, 6),
    )
    assert isinstance(out, bytes)
    assert out.startswith(b"%PDF")
    assert len(out) > 200  # not just a stub


def test_safe_text_em_dash():
    from pdf import _safe_text
    assert _safe_text("Hello — world") == "Hello -- world"


def test_safe_text_smart_quotes():
    from pdf import _safe_text
    assert _safe_text("“Hello” ‘world’") == '"Hello" \'world\''


def test_safe_text_ellipsis():
    from pdf import _safe_text
    assert _safe_text("Hello…") == "Hello..."


def test_safe_text_stars():
    from pdf import _safe_text
    # 4 filled, 1 empty
    assert _safe_text("★★★★☆") == "****-"


def test_safe_text_strips_unencodable():
    from pdf import _safe_text
    # Chinese chars not in our explicit map, fallback to '?'
    assert _safe_text("Hello 中文") == "Hello ??"


def test_safe_text_handles_empty():
    from pdf import _safe_text
    assert _safe_text("") == ""


def test_safe_text_passthrough_ascii():
    from pdf import _safe_text
    assert _safe_text("Plain ASCII text!") == "Plain ASCII text!"


SAMPLE_FULL_BRIEF = """# ALKIRA OPPORTUNITY BRIEF
*May 2026*

## TestCo Holdings

**HQ:** Austin, TX | **Revenue:** $5B | **Employees:** 12,000 | **Industry:** Software

**Alkira Fit Score: 4 / 5**

TestCo runs production across Azure and AWS with active vendor consolidation
pressure. Multi-cloud connectivity and zero trust readiness make this a
strong fit for Alkira's NaaS platform.

## Infrastructure Snapshot

**Cloud Platforms:** Azure (confirmed), AWS production workloads.
**On-Prem / Hybrid:** Reduced footprint after 2024 consolidation.
**Deployment Model:** Active hybrid cloud migration.
**Resulting Complexity:** Two clouds plus acquired networks.

## Signals & Timing
- Vendor consolidation initiative announced Q1 2026
- New CIO from a cloud-native peer (Feb 2026)
- $300M IT modernization budget through 2027
- Zero trust mandate from board

## Three Alkira Entry Points

**1. Multi-cloud connectivity**
Signal: TestCo runs Azure and AWS production.
Solution: Alkira connects both in a single click.
Proof: 96% faster connection time.

**2. Zero trust segmentation**
Signal: Board mandate for zero trust.
Solution: Alkira applies policy as overlay.
Proof: Aligns to NIST SP 800-207.

**3. M&A integration**
Signal: Recent acquisitions create network sprawl.
Solution: Alkira instantly onboards new entities.
Proof: 98% reduction in partner integration time.

## Conversation Starters

**Stakeholders:** CIO, VP Network, CISO

**Best First Question:** Lead with question #1.

1. "How's the Azure-AWS connectivity going?"
2. "What's the timeline on zero trust?"

## References
[1] TestCo 10-K — https://example.com/10k
[2] CIO interview — https://example.com/interview
"""


def test_full_brief_renders():
    from pdf import generate_brief_pdf
    out = generate_brief_pdf(
        brief_md=SAMPLE_FULL_BRIEF,
        company="TestCo Holdings",
        score=4,
        generated_at=datetime(2026, 5, 6),
    )
    assert isinstance(out, bytes)
    assert out.startswith(b"%PDF")
    assert len(out) > 3000  # Real brief renders to substantive bytes (compressed)
