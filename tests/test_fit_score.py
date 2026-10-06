"""The score ceiling is worked out from the kind and date of the sources each angle cites."""

from datetime import date

import pytest

import fit_score

TODAY = date(2026, 10, 5)


def _ref(n, source_type="first_hand", dated="2026-09-01"):
    return {"n": n, "title": f"Page {n}", "url": f"https://example.com/{n}", "date": dated, "source_type": source_type, "open_posting": False}


def _angle(sources, use_case="multi_cloud"):
    return {
        "title": "Angle", "use_case": use_case, "alkira": "What Alkira does.",
        "evidence": [{"text": "A fact.", "date": "", "sources": list(sources)}],
        "story": {"id": "none", "customer": "", "result": ""},
        "deal_date": "", "deal_status": "none", "deal_pending_quote": "",
    }


def _cap(angles, references):
    return fit_score.ceiling(angles, references, TODAY)


# ── What each score needs ────────────────────────────────────────

def test_with_no_angle_the_score_stops_at_two():
    assert _cap([], [_ref(1)]) == fit_score.Ceiling(2, "score_held_no_angles")


@pytest.mark.parametrize("references", [
    [_ref(1, "second_hand")],                 # trade press
    [_ref(1, "last_resort")],                 # an encyclopedia or a data broker
    [_ref(1, "first_hand", dated="")],        # first-hand, but undated
    [_ref(1, "first_hand", dated="2023-05")], # first-hand, but older than two years
    [_ref(1, "first_hand", dated="2027-01")], # a date that has not happened yet proves nothing
], ids=["trade-press", "last-resort", "undated", "old", "future"])
def test_an_angle_without_current_first_hand_evidence_cannot_lift_the_score_above_three(references):
    assert _cap([_angle([1])], references) == fit_score.Ceiling(3, "score_held_evidence")


def test_second_hand_angles_stay_at_three_however_many_there_are():
    references = [_ref(1, "second_hand"), _ref(2, "second_hand"), _ref(3, "second_hand")]
    angles = [_angle([1], "m_and_a"), _angle([2], "multi_cloud"), _angle([3], "site_rollout")]
    assert _cap(angles, references).score == 3


def test_one_use_case_with_current_first_hand_evidence_reaches_four_and_no_higher():
    assert _cap([_angle([1])], [_ref(1)]) == fit_score.Ceiling(4, "score_held_use_cases")
    assert _cap([_angle([1, 2])], [_ref(1), _ref(2, "second_hand")]).score == 4  # a second-hand source beside it does no harm


def test_a_five_needs_two_use_cases_each_with_its_own_first_hand_source_and_a_dated_trigger():
    two = [_angle([1], "m_and_a"), _angle([2], "multi_cloud")]
    assert _cap(two, [_ref(1), _ref(2)]) == fit_score.Ceiling(5, "")
    assert _cap(two, [_ref(1), _ref(2, dated="")]).score == 5  # one dated trigger is enough


@pytest.mark.parametrize("angles, references", [
    ([_angle([1], "m_and_a"), _angle([1], "multi_cloud")], [_ref(1)]),                               # one page carrying both
    ([_angle([1], "m_and_a"), _angle([2], "m_and_a")], [_ref(1), _ref(2)]),                          # one use case told twice
    ([_angle([1], "m_and_a"), _angle([2], "multi_cloud")], [_ref(1), _ref(2, "second_hand")]),       # the second is second-hand
    ([_angle([1], "m_and_a"), _angle([2], "multi_cloud")], [_ref(1), _ref(2, "last_resort")]),
], ids=["same-source", "same-use-case", "second-is-trade-press", "second-is-last-resort"])
def test_two_angles_that_are_not_independently_first_hand_stay_at_four(angles, references):
    assert _cap(angles, references) == fit_score.Ceiling(4, "score_held_use_cases")


def test_a_shared_page_does_not_spoil_two_angles_that_also_have_their_own():
    angles = [_angle([1], "m_and_a"), _angle([1, 2], "multi_cloud")]
    assert _cap(angles, [_ref(1), _ref(2)]).score == 5


# ── What counts as current ───────────────────────────────────────

@pytest.mark.parametrize("dated, current", [
    ("2026-10-05", True), ("2026-09", True), ("2025", True), ("2024-10-06", True),
    ("2024-10-04", False), ("2024", False), ("", False), ("last spring", False), ("2026-10-06", False),
])
def test_current_means_dated_within_about_the_last_two_years(dated, current):
    assert fit_score.is_current(dated, TODAY) is current


def test_the_limits_are_named():
    assert fit_score.CURRENT_EVIDENCE_DAYS == 730
    assert (fit_score.MAX_SCORE_WITHOUT_ANGLES, fit_score.MAX_SCORE_WITHOUT_CURRENT_FIRST_HAND,
            fit_score.MAX_SCORE_WITH_ONE_USE_CASE) == (2, 3, 4)
