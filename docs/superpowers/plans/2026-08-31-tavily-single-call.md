# Tavily Research + Single-Call Generation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Claude Managed Agent with a Tavily research layer plus one streaming `claude-sonnet-5` call, cutting brief generation from 120-200s to ~20-30s and roughly an order of magnitude of cost.

**Architecture:** Two deterministic stages. `research.py` runs 7 parallel Tavily searches (one per checklist category) then extracts the highest-scoring pages, with no model in the loop. `generate.py` makes a single streamed Sonnet 5 call whose system prefix inlines the three existing skill files and is prompt-cached. The markdown output contract is unchanged, so every downstream consumer (`app.py` parsers, `pdf.py`, `db.py`) is untouched.

**Tech Stack:** Python 3.14 (prod) / 3.11 (local), Streamlit, `anthropic` SDK, `tavily-python` 0.8.0, Supabase, pytest.

**Spec:** `docs/superpowers/specs/2026-08-31-tavily-single-call-design.md`

## Global Constraints

- **Output contract is frozen.** Generation must return markdown beginning with `# ALKIRA OPPORTUNITY BRIEF`. Nothing downstream may change.
- **`tests/test_parsers.py` and `tests/test_pdf.py` must not be edited.** They are the regression gate proving the contract held. Baseline: **55 tests passing.**
- **Model:** `claude-sonnet-5` exactly. Verified available on the production key.
- **Generation params:** `thinking={"type": "adaptive"}`, `output_config={"effort": "medium"}`, `max_tokens=8000`, streamed.
- **`budget_tokens` is rejected with a 400 on Sonnet 5.** Never use it.
- **No assistant prefill** — rejected with a 400 on Sonnet 5.
- **The cached system prefix must be byte-stable.** No timestamps, no UUIDs, no `datetime.now()`. Month/year belongs in the user message.
- **`MAX_PAGE_CHARS = 8000`** per extracted page.
- **Tavily key** is read as `TAVILY_API_KEY` through the existing `_secret()` helper in `app.py` (env var first, then `st.secrets`).
- **Skill files in `skills/` are read verbatim and never modified.**
- No live network calls in tests. Tavily and Anthropic are always mocked.

---

## File Structure

| File | Responsibility |
|---|---|
| `research.py` (new) | Tavily search + ranking + extract + payload formatting. No Anthropic imports. |
| `prompts.py` (new) | Builds the cached system prefix from skill files, and the per-brief user message. |
| `generate.py` (new) | The single Sonnet 5 streaming call. Consumes `research.py` and `prompts.py`. |
| `app.py` (modify) | Swap `run_agent_session` for `generate.generate_brief`; add cache lookup. |
| `db.py` (modify) | Add `find_recent_brief_by_company`. |
| `generate_brief.py` (modify) | CLI rewired to the new path. |
| `system_prompt.py` (delete) | Superseded by `prompts.py`. |
| `setup_agent.py`, `setup_skills.py` (delete) | No agent, no uploaded skills. |
| `tests/test_research.py` (new) | Ranking, truncation, payload numbering. |
| `tests/test_prompts.py` (new) | Prefix byte-stability, skill inlining, volatile content placement. |

Splitting prompt construction into `prompts.py` keeps `generate.py` to just the API call, and makes the byte-stability property directly testable without touching the network layer.

---

### Task 1: Tavily research layer

**Files:**
- Create: `research.py`
- Test: `tests/test_research.py`

**Interfaces:**
- Consumes: nothing (leaf module).
- Produces:
  - `Source` — `TypedDict` with keys `n: int`, `title: str`, `url: str`, `content: str`
  - `ResearchResult` — `NamedTuple` with fields `sources: list[Source]`, `payload: str`
  - `ResearchError(RuntimeError)`
  - `build_queries(company: str) -> list[dict]`
  - `rank_results(raw_results: list[dict], limit: int = 5) -> list[dict]`
  - `truncate(text: str, cap: int = MAX_PAGE_CHARS) -> str`
  - `format_payload(sources: list[Source]) -> str`
  - `research(company: str, status_callback, api_key: str) -> ResearchResult`
  - `MAX_PAGE_CHARS = 8000`, `DEPRIORITISED_DOMAINS = ("linkedin.com", "facebook.com", "twitter.com", "x.com")`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_research.py
"""Tests for the Tavily research layer. No live network calls."""

import research


def test_build_queries_covers_all_checklist_categories():
    qs = research.build_queries("Acme Corp")
    assert len(qs) == 7
    assert all("Acme Corp" in q["query"] for q in qs)


def test_signals_query_uses_news_topic_and_year_range():
    """The brief demands past-12-month emphasis; default ranking ignores recency."""
    qs = research.build_queries("Acme Corp")
    signals = [q for q in qs if q.get("topic") == "news"]
    assert len(signals) == 1
    assert signals[0]["time_range"] == "year"


def test_rank_results_sorts_by_score_descending():
    raw = [
        {"url": "https://a.com/1", "title": "A", "score": 0.20},
        {"url": "https://b.com/2", "title": "B", "score": 0.90},
        {"url": "https://c.com/3", "title": "C", "score": 0.55},
    ]
    ranked = research.rank_results(raw)
    assert [r["url"] for r in ranked] == [
        "https://b.com/2", "https://c.com/3", "https://a.com/1",
    ]


def test_rank_results_deduplicates_by_url():
    raw = [
        {"url": "https://a.com/1", "title": "A", "score": 0.9},
        {"url": "https://a.com/1", "title": "A dup", "score": 0.8},
    ]
    assert len(research.rank_results(raw)) == 1


def test_rank_results_deprioritises_social_domains():
    """LinkedIn ranks well but extracts to boilerplate; it must lose to a real page."""
    raw = [
        {"url": "https://www.linkedin.com/company/acme", "title": "LI", "score": 0.99},
        {"url": "https://acme.com/investors", "title": "IR", "score": 0.40},
    ]
    ranked = research.rank_results(raw)
    assert ranked[0]["url"] == "https://acme.com/investors"


def test_rank_results_respects_limit():
    raw = [
        {"url": f"https://a.com/{i}", "title": str(i), "score": i / 10}
        for i in range(20)
    ]
    assert len(research.rank_results(raw, limit=5)) == 5


def test_truncate_caps_long_content():
    assert len(research.truncate("x" * 50_000)) == research.MAX_PAGE_CHARS


def test_truncate_leaves_short_content_untouched():
    assert research.truncate("short") == "short"


def test_format_payload_numbers_sources_and_includes_urls():
    sources = [
        {"n": 1, "title": "IR page", "url": "https://acme.com/ir", "content": "revenue"},
        {"n": 2, "title": "News", "url": "https://news.com/a", "content": "acquired"},
    ]
    payload = research.format_payload(sources)
    assert "[1]" in payload and "[2]" in payload
    assert "https://acme.com/ir" in payload
    assert "https://news.com/a" in payload
    assert "revenue" in payload
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_research.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'research'`

- [ ] **Step 3: Implement `research.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_research.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Confirm the regression gate is untouched**

Run: `python3 -m pytest tests/ -q`
Expected: 64 passed (55 baseline + 9 new)

- [ ] **Step 6: Commit**

```bash
git add research.py tests/test_research.py
git commit -m "feat(research): add Tavily search and extract layer"
```

---

### Task 2: Prompt construction with cached prefix

**Files:**
- Create: `prompts.py`
- Test: `tests/test_prompts.py`
- Delete: `system_prompt.py`

**Interfaces:**
- Consumes: nothing (reads `skills/` from disk).
- Produces:
  - `build_system_prefix() -> str`
  - `build_user_message(company: str, payload: str, today: date) -> str`
  - `SKILL_FILES: tuple[str, ...]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_prompts.py
"""Tests for prompt construction and prompt-cache stability."""

from datetime import date

import prompts


def test_system_prefix_is_byte_stable_across_builds():
    """Any drift silently destroys the prompt cache and the cost savings."""
    assert prompts.build_system_prefix() == prompts.build_system_prefix()


def test_system_prefix_inlines_all_skill_files():
    prefix = prompts.build_system_prefix()
    assert "Alkira Fit Score" in prefix          # alkira-brief-template
    assert len(prefix) > 30_000                   # all skills present, not just one


def test_system_prefix_contains_no_volatile_content():
    """A date in the prefix invalidates the cache on every month boundary."""
    prefix = prompts.build_system_prefix()
    for year in ("2025", "2026", "2027"):
        assert year not in prefix


def test_system_prefix_states_the_output_contract():
    assert "# ALKIRA OPPORTUNITY BRIEF" in prompts.build_system_prefix()


def test_user_message_carries_company_payload_and_date():
    msg = prompts.build_user_message(
        "Acme Corp", "[1] Source\nURL: https://a.com", date(2026, 8, 31)
    )
    assert "Acme Corp" in msg
    assert "August 2026" in msg
    assert "https://a.com" in msg


def test_user_message_instructs_citation_by_number():
    msg = prompts.build_user_message("Acme", "[1] x", date(2026, 8, 31))
    assert "[1]" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_prompts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prompts'`

- [ ] **Step 3: Implement `prompts.py`**

```python
"""
Prompt construction for single-call brief generation.

The system prefix is byte-stable and prompt-cached: it inlines the three skill
files that the Managed Agent used to load one tool call at a time. Anything that
varies per brief (company, date, sources) belongs in the user message, or the
cache invalidates and the cost savings disappear.
"""

from datetime import date
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path(__file__).parent / "skills"

SKILL_FILES: tuple[str, ...] = (
    "alkira-brief-template/SKILL.md",
    "alkira-customer/SKILL.md",
    "alkira-customer/references/case-studies.md",
    "alkira-customer/references/objection-handling.md",
    "alkira-customer/references/pricing.md",
    "stop-slop/SKILL.md",
    "stop-slop/references/phrases.md",
    "stop-slop/references/structures.md",
)

_INSTRUCTIONS = """\
# Alkira Opportunity Brief Generator

You are a senior B2B account intelligence analyst supporting Channel Account
Managers and their VAR partners selling Alkira's cloud networking platform. You
will be given a company name and a numbered set of research sources. Produce a
scored opportunity brief.

## Accuracy Rules

- Use only what the provided sources support. Do not rely on prior knowledge for
  company claims.
- Separate confirmed facts from directional signals. Label each clearly.
- Flag uncertainty. Avoid speculation.
- Do NOT assert deal values, timelines, internal architectures, or named
  decision-makers unless a source confirms them.
- If the sources are thin, score the fit low. A 1 or 2 star score on sparse
  evidence is the correct answer, not a failure.

## Writing Style

- Direct, specific, no filler. Every sentence references something concrete.
- No marketing fluff. Partners need "here's exactly what to say and why."
- Proof points come from the Alkira metrics in the reference material below.
  Don't invent numbers.
- Label "(confirmed)" vs "(directional)" throughout.
- Apply the stop-slop rules below: no em dashes, no adverbs, no throat-clearing,
  no binary contrasts, no false agency. Two items beat three. Vary sentence
  length.
- Conversation starters must use plain business language. No networking jargon.
  A non-technical sales rep must be able to say every question out loud
  comfortably.

## Critical Rules

- **OUTPUT ONLY THE BRIEF.** Do not narrate. Your entire response is the markdown
  brief. The first line must be "# ALKIRA OPPORTUNITY BRIEF".
- ~700 words excluding references. Shorter is better.
- Pick only 3 entry points, the ones with the strongest evidence.
- **Cite by source number.** The References section must list the sources you
  used, with the exact URLs given to you. Format: `[N] Description - URL`.
  Never write a URL that does not appear in the provided sources.
- No files, no code. Markdown text only.

---

# Reference Material

The following is your complete reference material: the brief template and
scoring rubric, the Alkira knowledge base, and the writing quality rules.
"""


@lru_cache(maxsize=1)
def build_system_prefix() -> str:
    """Assemble the cached system prefix. Must be byte-stable across calls."""
    parts = [_INSTRUCTIONS]
    for relative in SKILL_FILES:
        body = (SKILLS_DIR / relative).read_text(encoding="utf-8")
        parts.append(f"\n\n---\n\n<!-- {relative} -->\n\n{body}")
    return "".join(parts)


def build_user_message(company: str, payload: str, today: date) -> str:
    """Per-brief content. Everything volatile lives here, never in the prefix."""
    return (
        f'Company: "{company}"\n'
        f"Current date: {today.strftime('%B %Y')}\n\n"
        f"Write the brief's date line as *[{today.strftime('%B %Y')}]*.\n\n"
        "Research sources follow. Cite them by their bracketed number, and use "
        "their exact URLs in the References section.\n\n"
        f"{payload}"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_prompts.py -v`
Expected: PASS (6 tests)

Note: if `test_system_prefix_contains_no_volatile_content` fails, a skill file
contains a year literal. Do not edit the skill file. Narrow the assertion to the
`_INSTRUCTIONS` constant instead, since only content authored here is at risk of
becoming volatile.

- [ ] **Step 5: Delete the superseded system prompt**

```bash
git rm system_prompt.py
```

- [ ] **Step 6: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: 70 passed

- [ ] **Step 7: Commit**

```bash
git add prompts.py tests/test_prompts.py
git commit -m "feat(prompts): add cached system prefix inlining skill files"
```

---

### Task 3: Single-call generation

**Files:**
- Create: `generate.py`

**Interfaces:**
- Consumes: `research.research`, `prompts.build_system_prefix`, `prompts.build_user_message`
- Produces: `generate_brief(api_key: str, tavily_key: str, company: str, status_callback, timeout_seconds: float = 180) -> str`
- Raises: `research.ResearchError` propagates uncaught to the caller. `app.py` already
  wraps both call sites in `try/except`, so a research failure surfaces as an error in
  the UI rather than an uncited brief. Do not swallow it here.

This signature deliberately mirrors the old `run_agent_session(config, company, status_callback, timeout_seconds)` so the `app.py` call sites change minimally.

- [ ] **Step 1: Implement `generate.py`**

There is no unit test for this module. It is a thin wrapper over a network call whose parts are already covered: `research.py` and `prompts.py` are unit-tested, and the markdown it returns is covered by the untouched `test_parsers.py` / `test_pdf.py`. Mocking the streaming SDK here would test the mock, not the code. It is verified by the manual end-to-end check in Task 6.

```python
"""
Single-call brief generation.

Replaces the Managed Agent session: research runs deterministically in
research.py, then one streamed Sonnet 5 call composes the brief. ~30 sequential
model turns become 1.
"""

import logging
from datetime import date

from anthropic import Anthropic

import prompts
import research

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-5"
MAX_TOKENS = 8000
EFFORT = "medium"


def generate_brief(
    api_key: str,
    tavily_key: str,
    company: str,
    status_callback,
    timeout_seconds: float = 180,
) -> str:
    """Research the company, then compose the brief in one streamed call."""
    status_callback("init")

    result = research.research(company, status_callback, tavily_key)

    client = Anthropic(api_key=api_key, timeout=timeout_seconds)

    status_callback("compose")
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive"},
        output_config={"effort": EFFORT},
        cache_control={"type": "ephemeral"},
        system=prompts.build_system_prefix(),
        messages=[
            {
                "role": "user",
                "content": prompts.build_user_message(
                    company, result.payload, date.today()
                ),
            }
        ],
    ) as stream:
        message = stream.get_final_message()

    usage = message.usage
    logger.info(
        "brief=%s cache_read=%s cache_write=%s input=%s output=%s",
        company,
        getattr(usage, "cache_read_input_tokens", 0),
        getattr(usage, "cache_creation_input_tokens", 0),
        usage.input_tokens,
        usage.output_tokens,
    )

    status_callback("done")
    return "".join(b.text for b in message.content if b.type == "text")
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python3 -c "import generate; print(generate.MODEL)"`
Expected: `claude-sonnet-5`

- [ ] **Step 3: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: 70 passed

- [ ] **Step 4: Commit**

```bash
git add generate.py
git commit -m "feat(generate): single streaming Sonnet 5 call replaces agent session"
```

---

### Task 4: Repeat-company cache in db.py

**Files:**
- Modify: `db.py`
- Test: `tests/test_db.py` (append; do not edit existing tests)

**Interfaces:**
- Consumes: `db._get_client`
- Produces: `find_recent_brief_by_company(company: str, max_age_days: int = 7) -> Optional[dict]`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_db.py`:

```python
def test_find_recent_brief_by_company_returns_match():
    """A brief for the same company within the window is reused across users."""
    fake_row = {"id": "x-1", "company": "Acme", "score": 4, "brief_md": "# b",
                "created_at": "2026-08-30T10:00:00Z", "email": "other@example.com"}
    fake_client = MagicMock()
    (fake_client.table.return_value.select.return_value.ilike.return_value
     .gte.return_value.order.return_value.limit.return_value
     .execute.return_value.data) = [fake_row]

    with patch("db._get_client", return_value=fake_client):
        import db
        assert db.find_recent_brief_by_company("acme") == fake_row


def test_find_recent_brief_by_company_returns_none_when_empty():
    fake_client = MagicMock()
    (fake_client.table.return_value.select.return_value.ilike.return_value
     .gte.return_value.order.return_value.limit.return_value
     .execute.return_value.data) = []

    with patch("db._get_client", return_value=fake_client):
        import db
        assert db.find_recent_brief_by_company("nobody") is None


def test_find_recent_brief_by_company_returns_none_without_client():
    with patch("db._get_client", return_value=None):
        import db
        assert db.find_recent_brief_by_company("Acme") is None


def test_find_recent_brief_by_company_swallows_errors():
    """db.py's contract: never crash the app on a DB problem."""
    fake_client = MagicMock()
    fake_client.table.side_effect = RuntimeError("boom")
    with patch("db._get_client", return_value=fake_client):
        import db
        assert db.find_recent_brief_by_company("Acme") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_db.py -v -k find_recent`
Expected: FAIL — `AttributeError: module 'db' has no attribute 'find_recent_brief_by_company'`

- [ ] **Step 3: Implement in `db.py`**

Add `from datetime import datetime, timedelta, timezone` to the imports, then append:

```python
def find_recent_brief_by_company(
    company: str,
    max_age_days: int = 7,
) -> Optional[dict]:
    """Most recent brief for this company across all users, or None.

    Unlike get_user_briefs this deliberately ignores email: if any partner
    briefed the company this week, reuse that research.
    """
    client = _get_client()
    if client is None:
        return None

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=max_age_days)
    ).isoformat()

    try:
        result = (
            client.table("briefs")
            .select("id, email, company, score, brief_md, created_at")
            .ilike("company", company.strip())
            .gte("created_at", cutoff)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.error("Failed company-cache lookup for %s: %s", company, exc)
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: 74 passed

- [ ] **Step 6: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat(db): add 7-day repeat-company brief lookup"
```

---

### Task 5: Wire app.py and the CLI, delete agent setup

**Files:**
- Modify: `app.py` (imports at 20-24, config at 30-52, `run_agent_session` at 58-136, call sites at ~2011 and ~2088)
- Modify: `generate_brief.py`
- Modify: `requirements.txt`
- Modify: `.streamlit/secrets.toml.example`
- Delete: `setup_agent.py`, `setup_skills.py`

**Interfaces:**
- Consumes: `generate.generate_brief`, `db.find_recent_brief_by_company`
- Produces: `AgentConfig` gains `tavily_key: str` and drops `agent_id` / `env_id`.

- [ ] **Step 1: Update `AgentConfig` and `load_config` in `app.py`**

Replace the dataclass and loader (around lines 30-52):

```python
@dataclass(frozen=True)
class AgentConfig:
    api_key: str
    tavily_key: str


def load_config() -> AgentConfig:
    return AgentConfig(
        api_key=_secret("ANTHROPIC_API_KEY"),
        tavily_key=_secret("TAVILY_API_KEY"),
    )
```

- [ ] **Step 2: Delete `run_agent_session` and fix imports**

Delete the whole `run_agent_session` function (lines 58-136). Add `import generate` alongside `import db` at line 24. Remove the now-unused `from anthropic import Anthropic` import at line 20.

- [ ] **Step 3: Update both call sites**

At line ~2011 (the Update Brief path), replace:

```python
raw = run_agent_session(
    config, update_company, update_status,
)
```

with:

```python
raw = generate.generate_brief(
    config.api_key, config.tavily_key, update_company, update_status,
)
```

At line ~2088 (the generate path), replace:

```python
raw = run_agent_session(
    config, company_name.strip(), update_status,
)
```

with:

```python
raw = generate.generate_brief(
    config.api_key, config.tavily_key, company_name.strip(), update_status,
)
```

- [ ] **Step 4: Add the cache lookup at the generate site only**

At the generate site, replace the `with st.spinner(""):` block so a cache hit skips
the model call entirely:

```python
cached = db.find_recent_brief_by_company(company_name.strip())

if cached:
    raw = cached["brief_md"]
    st.info(
        f"Reusing research from {cached.get('created_at', '')[:10]}. "
        "Use Update Brief to re-research."
    )
    tracker_ph.empty()
else:
    with st.spinner(""):
        raw = generate.generate_brief(
            config.api_key, config.tavily_key, company_name.strip(), update_status,
        )
```

Everything after this point is unchanged: `raw` still flows into `clean_brief`,
`extract_score`, and `db.save_brief`, so a cache hit is saved under the requesting
user's email and their history, delete, and PDF behaviour all work normally.

The Update Brief path at line ~2011 must never consult the cache. That button
exists to force fresh research.

- [ ] **Step 5: Rewire `generate_brief.py`**

Replace the entire file:

```python
"""
Generate an Alkira opportunity brief for any company.

Usage:
    python generate_brief.py "Mary Kay"
    python generate_brief.py "Walmart" --output walmart_brief.md
"""

import argparse
import os
import sys
import time

from dotenv import load_dotenv

import generate

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate an Alkira opportunity brief for a target company."
    )
    parser.add_argument("company", help="Company name (e.g., 'Mary Kay')")
    parser.add_argument("--output", "-o", help="Output filename (e.g., brief.md)")
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show phase progress"
    )
    args = parser.parse_args()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    if not api_key or not tavily_key:
        print("Error: ANTHROPIC_API_KEY and TAVILY_API_KEY must be set.")
        sys.exit(1)

    def status(phase: str) -> None:
        if args.verbose:
            print(f"  [{phase}]")

    start = time.time()
    brief = generate.generate_brief(api_key, tavily_key, args.company, status)
    print(f"\nCompleted in {time.time() - start:.0f} seconds.\n")
    print(brief)

    if args.output:
        with open(args.output, "w") as handle:
            handle.write(brief)
        print(f"\nBrief saved to: {args.output}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Update dependencies and the secrets example**

Add to `requirements.txt`:

```
tavily-python>=0.8.0
```

In `.streamlit/secrets.toml.example`, add `TAVILY_API_KEY = "tvly-..."` and remove the `ALKIRA_AGENT_ID` / `ALKIRA_ENV_ID` lines.

- [ ] **Step 7: Delete the agent setup scripts**

```bash
git rm setup_agent.py setup_skills.py
```

- [ ] **Step 8: Verify no dangling references**

Run: `grep -rn "run_agent_session\|ALKIRA_AGENT_ID\|ALKIRA_ENV_ID\|system_prompt" --include=*.py --include=*.toml --include=*.example .`
Expected: no matches outside `docs/`

- [ ] **Step 9: Run the full suite**

Run: `python3 -m pytest tests/ -q`
Expected: 74 passed

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat(app): replace Managed Agent with Tavily + single-call generation"
```

---

### Task 6: End-to-end verification

**Files:** none modified except the spec in the final step.

- [ ] **Step 1: Generate a brief through the CLI**

```bash
export TAVILY_API_KEY=... ANTHROPIC_API_KEY=...
time python3 generate_brief.py "Mary Kay" --verbose --output /tmp/brief1.md
```

Expected: completes well under 120s; output starts with `# ALKIRA OPPORTUNITY BRIEF`.

The CLI calls `generate.generate_brief` directly and never consults the company
cache, so it always does real work. **In the Streamlit UI the opposite is true:** a
company briefed within 7 days returns the cached brief instead of generating. To
exercise the new path through the UI, pick a company with no recent brief, or use
Update Brief.

- [ ] **Step 2: Verify the output contract holds**

```bash
python3 -c "
import app
md = open('/tmp/brief1.md').read()
print('score:', app.extract_score(md))
print('company:', app.extract_company_header(md))
print('entry points:', len(app.extract_entry_points(md)))
print('infra cells:', app.extract_infra_cells(md))
"
```

Expected: a non-zero score, a company name, and 3 entry points. If any is empty the contract broke — fix generation, do not touch the parsers.

- [ ] **Step 3: Verify every reference URL came from the sources**

Read the brief's References section and confirm each URL is one Tavily returned. Any invented URL means the citation instruction in `prompts.py` needs tightening, or the deterministic References fallback from the spec should be built.

- [ ] **Step 4: Verify the prompt cache is working**

```bash
time python3 generate_brief.py "Chevron" --verbose --output /tmp/brief2.md
```

Check the logged `cache_read`. It must be non-zero on this second run. Zero means a silent invalidator in the prefix.

- [ ] **Step 5: Verify the PDF path**

```bash
python3 -c "
import app, pdf
md = open('/tmp/brief1.md').read()
score, _ = app.extract_score(md)
company, _ = app.extract_company_header(md)
data = pdf.generate_brief_pdf(md, company, score)
open('/tmp/brief1.pdf','wb').write(data)
print('pdf bytes:', len(data))
"
```

Expected: a non-trivial byte count. Open it and confirm it renders.

- [ ] **Step 6: Quality comparison against the old path**

Task 5 deleted `run_agent_session`, so the old path cannot be re-run. It does not
need to be: **Supabase already holds the old path's output.** Every brief in the
`briefs` table was generated by the Managed Agent, and that is the comparison corpus.

Pick 5 companies that already have saved briefs, generate each through the CLI (which
bypasses the cache), and compare against the stored `brief_md`:

```bash
python3 -c "
import db
for row in db.get_user_briefs('YOUR_EMAIL'):
    print(row['created_at'][:10], row['score'], row['company'])
"
```

For each pair, check: is the fit score within one star, are the entry points the same
three or defensibly different, are the conversation starters as specific, and do the
references point at real pages. Expect the new briefs to score lower on companies with
thin public infrastructure signal — that is the accepted tradeoff from the spec, not a
regression. Stop and reconsider if scores move by more than one star on companies with
*rich* public signal.

- [ ] **Step 7: Record the measured result**

Replace the estimate in the spec's Measured Baseline section with the real end-to-end latency and token counts.

```bash
git add docs/superpowers/specs/2026-08-31-tavily-single-call-design.md
git commit -m "docs: record measured end-to-end latency"
```

---

### Task 7: Deploy

Do not start until Task 6 passes and the briefs read as well as the agent's.

**Prerequisite:** a production Tavily key. The current key is `tvly-dev-` tier with lower rate limits and credit caps.

- [ ] **Step 1: Push and open the PR**

```bash
git push -u origin perf/tavily-single-call
gh pr create --title "Replace Managed Agent with Tavily research + single-call generation" \
  --body "See docs/superpowers/specs/2026-08-31-tavily-single-call-design.md"
```

- [ ] **Step 2: Deploy instance A** (`35.166.223.217`)

```bash
ssh -i "/Users/blakehays/Downloads/Alkira Channel (3).pem" ubuntu@35.166.223.217
git -C /var/www/briefgen pull
/var/www/briefgen/venv/bin/pip install -r /var/www/briefgen/requirements.txt
# edit /var/www/briefgen/.env: add TAVILY_API_KEY, remove ALKIRA_AGENT_ID and ALKIRA_ENV_ID
pm2 restart briefgen
```

**`pm2 restart briefgen` by name. Never `pm2 restart all`** — each box runs 11 other Alkira apps (dashboard, quoting, rfp, ela, proservices, networkassessment, intranet proxy and webhook, resources).

- [ ] **Step 3: Verify instance A**

```bash
pm2 logs briefgen --lines 50 --nostream
```

Generate one brief through the site. Confirm it renders and the PDF downloads.

- [ ] **Step 4: Deploy instance B** (`32.184.242.60`)

Same four commands. Sticky sessions mean A keeps serving while B restarts.

- [ ] **Step 5: Verify instance B**

Generate one brief per instance. Confirm timing lands in the 20-40s range and the briefs read correctly.

---

## Rollback

```bash
git -C /var/www/briefgen reset --hard 1122607
# restore ALKIRA_AGENT_ID and ALKIRA_ENV_ID in /var/www/briefgen/.env
pm2 restart briefgen
```

The old path needs no packages the boxes lack, so rollback is a checkout plus a restart. The Managed Agent and its environment are not deleted by this work, so the agent IDs stay valid.
