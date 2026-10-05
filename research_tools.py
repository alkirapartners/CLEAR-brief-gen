"""The tools the research model may call, run against Tavily under a budget.

The model decides what to search for and which pages to open. This module
decides whether it may: it counts every search and page read, refuses calls
past the budget, remembers which pages were opened, and wraps everything
that comes back from the web in a random fence.
"""

import concurrent.futures as futures
import logging
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit

from evidence import (
    CATEGORIES, EvidenceItem, Page, canonical_url, is_fetchable_url, mark_opened, one_line,
    safe_url,
)

logger = logging.getLogger(__name__)

# The research budget for one brief.
MAX_SEARCHES = 25
MAX_PAGES = 20

RESULTS_PER_SEARCH = 5
SUMMARY_CHARS = 300
# What one read returns. An annual report can run to 850,000 characters, so
# a long page comes back as its first part, or as the passages around the
# words the model asks to find.
MAX_PAGE_CHARS = 12_000
PASSAGE_BEFORE_CHARS = 400
PASSAGE_AFTER_CHARS = 1_100
MAX_PASSAGES = 40
PASSAGE_BREAK = "\n[...]\n"
# Less text than this is a cookie wall or an empty shell, not a page.
MIN_PAGE_CHARS = 200
MAX_QUERY_CHARS = 400
MAX_FACT_CHARS = 500
MAX_TITLE_CHARS = 160
MAX_DATE_CHARS = 20
MAX_SOURCE_URL_CHARS = 500
MAX_EVIDENCE_ITEMS = 150
MAX_PARALLEL_CALLS = 6
TAVILY_TIMEOUT_SECONDS = 30
SEARCH_DEPTH = "advanced"
# "advanced" renders JavaScript pages (Workday careers sites) and reads PDFs.
EXTRACT_DEPTH = "advanced"

SEARCH = "web_search"
READ = "read_page"
RECORD = "record_evidence"

TIME_UP = "The research time is used up. Record any evidence you have not recorded yet, then stop."
SEARCHES_SPENT = "The search budget is spent. Open pages you already found, or record your evidence and stop."
PAGES_SPENT = "The page budget is spent. Record your evidence and stop."
NOT_PUBLIC = "That is not a public web address, so it was not opened."
NO_QUERY = "Give a search query."
LEADS_ONLY = (
    "These are search summaries. They are leads, never evidence: open a page "
    "with read_page before you record a fact from it."
)


def _tool(name: str, description: str, properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        },
    }


_EVIDENCE_ITEM = {
    "type": "object",
    "properties": {
        "fact": {"type": "string", "description": "One specific fact, in the page's own terms."},
        "category": {"type": "string", "enum": list(CATEGORIES)},
        "source_url": {"type": "string", "description": "The exact URL you opened."},
        "source_title": {"type": "string", "description": "A short name for the page."},
        "source_date": {
            "type": "string",
            "description": "The date the page gives for itself, YYYY-MM-DD or YYYY-MM. Empty if none.",
        },
    },
    "required": ["fact", "category", "source_url", "source_title", "source_date"],
    "additionalProperties": False,
}

# Sent with every research request and cached with the system prefix, so it
# must never vary between calls.
TOOLS: tuple[dict[str, Any], ...] = (
    _tool(SEARCH, "Search the web. Returns titles, URLs and short summaries. Summaries are leads, not evidence.", {
        "query": {"type": "string"},
        "site": {
            "type": "string",
            "description": "Limit results to one domain, such as sec.gov or a careers site. Empty for the whole web.",
        },
        "recent_news": {"type": "boolean", "description": "True for news from the past year only."},
    }),
    _tool(READ, "Open one page or PDF and return its text. Only an opened page can be cited.", {
        "url": {"type": "string"},
        "find": {
            "type": "string",
            "description": (
                "Words or phrases to look for, separated by commas. For a long document the "
                "passages around them are returned instead of its first part. Empty for the start."
            ),
        },
    }),
    _tool(RECORD, "Record facts you read on pages you opened. Call it straight after reading a page.", {
        "items": {"type": "array", "items": _EVIDENCE_ITEM},
    }),
)


class WebClient(Protocol):
    """The part of ``tavily.TavilyClient`` the tools use."""

    def search(self, query: str, **kwargs: Any) -> dict: ...

    def extract(self, urls: list[str], **kwargs: Any) -> dict: ...


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: Mapping[str, Any]


@dataclass(frozen=True)
class Ledger:
    """What the research has spent and gathered so far."""

    searches: int = 0
    page_reads: int = 0
    pages: tuple[Page, ...] = ()
    evidence: tuple[EvidenceItem, ...] = ()
    failures_in_a_row: int = 0
    # The full text of each opened page, by canonical URL, so reading another
    # part of a long document costs no second fetch and no budget.
    texts: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Outcome:
    call_id: str
    text: str
    is_error: bool = False
    page: Page | None = None
    page_text: str = ""
    evidence: tuple[EvidenceItem, ...] = ()
    # True when the web service itself failed, False when it answered, None otherwise.
    web_failed: bool | None = None


def budget_line(ledger: Ledger, accepting: bool = True) -> str:
    if not accepting:
        return TIME_UP
    searches = max(0, MAX_SEARCHES - ledger.searches)
    pages = max(0, MAX_PAGES - ledger.page_reads)
    return f"Budget left: {searches} searches, {pages} page reads."


def _fenced(body: str, fence: str) -> str:
    return f"<web-{fence}>\n{body}\n</web-{fence}>"


def _text_input(call: ToolCall, key: str) -> str:
    value = call.input.get(key)
    return value.strip() if isinstance(value, str) else ""


def _refusal(call: ToolCall, ledger: Ledger, accepting: bool) -> str | None:
    """Why a call may not run, or None when it may."""
    if call.name == RECORD:
        return None
    if call.name not in (SEARCH, READ):
        return f"There is no tool named {call.name}. Use {SEARCH}, {READ} or {RECORD}."
    if not accepting:
        return TIME_UP
    if call.name == SEARCH:
        if not _text_input(call, "query"):
            return NO_QUERY
        return SEARCHES_SPENT if ledger.searches >= MAX_SEARCHES else None
    url = _text_input(call, "url")
    if not is_fetchable_url(url):
        return NOT_PUBLIC
    if canonical_url(url) in ledger.texts:
        return None  # already opened: reading another part of it is free
    return PAGES_SPENT if ledger.page_reads >= MAX_PAGES else None


def _is_new_page(call: ToolCall, ledger: Ledger) -> bool:
    return canonical_url(_text_input(call, "url")) not in ledger.texts


def _admit(
    calls: Sequence[ToolCall], ledger: Ledger, accepting: bool,
) -> tuple[Ledger, list[str | None]]:
    """Charge the budget for each call that may run, in the order given."""
    refusals: list[str | None] = []
    for call in calls:
        refusal = _refusal(call, ledger, accepting)
        refusals.append(refusal)
        if refusal is None and call.name == SEARCH:
            ledger = replace(ledger, searches=ledger.searches + 1)
        if refusal is None and call.name == READ and _is_new_page(call, ledger):
            ledger = replace(ledger, page_reads=ledger.page_reads + 1)
    return ledger, refusals


def _site(raw: str) -> str:
    """A bare host from whatever the model gave: a domain, a URL, or nothing."""
    host = urlsplit(raw).hostname if "://" in raw else raw.split("/")[0]
    return (host or "").strip().lower()


def _hit_lines(number: int, hit: Mapping[str, Any]) -> str:
    lines = [f"{number}. {one_line(str(hit.get('title') or ''))}", f"   URL: {hit['url']}"]
    if hit.get("published_date"):
        lines.append(f"   Date: {one_line(str(hit['published_date']))}")
    lines.append(f"   Summary: {one_line(str(hit.get('content') or ''))[:SUMMARY_CHARS]}")
    return "\n".join(lines)


def _search(call: ToolCall, web: WebClient, fence: str) -> Outcome:
    options: dict[str, Any] = {
        "max_results": RESULTS_PER_SEARCH,
        "search_depth": SEARCH_DEPTH,
        "timeout": TAVILY_TIMEOUT_SECONDS,
    }
    site = _site(_text_input(call, "site"))
    if site:
        options["include_domains"] = [site]
    if call.input.get("recent_news") is True:
        options.update(topic="news", time_range="year")
    response = web.search(_text_input(call, "query")[:MAX_QUERY_CHARS], **options)
    found = [{**hit, "url": safe_url(str(hit.get("url") or ""))} for hit in response.get("results") or []]
    hits = [hit for hit in found if hit["url"] is not None]
    if not hits:
        return Outcome(call.id, "No results. Try other words, or drop the site filter.", web_failed=False)
    body = "\n".join(_hit_lines(number, hit) for number, hit in enumerate(hits, start=1))
    return Outcome(call.id, f"{_fenced(body, fence)}\n{LEADS_ONLY}", web_failed=False)


Span = tuple[int, int]


def _term_spans(lowered: str, term: str) -> list[Span]:
    """Where one wanted word appears, as passages that do not overlap each other."""
    spans: list[Span] = []
    at = lowered.find(term)
    while at != -1 and len(spans) < MAX_PASSAGES:
        if not spans or at >= spans[-1][1]:
            spans.append((max(0, at - PASSAGE_BEFORE_CHARS), min(len(lowered), at + PASSAGE_AFTER_CHARS)))
        at = lowered.find(term, at + len(term))
    return spans


def _overlaps(span: Span, others: list[Span]) -> bool:
    return any(span[0] < other[1] and other[0] < span[1] for other in others)


def _passages(content: str, find: str) -> tuple[str, int, int]:
    """The text around the wanted words, with how many passages are shown and exist.

    Every word gets its first passage before any word gets a second, so a
    common word cannot crowd out a rare one.
    """
    terms = [part.strip().lower() for part in find.split(",") if part.strip()]
    per_term = [_term_spans(content.lower(), term) for term in terms]
    chosen: list[Span] = []
    distinct: list[Span] = []
    room = MAX_PAGE_CHARS
    for rank in range(max((len(spans) for spans in per_term), default=0)):
        for span in (spans[rank] for spans in per_term if rank < len(spans)):
            if _overlaps(span, distinct):
                continue
            distinct.append(span)
            size = span[1] - span[0] + len(PASSAGE_BREAK)
            if size <= room:
                chosen.append(span)
                room -= size
    text = PASSAGE_BREAK.join(content[start:end] for start, end in sorted(chosen))
    return text, len(chosen), len(distinct)


def _page_view(url: str, content: str, find: str) -> tuple[str, str]:
    """The part of a page to show, and the note that goes with it."""
    if find:
        found, shown, total = _passages(content, find)
        if not found:
            return "", f"None of those words appear on {url}. It is opened; try other words."
        cut = (
            f" Showing {shown} of {total} matching passages: ask for fewer or narrower words to see the rest."
            if shown < total else ""
        )
        return found, f"These are the passages of {url} around the words you asked for.{cut}"
    if len(content) > MAX_PAGE_CHARS:
        return content[:MAX_PAGE_CHARS], (
            f"{url} is opened. It is long ({len(content):,} characters) and this is its first part: "
            f"call {READ} on it again with `find` to read the passages you need. Re-reading it is free."
        )
    return content, f"{url} is opened. Record what it states with {RECORD}."


def _read(call: ToolCall, web: WebClient, fence: str, texts: Mapping[str, str]) -> Outcome:
    url, find = safe_url(_text_input(call, "url")) or "", _text_input(call, "find")
    known = texts.get(canonical_url(url))
    if known is None:
        response = web.extract(urls=[url], extract_depth=EXTRACT_DEPTH, timeout=TAVILY_TIMEOUT_SECONDS)
        results = response.get("results") or []
        content = str(results[0].get("raw_content") or "").strip() if results else ""
        if len(content) < MIN_PAGE_CHARS:
            return Outcome(
                call.id, f"{url} returned no readable text. It was not opened and cannot be cited.",
                is_error=True, web_failed=False,
            )
    else:
        content = known
    shown, note = _page_view(url, content, find)
    body = f"URL: {url}\n{shown}"
    text = f"{_fenced(body, fence)}\n{note}" if shown else note
    if known is not None:
        return Outcome(call.id, text)
    return Outcome(call.id, text, page=Page(url, len(content)), page_text=content, web_failed=False)


def _evidence_item(raw: Any) -> EvidenceItem | None:
    """One recorded fact, or None when the entry is not usable."""
    if not isinstance(raw, Mapping):
        return None
    fact, url = raw.get("fact"), raw.get("source_url")
    if not isinstance(fact, str) or not isinstance(url, str) or raw.get("category") not in CATEGORIES:
        return None
    if not fact.strip() or not url.strip():
        return None
    return EvidenceItem(
        fact=one_line(fact)[:MAX_FACT_CHARS],
        category=raw["category"],
        source_url=one_line(url)[:MAX_SOURCE_URL_CHARS],
        source_title=one_line(str(raw.get("source_title") or ""))[:MAX_TITLE_CHARS],
        source_date=one_line(str(raw.get("source_date") or ""))[:MAX_DATE_CHARS],
    )


def _record(call: ToolCall, opened_before: Sequence[Page]) -> Outcome:
    """Keep facts whose page was opened before this turn. Say which were not."""
    raw_items = call.input.get("items")
    parsed = [_evidence_item(raw) for raw in raw_items] if isinstance(raw_items, list) else []
    marked = mark_opened([item for item in parsed if item is not None], opened_before)
    unopened = sorted({item.source_url for item in marked if not item.opened})
    text = f"Recorded {sum(item.opened for item in marked)} fact(s)."
    if unopened:
        text += (
            f" Not kept: facts from pages you have not opened ({', '.join(unopened)})."
            f" Open a page with {READ} first, then record what it states."
        )
    return Outcome(call.id, text, evidence=marked)


def _execute(call: ToolCall, refusal: str | None, web: WebClient, fence: str, before: Ledger) -> Outcome:
    """Run one call against the ledger as it stood when the turn began."""
    if refusal is not None:
        return Outcome(call.id, refusal, is_error=True)
    if call.name == RECORD:
        return _record(call, before.pages)
    try:
        if call.name == SEARCH:
            return _search(call, web, fence)
        return _read(call, web, fence, before.texts)
    except Exception as exc:  # whatever the web service did, the model must get an answer
        logger.warning("%s failed: %s: %s", call.name, type(exc).__name__, exc)
        return Outcome(
            call.id, f"{call.name} failed ({type(exc).__name__}). Try a different query or page.",
            is_error=True, web_failed=True,
        )


def _settle(ledger: Ledger, outcomes: Sequence[Outcome]) -> Ledger:
    """The ledger after a turn: new pages, new evidence, and the failure streak."""
    streak = ledger.failures_in_a_row
    for outcome in outcomes:
        if outcome.web_failed is not None:
            streak = streak + 1 if outcome.web_failed else 0
    opened = [o for o in outcomes if o.page is not None]
    pages = ledger.pages + tuple(o.page for o in opened)
    texts = {**ledger.texts, **{canonical_url(o.page.url): o.page_text for o in opened}}
    gathered = ledger.evidence + tuple(item for o in outcomes for item in o.evidence)
    return replace(
        ledger, pages=pages, texts=texts, evidence=gathered[:MAX_EVIDENCE_ITEMS],
        failures_in_a_row=streak,
    )


def _result_block(outcome: Outcome, footer: str) -> dict[str, Any]:
    block: dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": outcome.call_id,
        "content": f"{outcome.text}\n\n{footer}",
    }
    return {**block, "is_error": True} if outcome.is_error else block


def run_calls(
    calls: Sequence[ToolCall], ledger: Ledger, web: WebClient, fence: str, accepting: bool = True,
) -> tuple[list[dict[str, Any]], Ledger]:
    """Run one turn's tool calls and return their results with the new ledger.

    Calls past the budget are refused without reaching the web. The rest run
    side by side, each against the ledger as it stood when the turn began.
    ``accepting`` is False once the research time is used up: searches and
    page reads are refused, evidence is still recorded.
    """
    admitted, refusals = _admit(calls, ledger, accepting)

    def work(pair: tuple[ToolCall, str | None]) -> Outcome:
        return _execute(pair[0], pair[1], web, fence, ledger)

    with futures.ThreadPoolExecutor(max_workers=MAX_PARALLEL_CALLS) as pool:
        outcomes = list(pool.map(work, zip(calls, refusals)))
    settled = _settle(admitted, outcomes)
    footer = budget_line(settled, accepting)
    return [_result_block(outcome, footer) for outcome in outcomes], settled
