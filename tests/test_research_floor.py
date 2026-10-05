"""The research floor: what research must have tried before it may stop."""

import pytest

import research_floor as floor
from evidence import EvidenceItem, Page

CAREERS_PAGES = (
    Page("https://careers.acme.com/job/123", 900),
    Page("https://acme.wd5.myworkdayjobs.com/en-US/careers/job/Senior-Network-Engineer_R1", 900),
)
ALL_TOPICS = frozenset(floor.SNAPSHOT_TOPICS)


def _search(query, site="", recent_news=False):
    return floor.attempted("web_search", {"query": query, "site": site, "recent_news": recent_news})


def _read(url):
    return floor.attempted("read_page", {"url": url, "find": ""})


def _fact(category):
    return EvidenceItem("A fact.", category, "https://careers.acme.com/job/123", opened=True)


def _open(attempts=frozenset(), pages=(), evidence=None, searches=floor.MIN_SEARCHES):
    """Open items. Unless told otherwise, every opened page gave one recorded fact."""
    if evidence is None:
        evidence = [EvidenceItem("A fact.", "people", page.url, opened=True) for page in pages]
    return floor.open_items(frozenset(attempts), pages, evidence, searches)


# ── What a tool call is an attempt at ────────────────────────────

@pytest.mark.parametrize("attempts, key", [
    (_search("Acme careers network engineer"), floor.CAREERS_SITE),
    (_search("Acme senior network engineer job posting"), floor.CAREERS_SITE),
    (_search("network", site="careers.acme.com"), floor.CAREERS_SITE),
    (_read("https://www.acme.com/careers/search?q=network"), floor.CAREERS_SITE),
    (_read("https://jobs.acme.com/us/en/job/R-1/Principal-Network-Engineer"), floor.CAREERS_SITE),
    (_search("Acme network engineer", site="myworkdayjobs.com"), floor.HOSTED_JOBS),
    (_search("Acme workday network engineer jobs"), floor.HOSTED_JOBS),
    (_read("https://boards.greenhouse.io/acme/jobs/1"), floor.HOSTED_JOBS),
    (_search("Acme 10-K annual report"), floor.FILING),
    (_search("Acme acquisitions data center", site="sec.gov"), floor.FILING),
    (_read("https://www.sec.gov/Archives/edgar/data/1/acme-10k.htm"), floor.FILING),
    (_read("https://investors.acme.com/static/annual-report.pdf"), floor.FILING),
    (_search("Acme AWS Azure cloud provider"), "clouds"),
    (_search("Acme ExpressRoute Direct Connect"), "cloud_connectivity"),
    (_search("Acme SD-WAN MPLS"), "wan"),
    (_search("Acme Palo Alto firewall"), "firewalls"),
    (_search("Acme data center colocation"), "data_centers"),
    (_search("Acme SCADA OT network"), "plant_networks"),
    (_search("Acme network", recent_news=True), floor.NEWS),
    (_search("Acme acquisition completed press release"), floor.NEWS),
    (_search("Acme announces divestiture"), floor.NEWS),
    (_read("https://www.prnewswire.com/news-releases/acme-completes-acquisition-1.html"), floor.NEWS),
    (_read("https://investors.acme.com/news/press-releases/detail/39/acme-and-google"), floor.NEWS),
])
def test_a_call_counts_as_an_attempt_at_what_it_was_aimed_at(attempts, key):
    assert key in attempts


def test_a_call_about_something_else_is_no_attempt_at_the_floor():
    assert _search("Acme headquarters ticker") == frozenset()
    assert _read("https://www.acme.com/about") == frozenset()
    assert floor.attempted("record_evidence", {"items": []}) == frozenset()
    assert floor.attempted("web_search", {"query": None}) == frozenset()


# ── What is still open ───────────────────────────────────────────

def test_at_the_start_everything_is_open():
    assert _open(searches=0) == (floor.CAREERS, floor.FILING, floor.NEWS, *floor.SNAPSHOT_TOPICS, floor.DEPTH)


def test_the_past_year_s_news_is_answered_once_it_has_been_searched():
    assert floor.NEWS in _open()
    assert floor.NEWS not in _open({floor.NEWS})


def test_two_job_pages_opened_answer_for_careers():
    assert floor.CAREERS not in _open(pages=CAREERS_PAGES)
    assert floor.CAREERS in _open(pages=CAREERS_PAGES[:1])


def test_a_job_page_that_gave_no_fact_was_not_really_read():
    """A posting that came back as a title and a cookie notice does not count as reached."""
    one_real = [EvidenceItem("Lists SD-WAN.", "network", CAREERS_PAGES[0].url, opened=True)]
    assert floor.CAREERS in _open(pages=CAREERS_PAGES, evidence=one_real)
    assert floor.CAREERS in _open(pages=CAREERS_PAGES, evidence=[])


def test_careers_is_also_answered_by_trying_both_the_site_and_a_hosted_job_site():
    assert floor.CAREERS in _open({floor.CAREERS_SITE})
    assert floor.CAREERS in _open({floor.HOSTED_JOBS})
    assert floor.CAREERS not in _open({floor.CAREERS_SITE, floor.HOSTED_JOBS})


def test_the_filing_is_answered_once_it_has_been_tried():
    assert floor.FILING in _open()
    assert floor.FILING not in _open({floor.FILING})


@pytest.mark.parametrize("topic, category", [
    ("clouds", "cloud"), ("cloud_connectivity", "cloud_connectivity"), ("wan", "network"),
    ("firewalls", "security"), ("data_centers", "data_center"),
])
def test_a_snapshot_line_is_answered_by_a_recorded_fact_or_by_a_search_for_it(topic, category):
    assert topic in _open()
    assert topic not in _open(evidence=[_fact(category)])
    assert topic not in _open({topic})


def test_plant_networks_are_never_demanded_since_many_companies_have_none():
    assert "plant_networks" not in floor.SNAPSHOT_TOPICS
    assert "plant_networks" not in _open()


def test_a_run_that_has_barely_looked_is_still_open_on_depth():
    done = {floor.CAREERS_SITE, floor.HOSTED_JOBS, floor.FILING, floor.NEWS, *ALL_TOPICS}
    eight = tuple(Page(f"https://acme.com/{i}", 900) for i in range(floor.MIN_PAGES_OPENED))
    assert _open(done, pages=eight[:3], searches=4) == (floor.DEPTH,)
    assert _open(done, pages=eight, searches=4) == (floor.DEPTH,)
    assert _open(done, pages=eight, searches=floor.MIN_SEARCHES) == ()


def test_the_floor_is_half_the_budget_or_less_so_it_can_always_be_met():
    import research_tools
    assert floor.MIN_SEARCHES <= research_tools.MAX_SEARCHES // 2
    assert floor.MIN_PAGES_OPENED <= research_tools.MAX_PAGES // 2


# ── Telling the model ────────────────────────────────────────────

def test_open_items_are_named_in_one_line_and_explained_in_full():
    open_now = (floor.CAREERS, floor.FILING, floor.NEWS, "wan", floor.DEPTH)
    line = floor.summary(open_now)
    assert line == (
        "Not covered yet: careers site and job postings; latest annual filing; "
        "news from the past year; WAN; more searches and pages."
    )
    assert floor.summary(()) == "The research checklist is covered."
    full = floor.instructions(open_now, searches=4, pages_opened=3)
    assert "myworkdayjobs.com" in full and "sec.gov" in full and "SD-WAN" in full
    assert "4 searches and 3 pages so far" in full
    assert "recent_news" in full and "revenue" in full
    assert len(full.splitlines()) == 5 and all(line.startswith("- ") for line in full.splitlines())
