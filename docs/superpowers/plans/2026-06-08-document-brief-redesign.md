# Document-Style Brief Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-render the brief as a clean single-column document (Style C: header band + navy fit-score badge + flowing sections) on screen and in the PDF — presentation only, no content/agent changes.

**Architecture:** Reuse the existing markdown→document pipeline (`md_to_html` + the `.brief-doc` CSS block). A new pure function builds the full document HTML (header band + lead rationale + body); the renderer wraps it with a slim action toolbar. The PDF replaces its tile drawers with a header band + one generic section walker (auto page-break, no truncation). Dead tile parsers/CSS are removed last, grep-verified.

**Tech Stack:** Python 3, Streamlit, fpdf2, pytest.

**Spec:** [`docs/superpowers/specs/2026-06-08-document-brief-redesign-design.md`](../specs/2026-06-08-document-brief-redesign-design.md)

**Branch:** `feature/document-brief-redesign` (already created off `origin/main`).

---

## Reference: functions involved (current line numbers in `app.py` / `pdf.py`)

Reusable as-is: `extract_score` (app.py:148→`(int,str)`), `extract_company_header` (169→`(company,stats)`), `get_brief_body` (359→body from first `###` section to CONFIDENTIAL), `md_to_html` (386), `inline` (508).
Replaced: `render_brief_bento` (app.py:1620), alias `render_brief_display` (1794). Call sites: app.py:2046, 2101, 2154.
Removed in cleanup: `extract_infra_cells` (295), `extract_entry_points` (232), `EntryPoint` (206), `_label_pattern` (214), `_grab` (227), `_format_starters_text` (1598), plus dead tile CSS.
PDF replaced: `_draw_hero` (183), `_draw_score_tile` (207), `_draw_infra_grid` (267), `_draw_signals` (327), `_draw_references` (357), `_draw_entry_points` (386), `_draw_conversation_starters` (479); `generate_brief_pdf` (554) rewritten. Kept: `_BriefPDF`, `build_filename`, `_safe_text`, `_strip_md`.

Design tokens already in `:root` (app.py:531): `--alkira-blue #2D58F2`, `--alkira-navy #0A1F44`, `--alkira-ink #211F1F`, `--alkira-muted #7F7F7F`, `--alkira-border #e0e7ff`. PDF RGB mirrors at top of `pdf.py` (`ALKIRA_NAVY`, `ALKIRA_INK`, `ALKIRA_MUTED`, `ALKIRA_BORDER`, `ALKIRA_BLUE`).

---

## File structure

- `app.py` — add `build_brief_document_html` (pure), add `render_brief_document` (replaces `render_brief_bento`), add Style-C CSS, remove dead tile code/CSS.
- `pdf.py` — add `_draw_header_band`, `_iter_sections`, `_draw_section`; rewrite `generate_brief_pdf`; remove tile drawers.
- `tests/test_render.py` — NEW: unit tests for `build_brief_document_html`.
- `tests/test_pdf.py` — NEW: unit tests for `_iter_sections` + a `generate_brief_pdf` smoke test.
- `tests/test_parsers.py` — remove tests for retired parsers (cleanup task).

A shared sample brief fixture is defined in each new test file (kept local to avoid a conftest dependency, matching the existing `tests/` style).

---

## Task 0: Baseline — confirm tests pass before changes

**Files:** none (verification only)

- [ ] **Step 1: Run the existing test suite from the repo root (project Python env active)**

Run: `python -m pytest tests/ -v`
Expected: PASS (green). Note any pre-existing failures before proceeding — do not start on a red baseline.

---

## Task 1: Pure function `build_brief_document_html`

Builds the full document HTML (header band + lead rationale + body) with no Streamlit side effects, so it is unit-testable.

**Files:**
- Modify: `app.py` (add function just above `render_brief_bento`, ~line 1619)
- Test: `tests/test_render.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render.py`:

```python
from app import build_brief_document_html

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
- New VP Infrastructure hired Mar 2026

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

def test_document_has_header_band_with_company_and_badge():
    html = build_brief_document_html(SAMPLE)
    assert "brief-header-band" in html
    assert "Halverson Freight Group" in html
    assert "brief-score-badge" in html
    assert ">4<" in html  # score numeral in badge

def test_document_leads_with_score_rationale():
    html = build_brief_document_html(SAMPLE)
    assert "brief-lead" in html
    assert "multicloud migration" in html

def test_document_renders_section_headers_not_tiles():
    html = build_brief_document_html(SAMPLE)
    assert "Infrastructure Snapshot" in html
    assert "Conversation Starters" in html
    assert 'class="tile' not in html   # no bento tiles
    assert "brief-doc" in html

def test_missing_sections_are_omitted_not_errored():
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
    assert "Infrastructure Snapshot" not in html  # absent section simply not present
    assert "No data" not in html

def test_empty_input_does_not_crash():
    assert "brief-doc" in build_brief_document_html("")

def test_meta_right_is_included_when_provided():
    html = build_brief_document_html(SAMPLE, meta_right="Generated in 42s")
    assert "Generated in 42s" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_render.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_brief_document_html' from 'app'`.

- [ ] **Step 3: Implement the function**

In `app.py`, add immediately above `def render_brief_bento(` (~line 1619):

```python
def build_brief_document_html(brief_md: str, meta_right: str = "") -> str:
    """Build the full document HTML for a brief: header band + lead rationale + body.

    Pure function (no Streamlit side effects) so it is unit-testable. Reuses the
    existing markdown->HTML pipeline (md_to_html) for the body; the score badge and
    company header are the only special-cased pieces. Missing sections simply do not
    appear (md_to_html emits only what the markdown contains).
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_render.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_render.py
git commit -m "feat(brief): add build_brief_document_html pure renderer"
```

---

## Task 2: Style-C CSS — header band, score badge, lead, document body

**Files:**
- Modify: `app.py` — `CUSTOM_CSS`, append after the `.brief-doc .confidential { ... }` block (~line 1095)
- Test: `tests/test_render.py` (add a guard test)

- [ ] **Step 1: Write the failing guard test**

Append to `tests/test_render.py`:

```python
from app import CUSTOM_CSS

def test_custom_css_defines_style_c_classes():
    for cls in (".brief-header-band", ".brief-score-badge", ".brief-lead", ".bsb-num"):
        assert cls in CUSTOM_CSS
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_render.py::test_custom_css_defines_style_c_classes -v`
Expected: FAIL (classes not yet in CSS).

- [ ] **Step 3: Add the CSS**

In `app.py`, find the end of the `.brief-doc .confidential { ... }` rule (~line 1095, inside the `CUSTOM_CSS` string) and insert the following CSS rules right after it (still inside the `<style>` block):

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
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/test_render.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_render.py
git commit -m "feat(brief): add Style-C header band + score badge CSS"
```

---

## Task 3: Swap the renderer to `render_brief_document`

Replace the bento renderer body with the document render + a slim 3-column action toolbar (instead of the stacked full-width buttons that pushed content below the fold). Keep the `render_brief_display` alias so the three call sites are unchanged.

**Files:**
- Modify: `app.py` — replace `render_brief_bento` (1620–1756) with `render_brief_document`; update alias (1794)

- [ ] **Step 1: Replace the function**

Delete the entire body of `render_brief_bento` (from `def render_brief_bento(` at 1620 through the end of the References block at ~1756) and replace with:

```python
def render_brief_document(
    brief_md: str,
    meta_right: str = "",
    show_update: bool = False,
    brief_idx: int | None = None,
) -> None:
    """Render a brief as a clean single-column document (Style C).

    A slim 3-column action toolbar (Download / Update / Delete) sits above the
    document instead of the old stacked full-width buttons.
    """
    score, _ = extract_score(brief_md)
    company, _ = extract_company_header(brief_md)

    # Slim action toolbar (was: three stacked full-width buttons)
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

    # The document itself (header band + lead rationale + flowing sections)
    st.markdown(build_brief_document_html(brief_md, meta_right), unsafe_allow_html=True)
```

- [ ] **Step 2: Update the alias**

Change the alias line (was `render_brief_display = render_brief_bento`, ~line 1794) to:

```python
# Public entry point for rendering a brief (keeps call sites stable)
render_brief_display = render_brief_document
```

- [ ] **Step 3: Verify the module imports and the alias resolves**

Run: `python -c "import app; assert app.render_brief_display is app.render_brief_document; print('ok')"`
Expected: prints `ok` (no ImportError — confirms no lingering references to the deleted body, e.g. `extract_infra_cells` is still defined at this point since cleanup is Task 5).

- [ ] **Step 4: Run the render tests (still green)**

Run: `python -m pytest tests/test_render.py -v`
Expected: PASS (7 passed).

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat(brief): render brief as document with slim action toolbar"
```

---

## Task 4: PDF — header band + generic section walker (no truncation)

Replace the per-tile drawers with a header band (company + stats + navy score badge) and one `_draw_section` that flows headings → paragraphs/bullets, relying on fpdf2 auto page-break.

**Files:**
- Modify: `pdf.py` — add `_iter_sections`, `_draw_header_band`, `_draw_section`; rewrite `generate_brief_pdf` (554)
- Test: `tests/test_pdf.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pdf.py`:

```python
from datetime import datetime
from pdf import _iter_sections, generate_brief_pdf

SAMPLE = """# ALKIRA OPPORTUNITY BRIEF

## Halverson Freight Group
**HQ:** Memphis, TN

**Alkira Fit Score: 4 / 5**
Active multicloud migration.

### Infrastructure Snapshot
- **Cloud Platforms:** AWS, Azure

### Signals & Timing
- Closed Cole Cartage acquisition

### References
[1] Earnings call — https://example.com/hfg

*CONFIDENTIAL*
"""

def test_iter_sections_splits_in_order():
    body = "### One\nalpha\n\n### Two\nbeta\n"
    assert _iter_sections(body) == [("One", "alpha"), ("Two", "beta")]

def test_iter_sections_empty():
    assert _iter_sections("") == []

def test_generate_pdf_returns_pdf_bytes():
    out = generate_brief_pdf(SAMPLE, "Halverson Freight Group", 4, datetime(2026, 6, 8))
    assert isinstance(out, (bytes, bytearray))
    assert bytes(out[:5]) == b"%PDF-"

def test_generate_pdf_long_brief_does_not_crash():
    long_brief = SAMPLE + "\n".join(
        f"### Section {i}\n" + ("Long paragraph of content. " * 40) for i in range(15)
    )
    out = generate_brief_pdf(long_brief, "Big Co", 5, datetime(2026, 6, 8))
    assert bytes(out[:5]) == b"%PDF-"   # multi-page, no truncation exceptions

def test_generate_pdf_sparse_brief_does_not_crash():
    sparse = "# ALKIRA OPPORTUNITY BRIEF\n\n## Tiny Co\n\n**Alkira Fit Score: 1 / 5**\nThin.\n\n*CONFIDENTIAL*\n"
    out = generate_brief_pdf(sparse, "Tiny Co", 1, datetime(2026, 6, 8))
    assert bytes(out[:5]) == b"%PDF-"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_pdf.py -v`
Expected: FAIL with `ImportError: cannot import name '_iter_sections' from 'pdf'`.

- [ ] **Step 3: Add the section splitter**

In `pdf.py`, add after `_strip_md` (~line 102):

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

- [ ] **Step 4: Add the header band drawer**

In `pdf.py`, replace `_draw_hero` (183–201) with:

```python
def _draw_header_band(pdf: "_BriefPDF", company: str, stats_line: str, score: int) -> None:
    """Company + stats (left) with a navy fit-score badge (right), then a rule."""
    top = pdf.get_y()
    badge = 22.0  # mm square

    # Company name (left), wrapped to leave room for the badge
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

    # Navy score badge, top-right
    if score:
        bx, by = 215.9 - 12.7 - badge, top
        pdf.set_fill_color(*ALKIRA_NAVY)
        pdf.rect(bx, by, badge, badge, style="F")  # rounded: add round_corners=True, corner_radius=3 (fpdf2 >= 2.7.7)
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

> Note: the badge uses a plain square `rect` so it works on any fpdf2 version. Rounded corners are an optional enhancement (the inline comment shows how) only if `requirements.txt` pins fpdf2 ≥ 2.7.7.

- [ ] **Step 5: Add the generic section drawer**

In `pdf.py`, add (replacing the now-unused `_draw_signals`/`_draw_references` etc. — they're removed in Step 6):

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
        # Bold sub-heading like **1. Multicloud Networking**
        if re.match(r"^\*\*.+\*\*$", line):
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

- [ ] **Step 6: Rewrite `generate_brief_pdf` and delete the tile drawers**

Replace `generate_brief_pdf` (554–613) with:

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

Then DELETE these now-unused functions from `pdf.py`: `_draw_score_tile`, `_draw_infra_grid`, `_draw_signals`, `_draw_references`, `_draw_entry_points`, `_draw_conversation_starters` (and the old `_draw_hero` if not already replaced in Step 4).

- [ ] **Step 7: Run the PDF tests**

Run: `python -m pytest tests/test_pdf.py -v`
Expected: PASS (5 passed).

- [ ] **Step 8: Commit**

```bash
git add pdf.py tests/test_pdf.py
git commit -m "feat(pdf): render brief as flowing document, drop tile truncation"
```

---

## Task 5: Cleanup — remove dead tile parsers, CSS, and tests (grep-verified)

**Files:**
- Modify: `app.py` (remove dead parsers + dead CSS), `tests/test_parsers.py` (remove tests for removed parsers)

- [ ] **Step 1: Confirm the dead symbols have no remaining references**

Run:
```bash
grep -n "extract_infra_cells\|extract_entry_points\|_format_starters_text\|EntryPoint\|_label_pattern\|_grab\|render_brief_bento\|extract_exec_snippet\|extract_section" app.py pdf.py tests/*.py
```
Expected: matches ONLY at the definitions (and any tests in `test_parsers.py` you will remove in Step 3). Any symbol that ALSO appears in live code (e.g. `extract_exec_snippet` or `extract_section` referenced by `_render_dashboard_cards` or elsewhere) MUST be kept. Resolve/triage every non-definition reference before deleting anything.

- [ ] **Step 2: Delete the dead parsers in `app.py`**

Remove these definitions (verified unreferenced in Step 1): `extract_entry_points` (232–293), `extract_infra_cells` (295–331), `class EntryPoint` (206–212), `_label_pattern` (214–225), `_grab` (227–230), `_format_starters_text` (1598–1617). Remove `extract_exec_snippet` (333–357) ONLY if Step 1 showed no references. Keep `extract_section` (used by `pdf.py`? no — pdf now uses `_iter_sections`; keep only if still referenced; otherwise remove).

- [ ] **Step 3: Remove dead CSS classes in `CUSTOM_CSS`**

Delete the rule blocks for the now-unused tile classes: `.bento-grid` (~848), `.row3` (~857), `.infra-grid` (~863), `.tile` and its variants `.tile.full/.gradient/.dark/.entry`, `.tile-label`, `.tile-value`, `.score-big`, `.score-stars-bento`, `.score-rationale`, `.entry-heading`, `.entry-row`, and the `.tile .brief-doc` / `.tile.dark .brief-doc ...` override blocks (~922–948). KEEP `.brief-doc*`, `.dash-card*`, `.sb-*`, `a.delete-brief-link`, and all sidebar/global rules. Before removing each, confirm with `grep -n '<class>' app.py` that it is not referenced outside the deleted render code.

- [ ] **Step 4: Remove tests for the deleted parsers**

In `tests/test_parsers.py`, delete tests that call `extract_entry_points` / `extract_infra_cells` / `_format_starters_text`. Keep tests for `extract_score`, `extract_company_header`, `extract_section` (if retained), `clean_brief`, `get_brief_body`.

- [ ] **Step 5: Verify import + full suite**

Run:
```bash
python -c "import app, pdf; print('import ok')"
python -m pytest tests/ -v
```
Expected: `import ok`, then all tests PASS (no `NameError`/`ImportError` from a missed reference).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_parsers.py
git commit -m "refactor(brief): remove dead bento tile parsers, CSS, and tests"
```

---

## Task 6: Visual + PDF verification

**Files:** none (manual verification; the visual companion server may still be running from brainstorming)

- [ ] **Step 1: Run the app locally**

Run: `streamlit run app.py` (auth is gated; for local viewing follow `SETUP.md` / use the `auth_email` query param path if configured for local dev). Open an existing brief.

- [ ] **Step 2: Confirm the on-screen document**

Verify: header band (company + stats + navy FIT n/5 badge), slim 3-button toolbar (not stacked), flowing sections with clear headers, no tile grid, brief visible without scrolling past a tall button stack.

- [ ] **Step 3: Check responsive widths**

At 320 / 768 / 1024 / 1440 px (browser devtools): no horizontal overflow; the header band wraps gracefully (badge stays intact).

- [ ] **Step 4: Download the PDF**

Click Download PDF. Confirm: header band + badge, sections flow across pages with NO "[continued in full brief]" / truncated text, multi-page briefs render fully.

- [ ] **Step 5: Sparse brief**

View/generate a brief that is missing a section (e.g., no Infrastructure Snapshot). Confirm the section is simply absent on screen and in the PDF — no empty "No data" box, no crash.

- [ ] **Step 6: Final commit (if any tweaks were needed)**

```bash
git add -A
git commit -m "fix(brief): visual polish from document redesign verification"
```

---

## Definition of done

- Brief renders as Style-C document on screen and in PDF; no tiles.
- `python -m pytest tests/ -v` green.
- Dead tile parsers/CSS removed; `import app, pdf` clean.
- PDF no longer truncates content; sparse briefs degrade gracefully.
- Agent prompt, skills, brief content, sidebar/dashboard, auth, and DB schema unchanged.
