"""The stories taken from published material: who is named, what each row says, and what it leaves out."""

import re
from pathlib import Path

import pytest

import case_studies

CASE_STUDIES = (
    Path(__file__).resolve().parent.parent / "skills" / "alkira-customer" / "references" / "case-studies.md"
).read_text(encoding="utf-8")
# The customers a published source names. Every other story is anonymous.
NAMED = {"michaels", "koch", "tekion", "sp-global", "chart", "warner"}


def _story(story_id: str) -> case_studies.Story:
    story = case_studies.story_by_id(story_id)
    assert story is not None, story_id
    return story


def test_only_customers_a_published_source_names_are_named():
    assert {story.id for story in case_studies.load_stories() if story.public} == NAMED


def test_every_use_case_has_a_story_and_china_and_partner_connectivity_have_a_named_one():
    stories = case_studies.load_stories()
    for use_case in case_studies.SITUATIONS:
        assert any(use_case in story.situations for story in stories), use_case
    for use_case in ("china_global", "partner_connectivity"):
        assert any(story.public and use_case in story.situations for story in stories), use_case


def test_koch_states_the_china_expansion_with_no_number_on_it():
    koch = _story("koch")
    assert set(koch.situations) == {"multi_cloud", "m_and_a", "china_global"}
    assert "10 transport hubs with 2 Alkira Cloud Exchange Points" in koch.result
    china = next(clause for clause in koch.result.split(",") if "China" in clause)
    assert "mainland China" in china and not re.search(r"\d", china)


def test_chart_is_not_given_the_figure_its_source_states_for_two_customers_together():
    chart = _story("chart")
    assert chart.customer == "Chart Industries" and set(chart.situations) == {"m_and_a", "multi_cloud"}
    assert "from 40 to over 130 global sites" in chart.result
    section = CASE_STUDIES.split("### Chart Industries", 1)[1].split("\n### ", 1)[0]
    assert "60 VPN endpoints installed in 3 days" in section
    assert "99%" not in chart.result and "99%" not in section


def test_warner_is_a_hospitality_story_about_changes_made_in_minutes():
    warner = _story("warner")
    assert warner.customer == "Warner Hotels" and warner.industry == "Hospitality"
    assert "network_modernization" in warner.situations
    assert "days or weeks" in warner.result and "minutes" in warner.result and "18 UK properties" in warner.result


def test_s_and_p_global_is_an_extranet_and_m_and_a_story():
    story = _story("sp-global")
    assert {"partner_connectivity", "m_and_a", "multi_cloud"} == set(story.situations)
    assert "extranet as a service" in story.result


def test_tekion_says_only_what_its_case_study_says():
    assert not re.search(r"\d", _story("tekion").result)


def test_michaels_keeps_its_one_figure():
    michaels = _story("michaels")
    assert "1,400 stores" in michaels.result and "three weeks" in michaels.result
    section = CASE_STUDIES.split("### Michaels", 1)[1].split("\n### ", 1)[0]
    assert re.findall(r"\d[\d,]*X?", section) == ["1,400", "1,400"]


@pytest.mark.parametrize("story_id, customer, figure", [
    ("canada-professional-services", "A leading Canadian professional services organization", "0 networking hires"),
    ("finserv-egress", "A global financial services company", "over $800,000 annually in cloud egress fees"),
    ("retail-colocation", "A retail customer", "$3M in upfront costs per colocation hub"),
])
def test_an_anonymous_story_is_labelled_as_its_source_labels_it(story_id, customer, figure):
    story = _story(story_id)
    assert story.public is False and story.customer == customer and figure in story.result


def test_the_fortune_50_healthcare_company_has_no_figure_and_no_other_description():
    story = _story("fortune50-healthcare")
    assert story.public is False and story.customer == "A Fortune 50 healthcare company"
    assert set(story.situations) == {"multi_cloud", "m_and_a", "partner_connectivity"}
    assert not re.search(r"\d", story.result)


@pytest.mark.parametrize("term", ["TCV", "deal value", "commitment", "three-year", "3-year", "discount"])
def test_no_story_states_a_deal_size_or_a_contract_term(term):
    assert term.lower() not in CASE_STUDIES.lower()
