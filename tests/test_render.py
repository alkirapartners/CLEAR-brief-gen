from app import get_brief_body, build_brief_document_html, CUSTOM_CSS

SAMPLE = """# ALKIRA OPPORTUNITY BRIEF
*June 2026*

## Halverson Freight Group
**HQ:** Memphis, TN | **Revenue:** $2.1B | **Employees:** 8,500

**Alkira Fit Score: 4 / 5**
Active multicloud migration after two 2025 acquisitions and a legacy MPLS backbone.

### Infrastructure Snapshot
- **Cloud Platforms:** AWS (confirmed), Azure (confirmed)
- **On-Prem / Hybrid:** Two data centers + VMware

### Signals & Timing
- Closed Cole Cartage acquisition (Jan 2025)

### Three Alkira Entry Points
**1. Multicloud Networking**
- Signal: Two clouds inherited via M&A
- Solution: Alkira unifies AWS + Azure
- Proof: 96% faster connection

### Conversation Starters
1. How are you connecting Azure to AWS today?
2. What is your appetite for moving off MPLS?

### References
[1] HFG Q1 2026 earnings call — https://example.com/hfg

*CONFIDENTIAL*
"""

# get_brief_body
def test_body_excludes_title_company_and_score():
    body = get_brief_body(SAMPLE)
    assert "Infrastructure Snapshot" in body
    assert "Halverson Freight Group" not in body
    assert "Alkira Fit Score" not in body
    assert "ALKIRA OPPORTUNITY BRIEF" not in body
    assert "CONFIDENTIAL" not in body

def test_body_handles_h2_section_headings():
    body = get_brief_body(SAMPLE.replace("### ", "## "))
    assert "Infrastructure Snapshot" in body
    assert "Halverson Freight Group" not in body

def test_body_empty_input():
    assert get_brief_body("") == ""

# build_brief_document_html
def test_document_has_header_band_company_and_badge():
    html = build_brief_document_html(SAMPLE)
    assert "brief-header-band" in html
    assert "Halverson Freight Group" in html
    assert "brief-score-badge" in html
    assert ">4<" in html

def test_document_does_not_duplicate_company_or_score():
    html = build_brief_document_html(SAMPLE)
    assert html.count("Halverson Freight Group") == 1
    assert "Alkira Fit Score:" not in html

def test_document_leads_with_score_rationale():
    html = build_brief_document_html(SAMPLE)
    assert "brief-lead" in html
    assert "multicloud migration" in html

def test_document_renders_sections_not_tiles():
    html = build_brief_document_html(SAMPLE)
    assert "Infrastructure Snapshot" in html
    assert "Conversation Starters" in html
    assert 'class="tile' not in html
    assert "brief-doc" in html

def test_missing_section_omitted_not_errored():
    sparse = """# ALKIRA OPPORTUNITY BRIEF

## Tiny Co
**HQ:** Nowhere

**Alkira Fit Score: 2 / 5**
Little public infrastructure detail.

### Signals & Timing
- Quiet company

*CONFIDENTIAL*
"""
    html = build_brief_document_html(sparse)
    assert "Tiny Co" in html
    assert "Infrastructure Snapshot" not in html
    assert "No data" not in html

def test_empty_input_does_not_crash():
    assert "brief-doc" in build_brief_document_html("")

def test_meta_right_included():
    assert "Generated in 42s" in build_brief_document_html(SAMPLE, meta_right="Generated in 42s")

def test_score_zero_suppresses_badge():
    no_score = SAMPLE.replace("**Alkira Fit Score: 4 / 5**", "")
    html = build_brief_document_html(no_score)
    assert "brief-score-badge" not in html

def test_custom_css_defines_style_c_classes():
    for cls in (".brief-header-band", ".brief-score-badge", ".brief-lead", ".bsb-num"):
        assert cls in CUSTOM_CSS
