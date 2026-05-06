"""Tests for brief markdown parsers."""

from app import extract_entry_points, extract_infra_cells

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


BOLD_BRIEF = """
## Three Alkira Entry Points

**1. Multi-cloud connectivity**
1. **Signal**: McKesson runs production on Azure, GCP, and Oracle.
2. **Solution**: Alkira connects all three in a single click.
3. **Proof**: 96% faster connection time.

**2. M&A integration**
1. **Signal**: RxTS divestiture creates network separation pressure.
2. **Solution**: Alkira instantly onboards new entities.
3. **Proof**: 98% reduction in partner integration time.

**3. Zero trust segmentation**
1. **Signal**: Healthcare compliance requires strict segmentation.
2. **Solution**: Alkira applies HIPAA-aligned policy as overlay.
3. **Proof**: Aligns to NIST SP 800-207.
"""

BULLET_BRIEF = """
## Three Alkira Entry Points

**1. Cloud connectivity**
- Signal: Two clouds, lots of pain.
- Solution: Alkira connects them.
- Proof: 96% faster.

**2. M&A integration**
- Signal: Acquisitions create sprawl.
- Solution: Alkira onboards instantly.
- Proof: 98% faster.

**3. Zero trust**
- Signal: Compliance requires it.
- Solution: Alkira applies overlay.
- Proof: NIST aligned.
"""


def test_extract_entry_points_handles_bold_labels():
    points = extract_entry_points(BOLD_BRIEF)
    assert len(points) == 3
    assert "Azure, GCP" in points[0]["signal"]
    assert "single click" in points[0]["solution"]
    assert "96%" in points[0]["proof"]
    assert "**" not in points[0]["signal"]  # no leaked bold markers


def test_extract_entry_points_handles_bullet_labels():
    points = extract_entry_points(BULLET_BRIEF)
    assert len(points) == 3
    assert "Two clouds" in points[0]["signal"]
    assert "Alkira connects" in points[0]["solution"]
    assert "96%" in points[0]["proof"]


def test_extract_entry_points_handles_emphasis_in_heading():
    brief = """
## Three Alkira Entry Points

**1. Multi-cloud *for healthcare* connectivity**
Signal: Three clouds in production.
Solution: Alkira connects them.
Proof: 96% faster.

**2. Compliance overlay**
Signal: HIPAA pressure.
Solution: Policy overlay.
Proof: NIST aligned.

**3. M&A**
Signal: Acquisitions.
Solution: Instant onboarding.
Proof: 98% faster.
"""
    points = extract_entry_points(brief)
    assert len(points) == 3
    assert "for healthcare" in points[0]["heading"]


def test_extract_entry_points_truncates_to_three():
    """4 entry points → only first 3 returned."""
    brief = """
## Three Alkira Entry Points

**1. A**
Signal: a.
Solution: a.
Proof: a.

**2. B**
Signal: b.
Solution: b.
Proof: b.

**3. C**
Signal: c.
Solution: c.
Proof: c.

**4. D**
Signal: d.
Solution: d.
Proof: d.
"""
    points = extract_entry_points(brief)
    assert len(points) == 3
    assert points[2]["heading"] == "C"


def test_extract_entry_points_partial_data():
    """Missing field → empty string, no crash."""
    brief = """
## Three Alkira Entry Points

**1. Test entry**
Signal: present.
Proof: also present.
"""
    points = extract_entry_points(brief)
    assert len(points) == 1
    assert points[0]["signal"] == "present."
    assert points[0]["solution"] == ""  # missing
    assert "also present" in points[0]["proof"]


def test_extract_entry_points_word_boundary():
    """Label match must not extend into longer words like 'Signaling'."""
    brief = """
## Three Alkira Entry Points

**1. Test entry**
Signaling: spurious line that should be ignored.
Signal: this is the real signal.
Solution: real solution.
Proof: real proof.

**2. Another entry**
Signal: x.
Solution: y.
Proof: z.

**3. Third**
Signal: a.
Solution: b.
Proof: c.
"""
    points = extract_entry_points(brief)
    assert len(points) == 3
    assert points[0]["signal"] == "this is the real signal."
    assert "spurious" not in points[0]["signal"]


INFRA_BRIEF = """
## Infrastructure Snapshot

**Cloud Platforms:** Azure (confirmed), GCP, Oracle Cloud production workloads.
**On-Prem / Hybrid:** Reduced footprint after 2024 data center consolidation.
**Deployment Model:** Active hybrid cloud migration through 2027.
**Resulting Complexity:** Three clouds plus dozens of acquired networks.
"""


def test_extract_infra_cells_all_four_keys():
    cells = extract_infra_cells(INFRA_BRIEF)
    assert "cloud_platforms" in cells
    assert "on_prem" in cells
    assert "deployment" in cells
    assert "complexity" in cells


def test_extract_infra_cells_content():
    cells = extract_infra_cells(INFRA_BRIEF)
    assert "Azure" in cells["cloud_platforms"]
    assert "2024" in cells["on_prem"]
    assert "2027" in cells["deployment"]
    assert "Three clouds" in cells["complexity"]


def test_extract_infra_cells_missing_section():
    cells = extract_infra_cells("# Just a title")
    assert cells == {
        "cloud_platforms": "",
        "on_prem": "",
        "deployment": "",
        "complexity": "",
    }


def test_extract_infra_cells_no_leaked_bold_markers():
    """Captured values must never contain stray ** markers."""
    cells = extract_infra_cells(INFRA_BRIEF)
    for v in cells.values():
        assert "**" not in v


def test_extract_infra_cells_colon_outside_bold():
    """Bold around label only, colon outside (e.g., ``**Cloud Platforms**: body``)."""
    brief = """
## Infrastructure Snapshot

**Cloud Platforms**: Azure and GCP.
**On-Prem**: Two data centers remaining.
**Deployment**: Hybrid through 2027.
**Complexity**: Multi-cloud sprawl.
"""
    cells = extract_infra_cells(brief)
    assert "Azure" in cells["cloud_platforms"]
    assert "Two data centers" in cells["on_prem"]
    assert "2027" in cells["deployment"]
    assert "Multi-cloud sprawl" in cells["complexity"]
    for v in cells.values():
        assert "**" not in v


def test_extract_infra_cells_label_variants():
    """Singular Cloud Platform, plain On-Prem (no Hybrid), short Complexity work."""
    brief = """
## Infrastructure Snapshot

**Cloud Platform:** Single Azure tenant.
**On-Prem:** Legacy footprint only.
**Deployment Model:** Lift-and-shift in flight.
**Resulting Complexity:** Modest dual-stack overhead.
"""
    cells = extract_infra_cells(brief)
    assert "Single Azure tenant" in cells["cloud_platforms"]
    assert "Legacy footprint" in cells["on_prem"]
    assert "Lift-and-shift" in cells["deployment"]
    assert "Modest" in cells["complexity"]
    for v in cells.values():
        assert "**" not in v
