"""
Tavily research layer for the Alkira brief generator.

Runs the brief template's research checklist as parallel Tavily searches,
ranks the results, and extracts the highest-signal pages. No model in the loop.
"""

import concurrent.futures as futures
import logging
from typing import Callable, NamedTuple, TypedDict

from tavily import TavilyClient

logger = logging.getLogger(__name__)

MAX_PAGE_CHARS = 8000
EXTRACT_LIMIT = 5
SEARCH_RESULTS_PER_QUERY = 4
DEPRIORITISED_DOMAINS = ("linkedin.com", "facebook.com", "twitter.com", "x.com")


class Source(TypedDict):
    n: int
    title: str
    url: str
    content: str


class ResearchResult(NamedTuple):
    sources: list[Source]
    payload: str


class ResearchError(RuntimeError):
    """Raised when research fails. Never generate an uncited brief."""


def build_queries(company: str) -> list[dict]:
    """One query per research-checklist category in the brief template."""
    return [
        {"query": f"{company} headquarters revenue employees industry"},
        {"query": f"{company} global offices facilities international markets"},
        {"query": f"{company} CIO CTO chief information officer technology leadership"},
        {"query": f"{company} AWS Azure Google Cloud migration"},
        {"query": f"{company} VMware Nutanix data center on-premises infrastructure"},
        {"query": f"{company} network MPLS SD-WAN firewall zero trust"},
        {
            "query": f"{company} acquisition expansion restructuring leadership change",
            "topic": "news",
            "time_range": "year",
        },
    ]


def _is_deprioritised(url: str) -> bool:
    return any(d in url.lower() for d in DEPRIORITISED_DOMAINS)


def rank_results(raw_results: list[dict], limit: int = EXTRACT_LIMIT) -> list[dict]:
    """Dedupe by URL, sort by Tavily score, push social domains to the back."""
    seen: set[str] = set()
    unique: list[dict] = []
    for item in raw_results:
        url = item.get("url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        unique.append(item)

    unique.sort(
        key=lambda r: (_is_deprioritised(r.get("url", "")), -float(r.get("score", 0.0)))
    )
    return unique[:limit]


def truncate(text: str, cap: int = MAX_PAGE_CHARS) -> str:
    """Cap page content. Uncapped extract measured ~50K tokens for 5 pages."""
    return text if len(text) <= cap else text[:cap]


def format_payload(sources: list[Source]) -> str:
    """Numbered, model-ready source block. Numbers become the brief's citations."""
    blocks = [
        f"[{s['n']}] {s['title']}\nURL: {s['url']}\n{s['content']}"
        for s in sources
    ]
    return "\n\n---\n\n".join(blocks)


def research(
    company: str,
    status_callback: Callable[[str], None],
    api_key: str,
) -> ResearchResult:
    """Search in parallel, extract the top pages, return numbered sources."""
    if not api_key:
        raise ResearchError("TAVILY_API_KEY is not configured.")

    client = TavilyClient(api_key=api_key)
    queries = build_queries(company)

    status_callback("research")
    try:
        with futures.ThreadPoolExecutor(max_workers=len(queries)) as pool:
            responses = list(
                pool.map(
                    lambda q: client.search(
                        max_results=SEARCH_RESULTS_PER_QUERY,
                        search_depth="advanced",
                        **q,
                    ),
                    queries,
                )
            )
    except Exception as exc:
        raise ResearchError(f"Tavily search failed: {exc}") from exc

    hits: list[dict] = []
    for response in responses:
        hits.extend(response.get("results", []))

    if not hits:
        raise ResearchError(f"No search results found for '{company}'.")

    ranked = rank_results(hits)

    status_callback("analyze")
    extracted: dict[str, str] = {}
    try:
        response = client.extract(urls=[r["url"] for r in ranked])
        for item in response.get("results", []):
            extracted[item.get("url", "")] = item.get("raw_content", "") or ""
    except Exception as exc:
        logger.warning("Tavily extract failed, falling back to snippets: %s", exc)

    sources: list[Source] = []
    for i, item in enumerate(ranked, start=1):
        url = item.get("url", "")
        body = extracted.get(url) or item.get("content", "")
        sources.append(
            {
                "n": i,
                "title": item.get("title", "") or url,
                "url": url,
                "content": truncate(body),
            }
        )

    return ResearchResult(sources=sources, payload=format_payload(sources))
