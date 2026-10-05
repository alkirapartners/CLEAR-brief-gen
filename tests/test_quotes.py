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

COOKIES = "We use cookies to improve your experience."
TITLE = "Senior Cisco ACI Engineer | Careers at Example Payments"


@pytest.mark.parametrize("fact, quote, missing", [
    ("The role needs Cisco ACI, BGP and Palo Alto firewalls across two data centers.", TITLE, ("BGP", "Palo", "Alto")),
    ("The company runs 14 data centers on Cisco ACI.", COOKIES, ("14", "Cisco", "ACI")),
    ("Revenue was $28.4 billion.", "Revenue was $26.9 billion in the year.", ("28.4",)),
    ("The posting asks for AWS Direct Connect.", "experience with Azure ExpressRoute required", ("AWS", "Direct", "Connect")),
    ("It closed 522 stores and opened 39.", "we closed 522 stores during the year", ("39",)),
], ids=["title-only", "cookie-notice", "changed-figure", "other-cloud", "half-quoted"])
def test_a_figure_or_a_name_the_quote_does_not_hold_is_reported(fact, quote, missing):
    assert quotes.missing_from_quote(fact, quote) == missing


@pytest.mark.parametrize("fact, quote", [
    ("The posting asks for ExpressRoute, Virtual WAN and BGP.", "experience with ExpressRoute, Virtual WAN hub-and-spoke and BGP"),
    ("It closed 522 stores and opened 39 in the year.", "we closed 522 stores and opened 39 new stores"),
    ("Revenue was $26,869 million.", "Sales and other revenues 26,869"),
    ("The FY2025 10-K says the lubricants business will be separated in Q2.", "the lubricants business will be separated"),
    ("A role is listed.", TITLE),
    ("The network runs SD-WAN at 5 refineries.", "our SD WAN connects 5 refineries"),
    ("Azure is the primary cloud.", "Microsoft Azure is our primary cloud platform"),
    ("Overseas revenue was 96.62% of the total.", "overseas revenue accounted for 96.62%"),
], ids=["names", "figures", "thousands", "labels-and-years", "plain", "hyphen", "sentence-start", "percent"])
def test_a_fact_whose_figures_and_names_are_in_its_quote_is_supported(fact, quote):
    assert quotes.missing_from_quote(fact, quote) == ()


def test_what_names_the_source_does_not_have_to_be_quoted():
    """The company and the page are known from where the fact came from, not from the passage."""
    fact = "HF Sinclair's Network Engineer posting in Dallas asks for ExpressRoute."
    quote = "hybrid connectivity using ExpressRoute"
    assert quotes.missing_from_quote(fact, quote) == ("HF", "Sinclair", "Dallas")
    context = ("HF Sinclair", "https://careers.hfsinclair.com/job/Dallas-Network-Engineer-TX-75219/1387485900")
    assert quotes.missing_from_quote(fact, quote, context) == ()


@pytest.mark.parametrize("fact, quote", [
    ("It completed the acquisition of Andlauer Healthcare Group on November 3, 2025.", "it has completed the acquisition of Andlauer Healthcare Group Inc."),
    ("The role was posted Oct 30 2024 and covers VPC networking.", "Strong understanding of VPC networking"),
    ("The sale of Worldpac closed 2024-11-04.", "announced the close of the sale of Worldpac, Inc."),
    ("Income fell in the sixteen weeks ended April 25, 2026.", "income recognized in the sixteen weeks ended"),
    ("The plan was approved on 13 November 2024.", "the Board approved the plan"),
    ("Posted October 30th 2024 for VPC networking.", "VPC networking, and IAM"),
], ids=["month-day-year", "abbreviated", "iso", "week-ended", "day-first", "ordinal"])
def test_a_date_in_a_fact_is_not_a_figure_the_quote_must_hold(fact, quote):
    """The date belongs to the source. The figures a quote must hold are quantities."""
    assert quotes.missing_from_quote(fact, quote) == ()


def test_a_quantity_beside_a_date_is_still_checked():
    fact = "On November 3, 2025 it paid $1.6 billion for 31 sites."
    assert quotes.missing_from_quote(fact, "it paid $1.6 billion for the business") == ("31",)
