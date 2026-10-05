"""What the code enforces on a brief, whatever the model wrote."""

import copy
from datetime import date

import brief_doc
import brief_rules
import case_studies
from tests.brief_fixtures import SAMPLE_DOC, writer_output

TODAY = date(2026, 10, 5)
NOTE = {"searches": 21, "pages": 17, "seconds": 203, "stopped_by": "finished"}


def _candidates(count=4):
    return [
        {"n": n, "title": f"Page {n}", "url": f"https://example.com/{n}", "date": "", "data_broker": False}
        for n in range(1, count + 1)
    ]


def _finalize(output=None, candidates=None, language="en"):
    return brief_rules.finalize(
        output if output is not None else writer_output(),
        candidates if candidates is not None else _candidates(),
        language, TODAY, NOTE,
    )


def _angle(sources, title="Angle", story_id="koch"):
    return {
        "title": title, "use_case": "multi_cloud",
        "evidence": [{"text": "A dated fact.", "date": "2026-09-01", "sources": sources}],
        "alkira": "What Alkira does.",
        "story": {"id": story_id, "customer": "Whoever", "result": "A result."},
    }


def test_the_document_carries_what_the_code_adds():
    doc = _finalize(language="es")
    assert doc["format"] == brief_doc.FORMAT_VERSION
    assert doc["language"] == "es" and doc["generated"] == "2026-10-05"
    assert doc["research"] == NOTE
    assert brief_doc.load(brief_doc.dump(doc)) == doc


def test_the_writer_output_is_not_changed_in_place():
    output = writer_output()
    before = copy.deepcopy(output)
    _finalize(output)
    assert output == before


# ── Only opened pages may be cited ───────────────────────────────

def test_references_are_the_cited_pages_only_renumbered_in_citation_order():
    output = writer_output(angles=[_angle([4]), _angle([2, 4], title="Second")])
    for key in output["snapshot"]:
        output["snapshot"][key] = {"text": "", "sources": []}
    output["people"] = []
    doc = _finalize(output)
    assert [(r["n"], r["url"]) for r in doc["references"]] == [
        (1, "https://example.com/4"), (2, "https://example.com/2"),
    ]
    assert doc["angles"][0]["evidence"][0]["sources"] == [1]
    assert doc["angles"][1]["evidence"][0]["sources"] == [2, 1]


def test_a_citation_of_a_page_that_was_never_opened_is_removed():
    doc = _finalize(writer_output(angles=[_angle([1, 99])]))
    assert doc["angles"][0]["evidence"][0]["sources"] == [1]
    assert all(ref["n"] <= len(doc["references"]) for ref in doc["references"])


def test_an_angle_whose_only_evidence_was_never_opened_is_removed():
    doc = _finalize(writer_output(angles=[_angle([99], title="Invented"), _angle([2], title="Real")]))
    assert [angle["title"] for angle in doc["angles"]] == ["Real"]


def test_an_evidence_line_with_no_text_is_removed():
    angle = _angle([1])
    angle["evidence"].append({"text": "   ", "date": "", "sources": [2]})
    doc = _finalize(writer_output(angles=[angle]))
    assert len(doc["angles"][0]["evidence"]) == 1


def test_an_unsourced_snapshot_line_becomes_not_found():
    output = writer_output()
    output["snapshot"]["wan"] = {"text": "MPLS everywhere, probably.", "sources": []}
    output["snapshot"]["firewalls"] = {"text": "Palo Alto.", "sources": [77]}
    doc = _finalize(output)
    assert doc["snapshot"]["wan"] == {"text": "", "sources": []}
    assert doc["snapshot"]["firewalls"] == {"text": "", "sources": []}
    assert doc["snapshot"]["clouds"]["text"] == "Azure is the primary cloud."


def test_a_name_without_a_source_is_reduced_to_the_role():
    output = writer_output(people=[
        {"name": "Pat Lee", "role": "VP Infrastructure", "note": "", "sources": []},
        {"name": "Dana Ruiz", "role": "CIO", "note": "", "sources": [2]},
        {"name": "", "role": "", "note": "nobody", "sources": []},
    ])
    people = _finalize(output)["people"]
    assert [(p["name"], p["role"]) for p in people] == [("", "VP Infrastructure"), ("Dana Ruiz", "CIO")]


# ── Angles are never padded, and the score follows them ──────────

def test_more_than_three_angles_are_cut_to_three():
    angles = [_angle([1], title=f"Angle {i}") for i in range(1, 6)]
    doc = _finalize(writer_output(angles=angles))
    assert [a["title"] for a in doc["angles"]] == ["Angle 1", "Angle 2", "Angle 3"]


def test_a_one_angle_brief_stays_at_one_angle():
    doc = _finalize(writer_output(angles=[_angle([1])], fit={"score": 3, "verdict": "v", "lead": "l"}))
    assert len(doc["angles"]) == 1 and doc["fit"]["score"] == 3


def test_a_score_of_five_needs_two_angles():
    doc = _finalize(writer_output(angles=[_angle([1])], fit={"score": 5, "verdict": "v", "lead": "l"}))
    assert doc["fit"]["score"] == 4


def test_a_brief_with_no_evidenced_angle_cannot_score_above_two():
    doc = _finalize(writer_output(angles=[_angle([99])], fit={"score": 4, "verdict": "v", "lead": "l"}))
    assert doc["angles"] == [] and doc["fit"]["score"] == 2


def test_a_low_score_is_never_raised():
    doc = _finalize(writer_output(fit={"score": 2, "verdict": "v", "lead": "l"}))
    assert doc["fit"]["score"] == 2


# ── Customer stories come from the knowledge base ────────────────

def test_the_customer_name_comes_from_the_story_table_not_the_model():
    doc = _finalize(writer_output(angles=[_angle([1], story_id="michaels")]))
    story = doc["angles"][0]["story"]
    assert story["customer"] == "Michaels"  # the model wrote "Whoever"


def test_in_english_the_proof_is_the_knowledge_base_wording_not_the_model_s():
    doc = _finalize(writer_output(angles=[_angle([1], story_id="michaels")]))
    michaels = case_studies.story_by_id("michaels")
    assert doc["angles"][0]["story"] == {
        "id": "michaels", "customer": "Michaels", "result": michaels.result,
    }
    assert "1,400 stores" in doc["angles"][0]["story"]["result"]


def test_in_spanish_the_translated_proof_is_kept_and_a_missing_one_falls_back_to_the_table():
    translated = _angle([1], story_id="michaels")
    translated["story"]["result"] = "Unas 1,400 tiendas conectadas en tres semanas."
    blank = _angle([2], story_id="koch", title="Second")
    blank["story"]["result"] = "  "
    doc = _finalize(writer_output(angles=[translated, blank]), language="es")
    assert doc["angles"][0]["story"]["result"] == "Unas 1,400 tiendas conectadas en tres semanas."
    assert doc["angles"][1]["story"]["result"] == case_studies.story_by_id("koch").result


def test_a_story_that_is_not_in_the_knowledge_base_is_dropped():
    doc = _finalize(writer_output(angles=[_angle([1], story_id="globex")]))
    assert doc["angles"][0]["story"] == {"id": "none", "customer": "", "result": ""}


# ── Lists ────────────────────────────────────────────────────────

def test_questions_are_capped_at_four_and_blanks_are_dropped():
    question = SAMPLE_DOC["questions"][0]
    blank = {**question, "question": " "}
    doc = _finalize(writer_output(questions=[question, blank] + [question] * 5))
    assert len(doc["questions"]) == 4


def test_blank_list_items_are_dropped():
    doc = _finalize(writer_output(unconfirmed=["  ", "Who owns the WAN. "], raise_score=[""]))
    assert doc["unconfirmed"] == ["Who owns the WAN."] and doc["raise_score"] == []


# ── Links ────────────────────────────────────────────────────────

def test_a_website_that_is_not_a_public_web_address_is_dropped():
    for bad in ("javascript:alert(1)", "http://127.0.0.1/admin", "ftp://files.example.com", "not a url"):
        company = {**SAMPLE_DOC["company"], "website": bad}
        assert _finalize(writer_output(company=company))["company"]["website"] == ""


def test_a_real_website_is_kept_rebuilt_from_its_parts():
    company = {**SAMPLE_DOC["company"], "website": " HTTPS://WWW.Northwind.example/about#team "}
    doc = _finalize(writer_output(company=company))
    assert doc["company"]["website"] == "https://www.northwind.example/about"
