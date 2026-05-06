# Bento Brief Layout + PDF Export — Design

**Date:** 2026-05-06
**Status:** Approved (brainstorming complete, awaiting implementation plan)
**Owner:** Blake Hays

---

## 1. Problem

Two related issues with the current Alkira Brief Generator:

1. **Dashboard reads as generic SaaS.** The structure is sound (hero, search, recent briefs grid, sidebar history), but the visual treatment is competent rather than distinctive. Partner reps and CAMs are looking at this app daily — it should feel like a premium intelligence tool, not a stock template.

2. **No PDF export.** Briefs need to be shareable as standalone artifacts. Partner reps want to forward a brief to a colleague, attach it to an email, or print it for a customer meeting. Today the only sharing path is "screenshot the page."

A previous PDF attempt was abandoned because the chosen approach (likely WeasyPrint) was slow on Streamlit Cloud. We need an approach that works reliably in the existing deployment.

## 2. Decisions made during brainstorming

| Decision | Choice | Why |
|---|---|---|
| Visual direction | **Bento** (modular tiles with depth) | Tech-forward, scannable, varied tile sizes give visual rhythm |
| Color treatment | **Branded blue** (light surface + Alkira navy/electric blue) | Inherits existing brand; web and PDF use one palette |
| Brief layout philosophy | **Full bento** (sections become tiles) | Commits to the design direction; matches dashboard |
| PDF library | **fpdf2** (programmatic, pure Python) | ~500ms, no system deps, reliable on Streamlit Cloud |
| Logo asset | Real Alkira SVG (provided by user, copied to `assets/alkira-logo.svg`) | Brand authenticity |
| Stay on Streamlit | **Yes** | Refactor to React/Next.js is 2-3 weeks of rebuild for ~hours of PDF work |

## 3. Architecture

```
alkira-brief-agent/
├── app.py              [MAJOR EDIT] new brief renderer + restyled dashboard + Download PDF wiring
├── pdf.py              [NEW]        fpdf2 brief generator
├── assets/
│   ├── alkira-logo.svg [NEW]        brand logo (already copied)
│   └── fonts/
│       ├── Inter-Regular.ttf [NEW] embedded for PDF
│       └── Inter-Bold.ttf    [NEW] embedded for PDF
├── requirements.txt    [EDIT]       add fpdf2>=2.7.9
└── (everything else unchanged)
```

### Untouched

- `db.py` (no schema changes)
- `system_prompt.py` (same agent prompt)
- `skills/*` (same content; rendering changes, not content)
- `setup_skills.py`, `setup_agent.py`
- Supabase `briefs` table schema

The agent's markdown output is **unchanged**. We change the renderer (web bento) and add a new generator (fpdf2 PDF). Both consume the same brief markdown via the existing parsing functions.

## 4. Brief renderer — web (bento layout)

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│ HERO TILE (full width)                                      │
│ Company name, header pills, date, "Download PDF" button     │
└─────────────────────────────────────────────────────────────┘
┌──────────────────┬──────────────────────────────────────────┐
│ SCORE TILE       │ INFRASTRUCTURE 4-CELL                    │
│ (1/3 wide,       │ ┌──────────────┬──────────────┐          │
│  gradient blue)  │ │ Cloud        │ On-Prem /    │          │
│                  │ │ Platforms    │ Hybrid       │          │
│ Big "4"          │ ├──────────────┼──────────────┤          │
│ ★★★★☆           │ │ Deployment   │ Resulting    │          │
│ 3-4 sentence     │ │ Model        │ Complexity   │          │
│ rationale        │ └──────────────┴──────────────┘          │
└──────────────────┴──────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ SIGNALS & TIMING (full width, white tile)                   │
│ • bullet 1                                                  │
│ • bullet 2                                                  │
│ • bullet 3                                                  │
│ • bullet 4                                                  │
└─────────────────────────────────────────────────────────────┘
┌──────────────┬──────────────┬──────────────────────────────┐
│ ENTRY 01     │ ENTRY 02     │ ENTRY 03                     │
│ orange top   │ orange top   │ orange top                   │
│ Signal:      │ Signal:      │ Signal:                      │
│ Solution:    │ Solution:    │ Solution:                    │
│ Proof:       │ Proof:       │ Proof:                       │
└──────────────┴──────────────┴──────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ CONVERSATION STARTERS (full width, dark navy tile)          │
│ Stakeholders: ...                                           │
│ ★ Best First Question: Lead with #X — ...                   │
│ 1. Question                                                 │
│    (You're listening for: ...)                              │
│ 2. Question                                                 │
│    (You're listening for: ...)                              │
│ ... (5 total)                                               │
│ Validate Early:                                             │
│ • Bullet                                                    │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ REFERENCES (full width, footer-style tile)                  │
│ [1] Description — https://...                               │
│ [2] Description — https://...                               │
└─────────────────────────────────────────────────────────────┘
```

### Tile-to-section mapping

| Tile | Source markdown section | Parsing function |
|---|---|---|
| Hero | Title + Company Header lines | `extract_company_header()` (existing) |
| Score | "Alkira Fit Score" line + 3-4 sentence rationale | `extract_score()` (existing) + section after |
| Infrastructure | "Infrastructure Snapshot" with bold sub-labels | `extract_section("Infrastructure Snapshot")` + new sub-parser |
| Signals | "Signals & Timing" bulleted list | `extract_section("Signals & Timing")` |
| Entry Points | "Three Alkira Entry Points" split by `**N. heading**` | new `extract_entry_points()` |
| Conversation Starters | "Conversation Starters" section | `extract_section("Conversation Starters")` |
| References | "References" section | `extract_section("References")` |

### New helper functions in `app.py`

```python
def extract_entry_points(brief_md: str) -> list[dict]:
    """Split entry points section into 3 dicts with signal, solution, proof keys."""

def extract_infra_cells(brief_md: str) -> dict:
    """Parse the 4 bold sub-labels from Infrastructure Snapshot."""

def render_brief_bento(brief_md: str, meta_right: str = "", show_update: bool = False) -> None:
    """Replace render_brief_display(); orchestrate tile rendering."""
```

### Fallback behavior

If a section is missing or malformed, the tile renders an empty state ("No data available") instead of crashing. The whole brief still renders — partial bento beats a blank page.

### Information density preserved

All current content sections are preserved:

- Full company header (HQ, revenue, employees, industry, markets, ownership)
- 3-4 sentence score rationale
- All 4 infrastructure subsections
- 4 signals & timing bullets
- 3 entry points with full Signal/Solution/Proof for each
- Stakeholders, Best First Question, 5 questions with parentheticals, Validate Early
- Numbered references with URLs

Bento is a **rendering choice**, not a content choice. The skill prompt and research checklist are unchanged.

## 5. Dashboard restyle

Same layout structure, refreshed visual treatment. Nothing structural changes.

### Hero

- Replace text "CHANNEL SALES INTELLIGENCE" badge with Alkira logo SVG (top-left, ~28px tall)
- Background gradient: `linear-gradient(135deg, #0a1f44 0%, #2D58F2 100%)`
- Same headline ("Alkira Brief Generator") and tagline copy
- Same rounded corners and padding

### Search

- Same form structure (input + Generate submit button)
- Pill input with subtle blue glow on focus (`#2D58F2`)
- Generate button: solid `#2D58F2` background, white text

### Recent briefs cards

- Same 2x2 grid, same min-height (130px), same line-clamp-1 on company names
- Card background: white with `1px solid #e0e7ff` border + soft shadow
- **Star row** moves to top-right corner of card (currently below name)
- **Score color stripe** (3px top stripe), color-coded:
  - 5 stars → `#2D58F2`
  - 4 stars → `#60a5fa`
  - 3 stars → `#fbbf24`
  - 2-1 stars → `#cbd5e1`
- Snippet: muted `#475569`, line-clamp-2
- Date: small, `#94a3b8`
- Hover: subtle lift (`translate-y -1px`) + stronger shadow
- Open button stays full-width at bottom: `#2D58F2` bg + white text

### Sidebar

- User avatar circle: `#2D58F2` background with first initial
- "Your Briefs" header: small caps, `#7F7F7F`
- Each brief row: white tile with subtle border, company name + stars
- Active brief: left border accent `#2D58F2`, slightly darker background
- Existing star format kept

### Empty state

Restyled in branded blue (subtle illustration or icon). Existing copy unchanged.

### Not changing

- Auth gate / welcome screen
- Sidebar list ordering (still by score desc)
- "How it works" section for first-time users
- Form / submit logic

## 6. PDF generator (`pdf.py`)

### Public API

```python
def generate_brief_pdf(
    brief_md: str,
    company: str,
    score: int,
    generated_at: datetime | None = None,
) -> bytes:
    """Render brief markdown as a print-optimized PDF. Returns PDF bytes."""
```

Streamlit consumption: `st.download_button(data=pdf_bytes, file_name=...)`.

### Page layout

**US Letter** (8.5" × 11"), portrait, 0.5" margins. 2-3 pages typical.

**Page 1 — Overview:** Header (logo + meta) → Hero (company name + pills) → Score tile (1/3 width) + Infrastructure 4-cell (2/3 width) → Signals & Timing (full width) → Footer.

**Page 2 — Entry Points + Conversation Starters:** Header → Three Entry Points (3 columns, orange top stripes) → Conversation Starters (dark navy fill) → Footer.

**Page 3 (only if needed) — References:** Header → numbered references with URLs → Footer.

If short, references can fit on page 2. fpdf2 auto page breaks handle this naturally.

### Header & footer (every page)

- **Header:** Alkira logo (left, rasterized PNG) + `CONFIDENTIAL` + month/year (right)
- **Footer:** `Page N of M` (left) + `Generated YYYY-MM-DD` (right) + hairline rule above

### Color palette (no gradients)

| Token | Hex | Use |
|---|---|---|
| `ALKIRA_BLUE` | `#2D58F2` | Score tile fill, accent rules, links |
| `ALKIRA_NAVY` | `#0A1F44` | Conversation Starters tile |
| `ALKIRA_INK` | `#211F1F` | Body text |
| `ALKIRA_MUTED` | `#7F7F7F` | Header/footer meta |
| `ALKIRA_BORDER` | `#E0E7FF` | Tile borders |
| `ALKIRA_WHITE` | `#FFFFFF` | Tile fills |
| `ALKIRA_ORANGE` | `#FB923C` | Entry point top stripe |
| `ALKIRA_AMBER` | `#FBBF24` | Stars |

### Typography

Inter embedded via TTF. Sizes:

- H1 company name: 22pt bold
- H2 section labels: 9pt bold caps
- Body: 10pt regular
- Caption/footer: 8pt regular
- Stars: 11pt

### Internal helpers in `pdf.py`

```python
def _draw_header(pdf, generated_at): ...
def _draw_footer(pdf, page_num, total_pages, generated_at): ...
def _draw_hero(pdf, company, header_pills): ...
def _draw_score_tile(pdf, score, rationale, x, y, w, h): ...
def _draw_infra_grid(pdf, infra_cells, x, y, w, h): ...
def _draw_signals(pdf, signal_bullets): ...
def _draw_entry_points(pdf, entry_points): ...
def _draw_conversation_starters(pdf, stakeholders, best_first, questions, validate): ...
def _draw_references(pdf, refs): ...
```

Each helper takes pre-parsed data extracted from the brief markdown using the same parsers as the web renderer. PDF logic is purely presentational.

### Filename

`AlkiraBrief_<Company>_<YYYY-MM>.pdf`

- Sanitize company name: strip punctuation, replace spaces with hyphens, max 40 chars
- Examples: `AlkiraBrief_McKesson-Corporation_2026-04.pdf`, `AlkiraBrief_PepsiCo_2026-04.pdf`

### Performance & failure modes

- Target: ~500ms generation
- On exception (corrupted brief, missing section): show error toast in Streamlit; don't crash the app
- Logo embedded once at PDF init; rasterized to PNG since fpdf2 doesn't render SVG natively

## 7. Design system (shared tokens)

### CSS variables (in `app.py`'s injected stylesheet)

```css
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

### Python constants in `pdf.py`

```python
ALKIRA_BLUE   = (45, 88, 242)
ALKIRA_NAVY   = (10, 31, 68)
ALKIRA_INK    = (33, 31, 31)
ALKIRA_MUTED  = (127, 127, 127)
ALKIRA_ORANGE = (251, 146, 60)
ALKIRA_AMBER  = (251, 191, 36)
ALKIRA_BORDER = (224, 231, 255)
ALKIRA_WHITE  = (255, 255, 255)
```

### Reusable web tile classes

| Class | Use |
|---|---|
| `.tile` | base: white surface, border, radius, shadow |
| `.tile.gradient` | score tile: linear-gradient navy → blue, white text |
| `.tile.dark` | conversation starters: solid navy, white text, orange accent label |
| `.tile.entry` | entry point: white + 3px orange top stripe |

### Typography hierarchy

| Element | Web (px) | PDF (pt) | Weight |
|---|---|---|---|
| Company name (hero) | 28 | 22 | 700 |
| Section label (caps) | 11 | 9 | 700 |
| Body | 14 | 10 | 400 |
| Caption / footer | 12 | 8 | 400 |
| Stars | 16 | 11 | — |

### Font loading

- **Web:** Inter via Google Fonts CDN (already present)
- **PDF:** Inter TTFs in `assets/fonts/Inter-Regular.ttf` + `Inter-Bold.ttf` (committed, ~280KB total)

## 8. Out of scope

- Auth gate / welcome screen redesign
- Skill prompt or research checklist changes
- Supabase schema changes
- ZoomInfo integration (separate feature)
- Moving off Streamlit
- Stats bar (already removed; stays out)
- Asymmetric bento on dashboard (uniform grid kept for predictability)
- Email-the-brief button (out for now; PDF download covers sharing)

## 9. Testing

Manual verification (no automated test suite for this app yet):

1. Generate a brief end-to-end → confirm bento layout renders correctly with all sections present
2. Click into a brief from dashboard → confirm tile rendering matches design
3. Click "Download PDF" → confirm file downloads as `AlkiraBrief_<Company>_<YYYY-MM>.pdf`
4. Open PDF → confirm 2-3 pages, all sections present, header/footer correct, brand colors match
5. Test with a long brief (3+ pages) and a short brief (fits on 2)
6. Test with a brief missing a section → confirm fallback empty state renders, no crash
7. Test on Streamlit Cloud deployment after merge → confirm PDF generation completes in <1s

## 10. Open questions

None. All decisions resolved during brainstorming.

## 11. Implementation order (preview, full plan in writing-plans output)

1. Add `fpdf2` to `requirements.txt`; commit Inter TTFs
2. Create `pdf.py` with stub generator + helper signatures
3. Implement `pdf.py` helpers one-by-one (header/footer → hero → score → infra → signals → entry points → conversation starters → references)
4. Wire `pdf.py` into `app.py` via `st.download_button`
5. Add new helper parsers in `app.py` (`extract_entry_points`, `extract_infra_cells`)
6. Replace `render_brief_display()` with `render_brief_bento()`
7. Add new CSS tile classes
8. Restyle hero, search, sidebar, dashboard cards
9. Manual end-to-end verification
10. Commit and deploy
