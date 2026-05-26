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
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...  # optional — posts a notification to Slack on successful brief generation
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

- **Users** sign in via magic link if their email domain is on the trusted domains list
- **Admins** can view the admin panel at `/admin.html` (read-only — manage via [Admin Portal](https://admin.partners.alkira.cc))
- Sessions are cookie-based (7-day TTL, HttpOnly, Secure, SameSite=Strict), persisted to `data/sessions.json` on EFS — shared between instances
- Magic links expire after 15 minutes
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
