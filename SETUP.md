# Alkira Brief Generator — Setup

The API behind the Brief Generator: partners type a company name and get a scored Alkira opportunity brief, downloadable as PDF. The screens are in [alkira-account-radar](https://github.com/alkirapartners/alkira-account-radar) (`web/`).

## How a brief is produced

1. `research.py` runs the brief template's research checklist as 8 parallel Tavily searches, ranks the hits, and extracts the top 5 pages.
2. `generate.py` makes one streamed `claude-sonnet-5` call that composes the whole brief from those sources.
3. `prompts.py` builds the system prefix (brief template, Alkira knowledge base, writing rules). It is byte-stable and prompt-cached with a 1-hour TTL; everything per-brief lives in the user message.
4. `brief_service.py` saves the brief; `briefparse.py` and `brief_view.py` turn the stored markdown into the fields the front end shows.

There is no agent session and no model-driven tool loop. A brief takes roughly 45 seconds.

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
| `research.py` | Tavily search + extract, ranking, source payload |
| `generate.py` | The single streamed Sonnet 5 call |
| `prompts.py` | Cached system prefix + per-brief user message |
| `db.py` | Supabase persistence and the 7-day repeat-company cache |
| `pdf.py` | PDF generation (fpdf2) |
| `notifications.py` | Slack webhook on successful generation |
| `generate_brief.py` | CLI alternative |
| `skills/` | Brief template, Alkira knowledge base, writing rules — inlined into the system prefix |

## Model Choice

`claude-sonnet-5` with `thinking={"type": "adaptive"}` and `output_config={"effort": "medium"}`, streamed. The task is source-grounded synthesis against a fixed template, not open-ended reasoning. To change it, edit `MODEL` in `generate.py`.

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
| Tavily searches (8) + extract | ~$0.05 |
| Sonnet 5 tokens (cached prefix, ~3K output) | ~$0.05–0.15 |
| **Total** | **~$0.10–0.20 per brief** |

The system prefix is prompt-cached for 1 hour. Repeat briefs within that window read the cache instead of paying full input rate. Separately, a brief for a company already researched in the last 7 days is served from Supabase without any model call at all.
