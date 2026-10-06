"""The company basics as the short pills at the top of the current brief page.

The page shows each stat in a pill of fixed height, so a value has to be a
few words: a city, one rounded figure, an industry. The brief document keeps
the full values. This module shortens them for that page only, and never
adds anything the document does not say.

The page was built for six stats. The document has five of them (it has no
"markets" value), so at most five pills are produced. The legal entity, the
ticker on its own and the cloud-and-network headline are never pills.
"""

import re

import ticker
from brief_doc import BriefDoc

Labels = dict[str, str]

# The longest value a pill can show on one line of a phone screen, beside its label.
MAX_PILL_CHARS = 36
CUT_MARK = "..."

_PARENTHESES = re.compile(r"\s*\([^)]*\)")
_POSTCODE = re.compile(r"\s+\d[\d-]{3,}$")
_STREET = re.compile(
    r"\b(?:street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|plaza|parkway|pkwy"
    r"|place|square|court|highway|hwy|suite|floor)\.?$",
    re.IGNORECASE,
)
_UNITED_STATES = frozenset({"united states", "united states of america", "usa", "us", "u.s.", "u.s.a."})

_UNITS: dict[str, float] = {
    "trillion": 1e12, "t": 1e12, "billion": 1e9, "bn": 1e9, "b": 1e9,
    "million": 1e6, "mm": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3,
}
_SCALES: tuple[tuple[float, str], ...] = ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K"))
_SYMBOLS: dict[str, str] = {"US$": "$", "USD": "$", "$": "$", "€": "€", "EUR": "€", "£": "£", "¥": "¥"}
_AMOUNT = re.compile(
    r"(?P<currency>US\$|USD|CNY|RMB|EUR|GBP|JPY|CAD|AUD|CHF|[$€£¥])?\s*"
    r"(?P<number>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<unit>trillion|billion|million|thousand|bn|mm|[TBMK])?(?![A-Za-z])"
    r"(?:\s*(?P<named>yuan|renminbi|euros?|dollars|pounds|yen)\b)?",
    re.IGNORECASE,
)
# A currency written as a word after the amount: "30.5 billion yuan".
_CURRENCY_WORDS: dict[str, str] = {
    "yuan": "CNY", "renminbi": "CNY", "euro": "EUR", "euros": "EUR", "dollars": "$",
    "pounds": "£", "yen": "¥",
}
_FISCAL_YEAR = re.compile(r"\bFY\s?(?:\d{4}|\d{2})\b", re.IGNORECASE)
_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
_ROUGHLY = re.compile(r"^(?:about|approximately|approx\.?|around|roughly|nearly|~)", re.IGNORECASE)
_HEADCOUNT = re.compile(
    r"^(?P<lead>about|approximately|approx\.?|around|roughly|nearly|over|more than|~)?\s*"
    r"(?P<number>\d[\d,]*\d|\d)\+?(?:\s+(?P<kind>full-time|part-time))?",
    re.IGNORECASE,
)
# A cut never ends on a word that only joins what was cut off.
_DANGLING_WORD = re.compile(r"\s+(?:and|or|of|the|with|for|in|to|a|an|&|y|de|del|la|el|con|en)$", re.IGNORECASE)
_FIRST_PHRASE = re.compile(r"[:;,(]|\s[-–]\s")


def _short(text: str) -> str:
    """The text when it fits a pill, or its first words with a mark that it was cut."""
    clean = " ".join(text.replace("|", "/").split())
    if len(clean) <= MAX_PILL_CHARS:
        return clean
    room = MAX_PILL_CHARS - len(CUT_MARK)
    kept = clean[:room].rsplit(" ", 1)[0].rstrip(" ,;:/-")
    return _DANGLING_WORD.sub("", kept) + CUT_MARK


def headquarters(text: str) -> str:
    """A city with its state or country: no street, no postcode, no second office."""
    first = _PARENTHESES.sub("", text).split(";")[0]
    parts = [_POSTCODE.sub("", part.strip()) for part in first.split(",")]
    places = [part for part in parts if part and not part[0].isdigit() and not _STREET.search(part)]
    if len(places) > 2:
        home = places[-1].casefold() in _UNITED_STATES
        places = places[:2] if home else [places[0], places[-1]]
    return _short(", ".join(places))


def _figure(match: re.Match[str]) -> str:
    """One amount, rounded to a decimal in the largest unit that fits it."""
    value = float(match.group("number").replace(",", "")) * _UNITS.get((match.group("unit") or "").lower(), 1.0)
    currency = (match.group("currency") or _CURRENCY_WORDS.get((match.group("named") or "").lower(), "")).upper()
    prefix = _SYMBOLS.get(currency, f"{currency} " if currency else "")
    for size, letter in _SCALES:
        if value >= size:
            return f"{prefix}{value / size:.1f}".removesuffix(".0") + letter
    return f"{prefix}{value:,.0f}"


def revenue(text: str) -> str:
    """The first amount the value gives, rounded, with its year: "$26.9B (FY2025)"."""
    amount = next(
        (m for m in _AMOUNT.finditer(text) if m.group("currency") or m.group("unit")), None,
    )
    if amount is None:
        return _short(text)
    rest = text[: amount.start()] + " " + text[amount.end():]
    period = _FISCAL_YEAR.search(rest) or _YEAR.search(rest)
    lead = "About " if _ROUGHLY.match(text.strip()) else ""
    when = f" ({period.group(0).replace(' ', '')})" if period else ""
    return _short(f"{lead}{_figure(amount)}{when}")


def employees(text: str) -> str:
    """The count, with "about" or "full-time" when the value says so, and nothing after it."""
    match = _HEADCOUNT.match(text.strip())
    if match is None:
        return _short(text)
    lead = (match.group("lead") or "").replace("~", "about").strip()
    kind = match.group("kind") or ""
    words = [lead.capitalize(), match.group("number"), kind.lower()]
    return _short(" ".join(word for word in words if word))


def industry(text: str) -> str:
    """The industry in a few words: what comes before the first comma, colon or bracket."""
    return _short(_FIRST_PHRASE.split(text.strip(), maxsplit=1)[0] or text)


def ownership(text: str, listing: str) -> str:
    """Public or private, with the ticker stated once: "Public (NYSE: DINO)"."""
    stated = ticker.normalise(listing)
    kind = "" if ticker.normalise(text) else _FIRST_PHRASE.split(text.strip(), maxsplit=1)[0].strip()
    if kind and stated:
        return _short(f"{kind} ({stated})")
    return _short(kind or stated)


def pills(doc: BriefDoc, labels: Labels) -> list[tuple[str, str]]:
    """Label and short value for each basic that was found, in the page's order."""
    stats = doc["stats"]
    found = [
        (labels["stat_hq"], headquarters(stats["hq"])),
        (labels["stat_revenue"], revenue(stats["revenue"])),
        (labels["stat_employees"], employees(stats["employees"])),
        (labels["stat_industry"], industry(stats["industry"])),
        (labels["stat_ownership"], ownership(stats["ownership"], doc["company"]["ticker"])),
    ]
    return [(label, value) for label, value in found if value]


def line(doc: BriefDoc, labels: Labels) -> str:
    """The pills as the one line the page splits apart: "HQ: Dallas, TX | Revenue: $28B"."""
    return " | ".join(f"{label}: {value}" for label, value in pills(doc, labels))
