"""Owner-scoped brief access and Streamlit-free configuration."""

import subprocess
import sys
from unittest.mock import MagicMock, patch

import db

ROW = {
    "id": "b1", "email": "a@x.com", "company": "Acme", "score": 4,
    "brief_md": "# b", "created_at": "2026-10-01T00:00:00Z",
}


def test_db_and_notifications_do_not_import_streamlit():
    code = "import sys, db, notifications; assert 'streamlit' not in sys.modules"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_get_brief_filters_by_id_and_owner():
    client = MagicMock()
    select = client.table.return_value.select.return_value
    select.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [ROW]
    with patch("db._get_client", return_value=client):
        assert db.get_brief("b1", " A@X.com ") == ROW
    select.eq.assert_called_once_with("id", "b1")
    select.eq.return_value.eq.assert_called_once_with("email", "a@x.com")


def test_get_brief_returns_none_when_no_row_matches():
    client = MagicMock()
    select = client.table.return_value.select.return_value
    select.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    with patch("db._get_client", return_value=client):
        assert db.get_brief("b1", "other@x.com") is None


def test_get_brief_returns_none_without_a_client():
    with patch("db._get_client", return_value=None):
        assert db.get_brief("b1", "a@x.com") is None


def test_delete_brief_is_scoped_to_the_owner_and_reports_removal():
    client = MagicMock()
    delete = client.table.return_value.delete.return_value
    execute = delete.eq.return_value.eq.return_value.execute
    execute.return_value.data = [{"id": "b1"}]
    with patch("db._get_client", return_value=client):
        assert db.delete_brief("b1", "A@x.com") is True
    delete.eq.assert_called_once_with("id", "b1")
    delete.eq.return_value.eq.assert_called_once_with("email", "a@x.com")

    execute.return_value.data = []
    with patch("db._get_client", return_value=client):
        assert db.delete_brief("b1", "other@x.com") is False


def test_count_user_briefs_since_uses_an_exact_count():
    client = MagicMock()
    select = client.table.return_value.select
    select.return_value.eq.return_value.gte.return_value.execute.return_value.count = 7
    with patch("db._get_client", return_value=client):
        assert db.count_user_briefs_since("A@x.com", "2026-10-05T00:00:00+00:00") == 7
    select.assert_called_once_with("id", count="exact")
    select.return_value.eq.assert_called_once_with("email", "a@x.com")


def test_count_user_briefs_since_is_zero_on_error():
    client = MagicMock()
    client.table.side_effect = RuntimeError("down")
    with patch("db._get_client", return_value=client):
        assert db.count_user_briefs_since("a@x.com", "2026-10-05T00:00:00+00:00") == 0
