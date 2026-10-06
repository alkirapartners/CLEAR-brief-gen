"""When no customer story fits an angle, the proof is a knowledge-base figure chosen in code."""

import re
from pathlib import Path

import pytest

import brief_doc
import proof_points

KNOWLEDGE_BASE = (Path(__file__).resolve().parent.parent / "skills" / "alkira-customer" / "SKILL.md").read_text(encoding="utf-8")


CLOUD = "Less calendar time to add a cloud environment (Nemertes study average)"
FIREWALLS = "Fewer firewalls for cloud (Nemertes study average)"
PARTNER_STAFF = "Less staff time to add an extranet partner (Nemertes study average)"
PARTNER_CALENDAR = "Less calendar time to add an extranet partner (Nemertes study average)"
PROVISIONING = "Provisioning time reduction (Alkira's own figure)"
TCO = "TCO reduction (Alkira's own figure)"


def test_the_figures_are_read_from_the_knowledge_base_table():
    table = proof_points.load()
    assert table[CLOUD] == "96%"
    assert table[FIREWALLS] == "73%"
    assert (table[PARTNER_STAFF], table[PARTNER_CALENDAR]) == ("98%", "91%")
    for metric, value in table.items():
        assert f"| {metric} | {value} |" in KNOWLEDGE_BASE


def test_every_figure_says_whose_it_is_and_is_only_a_figure():
    """An average across the study's customers is labelled as one, so it is never read as a customer's result."""
    for metric, value in proof_points.load().items():
        assert metric.endswith(("(Nemertes study average)", "(Alkira's own figure)")), metric
        assert re.fullmatch(r"\d+(-\d+)?%", value), (metric, value)


def test_no_figure_claims_network_availability():
    assert not any("availab" in metric.lower() for metric in proof_points.load())


def test_every_use_case_has_a_headline_metric_that_is_in_the_table():
    use_cases = brief_doc.UseCase.__args__
    assert set(proof_points.METRIC_FOR_USE_CASE) == set(use_cases)
    assert set(proof_points.METRIC_FOR_USE_CASE.values()) <= set(proof_points.load())


@pytest.mark.parametrize("use_case, proof", [
    ("multi_cloud", f"{CLOUD}: 96%."),
    ("firewall_consolidation", f"{FIREWALLS}: 73%."),
    ("partner_connectivity", f"{PARTNER_STAFF}: 98%."),
    ("network_modernization", f"{TCO}: 40-60%."),
    ("site_rollout", f"{PROVISIONING}: 80%."),
    ("m_and_a", f"{PROVISIONING}: 80%."),
    ("china_global", f"{PROVISIONING}: 80%."),
])
def test_the_proof_is_the_metric_and_its_figure_with_no_customer_named(use_case, proof):
    assert proof_points.fallback(use_case, "en") == {"id": "metric", "customer": "", "result": proof}


def test_a_spanish_brief_gets_the_metric_in_spanish_with_the_same_figure():
    story = proof_points.fallback("multi_cloud", "es")
    assert story == {
        "id": "metric", "customer": "",
        "result": "Menos tiempo calendario para agregar un entorno de nube (promedio del estudio de Nemertes): 96%.",
    }
    for use_case in proof_points.METRIC_FOR_USE_CASE:
        english, spanish = proof_points.fallback(use_case, "en"), proof_points.fallback(use_case, "es")
        assert english["result"].split(": ", 1)[1] == spanish["result"].split(": ", 1)[1]
        assert english["result"] != spanish["result"]
