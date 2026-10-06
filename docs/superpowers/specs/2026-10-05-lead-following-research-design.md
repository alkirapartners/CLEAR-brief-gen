# Design: research that follows leads, and a brief that judges fit

**Date:** 2026-10-05
**Status:** approved by Blake 2026-10-05, with go-ahead for the full build
**Background:** `docs/handoff-brief-research-depth.md` (constraints, output contract, shipping rules)

## Goal

A partner types a company name and gets a brief that answers "is this an Alkira fit, and what do I attach to?" at the depth of the partner discovery briefs Blake writes by hand in a Claude session. Run time of 2 to 4 minutes is acceptable. Readable by a sales rep and by an engineer.

## What is wrong today (evidence)

- **Fixed searches cannot recover.** Twelve keyword searches run once. Two Anker briefs (2026-08-31 and 2026-10-05) used the same method and returned different junk.
- **No identity step.** The Anker briefs mixed Anker Innovations with Ankercloud, a person named Andrew Anker, and Anker Swiss AG. `research.is_company_relevant` keeps any page containing the token "anker".
- **Weak sources.** Data-broker profiles and content farms instead of the company's own careers site, filings and press releases.
- **The rubric scores evidence volume, not fit**, and the template requires three entry points, so a brief with "no confirmed technical entry point" still presents three.
- **Noise presented as signal.** New executives, ERP projects, headcount statistics, a product recall.

## What was tested (2026-10-05)

Two web-only research runs (search and page reading only, no ZoomInfo), about 25 searches and 20 page reads each, roughly 4.7 and 4.9 minutes untuned:

- **HF Sinclair:** matched Blake's hand-made brief on company facts, the Azure design (ExpressRoute, Virtual WAN hub-and-spoke, SD-WAN, Palo Alto or Fortinet, from a 2026-09-23 posting on the company careers site) and the Lubricants separation. Also found a January 2026 acquisition and plant-network postings the hand-made brief lacks. Did not confirm the CIO or find the network owner.
- **Anker:** resolved the entity (Anker Innovations Technology Co., Changsha, SZSE 300866, HKEX 0668), found AWS since 2017 from AWS case studies, an AWS China (Beijing) to AWS Oregon split joined by Direct Connect (old evidence), and the CIO's name. Excluded Ankercloud.

Findings that shape the design: the best facts came from a second or third search chosen after reading earlier results; the company's own careers site and SEC or exchange filings carried most of the value; search-result summaries merged companies and invented a name, so only opened pages may be cited; named people below the CEO are the gap.

## Fit rules

Written into the knowledge base and the scoring rubric.

**One clear use case is enough.** A customer does not have to check every box. Any single one of these, with evidence, is a fit:

- Multi-cloud or hybrid cloud connectivity, including a cloud network built by hand (ExpressRoute, Direct Connect, Virtual WAN, Transit Gateway hub-and-spoke). Hand-built cloud-native networking is a positive signal, not a negative one. One cloud is enough if the network around it is complex.
- China-to-global connectivity.
- Firewall or security-services consolidation in the cloud.
- M&A: acquisition integration, divestiture, carve-out, transition services agreements.
- MPLS exit, backbone replacement, data-center exit, SD-WAN or SASE programme, or any stated network or infrastructure modernization.
- Sites opening or closing at scale.
- Business-partner or third-party connectivity.

**Supporting only (never an angle on its own):** a cost programme with network contracts in scope; a new CIO or head of infrastructure; a lean network team.

**Never fit evidence:** new CEO or CFO, SAP, Workday or other ERP projects, generic "digital transformation", headcount or hiring statistics, recalls, earnings.

## Scoring

The score reflects the strength and freshness of the best use case, not the number of boxes checked.

| Score | Meaning |
|---|---|
| 5 | A clear use case with first-hand, current evidence and a dated trigger, plus at least one more evidenced use case |
| 4 | One clear use case with first-hand, current evidence |
| 3 | One clear use case whose evidence is older or indirect (Anker's China-to-global AWS split) |
| 2 | A plausible use case with no evidence found |
| 1 | No use case |

A separate "What we couldn't confirm" list keeps "weak fit" apart from "could not find out".

## Pipeline

1. **Identify.** Resolve the legal entity, ticker, HQ and website. Printed on the brief. If the name is ambiguous, choose the most likely entity and say which was chosen.
2. **Research.** A model with web search and page-reading tools works the fit rules under a budget (about 25 searches, 20 pages, and a wall-clock cap of about 4 minutes; when a cap is hit it stops and writes with what it has). Source order: company careers site and job postings, filings and annual report, press releases, cloud-vendor case studies, trade press. Data brokers are last resort and labelled. Output is an evidence list: fact, category, source URL, source date, opened or not. Facts from pages that were not opened are discarded.
3. **Judge and write.** One call scores the fit, keeps the one to three angles that have evidence, matches each to a customer story, and writes the brief from the evidence list only.

**Research tooling decision rule:** use Anthropic's server-side web search and web fetch tools if the production key has them and they can read the PDFs and careers pages in the test set; otherwise run the loop in our code with Tavily search and extract exposed as tools. Confirm capabilities, model IDs (target: Sonnet 5.5) and pricing with the `claude-api` skill as the first task of the plan. Cost per brief is estimated, not measured, at $0.50 to $1.50.

## What a brief contains

- Resolved company name and identifiers; stat row including the cloud and network headline.
- Fit score, verdict and a lead line: what to open with and whom to call.
- **Why this account, why now:** one to three angles. Each has the evidence with its date and source, what Alkira does about it, and a named customer story with its result.
- **Technical snapshot** for engineers: clouds, cloud connectivity, WAN, firewalls, data centers, plant networks. Each line sourced or marked "not found". Keep the specific terms (ExpressRoute, Virtual WAN, BGP, Palo Alto).
- **Who to talk to:** names only from first-hand sources, roles otherwise.
- Three or four questions, each with what to listen for and the Alkira angle. Technical vocabulary is allowed.
- What we couldn't confirm; what would raise the score.
- References (opened pages only).

A one-angle brief (Anker: China-to-global connectivity) uses the same layout with one angle and a shorter question list. It is not padded to three.

## Customer-story matching

`skills/alkira-customer/references/case-studies.md` gains a table tagging each story by situation (M&A, store or site rollout, multi-cloud, China connectivity, firewall consolidation, MPLS exit) and industry. The writer matches by situation first, then industry, and names the customer when the story is public. Add Michaels (1,400 stores in three weeks, before peak season) from `~/Downloads/Alkira-Michaels-Futuriom-v1.3-final-1.pdf`. Only facts in the knowledge base may be cited as proof.

## Storage and display

- New briefs are stored as a JSON document in the existing `brief_md` column (no Supabase schema change). `brief_view` returns the JSON fields directly; a stored value starting with `# ALKIRA OPPORTUNITY BRIEF` is a legacy brief and keeps using `briefparse.py` unchanged. Language is a field in the JSON. `generate.py` validates the JSON against a schema instead of checking the first line. Rejected alternative: more regex-parsed markdown sections, which is the source of the current display bugs.
- `pdf.py` gains a renderer for the new shape; the legacy renderer stays for old briefs.
- Front end (`alkira-account-radar`, `web/`): new detail layout (lead line, angles with customer story, technical snapshot, who to talk to, couldn't-confirm), one-angle layout, updated step text and "takes about three minutes". The five phase strings (`init`, `research`, `analyze`, `compose`, `done`) are kept so `BriefPhase` does not change.

## Limits and safety

- Anthropic client timeout rises from 180 seconds to cover the research budget. PM2 kill timeout for `briefgen` (240 seconds) must rise on both servers over SSH, with Blake's go-ahead.
- Decided by Blake 2026-10-05: the daily cap default drops from 50 to 10 paid generations per person (`settings.DEFAULT_DAILY_LIMIT`; check the environment file on both servers for a `BRIEF_DAILY_LIMIT` override), and the reuse window rises from 7 to 14 days (`max_age_days` in `db.find_recent_brief_by_company` and any UI text that states it).
- Evaluation runs use the production keys in a scratch checkout on a server, so the keys never leave the box. Blake approved SSH access for this on 2026-10-05.
- All fetched text stays inside the random source fence and is treated as data. Briefs are never rendered as HTML.
- Research failure never produces an uncited brief; it returns an error.

## Testing and rollout

- Unit tests with no network: evidence filtering, schema validation, legacy versus new detection, `brief_view`, PDF, case-study table loading. Existing parser tests stay untouched.
- Evaluation set run through `generate_brief.py` before any merge: HF Sinclair, Occidental, Global Payments, Kemper, Anker, UPS, Advance Auto Parts, Southern Glazer's. Blake compares real output with his hand-made briefs. This needs API keys locally or a scratch checkout on a server, either with Blake's go-ahead.
- Two PRs from `feature/*` branches: this repo (API, research, knowledge base, PDF) and `alkira-account-radar` (front end). Merging to `main` deploys within a minute, so the API must serve both legacy and new briefs before the front end changes, and nothing merges without Blake's go-ahead.

## Not in this work

- Paid contact data (ZoomInfo or similar) for named people. Later add-on if Alkira has API access.
- The Account Radar scorer.
- Re-generating existing stored briefs.
