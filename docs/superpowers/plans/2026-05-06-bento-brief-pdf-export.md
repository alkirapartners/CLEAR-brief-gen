# Bento Brief + PDF Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flowing-document brief renderer with a bento-tile layout in branded blue, restyle the dashboard to match, and add a one-click PDF export.

**Architecture:** Pure additive + targeted edits. The agent's markdown output is unchanged. We add `pdf.py` (fpdf2-based generator), add two new parsers + the bento renderer to `app.py`, replace the existing CSS hero/dashboard styling, and wire a Download PDF button into the brief view. No changes to `db.py`, `system_prompt.py`, the skills, or Supabase.

**Tech Stack:** Streamlit, fpdf2 (NEW), pytest (dev only), existing Anthropic Managed Agents + Supabase.

**Spec reference:** `docs/superpowers/specs/2026-05-06-bento-brief-pdf-export-design.md`

**Implementation note — font deviation from spec:** The spec calls for embedding Inter TTFs in the PDF for typography parity with the web. Inter doesn't have a clean static-TTF download path (Google Fonts serves WOFF2; rsms/inter ships a variable font). The plan uses **Helvetica** (built into fpdf2) for the initial PDF. Helvetica is visually adjacent to Inter — same humanist sans-serif lineage. Inter embedding can be a follow-up if brand parity matters.

---

## Phase 1 — Setup

### Task 1: Add fpdf2 dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add fpdf2 to requirements**

Edit `requirements.txt` to add the new line. The full file becomes:

```
anthropic>=0.52.0
python-dotenv>=1.0.0
streamlit>=1.40.0
supabase>=2.0.0
fpdf2>=2.7.9
```

- [ ] **Step 2: Install locally to verify it resolves**

Run: `pip install -r requirements.txt`
Expected: `Successfully installed fpdf2-2.7.X` (or similar). No error.

- [ ] **Step 3: Smoke test fpdf2 import**

Run: `python3 -c "from fpdf import FPDF; print('fpdf2 OK')"`
Expected: `fpdf2 OK`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: add fpdf2 dependency for PDF export"
```

---

### Task 2: Add design system CSS variables

**Files:**
- Modify: `app.py:398` (inside `CUSTOM_CSS` block)

- [ ] **Step 1: Find the CSS block**

Open `app.py`. The CSS string starts at line 398 with `CUSTOM_CSS = """\n<style>`. The `:root` block does not exist yet — we add it as the first thing inside `<style>`.

- [ ] **Step 2: Insert design tokens at the top of the CSS**

Replace the line `<style>` plus the next blank/import line with:

```css
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

    :root {
        /* Brand */
        --alkira-blue: #2D58F2;
        --alkira-navy: #0A1F44;
        --alkira-ink: #211F1F;
        --alkira-muted: #7F7F7F;
        --alkira-orange: #FB923C;
        --alkira-amber: #FBBF24;

        /* Surfaces */
        --alkira-bg: #f8faff;
        --alkira-surface: #ffffff;
        --alkira-border: #e0e7ff;

        /* Score color stops */
        --score-5: #2D58F2;
        --score-4: #60a5fa;
        --score-3: #fbbf24;
        --score-2: #cbd5e1;
        --score-1: #cbd5e1;

        /* Type */
        --font-sans: 'Inter', system-ui, sans-serif;

        /* Radii / spacing */
        --tile-radius: 16px;
        --tile-pad: 14px 16px;
        --tile-shadow: 0 1px 3px rgba(10,31,68,0.04);
    }
```

(The Google Fonts import line should already be present — keep it. Insert the `:root` block right after.)

- [ ] **Step 3: Verify Streamlit still loads**

Run: `streamlit run app.py` (briefly; just confirm no errors on startup)
Expected: app launches at `http://localhost:8501` without errors. Existing UI unchanged.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(css): add Alkira design system tokens"
```

---

## Phase 2 — New parsers (with tests)

### Task 3: Add `extract_entry_points` parser

**Files:**
- Modify: `app.py` (add after existing `extract_section`, around line 200)
- Create: `tests/__init__.py` (empty)
- Create: `tests/test_parsers.py`

- [ ] **Step 1: Install pytest locally (dev only — don't add to requirements.txt)**

Run: `pip install pytest`
Expected: `Successfully installed pytest-X.X.X`

- [ ] **Step 2: Create the test file with the failing test**

Create `tests/__init__.py` as empty file.

Create `tests/test_parsers.py`:

```python
"""Tests for brief markdown parsers."""

from app import extract_entry_points

SAMPLE_BRIEF = """
## Three Alkira Entry Points

**1. Multi-cloud connectivity**
Signal: McKesson runs production on Azure, GCP, and Oracle.
Solution: Alkira connects all three in a single click.
Proof: 96% faster connection time vs DIY transit hubs.

**2. M&A integration**
Signal: RxTS divestiture creates network separation pressure.
Solution: Alkira instantly onboards new entities to the cloud network.
Proof: 98% reduction in partner integration time.

**3. Zero trust segmentation**
Signal: Healthcare compliance requires strict segmentation.
Solution: Alkira applies HIPAA-aligned policy as overlay.
Proof: Aligns to NIST SP 800-207 zero trust architecture.
"""


def test_extract_entry_points_returns_three():
    points = extract_entry_points(SAMPLE_BRIEF)
    assert len(points) == 3


def test_extract_entry_points_signal_solution_proof():
    points = extract_entry_points(SAMPLE_BRIEF)
    assert points[0]["heading"] == "Multi-cloud connectivity"
    assert "Azure, GCP" in points[0]["signal"]
    assert "single click" in points[0]["solution"]
    assert "96%" in points[0]["proof"]


def test_extract_entry_points_handles_missing_section():
    points = extract_entry_points("# Just a title\n\nNo entry points here.")
    assert points == []
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd /Users/blakehays/Desktop/projects/alkira-brief-agent && python -m pytest tests/test_parsers.py -v`
Expected: All 3 tests FAIL with `ImportError: cannot import name 'extract_entry_points'`.

- [ ] **Step 4: Implement `extract_entry_points` in `app.py`**

Add this function in `app.py` immediately after the existing `extract_section` function (around line 202):

```python
def extract_entry_points(brief: str) -> list[dict]:
    """Parse the 'Three Alkira Entry Points' section into 3 dicts.

    Each dict has: heading, signal, solution, proof.
    Returns empty list if section is missing.
    """
    section = extract_section(brief, "Three Alkira Entry Points")
    if not section:
        section = extract_section(brief, "Alkira Entry Points")
    if not section:
        return []

    # Split on bold-numbered headings: **1. Title**, **2. Title**, **3. Title**
    parts = re.split(r"\*\*\d+\.\s+([^*]+?)\*\*", section)
    # parts = ["", "heading1", "body1", "heading2", "body2", ...]

    points: list[dict] = []
    for i in range(1, len(parts), 2):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""

        # Pull Signal / Solution / Proof lines (case-insensitive)
        def _grab(label: str) -> str:
            m = re.search(
                rf"(?i)\b{label}\s*[:\-]\s*(.+?)(?=\n\s*(?:Signal|Solution|Proof)\s*[:\-]|\Z)",
                body,
                re.DOTALL,
            )
            return m.group(1).strip() if m else ""

        points.append({
            "heading": heading,
            "signal": _grab("signal"),
            "solution": _grab("solution"),
            "proof": _grab("proof"),
        })

    return points[:3]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest tests/test_parsers.py -v`
Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/__init__.py tests/test_parsers.py
git commit -m "feat(parsers): add extract_entry_points with tests"
```

---

### Task 4: Add `extract_infra_cells` parser

**Files:**
- Modify: `app.py` (add right after `extract_entry_points`)
- Modify: `tests/test_parsers.py`

- [ ] **Step 1: Add the failing tests**

Append to `tests/test_parsers.py`:

```python
from app import extract_infra_cells

INFRA_BRIEF = """
## Infrastructure Snapshot

**Cloud Platforms:** Azure (confirmed), GCP, Oracle Cloud production workloads.
**On-Prem / Hybrid:** Reduced footprint after 2024 data center consolidation.
**Deployment Model:** Active hybrid cloud migration through 2027.
**Resulting Complexity:** Three clouds plus dozens of acquired networks.
"""


def test_extract_infra_cells_all_four_keys():
    cells = extract_infra_cells(INFRA_BRIEF)
    assert "cloud_platforms" in cells
    assert "on_prem" in cells
    assert "deployment" in cells
    assert "complexity" in cells


def test_extract_infra_cells_content():
    cells = extract_infra_cells(INFRA_BRIEF)
    assert "Azure" in cells["cloud_platforms"]
    assert "2024" in cells["on_prem"]
    assert "2027" in cells["deployment"]
    assert "Three clouds" in cells["complexity"]


def test_extract_infra_cells_missing_section():
    cells = extract_infra_cells("# Just a title")
    assert cells == {
        "cloud_platforms": "",
        "on_prem": "",
        "deployment": "",
        "complexity": "",
    }
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_parsers.py -v`
Expected: 3 new tests FAIL with import error.

- [ ] **Step 3: Implement `extract_infra_cells` in `app.py`**

Add after `extract_entry_points`:

```python
def extract_infra_cells(brief: str) -> dict:
    """Parse the 4 bold sub-labels from Infrastructure Snapshot.

    Returns dict with keys: cloud_platforms, on_prem, deployment, complexity.
    Missing values are empty strings.
    """
    empty = {
        "cloud_platforms": "",
        "on_prem": "",
        "deployment": "",
        "complexity": "",
    }
    section = extract_section(brief, "Infrastructure Snapshot")
    if not section:
        return empty

    label_map = {
        "cloud_platforms": [r"Cloud Platforms?"],
        "on_prem": [r"On-?Prem(?:\s*/\s*Hybrid)?", r"Hybrid"],
        "deployment": [r"Deployment Model", r"Deployment"],
        "complexity": [r"Resulting Complexity", r"Complexity"],
    }

    out = dict(empty)
    for key, patterns in label_map.items():
        for pat in patterns:
            m = re.search(
                rf"\*\*\s*{pat}\s*:?\s*\*\*\s*(.+?)(?=\n\s*\*\*|\Z)",
                section,
                re.DOTALL | re.IGNORECASE,
            )
            if m:
                out[key] = m.group(1).strip()
                break

    return out
```

- [ ] **Step 4: Run tests to verify**

Run: `python -m pytest tests/test_parsers.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_parsers.py
git commit -m "feat(parsers): add extract_infra_cells with tests"
```

---

## Phase 3 — PDF generator

### Task 5: Create `pdf.py` skeleton with constants and filename helper

**Files:**
- Create: `pdf.py`
- Create: `tests/test_pdf.py`

- [ ] **Step 1: Add the failing tests**

Create `tests/test_pdf.py`:

```python
"""Tests for the PDF generator."""

from pdf import build_filename, ALKIRA_BLUE


def test_filename_basic():
    assert build_filename("PepsiCo", "2026-04") == "AlkiraBrief_PepsiCo_2026-04.pdf"


def test_filename_with_spaces_and_punctuation():
    assert build_filename("McKesson Corporation, Inc.", "2026-04") == \
        "AlkiraBrief_McKesson-Corporation-Inc_2026-04.pdf"


def test_filename_truncates_long_company():
    long_name = "Some Extremely Long Holding Company Group International Limited Partnership"
    out = build_filename(long_name, "2026-04")
    # Company portion (between AlkiraBrief_ and _2026-04) should be at most 40 chars
    company_part = out.replace("AlkiraBrief_", "").replace("_2026-04.pdf", "")
    assert len(company_part) <= 40


def test_constants_match_brand_palette():
    assert ALKIRA_BLUE == (45, 88, 242)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_pdf.py -v`
Expected: All tests FAIL with `ModuleNotFoundError: No module named 'pdf'`.

- [ ] **Step 3: Create `pdf.py` with constants and `build_filename`**

Create `pdf.py`:

```python
"""PDF generator for Alkira opportunity briefs.

Uses fpdf2 (programmatic, pure Python). Mirrors the bento web layout
in a print-optimized form. See docs/superpowers/specs/2026-05-06-bento-brief-pdf-export-design.md.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from fpdf import FPDF

# ── Brand palette (RGB tuples for fpdf2) ─────────────────────────
ALKIRA_BLUE   = (45, 88, 242)    # #2D58F2
ALKIRA_NAVY   = (10, 31, 68)     # #0A1F44
ALKIRA_INK    = (33, 31, 31)     # #211F1F
ALKIRA_MUTED  = (127, 127, 127)  # #7F7F7F
ALKIRA_ORANGE = (251, 146, 60)   # #FB923C
ALKIRA_AMBER  = (251, 191, 36)   # #FBBF24
ALKIRA_BORDER = (224, 231, 255)  # #E0E7FF
ALKIRA_WHITE  = (255, 255, 255)  # #FFFFFF


# ── Filename helper ──────────────────────────────────────────────

_FILENAME_MAX = 40


def build_filename(company: str, period: str) -> str:
    """Build the PDF filename: AlkiraBrief_<sanitized-company>_<YYYY-MM>.pdf.

    Strips punctuation, replaces spaces with hyphens, truncates company to 40 chars.
    """
    cleaned = re.sub(r"[^\w\s-]", "", company)         # drop punctuation
    cleaned = re.sub(r"\s+", "-", cleaned.strip())      # spaces → hyphens
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")    # collapse hyphens
    if len(cleaned) > _FILENAME_MAX:
        cleaned = cleaned[:_FILENAME_MAX].rstrip("-")
    return f"AlkiraBrief_{cleaned}_{period}.pdf"


# ── Public API (stub for now — fleshed out in later tasks) ──────

def generate_brief_pdf(
    brief_md: str,
    company: str,
    score: int,
    generated_at: datetime | None = None,
) -> bytes:
    """Render brief markdown as a print-optimized PDF. Returns PDF bytes.

    Stub implementation — returns minimal valid PDF. Phase 3 tasks fill this in.
    """
    pdf = FPDF(orientation="P", unit="mm", format="Letter")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Alkira Brief — Coming Soon", new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_pdf.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pdf.py tests/test_pdf.py
git commit -m "feat(pdf): add pdf.py skeleton with brand palette and filename helper"
```

---

### Task 6: Implement page header and footer

**Files:**
- Modify: `pdf.py`

- [ ] **Step 1: Add a smoke test for header/footer output**

Append to `tests/test_pdf.py`:

```python
def test_pdf_has_pages_after_header_footer():
    """Smoke test: rendering a PDF with header+footer produces valid PDF bytes."""
    from pdf import generate_brief_pdf
    out = generate_brief_pdf(
        brief_md="# ALKIRA OPPORTUNITY BRIEF\n## TestCo\nSample.",
        company="TestCo",
        score=3,
        generated_at=datetime(2026, 5, 6),
    )
    assert isinstance(out, bytes)
    assert out.startswith(b"%PDF")
    assert len(out) > 200  # not just a stub
```

Add the missing import at the top of `tests/test_pdf.py`:

```python
from datetime import datetime
```

- [ ] **Step 2: Add `_BriefPDF` subclass with header and footer in `pdf.py`**

In `pdf.py`, after the constants block and before `build_filename`, add:

```python
class _BriefPDF(FPDF):
    """fpdf2 subclass with Alkira-branded header and footer on every page."""

    def __init__(self, generated_at: datetime):
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(left=12.7, top=20, right=12.7)  # 0.5"
        self.generated_at = generated_at
        self.alias_nb_pages()  # enables {nb} for total page count

    def header(self) -> None:  # noqa: D401  (fpdf hook)
        # Wordmark left
        self.set_xy(12.7, 8)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*ALKIRA_INK)
        self.cell(40, 6, "ALKIRA")

        # Confidential + month-year right
        self.set_xy(-80, 8)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*ALKIRA_MUTED)
        period = self.generated_at.strftime("%B %Y").upper()
        self.cell(0, 6, f"CONFIDENTIAL  |  {period}", align="R")

        # Hairline rule
        self.set_draw_color(*ALKIRA_BORDER)
        self.set_line_width(0.2)
        self.line(12.7, 16, 215.9 - 12.7, 16)

        # Move below header
        self.set_y(22)

    def footer(self) -> None:  # noqa: D401  (fpdf hook)
        self.set_y(-15)
        # Hairline
        self.set_draw_color(*ALKIRA_BORDER)
        self.set_line_width(0.2)
        self.line(12.7, self.get_y(), 215.9 - 12.7, self.get_y())

        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*ALKIRA_MUTED)
        self.cell(0, 4, f"Page {self.page_no()} of {{nb}}")
        self.set_y(-12)
        self.cell(
            0, 4,
            f"Generated {self.generated_at.strftime('%Y-%m-%d')}",
            align="R",
        )
```

- [ ] **Step 3: Update `generate_brief_pdf` to use the subclass**

Replace the stub body of `generate_brief_pdf` with:

```python
def generate_brief_pdf(
    brief_md: str,
    company: str,
    score: int,
    generated_at: datetime | None = None,
) -> bytes:
    """Render brief markdown as a print-optimized PDF. Returns PDF bytes."""
    when = generated_at or datetime.now()
    pdf = _BriefPDF(generated_at=when)
    pdf.add_page()

    # Placeholder body — fleshed out in tasks 7-13.
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*ALKIRA_INK)
    pdf.cell(0, 10, company, new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_pdf.py -v`
Expected: All 5 tests PASS (including new smoke test).

- [ ] **Step 5: Visually inspect the output**

Run: `python -c "from datetime import datetime; from pdf import generate_brief_pdf; open('/tmp/test.pdf','wb').write(generate_brief_pdf('# Test', 'TestCo', 3, datetime(2026,5,6)))"`

Then: `open /tmp/test.pdf` (macOS) or equivalent.

Expected: 1-page PDF showing "ALKIRA" wordmark top-left, "CONFIDENTIAL | MAY 2026" top-right, hairline rules above header bottom and footer top, "Page 1 of 1" bottom-left, "Generated 2026-05-06" bottom-right.

- [ ] **Step 6: Commit**

```bash
git add pdf.py tests/test_pdf.py
git commit -m "feat(pdf): add Alkira-branded page header and footer"
```

---

### Task 7: Implement `_draw_hero` (company name + meta pills)

**Files:**
- Modify: `pdf.py`

- [ ] **Step 1: Add `_draw_hero` helper to `pdf.py`**

Add this function before `generate_brief_pdf`:

```python
def _draw_hero(pdf: _BriefPDF, company: str, header_pills: str) -> None:
    """Draw the company-name hero block at top of page 1.

    `header_pills` is the original pipe-delimited line, e.g.
    'HQ: Irving, TX | Revenue: $309B | Employees: 51K'.
    """
    pdf.set_x(12.7)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*ALKIRA_INK)
    pdf.cell(0, 10, company or "Untitled Brief", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(1)
    pdf.set_x(12.7)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ALKIRA_MUTED)
    cleaned = (header_pills or "").replace("**", "").strip()
    if cleaned:
        pdf.multi_cell(0, 5, cleaned)
    pdf.ln(3)
```

- [ ] **Step 2: Wire it into `generate_brief_pdf`**

Inside `generate_brief_pdf`, replace the placeholder body block (the `pdf.set_font(... "B", 22)` line and the `cell(...company)` line) with:

```python
    # Parse header (uses app.py parsers — imported lazily to avoid circular deps)
    from app import extract_company_header
    company_name, stats_line = extract_company_header(brief_md)
    if not company_name:
        company_name = company

    _draw_hero(pdf, company_name, stats_line)
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_pdf.py -v`
Expected: 5 tests PASS.

- [ ] **Step 4: Visually inspect**

Run the same `python -c "..."` command from Task 6 Step 5 with a longer brief markdown that has a real company header. Open the PDF.

Expected: Hero shows company name big, pills line below in muted gray.

- [ ] **Step 5: Commit**

```bash
git add pdf.py
git commit -m "feat(pdf): add hero block with company name and meta pills"
```

---

### Task 8: Implement `_draw_score_tile`

**Files:**
- Modify: `pdf.py`

- [ ] **Step 1: Add `_draw_score_tile` helper**

Add this function before `generate_brief_pdf`:

```python
def _draw_score_tile(
    pdf: _BriefPDF,
    score: int,
    rationale: str,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    """Draw the gradient-blue score tile with big number, stars, and rationale.

    fpdf2 has no gradient primitive — we use a solid Alkira blue fill,
    which reads as a clean print equivalent of the web gradient.
    """
    # Tile background
    pdf.set_fill_color(*ALKIRA_BLUE)
    pdf.rect(x, y, w, h, style="F")

    # Label
    pdf.set_xy(x + 4, y + 4)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*ALKIRA_WHITE)
    pdf.cell(w - 8, 4, "ALKIRA FIT")

    # Big number
    pdf.set_xy(x + 4, y + 10)
    pdf.set_font("Helvetica", "B", 36)
    pdf.cell(w - 8, 14, str(max(1, min(5, score))))

    # Stars (filled + empty)
    filled = "★" * max(0, min(5, score))
    empty = "☆" * max(0, 5 - max(0, min(5, score)))
    pdf.set_xy(x + 4, y + 26)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(w - 8, 5, filled + empty)

    # Rationale
    pdf.set_xy(x + 4, y + 33)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*ALKIRA_WHITE)
    text_w = w - 8
    text_h = h - 36
    # Use multi_cell for wrapped rationale; fpdf2 will clip to height.
    pdf.multi_cell(text_w, 4, (rationale or "").strip()[:480])
```

- [ ] **Step 2: Wire it into `generate_brief_pdf`**

After the `_draw_hero(pdf, company_name, stats_line)` call, add:

```python
    # Parse score + rationale
    from app import extract_score
    parsed_score, rationale = extract_score(brief_md)
    if not parsed_score:
        parsed_score = score

    # Layout constants (page is 215.9mm wide, 12.7mm margins → 190.5mm content)
    content_w = 190.5
    score_w = content_w * 0.34
    score_h = 60
    score_x = 12.7
    score_y = pdf.get_y()

    _draw_score_tile(pdf, parsed_score, rationale, score_x, score_y, score_w, score_h)
```

- [ ] **Step 3: Run tests + visually inspect**

Run: `python -m pytest tests/test_pdf.py -v` (5 tests PASS)

Run a manual render to `/tmp/test.pdf` with a real brief; open and confirm a blue tile with big "4", stars, and rationale text appears.

- [ ] **Step 4: Commit**

```bash
git add pdf.py
git commit -m "feat(pdf): add score tile with stars and rationale"
```

---

### Task 9: Implement `_draw_infra_grid` (4-cell)

**Files:**
- Modify: `pdf.py`

- [ ] **Step 1: Add `_draw_infra_grid` helper**

Add before `generate_brief_pdf`:

```python
def _draw_infra_grid(
    pdf: _BriefPDF,
    cells: dict,
    x: float,
    y: float,
    w: float,
    h: float,
) -> None:
    """Draw the 2x2 infrastructure cell grid.

    `cells` keys: cloud_platforms, on_prem, deployment, complexity.
    """
    half_w = w / 2
    half_h = h / 2
    items = [
        ("CLOUD PLATFORMS", cells.get("cloud_platforms", ""), x, y),
        ("ON-PREM / HYBRID", cells.get("on_prem", ""), x + half_w, y),
        ("DEPLOYMENT MODEL", cells.get("deployment", ""), x, y + half_h),
        ("RESULTING COMPLEXITY", cells.get("complexity", ""), x + half_w, y + half_h),
    ]
    pad = 3.0
    for label, body, cx, cy in items:
        # Cell border
        pdf.set_draw_color(*ALKIRA_BORDER)
        pdf.set_line_width(0.2)
        pdf.set_fill_color(*ALKIRA_WHITE)
        pdf.rect(cx, cy, half_w, half_h, style="DF")

        # Label
        pdf.set_xy(cx + pad, cy + pad)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*ALKIRA_BLUE)
        pdf.cell(half_w - 2 * pad, 3.5, label)

        # Body
        pdf.set_xy(cx + pad, cy + pad + 4.5)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*ALKIRA_INK)
        pdf.multi_cell(half_w - 2 * pad, 3.6, (body or "—").strip()[:360])
```

- [ ] **Step 2: Wire into `generate_brief_pdf`**

After the score tile placement, add:

```python
    # Infrastructure grid (right of score tile, same height)
    infra_w = content_w - score_w - 4
    infra_x = score_x + score_w + 4
    cells = extract_infra_cells(brief_md)
    _draw_infra_grid(pdf, cells, infra_x, score_y, infra_w, score_h)

    # Move below the score+infra row
    pdf.set_y(score_y + score_h + 4)
```

You'll also need to add at the top of `pdf.py` (after the existing imports):

```python
# Lazy import target — used inside generate_brief_pdf to avoid circular dep
def _import_app_parsers():
    """Import app.py parsers lazily to avoid circular import on Streamlit start."""
    from app import (
        extract_company_header,
        extract_score,
        extract_section,
        extract_entry_points,
        extract_infra_cells,
    )
    return {
        "extract_company_header": extract_company_header,
        "extract_score": extract_score,
        "extract_section": extract_section,
        "extract_entry_points": extract_entry_points,
        "extract_infra_cells": extract_infra_cells,
    }
```

And replace the inline `from app import ...` imports in `generate_brief_pdf` with a single call at the top of the function:

```python
    parsers = _import_app_parsers()
    extract_company_header = parsers["extract_company_header"]
    extract_score = parsers["extract_score"]
    extract_section = parsers["extract_section"]
    extract_entry_points = parsers["extract_entry_points"]
    extract_infra_cells = parsers["extract_infra_cells"]
```

- [ ] **Step 3: Run tests + visual check**

Run: `python -m pytest tests/test_pdf.py -v` (5 tests PASS)

Manual render: confirm 4-cell grid appears to right of score tile with labels CLOUD PLATFORMS, ON-PREM/HYBRID, DEPLOYMENT MODEL, RESULTING COMPLEXITY.

- [ ] **Step 4: Commit**

```bash
git add pdf.py
git commit -m "feat(pdf): add 4-cell infrastructure grid"
```

---

### Task 10: Implement `_draw_signals` and `_draw_references`

**Files:**
- Modify: `pdf.py`

- [ ] **Step 1: Add both helpers**

Add before `generate_brief_pdf`:

```python
def _draw_signals(pdf: _BriefPDF, signals_md: str) -> None:
    """Draw the Signals & Timing tile (full width, white)."""
    if not signals_md.strip():
        return

    x = 12.7
    y = pdf.get_y()
    w = 190.5

    # Estimate height — fpdf2 will auto-page-break if needed
    pdf.set_draw_color(*ALKIRA_BORDER)
    pdf.set_line_width(0.2)
    pdf.set_fill_color(*ALKIRA_WHITE)
    pdf.set_xy(x, y)

    # Section label
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*ALKIRA_BLUE)
    pdf.cell(0, 5, "SIGNALS & TIMING", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    # Bullets — strip "- " or "* " from each line
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*ALKIRA_INK)
    for raw in signals_md.splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[-*]\s+", "", line)
        pdf.set_x(15)
        pdf.cell(3, 4.5, "•")
        pdf.multi_cell(w - 5, 4.5, line)
    pdf.ln(2)


def _draw_references(pdf: _BriefPDF, refs_md: str) -> None:
    """Draw the References tile at the end of the brief."""
    if not refs_md.strip():
        return

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*ALKIRA_BLUE)
    pdf.cell(0, 5, "REFERENCES", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(*ALKIRA_INK)
    for raw in refs_md.splitlines():
        line = raw.strip()
        if not line:
            continue
        # Lines look like "[1] Description — https://..."
        pdf.multi_cell(0, 4, line)
```

- [ ] **Step 2: Wire into `generate_brief_pdf`**

After the infra grid block, add:

```python
    signals = extract_section(brief_md, "Signals & Timing") or extract_section(brief_md, "Signals and Timing")
    _draw_signals(pdf, signals)
```

(References call comes later — at the very end of the function, added in Task 13.)

- [ ] **Step 3: Tests + visual**

Run: `python -m pytest tests/test_pdf.py -v` (5 tests PASS)

Manual render: signals tile appears below the score+infra row with bulleted timing items.

- [ ] **Step 4: Commit**

```bash
git add pdf.py
git commit -m "feat(pdf): add signals and references tile renderers"
```

---

### Task 11: Implement `_draw_entry_points` (3-column row)

**Files:**
- Modify: `pdf.py`

- [ ] **Step 1: Add `_draw_entry_points` helper**

Add before `generate_brief_pdf`:

```python
def _draw_entry_points(pdf: _BriefPDF, points: list[dict]) -> None:
    """Draw the 3 entry-point tiles in a row, each with orange top stripe."""
    if not points:
        return

    pdf.add_page()  # entry points start a fresh page for clean layout

    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*ALKIRA_BLUE)
    pdf.cell(0, 5, "THREE ALKIRA ENTRY POINTS", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    x = 12.7
    y = pdf.get_y()
    content_w = 190.5
    gap = 3.0
    tile_w = (content_w - 2 * gap) / 3
    tile_h = 75

    for i, point in enumerate(points[:3]):
        cx = x + i * (tile_w + gap)
        # Tile background
        pdf.set_draw_color(*ALKIRA_BORDER)
        pdf.set_line_width(0.2)
        pdf.set_fill_color(*ALKIRA_WHITE)
        pdf.rect(cx, y, tile_w, tile_h, style="DF")

        # Orange top stripe (3pt)
        pdf.set_fill_color(*ALKIRA_ORANGE)
        pdf.rect(cx, y, tile_w, 1.2, style="F")

        pad = 3.0
        # Label
        pdf.set_xy(cx + pad, y + 3)
        pdf.set_font("Helvetica", "B", 7)
        pdf.set_text_color(*ALKIRA_ORANGE)
        pdf.cell(tile_w - 2 * pad, 3.5, f"ENTRY 0{i+1}")

        # Heading
        pdf.set_xy(cx + pad, y + 7.5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*ALKIRA_INK)
        pdf.multi_cell(tile_w - 2 * pad, 4.5, point.get("heading", "")[:80])

        # Body — Signal / Solution / Proof
        cy = pdf.get_y() + 1
        for label_key, body_key in [("Signal", "signal"), ("Solution", "solution"), ("Proof", "proof")]:
            pdf.set_xy(cx + pad, cy)
            pdf.set_font("Helvetica", "B", 7)
            pdf.set_text_color(*ALKIRA_BLUE)
            pdf.cell(tile_w - 2 * pad, 3.2, label_key.upper())
            cy = pdf.get_y() + 3.5
            pdf.set_xy(cx + pad, cy)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*ALKIRA_INK)
            pdf.multi_cell(tile_w - 2 * pad, 3.6, point.get(body_key, "—")[:240])
            cy = pdf.get_y() + 1

    # Move below the row
    pdf.set_y(y + tile_h + 4)
```

- [ ] **Step 2: Wire into `generate_brief_pdf`**

After the `_draw_signals(pdf, signals)` call, add:

```python
    points = extract_entry_points(brief_md)
    _draw_entry_points(pdf, points)
```

- [ ] **Step 3: Tests + visual check**

Run: `python -m pytest tests/test_pdf.py -v` (5 PASS)

Manual render with a brief that has 3 entry points: confirm a fresh page begins with "THREE ALKIRA ENTRY POINTS" header and 3 tiles with orange top stripes appear in a row.

- [ ] **Step 4: Commit**

```bash
git add pdf.py
git commit -m "feat(pdf): add three entry-point tiles with orange stripes"
```

---

### Task 12: Implement `_draw_conversation_starters`

**Files:**
- Modify: `pdf.py`

- [ ] **Step 1: Add `_draw_conversation_starters` helper**

Add before `generate_brief_pdf`:

```python
def _draw_conversation_starters(pdf: _BriefPDF, starters_md: str) -> None:
    """Draw the dark-navy Conversation Starters tile."""
    if not starters_md.strip():
        return

    x = 12.7
    y = pdf.get_y()
    w = 190.5

    # Body height — let fpdf2 auto-page-break if it overflows
    body_h = 75

    pdf.set_fill_color(*ALKIRA_NAVY)
    pdf.rect(x, y, w, body_h, style="F")

    pad = 5.0
    pdf.set_xy(x + pad, y + pad)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(*ALKIRA_ORANGE)
    pdf.cell(0, 4, "CONVERSATION STARTERS", new_x="LMARGIN", new_y="NEXT")

    # Body — render the markdown as plain text, line by line.
    pdf.set_x(x + pad)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*ALKIRA_WHITE)

    lines = [ln for ln in starters_md.splitlines() if ln.strip()]
    cy = y + pad + 6
    for raw in lines:
        line = raw.strip()
        # Strip simple markdown
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"^[-*]\s+", "• ", line)

        if cy > y + body_h - 6:
            break  # exhausted; defensive cap

        pdf.set_xy(x + pad, cy)
        pdf.multi_cell(w - 2 * pad, 4, line)
        cy = pdf.get_y() + 0.5

    pdf.set_y(y + body_h + 4)
```

- [ ] **Step 2: Wire into `generate_brief_pdf`**

After the `_draw_entry_points(pdf, points)` call, add:

```python
    starters = extract_section(brief_md, "Conversation Starters")
    _draw_conversation_starters(pdf, starters)
```

- [ ] **Step 3: Tests + visual**

Run: `python -m pytest tests/test_pdf.py -v` (5 PASS)

Manual render with a real brief: confirm dark navy block appears below entry points with "CONVERSATION STARTERS" in orange and the questions list inside.

- [ ] **Step 4: Commit**

```bash
git add pdf.py
git commit -m "feat(pdf): add navy conversation-starters tile"
```

---

### Task 13: Wire references and finalize `generate_brief_pdf`

**Files:**
- Modify: `pdf.py`

- [ ] **Step 1: Add references call at the end of `generate_brief_pdf`**

After the conversation-starters call, add:

```python
    refs = extract_section(brief_md, "References")
    _draw_references(pdf, refs)

    return bytes(pdf.output())
```

(Make sure the previous `return bytes(pdf.output())` line is removed if it was earlier in the function. There should be only one `return`.)

- [ ] **Step 2: Add a fuller smoke test**

Append to `tests/test_pdf.py`:

```python
SAMPLE_FULL_BRIEF = """# ALKIRA OPPORTUNITY BRIEF
*May 2026*

## TestCo Holdings

**HQ:** Austin, TX | **Revenue:** $5B | **Employees:** 12,000 | **Industry:** Software

**Alkira Fit Score: 4 / 5**

TestCo runs production across Azure and AWS with active vendor consolidation
pressure. Multi-cloud connectivity and zero trust readiness make this a
strong fit for Alkira's NaaS platform.

## Infrastructure Snapshot

**Cloud Platforms:** Azure (confirmed), AWS production workloads.
**On-Prem / Hybrid:** Reduced footprint after 2024 consolidation.
**Deployment Model:** Active hybrid cloud migration.
**Resulting Complexity:** Two clouds plus acquired networks.

## Signals & Timing
- Vendor consolidation initiative announced Q1 2026
- New CIO from a cloud-native peer (Feb 2026)
- $300M IT modernization budget through 2027
- Zero trust mandate from board

## Three Alkira Entry Points

**1. Multi-cloud connectivity**
Signal: TestCo runs Azure and AWS production.
Solution: Alkira connects both in a single click.
Proof: 96% faster connection time.

**2. Zero trust segmentation**
Signal: Board mandate for zero trust.
Solution: Alkira applies policy as overlay.
Proof: Aligns to NIST SP 800-207.

**3. M&A integration**
Signal: Recent acquisitions create network sprawl.
Solution: Alkira instantly onboards new entities.
Proof: 98% reduction in partner integration time.

## Conversation Starters

**Stakeholders:** CIO, VP Network, CISO

**Best First Question:** Lead with question #1.

1. "How's the Azure-AWS connectivity going?"
2. "What's the timeline on zero trust?"

## References
[1] TestCo 10-K — https://example.com/10k
[2] CIO interview — https://example.com/interview
"""


def test_full_brief_renders():
    from pdf import generate_brief_pdf
    out = generate_brief_pdf(
        brief_md=SAMPLE_FULL_BRIEF,
        company="TestCo Holdings",
        score=4,
        generated_at=datetime(2026, 5, 6),
    )
    assert isinstance(out, bytes)
    assert out.startswith(b"%PDF")
    assert len(out) > 5000  # Real brief renders to substantive bytes
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: All tests PASS (parsers + PDF).

- [ ] **Step 3: Visual end-to-end check**

Render to `/tmp/full.pdf`:

```bash
python -c "
from datetime import datetime
from pdf import generate_brief_pdf
from tests.test_pdf import SAMPLE_FULL_BRIEF
out = generate_brief_pdf(SAMPLE_FULL_BRIEF, 'TestCo Holdings', 4, datetime(2026,5,6))
open('/tmp/full.pdf','wb').write(out)
"
open /tmp/full.pdf
```

Expected: 2-3 page PDF showing hero (TestCo Holdings), score tile + infra grid, signals, fresh page with 3 entry-point tiles, navy conversation-starters tile, references list. Header and footer on every page.

- [ ] **Step 4: Commit**

```bash
git add pdf.py tests/test_pdf.py
git commit -m "feat(pdf): wire references and complete end-to-end brief PDF"
```

---

## Phase 4 — Web bento renderer

### Task 14: Add tile CSS classes

**Files:**
- Modify: `app.py` (inside `CUSTOM_CSS`)

- [ ] **Step 1: Find a good insertion point**

In `CUSTOM_CSS` (starting line 397), find the existing `.brief-doc` block (somewhere around lines 700-900). Add the new tile classes immediately before that block, or at the end of the CSS string before the closing `</style>`.

- [ ] **Step 2: Add tile classes**

Insert this CSS:

```css
    /* ── Bento brief tiles ─────────────────────────── */
    .bento-grid {
        display: grid;
        grid-template-columns: 1fr 2fr;
        gap: 12px;
        margin-top: 1rem;
    }
    .bento-grid .full {
        grid-column: 1 / -1;
    }
    .bento-grid .row3 {
        grid-column: 1 / -1;
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 12px;
    }
    .bento-grid .infra-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
    }

    .tile {
        background: var(--alkira-surface);
        border: 1px solid var(--alkira-border);
        border-radius: var(--tile-radius);
        padding: var(--tile-pad);
        box-shadow: var(--tile-shadow);
    }
    .tile.gradient {
        background: linear-gradient(135deg, var(--alkira-navy) 0%, var(--alkira-blue) 100%);
        color: #fff;
        border: none;
    }
    .tile.dark {
        background: var(--alkira-navy);
        color: #fff;
        border: none;
    }
    .tile.entry {
        position: relative;
        padding-top: 18px;
    }
    .tile.entry::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: var(--alkira-orange);
        border-radius: var(--tile-radius) var(--tile-radius) 0 0;
    }
    .tile-label {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--alkira-blue);
        margin: 0 0 6px;
    }
    .tile.dark .tile-label {
        color: var(--alkira-orange);
    }
    .tile.gradient .tile-label {
        color: rgba(255,255,255,0.8);
    }
    .tile-value {
        font-size: 14px;
        line-height: 1.5;
        color: var(--alkira-ink);
    }
    .tile.dark .tile-value,
    .tile.gradient .tile-value {
        color: #fff;
    }
    .score-big {
        font-size: 56px;
        font-weight: 800;
        line-height: 1;
        color: #fff;
    }
    .score-stars-bento {
        font-size: 16px;
        color: var(--alkira-amber);
        letter-spacing: 0.1em;
        margin: 6px 0 8px;
    }
    .score-rationale {
        font-size: 13px;
        line-height: 1.5;
        color: rgba(255,255,255,0.9);
    }
    .entry-heading {
        font-size: 14px;
        font-weight: 700;
        margin: 4px 0 8px;
        color: var(--alkira-ink);
    }
    .entry-row {
        margin: 6px 0;
        font-size: 12px;
        line-height: 1.4;
    }
    .entry-row b {
        color: var(--alkira-blue);
        font-size: 10px;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        display: block;
        margin-bottom: 2px;
    }
```

- [ ] **Step 3: Verify Streamlit still loads**

Run: `streamlit run app.py`
Expected: app loads. Existing UI unchanged (we haven't called the new classes yet).

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(css): add bento tile classes for brief layout"
```

---

### Task 15: Implement `render_brief_bento`

**Files:**
- Modify: `app.py` (replace body of `render_brief_display` at line 1254)

- [ ] **Step 1: Replace `render_brief_display` with `render_brief_bento`**

In `app.py`, locate `def render_brief_display(...)` at line 1254. Replace the entire function (everything from `def render_brief_display` to its closing — about 60 lines) with:

```python
def render_brief_bento(
    brief_md: str,
    meta_right: str = "",
    show_update: bool = False,
) -> None:
    """Render a brief as a bento tile layout."""
    score, reasoning = extract_score(brief_md)
    company, stats_line = extract_company_header(brief_md)

    # Stats pills line (cleaned)
    cleaned_stats = (stats_line or "").replace("**", "").strip()

    # Stars
    filled = "★" * max(0, min(5, score))
    empty = "☆" * max(0, 5 - max(0, min(5, score)))

    # Hero tile (full width)
    hero_html = (
        f'<div class="tile full" style="margin-bottom:12px">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">'
        f'<div>'
        f'<h2 style="margin:0;font-size:24px;font-weight:700;color:var(--alkira-ink)">{company or "Brief"}</h2>'
        f'<p style="margin:4px 0 0;color:var(--alkira-muted);font-size:13px">{cleaned_stats}</p>'
        f'</div>'
        f'<div style="text-align:right;color:var(--alkira-muted);font-size:12px;white-space:nowrap">{meta_right}</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(hero_html, unsafe_allow_html=True)

    # Download PDF button (wired in next task)
    _render_download_pdf_button(brief_md, company or "Brief", score)

    # Update button stays as-is for re-research
    if show_update and company:
        if st.button("Update Brief", key="update_brief", use_container_width=True):
            st.session_state["_update_company"] = company
            st.rerun()

    # Score tile + infra grid (1/3 + 2/3)
    cells = extract_infra_cells(brief_md)
    score_html = (
        f'<div class="tile gradient">'
        f'<p class="tile-label">Alkira Fit</p>'
        f'<div class="score-big">{score}</div>'
        f'<div class="score-stars-bento">{filled}{empty}</div>'
        f'<p class="score-rationale">{reasoning}</p>'
        f'</div>'
    )
    infra_html = (
        f'<div>'
        f'<div class="infra-grid">'
        f'<div class="tile"><p class="tile-label">Cloud Platforms</p>'
        f'<p class="tile-value">{cells["cloud_platforms"] or "—"}</p></div>'
        f'<div class="tile"><p class="tile-label">On-Prem / Hybrid</p>'
        f'<p class="tile-value">{cells["on_prem"] or "—"}</p></div>'
        f'<div class="tile"><p class="tile-label">Deployment Model</p>'
        f'<p class="tile-value">{cells["deployment"] or "—"}</p></div>'
        f'<div class="tile"><p class="tile-label">Resulting Complexity</p>'
        f'<p class="tile-value">{cells["complexity"] or "—"}</p></div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(
        f'<div class="bento-grid">{score_html}{infra_html}</div>',
        unsafe_allow_html=True,
    )

    # Signals tile (full width)
    signals_md = extract_section(brief_md, "Signals & Timing") or extract_section(brief_md, "Signals and Timing")
    if signals_md.strip():
        bullets = "".join(
            f"<li>{inline(re.sub(r'^[-*]\\s+', '', ln.strip()))}</li>"
            for ln in signals_md.splitlines() if ln.strip()
        )
        st.markdown(
            f'<div class="tile full" style="margin-top:12px">'
            f'<p class="tile-label">Signals &amp; Timing</p>'
            f'<ul style="margin:6px 0 0;padding-left:18px;font-size:13px;line-height:1.5;color:var(--alkira-ink)">{bullets}</ul>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Three entry-point tiles
    points = extract_entry_points(brief_md)
    if points:
        cards = []
        for i, p in enumerate(points[:3]):
            heading = p.get("heading", "")
            cards.append(
                f'<div class="tile entry">'
                f'<p class="tile-label">Entry 0{i+1}</p>'
                f'<h3 class="entry-heading">{heading}</h3>'
                f'<div class="entry-row"><b>Signal</b>{p.get("signal","—")}</div>'
                f'<div class="entry-row"><b>Solution</b>{p.get("solution","—")}</div>'
                f'<div class="entry-row"><b>Proof</b>{p.get("proof","—")}</div>'
                f'</div>'
            )
        st.markdown(
            f'<div class="row3" style="margin-top:12px">{"".join(cards)}</div>',
            unsafe_allow_html=True,
        )

    # Conversation Starters tile (dark navy)
    starters = extract_section(brief_md, "Conversation Starters")
    if starters.strip():
        st.markdown(
            f'<div class="tile dark full" style="margin-top:12px">'
            f'<p class="tile-label">Conversation Starters</p>'
            f'<div class="tile-value" style="margin-top:6px">{md_to_html(starters)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # References tile (full width, footer-style)
    refs = extract_section(brief_md, "References")
    if refs.strip():
        st.markdown(
            f'<div class="tile full" style="margin-top:12px">'
            f'<p class="tile-label">References</p>'
            f'<div class="tile-value" style="font-size:12px">{md_to_html(refs)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def _render_download_pdf_button(brief_md: str, company: str, score: int) -> None:
    """Stub — wired in next task."""
    pass


# Keep render_brief_display as an alias for backwards compatibility
render_brief_display = render_brief_bento
```

- [ ] **Step 2: Run the app**

Run: `streamlit run app.py`
Expected: app loads. Open an existing brief; confirm bento tiles render (hero, score+infra, signals, entry points, conversation starters, references). Update button still works.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(brief): replace flowing renderer with bento tile layout"
```

---

### Task 16: Wire Download PDF button

**Files:**
- Modify: `app.py` (replace `_render_download_pdf_button` stub)

- [ ] **Step 1: Implement the button**

In `app.py`, replace the stub `_render_download_pdf_button` (added in Task 15) with:

```python
def _render_download_pdf_button(brief_md: str, company: str, score: int) -> None:
    """Render the Download PDF button. Generates the PDF on-demand."""
    from datetime import datetime
    try:
        from pdf import generate_brief_pdf, build_filename
    except Exception as exc:
        st.warning(f"PDF generation unavailable: {exc}")
        return

    now = datetime.now()
    period = now.strftime("%Y-%m")
    filename = build_filename(company or "Brief", period)

    # Generate bytes lazily on click
    if st.session_state.get("_pdf_company_cache") != company:
        st.session_state["_pdf_company_cache"] = company
        try:
            pdf_bytes = generate_brief_pdf(brief_md, company, score, now)
            st.session_state["_pdf_bytes_cache"] = pdf_bytes
        except Exception as exc:
            st.warning(f"PDF generation failed: {exc}")
            return

    st.download_button(
        label="↓ Download PDF",
        data=st.session_state.get("_pdf_bytes_cache", b""),
        file_name=filename,
        mime="application/pdf",
        use_container_width=True,
        key="download_pdf",
    )
```

- [ ] **Step 2: Run the app and verify**

Run: `streamlit run app.py`
Expected: open a brief → "↓ Download PDF" button appears under hero. Click → PDF downloads as `AlkiraBrief_<Company>_<YYYY-MM>.pdf`. Open the PDF — confirm the layout from Phase 3.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(brief): wire Download PDF button"
```

---

## Phase 5 — Dashboard restyle

### Task 17: Replace hero text badge with Alkira logo + new gradient

**Files:**
- Modify: `app.py` (CSS hero block around line 423; hero markup elsewhere — search for `class="hero"`)

- [ ] **Step 1: Find existing hero markup**

Run: `grep -n 'class="hero"\|hero-icon\|hero-badge' /Users/blakehays/Desktop/projects/alkira-brief-agent/app.py`

Note the line numbers. The hero is rendered as inline HTML inside `main()` somewhere after `st.markdown(CUSTOM_CSS, ...)`.

- [ ] **Step 2: Replace hero CSS to use real Alkira blue**

In `CUSTOM_CSS`, find the `.hero { background: linear-gradient(...) }` rule (line ~425) and update it to:

```css
    .hero {
        background: linear-gradient(135deg, #0a1f44 0%, #2D58F2 100%);
        border-radius: 14px;
        padding: 1.6rem 1.8rem;
        margin-bottom: 1.25rem;
        position: relative;
        overflow: hidden;
    }
```

Also update the `.hero::after` radial gradient color to match the new blue:

```css
    .hero::after {
        content: '';
        position: absolute;
        top: -60%;
        right: -10%;
        width: 300px;
        height: 300px;
        background: radial-gradient(circle, rgba(45,88,242,0.12) 0%, transparent 70%);
        pointer-events: none;
    }
```

- [ ] **Step 3: Replace the hero-icon image with the Alkira logo SVG**

Find the hero markup in `main()`. Currently the hero shows a "CHANNEL SALES INTELLIGENCE" badge. Replace its HTML with logo + headline:

Locate the `<div class="hero">` block. Replace with:

```python
    # Read the SVG once at startup
    try:
        with open("assets/alkira-logo.svg", "r", encoding="utf-8") as f:
            logo_svg = f.read()
    except FileNotFoundError:
        logo_svg = '<span style="font-weight:800;font-size:18px;color:#fff">ALKIRA</span>'

    st.markdown(
        f'<div class="hero">'
        f'<div class="hero-top" style="margin-bottom:1rem">'
        f'<div style="height:32px;display:inline-block;filter:brightness(0) invert(1)">{logo_svg}</div>'
        f'</div>'
        f'<h1 style="color:#fff;font-size:32px;margin:0 0 4px;font-weight:700">Alkira Brief Generator</h1>'
        f'<p style="color:rgba(255,255,255,0.85);margin:0;font-size:14px">'
        f'Research any company. Get a scored opportunity brief with Alkira fit analysis, '
        f'proof points, and sales questions.'
        f'</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
```

(The `filter:brightness(0) invert(1)` flips the dark logo to white so it reads on the navy gradient.)

- [ ] **Step 4: Visual check**

Run: `streamlit run app.py`
Expected: Hero shows the actual Alkira logo (white) top-left, the gradient now uses real brand blue, headline stays "Alkira Brief Generator", tagline below.

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat(hero): use Alkira logo SVG and real brand blue gradient"
```

---

### Task 18: Restyle search input + Generate button

**Files:**
- Modify: `app.py` (CSS only)

- [ ] **Step 1: Locate the search-wrap CSS**

Run: `grep -n "search-wrap\|stFormSubmitButton\|formSubmit" /Users/blakehays/Desktop/projects/alkira-brief-agent/app.py`

- [ ] **Step 2: Update the search and button CSS**

Find the existing `.search-wrap` rule and the form submit button rules. Update / add the following CSS in `CUSTOM_CSS`:

```css
    /* ── Search / Generate ─────────────────────────── */
    .stTextInput > div > div > input {
        border-radius: 9999px !important;
        border: 1px solid var(--alkira-border) !important;
        padding: 0.6rem 1rem !important;
        font-family: var(--font-sans) !important;
        font-size: 14px !important;
        background: #fff !important;
    }
    .stTextInput > div > div > input:focus {
        outline: none !important;
        border-color: var(--alkira-blue) !important;
        box-shadow: 0 0 0 3px rgba(45,88,242,0.15) !important;
    }

    .stFormSubmitButton > button,
    button[kind="formSubmit"] {
        background: var(--alkira-blue) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 9999px !important;
        padding: 0.6rem 1.4rem !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        transition: transform 100ms ease, box-shadow 100ms ease;
    }
    .stFormSubmitButton > button:hover,
    button[kind="formSubmit"]:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(45,88,242,0.25);
    }
```

- [ ] **Step 3: Visual check**

Run: `streamlit run app.py`
Expected: search input is pill-shaped with subtle blue glow on focus. Generate button is solid Alkira blue, lifts slightly on hover.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(search): restyle search input and Generate button"
```

---

### Task 19: Restyle dashboard cards with score color stripes

**Files:**
- Modify: `app.py` (CSS + `_render_dashboard_cards` at line 1198)

- [ ] **Step 1: Update card CSS**

In `CUSTOM_CSS`, find the existing dashboard-card-related rules (search for `dash-card`, `dash-company`). Add or replace:

```css
    /* ── Dashboard cards ──────────────────────────── */
    .dash-card {
        background: #fff;
        border: 1px solid var(--alkira-border);
        border-radius: 14px;
        padding: 14px 16px;
        box-shadow: var(--tile-shadow);
        transition: transform 120ms ease, box-shadow 120ms ease;
        position: relative;
        min-height: 130px;
        overflow: hidden;
    }
    .dash-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 3px;
        background: var(--score-3);
    }
    .dash-card[data-score="5"]::before { background: var(--score-5); }
    .dash-card[data-score="4"]::before { background: var(--score-4); }
    .dash-card[data-score="3"]::before { background: var(--score-3); }
    .dash-card[data-score="2"]::before { background: var(--score-2); }
    .dash-card[data-score="1"]::before { background: var(--score-1); }
    .dash-card:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(10,31,68,0.08);
    }
    .dash-card-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 8px;
        margin-bottom: 6px;
    }
    .dash-company {
        font-size: 15px;
        font-weight: 700;
        color: var(--alkira-ink);
        line-height: 1.2;
        margin: 0;
        display: -webkit-box;
        -webkit-line-clamp: 1;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .dash-stars {
        font-size: 12px;
        color: var(--alkira-amber);
        letter-spacing: 0.1em;
        white-space: nowrap;
    }
    .dash-snippet {
        font-size: 12px;
        color: #475569;
        line-height: 1.45;
        margin: 0 0 8px;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }
    .dash-date {
        font-size: 11px;
        color: #94a3b8;
        margin: 0;
    }
```

- [ ] **Step 2: Update `_render_dashboard_cards` to use new markup**

Find `_render_dashboard_cards` at line 1198. Inside the loop that builds each card, ensure each card includes the score in the `data-score` attribute and uses the new class structure. Replace the inner `st.markdown` for each card with:

```python
    st.markdown(
        f'<div class="dash-card" data-score="{score}">'
        f'<div class="dash-card-top">'
        f'<p class="dash-company">{company}</p>'
        f'<span class="dash-stars">{stars}</span>'
        f'</div>'
        f'<p class="dash-snippet">{snippet}</p>'
        f'<p class="dash-date">{date_str}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )
```

(If the function uses different variable names — `company_name`, `score_int`, etc. — adjust accordingly. The structure is what matters: top row with company + stars, snippet, date.)

- [ ] **Step 3: Visual check**

Run: `streamlit run app.py`
Expected: each dashboard card has a colored top stripe (Alkira blue for 5★, lighter blue for 4★, amber for 3★, gray for ≤2★). Hover lifts the card. Stars at top-right.

- [ ] **Step 4: Commit**

```bash
git add app.py
git commit -m "feat(dashboard): restyle cards with score color stripes and hover"
```

---

### Task 20: Restyle sidebar

**Files:**
- Modify: `app.py` (CSS only)

- [ ] **Step 1: Update sidebar CSS**

In `CUSTOM_CSS`, find the existing `.sb-user`, `.sb-avatar`, `.sb-email`, `.sb-title` rules. Update or replace with:

```css
    /* ── Sidebar ──────────────────────────────────── */
    [data-testid="stSidebar"] {
        background: #fff !important;
        border-right: 1px solid var(--alkira-border);
    }
    .sb-user {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 14px 8px;
        border-bottom: 1px solid var(--alkira-border);
        margin-bottom: 8px;
    }
    .sb-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: var(--alkira-blue);
        color: #fff;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
    }
    .sb-email {
        font-size: 12px;
        color: var(--alkira-ink);
        font-weight: 500;
    }
    .sb-title {
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--alkira-muted);
        margin: 12px 8px 6px;
    }

    [data-testid="stSidebar"] .stButton > button {
        background: #fff !important;
        color: var(--alkira-ink) !important;
        border: 1px solid var(--alkira-border) !important;
        border-radius: 10px !important;
        padding: 10px 12px !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        text-align: left !important;
        margin-bottom: 6px !important;
        transition: border-color 120ms ease, background 120ms ease;
    }
    [data-testid="stSidebar"] .stButton > button:hover {
        border-color: var(--alkira-blue) !important;
        background: #f8faff !important;
    }
```

- [ ] **Step 2: Visual check**

Run: `streamlit run app.py`
Expected: sidebar has Alkira-blue avatar circle, brief tiles in a clean list, hover hints in branded blue.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "feat(sidebar): restyle in branded blue"
```

---

## Phase 6 — Final integration

### Task 21: End-to-end manual verification

**Files:**
- No changes

- [ ] **Step 1: Run the app fresh**

Run: `streamlit run app.py`

- [ ] **Step 2: Verify each surface**

Walk through and confirm:

- [ ] Welcome screen / auth gate still works (no regressions)
- [ ] Dashboard hero shows Alkira logo + new gradient
- [ ] Search input is pill-shaped + Generate button is Alkira blue
- [ ] Dashboard cards have score color stripes + hover lift
- [ ] Sidebar restyled in branded blue
- [ ] Click a brief → bento layout renders (hero / score+infra / signals / 3 entry points / conv starters / references)
- [ ] "↓ Download PDF" button visible under hero
- [ ] Click Download → file downloads as `AlkiraBrief_<Company>_<YYYY-MM>.pdf`
- [ ] Open the PDF → 2-3 pages, all sections present, header (ALKIRA + CONFIDENTIAL + month-year) and footer (page N of M + generated date) on every page
- [ ] "Update Brief" button still re-runs the agent and replaces the brief in DB
- [ ] Generate a brand new brief → confirm it renders in bento + downloads as PDF

- [ ] **Step 3: Run all tests**

Run: `python -m pytest tests/ -v`
Expected: all tests PASS.

- [ ] **Step 4: If any visual issue is found, fix inline and commit per fix**

For each fix:
```bash
git add <file>
git commit -m "fix(brief|dashboard|pdf): <short description>"
```

---

### Task 22: Deploy to Streamlit Cloud

**Files:**
- No changes (deploys via existing GitHub auto-deploy)

- [ ] **Step 1: Push to main**

```bash
git push origin main
```

- [ ] **Step 2: Watch Streamlit Cloud build**

Open the Streamlit Cloud dashboard. Watch the build log to confirm `fpdf2` installs.
Expected: deploy succeeds. Live app reflects new bento layout + Download PDF.

- [ ] **Step 3: Live smoke test**

In the deployed app: log in, open a brief, click Download PDF. Open the downloaded file.
Expected: PDF downloads + opens correctly, branded header/footer on every page.

- [ ] **Step 4: If any environment-specific issue surfaces, fix and re-push**

Most likely issue: `pdf.py` lazy-imports `app.py` parsers. If Streamlit Cloud's import order surfaces a circular-import error, move the parsers to a new `parsers.py` module that both `app.py` and `pdf.py` import. (This is a contingency — the lazy `_import_app_parsers` helper in Task 9 should prevent it.)

---

## Self-Review Notes

**Spec coverage check:**

| Spec section | Implementation task(s) |
|---|---|
| Architecture | Task 1, 5 (file creation) |
| Brief renderer (web bento) | Task 3, 4 (parsers) + Task 14, 15 (CSS + renderer) |
| Dashboard restyle | Task 17, 18, 19, 20 |
| PDF generator | Task 5-13 |
| Design system tokens | Task 2 (CSS), Task 5 (Python constants) |
| Filename convention | Task 5 (`build_filename`) |
| Inter font embedding | NOT IMPLEMENTED — using Helvetica per plan header note. Follow-up if needed. |
| Out-of-scope items | Confirmed not implemented (auth gate, schema, prompt, ZoomInfo, etc.) |
| Manual verification | Task 21 |

**Type/name consistency:**

- `extract_entry_points()` → returns `list[dict]` with keys `heading`, `signal`, `solution`, `proof` — used identically in Task 11 (`_draw_entry_points`) and Task 15 (web bento)
- `extract_infra_cells()` → returns dict with keys `cloud_platforms`, `on_prem`, `deployment`, `complexity` — used identically in Task 9 (PDF) and Task 15 (web)
- `build_filename(company, period)` → consistent signature in Task 5 (definition) and Task 16 (call site)
- `generate_brief_pdf(brief_md, company, score, generated_at)` → consistent signature throughout

**Placeholder scan:** No TBDs / TODOs / "implement later" markers. All steps include actual code. Task 22's contingency note is concrete (move to `parsers.py` if circular import surfaces) — not a placeholder.

**Open follow-ups (after this plan ships):**

- Inter TTF embedding for PDF (deferred per plan header note)
- Optional: smoke test that opens the generated PDF with `pypdf` to assert page count
- Optional: extract dashboard card rendering to `components/` if `app.py` continues to grow
