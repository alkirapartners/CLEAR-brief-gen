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
