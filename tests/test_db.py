"""Tests for the db.save_brief notification hook."""

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
