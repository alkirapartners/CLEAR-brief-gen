"""PDF generator for Alkira opportunity briefs.

Uses fpdf2 (programmatic, pure Python). Mirrors the bento web layout
in a print-optimized form. See docs/superpowers/specs/2026-05-06-bento-brief-pdf-export-design.md.
"""

from __future__ import annotations

import re
from datetime import datetime

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


# ── Unicode → latin-1 sanitization ───────────────────────────────
# fpdf2's core Helvetica font is latin-1 only. Map common typographic
# characters to ASCII equivalents so any Unicode char in brief content
# (em-dashes, smart quotes, stars, bullets) renders cleanly.

_UNICODE_MAP = {
    "–": "-",     # en-dash –
    "—": "--",    # em-dash —
    "―": "--",    # horizontal bar ―
    "‘": "'",     # left single quote ‘
    "’": "'",     # right single quote ’
    "‚": ",",     # single low-9 quote ‚
    "“": '"',     # left double quote “
    "”": '"',     # right double quote ”
    "„": '"',     # double low-9 quote „
    "…": "...",   # horizontal ellipsis …
    "•": "-",     # bullet •
    "‣": "-",     # triangular bullet ‣
    "◦": "-",     # white bullet ◦
    "⁃": "-",     # hyphen bullet ⁃
    "→": "->",    # rightwards arrow →
    "←": "<-",    # leftwards arrow ←
    "★": "*",     # black star ★
    "☆": "-",     # white star ☆ (used as empty in our score)
    "✓": "v",     # check mark ✓
    "✗": "x",     # ballot x ✗
    " ": " ",     # non-breaking space
    "​": "",      # zero-width space
    " ": " ",     # thin space
    " ": " ",     # narrow no-break space
}


def _safe_text(s: str) -> str:
    """Map common Unicode chars to latin-1 equivalents for fpdf2 core fonts.

    Anything not in the map and not in latin-1 is replaced with a
    question mark (the latin-1 'replacement' fallback). This is a one-way
    sanitization — the goal is to never crash fpdf2 on user content.
    """
    if not s:
        return ""
    # Apply explicit map first
    for ch, replacement in _UNICODE_MAP.items():
        if ch in s:
            s = s.replace(ch, replacement)
    # Catch anything else not encodable in latin-1
    try:
        s.encode("latin-1")
        return s
    except UnicodeEncodeError:
        return s.encode("latin-1", errors="replace").decode("latin-1")


# ── Filename helper ──────────────────────────────────────────────

_FILENAME_MAX = 40


def build_filename(company: str, period: str) -> str:
    """Build the PDF filename: AlkiraBrief_<sanitized-company>_<YYYY-MM>.pdf.

    Strips non-ASCII chars and punctuation (incl. underscores, our delimiter),
    replaces spaces with hyphens, truncates company to 40 chars. Falls back to
    "Company" sentinel for empty/all-punctuation/whitespace-only input.
    """
    cleaned = re.sub(r"[^A-Za-z0-9\s-]", "", company)   # ASCII-only, drop punctuation + underscores
    cleaned = re.sub(r"\s+", "-", cleaned.strip())      # spaces → hyphens
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")    # collapse hyphens
    if not cleaned:
        cleaned = "Company"
    if len(cleaned) > _FILENAME_MAX:
        cleaned = cleaned[:_FILENAME_MAX].rstrip("-")
    return f"AlkiraBrief_{cleaned}_{period}.pdf"


# ── PDF subclass with branded header + footer ──────────────────


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


# ── Hero block ───────────────────────────────────────────────────


def _draw_hero(pdf: _BriefPDF, company: str, header_pills: str) -> None:
    """Draw the company-name hero block at top of page 1.

    `header_pills` is the original pipe-delimited line, e.g.
    'HQ: Irving, TX | Revenue: $309B | Employees: 51K'.
    """
    pdf.set_x(12.7)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*ALKIRA_INK)
    pdf.cell(0, 10, _safe_text(company) or "Untitled Brief", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(1)
    pdf.set_x(12.7)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*ALKIRA_MUTED)
    cleaned = (header_pills or "").replace("**", "").strip()
    if cleaned:
        pdf.multi_cell(0, 5, _safe_text(cleaned))
    pdf.ln(3)


# ── Score tile ──────────────────────────────────────────────────


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

    # Stars (filled + empty) — _safe_text converts ★→* and ☆→-
    filled = "★" * max(0, min(5, score))
    empty = "☆" * max(0, 5 - max(0, min(5, score)))
    pdf.set_xy(x + 4, y + 26)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(w - 8, 5, _safe_text(filled + empty))

    # Rationale
    pdf.set_xy(x + 4, y + 33)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*ALKIRA_WHITE)
    text_w = w - 8
    text_h = h - 36
    # Use multi_cell for wrapped rationale; fpdf2 will clip to height.
    pdf.multi_cell(text_w, 4, _safe_text((rationale or "").strip()[:480]))


# ── Infrastructure 2x2 grid ─────────────────────────────────────


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
        pdf.multi_cell(half_w - 2 * pad, 3.6, _safe_text((body or "—").strip()[:360]))


# ── Signals & References tiles ──────────────────────────────────


def _draw_signals(pdf: _BriefPDF, signals_md: str) -> None:
    """Draw the Signals & Timing tile (full width, white)."""
    if not signals_md.strip():
        return

    w = 190.5

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
        pdf.cell(3, 4.5, "-")
        pdf.multi_cell(w - 5, 4.5, _safe_text(line))
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
        # Lines look like "[1] Description -- https://..."
        pdf.multi_cell(0, 4, _safe_text(line))


# ── Three Alkira Entry Points (3-column row) ────────────────────


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
        pdf.multi_cell(tile_w - 2 * pad, 4.5, _safe_text(point.get("heading", ""))[:80])

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
            pdf.multi_cell(tile_w - 2 * pad, 3.6, _safe_text(point.get(body_key, "—"))[:240])
            cy = pdf.get_y() + 1

    # Move below the row
    pdf.set_y(y + tile_h + 4)


# ── Public API (placeholder body — fleshed out in later tasks) ──

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

    # Parse header (uses app.py parsers — imported lazily to avoid circular deps)
    from app import extract_company_header
    company_name, stats_line = extract_company_header(brief_md)
    if not company_name:
        company_name = company

    _draw_hero(pdf, company_name, stats_line)

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

    # Infrastructure grid (right of score tile, same height)
    from app import extract_infra_cells
    infra_w = content_w - score_w - 4
    infra_x = score_x + score_w + 4
    cells = extract_infra_cells(brief_md)
    _draw_infra_grid(pdf, cells, infra_x, score_y, infra_w, score_h)

    # Move below the score+infra row
    pdf.set_y(score_y + score_h + 4)

    # Signals & Timing tile (full width)
    from app import extract_section
    signals = extract_section(brief_md, "Signals & Timing") or extract_section(brief_md, "Signals and Timing")
    _draw_signals(pdf, signals)

    from app import extract_entry_points
    points = extract_entry_points(brief_md)
    _draw_entry_points(pdf, points)

    return bytes(pdf.output())
