"""The knowledge base and the template carry the fit rules and the rubric."""

from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parent.parent / "skills"
KNOWLEDGE_BASE = (SKILLS / "alkira-customer" / "SKILL.md").read_text(encoding="utf-8")
TEMPLATE = (SKILLS / "alkira-brief-template" / "SKILL.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("rule", [
    "**One clear use case is enough.**",
    "Hand-built cloud-native networking is a positive signal, never a negative one.",
    "One cloud is enough when the network around it is complex.",
    "**Supporting only.**",
    "a new CIO or head of infrastructure",
    "**Never fit evidence.**",
    "SAP, Workday or other ERP projects",
    "A data-broker profile is a last resort and must be labelled as one.",
])
def test_the_knowledge_base_states_the_fit_rules(rule):
    assert rule in KNOWLEDGE_BASE


@pytest.mark.parametrize("use_case", [
    "multi_cloud", "china_global", "firewall_consolidation", "m_and_a",
    "network_modernization", "site_rollout", "partner_connectivity",
])
def test_every_use_case_has_an_id_in_the_fit_rules(use_case):
    assert f"`{use_case}`" in KNOWLEDGE_BASE


@pytest.mark.parametrize("row", [
    "| 5 | Two different use cases, each resting on a first-hand source of its own, and at least one of those sources dated within the last two years |",
    "| 4 | One use case resting on a first-hand source dated within the last two years |",
    "| 3 | A use case whose evidence is second-hand, undated or older than two years |",
    "| 2 | A plausible use case with no evidence found |",
    "| 1 | No use case |",
])
def test_the_template_scores_the_best_use_case_not_the_volume_of_evidence(row):
    assert row in TEMPLATE
    assert "never the number of boxes checked" in TEMPLATE


def test_the_template_says_what_second_hand_evidence_can_and_cannot_do():
    assert "cannot lift the score above 3" in TEMPLATE
    assert "one use case told twice" in TEMPLATE
    assert "a score they do not support is lowered" in TEMPLATE


def test_the_template_never_asks_for_three_entry_points():
    assert "Never pad to three." in TEMPLATE
    assert "A score of 1 or 2 has no angles." in TEMPLATE
    for retired in ("Three Alkira Entry Points", "Multiple entry points with direct evidence", "TWO PRINTED PAGES"):
        assert retired not in TEMPLATE


def test_the_research_checklist_puts_first_hand_sources_first_and_brokers_last():
    careers = TEMPLATE.index("The company's own careers site and job postings")
    filings = TEMPLATE.index("Filings and the annual report")
    brokers = TEMPLATE.index("Data brokers")
    assert careers < filings < brokers
    assert "A fact counts only when it is stated on a page that was opened." in TEMPLATE


def test_no_skill_file_holds_a_year_that_would_date_the_cached_prefix():
    for path in sorted(SKILLS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for year in ("2025", "2026", "2027"):
            assert year not in text, f"{year} in {path.name}"
