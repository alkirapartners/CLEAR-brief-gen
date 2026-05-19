# Alkira Brief Generator

A web app for Alkira partners to generate scored opportunity briefs for any company. Enter a company name, get a structured brief with an Alkira Fit Score (1–5), strategic entry points, proof points, and sales questions — plus a downloadable PDF.

Powered by Claude Managed Agents (Anthropic) for research and generation, with magic-link authentication so only authorized partner domains can sign in.

---

## How It Works

1. Partner visits the app and signs in via magic link (email-based, no password)
2. Types a company name and clicks **Generate Brief**
3. Claude researches the company via web search and generates a structured brief
4. Brief is scored (Alkira Fit 1–5), displayed as a bento card layout, and saved to the sidebar
5. Partner can download as PDF, update (re-research), or delete the brief

---

## Architecture

```
Browser
  │
  └─► nginx (HTTPS, briefgen.partners.alkira.cc)
        │
        ├─► /api/*  ──► briefgen-proxy.js   (Node.js, port 3461)
        │                  Magic link auth, session cookies,
        │                  trusted domain + admin read APIs
        │
        ├─► /auth.html, /admin.html  ──► static files (/var/www/briefgen)
        │
        └─► /*  ──► Streamlit app (Python, port 8501)
                     auth_request gate: valid session required
                     X-Auth-Email header passed from nginx
```

**Key components:**

| File | Purpose |
|------|---------|
| `app.py` | Streamlit web app — UI, auth gate, brief rendering |
| `generate_brief.py` | CLI tool for generating briefs from the terminal |
| `briefgen-proxy.js` | Node.js auth backend — magic links, sessions, admin read API |
| `db.py` | Supabase persistence layer for brief history |
| `pdf.py` | PDF generation (fpdf2) |
| `system_prompt.py` | Alkira knowledge base embedded in the agent's system prompt |
| `auth.html` | Magic link sign-in page (static) |
| `admin.html` | Admin panel — read-only view of trusted domains and admins |
| `setup_agent.py` | One-time setup: creates the Claude agent + environment |
| `setup_skills.py` | Registers web-search and other skills on the agent |

---

## Admin management

Trusted domains and admin accounts are managed centrally via the **[Admin Portal](https://admin.partners.alkira.cc)**. The per-app admin panel at `/admin.html` is read-only — it shows the current lists but changes must be made in the admin portal.

---

## Local Development

### Prerequisites

- Python 3.10+
- Node.js 18+ (for `briefgen-proxy.js` if running auth locally)
- An Anthropic API key with Managed Agents beta access
- A Supabase project (optional — app runs without it, briefs won't persist)

### Setup

```bash
git clone https://github.com/alkirapartners/CLEAR-brief-gen.git
cd CLEAR-brief-gen

# Python dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment variables
cp .env.example .env   # or create .env manually
```

**.env file:**
```
ANTHROPIC_API_KEY=sk-ant-...
ALKIRA_AGENT_ID=...
ALKIRA_ENV_ID=...
SUPABASE_URL=https://xxxx.supabase.co      # optional
SUPABASE_KEY=sb_secret_...                  # optional
```

```bash
# First time only: create the agent and register skills
python setup_agent.py
python setup_skills.py

# Run the app
streamlit run app.py
```

App opens at `http://localhost:8501`. Auth is bypassed locally — the nginx gate only runs in production.

### CLI Usage

```bash
python generate_brief.py "Palo Alto Networks"
python generate_brief.py "Walmart" --output walmart_brief.md
python generate_brief.py "Chevron" --verbose
```

---

## Production Deployment

The app runs on an EC2 instance (`briefgen.partners.alkira.cc`) managed by PM2 and nginx.

**Processes:**

| PM2 name | What it runs |
|----------|-------------|
| `briefgen` | `streamlit run app.py` (port 8501) |
| `briefgen-proxy` | `node briefgen-proxy.js` (port 3461) |

**Auto-deploy:**  
Every push to `main` triggers the GitHub webhook → server pulls latest code, installs dependencies, and restarts both PM2 processes automatically. No manual SSH needed.

**Secrets on server** (not in repo):
- `/var/www/briefgen/.env` — API keys and Supabase credentials
- `/var/www/briefgen/data/admins.json` — admin user list (written by admin portal)
- `/var/www/briefgen/data/domains.json` — trusted domain list (written by admin portal)

---

## Authentication

Access is controlled by `briefgen-proxy.js`:

- **Users** sign in via magic link if their email domain is on the trusted domains list
- **Admins** can view the admin panel at `/admin.html` (read-only — manage via [Admin Portal](https://admin.partners.alkira.cc))
- Sessions are cookie-based (7-day TTL, HttpOnly, Secure, SameSite=Strict), persisted to `data/sessions.json` — survive process restarts
- Magic links expire after 15 minutes
- nginx `auth_request` gates all Streamlit traffic — unauthenticated requests redirect to `/auth.html`

---

## Updating the Knowledge Base

Edit `system_prompt.py` (Alkira proof points, brief template, scoring rubric), then re-run:

```bash
python setup_agent.py
```

This creates a new agent version. Update `ALKIRA_AGENT_ID` in `.env` with the new ID.

---

## Cost Per Brief

| Item | Estimate |
|------|----------|
| Claude Sonnet tokens | ~$0.10–0.30 |
| Managed Agents session | ~$0.08/hr |
| Web search queries (~5–10) | ~$0.05–0.10 |
| **Total** | **~$0.15–0.40 per brief** |
