"""What the code enforces on a brief, whatever the model wrote."""

import copy
from datetime import date

import brief_doc
import brief_rules
import case_studies
from evidence import EvidenceItem, Source
from tests.brief_fixtures import SAMPLE_DOC, writer_output

TODAY = date(2026, 10, 5)
NOTE = {"searches": 21, "pages": 17, "seconds": 203, "stopped_by": "finished"}


# What the opened pages state about the sample company's basics.
STATED = "Northwind Energy Corporation is headquartered in Dallas, Texas. Revenue was $28B. It has 5,200 employees."


def _sources(count=4, stated=STATED):
    """The opened pages, numbered as the writer saw them, each stating the same basics."""
    return tuple(
        Source(
            n=n, url=f"https://example.com/{n}", title=f"Page {n}", date="", data_broker=False,
            facts=(EvidenceItem("Company basics.", "basics", f"https://example.com/{n}", opened=True, quote=stated),),
        )
        for n in range(1, count + 1)
    )


def _finalize(output=None, sources=None, language="en"):
    return brief_rules.finalize(
        output if output is not None else writer_output(),
        sources if sources is not None else _sources(),
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


def test_what_is_said_about_a_person_needs_a_source_too():
    output = writer_output(people=[
        {"name": "Pat Lee", "role": "VP Infrastructure", "note": "Signed the MPLS contract.", "sources": [99]},
        {"name": "Dana Ruiz", "role": "CIO", "note": "Named in the annual report.", "sources": [2]},
    ])
    people = _finalize(output)["people"]
    assert people[0] == {"name": "", "role": "VP Infrastructure", "note": "", "sources": []}
    assert people[1]["note"] == "Named in the annual report."


# ── Headquarters, revenue and headcount come from the evidence or stay empty ──

def _stats(**changes):
    return _finalize(writer_output(stats={**SAMPLE_DOC["stats"], **changes}))["stats"]


def test_basics_the_evidence_states_are_kept_as_written():
    stats = _stats()
    assert (stats["hq"], stats["revenue"], stats["employees"]) == ("Dallas, TX", "$28B", "5,200")


def test_a_figure_that_is_not_in_the_evidence_is_left_empty():
    assert _stats(revenue="$31.4B")["revenue"] == ""
    assert _stats(employees="About 9,000")["employees"] == ""
    assert _stats(revenue="$28B in FY24, up from $26B")["revenue"] == ""  # one figure of the two is not there


def test_a_value_with_no_figure_in_it_is_left_empty():
    assert _stats(revenue="Not disclosed")["revenue"] == ""
    assert _stats(employees="A large workforce")["employees"] == ""


def test_the_same_figure_written_another_way_is_still_the_evidence_s_figure():
    assert _stats(employees="5200 employees")["employees"] == "5200 employees"
    assert _stats(revenue="Revenue $28B")["revenue"] == "Revenue $28B"


def test_a_headquarters_the_evidence_never_mentions_is_left_empty():
    assert _stats(hq="Houston, TX")["hq"] == ""
    assert _stats(hq="dallas, texas")["hq"] == "dallas, texas"
    assert _stats(hq="TX")["hq"] == ""  # too little to check


def test_the_other_basics_are_the_writer_s_summary_and_are_left_alone():
    stats = _stats()
    assert stats["industry"] == "Refining" and stats["ownership"] == "Public"
    assert stats["cloud_network"].startswith("Azure, ExpressRoute")


def test_with_no_evidence_about_the_basics_all_three_are_empty():
    doc = _finalize(sources=_sources(stated="A posting lists ExpressRoute and Virtual WAN."))
    assert (doc["stats"]["hq"], doc["stats"]["revenue"], doc["stats"]["employees"]) == ("", "", "")


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


def test_a_translated_proof_whose_numbers_differ_from_the_knowledge_base_is_replaced():
    michaels = case_studies.story_by_id("michaels").result
    koch = case_studies.story_by_id("koch").result
    cases = [
        ("michaels", "Unas 2,000 tiendas conectadas en tres semanas.", michaels),          # a different number
        ("michaels", "Unas 1,400 tiendas en tres semanas, con 50% menos costo.", michaels),  # an added number
        ("michaels", "Unas 1.400 tiendas conectadas a Google Cloud en tres semanas.", None),  # same number, Spanish separator
        ("koch", "Reducción del 40% en la complejidad de la red.", koch),                 # a number the table never had
        ("koch", "Reducción significativa de la complejidad de la red.", None),
    ]
    for story_id, translated, expected in cases:
        angle = _angle([1], story_id=story_id)
        angle["story"]["result"] = translated
        result = _finalize(writer_output(angles=[angle]), language="es")["angles"][0]["story"]["result"]
        assert result == (expected or translated), translated


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


def test_links_and_addresses_are_removed_from_everything_the_model_wrote():
    """A brief is read by partners: nothing the model wrote may carry them to a web address."""
    output = writer_output()
    output["fit"]["verdict"] = "Strong fit, see [the full report](https://evil.example/login) for more."
    output["fit"]["lead"] = "Call the CIO or visit www.evil.example/now today."
    output["angles"][0]["alkira"] = "Details at HTTPS://evil.example/a?b=c and ![x](http://evil.example/p.png) here."
    output["angles"][0]["evidence"][0]["text"] = "A posting lists ExpressRoute http://evil.example"
    output["snapshot"]["wan"]["text"] = "SD-WAN [vendor](http://evil.example)"
    output["people"][0]["note"] = "Profile: https://evil.example/u/1"
    output["questions"][0]["question"] = "Have you seen https://evil.example ?"
    output["unconfirmed"] = ["Confirm at https://evil.example/confirm"]
    output["company"]["identity_note"] = "Not [Northwind Traders](https://evil.example)."
    doc = _finalize(output)
    assert doc["fit"]["verdict"] == "Strong fit, see the full report for more."
    assert doc["fit"]["lead"] == "Call the CIO or visit today."
    assert doc["angles"][0]["alkira"] == "Details at and x here."
    assert doc["snapshot"]["wan"]["text"] == "SD-WAN vendor"
    assert doc["company"]["identity_note"] == "Not Northwind Traders."
    everything = brief_doc.dump({**doc, "references": [], "company": {**doc["company"], "website": ""}})
    assert "evil.example" not in everything and "](" not in everything


def test_scrubbing_leaves_identifiers_and_the_writer_output_alone():
    output = writer_output()
    doc = _finalize(output)
    assert doc["angles"][0]["use_case"] == "multi_cloud" and doc["angles"][0]["story"]["id"] == "koch"
    assert output == writer_output()
