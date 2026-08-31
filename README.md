# Alkira Brief Generator

A web app for Alkira partners to generate scored opportunity briefs for any company. Enter a company name, get a structured brief with an Alkira Fit Score (1–5), strategic entry points, proof points, and sales questions — plus a downloadable PDF.

Research runs on Tavily, generation on a single streamed `claude-sonnet-5` call. Magic-link authentication limits sign-in to authorized partner domains.

---

## How It Works

1. Partner visits the app and signs in via magic link (email-based, no password)
2. Types a company name and clicks **Generate Brief**
3. `research.py` runs the brief template's research checklist as 8 parallel Tavily searches, ranks the hits, and extracts the top 5 pages
4. `generate.py` composes the whole brief in one streamed `claude-sonnet-5` call against those sources (~45s)
5. Brief is scored (Alkira Fit 1–5), displayed as a bento card layout, and saved to the sidebar
6. Partner can download as PDF, update (re-research), or delete the brief

A brief for a company already researched in the last 7 days is served from Supabase without a model call. **Update Brief** always re-researches and never consults that cache.

---

## Architecture

```
Browser (HTTPS)
  │
  └─► ALB (SSL termination, *.partners.alkira.cc)
        │         [sticky sessions enabled — required for Streamlit WebSocket]
        ├─► Instance A  →  nginx (HTTP)
        │     ├─► /api/*  →  briefgen-proxy.js (port 3461)
        │     └─► /*      →  Streamlit app (port 8501, auth_request gated)
        └─► Instance B  →  nginx (HTTP)
              ├─► /api/*  →  briefgen-proxy.js (port 3461)
              └─► /*      →  Streamlit app (port 8501, auth_request gated)
```

**Load balancer:** `ALB-Alkira-Channel-Team-Tools-170715566.us-west-2.elb.amazonaws.com`  
**SSL cert:** ACM wildcard `*.partners.alkira.cc` (auto-renewed)  
**Instance A:** `35.166.223.217` (us-west-2c)  
**Instance B:** `32.184.242.60` (us-west-2b)  
**EFS:** `fs-00082cbd5d53945eb` — shared data storage, mounted on both instances

> **Sticky sessions** are enabled on the ALB target group (load balancer generated cookie, 1-day duration). This is required because Streamlit uses WebSockets — all requests from a user must go to the same instance.

**Key components:**

| File | Purpose |
|------|---------|
| `app.py` | Streamlit web app — UI, auth gate, brief parsing and rendering |
| `research.py` | Tavily search + extract, result ranking, source payload |
| `generate.py` | The single streamed Sonnet 5 call |
| `prompts.py` | Prompt-cached system prefix + per-brief user message |
| `generate_brief.py` | CLI tool for generating briefs from the terminal |
| `briefgen-proxy.js` | Node.js auth backend — magic links, sessions, admin read API |
| `db.py` | Supabase persistence and the 7-day repeat-company cache |
| `pdf.py` | PDF generation (fpdf2) |
| `notifications.py` | Slack webhook on successful brief generation |
| `skills/` | Brief template, Alkira knowledge base, writing rules — inlined into the cached system prefix |
| `auth.html` | Magic link sign-in page (static) |
| `admin.html` | Admin panel — read-only view of trusted domains and admins |

---

## Admin management

Trusted domains and admin accounts are managed centrally via the **[Admin Portal](https://admin.partners.alkira.cc)**. The per-app admin panel at `/admin.html` is read-only — it shows the current lists but changes must be made in the admin portal.

---

## Local Development

### Prerequisites

- Python 3.10+
- Node.js 18+ (for `briefgen-proxy.js` if running auth locally)
- An Anthropic API key
- A Tavily API key
- A Supabase project (optional — app runs without it, briefs won't persist)

### Setup

```bash
git clone https://github.com/alkirapartners/CLEAR-brief-gen.git
cd CLEAR-brief-gen

# Python dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Environment variables — create .env in the repo root
```

**.env file:**
```
ANTHROPIC_API_KEY=sk-ant-...
TAVILY_API_KEY=tvly-...
SUPABASE_URL=https://xxxx.supabase.co      # optional
SUPABASE_KEY=sb_secret_...                  # optional
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...  # optional — posts a notification to Slack on successful brief generation
```

`ANTHROPIC_API_KEY` and `TAVILY_API_KEY` are both required; the app fails at the config guard without them. There is no agent or environment to provision.

```bash
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

**Processes on each instance:**

| PM2 name | What it runs |
|----------|-------------|
| `briefgen` | `streamlit run app.py` (port 8501) |
| `briefgen-proxy` | `node briefgen-proxy.js` (port 3461) |

**Auto-deploy:**  
Every push to `main` triggers webhooks on both instances → each server pulls latest code, installs dependencies, and restarts both PM2 processes automatically. No manual SSH needed.

- **Instance A webhook:** `http://35.166.223.217/webhook`
- **Instance B webhook:** `http://32.184.242.60/webhook`

**Secrets on server** (not in repo):
- `/var/www/briefgen/.env` — API keys and Supabase credentials
- `/var/www/briefgen/data/admins.json` — admin user list (written by admin portal, stored on EFS)
- `/var/www/briefgen/data/domains.json` — trusted domain list (written by admin portal, stored on EFS)

---

## SSH access

```bash
# Instance A
ssh -i ~/.ssh/alkira-channel.pem ubuntu@35.166.223.217

# Instance B
ssh -i ~/.ssh/alkira-channel.pem ubuntu@32.184.242.60
```

---

## Authentication

Access is controlled by `briefgen-proxy.js`:

- **Users** sign in via magic link on `auth.html` if their email domain is on the trusted domains list. A "Generate new code" button on step 2 lets users resend the link without starting over.
- **Admins** can view the admin panel at `/admin.html` (read-only — manage via [Admin Portal](https://admin.partners.alkira.cc))
- Sessions are cookie-based (7-day TTL, HttpOnly, Secure, SameSite=Strict), persisted to `data/sessions.json` on EFS — shared between instances
- Magic-link tokens are persisted to `data/tokens.json` on EFS (15-min TTL) so either instance can verify a link regardless of which generated it
- nginx `auth_request` gates all Streamlit traffic — unauthenticated requests redirect to `/auth.html`

---

## Restore procedure (replacing a failed instance)

> If restoring from AMI, most steps can be skipped — launch from the latest AMI snapshot and proceed from step 3.

1. **Launch new EC2** — Ubuntu, us-west-2, security group `sg-0916d14b598c043d0`.

2. **Install dependencies** (skip if launching from AMI):
   ```bash
   sudo apt update && sudo apt install -y nginx nodejs npm nfs-common python3 python3-venv python3-pip
   sudo npm install -g pm2
   ```

3. **Mount EFS:**
   ```bash
   # Replace <AZ> with the instance's availability zone (e.g. us-west-2b)
   sudo mkdir -p /mnt/efs
   echo "<AZ>.fs-00082cbd5d53945eb.efs.us-west-2.amazonaws.com:/ /mnt/efs nfs4 defaults,_netdev 0 0" | sudo tee -a /etc/fstab
   sudo mount /mnt/efs
   ```

4. **Deploy:**
   ```bash
   sudo mkdir -p /var/www/briefgen
   sudo chown -R ubuntu:ubuntu /var/www/briefgen
   git clone https://github.com/alkirapartners/CLEAR-brief-gen.git /var/www/briefgen
   cd /var/www/briefgen
   python3 -m venv venv && venv/bin/pip install -r requirements.txt
   npm install @aws-sdk/client-ses
   # Copy .env from another instance or restore from secure storage
   ln -s /mnt/efs/briefgen/data /var/www/briefgen/data
   sudo cp nginx-briefgen.conf /etc/nginx/sites-available/briefgen
   sudo ln -s /etc/nginx/sites-available/briefgen /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   pm2 start "venv/bin/streamlit run app.py --server.port 8501" --name briefgen
   pm2 start briefgen-proxy.js --name briefgen-proxy
   pm2 save && pm2 startup
   ```

5. **Register with ALB** — add the new instance to the ALB target group.

6. **Add GitHub webhook** — add `http://<new-instance-eip>/webhook` to repo Settings → Webhooks.

---

## Updating the Knowledge Base

Edit the files under `skills/` (brief template and scoring rubric, Alkira proof points, writing rules) and restart the app. They are read at startup and inlined into the prompt-cached system prefix. Nothing to re-provision.

---

## Cost Per Brief

| Item | Estimate |
|------|----------|
| Tavily searches (8) + extract | ~$0.05 |
| Sonnet 5 tokens (cached prefix, ~3K output) | ~$0.05–0.15 |
| **Total** | **~$0.10–0.20 per brief** |

The system prefix is prompt-cached with a 1-hour TTL, so briefs generated within an hour of each other read the cache instead of paying full input rate.
