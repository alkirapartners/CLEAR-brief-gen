"""The top of the brief PDF: whose brief it is, then the verdict on the one dark panel."""

from fpdf import FPDF

import export_content
import i18n
import pdf_canvas as canvas
import pdf_parts as parts
import pdf_theme as theme
from pdf_canvas import Part
from pdf_flow import Block
from pdf_parts import Context
from pdf_text import Run

# The masthead: the company on the left, what this document is on the right.
ASIDE_W = 56.0
ASIDE_TOP = 2.9
SEPARATOR = "   ·   "
# The verdict panel: the score and why on the left, what to open with on the right.
PANEL_PAD = 6.4
SCORE_SHARE = 0.48
GUTTER = 7.0
BAND_PAD = 3.2
BAND_LABEL_W = 38.0
TICK = (1.5, 6.4)
TICK_GAP = 1.15
GLOW_REACH = 96.0
# From the foot of the score's line up to the foot of the numeral, which has no descender.
NUMERAL_FOOT = 0.2


def _identity_runs(identity: export_content.Identity) -> list[Run]:
    """The entity, how it is owned and its site, with a dot between them."""
    runs: list[Run] = []
    facts = [Run(fact, theme.SMALL_INK if index == 0 and len(identity.facts) > 1 else theme.SMALL)
             for index, fact in enumerate(identity.facts)]
    if identity.site:
        facts.append(Run(identity.site, theme.SMALL, link=identity.site_url))
    for fact in facts:
        if runs:
            runs.append(Run(SEPARATOR, theme.toned(theme.SMALL, theme.INK_3)))
        runs.append(fact)
    return runs


def _note_runs(note: str, labels: dict[str, str]) -> list[Run]:
    if not note:
        return []
    return [Run(f"{labels['identity']}: ", theme.SMALL_INK), Run(note, theme.SMALL)]


def _stat_pills(ctx: Context) -> Part:
    pills = [
        parts.capsule([Run(f"{name} ", theme.SMALL), Run(value, theme.SMALL_INK)], theme.CONTENT_W)
        for name, value in export_content.stat_pills_for(ctx.doc, ctx.labels)
    ]
    return parts.flow(pills, theme.CONTENT_W, gap_x=1.8, gap_y=1.8)


def _aside(ctx: Context) -> Part:
    """What the document is and when the research was done, set against the right margin."""
    researched = i18n.readable_date(ctx.doc["generated"], ctx.language)
    when = ctx.labels["researched_on"].format(date=researched) if researched else ""
    return canvas.stack(
        (0, canvas.text([Run(ctx.labels["brief_title"].upper(), theme.MICRO)], ASIDE_W, align="R")),
        (1.3, canvas.text([Run(when, theme.SMALL)], ASIDE_W, align="R")),
    )


def masthead(ctx: Context) -> Block:
    labels = ctx.labels
    name = ctx.doc["company"]["name"].strip() or labels["brief_title"]
    room = theme.CONTENT_W - ASIDE_W - GUTTER
    identity = export_content.identity(ctx.doc, labels)
    company = canvas.stack(
        (0, canvas.words(name, theme.COMPANY, room)),
        (2.2, canvas.text(_identity_runs(identity), room)),
        (1.2, canvas.text(_note_runs(identity.note, labels), room)),
    )
    top = canvas.beside((0, company), (theme.CONTENT_W - ASIDE_W, canvas.inset(_aside(ctx), top=ASIDE_TOP)))
    return parts.block(canvas.stack((0, top), (3.2, _stat_pills(ctx))), space_before=0)


# ── The verdict panel ────────────────────────────────────────────────────────

def _meter_fill(score: int) -> tuple[int, int, int]:
    if score >= export_content.STRONG_FROM:
        return theme.ACCENT_SOFT
    return theme.WARNING_FILL if score >= export_content.MODERATE_FROM else theme.AMBIENT_WEAK


def _score_row(ctx: Context, room: float) -> Part:
    """The score large, with its scale, its meter and how strong it is in words."""
    score = ctx.doc["fit"]["score"]
    figure = canvas.text([Run(str(score), theme.SCORE), Run(f" / {export_content.FIT_SCALE}", theme.SCORE_SCALE)], room)
    tier = canvas.text(
        [parts.pill(export_content.fit_label(score, ctx.labels), theme.ON_AMBIENT, theme.AMBIENT_PILL)], room,
    )
    tick_w, tick_h = TICK

    def paint(pdf: FPDF, x: float, y: float) -> None:
        figure.paint(pdf, x, y)
        foot = y + figure.height - NUMERAL_FOOT - tick_h - 2.1
        beside = x + figure.width + 5.0
        width = canvas.meter(pdf, beside, foot, score, TICK, TICK_GAP, _meter_fill(score), theme.AMBIENT_TRACK)
        tier.paint(pdf, beside + width + 3.2, foot + (tick_h - tier.height) / 2)

    return Part(figure.height, paint)


def _lead(ctx: Context, room: float) -> Part:
    """What to open with, the largest text on the panel, then whom to call a step quieter."""
    first, rest = export_content.split_lead(ctx.doc["fit"]["lead"])
    if not first:
        return canvas.EMPTY
    runs = [Run(first, theme.LEAD)] + ([Run(f" {rest}", theme.LEAD_REST)] if rest else [])
    return canvas.stack(
        (0, canvas.label(ctx.labels["lead"], theme.EYEBROW, room)),
        (3.8, canvas.text(runs, room)),
    )


def _band(ctx: Context, room: float) -> Part:
    """What the company runs, across the foot of the panel."""
    cloud_network = ctx.doc["stats"]["cloud_network"].strip()
    if not cloud_network:
        return canvas.EMPTY
    value = canvas.words(cloud_network, theme.ON_DARK_MEDIUM, room - BAND_LABEL_W)
    name = canvas.label(ctx.labels["stat_cloud_network"], theme.EYEBROW, BAND_LABEL_W)
    return canvas.beside((0, canvas.inset(name, top=1.25)), (BAND_LABEL_W, value))


def verdict(ctx: Context) -> list[Block]:
    """The thirty-second answer: the score and why, what to open with, and what the company runs."""
    inner = theme.CONTENT_W - 2 * PANEL_PAD
    # The rule between the two columns stands at the split, with a gutter on each side of it.
    split = PANEL_PAD + inner * SCORE_SHARE
    lead_w = inner * (1 - SCORE_SHARE) - GUTTER
    has_lead = bool(ctx.doc["fit"]["lead"].strip())
    score_w = inner * SCORE_SHARE - GUTTER if has_lead else inner
    score = canvas.stack(
        (0, canvas.label(ctx.labels["alkira_fit"], theme.EYEBROW, score_w)),
        (2.8, _score_row(ctx, score_w)),
        (3.4, canvas.words(ctx.doc["fit"]["verdict"], theme.VERDICT, score_w)),
    )
    lead = _lead(ctx, lead_w)
    band = _band(ctx, inner)
    top_h = max(score.height, lead.height) + 2 * PANEL_PAD
    height = top_h + (band.height + 2 * BAND_PAD if band.height else 0.0)

    def paint(pdf: FPDF, y: float) -> None:
        x, w = theme.MARGIN_X, theme.CONTENT_W
        canvas.fill_round(pdf, x, y, w, height, theme.PANEL_RADIUS, theme.AMBIENT)
        canvas.glow(pdf, (x, y, w, height), theme.PANEL_RADIUS, (x + w * 0.2, y + 6.0), GLOW_REACH,
                    theme.AMBIENT_GLOW, theme.AMBIENT)
        score.paint(pdf, x + PANEL_PAD, y + PANEL_PAD)
        if lead.height:
            canvas.upright(pdf, x + split, y + PANEL_PAD, top_h - 2 * PANEL_PAD, theme.AMBIENT_LINE)
            lead.paint(pdf, x + split + GUTTER, y + PANEL_PAD)
        if band.height:
            canvas.rule(pdf, x, y + top_h, w, theme.AMBIENT_LINE)
            band.paint(pdf, x + PANEL_PAD, y + top_h + BAND_PAD)

    return [Block(height, paint, space_before=5.0)]
