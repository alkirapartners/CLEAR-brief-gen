"""Tests for the db.save_brief notification hook."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


def test_save_brief_triggers_notification_on_success():
    """After a successful insert, notify_brief_generated must be called once."""
    fake_inserted = {
        "id": "abc-123",
        "email": "user@example.com",
        "company": "Acme",
        "score": 5,
        "brief_md": "# brief",
        "created_at": "2026-05-22T14:30:00Z",
    }

    fake_client = MagicMock()
    fake_client.table.return_value.insert.return_value.execute.return_value.data = [
        fake_inserted
    ]

    with patch("db._get_client", return_value=fake_client), patch(
        "notifications.notify_brief_generated"
    ) as mock_notify:
        import db
        result = db.save_brief("user@example.com", "Acme", 5, "# brief")

    assert result == fake_inserted
    mock_notify.assert_called_once_with("user@example.com", "Acme", 5)


def test_save_brief_returns_record_even_if_notification_raises():
    """Notification failures must not affect the saved-brief return value."""
    fake_inserted = {"id": "abc-123", "company": "Acme"}
    fake_client = MagicMock()
    fake_client.table.return_value.insert.return_value.execute.return_value.data = [
        fake_inserted
    ]

    with patch("db._get_client", return_value=fake_client), patch(
        "notifications.notify_brief_generated",
        side_effect=RuntimeError("boom"),
    ):
        import db
        result = db.save_brief("user@example.com", "Acme", 5, "# brief")

    assert result == fake_inserted


def test_save_brief_does_not_notify_when_insert_returns_no_rows():
    """If Supabase returns no rows, the notification must not be sent."""
    fake_client = MagicMock()
    fake_client.table.return_value.insert.return_value.execute.return_value.data = []

    with patch("db._get_client", return_value=fake_client), patch(
        "notifications.notify_brief_generated"
    ) as mock_notify:
        import db
        result = db.save_brief("user@example.com", "Acme", 5, "# brief")

    assert result is None
    mock_notify.assert_not_called()


def test_find_recent_brief_by_company_returns_match():
    """A brief for the same company within the window is reused across users.

    Also asserts the exact arguments passed to each step of the query chain,
    so a wrong column, wrong ordering direction, or wrong limit would fail
    this test even though the mocked return value is correct.
    """
    fake_row = {"id": "x-1", "company": "Acme", "score": 4, "brief_md": "# b",
                "created_at": "2026-08-30T10:00:00Z", "email": "other@example.com"}
    fake_client = MagicMock()
    (fake_client.table.return_value.select.return_value.ilike.return_value
     .gte.return_value.order.return_value.limit.return_value
     .execute.return_value.data) = [fake_row]

    with patch("db._get_client", return_value=fake_client):
        import db
        assert db.find_recent_brief_by_company("acme") == fake_row

    fake_client.table.assert_called_once_with("briefs")
    fake_client.table.return_value.select.assert_called_once_with(
        "id, email, company, score, brief_md, created_at"
    )
    fake_client.table.return_value.select.return_value.ilike.assert_called_once_with(
        "company", "acme"
    )
    (fake_client.table.return_value.select.return_value.ilike.return_value
     .gte.assert_called_once())
    gte_call = (fake_client.table.return_value.select.return_value.ilike
                .return_value.gte.call_args)
    assert gte_call.args[0] == "created_at"
    (fake_client.table.return_value.select.return_value.ilike.return_value
     .gte.return_value.order.assert_called_once_with("created_at", desc=True))
    (fake_client.table.return_value.select.return_value.ilike.return_value
     .gte.return_value.order.return_value.limit.assert_called_once_with(1))


def test_find_recent_brief_by_company_returns_none_when_empty():
    fake_client = MagicMock()
    (fake_client.table.return_value.select.return_value.ilike.return_value
     .gte.return_value.order.return_value.limit.return_value
     .execute.return_value.data) = []

    with patch("db._get_client", return_value=fake_client):
        import db
        assert db.find_recent_brief_by_company("nobody") is None


def test_find_recent_brief_by_company_returns_none_without_client():
    with patch("db._get_client", return_value=None):
        import db
        assert db.find_recent_brief_by_company("Acme") is None


def test_find_recent_brief_by_company_swallows_errors():
    """db.py's contract: never crash the app on a DB problem."""
    fake_client = MagicMock()
    fake_client.table.side_effect = RuntimeError("boom")
    with patch("db._get_client", return_value=fake_client):
        import db
        assert db.find_recent_brief_by_company("Acme") is None


def test_find_recent_brief_by_company_escapes_like_wildcards():
    """LIKE metacharacters in the company name must not act as wildcards.

    Without escaping, '%' and '_' in the input would let the ILIKE pattern
    match a different company's row. This test asserts both the exact
    escaped pattern reaches ilike(), and that the wrong-company row (which
    a naive unescaped call would surface) is NOT what's returned.
    """
    company = "50%_Off Inc"
    escaped = "50\\%\\_Off Inc"

    correct_row = {"id": "right", "company": company, "score": 5, "brief_md": "# right",
                   "created_at": "2026-08-30T10:00:00Z", "email": "a@example.com"}
    wrong_row = {"id": "wrong", "company": "50XOffZInc", "score": 1, "brief_md": "# wrong",
                 "created_at": "2026-08-30T10:00:00Z", "email": "b@example.com"}

    def fake_ilike(_column, pattern):
        chain = MagicMock()
        if pattern == escaped:
            (chain.gte.return_value.order.return_value.limit.return_value
             .execute.return_value.data) = [correct_row]
        else:
            # An unescaped pattern would let '%'/'_' match arbitrary
            # characters, surfacing this unrelated company's row instead.
            (chain.gte.return_value.order.return_value.limit.return_value
             .execute.return_value.data) = [wrong_row]
        return chain

    fake_client = MagicMock()
    fake_client.table.return_value.select.return_value.ilike.side_effect = fake_ilike

    with patch("db._get_client", return_value=fake_client):
        import db
        result = db.find_recent_brief_by_company(company)

    fake_client.table.return_value.select.return_value.ilike.assert_called_once_with(
        "company", escaped
    )
    assert result == correct_row


def test_find_recent_brief_by_company_cutoff_is_in_the_past():
    """The cutoff passed to gte() must be in the past, ~max_age_days ago.

    Guards against an inverted cutoff (e.g. '+' instead of '-'), which would
    silently make the cache never hit or always hit.
    """
    fake_client = MagicMock()
    (fake_client.table.return_value.select.return_value.ilike.return_value
     .gte.return_value.order.return_value.limit.return_value
     .execute.return_value.data) = []

    before = datetime.now(timezone.utc)
    with patch("db._get_client", return_value=fake_client):
        import db
        db.find_recent_brief_by_company("Acme")
    after = datetime.now(timezone.utc)

    gte_mock = (fake_client.table.return_value.select.return_value.ilike
                .return_value.gte)
    cutoff = datetime.fromisoformat(gte_mock.call_args.args[1])

    assert cutoff < after
    tolerance = timedelta(seconds=5)
    assert before - timedelta(days=7) - tolerance <= cutoff <= after - timedelta(days=7) + tolerance


def test_find_recent_brief_by_company_honors_custom_max_age_days():
    """A non-default max_age_days must shift the cutoff accordingly."""
    fake_client = MagicMock()
    (fake_client.table.return_value.select.return_value.ilike.return_value
     .gte.return_value.order.return_value.limit.return_value
     .execute.return_value.data) = []

    before = datetime.now(timezone.utc)
    with patch("db._get_client", return_value=fake_client):
        import db
        db.find_recent_brief_by_company("Acme", max_age_days=1)
    after = datetime.now(timezone.utc)

    gte_mock = (fake_client.table.return_value.select.return_value.ilike
                .return_value.gte)
    cutoff = datetime.fromisoformat(gte_mock.call_args.args[1])

    tolerance = timedelta(seconds=5)
    assert before - timedelta(days=1) - tolerance <= cutoff <= after - timedelta(days=1) + tolerance
    # Clearly the 1-day window, not the 7-day default.
    assert cutoff > before - timedelta(days=2)
