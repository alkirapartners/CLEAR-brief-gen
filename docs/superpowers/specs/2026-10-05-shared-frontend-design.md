# Shared front end for Brief Generator and Account Radar

**Date:** 2026-10-05
**Status:** Draft for review
**Repos:** `alkirapartners/CLEAR-brief-gen` (API, auth service, sign-in pages) and `alkirapartners/alkira-account-radar` (the shared web app)

## 1. Goal

Remove Streamlit from the Brief Generator and serve both partner tools from one web app with one design system, so that:

- Both tools look like one premium, modern product. They face partners and represent an IT company.
- A visual change is made once and both tools pick it up.
- Each brief has its own address, so it can be bookmarked and reopened.
- Nothing about sign-in, saved briefs, PDFs, prompts, or cost per brief changes.

**Done means:** partners sign in exactly as today and land on the new Brief Generator at the same address; every feature listed in section 2 works; Account Radar lives in the same shell at `/radar`; Streamlit is no longer running or in the repo; both repos' tests pass.

## 2. What must keep working

Brief Generator features carried over one for one:

| Feature | Today | After |
|---|---|---|
| Generate a brief | Form, 4-step tracker, ~45s | Same steps, live progress |
| 7-day reuse of recent research | Cache lookup, "reused research" badge | Same rule, same badge |
| English / Spanish | Toggle next to the input | Same |
| Your briefs | Sidebar list and four dashboard cards | Library on the home page |
| Open a saved brief | Click in sidebar | Own page at `/briefs/<id>` |
| Update Brief (re-research) | Button on a saved brief | Same |
| Delete with confirmation | Link plus dialog | Button plus dialog |
| Download PDF | Button | Same file, same filename rule |
| Prefill from Radar (`/?company=`) | Fills the input, does not auto-run | Same |
| Slack notification on new brief | Fired on save | Unchanged (lives in `db.py`) |
| Admin "Settings" link | Sidebar, admins only | User menu, admins only |
| Sign out | Sidebar link | User menu |

Account Radar keeps every feature it has. It is restyled and moved into the shared shell, not redesigned.

## 3. Architecture

### Today

```
nginx (auth_request -> briefgen-proxy.js :3461, sets X-Auth-Email)
  /            -> Streamlit :8501            (PM2 "briefgen")
  /radar/      -> Next.js :3001              (systemd radar-web, basePath /radar)
  /api/radar/  -> FastAPI :8601              (systemd radar-api)
  /api/*       -> briefgen-proxy.js :3461    (PM2 "briefgen-proxy")
```

### After

```
nginx (same auth gate, same header)
  /            -> Next.js :3001              (one app: Brief Generator + Radar)
  /api/brief/  -> FastAPI :8501              (PM2 "briefgen", now uvicorn)
  /api/radar/  -> FastAPI :8601              (unchanged)
  /api/*       -> briefgen-proxy.js :3461    (unchanged)
```

Process count and ports are unchanged. The auth service, its cookie, the sign-in flow and SSO are not touched.

### Why this shape

- The deploy poller's recipe for brief-gen is fixed (pull, `pip install`, restart PM2 `briefgen` and `briefgen-proxy`) and lives in a repo we cannot edit. A Python API on the existing PM2 name deploys with that recipe as is.
- The radar's recipe already builds a Next.js app. Making that app the shared front end needs no poller change either.
- One front end means one design system and one navigation shell.

### Where code lives

| Repo | Holds |
|---|---|
| `CLEAR-brief-gen` | Brief API (`server.py` and helpers), research/generation/PDF/db modules, auth service, `auth.html`, `admin.html` |
| `alkira-account-radar` | `web/` becomes the shared front end for both tools; `api/` stays the radar API |

A feature that touches the brief API and its screen is two PRs. The API ships first and stays backward compatible.

## 4. Brief API (CLEAR-brief-gen)

FastAPI app served by `uvicorn server:app --host 127.0.0.1 --port 8501 --workers 1`.

### Module changes

| File | Change |
|---|---|
| `briefparse.py` (new) | The pure parsers move here from `app.py` unchanged: `clean_brief`, `extract_score`, `extract_company_header`, `extract_section`, `extract_entry_points`, `extract_infra_cells`, `extract_exec_snippet`, `clean_company_prefill` |
| `server.py` (new) | App factory and routes |
| `brief_service.py` (new) | Generate / reuse / save / replace orchestration, lifted out of `main()` |
| `authdep.py` (new) | `X-Auth-Email` dependency (same contract as the radar's) and the admin check |
| `streaming.py` (new) | Server-sent-event helper with heartbeat |
| `db.py`, `notifications.py` | Drop the `streamlit` import; read config from the environment only. Add `get_brief(id, email)`; `delete_brief` gains an owner filter |
| `app.py` | Kept until cutover is confirmed, importing parsers from `briefparse`. Deleted in the cleanup PR |

### Routes

All routes require the `X-Auth-Email` header that nginx sets. Every route that takes a brief id filters by the caller's email and returns 404 otherwise. Today's `delete_brief` has no owner check; that was safe only because ids never left the server.

| Method and path | Purpose |
|---|---|
| `GET /api/brief/me` | `{email, isAdmin}` for the user menu |
| `GET /api/brief/briefs` | The caller's briefs: id, company, score, snippet, language, createdAt |
| `GET /api/brief/briefs/{id}` | One brief, parsed into fields (below) |
| `POST /api/brief/briefs` | Body `{company, language}`. Streams progress, then the new brief id |
| `POST /api/brief/briefs/{id}/refresh` | Update Brief: always re-researches. Same stream |
| `DELETE /api/brief/briefs/{id}` | Delete |
| `GET /api/brief/briefs/{id}/pdf` | PDF download with the existing filename rule |
| `GET /api/brief/health` | Liveness |

Non-stream responses use one envelope: `{"success": bool, "data": ..., "error": string | null}`.

**Parsed brief:** `company`, `statsLine`, `score`, `scoreRationale`, `infra` (cloud platforms, on-prem, deployment, complexity), `signals` (list of markdown strings), `entryPoints` (heading, signal, solution, proof), `startersMd`, `referencesMd`, `language`, `labels` (the tile labels in the brief's language), `createdAt`. Section text is sent as markdown, never as HTML. The browser renders it with a markdown component that does not allow raw HTML, which removes today's unescaped-HTML path.

### Generation stream

`POST` returns `text/event-stream` on the same request. No job table and no shared state, so it does not matter which server handles it.

- Events: `{"type":"phase","phase":"init|research|analyze|compose"}`, then `{"type":"done","briefId":"...","reusedFrom":"<date>" | null}` or `{"type":"error","message":"..."}`.
- A comment line every 15 seconds keeps the load balancer from closing an idle connection during the compose step.
- The blocking research and model call run in a worker thread. The thread saves the brief itself, so a closed tab still produces a saved brief and paid work is never lost.
- Update Brief saves the new brief before removing the old one, so a failed re-research never costs the partner the brief they had. The stored briefs have no "reused" column, so the reused-research badge travels on the `done` event, as it does today.
- Response sets `X-Accel-Buffering: no`.

### Limits and validation

- `company`: control characters and whitespace flattened, 1 to 100 characters (the radar's cap on an account name). `language`: `en` or `es`.
- One generation in flight per user per server (in memory).
- Daily cap per user, counted from that user's briefs dated today (UTC). `BRIEF_DAILY_LIMIT`, default 50. A reused brief is never blocked by the cap, since it costs nothing.
- Errors shown to the user are friendly and generic. The exception detail goes to the server log only. Today the page prints the raw exception.
- The session cookie is `SameSite=Strict`, which blocks cross-site requests. Mutating routes also require a JSON content type.

## 5. Front end (alkira-account-radar `web/`)

Next.js 16, React 19, Tailwind 3 (already in place).

### Routes

| Path | Screen |
|---|---|
| `/` | Brief Generator: generate box, stats, library |
| `/briefs/[id]` | One brief |
| `/radar` | Account Radar |
| `/radar/batch/[id]` | A past radar batch |

`basePath` and `assetPrefix` are removed and the radar pages move under `app/radar/`. Existing `/radar` links keep working. The radar's "Generate brief" link becomes an internal link to `/?company=`.

### Structure

```
web/
  app/            layout, (brief)/page, briefs/[id]/page, radar/...
  components/
    shell/        top bar, tool tabs, user menu
    brief/        generate box, step tracker, library, brief view tiles
    radar/        existing components, restyled
    ui/           button, input, segmented control, dialog, toast, skeleton, score meter, pill
  lib/
    brief-api.ts, brief-stream.ts, prefill.ts, score.ts
  styles/         tokens.css, typography.css
```

### Libraries added

| Library | For |
|---|---|
| `@tanstack/react-query` | Brief list and detail caching, refresh after generate or delete |
| `react-markdown` | Safe rendering of starters, references and signals |
| `@radix-ui/react-dialog` | Accessible delete confirmation (focus trap, escape, labelling) |
| `lucide-react` | One icon set |
| `motion` | Layout, presence and spring animation (loaded lazily to stay inside the JS budget) |
| `@axe-core/playwright` (dev) | Automated accessibility checks |

Fonts are committed to the repo and loaded with `next/font/local`, so builds on the servers do not fetch anything.

### Security headers

Set from the Next app: a nonce-based Content-Security-Policy (`default-src 'self'`, no inline script without the nonce, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, and a minimal `Permissions-Policy`. No third-party scripts or fonts are loaded.

## 6. Design direction

**Direction:** warm, soft, premium product design, in the house style. A warm off-white page, white cards with hairline borders and whisper shadows, generous rounding, one accent, and large confident numerals. Information-dense but airy. Not a dashboard template, and not the current navy-gradient hero.

**Theme:** light only at launch. Tokens are structured so dark can be added later.

### Tokens

| Token | Value | Use |
|---|---|---|
| Canvas | `#F5F5F3` | Page background |
| Surface | `#FFFFFF` | Cards |
| Sunken | `#EFEFED` | Tracks, input wells |
| Ambient | `#0D0D0E` with a soft Alkira-blue radial glow | The generate box and the conversation-starters tile only |
| Text | `#141414` / `#6B7280` / `#9CA3AF` | Primary / secondary / tertiary |
| Accent | Alkira blue `#2D58F2` | Primary action, active tab, strong scores. The only accent |
| Semantic | green, amber, red-pink with tints | Status only |
| Radius | 20 cards, 12 inner, full pills | Nested rounding |
| Type | Inter (variable, optical sizing) for UI; JetBrains Mono for scores and counts | Two families |
| Motion | 150 / 250 ms, transform and opacity only, reduced-motion respected | |

### Signature elements

- **Score as a numeral.** Fit score set large and bold with a five-tick meter beneath it and the rationale beside it. Radar's 1 to 10 score uses the same meter at ten ticks. Colour always travels with a number and a label.
- **Ambient generate box.** The one dark surface on the page: near-black, a soft blue glow, the company input, the language pill and the Generate button. During generation it becomes the progress view with the four steps and an elapsed timer.
- **Pills.** Language toggle and tool tabs are full-round segmented controls with a solid active pill.
- **Brief page as a bento.** Header with company, stat pills and actions; score tile beside the four infrastructure tiles; signals; three entry points; conversation starters on the ambient surface; references as a quiet footer.
- **Library.** Tall rows with company, score meter, one-line summary and date; search and sort. A designed empty state explains the tool in three steps.
- **Radar table.** Tall rows, mono numerals, tier pills, three reasons, and a clear Generate brief action.

### Motion

Motion is part of the product, present on every screen, and always tied to a cause: something arrives, responds, progresses or reorders. The only looping decoration is the ambient glow.

| Moment | Motion |
|---|---|
| Page change | Content fades and rises 8px. Where the browser supports view transitions, a library row's company name and score morph into the brief page header; elsewhere a plain fade |
| Tabs and language toggle | The active pill slides between options on a spring |
| Buttons and cards | Press scales to 0.97 within 100ms; cards lift 2px with a deeper shadow on hover; focus rings ease in |
| Generate box | The glow drifts slowly behind the form. On submit the box morphs from form to progress view and the typed name becomes the title |
| Progress | The connector draws between steps, the active step carries a soft pulse, finished steps tick, and an elapsed timer runs in tabular numerals. Each step shows a true one-line description of what is happening |
| Brief reveal | Tiles arrive in a 40ms stagger; the score counts up while its meter fills tick by tick; stat pills settle in |
| Library | Rows stagger in on first load; a new brief slides into place; a deleted brief collapses out, confirmed by a toast |
| Stats | Numerals count up the first time they are seen |
| Dialog and toast | Dialog scales in from 0.96 over a blurred backdrop and leaves faster than it arrives; toasts slide up and dismiss themselves |
| Radar | Pending rows shimmer; each result lands with its meter filling; when scoring finishes, rows glide into score order |

Rules: transform and opacity only; 150ms for responses, 250ms for arrivals, 400ms at most for the morphs; ease-out in, ease-in out; springs for pills and reordering; everything interruptible and nothing blocks input. Under reduced motion, movement is replaced by short fades, counts jump to their final value, and the glow holds still.

### Details that carry the polish

- The tab title follows the content (the company name on a brief page).
- `/` focuses the company input; Enter generates.
- Dates read as "2 days ago" with the exact time on hover.
- Each conversation starter has a copy button that confirms with a tick.
- The brief header and its actions stay pinned while scrolling.
- Skeletons match the final layout, so nothing jumps when data arrives.
- Designed empty, error and not-found states, each with a next step.
- An expired session sends the browser to sign-in instead of showing a broken page.
- Scroll position and library search survive going into a brief and back.

### Quality gates

Contrast at least 4.5:1, visible focus rings, full keyboard operation, 44px touch targets, visible form labels, skeletons instead of spinners for loads over a second, no layout shift, and layouts that hold from 320px to 1920px.

## 7. Server changes and cutover

All server steps are one-time, done over SSH on both instances, and reversible. The nginx site file is backed up first.

### Preview before anything public changes

On one instance, a second checkout of each feature branch runs on spare ports (web 3002, API 8502). A localhost-only nginx listener routes to them and injects a fixed test email. It is reachable only through an SSH tunnel. This exercises the real environment, real keys and real database with no public exposure. It generates one or two real briefs (about $0.15 each) under Blake's email. The preview is torn down after cutover.

### Cutover order

1. **Prep (additive):** add an auth-gated `location /_next/` pointing at port 3001 on both instances. Streamlit does not use that path.
2. **Merge the brief-gen PR.** The poller installs FastAPI and restarts Streamlit, which is still what PM2 runs. The only visible change is the restyled sign-in page.
3. **Merge the radar PR.** The poller builds the new app. Radar keeps working at `/radar`. The new home page exists but `/` still goes to Streamlit.
4. **Switch instance A**, verify, then **instance B:** change PM2 `briefgen` to the uvicorn command and save; point `location /` at port 3001 and add `location /api/brief/` to port 8501 with a 600s read timeout; remove the Streamlit title and favicon rewrite; `nginx -t` and reload. Seconds per instance.
5. **Verify** in a browser: sign in, generate, open, download PDF, update, delete, Spanish, radar, prefill handoff.
6. **Cleanup PR** once confirmed: delete `app.py`, `.streamlit/`, the `streamlit` requirement; update Dockerfile, README and SETUP.

Between steps 3 and 4 the only gap is cosmetic. Steps 2 to 5 happen in one sitting.

### Rollback

Until the cleanup PR merges: restore the backed-up nginx file and reload, then restart PM2 `briefgen` with the old Streamlit command. Data is untouched either way, since both versions read and write the same table.

### Afterwards

The load balancer no longer needs sticky sessions. They can stay on; nothing depends on them.

## 8. Testing

**Brief API (pytest):** existing suites pass with imports moved to `briefparse`. New tests use FastAPI's test client with an in-memory repository and a stubbed generator: missing header is 401; another user's brief is 404 on get, delete, refresh and PDF; generation emits phases then done and saves once; a recent brief is reused; a language mismatch regenerates; the daily cap and the in-flight guard hold; a failed generation emits an error and saves nothing; PDF returns the right content type and filename.

**Front end:** Vitest for `lib/` (prefill cleaning, stream parsing, score tiers) and the brief view. Playwright with mocked API routes for the generate flow, opening a brief, delete with confirmation, the radar flow and the prefill handoff; screenshots at 320, 768, 1024 and 1440; axe checks; keyboard-only pass; reduced motion.

**On the server:** the preview walkthrough in section 7, then the same checklist after cutover.

There is no local `.env`, so local runs use fixtures and mocked routes. The preview is the first run against real services.

## 9. Delivery phases

| Phase | Output | Checkpoint |
|---|---|---|
| 1. Look first | Design tokens, shell, and the three screens (home, brief, radar) in the Next app on fixture data | Blake reviews screenshots and reacts before anything is wired |
| 2. Brief API | FastAPI alongside Streamlit, parsers extracted, tests; sign-in and admin pages restyled | PR open on CLEAR-brief-gen, tests green |
| 3. Wire it up | Generate with live progress, library, brief page, PDF, update, delete, Spanish; radar restyled in the shell; tests | PR open on alkira-account-radar, tests green |
| 4. Preview | Both branches running privately on one server | Blake walks through it |
| 5. Cutover | Section 7 steps 1 to 5 on both instances | Verified in production |
| 6. Cleanup | Streamlit deleted, docs updated | Merged |

Phases 1 and 2 are independent and run in parallel.

## 10. Out of scope

- **Rotating the admin SSO signing key.** Urgent, tracked separately, and needs the owner of the other eight apps. This project does not change the auth service.
- Sharing a brief with another user. A brief's address works only for its owner.
- Dark theme.
- Streaming the brief text as it is written.
- Changing the deploy poller, or merging the two repos.
- New radar features.

## 11. Assumptions to confirm

1. The shared front end lives in the radar repo's `web/` folder, so that repo's name undersells what it holds.
2. A daily cap of 50 generated briefs per user is acceptable as a default.
3. One or two real test briefs under Blake's email during preview are fine.
4. The sign-in and admin pages are restyled to match but keep their behaviour and stay as static pages.
