"""The customer-story table in the knowledge base, read as data.

The writer picks a story by its ID. The customer name printed on a brief
comes from this table, so a story that is not in the knowledge base can
never be named as proof.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CASE_STUDIES_PATH = (
    Path(__file__).parent / "skills" / "alkira-customer" / "references" / "case-studies.md"
)
TABLE_HEADING = "## Story Matching Table"
COLUMN_COUNT = 6
# The story ID a writer uses when nothing in the table matches.
NO_STORY = "none"
# The situations that make a company an Alkira fit. Angles, evidence and
# stories all use this one vocabulary.
SITUATIONS: tuple[str, ...] = (
    "multi_cloud",
    "china_global",
    "firewall_consolidation",
    "m_and_a",
    "network_modernization",
    "site_rollout",
    "partner_connectivity",
)


class CaseStudyTableError(ValueError):
    """The story table in case-studies.md is missing or malformed."""


@dataclass(frozen=True)
class Story:
    id: str
    customer: str
    public: bool
    situations: tuple[str, ...]
    industry: str
    result: str


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(cells: list[str]) -> bool:
    return all(cell and set(cell) <= set("-: ") for cell in cells)


def _table_rows(markdown: str) -> list[list[str]]:
    """The data rows under the table heading: no header row, no separator row."""
    _, found, after = markdown.partition(TABLE_HEADING)
    if not found:
        raise CaseStudyTableError(f"no {TABLE_HEADING!r} section")
    table: list[list[str]] = []
    for line in after.splitlines()[1:]:
        if line.startswith("#"):
            break
        if line.lstrip().startswith("|"):
            table.append(_cells(line))
    rows = [cells for cells in table[1:] if not _is_separator(cells)]
    if not rows:
        raise CaseStudyTableError("the story table has no rows")
    return rows


def _story(cells: list[str]) -> Story:
    if len(cells) != COLUMN_COUNT:
        raise CaseStudyTableError(f"expected {COLUMN_COUNT} columns, got {len(cells)}: {cells}")
    story_id, customer, public, situations, industry, result = cells
    if public not in ("yes", "no"):
        raise CaseStudyTableError(f"{story_id}: Public must be yes or no, got {public!r}")
    tags = tuple(tag.strip() for tag in situations.split(",") if tag.strip())
    unknown = [tag for tag in tags if tag not in SITUATIONS]
    if unknown or not tags:
        raise CaseStudyTableError(f"{story_id}: bad situations {situations!r}")
    if not (story_id and customer and industry and result) or story_id == NO_STORY:
        raise CaseStudyTableError(f"incomplete row: {cells}")
    return Story(story_id, customer, public == "yes", tags, industry, result)


def parse_story_table(markdown: str) -> tuple[Story, ...]:
    stories = tuple(_story(cells) for cells in _table_rows(markdown))
    ids = [story.id for story in stories]
    duplicates = sorted({story_id for story_id in ids if ids.count(story_id) > 1})
    if duplicates:
        raise CaseStudyTableError(f"duplicate story IDs: {duplicates}")
    return stories


@lru_cache(maxsize=1)
def load_stories() -> tuple[Story, ...]:
    """Every story in the knowledge base. Read once per process."""
    return parse_story_table(CASE_STUDIES_PATH.read_text(encoding="utf-8"))


def story_by_id(story_id: str) -> Story | None:
    for story in load_stories():
        if story.id == story_id:
            return story
    return None
