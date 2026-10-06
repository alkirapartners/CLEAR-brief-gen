"""Stories from Alkira's use-case deck: each anonymous, under the label its owner gave it, with no money in it."""

import re
from pathlib import Path

import pytest

import case_studies

SOURCES = (Path(__file__).resolve().parent.parent / "docs" / "knowledge-base-sources.md").read_text(encoding="utf-8")
# How the source list marks a story taken from the deck.
_DECK_LINE = re.compile(
    r"^- `([a-z0-9-]+)` — Alkira use-case stories deck, internal, undated; customer anonymised", re.MULTILINE,
)
DECK_IDS: list[str] = _DECK_LINE.findall(SOURCES)
# The stories the owner approved, each with its label and the words its result must carry.
APPROVED: dict[str, tuple[str, str]] = {
    "airline-hub": ("A large airline", "in 1 hour, remotely"),
    "railroad-multicloud": (
        "A large railroad", "2 regions, 3 clouds, highly available firewalls and SD-WAN in 2 days",
    ),
    "retailer-latam": ("A large retailer", "200 retail stores in Latin America"),
    "clearing-house": ("A financial clearing house", "self-service portal"),
    "food-distributor": ("A large food distributor", "can eliminate 4 of its 6 connections to the cloud"),
}


def test_the_approved_stories_are_on_record_as_deck_stories():
    assert set(APPROVED) <= set(DECK_IDS)


@pytest.mark.parametrize("story_id", sorted(APPROVED))
def test_an_approved_story_is_told_under_its_label_and_says_what_its_page_says(story_id):
    label, words = APPROVED[story_id]
    story = case_studies.story_by_id(story_id)
    assert story is not None and story.customer == label and words in story.result


@pytest.mark.parametrize("story_id", DECK_IDS)
def test_every_deck_story_is_anonymous_and_carries_no_dollar_figure(story_id):
    story = case_studies.story_by_id(story_id)
    assert story is not None and story.public is False and "$" not in story.result


def test_the_clearing_house_gives_partner_connectivity_a_story_with_no_figure():
    story = case_studies.story_by_id("clearing-house")
    assert story.situations == ("partner_connectivity",) and not re.search(r"\d", story.result)
