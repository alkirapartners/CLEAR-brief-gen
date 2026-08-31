"""PDF generator for Alkira opportunity briefs.

Uses fpdf2 (programmatic, pure Python). Renders the brief as a flowing
single-column document (header band + score badge + sections), mirroring the
on-screen layout. See docs/superpowers/specs/2026-06-08-document-brief-redesign-design.md.
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


def _iter_sections(body_md: str) -> list[tuple[str, str]]:
    """Split brief body markdown into (heading, body) pairs by ## / ### headings, in order."""
    parts = re.split(r"(?m)^[ \t]*#{2,3}[ \t]+(.+?)[ \t]*$", body_md)
    out: list[tuple[str, str]] = []
    it = iter(parts[1:])  # parts[0] is any pre-heading text; ignore it
    for title in it:
        body = next(it, "")
        out.append((title.strip(), body.strip()))
    return out


def _strip_md(s: str) -> str:
    r"""Strip basic inline markdown so PDF body text doesn't show literal markers.

    Handles ``**bold**``, ``__bold__``, ``*italic*``, ``_italic_``, ``\`code\```,
    and ``[text](url)`` (keeping just the link text). Also drops standalone
    horizontal rules (``---`` or ``***``) on their own lines, since the PDF
    has no equivalent visual primitive.
    """
    if not s:
        return ""
    # Strip **bold** and __bold__ -> bold
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    # Strip *italic* and _italic_ -> italic (but not bare * that was used for bullets)
    s = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"\1", s)
    s = re.sub(r"(?<!_)_([^_\n]+?)_(?!_)", r"\1", s)
    # Strip `code` -> code
    s = re.sub(r"`([^`]+?)`", r"\1", s)
    # Strip [text](url) -> text  (the body doesn't render hyperlinks)
    s = re.sub(r"\[([^\]]+?)\]\([^)]+?\)", r"\1", s)
    # Strip standalone horizontal rules (--- or ***) on their own lines
    s = re.sub(r"^\s*[-*]{3,}\s*$", "", s, flags=re.MULTILINE)
    return s


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


# ── Header band ─────────────────────────────────────────────────


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


# ── Generic section drawer ───────────────────────────────────────


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
            pdf.multi_cell(190.5 - 5.3, 4.6, _safe_text(text))
        else:
            pdf.set_x(12.7)
            pdf.multi_cell(0, 4.8, _safe_text(text))
        pdf.ln(0.6)


# ── Public API ───────────────────────────────────────────────────


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
