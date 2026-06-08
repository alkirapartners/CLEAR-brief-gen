"""Tests for retained brief markdown parsers."""

from app import extract_score, extract_company_header, get_brief_body

BRIEF = """# ALKIRA OPPORTUNITY BRIEF

## Halverson Freight Group
**HQ:** Memphis, TN | **Revenue:** $2.1B

**Alkira Fit Score: 4 / 5**
Strong multicloud fit with active migration.

### Infrastructure Snapshot
- **Cloud Platforms:** AWS, Azure

*CONFIDENTIAL*
"""

def test_extract_score_value_and_reasoning():
    score, reasoning = extract_score(BRIEF)
    assert score == 4
    assert "multicloud" in reasoning

def test_extract_score_missing():
    score, reasoning = extract_score("# No score here")
    assert score == 0
    assert reasoning == ""

def test_extract_company_header():
    company, stats = extract_company_header(BRIEF)
    assert company == "Halverson Freight Group"
    assert "Memphis" in stats
    assert "**" not in stats

def test_get_brief_body_strips_header_and_score():
    body = get_brief_body(BRIEF)
    assert "Infrastructure Snapshot" in body
    assert "Halverson Freight Group" not in body
    assert "Alkira Fit Score" not in body
