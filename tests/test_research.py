"""Tests for the Tavily research layer. No live network calls."""

from unittest.mock import MagicMock, patch

import pytest

import research


def _search_response(url, title="Title", score=0.9, content="snippet"):
    return {"results": [{"url": url, "title": title, "score": score, "content": content}]}


def test_build_queries_covers_all_checklist_categories():
    qs = research.build_queries("Acme Corp")
    assert len(qs) == 7
    assert all("Acme Corp" in q["query"] for q in qs)


def test_signals_query_uses_news_topic_and_year_range():
    """The brief demands past-12-month emphasis; default ranking ignores recency."""
    qs = research.build_queries("Acme Corp")
    signals = [q for q in qs if q.get("topic") == "news"]
    assert len(signals) == 1
    assert signals[0]["time_range"] == "year"


def test_rank_results_sorts_by_score_descending():
    raw = [
        {"url": "https://a.com/1", "title": "A", "score": 0.20},
        {"url": "https://b.com/2", "title": "B", "score": 0.90},
        {"url": "https://c.com/3", "title": "C", "score": 0.55},
    ]
    ranked = research.rank_results(raw)
    assert [r["url"] for r in ranked] == [
        "https://b.com/2", "https://c.com/3", "https://a.com/1",
    ]


def test_rank_results_deduplicates_by_url():
    raw = [
        {"url": "https://a.com/1", "title": "A", "score": 0.9},
        {"url": "https://a.com/1", "title": "A dup", "score": 0.8},
    ]
    assert len(research.rank_results(raw)) == 1


def test_rank_results_deprioritises_social_domains():
    """LinkedIn ranks well but extracts to boilerplate; it must lose to a real page."""
    raw = [
        {"url": "https://www.linkedin.com/company/acme", "title": "LI", "score": 0.99},
        {"url": "https://acme.com/investors", "title": "IR", "score": 0.40},
    ]
    ranked = research.rank_results(raw)
    assert ranked[0]["url"] == "https://acme.com/investors"


def test_rank_results_respects_limit():
    raw = [
        {"url": f"https://a.com/{i}", "title": str(i), "score": i / 10}
        for i in range(20)
    ]
    assert len(research.rank_results(raw, limit=5)) == 5


def test_truncate_caps_long_content():
    assert len(research.truncate("x" * 50_000)) == research.MAX_PAGE_CHARS


def test_truncate_leaves_short_content_untouched():
    assert research.truncate("short") == "short"


def test_format_payload_numbers_sources_and_includes_urls():
    sources = [
        {"n": 1, "title": "IR page", "url": "https://acme.com/ir", "content": "revenue"},
        {"n": 2, "title": "News", "url": "https://news.com/a", "content": "acquired"},
    ]
    payload = research.format_payload(sources)
    assert "[1]" in payload and "[2]" in payload
    assert "https://acme.com/ir" in payload
    assert "https://news.com/a" in payload
    assert "revenue" in payload


@patch("research.TavilyClient")
def test_research_happy_path_numbers_sources_and_includes_urls(mock_tavily_client):
    client = MagicMock()
    client.search.return_value = _search_response("https://acme.com/page")
    client.extract.return_value = {
        "results": [{"url": "https://acme.com/page", "raw_content": "full page content"}]
    }
    mock_tavily_client.return_value = client

    result = research.research("Acme Corp", lambda status: None, "fake-key")

    assert isinstance(result, research.ResearchResult)
    assert [s["n"] for s in result.sources] == list(range(1, len(result.sources) + 1))
    assert "https://acme.com/page" in result.payload


@patch("research.TavilyClient")
def test_research_extract_failure_falls_back_to_search_snippets(mock_tavily_client):
    client = MagicMock()
    client.search.return_value = _search_response(
        "https://acme.com/page", content="search snippet"
    )
    client.extract.side_effect = RuntimeError("extract down")
    mock_tavily_client.return_value = client

    result = research.research("Acme Corp", lambda status: None, "fake-key")

    assert isinstance(result, research.ResearchResult)
    assert result.sources
    assert result.sources[0]["content"] == "search snippet"


@patch("research.TavilyClient")
def test_research_raises_when_all_searches_fail(mock_tavily_client):
    client = MagicMock()
    client.search.side_effect = RuntimeError("rate limited")
    mock_tavily_client.return_value = client

    with pytest.raises(research.ResearchError):
        research.research("Acme Corp", lambda status: None, "fake-key")


@patch("research.TavilyClient")
def test_research_survives_one_failing_query_among_seven(mock_tavily_client):
    """A single throttled/timed-out query must not abort the whole batch."""
    client = MagicMock()
    failing_query = research.build_queries("Acme Corp")[2]["query"]

    def fake_search(**kwargs):
        if kwargs.get("query") == failing_query:
            raise RuntimeError("timeout")
        return _search_response(f"https://acme.com/{abs(hash(kwargs['query']))}")

    client.search.side_effect = fake_search
    client.extract.return_value = {"results": []}
    mock_tavily_client.return_value = client

    result = research.research("Acme Corp", lambda status: None, "fake-key")

    assert result.sources
    assert all(failing_query not in url for url in (s["url"] for s in result.sources))
