"""Tests for Slack notifications module."""

import pytest

from notifications import _format_message


def test_format_message_includes_email_company_score():
    msg = _format_message("user@example.com", "Mary Kay", 5)
    assert "user@example.com" in msg
    assert "Mary Kay" in msg
    assert "5" in msg


def test_format_message_green_at_5():
    msg = _format_message("u@x.com", "Acme", 5)
    assert ":large_green_circle:" in msg


def test_format_message_yellow_at_4():
    msg = _format_message("u@x.com", "Acme", 4)
    assert ":large_yellow_circle:" in msg


def test_format_message_yellow_at_3():
    msg = _format_message("u@x.com", "Acme", 3)
    assert ":large_yellow_circle:" in msg


def test_format_message_red_at_2():
    msg = _format_message("u@x.com", "Acme", 2)
    assert ":red_circle:" in msg


def test_format_message_red_at_1():
    msg = _format_message("u@x.com", "Acme", 1)
    assert ":red_circle:" in msg


def test_format_message_red_at_zero():
    msg = _format_message("u@x.com", "Acme", 0)
    assert ":red_circle:" in msg


def test_format_message_includes_utc_timestamp():
    msg = _format_message("u@x.com", "Acme", 3)
    assert "UTC" in msg


from unittest.mock import patch

from notifications import _slack_webhook_url


def test_slack_webhook_url_reads_from_env(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    assert _slack_webhook_url() == "https://hooks.slack.com/test"


def test_slack_webhook_url_returns_empty_when_unset(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    # Mock st.secrets too so the test is deterministic regardless of whether
    # a .streamlit/secrets.toml file exists in the runner's CWD.
    with patch("notifications.st") as mock_st:
        mock_st.secrets.get.return_value = ""
        assert _slack_webhook_url() == ""


def test_slack_webhook_url_falls_back_to_st_secrets(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    fake_secrets = {"SLACK_WEBHOOK_URL": "https://hooks.slack.com/from-secrets"}
    with patch("notifications.st") as mock_st:
        mock_st.secrets.get.side_effect = lambda k, d="": fake_secrets.get(k, d)
        assert _slack_webhook_url() == "https://hooks.slack.com/from-secrets"


from unittest.mock import MagicMock
from urllib.error import HTTPError, URLError

from notifications import _post


def test_post_success_does_not_raise():
    fake_response = MagicMock()
    fake_response.__enter__ = MagicMock(return_value=fake_response)
    fake_response.__exit__ = MagicMock(return_value=False)
    fake_response.status = 200
    with patch("notifications.urllib.request.urlopen", return_value=fake_response):
        _post("https://hooks.slack.com/test", {"text": "hi"})


def test_post_raises_on_url_error():
    with patch(
        "notifications.urllib.request.urlopen",
        side_effect=URLError("network down"),
    ):
        with pytest.raises(URLError):
            _post("https://hooks.slack.com/test", {"text": "hi"})


def test_post_raises_on_http_error():
    err = HTTPError("url", 500, "Server Error", {}, None)
    with patch("notifications.urllib.request.urlopen", side_effect=err):
        with pytest.raises(HTTPError):
            _post("https://hooks.slack.com/test", {"text": "hi"})


from notifications import notify_brief_generated


def test_notify_returns_false_when_webhook_unset(monkeypatch):
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    with patch("notifications.st") as mock_st:
        mock_st.secrets.get.return_value = ""
        result = notify_brief_generated("u@x.com", "Acme", 3)
    assert result is False


def test_notify_returns_true_on_successful_post(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    with patch("notifications._post") as mock_post:
        mock_post.return_value = None
        result = notify_brief_generated("u@x.com", "Acme", 5)
    assert result is True
    mock_post.assert_called_once()
    posted_url, posted_payload = mock_post.call_args.args
    assert posted_url == "https://hooks.slack.com/test"
    assert "u@x.com" in posted_payload["text"]
    assert "Acme" in posted_payload["text"]
    assert "5" in posted_payload["text"]


def test_notify_returns_false_on_post_failure(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    with patch("notifications._post", side_effect=URLError("network down")):
        result = notify_brief_generated("u@x.com", "Acme", 3)
    assert result is False


def test_notify_returns_false_on_http_error(monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    err = HTTPError("url", 500, "Server Error", {}, None)
    with patch("notifications._post", side_effect=err):
        result = notify_brief_generated("u@x.com", "Acme", 3)
    assert result is False
