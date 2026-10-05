"""Environment configuration must never stop the API from starting."""

import pytest

import settings as settings_module
from settings import DEFAULT_DAILY_LIMIT, load_settings


@pytest.fixture(autouse=True)
def _no_dotenv(monkeypatch):
    """Keep a developer's real .env out of these tests."""
    monkeypatch.setattr(settings_module, "load_dotenv", lambda *args, **kwargs: False)


def test_daily_limit_defaults_when_unset(monkeypatch):
    monkeypatch.delenv("BRIEF_DAILY_LIMIT", raising=False)
    assert load_settings().daily_limit == DEFAULT_DAILY_LIMIT


def test_daily_limit_reads_a_valid_number(monkeypatch):
    monkeypatch.setenv("BRIEF_DAILY_LIMIT", " 12 ")
    assert load_settings().daily_limit == 12


@pytest.mark.parametrize("value", ["", "   ", "fifty", "12.5", "0", "-3"])
def test_an_unusable_daily_limit_falls_back_to_the_default(monkeypatch, value):
    monkeypatch.setenv("BRIEF_DAILY_LIMIT", value)
    assert load_settings().daily_limit == DEFAULT_DAILY_LIMIT


def test_keys_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a-key")
    monkeypatch.setenv("TAVILY_API_KEY", "t-key")
    monkeypatch.setenv("BRIEF_ADMINS_FILE", "/tmp/admins.json")
    settings = load_settings()
    assert (settings.anthropic_key, settings.tavily_key, settings.admins_file) == (
        "a-key", "t-key", "/tmp/admins.json",
    )


def test_usage_is_kept_in_the_shared_data_directory_by_default(monkeypatch):
    monkeypatch.delenv("BRIEF_DATA_DIR", raising=False)
    assert load_settings().usage_dir.endswith("data")


def test_the_data_directory_can_be_moved(monkeypatch):
    monkeypatch.setenv("BRIEF_DATA_DIR", "/tmp/somewhere")
    assert load_settings().usage_dir == "/tmp/somewhere"
