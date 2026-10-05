"""What research must have tried before it may stop.

The model decides what to search for. This module keeps count of what it
has aimed at and what it has found, and says what is still open: the
company's careers site and job postings, its latest annual filing, each
line of the technical snapshot, and a minimum amount of looking.

Trying counts. A company with no public filing, or no job postings, is
covered once the research has looked: the floor asks for the attempt, and
the brief says what was not found.
"""

import re
from typing import Any, Mapping, Sequence

from evidence import HOSTED_JOB_SITES, EvidenceItem, Page, canonical_url, is_on

# ── The floor ────────────────────────────────────────────────────
# Job or careers pages read, each with a fact recorded from it. With this
# many, the postings were reached.
MIN_CAREERS_PAGES = 2
# Searches run and pages opened before research may call itself done.
MIN_SEARCHES = 10
MIN_PAGES_OPENED = 8
# How many times a model that says it is done is sent back to open items.
MAX_NUDGES = 2

# ── What a call can be aimed at ──────────────────────────────────
CAREERS_SITE = "careers_site"
HOSTED_JOBS = "hosted_jobs"
FILING = "filing"
# ── What can be open ─────────────────────────────────────────────
CAREERS = "careers"
DEPTH = "depth"
# Snapshot lines that every company has. Plant networks are left out: many
# companies have no plants, and a search for them would be wasted.
SNAPSHOT_TOPICS: tuple[str, ...] = ("clouds", "cloud_connectivity", "wan", "firewalls", "data_centers")
# The evidence category that sources each snapshot line.
TOPIC_CATEGORIES: dict[str, str] = {
    "clouds": "cloud",
    "cloud_connectivity": "cloud_connectivity",
    "wan": "network",
    "firewalls": "security",
    "data_centers": "data_center",
    "plant_networks": "plant_network",
}

_CAREERS_HOST = re.compile(r"^(?:www\.)?(?:careers?|jobs?|talent|recruiting|apply)\.", re.IGNORECASE)
_CAREERS_PATH = re.compile(r"/(?:careers?|jobs?|job-search|vacanc|openings|join-us|work-with-us)", re.IGNORECASE)
_JOB_QUERY = re.compile(
    r"\b(?:careers?|jobs?|job posting|postings?|hiring|openings?|vacanc\w+|recruit\w*)\b", re.IGNORECASE,
)
_HOSTED_QUERY = re.compile(
    r"workday|greenhouse|lever\.co|icims|smartrecruiters|jobvite|taleo|successfactors|ashby", re.IGNORECASE,
)
_FILING_QUERY = re.compile(
    r"\b(?:10-?K|20-?F|40-?F|annual report|annual filing|form 10|proxy statement|integrated report)\b",
    re.IGNORECASE,
)
_FILING_URL = re.compile(r"sec\.gov|10-?k|20-?f|annual[-_]?report|annualreport", re.IGNORECASE)
_TOPIC_QUERIES: dict[str, re.Pattern[str]] = {
    "clouds": re.compile(r"\b(?:AWS|Amazon Web Services|Azure|Google Cloud|GCP|Oracle Cloud|OCI|cloud)\b", re.IGNORECASE),
    "cloud_connectivity": re.compile(
        r"ExpressRoute|Direct Connect|Transit Gateway|Virtual WAN|Interconnect|hub-and-spoke"
        r"|\bVPC\b|\bVNet\b|cloud (?:network\w*|connectivity)|multi-?cloud", re.IGNORECASE,
    ),
    "wan": re.compile(r"\b(?:SD-?WAN|MPLS|WAN|SASE|backbone)\b", re.IGNORECASE),
    "firewalls": re.compile(
        r"firewalls?|Palo Alto|Fortinet|Check Point|Zscaler|zero trust|network security", re.IGNORECASE,
    ),
    "data_centers": re.compile(r"data[- ]?cent(?:er|re)s?|colocation|\bcolo\b|Equinix", re.IGNORECASE),
    "plant_networks": re.compile(
        r"\b(?:OT|SCADA|ICS|PLC)\b|industrial control|operational technology|plant network", re.IGNORECASE,
    ),
}

# The short name of each open item, for the line under every tool result.
_NAMES: dict[str, str] = {
    CAREERS: "careers site and job postings",
    FILING: "latest annual filing",
    "clouds": "clouds",
    "cloud_connectivity": "cloud connectivity",
    "wan": "WAN",
    "firewalls": "firewalls",
    "data_centers": "data centers",
    DEPTH: "more searches and pages",
}
# What to do about each open item, for a model that tried to stop.
_HOW: dict[str, str] = {
    CAREERS: (
        "Careers site and job postings: open the company's careers pages and its network, cloud and "
        "security postings. Many companies host postings elsewhere: search with `site` set to "
        "myworkdayjobs.com, greenhouse.io, lever.co or icims.com."
    ),
    FILING: (
        "Latest annual filing: find the newest 10-K or annual report (search with `site` set to "
        "sec.gov, or the investor pages), open it, and use `find` for acquisitions, divestitures, "
        "data centers, network and technology."
    ),
    "clouds": "Clouds: which cloud providers the company runs on. Search for it.",
    "cloud_connectivity": (
        "Cloud connectivity: ExpressRoute, Direct Connect, Transit Gateway, Virtual WAN or an "
        "interconnect. Job postings name them. Search for it."
    ),
    "wan": "WAN: SD-WAN, MPLS, the backbone, and who supplies it. Search for it.",
    "firewalls": "Firewalls: the vendors, and where the firewalls sit. Search for it.",
    "data_centers": "Data centers: how many, where, owned or colocated, any exit planned. Search for it.",
}
ALL_COVERED = "The research checklist is covered."


def _text(call_input: Mapping[str, Any], key: str) -> str:
    value = call_input.get(key)
    return value if isinstance(value, str) else ""


def _is_careers_address(url: str) -> bool:
    host, _, path = url.partition("://")[2].partition("/")
    return bool(_CAREERS_HOST.match(host) or _CAREERS_PATH.search("/" + path))


def _search_aims(query: str, site: str) -> set[str]:
    aims = {topic for topic, pattern in _TOPIC_QUERIES.items() if pattern.search(query)}
    if _JOB_QUERY.search(query) or _CAREERS_HOST.match(site):
        aims.add(CAREERS_SITE)
    if _HOSTED_QUERY.search(f"{query} {site}") or is_on(f"https://{site}", HOSTED_JOB_SITES):
        aims.add(HOSTED_JOBS)
    if _FILING_QUERY.search(query) or "sec.gov" in site.lower():
        aims.add(FILING)
    return aims


def _read_aims(url: str) -> set[str]:
    aims: set[str] = set()
    if is_on(url, HOSTED_JOB_SITES):
        aims.add(HOSTED_JOBS)
    elif _is_careers_address(url):
        aims.add(CAREERS_SITE)
    if _FILING_URL.search(url):
        aims.add(FILING)
    return aims


def attempted(call_name: str, call_input: Mapping[str, Any]) -> frozenset[str]:
    """What a search or a page read was aimed at, of the things the floor asks for."""
    if call_name == "web_search":
        return frozenset(_search_aims(_text(call_input, "query"), _text(call_input, "site").strip()))
    if call_name == "read_page":
        return frozenset(_read_aims(_text(call_input, "url").strip()))
    return frozenset()


def _careers_pages(pages: Sequence[Page], evidence: Sequence[EvidenceItem]) -> int:
    """Job and careers pages that were read: opened, and a fact recorded from them.

    A posting that comes back as a title and a cookie notice yields no fact,
    so it does not count as reached.
    """
    gave_facts = {canonical_url(item.source_url) for item in evidence}
    return sum(
        1 for page in pages
        if canonical_url(page.url) in gave_facts
        and (is_on(page.url, HOSTED_JOB_SITES) or _is_careers_address(page.url))
    )


def open_items(
    attempts: frozenset[str], pages: Sequence[Page], evidence: Sequence[EvidenceItem], searches: int,
) -> tuple[str, ...]:
    """What the floor still asks for, in the order to work on it."""
    still: list[str] = []
    tried_both = CAREERS_SITE in attempts and HOSTED_JOBS in attempts
    if _careers_pages(pages, evidence) < MIN_CAREERS_PAGES and not tried_both:
        still.append(CAREERS)
    if FILING not in attempts:
        still.append(FILING)
    sourced = {item.category for item in evidence}
    still += [
        topic for topic in SNAPSHOT_TOPICS
        if topic not in attempts and TOPIC_CATEGORIES[topic] not in sourced
    ]
    if searches < MIN_SEARCHES or len(pages) < MIN_PAGES_OPENED:
        still.append(DEPTH)
    return tuple(still)


def names(still_open: Sequence[str]) -> tuple[str, ...]:
    """Each open item by its short name."""
    return tuple(_NAMES[item] for item in still_open)


def summary(still_open: Sequence[str]) -> str:
    """One line for the end of a tool result."""
    if not still_open:
        return ALL_COVERED
    return f"Not covered yet: {'; '.join(names(still_open))}."


def instructions(still_open: Sequence[str], searches: int, pages_opened: int) -> str:
    """What to do about each open item, one per line."""
    depth = (
        f"More ground: {searches} searches and {pages_opened} pages so far. Follow your best leads "
        f"to at least {MIN_SEARCHES} searches and {MIN_PAGES_OPENED} opened pages."
    )
    return "\n".join(f"- {depth if item == DEPTH else _HOW[item]}" for item in still_open)
