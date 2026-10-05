"""Blake's rule: an M&A event counts when it happened in the last three months, or is announced and not yet completed."""

from datetime import date

import pytest

import deal_rules

TODAY = date(2026, 10, 5)


def _ref(n=1, source_type="first_hand", dated="2026-07-28"):
    return {"n": n, "title": f"Page {n}", "url": f"https://example.com/{n}", "date": dated, "source_type": source_type}


def _deal(deal_date, status, sources=(1,), use_case="m_and_a"):
    return {
        "title": "Deal", "use_case": use_case, "alkira": "What Alkira does.",
        "evidence": [{"text": "The business will become a standalone company.", "date": "", "sources": list(sources)}],
        "story": {"id": "none", "customer": "", "result": ""},
        "deal_date": deal_date, "deal_status": status,
    }


def _qualifies(angle, references=None, wording=None):
    return deal_rules.qualifies(angle, references or [_ref()], TODAY, wording or {})


# ── The window ───────────────────────────────────────────────────

def test_the_window_is_three_months_before_the_day_the_brief_is_made():
    assert deal_rules.DEAL_WINDOW_MONTHS == 3
    assert deal_rules.window_start(date(2026, 10, 5)) == date(2026, 7, 5)
    assert deal_rules.window_start(date(2026, 5, 31)) == date(2026, 2, 28)  # no 31st of February
    assert deal_rules.window_start(date(2026, 2, 10)) == date(2025, 11, 10)


@pytest.mark.parametrize("deal_date, expected", [
    ("2026-07-28", True),    # ten weeks ago
    ("2026-07-05", True),    # three months ago to the day
    ("2026-07-04", False),   # a day too old
    ("2026-01-02", False),   # completed in January, asked about in October
    ("2026-10-05", True),    # today
    ("2026-10-06", False),   # not yet happened
    ("2026-08", True), ("2026-06", False),  # a month counts from its first day
    ("", False), ("last summer", False),
])
def test_a_completed_deal_counts_only_when_it_happened_inside_the_window(deal_date, expected):
    assert _qualifies(_deal(deal_date, "completed"), [_ref(dated=deal_date)]) is expected


# ── Pending deals ────────────────────────────────────────────────

def test_a_deal_announced_and_not_yet_completed_counts_whatever_its_date():
    """HF Sinclair's separation: announced on 28 July, due to complete over the next 12 to 18 months."""
    assert _qualifies(_deal("2026-07-28", "pending"))
    assert _qualifies(_deal("2025-11-12", "pending"), [_ref(dated="2025-11-12")])  # announced a year ago, still open


def test_pending_deals_are_one_switch(monkeypatch):
    old_announcement = _deal("2025-11-12", "pending")
    references = [_ref(dated="2025-11-12")]
    monkeypatch.setattr(deal_rules, "PENDING_DEALS_COUNT", False)
    assert not _qualifies(old_announcement, references)
    assert _qualifies(_deal("2026-07-28", "pending"))  # still inside the window on its own date


def test_a_deal_called_pending_years_after_it_was_announced_is_not_believed():
    assert not _qualifies(_deal("2023-03-01", "pending"), [_ref(dated="2023-03-01")])


def test_the_carve_out_completed_in_january_does_not_count_in_october():
    """Occidental sold OxyChem on 2 January. Transition services still running do not bring it back."""
    assert not _qualifies(_deal("2026-01-02", "completed"), [_ref(dated="2026-01-02")])


# ── The date is the page's, and the source is first-hand ─────────

def test_the_event_has_to_be_dated_by_a_first_hand_source():
    assert not _qualifies(_deal("2026-07-28", "pending"), [_ref(source_type="second_hand")])
    assert not _qualifies(_deal("2026-07-28", "completed"), [_ref(source_type="last_resort")])
    both = [_ref(1, "second_hand"), _ref(2, "first_hand")]
    assert _qualifies(_deal("2026-07-28", "completed", sources=(1, 2)), both)


def test_a_date_no_cited_page_gives_does_not_count():
    assert not _qualifies(_deal("2026-08-15", "completed"), [_ref(dated="2026-02-20")])
    assert not _qualifies(_deal("2026-08-15", "pending"), [_ref(dated="")])


@pytest.mark.parametrize("wording", [
    "On August 15, 2026, we completed the sale of the lubricants business.",
    "The sale closed on 15 Aug 2026.",
    "completed 2026-08-15",
    "Completed in August 2026 (15th).",
])
def test_a_date_the_page_wording_states_counts_when_the_page_s_own_date_is_another(wording):
    """A quarterly filing is dated at its quarter end and reports a deal that closed weeks earlier."""
    assert _qualifies(_deal("2026-08-15", "completed"), [_ref(dated="2026-09-30")], {1: wording})


def test_the_page_wording_has_to_state_the_whole_date():
    assert not _qualifies(_deal("2026-08-15", "completed"), [_ref(dated="2026-09-30")], {1: "completed in March 2026"})
    assert not _qualifies(_deal("2026-08-15", "completed"), [_ref(dated="2026-09-30")], {1: "completed August 2025, 15 sites"})


def test_a_month_given_by_the_source_dates_an_event_on_a_day_in_that_month():
    assert _qualifies(_deal("2026-08-15", "completed"), [_ref(dated="2026-08-15")])
    assert _qualifies(_deal("2026-08", "completed"), [_ref(dated="2026-08-15")])


# ── Only M&A angles are asked ────────────────────────────────────

def test_an_angle_that_is_not_m_and_a_is_not_judged_by_this_rule():
    assert deal_rules.is_deal(_deal("", "none")) and not deal_rules.is_deal(_deal("", "none", use_case="multi_cloud"))
    assert not _qualifies(_deal("2026-07-28", "none"))  # an M&A angle has to say which it is
