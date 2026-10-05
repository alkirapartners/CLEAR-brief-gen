# Alkira Brief Generator — Setup

The API behind the Brief Generator: partners type a company name and get a scored Alkira opportunity brief, downloadable as PDF. The screens are in [alkira-account-radar](https://github.com/alkirapartners/alkira-account-radar) (`web/`).

## How a brief is produced

1. `research_loop.py` runs a research conversation with `claude-sonnet-5-5`. The model identifies the company, then searches, opens pages and records evidence through the tools in `research_tools.py`, which call Tavily. The budget is 25 searches, 20 page reads and about four minutes, enforced in code.
2. `generate.py` makes one streamed call that scores the fit and writes the brief as a JSON document from the recorded evidence. `brief_rules.py` enforces the rules on the result.
3. `prompts.py` builds two system prefixes, one per stage (instructions plus skill files). Each is byte-stable and prompt-cached with a 1-hour TTL; everything per-brief lives in the user message.
4. `brief_service.py` saves the brief; `brief_view.py` turns it into the fields the front end shows. Briefs from before this pipeline are markdown and are read by `briefparse.py`.

The loop runs in this process, not in a hosted agent. A brief took between one and a half and two and a half minutes when measured, and can take about five at the full research allowance.

## Prerequisites

- Python 3.11+
- An Anthropic API key
- A Tavily API key
- A Supabase project (optional — the API runs without it, briefs just won't persist)

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Create .env in the repo root, then:
uvicorn server:app --host 127.0.0.1 --port 8501 --reload
```

**.env:**

```
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
SUPABASE_URL=https://xxxx.supabase.co      # optional
SUPABASE_KEY=sb_secret_...                 # optional
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...  # optional
```

`ANTHROPIC_API_KEY` and `TAVILY_API_KEY` are both required to generate. Without them the API starts but refuses generation.

Every request needs the header nginx sets in production:

```bash
curl -H "X-Auth-Email: you@example.com" http://127.0.0.1:8501/api/brief/briefs
```

Tests: `python -m pytest -q`.

## File Overview

| File | Purpose |
|------|---------|
| `server.py` | Brief API: FastAPI routes under `/api/brief/` (JSON plus a server-sent-event stream for generation) |
| `brief_service.py` | Generate / reuse / save / update rules, the one-generation-per-user guard and the daily cap |
| `usage_ledger.py` | Append-only record of paid generations, for the daily cap |
| `brief_view.py` | Shapes a stored brief row into the API's summary and detail objects |
| `briefparse.py` | Pure brief-markdown parsers and the company-name cleaner |
| `streaming.py` | Runs a blocking job in a thread and exposes it as an SSE stream with a heartbeat |
| `authdep.py` | `X-Auth-Email` request dependency and the admin check |
| `settings.py` | Environment configuration |
| `errors.py` | Errors whose message is safe to show to a partner |
| `research_loop.py`, `research_tools.py`, `evidence.py` | The research conversation, its tools and budgets, and the evidence it records |
| `generate.py` | Research, then the judge-and-write call |
| `brief_doc.py`, `brief_rules.py` | The JSON brief document and the rules enforced on it |
| `llm.py` | The model and the request settings shared by both stages |
| `prompts.py` | Cached system prefixes + per-brief messages |
| `db.py` | Supabase persistence and the 14-day repeat-company cache |
| `pdf.py` | PDF generation (fpdf2) |
| `notifications.py` | Slack webhook on successful generation |
| `generate_brief.py` | CLI alternative |
| `skills/` | Brief template, Alkira knowledge base, writing rules — inlined into the system prefix |

## Model Choice

`claude-sonnet-5-5` with adaptive thinking at `medium` effort for both stages. Research is a tool loop of short requests; the judge-and-write call is streamed and returns JSON checked against a schema. To change the model, edit `MODEL` in `llm.py`.

## Docker

```bash
docker compose up --build
```

Reads `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` (plus the optional Supabase and Slack vars) from your shell or a `.env` file next to `docker-compose.yml`. The port is published on `127.0.0.1` only: the API trusts the `X-Auth-Email` header, so it must only be reachable through a proxy that sets it.

## Deployment

The API must never be exposed directly. It believes whatever `X-Auth-Email` says, so it listens on `127.0.0.1` and sits behind nginx, which sets that header from the sign-in service's answer. See `README.md` for the production two-instance layout and `deploy/nginx-briefgen.conf` for the site file.

## Updating the Knowledge Base

Edit the files under `skills/` (brief template and scoring rubric, Alkira proof points, writing rules) and restart the API. They are read at startup and inlined into the cached system prefix. No agent to re-provision.

## Cost Per Brief

| Item | Estimate |
|------|----------|
| Tavily: up to 25 searches and 20 page reads | up to ~$0.45 |
| Research tokens (a conversation that grows to about 120K tokens, cached turn to turn) | ~$0.40–0.75 |
| Judge-and-write tokens (cached prefix, ~6K output) | ~$0.07–0.13 |
| **Total** | **~$0.70–1.35 per brief (estimate)** |

The table is the estimate at the full research allowance. Measured over 8 companies on 2026-10-05: median 94 seconds and $0.39 per brief (range 82 to 138 seconds, $0.32 to $0.51). Those runs stopped on their own after 6 to 13 of the 25 searches and 4 to 11 of the 20 page reads. `generate_brief.py` prints the measured time, tokens and cost of every run.

Each stage's system prefix is prompt-cached for 1 hour. Repeat briefs within that window read the cache instead of paying full input rate. Separately, a brief for a company already researched in the last 14 days is served from Supabase without any model call at all. The daily cap is 10 paid briefs per person.
