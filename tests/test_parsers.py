"""Tests for brief markdown parsers."""

from app import extract_entry_points

SAMPLE_BRIEF = """
## Three Alkira Entry Points

**1. Multi-cloud connectivity**
Signal: McKesson runs production on Azure, GCP, and Oracle.
Solution: Alkira connects all three in a single click.
Proof: 96% faster connection time vs DIY transit hubs.

**2. M&A integration**
Signal: RxTS divestiture creates network separation pressure.
Solution: Alkira instantly onboards new entities to the cloud network.
Proof: 98% reduction in partner integration time.

**3. Zero trust segmentation**
Signal: Healthcare compliance requires strict segmentation.
Solution: Alkira applies HIPAA-aligned policy as overlay.
Proof: Aligns to NIST SP 800-207 zero trust architecture.
"""


def test_extract_entry_points_returns_three():
    points = extract_entry_points(SAMPLE_BRIEF)
    assert len(points) == 3


def test_extract_entry_points_signal_solution_proof():
    points = extract_entry_points(SAMPLE_BRIEF)
    assert points[0]["heading"] == "Multi-cloud connectivity"
    assert "Azure, GCP" in points[0]["signal"]
    assert "single click" in points[0]["solution"]
    assert "96%" in points[0]["proof"]


def test_extract_entry_points_handles_missing_section():
    points = extract_entry_points("# Just a title\n\nNo entry points here.")
    assert points == []
