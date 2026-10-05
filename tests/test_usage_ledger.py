"""The daily cap counts generations paid for, not briefs that still exist."""

import os
from datetime import date, datetime, timedelta, timezone

import pytest

from usage_ledger import KEEP_DAYS, LedgerError, UsageLedger

NOON = datetime(2026, 10, 5, 12, 0, tzinfo=timezone.utc)
TODAY = date(2026, 10, 5)


def test_counts_what_was_recorded_for_that_person_on_that_day(tmp_path):
    ledger = UsageLedger(str(tmp_path))
    ledger.record("a@x.com", NOON)
    ledger.record("a@x.com", NOON + timedelta(hours=1))
    ledger.record("b@x.com", NOON)

    assert ledger.count_on_day("a@x.com", TODAY) == 2
    assert ledger.count_on_day("b@x.com", TODAY) == 1
    assert ledger.count_on_day("nobody@x.com", TODAY) == 0


def test_email_is_matched_without_regard_to_case_or_padding(tmp_path):
    ledger = UsageLedger(str(tmp_path))
    ledger.record(" A@X.com ", NOON)

    assert ledger.count_on_day("a@x.com", TODAY) == 1


def test_each_utc_day_starts_from_zero(tmp_path):
    ledger = UsageLedger(str(tmp_path))
    ledger.record("a@x.com", datetime(2026, 10, 5, 23, 59, tzinfo=timezone.utc))
    ledger.record("a@x.com", datetime(2026, 10, 6, 0, 1, tzinfo=timezone.utc))

    assert ledger.count_on_day("a@x.com", date(2026, 10, 5)) == 1
    assert ledger.count_on_day("a@x.com", date(2026, 10, 6)) == 1


def test_a_second_instance_sees_the_same_counts(tmp_path):
    """Production runs two servers over one shared data directory."""
    UsageLedger(str(tmp_path)).record("a@x.com", NOON)

    assert UsageLedger(str(tmp_path)).count_on_day("a@x.com", TODAY) == 1


def test_creates_its_directory_on_first_use(tmp_path):
    target = tmp_path / "not" / "there" / "yet"
    UsageLedger(str(target)).record("a@x.com", NOON)

    assert UsageLedger(str(target)).count_on_day("a@x.com", TODAY) == 1


def test_a_damaged_line_is_skipped_not_fatal(tmp_path):
    ledger = UsageLedger(str(tmp_path))
    ledger.record("a@x.com", NOON)
    day_file = next(tmp_path.iterdir())
    with open(day_file, "a", encoding="utf-8") as handle:
        handle.write("{half a line\n[1, 2]\n")
    ledger.record("a@x.com", NOON)

    assert ledger.count_on_day("a@x.com", TODAY) == 2


def test_an_unusable_directory_raises_instead_of_reporting_zero(tmp_path):
    """Reporting zero would silently lift the cap whenever storage is unhealthy."""
    blocker = tmp_path / "a-file"
    blocker.write_text("not a directory")
    ledger = UsageLedger(str(blocker))

    with pytest.raises(LedgerError):
        ledger.count_on_day("a@x.com", TODAY)
    with pytest.raises(LedgerError):
        ledger.record("a@x.com", NOON)


def test_old_days_are_cleared_out_but_recent_ones_kept(tmp_path):
    ledger = UsageLedger(str(tmp_path))
    old_day = NOON - timedelta(days=KEEP_DAYS + 3)
    recent_day = NOON - timedelta(days=1)
    ledger.record("a@x.com", old_day)
    ledger.record("a@x.com", recent_day)

    ledger.record("a@x.com", NOON)

    assert ledger.count_on_day("a@x.com", old_day.date()) == 0
    assert ledger.count_on_day("a@x.com", recent_day.date()) == 1
    assert len(os.listdir(tmp_path)) == 2


def test_only_its_own_files_are_ever_removed(tmp_path):
    keep = tmp_path / "sessions.json"
    keep.write_text("{}")
    ledger = UsageLedger(str(tmp_path))
    ledger.record("a@x.com", NOON - timedelta(days=KEEP_DAYS + 30))

    ledger.record("a@x.com", NOON)

    assert keep.exists()
