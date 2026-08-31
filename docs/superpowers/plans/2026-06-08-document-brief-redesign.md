# Document-Style Brief Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-render the brief as a clean single-column document (Style C: header band + navy fit-score badge + flowing sections) on screen and in the PDF — presentation only, no content/agent changes.

**Architecture:** Reuse the existing markdown→document pipeline (`md_to_html` + the `.brief-doc` CSS). A new pure function builds the full document HTML (header band + lead rationale + body); the renderer wraps it with a slim action toolbar. `get_brief_body` (currently unused) is hardened to robustly strip the title/company/score and return the section body regardless of `##`/`###` heading level. The PDF replaces its tile drawers with a header band + one generic section walker (auto page-break, no truncation). Dead tile parsers/CSS are removed last, grep-verified.

**Tech Stack:** Python 3.11, Streamlit 1.51, fpdf2 2.8.7, pytest.

**Spec:** [`docs/superpowers/specs/2026-06-08-document-brief-redesign-design.md`](../specs/2026-06-08-document-brief-redesign-design.md)

**Branch:** `feature/document-brief-redesign` (already created off `origin/main`).

---

## Environment & repo facts (verified)

- No virtualenv; deps are global (streamlit 1.51.0, fpdf2 2.8.7). **pytest is NOT installed** — Task 0 installs it.
- Tests are pytest-style (plain functions + `assert`). Run with `python3 -m pytest`.
- `tests/test_pdf.py` ALREADY EXISTS (tests `build_filename`, `_safe_text`, `ALKIRA_BLUE`, and `generate_brief_pdf` smoke/full). The PDF rewrite must keep these green and APPEND new tests — do not recreate the file.
- `tests/test_parsers.py` tests ONLY `extract_entry_points`/`extract_infra_cells` and imports them at module scope — removing those functions breaks its import, so Task 5 REPLACES the file's contents.
- Authoritative brief structure (`skills/alkira-brief-template/SKILL.md`): `# ALKIRA OPPORTUNITY BRIEF` (H1) → `## [Company]` (H2) + stats line → `**Alkira Fit Score: X / 5**` + 3-4 sentence rationale (no heading) → sections (Infrastructure Snapshot, Signals & Timing, Three Alkira Entry Points, Conversation Starters, References) → `*CONFIDENTIAL*`. The section heading level (`##` vs `###`) is NOT strictly pinned, so the renderer must handle both.

## Reference: functions (current line numbers in `app.py` / `pdf.py`)

Reused as-is: `extract_score` (app.py:148→`(int,str)`), `extract_company_header` (169→`(company,stats)`), `md_to_html` (386), `inline` (508).
Hardened: `get_brief_body` (359) — currently unused (no callers; verify with grep), rewritten to be heading-level robust.
Replaced: `render_brief_bento` (1620), alias `render_brief_display` (1794). Call sites: 2046, 2101, 2154 (all via the alias).
Removed in cleanup: `extract_infra_cells` (295), `extract_entry_points` (232), `EntryPoint` (206), `_label_pattern` (214), `_grab` (227), `_format_starters_text` (1598), plus dead tile CSS.
PDF replaced: tile drawers (`_draw_hero` 183, `_draw_score_tile` 207, `_draw_infra_grid` 267, `_draw_signals` 327, `_draw_references` 357, `_draw_entry_points` 386, `_draw_conversation_starters` 479); `generate_brief_pdf` (554) rewritten. Kept: `_BriefPDF`, `build_filename`, `_safe_text`, `_strip_md`.

Design tokens in `:root` (app.py:531): `--alkira-blue #2D58F2`, `--alkira-navy #0A1F44`, `--alkira-ink #211F1F`, `--alkira-muted #7F7F7F`, `--alkira-border #e0e7ff`. PDF RGB mirrors at top of `pdf.py`.

## File structure

- `app.py` — harden `get_brief_body`; add `build_brief_document_html` (pure) + `render_brief_document` (replaces `render_brief_bento`); add Style-C CSS; remove dead tile code/CSS.
- `pdf.py` — add `_iter_sections`, `_draw_header_band`, `_draw_section`; rewrite `generate_brief_pdf`; remove tile drawers.
- `tests/test_render.py` — NEW: unit tests for `get_brief_body` + `build_brief_document_html` + CSS guard.
- `tests/test_pdf.py` — APPEND tests for `_iter_sections` + long/sparse PDF; keep existing tests passing.
- `tests/test_parsers.py` — REPLACE contents with tests for retained parsers (`extract_score`, `extract_company_header`, `get_brief_body`).

---

## Task 0: Environment + green baseline

**Files:** none (setup/verification)

- [ ] **Step 1: Install pytest into the active Python environment**

Run: `python3 -m pip install pytest`
Expected: pytest installs (or "already satisfied").

- [ ] **Step 2: Run the existing suite from the repo root**

Run: `python3 -m pytest tests/ -v`
Expected: collects `test_parsers.py`, `test_pdf.py`, `test_db.py`, `test_notifications.py` and they PASS (green). If `test_db.py`/`test_notifications.py` fail for environment reasons unrelated to this work (e.g. missing Supabase/Slack env), note them and scope this work to `test_render.py`/`test_pdf.py`/`test_parsers.py`. Do not start on a red baseline for the files we touch.

---

## Task 1: Harden `get_brief_body` + add pure `build_brief_document_html`

**Files:**
- Modify: `app.py` — rewrite `get_brief_body` (359–381); add `build_brief_document_html` just above `render_brief_bento` (~1619)
- Test: `tests/test_render.py` (create)

- [ ] **Step 1: Confirm `get_brief_body` has no other callers (safe to rewrite)**

Run: `grep -rn "get_brief_body" app.py pdf.py tests/`
Expected: only its definition in `app.py`. (If any caller exists, preserve its expected behavior.)

- [ ] **Step 2: Write the failing tests**

Create `tests/test_render.py`:

```python
from app import get_brief_body, build_brief_document_html, CUSTOM_CSS

SAMPLE = """# ALKIRA OPPORTUNITY BRIEF
*June 2026*

## Halverson Freight Group
**HQ:** Memphis, TN | **Revenue:** $2.1B | **Employees:** 8,500

**Alkira Fit Score: 4 / 5**
Active multicloud migration after two 2025 acquisitions and a legacy MPLS backbone.

### Infrastructure Snapshot
- **Cloud Platforms:** AWS (confirmed), Azure (confirmed)
- **On-Prem / Hybrid:** Two data centers + VMware

### Signals & Timing
- Closed Cole Cartage acquisition (Jan 2025)

### Three Alkira Entry Points
**1. Multicloud Networking**
- Signal: Two clouds inherited via M&A
- Solution: Alkira unifies AWS + Azure
- Proof: 96% faster connection

### Conversation Starters
1. How are you connecting Azure to AWS today?
2. What is your appetite for moving off MPLS?

### References
[1] HFG Q1 2026 earnings call — https://example.com/hfg

*CONFIDENTIAL*
"""

# ── get_brief_body ──
def test_body_excludes_title_company_and_score():
    body = get_brief_body(SAMPLE)
    assert "Infrastructure Snapshot" in body
    assert "Halverson Freight Group" not in body   # company header excluded
    assert "Alkira Fit Score" not in body          # score line excluded
    assert "ALKIRA OPPORTUNITY BRIEF" not in body  # title excluded
    assert "CONFIDENTIAL" not in body              # footer excluded

def test_body_handles_h2_section_headings():
    body = get_brief_body(SAMPLE.replace("### ", "## "))
    assert "Infrastructure Snapshot" in body
    assert "Halverson Freight Group" not in body

def test_body_empty_input():
    assert get_brief_body("") == ""

# ── build_brief_document_html ──
def test_document_has_header_band_company_and_badge():
    html = build_brief_document_html(SAMPLE)
    assert "brief-header-band" in html
    assert "Halverson Freight Group" in html
    assert "brief-score-badge" in html
    assert ">4<" in html  # score numeral in badge

def test_document_does_not_duplicate_company_or_score():
    html = build_brief_document_html(SAMPLE)
    assert html.count("Halverson Freight Group") == 1   # only in the header band
    assert "Alkira Fit Score:" not in html              # badge shows it; not re-rendered

def test_document_leads_with_score_rationale():
    html = build_brief_document_html(SAMPLE)
    assert "brief-lead" in html
    assert "multicloud migration" in html

def test_document_renders_sections_not_tiles():
    html = build_brief_document_html(SAMPLE)
    assert "Infrastructure Snapshot" in html
    assert "Conversation Starters" in html
    assert 'class="tile' not in html
    assert "brief-doc" in html

def test_missing_section_omitted_not_errored():
    sparse = """# ALKIRA OPPORTUNITY BRIEF

## Tiny Co
**HQ:** Nowhere

**Alkira Fit Score: 2 / 5**
Little public infrastructure detail.

### Signals & Timing
- Quiet company

*CONFIDENTIAL*
"""
    html = build_brief_document_html(sparse)
    assert "Tiny Co" in html
    assert "Infrastructure Snapshot" not in html
    assert "No data" not in html

def test_empty_input_does_not_crash():
    assert "brief-doc" in build_brief_document_html("")

def test_meta_right_included():
    assert "Generated in 42s" in build_brief_document_html(SAMPLE, meta_right="Generated in 42s")
```

- [ ] **Step 3: Run to verify failure**

Run: `python3 -m pytest tests/test_render.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_brief_document_html'`.

- [ ] **Step 4: Harden `get_brief_body`**

Replace `get_brief_body` (app.py:359–381) with:

```python
def get_brief_body(brief: str) -> str:
    """Return the brief body: the first ## / ### section after the Fit Score line,
    through (but excluding) the CONFIDENTIAL footer.

    Excludes the title, company header, and the score line/rationale, which are
    rendered separately. Robust to both ## and ### section heading levels.
    """
    score = re.search(r"\*?\*?Alkira Fit Score:\s*\d\s*/\s*5\*?\*?", brief)
    if score:
        base = score.end()
        m = re.search(r"(?m)^\s*#{2,3}\s+\S.*$", brief[base:])
        start = base + m.start() if m else None
    else:
        # No score line: the first heading is the company header; take the second.
        heads = list(re.finditer(r"(?m)^\s*#{2,3}\s+\S.*$", brief))
        start = heads[1].start() if len(heads) > 1 else None
    if start is None:
        return ""
    end = len(brief)
    for marker in ("*CONFIDENTIAL*", "CONFIDENTIAL"):
        ei = brief.find(marker, start)
        if ei != -1:
            end = min(end, ei)
    return brief[start:end].strip()
```

- [ ] **Step 5: Add `build_brief_document_html`**

In `app.py`, add immediately above `def render_brief_bento(` (~line 1619):

```python
def build_brief_document_html(brief_md: str, meta_right: str = "") -> str:
    """Build the full document HTML for a brief: header band + lead rationale + body.

    Pure (no Streamlit side effects) so it is unit-testable. Reuses md_to_html for the
    body; the score badge and company header are the only special-cased pieces. Missing
    sections simply don't appear, and the company/score are never duplicated in the body
    (get_brief_body strips everything up to the first section after the score line).
    """
    score, reasoning = extract_score(brief_md)
    company, stats_line = extract_company_header(brief_md)
    cleaned_stats = (stats_line or "").replace("**", "").strip()

    badge = (
        f'<div class="brief-score-badge">'
        f'<span class="bsb-label">Fit</span>'
        f'<span class="bsb-num">{score}<span class="bsb-den">/5</span></span>'
        f'</div>'
    ) if score else ""

    meta = (
        f'<span class="brief-band-meta">{html.escape(meta_right)}</span>'
        if meta_right else ""
    )

    header = (
        f'<div class="brief-header-band">'
        f'<div class="brief-band-main">'
        f'<h1 class="brief-company">{html.escape(company or "Brief")}</h1>'
        f'<p class="brief-stats">{html.escape(cleaned_stats)}{meta}</p>'
        f'</div>'
        f'{badge}'
        f'</div>'
    )

    lead = f'<p class="brief-lead">{inline(reasoning)}</p>' if reasoning else ""
    body_html = md_to_html(get_brief_body(brief_md))

    return f'<div class="brief-doc">{header}{lead}{body_html}</div>'
```

- [ ] **Step 6: Run to verify pass**

Run: `python3 -m pytest tests/test_render.py -v`
Expected: PASS (11 passed).

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_render.py
git commit -m "feat(brief): robust get_brief_body + pure document HTML builder"
```

---

## Task 2: Style-C CSS — header band, score badge, lead, unified section headers

**Files:**
- Modify: `app.py` — `CUSTOM_CSS`: append after `.brief-doc .confidential { ... }` (~line 1095)
- Test: `tests/test_render.py` (guard test already imports `CUSTOM_CSS`)

- [ ] **Step 1: Write the failing guard test**

Append to `tests/test_render.py`:

```python
def test_custom_css_defines_style_c_classes():
    for cls in (".brief-header-band", ".brief-score-badge", ".brief-lead", ".bsb-num"):
        assert cls in CUSTOM_CSS
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_render.py::test_custom_css_defines_style_c_classes -v`
Expected: FAIL.

- [ ] **Step 3: Add the CSS**

In `app.py`, find the end of `.brief-doc .confidential { ... }` (~line 1095, inside `CUSTOM_CSS`) and insert after it (still inside `<style>`):

```css
    /* ── Style C: document header band + score badge ── */
    .brief-header-band {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 18px;
        padding-bottom: 14px;
        margin-bottom: 18px;
        border-bottom: 2px solid var(--alkira-border);
    }
    .brief-band-main { min-width: 0; }
    .brief-company {
        margin: 0 0 4px;
        font-size: 26px;
        font-weight: 800;
        color: var(--alkira-ink);
        letter-spacing: -0.01em;
    }
    .brief-stats { margin: 0; font-size: 12.5px; color: var(--alkira-muted); }
    .brief-band-meta { margin-left: 8px; font-style: italic; color: var(--alkira-muted); }
    .brief-score-badge {
        flex: none;
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        width: 74px; height: 74px;
        border-radius: 14px;
        background: var(--alkira-navy);
        color: #fff;
    }
    .bsb-label { font-size: 10px; letter-spacing: 0.14em; text-transform: uppercase; color: #9fb0d6; }
    .bsb-num { font-size: 24px; font-weight: 800; line-height: 1; margin-top: 2px; }
    .bsb-den { font-size: 13px; font-weight: 600; color: #9fb0d6; }
    .brief-doc .brief-lead { font-size: 14.5px; color: #3a465e; margin: 0 0 1rem; }

    /* Unify ## (h2) and ### (.sec) section headers as document headers, since the
       agent's heading level is not strictly pinned. */
    .brief-doc h2,
    .brief-doc .sec {
        margin: 1.5rem 0 0.55rem;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid var(--alkira-border);
    }
    .brief-doc h2 {
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #152a4e;
        font-weight: 700;
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_render.py -v`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_render.py
git commit -m "feat(brief): Style-C header band, score badge, unified section headers"
```

---

## Task 3: Swap renderer to `render_brief_document` with a slim toolbar

**Files:**
- Modify: `app.py` — replace `render_brief_bento` (1620–1756); update alias (1794)

- [ ] **Step 1: Replace the function**

Delete the entire `render_brief_bento` body (1620 → end of the References block ~1756) and replace with:

```python
def render_brief_document(
    brief_md: str,
    meta_right: str = "",
    show_update: bool = False,
    brief_idx: int | None = None,
) -> None:
    """Render a brief as a clean single-column document (Style C).

    A slim 3-column action toolbar (Download / Update / Delete) sits above the
    document instead of the old stacked full-width buttons that pushed content
    below the fold.
    """
    score, _ = extract_score(brief_md)
    company, _ = extract_company_header(brief_md)

    c1, c2, c3 = st.columns(3)
    with c1:
        _render_download_pdf_button(brief_md, company or "Brief", score)
    with c2:
        if show_update and company:
            if st.button("Update Brief", key="update_brief", use_container_width=True):
                st.session_state["_update_company"] = company
                st.rerun()
    with c3:
        if brief_idx is not None:
            st.markdown(
                f'<a class="delete-brief-link" href="?_del={brief_idx}">Delete Brief</a>',
                unsafe_allow_html=True,
            )

    st.markdown(build_brief_document_html(brief_md, meta_right), unsafe_allow_html=True)
```

- [ ] **Step 2: Update the alias** (was `render_brief_display = render_brief_bento`, ~1794):

```python
# Public entry point for rendering a brief (keeps call sites stable)
render_brief_display = render_brief_document
```

- [ ] **Step 3: Verify import + alias (parsers still defined; cleanup is Task 5)**

Run: `python3 -c "import app; assert app.render_brief_display is app.render_brief_document; print('ok')"`
Expected: prints `ok` (no ImportError — the now-dead parsers still exist at this point).

- [ ] **Step 4: Render tests still green**

Run: `python3 -m pytest tests/test_render.py -v`
Expected: PASS (12 passed).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat(brief): render brief as document with slim action toolbar"
```

---

## Task 4: PDF — header band + generic section walker (no truncation)

Reuses the now-hardened `get_brief_body`. Replaces all tile drawers with a header band + one `_draw_section`.

**Files:**
- Modify: `pdf.py` — add `_iter_sections`, `_draw_header_band`, `_draw_section`; rewrite `generate_brief_pdf` (554); delete tile drawers
- Test: `tests/test_pdf.py` (APPEND — file already exists; keep existing tests passing)

- [ ] **Step 1: Append the failing tests to the EXISTING `tests/test_pdf.py`**

Append (do not recreate the file; `SAMPLE_FULL_BRIEF` already exists there — use a new name):

```python
from pdf import _iter_sections

def test_iter_sections_splits_in_order():
    assert _iter_sections("### One\nalpha\n\n### Two\nbeta\n") == [("One", "alpha"), ("Two", "beta")]

def test_iter_sections_handles_h2():
    assert _iter_sections("## A\nx\n## B\ny\n") == [("A", "x"), ("B", "y")]

def test_iter_sections_empty():
    assert _iter_sections("") == []

def test_generate_pdf_long_brief_no_crash():
    long_brief = SAMPLE_FULL_BRIEF + "\n".join(
        f"## Section {i}\n" + ("Long paragraph of content. " * 40) for i in range(15)
    )
    out = generate_brief_pdf(long_brief, "Big Co", 5, datetime(2026, 6, 8))
    assert bytes(out[:5]) == b"%PDF-"

def test_generate_pdf_sparse_brief_no_crash():
    sparse = "# ALKIRA OPPORTUNITY BRIEF\n\n## Tiny Co\n\n**Alkira Fit Score: 1 / 5**\nThin.\n\n*CONFIDENTIAL*\n"
    out = generate_brief_pdf(sparse, "Tiny Co", 1, datetime(2026, 6, 8))
    assert bytes(out[:5]) == b"%PDF-"
```

> `from pdf import generate_brief_pdf` and `from datetime import datetime` are already imported at the top of the existing file; add `generate_brief_pdf` to the top import if it's currently imported lazily inside functions.

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_pdf.py -v`
Expected: FAIL — `ImportError: cannot import name '_iter_sections'`.

- [ ] **Step 3: Add the section splitter** (in `pdf.py`, after `_strip_md`, ~line 102):

```python
def _iter_sections(body_md: str) -> list[tuple[str, str]]:
    """Split brief body markdown into (heading, body) pairs by ## / ### headings, in order."""
    parts = re.split(r"(?m)^\s*#{2,3}\s+(.+?)\s*$", body_md)
    out: list[tuple[str, str]] = []
    it = iter(parts[1:])  # parts[0] is any pre-heading text; ignore it
    for title in it:
        body = next(it, "")
        out.append((title.strip(), body.strip()))
    return out
```

- [ ] **Step 4: Replace `_draw_hero` (183–201) with the header band** (fpdf2 is 2.8.7, so rounded corners are available):

```python
def _draw_header_band(pdf: "_BriefPDF", company: str, stats_line: str, score: int) -> None:
    """Company + stats (left) with a navy fit-score badge (right), then a rule."""
    top = pdf.get_y()
    badge = 22.0  # mm

    pdf.set_xy(12.7, top)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*ALKIRA_INK)
    pdf.multi_cell(190.5 - badge - 6, 8, _safe_text(company) or "Untitled Brief")

    pdf.set_x(12.7)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ALKIRA_MUTED)
    cleaned = (stats_line or "").replace("**", "").strip()
    if cleaned:
        pdf.multi_cell(190.5 - badge - 6, 5, _safe_text(_strip_md(cleaned)))

    if score:
        bx, by = 215.9 - 12.7 - badge, top
        pdf.set_fill_color(*ALKIRA_NAVY)
        pdf.rect(bx, by, badge, badge, style="F", round_corners=True, corner_radius=3)
        pdf.set_xy(bx, by + 4)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(badge, 3, "FIT", align="C")
        pdf.set_xy(bx, by + 9)
        pdf.set_font("Helvetica", "B", 15)
        pdf.cell(badge, 8, f"{max(1, min(5, score))}/5", align="C")

    pdf.set_y(max(pdf.get_y(), top + badge) + 3)
    pdf.set_draw_color(*ALKIRA_BORDER)
    pdf.set_line_width(0.4)
    pdf.line(12.7, pdf.get_y(), 215.9 - 12.7, pdf.get_y())
    pdf.ln(4)
```

- [ ] **Step 5: Add the generic section drawer:**

```python
def _draw_section(pdf: "_BriefPDF", title: str, body_md: str) -> None:
    """Draw one document section: heading + flowing paragraphs/bullets (auto page-break)."""
    if not title and not body_md.strip():
        return
    pdf.ln(2)
    pdf.set_x(12.7)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*ALKIRA_BLUE)
    pdf.multi_cell(0, 6, _safe_text(_strip_md(title)))
    pdf.set_draw_color(*ALKIRA_BORDER)
    pdf.set_line_width(0.2)
    pdf.line(12.7, pdf.get_y(), 215.9 - 12.7, pdf.get_y())
    pdf.ln(1.5)

    for raw in body_md.splitlines():
        line = raw.strip()
        if not line or line in ("---", "***", "___"):
            continue
        if re.match(r"^\*\*.+\*\*$", line):  # bold sub-heading e.g. **1. Multicloud**
            pdf.set_x(12.7)
            pdf.set_font("Helvetica", "B", 9.5)
            pdf.set_text_color(*ALKIRA_INK)
            pdf.multi_cell(0, 5, _safe_text(_strip_md(line)))
            continue
        bullet = bool(re.match(r"^[-*]\s+", line))
        text = _strip_md(re.sub(r"^[-*]\s+", "", line) if bullet else line)
        if not text:
            continue
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*ALKIRA_INK)
        if bullet:
            pdf.set_x(15)
            pdf.cell(3, 4.6, "-")
            pdf.multi_cell(190.5 - 5, 4.6, _safe_text(text))
        else:
            pdf.set_x(12.7)
            pdf.multi_cell(0, 4.8, _safe_text(text))
        pdf.ln(0.6)
```

- [ ] **Step 6: Rewrite `generate_brief_pdf` (554–613) and delete the tile drawers**

```python
def generate_brief_pdf(
    brief_md: str,
    company: str,
    score: int,
    generated_at: datetime | None = None,
) -> bytes:
    """Render brief markdown as a print-optimized document PDF. Returns PDF bytes."""
    when = generated_at or datetime.now()
    pdf = _BriefPDF(generated_at=when)
    pdf.add_page()

    from app import extract_company_header, extract_score, get_brief_body
    company_name, stats_line = extract_company_header(brief_md)
    if not company_name:
        company_name = company
    parsed_score, rationale = extract_score(brief_md)
    if not parsed_score:
        parsed_score = score

    _draw_header_band(pdf, company_name, stats_line, parsed_score)

    if rationale:
        pdf.set_x(12.7)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*ALKIRA_INK)
        pdf.multi_cell(0, 5, _safe_text(_strip_md(rationale)))
        pdf.ln(1)

    for title, body in _iter_sections(get_brief_body(brief_md)):
        _draw_section(pdf, title, body)

    return bytes(pdf.output())
```

Then DELETE these now-unused functions from `pdf.py`: `_draw_score_tile`, `_draw_infra_grid`, `_draw_signals`, `_draw_references`, `_draw_entry_points`, `_draw_conversation_starters` (and the old `_draw_hero`, replaced in Step 4).

- [ ] **Step 7: Run the PDF tests (new + existing all green)**

Run: `python3 -m pytest tests/test_pdf.py -v`
Expected: PASS — existing `build_filename`/`_safe_text`/`generate_brief_pdf`/`test_full_brief_renders` still pass (the contract "returns valid `%PDF` bytes" holds) AND the 5 new tests pass.

- [ ] **Step 8: Commit**

```bash
git add pdf.py tests/test_pdf.py
git commit -m "feat(pdf): render brief as flowing document, drop tile truncation"
```

---

## Task 5: Cleanup — remove dead tile parsers, CSS, and repurpose test_parsers.py

**Files:**
- Modify: `app.py` (remove dead parsers + dead CSS); `tests/test_parsers.py` (replace contents)

- [ ] **Step 1: Confirm the dead symbols have no remaining references in live code**

Run:
```bash
grep -n "extract_infra_cells\|extract_entry_points\|_format_starters_text\|EntryPoint\|_label_pattern\|_grab\|render_brief_bento\|extract_exec_snippet\|extract_section" app.py pdf.py
```
Expected: matches ONLY at definitions. Any symbol that ALSO appears in live code (e.g. `extract_exec_snippet`/`extract_section` used by `_render_dashboard_cards`) MUST be kept — triage every non-definition hit before deleting.

- [ ] **Step 2: Delete the dead parsers in `app.py`**

Remove (verified unreferenced in Step 1): `extract_entry_points` (232–293), `extract_infra_cells` (295–331), `class EntryPoint` (206–212), `_label_pattern` (214–225), `_grab` (227–230), `_format_starters_text` (1598–1617). Remove `extract_exec_snippet` and `extract_section` ONLY if Step 1 showed no live references; otherwise keep them.

- [ ] **Step 3: Remove dead tile CSS in `CUSTOM_CSS`**

Delete the rule blocks for the now-unused tile classes — `.bento-grid` (~848), `.row3` (~857), `.infra-grid` (~863), `.tile` and variants (`.tile.full/.gradient/.dark/.entry`), `.tile-label`, `.tile-value`, `.score-big`, `.score-stars-bento`, `.score-rationale`, `.entry-heading`, `.entry-row`, and the `.tile .brief-doc` / `.tile.dark .brief-doc ...` overrides (~922–948). KEEP `.brief-doc*` (now the main brief container), `.dash-card*`, `.sb-*`, `a.delete-brief-link`, and all global/sidebar rules. Before deleting each class, run `grep -n '<class>' app.py` to confirm it is not used outside the deleted render code.

- [ ] **Step 4: Replace `tests/test_parsers.py` contents** (it currently imports the removed functions at module scope)

Overwrite the whole file with tests for the RETAINED parsers:

```python
"""Tests for retained brief markdown parsers."""

from app import extract_score, extract_company_header, get_brief_body

BRIEF = """# ALKIRA OPPORTUNITY BRIEF

## Halverson Freight Group
**HQ:** Memphis, TN | **Revenue:** $2.1B

**Alkira Fit Score: 4 / 5**
Strong multicloud fit with active migration.

### Infrastructure Snapshot
- **Cloud Platforms:** AWS, Azure

*CONFIDENTIAL*
"""

def test_extract_score_value_and_reasoning():
    score, reasoning = extract_score(BRIEF)
    assert score == 4
    assert "multicloud" in reasoning

def test_extract_score_missing():
    score, reasoning = extract_score("# No score here")
    assert score == 0
    assert reasoning == ""

def test_extract_company_header():
    company, stats = extract_company_header(BRIEF)
    assert company == "Halverson Freight Group"
    assert "Memphis" in stats
    assert "**" not in stats

def test_get_brief_body_strips_header_and_score():
    body = get_brief_body(BRIEF)
    assert "Infrastructure Snapshot" in body
    assert "Halverson Freight Group" not in body
    assert "Alkira Fit Score" not in body
```

- [ ] **Step 5: Verify import + full suite**

Run:
```bash
python3 -c "import app, pdf; print('import ok')"
python3 -m pytest tests/ -v
```
Expected: `import ok`, then all tests PASS (no `NameError`/`ImportError` from a missed reference).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_parsers.py
git commit -m "refactor(brief): remove dead bento tile parsers, CSS, repurpose parser tests"
```

---

## Task 6: Visual + PDF verification (manual)

**Files:** none

- [ ] **Step 1: Run the app** — `streamlit run app.py` (auth-gated; use the local `auth_email` path per `SETUP.md`). Open an existing brief.
- [ ] **Step 2: On-screen document** — header band (company + stats + navy FIT n/5 badge), slim 3-button toolbar (not stacked), flowing sections with clear headers, no tile grid, brief visible without scrolling past a button stack.
- [ ] **Step 3: Responsive** — at 320 / 768 / 1024 / 1440 px: no horizontal overflow; header band wraps gracefully (badge intact).
- [ ] **Step 4: PDF** — Download PDF: header band + badge, sections flow across pages, NO "[continued in full brief]"/truncated text, multi-page renders fully.
- [ ] **Step 5: Sparse brief** — view/generate a brief missing a section: it is simply absent on screen and in PDF — no "No data" box, no crash.
- [ ] **Step 6: Commit any polish**

```bash
git add -A && git commit -m "fix(brief): visual polish from document redesign verification"
```

---

## Definition of done

- Brief renders as Style-C document on screen and in PDF; no tiles.
- `python3 -m pytest tests/ -v` green (existing + new).
- Dead tile parsers/CSS removed; `import app, pdf` clean.
- PDF no longer truncates; sparse briefs degrade gracefully; company/score not duplicated in the body.
- Agent prompt, skills, brief content, sidebar/dashboard, auth, and DB schema unchanged.
