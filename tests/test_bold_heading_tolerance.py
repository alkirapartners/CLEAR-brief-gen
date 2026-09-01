"""Tests for the bold-heading tolerance added to app.extract_section.

Production briefs (Dr Pepper, sampled 2026-08-31) emitted the Infrastructure
Snapshot heading as ``**Infrastructure Snapshot**`` instead of the mandated
``## Infrastructure Snapshot``. app.extract_section matched only ``##``/``###``
headings, so the section parsed to 0 chars and rendered as an empty gap in
the partner-facing brief and PDF. These tests lock in the fix: extract_section
(and anything built on it, like extract_entry_points) must tolerate a bold
heading written on its own line, while still requiring a bold *sub-label*
inside a section body (e.g. ``**Cloud Platforms:** text``) to NOT be mistaken
for the start of the next section.

tests/test_parsers.py and tests/test_pdf.py are the frozen regression gate
for existing behavior and are intentionally left untouched.
"""

import prompts
from app import extract_entry_points, extract_infra_cells, extract_section

BOLD_INFRA_BRIEF = """
**Infrastructure Snapshot**

**Cloud Platforms:** Azure (confirmed), GCP, Oracle Cloud production workloads.
**On-Prem / Hybrid:** Reduced footprint after 2024 data center consolidation.
**Deployment Model:** Active hybrid cloud migration through 2027.
**Resulting Complexity:** Three clouds plus dozens of acquired networks.

## Signals & Timing
- Vendor consolidation initiative announced Q1 2026
"""


def test_extract_section_finds_bold_heading():
    """A '**Heading**' line on its own must be recognized as a section start."""
    section = extract_section(BOLD_INFRA_BRIEF, "Infrastructure Snapshot")
    assert section != ""
    assert "Azure" in section
    assert "Three clouds" in section


def test_bold_sub_label_does_not_terminate_section_early():
    """A bold sub-label INSIDE the body (e.g. '**Cloud Platforms:** text') must
    not be treated as the start of the next section — only a bold span that
    is the entire line counts as a heading."""
    section = extract_section(BOLD_INFRA_BRIEF, "Infrastructure Snapshot")
    # The full body, including content after the FIRST sub-label, must survive.
    assert "On-Prem" in section
    assert "Deployment Model" in section
    assert "Resulting Complexity" in section
    assert "Three clouds plus dozens" in section
    # And it must stop before the next real (## ) section.
    assert "Signals & Timing" not in section
    assert "Vendor consolidation" not in section


HASH_HEADING_BRIEF = """
## Infrastructure Snapshot

**Cloud Platforms:** Azure and GCP.
**On-Prem / Hybrid:** Two data centers remaining.
**Deployment Model:** Hybrid through 2027.
**Resulting Complexity:** Multi-cloud sprawl.

## Signals & Timing
- Some signal.
"""


def test_hash_heading_sections_still_parse_exactly_as_before():
    """The existing '## Heading' contract must be unaffected by the new
    tolerance — this is a strict superset, not a rewrite."""
    section = extract_section(HASH_HEADING_BRIEF, "Infrastructure Snapshot")
    assert "Azure and GCP" in section
    assert "Multi-cloud sprawl" in section
    assert "Signals & Timing" not in section
    assert "Some signal" not in section


BOLD_ENTRY_POINTS_BRIEF = """
**Three Alkira Entry Points**

**1. Multi-cloud connectivity**
Signal: Runs production on Azure and GCP.
Solution: Alkira connects both in a single click.
Proof: 96% faster connection time.

**2. M&A integration**
Signal: Divestiture creates network separation pressure.
Solution: Alkira instantly onboards new entities.
Proof: 98% reduction in partner integration time.

**3. Zero trust segmentation**
Signal: Compliance requires strict segmentation.
Solution: Alkira applies policy as overlay.
Proof: Aligns to NIST SP 800-207 zero trust architecture.

## Conversation Starters
**Stakeholders:** CIO, VP Network
"""


def test_extract_entry_points_returns_three_when_heading_is_bold():
    points = extract_entry_points(BOLD_ENTRY_POINTS_BRIEF)
    assert len(points) == 3
    assert points[0]["heading"] == "Multi-cloud connectivity"
    assert "Azure and GCP" in points[0]["signal"]
    assert "single click" in points[0]["solution"]
    assert "96%" in points[0]["proof"]
    assert points[2]["heading"] == "Zero trust segmentation"


NO_INFRA_HEADING_BRIEF = """
# ALKIRA OPPORTUNITY BRIEF
## Occidental Petroleum

Some prose about the company with no heading at all before the infra content.

**Cloud Platforms:** AWS is the preferred cloud provider (confirmed).
**On-Prem / Hybrid:** Legacy data centers being consolidated.
**Deployment Model:** Multi-year cloud migration underway.
**Resulting Complexity:** Hybrid AWS plus legacy footprint.

## Signals & Timing
- Some signal.
"""


def test_extract_infra_cells_falls_back_when_heading_is_missing_entirely():
    """Measured production failure: the model wrote all four bold sub-labels
    with real content but emitted NO heading at all for Infrastructure
    Snapshot — not '##', not bold. extract_section returns "" in that case,
    so extract_infra_cells must fall back to scanning the whole brief for
    the four bold sub-labels instead of returning them all empty."""
    cells = extract_infra_cells(NO_INFRA_HEADING_BRIEF)
    assert "AWS" in cells["cloud_platforms"]
    assert "consolidated" in cells["on_prem"]
    assert "migration" in cells["deployment"]
    assert "Hybrid AWS" in cells["complexity"]


def test_build_system_prefix_contains_literal_output_skeleton():
    """Prose directives alone were not holding; the prefix must contain an
    explicit literal skeleton showing the exact document structure in order,
    including the '## Infrastructure Snapshot' heading."""
    prefix = prompts.build_system_prefix()
    assert "Full Literal Skeleton" in prefix
    skeleton_start = prefix.index("# ALKIRA OPPORTUNITY BRIEF\n## [Company Name]")
    skeleton = prefix[skeleton_start : skeleton_start + 2000]
    assert "## Infrastructure Snapshot" in skeleton
    assert "**Cloud Platforms:**" in skeleton
    assert "**On-Prem / Hybrid:**" in skeleton
    assert "**Deployment Model:**" in skeleton
    assert "**Resulting Complexity:**" in skeleton
    assert "## Signals & Timing" in skeleton
    assert "## Three Alkira Entry Points" in skeleton
    assert "## Conversation Starters" in skeleton
    assert "## References" in skeleton
    # Order matters: Infrastructure Snapshot must precede Signals & Timing.
    assert skeleton.index("## Infrastructure Snapshot") < skeleton.index(
        "## Signals & Timing"
    )


def test_build_system_prefix_mandates_infrastructure_snapshot_never_omitted():
    """The prompt must explicitly forbid dropping Infrastructure Snapshot
    when research is thin — the section-omission failure mode measured in
    4 of 5 sampled production briefs (Southwest, Neiman Marcus, Whole Foods,
    Sabre)."""
    prefix = prompts.build_system_prefix()
    assert "Never Omit" in prefix or "never omit" in prefix.lower()
    assert "not disclosed" in prefix.lower()
    # The four mandatory Infrastructure Snapshot sub-labels must be spelled
    # out alongside the "always present" directive.
    for sub_label in (
        "**Cloud Platforms:**",
        "**On-Prem / Hybrid:**",
        "**Deployment Model:**",
        "**Resulting Complexity:**",
    ):
        assert sub_label in prefix
