"""Tests for the markdown renderer's link handling.

md_to_html output is rendered with unsafe_allow_html=True, and URLs now
originate from arbitrary third-party pages, so only http(s) may reach an href.
"""

from app import inline


def test_http_and_https_links_render_as_anchors():
    assert inline("[Acme](https://acme.com/ir)") == (
        '<a href="https://acme.com/ir" target="_blank">Acme</a>'
    )
    assert '<a href="http://acme.com"' in inline("[Acme](http://acme.com)")


def test_javascript_scheme_is_left_as_plain_text():
    out = inline("[Click](javascript:alert(1))")
    assert "<a" not in out
    assert "href" not in out


def test_data_scheme_is_left_as_plain_text():
    out = inline("[Click](data:text/html,<script>alert(1)</script>)")
    assert "<a" not in out
    assert "href" not in out


def test_relative_and_scheme_relative_links_are_left_as_plain_text():
    assert "<a" not in inline("[Click](/admin)")
    assert "<a" not in inline("[Click](//evil.com)")


def test_reference_line_links_still_render():
    """The `[N] Description - URL` reference format is unaffected."""
    out = inline("[1] Acme investor relations - https://acme.com/ir")
    assert '<a href="https://acme.com/ir" target="_blank">[1] Acme' in out
