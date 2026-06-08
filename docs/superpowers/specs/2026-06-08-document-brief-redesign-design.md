# Document-Style Brief Redesign — Design

- **Date:** 2026-06-08
- **Status:** Approved (pending spec review)
- **Author:** Blake Hays (with Claude Code)
- **Supersedes (for the brief detail view + PDF only):** the bento rendering decision in [`2026-05-06-bento-brief-pdf-export-design.md`](2026-05-06-bento-brief-pdf-export-design.md). That spec's auth, Streamlit, Supabase, and "content is fixed" decisions still hold.

---

## 1. Problem

The generated brief renders as **7 stacked HTML "bento" tiles** styled by the tile-specific bulk of the 873-line `CUSTOM_CSS` block (`app.py:527–1405`). It's hard to scan:

- Every section wears the same 10px uppercase tile-label, so **nothing reads as more important than anything else** — there's no hierarchy.
- Dense, multi-sentence prose gets crammed into small grid cells (infrastructure cells, entry-point tiles).
- A tall, full-width action-button stack (Download / Update / Delete) pushes the actual brief **below the fold** on load.
- The PDF mirror (`pdf.py`) inherits the tile model and must **truncate content to fit fixed tiles** — it literally drops text ("[continued in full brief]", truncated rationale/infra cells).

The user wants the output to **read like a clean 1–2 page document with defined section headers** — "less boxy" — on screen and in the downloaded PDF.

## 2. Decisions (locked during brainstorming)

1. **Look:** Style **C — "Document + Score Header."** A clean, single-column sans-serif document; the one colored visual anchor is a slim header band with the company name and a navy **fit-score badge**. (Chosen from an interactive A/B/C mockup; A = clean report, B = serif memo, C = document + score header.)
2. **Content:** **Keep the existing brief content and wording** — this is a presentation change only. **No agent-prompt, skill, or research changes.**
3. **PDF:** The downloaded PDF **matches** the new document look.

## 3. Goals / Non-goals

**Goals**
- The brief detail view reads as a clean document: header band + flowing sections with clear heading hierarchy, no tile grid.
- The PDF matches that document look and **never truncates/drops content** (flows across pages).
- Net reduction in rendering code (remove tile parsers, bento HTML, ~700 lines of CSS, and the PDF tile drawers).

**Non-goals**
- No change to the agent, system prompt, skills, research flow, or brief *content/structure*.
- No change to the sidebar brief list, dashboard cards, auth, or the Supabase schema.
- API cost optimization (tracked as a **separate follow-on thread**, see §11).

## 4. Approach

**Chosen: Markdown-driven document (Approach 1).**

The agent already returns the brief as markdown whose `##` headings (`## Infrastructure Snapshot`, `## Signals & Timing`, `## Three Alkira Entry Points`, …) *are* the document's section structure. So we render the body straight from that markdown using the **existing** `md_to_html` (`app.py:386`) + `inline` (`app.py:508`), and special-case only the **header band** (company + stats + score badge) using the parsers we already have (`extract_score`:148, `extract_company_header`:169 — the score is also persisted to the DB, so these stay regardless).

**Alternative considered — Restyle in place (Approach 2):** keep every `extract_*` parser and just swap tile HTML/CSS for document HTML/CSS. Rejected as the default because it preserves the fragile regex parsing and PDF truncation math and is more code to maintain, for per-field styling control we don't need (the markdown's existing bold labels render the Signal/Solution/Proof lines fine, as confirmed in the mockup).

## 5. Visual spec — Style C

**Header band** (the only colored region):
- Left: company name (h1, ~28px/800, ink `#15233b`) + stats line (~12.5px, muted `#8b94a6`), pipe/▪-separated (HQ · Revenue · Employees · Industry · Markets · Ownership).
- Right: a **navy score badge** — rounded square, background Alkira navy `#0A1F44`, white text: small "FIT" label + large `n/5`.
- A 2px bottom rule separates the band from the body.

**Body** (`.brief-doc` document):
- Font: Inter (already loaded via Google Fonts `@import`). Body ~14.5px / line-height 1.65, ink `#33415c`.
- Section headers (from markdown `##`): ~12px uppercase, letter-spacing, ink, with a 1px hairline bottom rule and generous top margin.
- Lead paragraph = the fit-score **rationale** (the redundant `Alkira Fit Score: n/5` line is stripped from the flowed body since the badge shows it).
- Lists render as normal `<ul>/<ol>`; references render as small muted text.

**Tokens / palette** (reuse existing): Alkira blue `#2D58F2`, navy `#0A1F44`, ink `#15233b`/`#211F1F`, muted greys, border `#e6e9f0`. PDF uses the matching RGB tuples already defined at the top of `pdf.py`.

The reviewed interactive mockup lives at `.superpowers/brainstorm/<session>/content/document-styles.html` (style C) — gitignored, for reference only.

## 6. Architecture & changes

### 6.1 On-page — `app.py`
- **New** `render_brief_document(brief_md, ...)` replaces `render_brief_bento` (1620):
  1. Header band: `extract_company_header` + `extract_score` → company, stats, badge.
  2. Body: drop the `Alkira Fit Score:` line, surface its rationale as the lead paragraph, then `md_to_html(get_brief_body(...))` inside a `.brief-doc` wrapper.
- **Condense the action row:** collapse the full-width Download / Update / Delete stack into one slim toolbar directly under the header band so the brief is not pushed below the fold. (`_render_download_pdf_button`:1759 and the delete/update controls.)
- **`CUSTOM_CSS` (527–~1405):** remove tile/bento/`infra-grid`/`row3`/`entry`/score-tile rules; add the compact `.brief-doc` + header-band + score-badge styles. **Keep** shared chrome (logo, sidebar, dashboard cards, buttons, step tracker).
- **Retire** (and delete tests that pin tile structure): `extract_infra_cells` (295), `extract_entry_points` (232), `_format_starters_text` (1598), and `extract_exec_snippet` (333) if unused after this change. Keep `extract_section` (195) — the PDF section walker can reuse it, or it can be removed if fully unused.

### 6.2 PDF — `pdf.py`
- **Keep** `_BriefPDF` (branded header/footer + page numbers), `build_filename`, `_safe_text`, `_strip_md`.
- **Evolve** `_draw_hero` (183) into the **header band**: company + stats + navy score badge (a filled rounded rect + white "FIT n/5"), replacing `_draw_score_tile` (207).
- **Add** one generic `_draw_section(pdf, title, md_body)` that flows: section heading (bold, branded) → paragraphs/bullets via `multi_cell`, relying on fpdf2 **auto page-break** (already enabled, margin 18) so content never truncates.
- **Remove** `_draw_score_tile`, `_draw_infra_grid`, `_draw_entry_points`, `_draw_conversation_starters` and their per-tile truncation math. `_draw_signals`/`_draw_references` fold into `_draw_section`.
- **Simplify** `generate_brief_pdf` (554): parse header (company/score), draw the header band, then walk the brief's sections in document order through `_draw_section`.

## 7. Data flow

```
brief_md (markdown, from DB / fresh generation)
   ├─ extract_company_header → (company, stats_line) ─┐
   ├─ extract_score          → (score, rationale)    ├─► HEADER BAND  (web + PDF)
   └─ get_brief_body / sections ──────────────────────┘
                                   │
              web:  md_to_html(body) → .brief-doc HTML
              pdf:  walk sections → _draw_section (flowing, paginated)
```

Single source of truth = the brief markdown. Both renderers consume the same parsed header + the same section markdown — no divergent per-tile models.

## 8. Error handling — missing/partial sections

The brief markdown may omit a section (sparse company). Document rendering degrades naturally: a missing `##` heading simply doesn't appear — **no empty "No data available" tiles**. If the score can't be parsed, the badge shows the DB-stored score (fallback already exists). If the company header is missing, fall back to the user-entered name (as today).

## 9. Removed surface (simplification win)

- `app.py`: `extract_infra_cells`, `extract_entry_points`, `_format_starters_text`, the bento HTML in `render_brief_bento`, and the tile-specific bulk of `CUSTOM_CSS`.
- `pdf.py`: 4 tile drawers + all truncation math.
- Net: less code, fewer regexes, no dropped PDF content.

## 10. Testing

- Keep `tests/test_parsers.py` coverage for `extract_score` + `extract_company_header`; remove tests that assert tile-specific parsing (`extract_entry_points`/`extract_infra_cells`) as those functions are retired.
- Add a render test: a sample brief → header band present (company + `n/5`) + section headers present; **missing section is omitted, not errored.**
- Add a PDF smoke test: a long multi-section brief produces a multi-page PDF with **no truncation markers** and no exceptions; a sparse brief still renders.
- Manual visual check at 320 / 768 / 1024 / 1440 widths (per web testing rules) and a downloaded PDF.

## 11. Follow-on (separate thread): API cost

Out of scope here, tracked separately. Current model is **Sonnet 4.6** (`setup_agent.py:48`), ~$0.50/brief observed via Managed Agents. First step will be **instrumentation** (log per-brief `usage`: input/output/cache read+write/web-search count) so tuning isn't blind; then levers — cap/tighten web searches, A/B **Haiku 4.5** (3× cheaper tokens), and dedup repeat-company generations. Will get its own spec.

## 12. Open questions

- None blocking. Optional: a refined full-fidelity Style-C preview (with the condensed toolbar) before implementation — offered, not required.
