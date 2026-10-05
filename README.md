# Alkira Brief Generator

A web app for Alkira partners to generate scored opportunity briefs for any company. Enter a company name, get a structured brief with an Alkira Fit Score (1–5), strategic entry points, proof points, and sales questions — plus a downloadable PDF.

A `claude-sonnet-5-5` research loop follows leads on the web through Tavily, then one streamed call judges the fit and writes the brief. Sign-in is limited to authorized partner domains.

This repo holds the Brief API, the sign-in service and the sign-in pages. The screens partners use live in [alkira-account-radar](https://github.com/alkirapartners/alkira-account-radar) (`web/`), which serves both the Brief Generator and Account Radar.

---

## How It Works

1. Partner visits the app and signs in with a code sent to their work email (admins sign in through the dashboard's SSO)
2. Types a company name and clicks **Generate brief**
3. `research_loop.py` lets the model research the company: it identifies the entity, then searches, opens pages and records evidence, choosing each step from what it just read. The budget is 25 searches, 20 page reads and about four minutes, enforced in code. Only facts recorded from a page that was opened are kept
4. `generate.py` makes one streamed call that scores the fit and writes the brief from that evidence as a JSON document. `brief_rules.py` then enforces the rules in code: an angle with no opened-page evidence is removed, customer stories come from the knowledge base, and the score cannot exceed what the surviving angles support
5. The brief is saved and opened on its own page. It has one to three angles, never padded
6. Partner can download it as PDF, update it (re-research), or delete it

A brief took one and a half to two and a half minutes and cost about 40 cents when measured on eight companies; at the full research allowance it can take about five minutes and cost about a dollar. If research finds nothing it can cite, the partner gets an error and no brief is written.

A brief for a company already researched in the last 14 days is reused from Supabase without a model call. Reuse matches the name as it was typed, ignoring case: a brief is filed under what the partner typed, not under the name the model wrote, so nobody can plant a brief under another company's name. Only a brief in the current format whose research ran its course is shared; one that was cut short, or an older markdown brief, is researched again. **Update brief** always re-researches and never consults that cache.

Briefs written before this pipeline are stored as markdown and still open: `briefparse.py` reads them. New briefs are stored as JSON in the same column (`brief_doc.py`).

---

## Architecture

```
Browser (HTTPS)
  │
  └─► ALB (SSL termination, *.partners.alkira.cc)
        ├─► Instance A  →  nginx (HTTP, auth_request on everything but sign-in)
        │     ├─► /api/auth/*, /api/admins, /api/domains  →  briefgen-proxy.js (port 3461)
        │     ├─► /api/brief/*   →  Brief API, this repo (uvicorn, port 8501)
        │     ├─► /api/radar/*   →  Radar API (port 8601)
        │     └─► /*             →  Next.js front end, alkira-account-radar (port 3001)
        └─► Instance B  →  the same
```

**Load balancer:** `ALB-Alkira-Channel-Team-Tools-170715566.us-west-2.elb.amazonaws.com`  
**SSL cert:** ACM wildcard `*.partners.alkira.cc` (auto-renewed)  
**Instance A:** `35.166.223.217` (us-west-2c)  
**Instance B:** `32.184.242.60` (us-west-2b)  
**EFS:** `fs-00082cbd5d53945eb` — shared data storage, mounted on both instances

nginx asks the sign-in service whether the session cookie is valid, then passes the signed-in email to the APIs and the front end in an `X-Auth-Email` header, replacing anything the client sent. The Brief API trusts that header, which is why it listens on `127.0.0.1` only. The nginx site file is kept in `deploy/nginx-briefgen.conf`.

Sticky sessions are enabled on the ALB target group. Nothing here depends on them: any request can be served by either instance.

**Key components:**

| File | Purpose |
|------|---------|
| `server.py` | Brief API: FastAPI routes under `/api/brief/` (JSON plus a server-sent-event stream for generation) |
| `brief_service.py` | Generate / reuse / save / update rules, the one-generation-per-user guard and the daily cap |
| `usage_ledger.py` | Append-only record of paid generations in the shared data directory, for the daily cap |
| `brief_view.py` | Shapes a stored brief row into the API's summary and detail objects, for both stored formats |
| `brief_doc.py` | The JSON brief document: its shape, the schema sent to the model, and telling a JSON brief from a legacy one |
| `brief_rules.py` | Rules enforced on a brief in code: cited pages only, no padded angles, score capped by evidence, stories from the knowledge base |
| `brief_compat.py` | A JSON brief expressed as the fields the current front end reads |
| `stored_brief.py` | Score, company and language of a stored brief in either format |
| `brief_text.py` | A JSON brief as readable text, for the CLI |
| `briefparse.py` | Pure parsers for legacy markdown briefs, and the company-name cleaner |
| `streaming.py` | Runs a blocking job in a thread and exposes it as an SSE stream with a heartbeat |
| `authdep.py` | `X-Auth-Email` request dependency and the admin check |
| `settings.py` | Environment configuration |
| `errors.py` | Errors whose message is safe to show to a partner |
| `research_loop.py` | The research conversation: the clock, the turn limit, and the rule that research with nothing citable is an error |
| `research_tools.py` | The search, page-read and record-evidence tools, run against Tavily under the search and page budgets |
| `evidence.py` | Recorded facts, which pages were opened, and the fenced evidence the writer reads |
| `case_studies.py` | The customer-story table in the knowledge base, read as data |
| `llm.py` | The model, the request settings shared by both stages, and the cost estimate |
| `generate.py` | Research, then the judge-and-write call, then the rules |
| `prompts.py` | The two prompt-cached system prefixes and the per-brief messages |
| `db.py` | Supabase persistence and the 14-day repeat-company cache |
| `pdf.py`, `pdf_doc.py` | PDF generation (fpdf2): legacy markdown briefs and JSON briefs |
| `notifications.py` | Slack webhook on successful brief generation |
| `generate_brief.py` | CLI tool for generating briefs from the terminal |
| `skills/` | Brief template, Alkira knowledge base, writing rules — inlined into the cached system prefix |
| `briefgen-proxy.js` | Node.js sign-in service — email codes, SSO, sessions, admin read API |
| `auth.html` | Sign-in page (static) |
| `admin.html` | Settings page — read-only view of trusted domains |
| `deploy/nginx-briefgen.conf` | The nginx site file as deployed on both instances |

### API

Every route except `/health` needs `X-Auth-Email`. A brief id that belongs to someone else answers 404, the same as one that does not exist. Non-stream responses are `{"success", "data", "error"}`.

| Method and path | Purpose |
|---|---|
| `GET /api/brief/health` | Liveness |
| `GET /api/brief/me` | `{email, isAdmin}` |
| `GET /api/brief/briefs` | The caller's briefs |
| `GET /api/brief/briefs/{id}` | One brief as fields. A JSON brief also carries the whole document under `doc` (`format` is 2); a legacy brief has `format` 1 and `doc` null |
| `POST /api/brief/briefs` | Body `{company, language}`. Streams progress, then the brief id |
| `POST /api/brief/briefs/{id}/refresh` | Update: always re-researches. Same stream |
| `DELETE /api/brief/briefs/{id}` | Delete |
| `GET /api/brief/briefs/{id}/pdf` | PDF download |

---

## Admin management

Trusted domains and admin accounts are managed centrally via the **[Admin Portal](https://admin.partners.alkira.cc)**. The per-app page at `/admin.html` is read-only — it shows the current list but changes must be made in the admin portal.

---

## Local Development

### Prerequisites

- Python 3.11+
- Node.js 18+ (for `briefgen-proxy.js` if running sign-in locally)
- An Anthropic API key
- A Tavily API key
- A Supabase project (optional — the API runs without it, briefs won't persist)

### Setup

```bash
git clone https://github.com/alkirapartners/CLEAR-brief-gen.git
cd CLEAR-brief-gen

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

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

`ANTHROPIC_API_KEY` and `TAVILY_API_KEY` are both required to generate; without them the API starts but refuses generation with a 503.

Optional settings:

| Variable | Default | Purpose |
|----------|---------|---------|
| `BRIEF_DAILY_LIMIT` | `10` | Paid generations (new briefs and updates) each person may run per UTC day. Reused research is free and not counted. |
| `BRIEF_DATA_DIR` | `./data` | Where daily usage files (`brief-usage-YYYY-MM-DD.jsonl`) are kept. In production `data/` is the EFS symlink, so both instances share one count. |
| `BRIEF_ADMINS_FILE` | `/var/www/briefgen/data/admins.json` | The admin list used to show the Settings link. |

```bash
# Run the API
uvicorn server:app --host 127.0.0.1 --port 8501 --reload

# Every request needs the header nginx sets in production:
curl -H "X-Auth-Email: you@example.com" http://127.0.0.1:8501/api/brief/briefs

# Tests
python -m pytest -q
```

For the screens, run the front end from alkira-account-radar (`cd web && npm run dev`); it proxies `/api/brief/` to port 8501 in development. That repo also has a mock API, so the front end can be worked on with no keys at all.

### CLI Usage

```bash
python generate_brief.py "Palo Alto Networks"
python generate_brief.py "Walmart" --output walmart_brief.md
python generate_brief.py "Chevron" --verbose
python generate_brief.py "HF Sinclair" --save-dir out/   # JSON, text, PDF, and a line in out/metrics.jsonl
```

The CLI prints the brief as readable text, then one line of time, tokens and estimated cost.

---

## Production Deployment

**Processes on each instance:**

| Name | Manager | What it runs |
|------|---------|--------------|
| `briefgen` | PM2 | `uvicorn server:app --host 127.0.0.1 --port 8501`, started with `--kill-timeout 240000` |
| `briefgen-proxy` | PM2 | `node briefgen-proxy.js` (port 3461) |
| `radar-web` | systemd | The Next.js front end from alkira-account-radar (port 3001) |
| `radar-api` | systemd | The radar API from alkira-account-radar (port 8601) |

The kill timeout matters: PM2's default is 1.6 seconds, which would kill a brief mid-write on every deploy. With it, a restart waits up to four minutes for a brief in progress to finish and be saved.

Four minutes covers a normal brief but not the slowest one. The code caps research at 300 seconds (`RESEARCH_CEILING_SECONDS` in `research_loop.py`) and the writing call at 180 seconds plus one stalled connection (`WRITER_DEADLINE_SECONDS` and `WRITER_STALL_SECONDS` in `generate.py`), so a brief can run for up to about ten minutes when the model or the web search service is slow. A deploy that lands in the first minutes of such a brief kills it: the partner sees an error and the day's slot is spent. Raising the kill timeout to 600000 on both instances closes that gap. It is a change on the servers, not in this repo, and has not been made.

**Auto-deploy:**  
Every merge to `main` is picked up on both instances within about a minute → each server pulls the latest code, runs `pip install -r requirements.txt`, and restarts `briefgen` and `briefgen-proxy`. No manual SSH needed. The deploy recipe is fixed (it lives in the intranet repo), so anything beyond those three steps — a new process, an nginx change — has to be done by hand on both instances.

- **Instance A webhook:** `http://35.166.223.217/webhook`
- **Instance B webhook:** `http://32.184.242.60/webhook`

**On the server, not in the repo:**
- `/var/www/briefgen/.env` — API keys and Supabase credentials
- `/var/www/briefgen/data/` — symlink to EFS, shared by both instances: `admins.json`, `domains.json` (written by the admin portal), `sessions.json`, `otps.json` (sign-in service), and `brief-usage-*.jsonl` (daily cap)

---

## SSH access

```bash
# Instance A
ssh -i <path-to-key>.pem ubuntu@35.166.223.217

# Instance B
ssh -i <path-to-key>.pem ubuntu@32.184.242.60
```

---

## Authentication

Access is controlled by `briefgen-proxy.js`:

- **Users** enter their work email on `auth.html`. If its domain is on the trusted list they are emailed a 6-digit code, valid for 10 minutes, and enter it to sign in.
- **Admins** sign in through the Channel Team Dashboard's SSO and can view `/admin.html` (read-only — manage via the [Admin Portal](https://admin.partners.alkira.cc)).
- Sessions are cookie-based (7-day TTL, HttpOnly, Secure, SameSite=Strict), persisted to `data/sessions.json` on EFS — shared between instances. Pending codes are in `data/otps.json` for the same reason.
- nginx `auth_request` gates everything except the sign-in page and its assets. Unauthenticated requests are redirected to `/auth.html`, as a path rather than an `http://` address so that a background request from an expired session reaches the sign-in page too.

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

4. **Deploy this repo:**
   ```bash
   sudo mkdir -p /var/www/briefgen
   sudo chown -R ubuntu:ubuntu /var/www/briefgen
   git clone https://github.com/alkirapartners/CLEAR-brief-gen.git /var/www/briefgen
   cd /var/www/briefgen
   python3 -m venv venv && venv/bin/pip install -r requirements.txt
   npm install @aws-sdk/client-ses
   # Copy .env from another instance or restore from secure storage
   ln -s /mnt/efs/briefgen/data /var/www/briefgen/data
   sudo cp deploy/nginx-briefgen.conf /etc/nginx/sites-available/briefgen
   sudo ln -s /etc/nginx/sites-available/briefgen /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   pm2 start venv/bin/uvicorn --name briefgen --interpreter none --cwd /var/www/briefgen \
     --kill-timeout 240000 -- server:app --host 127.0.0.1 --port 8501
   pm2 start briefgen-proxy.js --name briefgen-proxy
   pm2 save && pm2 startup
   ```

5. **Deploy the front end and radar** — follow `SETUP.md` in alkira-account-radar (`/opt/radar`, systemd `radar-web` and `radar-api`). Without it nginx has nothing to serve at `/`.

6. **Register with ALB** — add the new instance to the ALB target group.

7. **Add GitHub webhook** — add `http://<new-instance-eip>/webhook` to repo Settings → Webhooks.

---

## Updating the Knowledge Base

Edit the files under `skills/` (brief template and scoring rubric, Alkira proof points, writing rules) and merge. They are read at startup and inlined into the prompt-cached system prefix. Nothing to re-provision.

---

## Cost Per Brief

| Item | Estimate |
|------|----------|
| Tavily searches (8) + extract | ~$0.05 |
| Sonnet 5 tokens (cached prefix, ~3K output) | ~$0.05–0.15 |
| **Total** | **~$0.10–0.20 per brief** |

The system prefix is prompt-cached with a 1-hour TTL, so briefs generated within an hour of each other read the cache instead of paying full input rate.
