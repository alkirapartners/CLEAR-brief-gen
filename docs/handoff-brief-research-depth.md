# Handoff: deeper research for the Brief Generator

Written 2026-10-05 for a new Claude session. It covers what that session needs to know from the work that just finished (Streamlit removed, new front end and API live). It does not design the research change.

## The goal, in Blake's words

The briefs are too shallow. The generator runs a handful of Tavily searches, skims a few pages, and writes from that. Blake regularly takes a generated brief to a local Claude session and asks for "a full deep dive" to find out whether the company is really a fit for Alkira. He wants the generator itself to do that depth of research and answer "is this a good fit for Alkira, and why?" comprehensively, with a better form of web search than the current one.

## How a brief is produced today

Repo: `alkirapartners/CLEAR-brief-gen` (local: `~/Work/Projects/clear-brief-gen`).

| File | What it does |
|---|---|
| `research.py` | `build_queries()` builds **12** Tavily searches per company (basics, footprint, IT leadership, cloud, data center, filings, IT strategy, SEC cybersecurity, ERP, divestiture, two news queries limited to the past year). `search_depth="advanced"`, 4 results per query, run in parallel. Results are filtered for relevance to the company, ranked (social sites deprioritised, a floor per category), and up to **10** pages are extracted, each cut to **8,000 characters**. |
| `generate.py` | One streamed `claude-sonnet-5` call: adaptive thinking, effort `medium`, `max_tokens` 16,000, 180-second client timeout. No tools; the model only sees what `research.py` gathered. |
| `prompts.py` | The system prefix (brief template + Alkira knowledge base + writing rules from `skills/`), prompt-cached for 1 hour. It must stay byte-identical between briefs or the cache stops hitting; everything per-brief goes in the user message. |
| `skills/` | `alkira-brief-template` (structure, sentence limits, scoring rubric), `alkira-customer` (knowledge base, case studies, pricing, objections), `stop-slop` (writing rules). |

Measured on 2026-10-05 in production: 52 and 56 seconds per brief, roughly $0.10 to $0.20 each.

**The README and the live UI say "8 searches" and "top 5 pages". The code does 12 and up to 10.** The UI text was written from the README during the migration and is wrong; see "UI text to update" below.

### Why it works this way

Until 2026-09-02 briefs were written by a Claude Managed Agent that did its own web research over about 30 model turns. It was replaced by Tavily plus one call for speed and cost. Read these before proposing anything, because the depth Blake is missing is exactly what that change traded away:

- `docs/superpowers/specs/2026-08-31-tavily-single-call-design.md`
- `docs/superpowers/plans/2026-08-31-tavily-single-call.md`

## What must not break

The brief is stored as markdown and read back by regex parsers. The page, the PDF and the API all depend on its exact shape.

- **First line** must be `# ALKIRA OPPORTUNITY BRIEF`. `generate.py` raises if it is not.
- **Headings stay in English, as `##` or `###`, with exact text**, in every output language: `Infrastructure Snapshot` (with bold sub-labels Cloud Platforms, On-Prem / Hybrid, Deployment Model, Resulting Complexity), `Signals & Timing`, `Three Alkira Entry Points` (numbered bold headings, each with Signal / Solution / Proof), `Conversation Starters`, `References`.
- **Score line:** `**Alkira Fit Score: N / 5**`, followed by the rationale paragraph.
- **Header:** `## Company Name`, then one stats line `**HQ:** … | **Revenue:** … | …`.
- **Date line:** `*[Month Year]*`. The language of a stored brief is detected from a Spanish month name here.
- **Conversation Starters:** `**Stakeholders:**`, `**Best First Question:**`, numbered questions each followed by `*(You're listening for: …)*`, then `**Validate early:**` bullets.
- **References:** one per line, `[n] Title — https://…`.
- Ends with `*CONFIDENTIAL*`.

Where that is enforced: `briefparse.py` (parsers), `brief_view.py` (API shape), `pdf.py`, and the tests `tests/test_parsers.py`, `tests/test_bold_heading_tolerance.py`, `tests/test_prompts.py`, `tests/test_language.py`, `tests/test_pdf.py`. Treat the parser tests as a frozen gate: fix a fixture or the prompt, not a parser.

**Adding depth means adding somewhere to show it.** The front end only displays these fields: company, stats, score, rationale, four infrastructure cells, signals, up to three entry points, conversation starters, references. A new section (say, a longer evidence or risks section) will be stored but invisible until three things are extended: `brief_view.to_detail` here, a tile in the front end, and a block in `pdf.py`.

## Constraints the new design has to fit

- **Generator signature.** The API calls `generator(api_key, tavily_key, company, status_callback, language=...)` and expects the brief markdown back (`brief_service._run_generator`). `settings.py` only knows `ANTHROPIC_API_KEY` and `TAVILY_API_KEY`; a different search provider means a new setting there, a matching check in `brief_service._reserve_generation`, and the key added to `/var/www/briefgen/.env` on **both** servers by hand.
- **Progress phases.** `status_callback` is called with `init`, `research`, `analyze`, `compose`, `done`. The front end maps exactly those four visible steps. More or different phases need changes in three places in `alkira-account-radar`: `web/lib/brief-types.ts` (`BriefPhase`), `web/components/brief/step-tracker.tsx`, `web/dev/mock-api.mjs`.
- **Run time.** Long runs are fine for the connection: generation runs in a worker thread, the stream sends a heartbeat every 15 seconds, and a brief is saved even if the tab closes. Two limits to raise if research takes longer than a few minutes: the 180-second Anthropic client timeout in `generate.py`, and PM2's kill timeout on the `briefgen` process (currently 240 seconds; a deploy that lands mid-brief waits that long, then kills it).
- **Cost controls already in place.** One generation at a time per person. A daily cap of 50 paid generations per person (`BRIEF_DAILY_LIMIT`), counted in `usage_ledger.py`. Research from the last 7 days is reused across all partners by exact company name, free; "Update brief" always re-researches. If a brief becomes several times more expensive, revisit the cap and the reuse window.
- **Spanish.** Research runs in English; only the user message changes. Keep it that way so the cached prefix stays stable.
- **Untrusted input.** Everything fetched from the web is third-party text. The source payload is wrapped in a random fence in the user message (`research.format_payload`). More sources and any model-driven browsing widen this surface; keep the fencing, and keep the rule that the brief is stored as markdown and never rendered as HTML.
- **Known open risk:** a carefully worded company name can steer the model, and because reuse is shared, the result can be served to the next partner who asks for that company. Fixing it needs a column for the typed name. Deeper, more autonomous research makes this more worth fixing.

## UI text to update when research changes

These strings in `alkira-account-radar` describe the research and are already inaccurate (they say 8 searches and 5 pages):

- `web/components/brief/step-tracker.tsx`: "Running 8 web searches", "Ranking results and reading the top 5 pages", "Writing the brief from those sources".
- `web/components/brief/hero-aside.tsx` and `web/components/brief/library.tsx`: "Eight searches, the best five pages…".
- `web/components/brief/generate-box.tsx`: "Takes about a minute."
- Tests that assert those strings: `web/tests/brief/generate-box.test.tsx`.

## Trying research changes without the web app

`generate_brief.py` is a CLI that runs the real pipeline: `python generate_brief.py "Company" --verbose --output out.md`. It needs `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` in a local `.env`, which this machine does not have. That CLI is the cheapest way to compare old and new research on the same companies before touching production. A good test set is companies where Blake had to redo the brief by hand; ask him for two or three and for what the manual deep dive found that the brief missed.

Tests: `.venv/bin/python -m pytest -q` (276 passing). No test calls the network.

## Shipping

- Blake is a contributor (push, not admin) on `alkirapartners/CLEAR-brief-gen` and `alkirapartners/alkira-account-radar`. Work on a `feature/*` branch from `origin` and open a PR. Never push to the personal `upstream` remotes.
- **Merging to `main` deploys to production on both servers within seconds**: pull, `pip install -r requirements.txt`, restart. The recipe cannot be changed, so new Python packages go in `requirements.txt`, and anything else (a new environment variable, a process setting) has to be done over SSH on both instances. Servers run Python 3.14; local is 3.11.
- Instances: A `35.166.223.217`, B `32.184.242.60`, login `ubuntu@`, key `~/Work/_Keys/Alkira Channel (3).pem`. The API is PM2 process `briefgen` (`uvicorn server:app`, port 8501); logs with `pm2 logs briefgen`.
- Get Blake's explicit go-ahead before merging or changing anything on a server. He is not a developer: report in plain language, and show him real output (a brief for a company he knows) rather than describing it.

## Before choosing an approach

Not evaluated in the session that wrote this, so treat these as questions, not recommendations:

- Is the gap the *search* (wrong or too few sources), the *reading* (pages cut at 8,000 characters, only 10 read), or the *reasoning* (one pass at medium effort with no chance to follow a lead)? Comparing a weak brief with Blake's manual deep dive on the same company should show which.
- Options range from tuning what exists (more queries, more pages, longer page limits, higher effort) to letting the model drive its own research with web search and fetch tools over several turns, which is closer to what the retired agent did and to what Blake does by hand. Check current Claude API capabilities, models and pricing with the `claude-api` skill rather than from memory.
- What run time and cost per brief will Blake accept for a much better brief? That answer decides most of the design.

The Account Radar's scorer (`alkira-account-radar`, `api/radar/scorer.py`) is separate: one Claude call per account from general knowledge, no web search. It is not part of this unless Blake says so.
