"""A brief stored by older code must open in newer code, and one that cannot be read must never raise."""

import copy
import json
import typing
from datetime import datetime

import pytest

import brief_doc
import brief_text
import brief_view
import pdf
from tests.api_fakes import AUTH, FakeRepo, make_client
from tests.brief_fixtures import SAMPLE_DOC, make_doc

WHEN = datetime(2026, 10, 5, 12, 0)


def _row(text):
    return {
        "id": "b-1", "email": "partner@example.com", "company": "Northwind", "score": 5,
        "brief_md": text, "created_at": "2026-10-05T12:00:00+00:00",
    }


def _as_first_written():
    """The sample as the first JSON briefs were stored: none of the fields added since."""
    doc = copy.deepcopy(SAMPLE_DOC)
    doc.pop("version", None)
    for angle in doc["angles"]:
        for added in ("deal_date", "deal_status", "deal_pending_quote"):
            angle.pop(added, None)
    for question in doc["questions"]:
        question.pop("angle", None)
    for number, reference in enumerate(doc["references"]):
        reference.pop("source_type", None)
        reference.pop("open_posting", None)
        reference["data_broker"] = number == 1
    return doc


# ── The version field ────────────────────────────────────────────

def test_a_brief_is_stored_with_the_revision_of_the_document_it_was_written_as():
    assert make_doc()["version"] == brief_doc.DOC_VERSION
    assert brief_doc.load(brief_doc.dump(make_doc()))["version"] == brief_doc.DOC_VERSION


def test_a_finalized_brief_carries_the_current_revision():
    from tests.test_brief_rules import _finalize
    assert _finalize()["version"] == brief_doc.DOC_VERSION


# ── Older documents ──────────────────────────────────────────────

def test_a_document_without_the_newest_fields_still_loads_with_their_defaults():
    doc = brief_doc.load(json.dumps(_as_first_written()))
    assert doc is not None and doc["version"] == 1
    assert [(a["deal_date"], a["deal_status"], a["deal_pending_quote"]) for a in doc["angles"]] == [("", "none", "")] * 2
    assert [q["angle"] for q in doc["questions"]] == [0, 0]
    assert [(r["source_type"], r["open_posting"]) for r in doc["references"]] == [
        ("second_hand", False), ("last_resort", False),  # a data broker was the old flag
    ]


def test_a_document_without_the_newest_fields_renders_for_the_page_as_text_and_as_a_pdf():
    text = json.dumps(_as_first_written())
    detail = brief_view.to_detail(_row(text))
    assert detail["format"] == 2 and detail["doc"] is not None and detail["score"] == 5
    assert len(detail["entryPoints"]) == 2 and all(p["signal"] and p["proof"] for p in detail["entryPoints"])
    assert "Annual report (last-resort source)" in detail["referencesMd"]
    assert brief_text.render(brief_doc.load(text)).startswith("# Northwind Energy")
    assert pdf.generate_brief_pdf(text, "Northwind Energy", 5, WHEN, "en").startswith(b"%PDF-")
    summary = brief_view.to_summary(_row(text))
    assert summary["company"] == "Northwind Energy"


def test_an_older_document_is_served_and_downloaded_through_the_api():
    repo = FakeRepo()
    row = repo.seed("partner@example.com", company="Northwind", brief_md=json.dumps(_as_first_written()), score=5)
    api = make_client(repo)
    assert api.get(f"/api/brief/briefs/{row['id']}", headers=AUTH).json()["data"]["format"] == 2
    assert api.get(f"/api/brief/briefs/{row['id']}/pdf", headers=AUTH).content.startswith(b"%PDF-")


def test_a_document_from_newer_code_with_fields_this_code_does_not_know_still_loads():
    doc = make_doc(version=brief_doc.DOC_VERSION + 3, layout_hint="bento")
    doc["angles"][0]["confidence"] = "high"
    doc["references"][0]["archived_copy"] = "https://example.com/archive"
    loaded = brief_doc.load(json.dumps(doc))
    assert loaded is not None and loaded["company"]["name"] == "Northwind Energy"
    assert brief_view.to_detail(_row(json.dumps(doc)))["format"] == 2


# ── Every field added from here on needs a default ───────────────

DOCUMENT_TYPES = (
    brief_doc.Company, brief_doc.Stats, brief_doc.Fit, brief_doc.EvidenceLine, brief_doc.Story,
    brief_doc.Angle, brief_doc.SnapshotLine, brief_doc.Snapshot, brief_doc.Person, brief_doc.Question,
    brief_doc.Reference, brief_doc.ResearchNote, brief_doc.BriefDoc,
)


@pytest.mark.parametrize("document_type", DOCUMENT_TYPES, ids=lambda t: t.__name__)
def test_every_field_is_either_in_the_first_stored_shape_or_has_a_default_at_load(document_type):
    """Add a field to the document without a default here and an older stored brief stops opening."""
    name = document_type.__name__
    fields = set(typing.get_type_hints(document_type))
    assert fields == brief_doc.FIRST_FIELDS[name] | set(brief_doc.ADDED_FIELDS.get(name, {})), name


# ── Documents that cannot be read ────────────────────────────────

UNREADABLE = [
    '{"format": 2, "angles": "everything"}',
    '{"format": 2, "angles": [1, 2, 3], "questions": null, "references": {"n": 1}}',
    '{"format": 2, "angles": [{"evidence": "none"}], "references": [7]}',
    '{"format": 2, "version": "latest"}',
    json.dumps({**SAMPLE_DOC, "fit": {"score": "high"}}),
    json.dumps({**SAMPLE_DOC, "snapshot": []}),
    json.dumps({**SAMPLE_DOC, "angles": [{**SAMPLE_DOC["angles"][0], "deal_status": "sometime"}]}),
    '{"format": 2, "company": {"name": {"nested": true}}}',
    "{" + '"a":' * 5000 + "1" + "}" * 5000,
]


@pytest.mark.parametrize("text", UNREADABLE, ids=range(len(UNREADABLE)))
def test_a_document_that_cannot_be_read_degrades_to_an_empty_brief_and_never_raises(text):
    assert brief_doc.load(text) is None
    detail = brief_view.to_detail(_row(text))
    assert detail["format"] == 1 and detail["doc"] is None and detail["entryPoints"] == []
    assert brief_view.to_summary(_row(text))["id"] == "b-1"
    assert pdf.generate_brief_pdf(text, "Typed Name", 0, WHEN, "en").startswith(b"%PDF-")
