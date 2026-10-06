"""One way to state a ticker: the exchange, a colon, the symbol.

The model writes tickers many ways: "NYSE: DINO", "AAP (NYSE)", or a
sentence about a second listing. Everything that prints a ticker reads it
through here, so it is stated the same way everywhere, or not at all.
"""

import re

# A short exchange code is upper-cased (nyse -> NYSE). A longer name, such as
# "Shenzhen", is left as written.
MAX_EXCHANGE_CODE_CHARS = 6
_SYMBOL = r"[A-Za-z0-9][A-Za-z0-9.\-]{0,9}"
# What may follow a ticker: the end, or punctuation. A word may not, so
# "Note: this company is private" is not read as a ticker.
_THEN_ENDS = r"(?=\s*(?:$|[;,()]))"
_EXCHANGE_FIRST = re.compile(rf"^\(?\s*(?P<exchange>[A-Za-z]{{2,10}})\s*:\s*(?P<symbol>{_SYMBOL}){_THEN_ENDS}")
_SYMBOL_FIRST = re.compile(r"^(?P<symbol>[A-Z0-9][A-Z0-9.\-]{0,9})\s*\(\s*(?P<exchange>[A-Za-z]{2,10})\s*[,)]")
_BARE_SYMBOL = re.compile(r"^[A-Z][A-Z0-9.\-]{0,5}$")


def _exchange(name: str) -> str:
    return name.upper() if len(name) <= MAX_EXCHANGE_CODE_CHARS else name


def normalise(text: str) -> str:
    """The main listing as "EXCHANGE: SYMBOL", a bare symbol, or nothing.

    Only the first listing is kept. Text that is not a ticker gives "".
    """
    written = text.strip()
    match = _EXCHANGE_FIRST.match(written) or _SYMBOL_FIRST.match(written)
    if match is not None:
        symbol = match.group("symbol").upper().rstrip(".")
        return f"{_exchange(match.group('exchange'))}: {symbol}"
    return written if _BARE_SYMBOL.match(written) else ""
