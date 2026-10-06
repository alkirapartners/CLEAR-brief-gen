"""Check that a passage the model quotes really is on the page it cites.

Every recorded fact comes with a quote. The fact is the model's words; the
quote has to be the page's. Comparing letters and digits only means layout,
markdown, punctuation and letter case never decide a match, while a changed
word or figure always does.
"""

import re
import unicodedata

# Letters and digits a quote must have in all. Fewer proves nothing.
MIN_QUOTE_CHARS = 20
# Letters and digits each passage of a quote joined with "..." must have, so
# a quote cannot be assembled from single words found here and there.
MIN_PART_CHARS = 12
# The address inside a markdown link, "](https://...)", is not page wording.
# An address has no spaces, no "]" and a bounded length. Because it cannot
# run past the next "]", no two attempts read the same text, and a page of
# unclosed "](" is searched in time that grows with its length, not with
# the square of it.
MAX_LINK_TARGET_CHARS = 2048
_LINK_TARGET = re.compile(rf"\]\([^)\]\s]{{0,{MAX_LINK_TARGET_CHARS}}}\)")
_NOT_LETTER_OR_DIGIT = re.compile(r"[\W_]+")
# How the model marks text it left out between two passages.
_OMISSION = re.compile(r"\[\s*(?:\.{3,}|…)\s*\]|\.{3,}|…")


def bare(text: str) -> str:
    """The letters and digits of a text, lower-cased, with nothing between them."""
    without_targets = _LINK_TARGET.sub("]", text)
    folded = unicodedata.normalize("NFKC", without_targets).casefold()
    return _NOT_LETTER_OR_DIGIT.sub("", folded)


def is_in(quote: str, bare_page: str) -> bool:
    """True when every passage of the quote is in a page already reduced by ``bare``."""
    parts = [part for part in (bare(piece) for piece in _OMISSION.split(quote)) if part]
    if sum(len(part) for part in parts) < MIN_QUOTE_CHARS:
        return False
    return all(len(part) >= MIN_PART_CHARS and part in bare_page for part in parts)


def is_on_page(quote: str, page_text: str) -> bool:
    """True when the page says what the quote says, word for word."""
    return is_in(quote, bare(page_text))


# ── Does the page bear the fact out? ─────────────────────────────
# A quote that is on the page proves the page says the quote. It does not
# prove the fact: a cookie notice is on the page too. So two more things are
# asked of a fact. Every figure in it has to be in its quote, because a
# figure belongs to the sentence it came from. And every name in it (a
# product, a vendor, a technology, a place, a company) has to be somewhere
# on the page: a press release names its city in the dateline and the deal
# three paragraphs down, and both are true of the same fact.

# Labels that hold digits and are not figures: a filing form, a fiscal period.
_DESIGNATOR = re.compile(r"\b(?:10-[KQ]|20-F|40-F|8-K|S-1|FY\s?\d{2,4}|Q[1-4]|H[12]|24/7)\b", re.IGNORECASE)
_YEAR = re.compile(r"^(?:19|20)\d{2}$")
# A date written in a fact is the source's date, not a quantity: "2024-11-04",
# "November 3, 2025", "Oct 30th 2024", "13 November 2024".
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_DATE = re.compile(
    rf"\b\d{{4}}-\d{{2}}(?:-\d{{2}})?\b"
    rf"|\b{_MONTH}\s+{_DAY}\b(?:,?\s+(?:19|20)\d{{2}}\b)?"
    rf"|\b{_DAY}\s+{_MONTH}(?:\s+(?:19|20)\d{{2}}\b)?",
    re.IGNORECASE,
)
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-/&+][A-Za-z0-9]+)*|\d[\d,]*(?:\.\d+)?")
_ENDS_A_SENTENCE = ".!?:"
# Capitalised words that describe a source or a role and name nothing.
_GENERIC = frozenset((
    "the a an and or of in at on for to by with from "
    "january february march april may june july august september october november december "
    "jan feb mar apr jun jul aug sep sept oct nov dec monday tuesday wednesday thursday friday "
    "senior principal lead head chief vice president director manager engineer engineering "
    "architect analyst specialist officer executive network cloud security infrastructure "
    "information technology digital data center centers centre posting job role careers report "
    "annual quarterly filing release press company corporation group inc form fiscal year "
    "it cio ceo cfo cto ciso coo evp svp vp hq us usa uk eu usd m&a"
).split())


def _plain_number(written: str) -> str:
    """One figure as a plain number: "1,400" is 1400 and "10.0" is 10."""
    number = written.replace(",", "")
    return number.rstrip("0").rstrip(".") if "." in number else number


def _without_labels(text: str) -> str:
    """The text with dates and labels such as "FY2025" blanked, so only quantities are left as digits."""
    return _DESIGNATOR.sub(" ", _DATE.sub(" ", text))


def _figures(text: str) -> frozenset[str]:
    found = (_plain_number(token) for token in _TOKEN.findall(_without_labels(text)) if token[0].isdigit())
    return frozenset(number for number in found if not _YEAR.match(number))


def _is_name(token: str, starts_sentence: bool) -> bool:
    """True for a word that names something: an acronym, a CamelCase word, a capitalised word."""
    if len(token) < 2 or token.casefold() in _GENERIC:
        return False
    if any(ch.isupper() for ch in token[1:]):
        return True
    return token[0].isupper() and not starts_sentence


# A number that belongs to a name: the number of a standard or a framework
# ("IEC 62443", "NIST SP 800-82", "SOC 2", "PCI DSS 4.0") or of a product
# model or version ("Catalyst 9300"). It is matched on the page like a name.
# Money, counts and percentages are figures and have to be in the quote.
_STANDARD_WORDS = frozenset(
    "iec iso isa nist ieee ansi rfc pci dss soc fips cis nerc cip cmmc sp csf tia en ul nfpa asme "
    "hipaa sox fedramp tier type level release version rev v".split()
)
# A model number after a product name has at least this many digits.
MIN_MODEL_NUMBER_DIGITS = 3
_CURRENCY_BEFORE = re.compile(r"(?:[$\u20ac\u00a3\u00a5]|\b(?:US\$|USD|CNY|RMB|EUR|GBP|JPY|CAD|AUD|CHF))\s*$")
_MAGNITUDE_AFTER = re.compile(r"\s*(?:%|percent\b|million\b|billion\b|trillion\b|thousand\b|bn\b|mm\b|[BMK]\b)", re.IGNORECASE)
_JOINS_A_NAME = re.compile(r"^[\s\-/:]*$")
_NAME_PARTS = re.compile(r"[-/&+]")


def _is_quantity(text: str, match: re.Match[str]) -> bool:
    """True for a number written as money, a percentage, a magnitude or with thousands."""
    return bool(
        "," in match.group(0)
        or _CURRENCY_BEFORE.search(text[: match.start()])
        or _MAGNITUDE_AFTER.match(text, match.end())
    )


def _numbers(text: str) -> list[tuple[str, bool]]:
    """Every number in the text, in order, with whether it is part of a name.

    A number is part of a name when it directly follows the name of a
    standard or framework, or follows another number that is. It is also
    one when it has three or more digits and directly follows a product
    name. A quantity never is.
    """
    found: list[tuple[str, bool]] = []
    previous: re.Match[str] | None = None
    previous_named = False
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        if not token[0].isdigit():
            previous, previous_named = match, False
            continue
        named = False
        if previous is not None and not _is_quantity(text, match) and _JOINS_A_NAME.match(text[previous.end(): match.start()]):
            before = previous.group(0)
            if before[0].isdigit():
                named = previous_named
            elif set(_NAME_PARTS.split(before.casefold())) & _STANDARD_WORDS:
                named = True
            else:
                digits = sum(ch.isdigit() for ch in token)
                named = digits >= MIN_MODEL_NUMBER_DIGITS and _is_name(before, starts_sentence=False)
        found.append((token, named))
        previous, previous_named = match, named
    return found


def missing_figures(fact: str, quote: str) -> tuple[str, ...]:
    """The figures in a fact that its quote does not hold, in the order they appear.

    Years, dates and labels such as "FY2025" or "10-K" are not figures.
    Neither is the number of a standard or a model: that is part of a name.
    """
    quoted = _figures(quote)
    missing: list[str] = []
    for token, named in _numbers(_without_labels(fact)):
        number = _plain_number(token)
        if not named and not _YEAR.match(number) and number not in quoted and token not in missing:
            missing.append(token)
    return tuple(missing)


_CAPITALISED_WORD = re.compile(r"\b[A-Z][A-Za-z0-9]*")
# An acronym short enough to be spelled out by the first letters of a name.
MAX_ACRONYM_CHARS = 6


def initials(text: str) -> str:
    """The first letter of every capitalised word, in order: where a page spells an acronym out."""
    return "".join(word[0] for word in _CAPITALISED_WORD.findall(text)).casefold()


def _spelled_out(token: str, page_initials: str) -> bool:
    """True for an acronym the page gives in full: NYSE for "New York Stock Exchange"."""
    return token.isupper() and 2 <= len(token) <= MAX_ACRONYM_CHARS and token.casefold() in page_initials


def _parts_on_page(token: str, bare_page: str) -> bool:
    """True for a compound whose naming parts are each on the page: "Dallas-based", "NYSE-listed".

    A part that is a number, or a word that names something, has to be on
    the page. An ordinary lower-case word joined to it does not.
    """
    parts = [part for part in _NAME_PARTS.split(token) if part]
    if len(parts) < 2:
        return False
    naming = [part for part in parts if part[0].isdigit() or _is_name(part, starts_sentence=False)]
    return bool(naming) and all(bare(part) in bare_page for part in naming)


# Below this share of Latin letters a passage is in another script, and an
# English name in a fact cannot be looked for in it.
MIN_LATIN_SHARE = 0.5


def names_can_be_checked(quote: str) -> bool:
    """False for a quote that is mostly not in Latin script, such as a page in Chinese."""
    letters = [ch for ch in quote if ch.isalpha()]
    latin = sum(1 for ch in letters if "LATIN" in unicodedata.name(ch, ""))
    return not letters or latin / len(letters) >= MIN_LATIN_SHARE


def missing_names(
    fact: str, bare_page: str, context: tuple[str, ...] = (), page_initials: str = "",
) -> tuple[str, ...]:
    """The names in a fact that the page never says, in the order they appear.

    ``bare_page`` is the page reduced by ``bare`` and ``page_initials`` the
    same page through ``initials``. ``context`` is what is known without the
    page: the company's name and the page's address. A name found there
    does not have to be on the page.
    """
    text = _without_labels(fact)
    known = tuple(bare(item) for item in context)
    missing: list[str] = []
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        before = text[: match.start()].rstrip()
        starts = not before or before[-1] in _ENDS_A_SENTENCE
        name = bare(token)
        if token[0].isdigit() or not _is_name(token, starts) or token in missing:
            continue
        on_page = name in bare_page or _spelled_out(token, page_initials) or _parts_on_page(token, bare_page)
        if not on_page and not any(name in item for item in known):
            missing.append(token)
    # The numbers of standards and models are names too, and the page has to give them.
    for token, named in _numbers(text):
        if named and not _YEAR.match(_plain_number(token)) and bare(token) not in bare_page and token not in missing:
            missing.append(token)
    return tuple(missing)
