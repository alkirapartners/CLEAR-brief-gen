"""The brief PDF's look: the brief page's colours and type, scaled for a US Letter sheet.

Colours are the page's design tokens (web/styles/tokens.css in the front
end). A PDF has no cheap transparency, so a token the page uses at an
opacity is mixed here with the surface it sits on. Lengths are millimetres;
type sizes are points.
"""

import pdf_fonts
from pdf_text import Chip, Color, Style

# ── The sheet ────────────────────────────────────────────────────────────────
PAGE_W = 215.9
PAGE_H = 279.4
MARGIN_X = 14.0
CONTENT_W = PAGE_W - 2 * MARGIN_X
# Content sits between the running header and the running footer.
CONTENT_TOP = 23.5
CONTENT_BOTTOM = PAGE_H - 14.5
HEADER_Y = 9.5
LOGO_H = 8.6
FOOTER_Y = PAGE_H - 10.2


def mix(color: Color, base: Color, share: float) -> Color:
    """``color`` laid over ``base`` at an opacity of ``share``."""
    red, green, blue = (round(under + (over - under) * share) for over, under in zip(color, base))
    return red, green, blue


# ── Colour tokens ────────────────────────────────────────────────────────────
CANVAS: Color = (245, 245, 243)
SURFACE: Color = (255, 255, 255)
SUNKEN: Color = (239, 239, 237)
AMBIENT: Color = (13, 13, 14)
INK: Color = (20, 20, 20)
INK_2: Color = (95, 102, 115)
INK_3: Color = (156, 163, 175)
ON_AMBIENT: Color = (244, 244, 245)
ON_AMBIENT_2: Color = (161, 161, 170)
ACCENT: Color = (45, 88, 242)
ACCENT_SOFT: Color = (124, 155, 255)
POSITIVE: Color = (21, 128, 61)
POSITIVE_TINT: Color = (220, 252, 231)
WARNING: Color = (180, 83, 9)
WARNING_FILL: Color = (245, 158, 11)
WARNING_TINT: Color = (254, 243, 199)
NEGATIVE: Color = (190, 18, 60)
NEGATIVE_TINT: Color = (255, 228, 230)

# Tokens the page uses at an opacity, on the surface each sits on.
LINE = mix(INK, SURFACE, 0.09)
LINE_ON_CANVAS = mix(INK, CANVAS, 0.10)
DASH_ON_CANVAS = mix(INK, CANVAS, 0.26)
ACCENT_TINT = mix(ACCENT, SURFACE, 0.10)
ACCENT_WASH = mix(ACCENT, SURFACE, 0.07)
POSITIVE_HALO = mix(POSITIVE, SURFACE, 0.18)
TERM_TINT = mix(INK, SURFACE, 0.06)
HATCH = mix(INK, SUNKEN, 0.07)
AMBIENT_LINE = mix(SURFACE, AMBIENT, 0.12)
AMBIENT_PILL = mix(SURFACE, AMBIENT, 0.13)
AMBIENT_TRACK = mix(SURFACE, AMBIENT, 0.16)
AMBIENT_WEAK = mix(SURFACE, AMBIENT, 0.50)
AMBIENT_GLOW = mix(ACCENT, AMBIENT, 0.42)
ON_AMBIENT_BODY = mix(ON_AMBIENT, AMBIENT, 0.82)
ON_AMBIENT_QUIET = mix(ON_AMBIENT, AMBIENT, 0.66)
TRACK = mix(INK, SURFACE, 0.10)
TRACK_ON_CANVAS = mix(INK, CANVAS, 0.10)

# ── Shape and rhythm ─────────────────────────────────────────────────────────
PANEL_RADIUS = 5.0
CARD_RADIUS = 4.0
INNER_RADIUS = 2.6
CARD_PAD = 5.0
HAIRLINE = 0.2
# Between the big parts of the page, and between cards that belong together.
SECTION_GAP = 6.4
CARD_GAP = 3.4

# ── Type ─────────────────────────────────────────────────────────────────────
COMPANY = Style(pdf_fonts.DISPLAY, 27, INK, tracking=-0.026, leading=1.08)
SECTION = Style(pdf_fonts.DISPLAY, 16, INK, tracking=-0.022, leading=1.15)
HEADING = Style(pdf_fonts.SEMIBOLD, 12, INK, tracking=-0.018, leading=1.25)
ANGLE_TITLE = Style(pdf_fonts.SEMIBOLD, 12.5, INK, tracking=-0.018, leading=1.26)
QUESTION = Style(pdf_fonts.MEDIUM, 10, INK, tracking=-0.006, leading=1.32)
BODY = Style(pdf_fonts.REGULAR, 8.4, INK, leading=1.42)
BODY_MEDIUM = Style(pdf_fonts.MEDIUM, 8.4, INK, leading=1.42)
BODY_MUTED = Style(pdf_fonts.REGULAR, 8.4, INK_2, leading=1.42)
FACT = Style(pdf_fonts.REGULAR, 8.2, INK, leading=1.4)
SMALL = Style(pdf_fonts.REGULAR, 7.6, INK_2, leading=1.4)
SMALL_INK = Style(pdf_fonts.MEDIUM, 7.6, INK, leading=1.4)
NAME = Style(pdf_fonts.SEMIBOLD, 9.4, INK, leading=1.3)
MICRO = Style(pdf_fonts.SEMIBOLD, 6.2, INK_2, tracking=0.09, leading=1.3)
MICRO_ACCENT = Style(pdf_fonts.SEMIBOLD, 6.2, ACCENT, tracking=0.09, leading=1.3)
STAMP = Style(pdf_fonts.MEDIUM, 7.0, INK_2, leading=1.3)
PILL = Style(pdf_fonts.MEDIUM, 6.9, INK_2, leading=1.3)
NUMBER = Style(pdf_fonts.MONO_MEDIUM, 6.6, INK_2, leading=1.3)
TERM = Style(pdf_fonts.MONO_MEDIUM, 7.3, INK, leading=1.42)
CHROME = Style(pdf_fonts.REGULAR, 7.0, INK_2, leading=1.3)

# On the dark panel and the dark proof plate.
EYEBROW = Style(pdf_fonts.SEMIBOLD, 6.2, ACCENT_SOFT, tracking=0.09, leading=1.3)
SCORE = Style(pdf_fonts.DISPLAY, 38, ON_AMBIENT, tracking=-0.03, leading=1.0)
SCORE_SCALE = Style(pdf_fonts.MEDIUM, 11, ON_AMBIENT_2, leading=1.0)
VERDICT = Style(pdf_fonts.REGULAR, 8.4, ON_AMBIENT_BODY, leading=1.44)
LEAD = Style(pdf_fonts.DISPLAY_MEDIUM, 13, ON_AMBIENT, tracking=-0.016, leading=1.28)
LEAD_REST = Style(pdf_fonts.DISPLAY_MEDIUM, 13, ON_AMBIENT_QUIET, tracking=-0.016, leading=1.28)
ON_DARK_MEDIUM = Style(pdf_fonts.MEDIUM, 8.6, ON_AMBIENT, leading=1.42)
CUSTOMER = Style(pdf_fonts.DISPLAY, 15, ON_AMBIENT, tracking=-0.024, leading=1.12)
QUALIFIER = Style(pdf_fonts.MEDIUM, 7.6, ON_AMBIENT_2, leading=1.4)
RESULT = Style(pdf_fonts.REGULAR, 8.8, ON_AMBIENT_BODY, leading=1.42)
RESULT_NUMBER = Style(pdf_fonts.SEMIBOLD, 8.8, ACCENT_SOFT, leading=1.42)
FIGURE = Style(pdf_fonts.MONO_MEDIUM, 26, INK, tracking=-0.03, leading=1.0)

# ── Pills and chips ──────────────────────────────────────────────────────────
PILL_HEIGHT = 4.5
PILL_PAD = 1.9
SOURCE_CHIP = Chip(fill=SUNKEN, pad=1.25, height=3.7)
TERM_CHIP = Chip(fill=TERM_TINT, pad=0.6, height=3.8)


def pill(fill: Color, border: Color | None = None) -> Chip:
    return Chip(fill=fill, pad=PILL_PAD, height=PILL_HEIGHT, border=border)


def toned(style: Style, color: Color) -> Style:
    """The same type in another colour."""
    return Style(style.face, style.size, color, style.tracking, style.leading)
