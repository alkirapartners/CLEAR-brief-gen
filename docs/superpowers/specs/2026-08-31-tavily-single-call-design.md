# Design: Tavily Research + Single-Call Generation

**Date:** 2026-08-31
**Branch:** `perf/tavily-single-call`
**Goal:** Cut brief generation from 120-200s to ~20-30s and drop cost per brief by roughly an order of magnitude.

---

## Problem

`app.py:run_agent_session` generates each brief through a Claude Managed Agent
(`setup_agent.py`: `claude-sonnet-4-6`, `agent_toolset_20260401`, cloud sandbox with
unrestricted networking). Every brief pays for:

1. Per-session container provisioning before the first token.
2. A long sequential agent loop. `system_prompt.py` prescribes an 8-step workflow:
   load skill -> web search xN -> score -> load skill -> load skill -> compose ->
   quality gate. Each skill load is a file read inside the sandbox, so each one is a
   full model round-trip. Estimated 25-40 sequential turns.
3. Context that grows every turn. By the compose step the model is re-reading ~40KB
   of skill files plus every search result. This dominates cost, not the ~1,500
   output tokens.
4. Session teardown.

The task does not need an agent. `skills/alkira-brief-template/SKILL.md` defines a
fixed research checklist (8 named categories), a fixed 1-5 rubric, 3-of-5 known entry
points, and a rigid 9-section template with hard sentence limits. There is no
open-ended exploration for the model to perform. This is a workflow paying agent
prices and agent latency.

---

## Measured Baseline (Tavily probe, 2026-08-31)

Real numbers from a probe against "Mary Kay":

| Stage | Result |
|---|---|
| 7 parallel searches, `search_depth="advanced"` | **4.5s**, 27 unique URLs |
| Extract 5 pages | **0.3s**, 202,487 chars (~50K tokens) |
| **Total research** | **4.8s** |

Three findings drive the design:

- Research is ~5s wall-clock. The remaining time is one generation.
- Uncapped extract returns ~50K tokens from 5 pages, mostly boilerplate. A per-page
  character cap is required, not optional.
- Default search ranking surfaces weak sources (Wikipedia, LinkedIn, a state history
  handbook, a trade magazine). Source selection needs deliberate handling.

---

## Approach

Replace the Managed Agent with a deterministic two-stage pipeline:

1. **Research** (`research.py`, no model in the loop): parallel Tavily searches,
   then Tavily Extract on the highest-scoring pages.
2. **Generate**: one streaming `claude-sonnet-5` call with the three skills inlined
   into a cached system prefix.

Model turns per brief: **1**, down from ~30.

### Rejected alternatives

- **Two-stage condense (Haiku -> Sonnet).** Adds a sequential call and a failure mode
  to solve an input-budget problem that the per-page cap already solves. Held as an
  escape hatch if extract volume proves unmanageable.
- **Optimize the agent in place.** Swapping to Sonnet 5, inlining skills, and
  lowering effort would likely reach 60-90s, but still pays container provisioning
  per brief and keeps a nondeterministic loop. A discount on the wrong architecture.
- **Switching provider (Grok / GPT).** After research moves to Tavily the model writes
  ~1,500 tokens against a rigid template; provider choice moves that by seconds. The
  cost is rewriting the integration, re-tuning three skills, losing Anthropic-native
  prompt caching, and re-validating output format on a partner-facing document. Poor
  trade. Revisit only if Sonnet 5 fails the quality bar.

---

## Output Contract (unchanged)

The model returns the same markdown it does today, beginning with
`# ALKIRA OPPORTUNITY BRIEF`.

This is the central constraint of the design. It means **no downstream change**: the
~10 regex extractors in `app.py`, every `_draw_*` in `pdf.py`, `db.py`, the bento
renderer, and the PDF path are all untouched. No Supabase schema change.

Structured JSON output was considered and explicitly dropped as unnecessary
complication.

---

## Components

### `research.py` (new)

```
research(company: str, status_callback) -> ResearchResult
    sources: list[Source]   # n, title, url, content
    payload: str            # numbered, model-ready block
```

- **Search.** `ThreadPoolExecutor` over 7 queries, one per checklist category:
  company basics, global footprint, IT leadership, cloud platforms, on-prem/hybrid,
  network/security, organisational signals. Concurrent, so wall-clock is the slowest
  query, not the sum.
- **Recency.** The organisational-signals query uses `topic="news"` and
  `time_range="year"`. The template requires past-12-months emphasis and default
  ranking does not prioritise recency.
- **Ranking.** Dedupe by URL. Sort by Tavily's per-result `score`. Deprioritise
  `linkedin.com` and `facebook.com`, which rank well and extract to boilerplate.
  Take the top 5 for extraction.
- **Cap.** Truncate each extracted page to `MAX_PAGE_CHARS = 8000`. Measured
  uncapped volume was ~50K tokens for 5 pages; the cap brings that to ~10K tokens
  (~$0.02/brief) with no meaningful signal loss.
- **Client.** Sync `TavilyClient` in threads. Streamlit is sync; asyncio would add
  complication for no gain.

### `system_prompt.py` (rewritten)

Two parts, split on cache stability.

**Cached system prefix**, built once at process start:

- Accuracy rules, writing style, critical rules, output contract (retained).
- The 8-step workflow section (deleted: there are no skills to load and no searches
  to run).
- Verbatim contents of `skills/alkira-brief-template/SKILL.md`,
  `skills/alkira-customer/SKILL.md` + references, `skills/stop-slop/SKILL.md` +
  references. ~11K tokens.
- `cache_control: {"type": "ephemeral"}`.

The prefix must be byte-stable. Nothing volatile goes in it. In particular the
template's `*[Month Year]*` line lives in the user message, not the prefix, or the
cache silently invalidates every month.

Skill files stay on disk exactly as they are today, read at startup instead of
uploaded via the Skills API. They remain editable in git with unchanged history.

**User message** (volatile): company name, current month/year, numbered Tavily payload.

### `app.py`

`run_agent_session` is replaced by `generate_brief(config, company, status_callback,
timeout)` with the same signature. Two call sites (lines 2011, 2088) change by one
identifier each.

```
claude-sonnet-5
thinking:       {"type": "adaptive"}
output_config:  {"effort": "medium"}
max_tokens:     8000, streamed
```

Effort starts at `medium`: fit scoring and entry-point selection involve real
judgment, and `low` risks sloppy scoring. Tune down after the side-by-side.

**Progress UI is unchanged.** `status_callback` keeps the same phase strings and
`PHASE_TO_STEP` already contains a `"compose"` entry that the current agent path
never emits, so step 4 "Composing" is dead today. The new pipeline maps honestly:
`init` -> `research` (search) -> `analyze` (extract) -> `compose` (streamed
generation) -> `done`.

### References

The model receives a numbered source list with real URLs in-context and cites by
number, rather than reconstructing URLs from search results seen twenty turns
earlier. This is a prompt-only fix and removes the failure mode that
`system_prompt.py` currently fights with an all-caps non-negotiable rule.

If drift persists, building the References section in Python from the source list is
~15 lines and emits byte-identical markdown, so `pdf.py:_draw_references` is
unaffected. Not built now.

### Repeat-company cache

`db.find_recent_brief_by_company(company, max_age_days=7)` queries the existing
`briefs` table by normalised company across all emails rather than by email. No
schema change.

On hit, save a copy under the requesting user's email so their history, delete, and
PDF behaviour work normally. A cached result renders with a visible **Regenerate**
control and its original date: a partner walking into a meeting must be able to tell
today's research from last Tuesday's.

### Configuration

- Added: `TAVILY_API_KEY`, read via the existing `_secret()` helper so env var and
  `.streamlit/secrets.toml` both work.
- Removed: `ALKIRA_AGENT_ID`, `ALKIRA_ENV_ID`.
- Deleted: `setup_agent.py`, `setup_skills.py`.
- `requirements.txt`: `+tavily-python`.
- `generate_brief.py`: CLI rewired to the new path.

---

## Testing

- `tests/test_parsers.py` and `tests/test_pdf.py` stay green **untouched**. That is
  the proof the output contract did not move, and it is the primary regression gate.
- New `tests/test_research.py`: ranking, social-domain deprioritisation, per-page
  truncation, payload numbering. Runs against recorded fixtures; no live Tavily
  calls in CI.
- New test asserting the cached system prefix is byte-identical across two builds
  (guards the caching contract).
- New `tests/test_db.py` cases for the company lookup and the staleness window.
- Manual: generate 5 briefs on both paths, compare quality, latency, and
  `usage.cache_read_input_tokens` (non-zero from brief 2 onward, else the prefix has
  a silent invalidator).

---

## Risks

| Risk | Handling |
|---|---|
| Thin-research companies score lower than the agent's | Accepted, and arguably more honest. The rubric's 1-2 star rungs exist for exactly this. Regenerate control available. |
| Tavily becomes a hard dependency | Wrap and surface a real error. Never generate an uncited brief on a research failure. |
| Tavily key is `tvly-dev-` (development tier) | Lower rate limits and credit caps than production. Obtain a production key before cutover. Deploy risk, not a code risk. |
| Env vars change on both EC2 instances | Deploy-time change, not just a merge. Instances A and B both need `TAVILY_API_KEY` added and the two agent IDs removed. |
| Cache prefix invalidated by a stray timestamp | Covered by the byte-stability test and by keeping month/year in the user message. |

---

## Non-Goals

- Deleting the regex parsing layer in `app.py` / `pdf.py`.
- Structured JSON output.
- Any change to brief content, template, scoring rubric, or the three skill files.
- Feature-flagged dual path. Downtime during cutover is acceptable; simplicity wins.
