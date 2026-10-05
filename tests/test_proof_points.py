"""When no customer story fits an angle, the proof is a knowledge-base figure chosen in code."""

from pathlib import Path

import pytest

import brief_doc
import proof_points

KNOWLEDGE_BASE = (Path(__file__).resolve().parent.parent / "skills" / "alkira-customer" / "SKILL.md").read_text(encoding="utf-8")


def test_the_figures_are_read_from_the_knowledge_base_table():
    table = proof_points.load()
    assert table["Cloud connection time reduction"] == "96%"
    assert table["Firewall reduction"] == "73% (up to 82% in some accounts)"
    assert table["Partner onboarding time reduction"] == "98%"
    for metric, value in table.items():
        assert f"| {metric} | {value} |" in KNOWLEDGE_BASE


def test_every_use_case_has_a_headline_metric_that_is_in_the_table():
    use_cases = brief_doc.UseCase.__args__
    assert set(proof_points.METRIC_FOR_USE_CASE) == set(use_cases)
    assert set(proof_points.METRIC_FOR_USE_CASE.values()) <= set(proof_points.load())


@pytest.mark.parametrize("use_case, proof", [
    ("multi_cloud", "Cloud connection time reduction: 96%."),
    ("firewall_consolidation", "Firewall reduction: 73% (up to 82% in some accounts)."),
    ("partner_connectivity", "Partner onboarding time reduction: 98%."),
    ("network_modernization", "TCO reduction: 40-60%."),
    ("site_rollout", "Network provisioning speed improvement: 80%."),
])
def test_the_proof_is_the_metric_and_its_figure_with_no_customer_named(use_case, proof):
    assert proof_points.fallback(use_case, "en") == {"id": "metric", "customer": "", "result": proof}


def test_a_spanish_brief_gets_the_metric_in_spanish_with_the_same_figure():
    story = proof_points.fallback("multi_cloud", "es")
    assert story == {"id": "metric", "customer": "", "result": "Reducción del tiempo de conexión a la nube: 96%."}
    for use_case in proof_points.METRIC_FOR_USE_CASE:
        english, spanish = proof_points.fallback(use_case, "en"), proof_points.fallback(use_case, "es")
        assert english["result"].split(": ", 1)[1] == spanish["result"].split(": ", 1)[1]
        assert english["result"] != spanish["result"]
