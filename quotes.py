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
