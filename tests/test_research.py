"""Tests for the Tavily research layer. No live network calls."""

import research


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
