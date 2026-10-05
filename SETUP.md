# Alkira Brief Generator — Setup

A web app where partners type a company name and get a scored Alkira opportunity brief on the page, downloadable as PDF.

## How a brief is produced

1. `research.py` runs the brief template's research checklist as 8 parallel Tavily searches, ranks the hits, and extracts the top 5 pages.
2. `generate.py` makes one streamed `claude-sonnet-5` call that composes the whole brief from those sources.
3. `prompts.py` builds the system prefix (brief template, Alkira knowledge base, writing rules). It is byte-stable and prompt-cached with a 1-hour TTL; everything per-brief lives in the user message.
4. `app.py` parses, renders, and saves the brief.

There is no agent session and no model-driven tool loop. A brief takes roughly 45 seconds.

## Prerequisites

- Python 3.10+
- An Anthropic API key
- A Tavily API key
- A Supabase project (optional — the app runs without it, briefs just won't persist)

## Setup

```bash
pip install -r requirements.txt

# Create .env in the repo root
streamlit run app.py
```

**.env:**

```
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
SUPABASE_URL=https://xxxx.supabase.co      # optional
SUPABASE_KEY=sb_secret_...                 # optional
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...  # optional
```

`ANTHROPIC_API_KEY` and `TAVILY_API_KEY` are both required. The app fails at the config guard without them.

The app opens at http://localhost:8501.

The Brief API (FastAPI routes under `/api/brief/`) runs alongside the Streamlit page. Streamlit remains the served UI until the shared front end cuts over.

```bash
uvicorn server:app --host 127.0.0.1 --port 8501 --reload
# every request needs the header nginx sets in production:
curl -H "X-Auth-Email: you@example.com" http://127.0.0.1:8501/api/brief/briefs
```

Both default to port 8501, so run one at a time or pass a different `--port`. Tests: `pip install -r requirements-dev.txt` then `python -m pytest -q`.

## File Overview

| File | Purpose |
|------|---------|
| `app.py` | Streamlit web app — UI, rendering, history. Still the served UI until the shared front end cuts over |
| `research.py` | Tavily search + extract, ranking, source payload |
| `generate.py` | The single streamed Sonnet 5 call |
| `prompts.py` | Cached system prefix + per-brief user message |
| `server.py` | Brief API: FastAPI routes under `/api/brief/` (JSON plus a server-sent-event stream for generation) |
| `brief_service.py` | Generate / reuse / save / refresh rules, the one-generation-per-user guard and the daily cap |
| `brief_view.py` | Shapes a stored brief row into the API's summary and detail objects |
| `streaming.py` | Runs a blocking job in a thread and exposes it as an SSE stream with a heartbeat |
| `briefparse.py` | Pure brief-markdown parsers and the company-name cleaner (no Streamlit, no I/O) |
| `authdep.py` | `X-Auth-Email` request dependency and the admin check |
| `settings.py` | Environment configuration for the Brief API |
| `errors.py` | Errors whose message is safe to show to a partner |
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

Reads `ANTHROPIC_API_KEY` and `TAVILY_API_KEY` (plus the optional Supabase and Slack vars) from your shell or a `.env` file next to `docker-compose.yml`.

## Deployment

**Local:** `streamlit run app.py`

**Cloud VM:**

```bash
pip install -r requirements.txt
streamlit run app.py --server.port 8080 --server.address 0.0.0.0
```

Put it behind nginx or Cloudflare Tunnel for HTTPS. See `README.md` for the production two-instance layout.

## Updating the Knowledge Base

Edit the files under `skills/` (brief template and scoring rubric, Alkira proof points, writing rules) and restart the app. They are read at startup and inlined into the cached system prefix. No agent to re-provision.

## Cost Per Brief

| Item | Estimate |
|------|----------|
| Tavily searches (8) + extract | ~$0.05 |
| Sonnet 5 tokens (cached prefix, ~3K output) | ~$0.05–0.15 |
| **Total** | **~$0.10–0.20 per brief** |

The system prefix is prompt-cached for 1 hour. Repeat briefs within that window read the cache instead of paying full input rate. Separately, a brief for a company already researched in the last 7 days is served from Supabase without any model call at all.
