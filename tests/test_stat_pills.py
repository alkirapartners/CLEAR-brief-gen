"""The stats at the top of the current page are short pills: five basics, each a few words."""

import pytest

import i18n
import stat_pills
from tests.brief_fixtures import SAMPLE_DOC, make_doc

EN = i18n.LABELS["en"]


@pytest.mark.parametrize("written, shown", [
    ("Dallas, TX", "Dallas, TX"),
    ("2323 Victory Avenue, Dallas, Texas", "Dallas, Texas"),
    ("4200 Six Forks Road, Raleigh, North Carolina", "Raleigh, North Carolina"),
    ("Miami, FL (and Dallas)", "Miami, FL"),
    ("Changsha, Hunan, China", "Changsha, China"),
    ("Houston, Texas, United States", "Houston, Texas"),
    ("One Microsoft Way, Redmond, WA 98052", "Redmond, WA"),
    ("Atlanta", "Atlanta"),
    ("Atlanta, Georgia; operations office in Columbus", "Atlanta, Georgia"),
    ("", ""),
])
def test_headquarters_is_a_city_and_its_state_or_country(written, shown):
    assert stat_pills.headquarters(written) == shown


@pytest.mark.parametrize("written, shown", [
    ("$26,869 million sales and other revenues, FY2025", "$26.9B (FY2025)"),
    ("$8.6B FY2025 net sales from continuing operations", "$8.6B (FY2025)"),
    ("FY2025 GAAP revenue $7.71B; adjusted net revenue $9.32B", "$7.7B (FY2025)"),
    ("$4,789.7 million total revenues in 2025", "$4.8B (2025)"),
    ("CNY 30.514B in 2025, up 23.49% (per Ebrun, trade press)", "CNY 30.5B (2025)"),
    ("$88.7B (FY2025)", "$88.7B (FY2025)"),
    ("$28B", "$28B"),
    ("About US$26B (Forbes, 2023, via Wikipedia)", "About $26B (2023)"),
    ("€412 million in FY24", "€412M (FY24)"),
    ("$1.2 trillion", "$1.2T"),
    ("2025 operating revenue 30.514 billion yuan, up 23.49% (trade press)", "CNY 30.5B (2025)"),
    ("Revenue of 412 million euros in 2025", "€412M (2025)"),
    ("", ""),
])
def test_revenue_is_one_rounded_figure_and_its_year(written, shown):
    assert stat_pills.revenue(written) == shown


def test_revenue_that_holds_no_amount_is_cut_short_not_invented():
    assert stat_pills.revenue("Not disclosed") == "Not disclosed"
    long = "Privately held and does not publish revenue figures of any kind"
    assert len(stat_pills.revenue(long)) <= stat_pills.MAX_PILL_CHARS and stat_pills.revenue(long).endswith("...")


@pytest.mark.parametrize("written, shown", [
    ("5,165 at Dec 31, 2025", "5,165"),
    ("About 7,400 at 2025 year-end", "About 7,400"),
    ("About 28,274 full-time and 25,733 part-time team members", "About 28,274 full-time"),
    ("6,304 at 2025-12-31 (56.3% in R&D)", "6,304"),
    ("About 460,000 (370,000 US, 90,000 international)", "About 460,000"),
    ("more than 10,000", "More than 10,000"),
    ("5,200", "5,200"),
    ("", ""),
])
def test_employees_is_the_count_and_nothing_after_it(written, shown):
    assert stat_pills.employees(written) == shown


@pytest.mark.parametrize("written, shown", [
    ("Independent energy company: refining and marketing of gasoline, diesel and jet fuel", "Independent energy company"),
    ("Logistics and package delivery, with a growing healthcare cold chain business", "Logistics and package delivery"),
    ("Insurance (property and casualty, life)", "Insurance"),
    ("Automotive aftermarket parts retail", "Automotive aftermarket parts retail"),
    ("Refining", "Refining"),
    ("Automotive parts retail and distribution", "Automotive parts retail..."),  # never cut on "and"
])
def test_industry_is_a_few_words(written, shown):
    assert stat_pills.industry(written) == shown


@pytest.mark.parametrize("written, listing, shown", [
    ("Public, NYSE: DINO", "NYSE: DINO", "Public (NYSE: DINO)"),
    ("Public (NYSE: UPS)", "NYSE: UPS", "Public (NYSE: UPS)"),
    ("Public, A+H listed (Shenzhen and Hong Kong)", "SHE: 300866", "Public (SHE: 300866)"),
    ("Public", "AAP (NYSE)", "Public (NYSE: AAP)"),
    ("Private, family-owned", "", "Private"),
    ("", "NYSE: OXY", "NYSE: OXY"),
    ("NYSE: OXY", "NYSE: OXY", "NYSE: OXY"),
    ("", "", ""),
])
def test_ownership_states_the_ticker_once(written, listing, shown):
    assert stat_pills.ownership(written, listing) == shown


# ── The line the page splits into pills ──────────────────────────

def test_only_the_basics_the_page_was_built_for_become_pills():
    line = stat_pills.line(make_doc(), EN)
    assert line == "HQ: Dallas, TX | Revenue: $28B | Employees: 5,200 | Industry: Refining | Ownership: Public (NYSE: NWE)"
    for absent in ("Entity", "Cloud and network", "Northwind Energy Corporation"):
        assert absent not in line


def test_no_pill_is_longer_than_the_page_can_show_and_none_can_split_the_line():
    stats = {
        "hq": "A Very Long Unpunctuated Headquarters Name That Never Ends Anywhere",
        "revenue": "No figure | see filings for the details of every segment",
        "employees": "A workforce spread | across many countries and subsidiaries worldwide",
        "industry": "Diversified industrial conglomerate with holdings in everything imaginable",
        "ownership": "Controlled by a holding company | owned by a family trust in turn",
        "cloud_network": "x",
    }
    pills = stat_pills.pills(make_doc(stats=stats), EN)
    assert len(pills) == 5
    for _, value in pills:
        assert len(value) <= stat_pills.MAX_PILL_CHARS and "|" not in value


def test_a_basic_that_was_not_found_has_no_pill():
    stats = {**SAMPLE_DOC["stats"], "revenue": "", "employees": " "}
    labels = [label for label, _ in stat_pills.pills(make_doc(stats=stats), EN)]
    assert labels == ["HQ", "Industry", "Ownership"]
