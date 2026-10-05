"""A quote is evidence only when the page really says it."""

import pytest

import quotes

PAGE = (
    "# Senior Network Engineer\n\n"
    "Posted 23 September. You will run our **Azure ExpressRoute** circuits and the\n"
    "[Virtual WAN](https://learn.example.com/vwan) hub-and-spoke in three regions.\n\n"
    "- Palo Alto firewalls in every hub\n"
    "- BGP peering with two carriers\n"
    "The team supports 5,200 employees “across refining and marketing”.\n"
)


@pytest.mark.parametrize("quote", [
    "You will run our Azure ExpressRoute circuits",
    "you will run our azure expressroute circuits and the virtual wan hub-and-spoke",  # case, markdown, link
    "You will run our Azure ExpressRoute circuits and the\nVirtual WAN hub-and-spoke in three regions.",
    "Palo Alto firewalls in every hub BGP peering with two carriers",  # list layout
    'supports 5,200 employees "across refining and marketing"',  # straight for curly quotes
    "Azure ExpressRoute circuits ... Palo Alto firewalls in every hub",  # two passages joined
    "Azure ExpressRoute circuits [...] BGP peering with two carriers",
    "Azure ExpressRoute circuits … BGP peering with two carriers",
], ids=["exact", "case-and-markup", "line-break", "list", "curly", "joined", "bracketed", "ellipsis-char"])
def test_a_passage_the_page_holds_is_found_whatever_its_layout(quote):
    assert quotes.is_on_page(quote, PAGE)


@pytest.mark.parametrize("quote", [
    "You will run our AWS Direct Connect circuits",  # the page says Azure ExpressRoute
    "The team supports 52,000 employees across refining",  # a changed figure
    "Azure ExpressRoute circuits ... a Cisco ACI fabric in two data centers",  # second passage invented
    "hub-and-spoke in five regions",
    "Azure",  # too short to prove anything
    "Azure ... BGP ... hub",  # shreds: each on the page, none a passage
    "", "   ", "...",
], ids=["other-cloud", "changed-figure", "half-invented", "changed-word", "one-word", "shreds", "empty", "blank", "dots"])
def test_a_passage_the_page_does_not_hold_is_not_found(quote):
    assert not quotes.is_on_page(quote, PAGE)


def test_a_link_target_on_the_page_is_not_part_of_what_the_page_says():
    assert not quotes.is_on_page("learn.example.com/vwan hub-and-spoke in three regions", PAGE)


def test_a_long_page_is_searched_to_the_end():
    page = "Filler sentence about nothing in particular. " * 20_000 + "The lubricants business will be separated by year end."
    assert quotes.is_on_page("The lubricants business will be separated by year end.", page)


def test_the_limits_are_named():
    assert quotes.MIN_QUOTE_CHARS >= 20 and quotes.MIN_PART_CHARS >= 10


def test_a_page_built_to_stall_the_check_is_handled_in_linear_time():
    """A page of unclosed link openings once took time that grew with the square of its length."""
    import time
    hostile = "](" * 400_000 + " The lubricants business will be separated by year end."
    started = time.perf_counter()
    found = quotes.is_on_page("The lubricants business will be separated by year end.", hostile)
    assert found and time.perf_counter() - started < 3.0


def test_a_link_target_is_still_removed_when_it_is_long_but_ordinary():
    page = "Runs on [Virtual WAN](https://learn.example.com/" + "a" * 500 + ") hub-and-spoke in three regions."
    assert quotes.is_on_page("Virtual WAN hub-and-spoke in three regions", page)


def test_long_unclosed_openings_are_linear_too():
    import time
    hostile = ("](" + "a" * 2000) * 400 + " The lubricants business will be separated by year end."
    started = time.perf_counter()
    assert quotes.is_on_page("The lubricants business will be separated by year end.", hostile)
    assert time.perf_counter() - started < 3.0


# ── A quote has to state the fact, not merely be on the page ─────
#
# Every figure in a fact has to be in its quote. Every name in it (a product,
# a vendor, a technology, a place, a company) has to be somewhere on the page.

COOKIES = "We use cookies to improve your experience."
TITLE = "Senior Cisco ACI Engineer | Careers at Example Payments"
SHELL_PAGE = f"{TITLE}\n{COOKIES} By continuing to browse you agree to our use of cookies. Sign in. Search jobs."
# What the HF Sinclair pages really look like: a dateline, then the news.
RELEASE = (
    "DALLAS--(BUSINESS WIRE)--Jul. 28, 2026-- HF Sinclair Corporation (NYSE: DINO) (\"HF Sinclair\" or the "
    "\"Company\") today announced that its Board of Directors has approved plans to pursue a separation of its "
    "Lubricants & Specialties business into a new independent, publicly traded company. The transaction is "
    "intended to be executed over the next 12-18 months. The Company also plans to retire its base oil "
    "refining assets in Mississauga, Ontario."
)
FILING = (
    "HF Sinclair Corporation. Address of principal executive offices: 2323 Victory Avenue, Suite 1400, Dallas, "
    "Texas 75219. Common Stock $0.01 par value DINO New York Stock Exchange. As of December 31, 2025, we had "
    "5,165 employees."
)


def _unsupported(fact, quote, page, context=()):
    names = quotes.missing_names(fact, quotes.bare(page), context, quotes.initials(page))
    return quotes.missing_figures(fact, quote), names


# The two facts the review showed slipping through. Both must still fail.

def test_a_detailed_fact_quoted_from_a_page_that_showed_only_its_title_is_not_supported():
    fact = "The role needs Cisco ACI, BGP and Palo Alto firewalls across two data centers."
    figures, names = _unsupported(fact, TITLE, SHELL_PAGE)
    assert names == ("BGP", "Palo", "Alto")  # the page never says them
    assert quotes.is_on_page(TITLE, SHELL_PAGE)  # though the quote itself is on the page


def test_a_figure_quoted_from_the_cookie_banner_is_not_supported():
    fact = "The company runs 14 data centers on Cisco ACI."
    figures, names = _unsupported(fact, COOKIES, SHELL_PAGE)
    assert figures == ("14",) and names == ()  # Cisco ACI is on the page, the 14 is nowhere near the quote


# The two real facts the stricter rule threw away. Both must be kept.

def test_the_headquarters_fact_is_kept_when_the_filing_names_the_place_outside_the_quote():
    fact = "HF Sinclair is headquartered in Dallas, Texas and trades on NYSE as DINO; it had 5,165 employees."
    quote = "As of December 31, 2025, we had 5,165 employees."
    assert _unsupported(fact, quote, FILING, ("HF Sinclair",)) == ((), ())


def test_the_separation_fact_is_kept_when_the_release_names_the_city_in_its_dateline():
    fact = (
        "HF Sinclair (NYSE: DINO), Dallas, announced plans to separate its Lubricants & Specialties segment "
        "into a new independent public company over the next 12-18 months, and to retire Mississauga assets."
    )
    quote = "plans to pursue a separation of its Lubricants & Specialties business ... executed over the next 12-18 months"
    assert quotes.is_on_page(quote, RELEASE)
    assert _unsupported(fact, quote, RELEASE, ("HF Sinclair",)) == ((), ())


# ── Figures: in the quote ────────────────────────────────────────

@pytest.mark.parametrize("fact, quote, missing", [
    ("Revenue was $28.4 billion.", "Revenue was $26.9 billion in the year.", ("28.4",)),
    ("It closed 522 stores and opened 39.", "we closed 522 stores during the year", ("39",)),
    ("On November 3, 2025 it paid $1.6 billion for 31 sites.", "it paid $1.6 billion for the business", ("31",)),
], ids=["changed-figure", "half-quoted", "beside-a-date"])
def test_a_figure_the_quote_does_not_hold_is_reported(fact, quote, missing):
    assert quotes.missing_figures(fact, quote) == missing


@pytest.mark.parametrize("fact, quote", [
    ("It closed 522 stores and opened 39 in the year.", "we closed 522 stores and opened 39 new stores"),
    ("Revenue was $26,869 million.", "Sales and other revenues 26,869"),
    ("The FY2025 10-K says the lubricants business will be separated in Q2.", "the lubricants business will be separated"),
    ("The network runs SD-WAN at 5 refineries.", "our SD WAN connects 5 refineries"),
    ("Overseas revenue was 96.62% of the total.", "overseas revenue accounted for 96.62%"),
    ("It completed the acquisition on November 3, 2025.", "it has completed the acquisition"),
    ("The role was posted Oct 30 2024 and covers VPC networking.", "Strong understanding of VPC networking"),
    ("The sale of Worldpac closed 2024-11-04.", "announced the close of the sale of Worldpac, Inc."),
    ("Income fell in the sixteen weeks ended April 25, 2026.", "income recognized in the sixteen weeks ended"),
    ("The plan was approved on 13 November 2024.", "the Board approved the plan"),
    ("Posted October 30th 2024 for VPC networking.", "VPC networking, and IAM"),
], ids=["figures", "thousands", "labels", "count", "percent", "month-day-year", "abbreviated", "iso", "week-ended", "day-first", "ordinal"])
def test_figures_in_the_quote_are_found_and_dates_and_labels_are_not_figures(fact, quote):
    assert quotes.missing_figures(fact, quote) == ()


# ── Names: somewhere on the page ─────────────────────────────────

def test_a_name_the_page_never_says_is_reported():
    page = quotes.bare("We need experience with Azure ExpressRoute and BGP in our Dallas office.")
    assert quotes.missing_names("The posting asks for AWS Direct Connect in Dallas.", page) == ("AWS", "Direct", "Connect")
    assert quotes.missing_names("The posting asks for ExpressRoute and BGP in Dallas.", page) == ()
    assert quotes.missing_names("Azure is the primary cloud.", page) == ()  # a sentence may start with a name the page has
    assert quotes.missing_names("A role is listed.", page) == ()


def test_what_names_the_source_does_not_have_to_be_on_the_page():
    """The company and the page are known from where the fact came from."""
    page = quotes.bare("hybrid connectivity using ExpressRoute")
    fact = "Northwind Energy's posting on the Kestrel site asks for ExpressRoute."
    assert quotes.missing_names(fact, page) == ("Energy", "Kestrel")  # a sentence's first word is not judged
    context = ("Northwind Energy", "https://careers.kestrel.example/job/1")
    assert quotes.missing_names(fact, page, context) == ()


def test_an_acronym_is_on_the_page_when_the_page_spells_it_out():
    """A filing says "New York Stock Exchange". The researcher writes NYSE."""
    text = "Common Stock DINO New York Stock Exchange. Offices in the United States of America."
    page, spelled = quotes.bare(text), quotes.initials(text)
    assert quotes.missing_names("It trades on the NYSE as DINO in the USA.", page, (), spelled) == ()
    assert quotes.missing_names("It trades on the LSE as DINO.", page, (), spelled) == ("LSE",)
    assert quotes.missing_names("It trades on the NYSE.", page) == ("NYSE",)  # not without the page's initials
