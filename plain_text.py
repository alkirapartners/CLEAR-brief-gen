"""Text with no links or addresses in it.

A brief is read by partners, so nothing the model wrote may carry them to
an address of its choosing. Sources are cited by number and listed by the
code. Everything else the model writes (sentences, and the titles it gives
the pages it read) goes through here.
"""

import re

# A markdown link or image is reduced to its words. The bounds keep the
# search linear on text built to stall it.
_MARKDOWN_LINK = re.compile(r"!?\[([^\]]{0,500})\]\([^)\]\s]{0,2048}\)")
# Any scheme ("https://", "ftp://"), a mail address link, a "www." host, or
# a host followed by a path ("evil.com/login"). A name such as "Booking.com"
# and a pair such as "IT/OT" are neither.
_ADDRESS = re.compile(
    r"(?:\b[a-z][a-z0-9+.\-]{1,20}://|\bmailto:|\bwww\.)\S+"
    r"|\b(?:[a-z0-9\-]+\.)+(?:[a-z]{2,24}|xn--[a-z0-9\-]+)/\S*",
    re.IGNORECASE,
)


def plain(text: str) -> str:
    """The text with markdown links reduced to their words and every address removed."""
    unlinked = _MARKDOWN_LINK.sub(r"\1", text)
    return " ".join(_ADDRESS.sub("", unlinked).split())
