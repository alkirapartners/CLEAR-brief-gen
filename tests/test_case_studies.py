"""The story table in the knowledge base must load as data."""

import pytest

import case_studies
from case_studies import CaseStudyTableError, parse_story_table

HEADER = "| ID | Customer | Public | Situations | Industry | Result |\n|---|---|---|---|---|---|\n"


def _table(*rows: str) -> str:
    return "# Notes\n\n## Story Matching Table\n\nIntro text.\n\n" + HEADER + "\n".join(rows) + "\n\n## Next\n"


def test_the_real_table_loads_and_includes_michaels():
    stories = case_studies.load_stories()
    michaels = case_studies.story_by_id("michaels")
    assert len(stories) >= 17
    assert michaels is not None and michaels.public is True
    assert michaels.customer == "Michaels" and michaels.industry == "Retail"
    assert "site_rollout" in michaels.situations
    assert "1,400 stores" in michaels.result and "three weeks" in michaels.result


def test_every_real_story_uses_a_known_situation_and_a_unique_id():
    stories = case_studies.load_stories()
    assert len({story.id for story in stories}) == len(stories)
    for story in stories:
        assert story.situations and set(story.situations) <= set(case_studies.SITUATIONS)
        assert story.customer and story.result


def test_an_anonymous_story_keeps_its_label_instead_of_a_name():
    story = case_studies.story_by_id("nemertes-10")
    assert story is not None and story.public is False
    assert "76 to 14" in story.result


def test_an_unknown_id_is_not_a_story():
    assert case_studies.story_by_id("acme") is None
    assert case_studies.story_by_id(case_studies.NO_STORY) is None


def test_rows_are_parsed_into_fields():
    (story,) = parse_story_table(_table("| a-1 | Acme | yes | m_and_a, multi_cloud | Retail | Did a thing. |"))
    assert story == case_studies.Story(
        "a-1", "Acme", True, ("m_and_a", "multi_cloud"), "Retail", "Did a thing."
    )


@pytest.mark.parametrize("row", [
    "| a-1 | Acme | maybe | m_and_a | Retail | Did a thing. |",
    "| a-1 | Acme | yes | cloud_stuff | Retail | Did a thing. |",
    "| a-1 | Acme | yes |  | Retail | Did a thing. |",
    "| a-1 | Acme | yes | m_and_a | Retail |",
    "| a-1 |  | yes | m_and_a | Retail | Did a thing. |",
    "| none | Acme | yes | m_and_a | Retail | Did a thing. |",
])
def test_a_malformed_row_is_refused(row):
    with pytest.raises(CaseStudyTableError):
        parse_story_table(_table(row))


def test_duplicate_ids_are_refused():
    row = "| a-1 | Acme | yes | m_and_a | Retail | Did a thing. |"
    with pytest.raises(CaseStudyTableError, match="duplicate"):
        parse_story_table(_table(row, row))


def test_a_file_without_the_table_is_refused():
    with pytest.raises(CaseStudyTableError):
        parse_story_table("# Case studies\n\nNo table here.\n")
    with pytest.raises(CaseStudyTableError, match="no rows"):
        parse_story_table("## Story Matching Table\n\n" + HEADER)
