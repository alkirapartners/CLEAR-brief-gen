"""The JSON brief document: schema, validation, and telling new from legacy."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import get_args

import pytest

import brief_doc
import case_studies
from brief_doc import BriefFormatError
from tests.brief_fixtures import SAMPLE_DOC, SAMPLE_JSON_BRIEF, make_doc, stored, writer_output
from tests.test_pdf import SAMPLE_FULL_BRIEF

REPO_ROOT = Path(__file__).resolve().parent.parent
# What structured outputs accept. Anything else is rejected by the API or ignored.
ALLOWED_KEYWORDS = {
    "type", "properties", "required", "additionalProperties", "items",
    "enum", "$ref", "$defs", "title", "description",
}


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item)


# ── Writer output ────────────────────────────────────────────────

def test_a_complete_writer_output_is_accepted():
    parsed = brief_doc.parse_writer_output(json.dumps(writer_output()))
    assert parsed["fit"]["score"] == 5
    assert parsed["angles"][0]["use_case"] == "multi_cloud"


@pytest.mark.parametrize("text", [
    "",
    "Sure! Here is the brief.",
    "[]",
    json.dumps({k: v for k, v in writer_output().items() if k != "fit"}),
    json.dumps(writer_output(fit={"score": 6, "verdict": "x", "lead": "y"})),
    json.dumps(writer_output(fit={"score": "high", "verdict": "x", "lead": "y"})),
    json.dumps(writer_output(angles="none")),
])
def test_anything_else_is_refused(text):
    with pytest.raises(BriefFormatError):
        brief_doc.parse_writer_output(text)


def test_an_angle_with_an_unknown_use_case_is_refused():
    angles = make_doc()["angles"]
    angles[0]["use_case"] = "erp_project"
    with pytest.raises(BriefFormatError):
        brief_doc.parse_writer_output(json.dumps(writer_output(angles=angles)))


def test_a_brief_with_no_angles_is_valid():
    parsed = brief_doc.parse_writer_output(json.dumps(writer_output(angles=[])))
    assert parsed["angles"] == []


# ── The schema sent to the API ───────────────────────────────────

def test_the_schema_uses_only_what_structured_outputs_support():
    for node in _walk(brief_doc.WRITER_SCHEMA):
        if "type" not in node and "$ref" not in node:
            continue  # a properties map or a $defs map, not a schema
        assert set(node) <= ALLOWED_KEYWORDS, f"unsupported keyword in {sorted(node)}"
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert sorted(node["required"]) == sorted(node["properties"])


def test_the_schema_asks_only_for_what_the_model_writes():
    assert set(brief_doc.WRITER_SCHEMA["properties"]) == set(writer_output())
    assert "references" not in brief_doc.WRITER_SCHEMA["properties"]


def test_the_score_is_limited_to_one_through_five():
    score = brief_doc.WRITER_SCHEMA["$defs"]["Fit"]["properties"]["score"]
    assert score["enum"] == [1, 2, 3, 4, 5]


def test_use_cases_match_the_story_situations():
    assert get_args(brief_doc.UseCase) == case_studies.SITUATIONS


def test_the_schema_is_identical_in_a_fresh_process():
    """It is part of the cached request: any drift re-bills the whole prefix."""
    script = (
        "import hashlib, json, brief_doc;"
        "print(hashlib.sha256(json.dumps(brief_doc.WRITER_SCHEMA).encode()).hexdigest())"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    here = hashlib.sha256(json.dumps(brief_doc.WRITER_SCHEMA).encode()).hexdigest()
    assert result.stdout.strip() == here


# ── Stored briefs: new or legacy ─────────────────────────────────

def test_a_stored_document_is_loaded():
    doc = brief_doc.load(SAMPLE_JSON_BRIEF)
    assert doc is not None
    assert doc["company"]["name"] == "Northwind Energy"
    assert doc["references"][1]["url"].endswith("annual-report.pdf")


def test_dump_and_load_round_trip_and_keep_accents():
    company = {**SAMPLE_DOC["company"], "name": "Cementos Añejo"}
    text = brief_doc.dump(make_doc(company=company))
    assert "Añejo" in text
    assert brief_doc.load(text) == make_doc(company=company)


def test_legacy_markdown_is_not_a_json_brief():
    assert brief_doc.is_json_brief(SAMPLE_FULL_BRIEF) is False
    assert brief_doc.load(SAMPLE_FULL_BRIEF) is None


def test_a_legacy_brief_that_mentions_braces_stays_legacy():
    legacy = SAMPLE_FULL_BRIEF + '\nThe config is {"mode": "hub"}.\n'
    assert brief_doc.is_json_brief(legacy) is False


def test_a_json_brief_that_quotes_the_legacy_title_is_still_json():
    fit = {**SAMPLE_DOC["fit"], "verdict": "# ALKIRA OPPORTUNITY BRIEF is the old title."}
    assert brief_doc.load(stored(fit=fit)) is not None


@pytest.mark.parametrize("damaged", [
    None,
    "",
    "{",
    '{"format": 2}',
    '{"format": 3, "company": {}}',
    '["format", 2]',
    SAMPLE_JSON_BRIEF[:200],
])
def test_a_damaged_or_unknown_document_loads_as_nothing(damaged):
    assert brief_doc.load(damaged) is None
