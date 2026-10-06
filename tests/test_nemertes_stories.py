"""The Nemertes case studies in the knowledge base say what the report says, one row per case."""

import re
from pathlib import Path

import pytest

import case_studies

SKILLS = Path(__file__).resolve().parent.parent / "skills" / "alkira-customer"
KNOWLEDGE_BASE_FILES = ("SKILL.md", "references/case-studies.md", "references/pricing.md")
QUALIFIER = "(Nemertes study)"
# Each case in the report with the one figure its row carries.
CASES: dict[str, str] = {
    "software-datacenter": "90% less network engineer time",
    "nemertes-healthcare-provider": "300% more cloud environments",
    "nemertes-investment-institution": "88% fewer VPN tunnels per partner",
    "nemertes-medical-manufacturer": "99.8% decrease in time to merge in an acquired company's network",
    "nemertes-financial-extranet": "88% less staff time to add an extranet partner",
    "nemertes-software-services": "600 VPCs and VNets",
    "nemertes-financial-telecoms": "from 80 to 120 days to 3 days",
    "nemertes-manufacturer": "in 2 weeks, not 2 years",
    "nemertes-financial-multicloud": "200% more cloud environments",
    "nemertes-software-acquirer": "60% fewer firewalls for cloud",
    "nemertes-telecom": "200% more cloud regions",
    "nemertes-biotech": "98% reduction in the number of WAN outages",
}
# The study's average cut in firewalls. One partner sheet prints it beside a named customer.
FIREWALL_AVERAGE = "73%"
# How the knowledge base words the study's averages. A line that quotes one says it is an average.
AVERAGES_AS_WORDED = ("73%", "96%", "47%", "98% less staff time")


def _nemertes_stories() -> list[case_studies.Story]:
    return [story for story in case_studies.load_stories() if story.customer.endswith(QUALIFIER)]


def test_the_report_s_twelve_cases_each_have_one_anonymous_row():
    stories = _nemertes_stories()
    assert {story.id for story in stories} == set(CASES)
    assert not any(story.public for story in stories)
    assert len({story.customer for story in stories}) == len(stories)


@pytest.mark.parametrize("story_id, figure", sorted(CASES.items()))
def test_each_case_carries_its_own_figure(story_id, figure):
    story = case_studies.story_by_id(story_id)
    assert story is not None and figure in story.result


def test_the_firewall_example_stands_alone():
    """76 firewalls to 14 is one healthcare enterprise. The study's healthcare provider is another customer."""
    example = case_studies.story_by_id("healthcare-firewalls")
    provider = case_studies.story_by_id("nemertes-healthcare-provider")
    assert QUALIFIER not in example.customer
    assert "76" not in provider.result and "14" not in provider.result


def test_the_average_cut_in_firewalls_is_never_one_customer_s_result():
    for story in case_studies.load_stories():
        assert FIREWALL_AVERAGE not in story.result, story.id


@pytest.mark.parametrize("name", KNOWLEDGE_BASE_FILES)
def test_the_knowledge_base_claims_no_availability_figure_and_no_outage_record(name):
    text = (SKILLS / name).read_text(encoding="utf-8")
    assert not re.search(r"\d%\+?[^.|\n]*availab|availab[^.|\n]*\d%", text, re.IGNORECASE)
    assert "unplanned outage" not in text.lower()


@pytest.mark.parametrize("gone", [
    "82%", "60-88%", "67-90%", "88% reduction in operational time", "88% less operational time",
    "Up to 1650%", "validated by Nemertes",
])
def test_figures_no_source_gives_are_gone_from_the_knowledge_base(gone):
    for name in KNOWLEDGE_BASE_FILES:
        assert gone not in (SKILLS / name).read_text(encoding="utf-8"), name


def test_the_averages_are_labelled_as_averages_wherever_they_are_quoted():
    """A line of the knowledge base that quotes a study average says it is one."""
    for name in KNOWLEDGE_BASE_FILES:
        for line in (SKILLS / name).read_text(encoding="utf-8").splitlines():
            if any(average in line for average in AVERAGES_AS_WORDED):
                assert "average" in line.lower(), (name, line)
