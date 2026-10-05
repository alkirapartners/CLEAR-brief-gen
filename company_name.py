"""What may be typed as a company name.

The name goes into a prompt and into web searches, so it is checked where
it enters. A web address would point the research at a page of the typist's
choosing, and markup has no place in a name: both are refused. A company
that is named like a website ("Booking.com") is let through.
"""

import re

NOT_A_NAME_MESSAGE = "Enter a company name, not a web address."

# A scheme ("http://"), a "www." prefix, a domain followed by a path, a query
# or a port, or an email address.
_WEB_ADDRESS = re.compile(
    r"://"
    r"|(?:^|[\s(\[\"'])www\."
    r"|\.[a-z]{2,24}[/?#:]\S"
    r"|\S@\S+\.\S",
    re.IGNORECASE,
)
_MARKUP_CHARS = frozenset("<>`{}\\")


def is_company_name(name: str) -> bool:
    """True when the text can be researched as a company name."""
    text = name.strip()
    if not text or _MARKUP_CHARS & set(text):
        return False
    return _WEB_ADDRESS.search(text) is None
