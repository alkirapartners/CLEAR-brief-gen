"""A ticker is stated one way: the exchange, a colon, the symbol."""

import pytest

import ticker


@pytest.mark.parametrize("written, expected", [
    ("NYSE: DINO", "NYSE: DINO"),
    ("NYSE:DINO", "NYSE: DINO"),
    ("AAP (NYSE)", "NYSE: AAP"),
    ("KMPR (NYSE)", "NYSE: KMPR"),
    ("NASDAQ: MSFT", "NASDAQ: MSFT"),
    ("nyse: ups", "NYSE: UPS"),
    ("SHE:300866 (Shenzhen); also listed in Hong Kong since 2 July 2026", "SHE: 300866"),
    ("300866 (Shenzhen), 00668 (Hong Kong, dual-listed since July 2026)", "Shenzhen: 300866"),
    ("TSX: ATD.B", "TSX: ATD.B"),
    ("LSE: BP.", "LSE: BP"),
    ("DINO", "DINO"),
    ("  NYSE: OXY  ", "NYSE: OXY"),
], ids=lambda value: value[:14])
def test_a_ticker_is_reduced_to_its_exchange_and_symbol(written, expected):
    assert ticker.normalise(written) == expected


@pytest.mark.parametrize("written", [
    "", "   ", "Private", "Not listed", "Privately held, no ticker", "n/a",
    "The company is listed on several exchanges", "Public",
])
def test_text_that_is_not_a_ticker_is_no_ticker(written):
    assert ticker.normalise(written) == ""
