"""Every story in the knowledge base has its source on record, and the record names documents, not files."""

import re
from pathlib import Path

import case_studies

SOURCES_PATH = Path(__file__).resolve().parent.parent / "docs" / "knowledge-base-sources.md"
SOURCES = SOURCES_PATH.read_text(encoding="utf-8")
_LINE = re.compile(r"^- `([a-z0-9-]+)` — (.+)$", re.MULTILINE)
_PAGE = re.compile(r"\bpp?\. \d")


def test_every_story_has_exactly_one_line_in_the_source_list():
    """Add a story to the table and this fails until its source is written down."""
    documented = [story_id for story_id, _ in _LINE.findall(SOURCES)]
    assert sorted(documented) == sorted(story.id for story in case_studies.load_stories())


def test_every_source_line_gives_a_page_or_says_the_source_was_not_opened():
    for story_id, line in _LINE.findall(SOURCES):
        assert _PAGE.search(line) or "not opened" in line, story_id


def test_the_source_list_names_documents_and_never_a_path_on_someone_s_machine():
    for marker in ("/Users/", "Collateral/", "Downloads", ".pdf", ".pptx", "\\"):
        assert marker not in SOURCES, marker
