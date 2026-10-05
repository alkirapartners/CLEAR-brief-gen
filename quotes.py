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


# ── Does the quote state the fact? ───────────────────────────────
# A quote that is on the page proves the page says the quote. It does not
# prove the fact: a cookie notice is on the page too. So the figures in a
# fact, and the names in it (products, vendors, technologies, places), have
# to be in its quote.

# Labels that hold digits and are not figures: a filing form, a fiscal period.
_DESIGNATOR = re.compile(r"\b(?:10-[KQ]|20-F|40-F|8-K|S-1|FY\s?\d{2,4}|Q[1-4]|H[12]|24/7)\b", re.IGNORECASE)
_YEAR = re.compile(r"^(?:19|20)\d{2}$")
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


def _figures(text: str) -> frozenset[str]:
    found = (_plain_number(token) for token in _TOKEN.findall(_DESIGNATOR.sub(" ", text)) if token[0].isdigit())
    return frozenset(number for number in found if not _YEAR.match(number))


def _is_name(token: str, starts_sentence: bool) -> bool:
    """True for a word that names something: an acronym, a CamelCase word, a capitalised word."""
    if len(token) < 2 or token.casefold() in _GENERIC:
        return False
    if any(ch.isupper() for ch in token[1:]):
        return True
    return token[0].isupper() and not starts_sentence


def missing_from_quote(fact: str, quote: str, context: tuple[str, ...] = ()) -> tuple[str, ...]:
    """The figures and names in a fact that its quote does not hold, in the order they appear.

    ``context`` is what is known without the quote: the company's name and
    the page's address. A name found there does not have to be quoted. Years
    and labels such as "FY2025" or "10-K" are not figures.
    """
    text = _DESIGNATOR.sub(" ", fact)
    quoted, quoted_figures = bare(quote), _figures(quote)
    known = tuple(bare(item) for item in context)
    missing: list[str] = []
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        if token[0].isdigit():
            number = _plain_number(token)
            absent = not _YEAR.match(number) and number not in quoted_figures
        else:
            before = text[: match.start()].rstrip()
            starts = not before or before[-1] in _ENDS_A_SENTENCE
            name = bare(token)
            absent = _is_name(token, starts) and name not in quoted and not any(name in item for item in known)
        if absent and token not in missing:
            missing.append(token)
    return tuple(missing)
