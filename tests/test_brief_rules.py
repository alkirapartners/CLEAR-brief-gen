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


def _sources(count=4, stated=STATED, source_type="first_hand", dated="2026-09-01", dates=None):
    """The opened pages, numbered as the writer saw them, each stating the same basics.

    ``dates`` gives single pages a date of their own, by number.
    """
    return tuple(
        Source(
            n=n, url=f"https://example.com/{n}", title=f"Page {n}",
            date=(dates or {}).get(n, dated), source_type=source_type,
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


def _angle(sources, title="Angle", story_id="koch", use_case="multi_cloud"):
    return {
        "title": title, "use_case": use_case,
        "evidence": [{"text": "A posting lists SD-WAN and ExpressRoute.", "date": "2026-09-01", "sources": sources}],
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


def test_a_name_from_trade_press_or_a_data_broker_is_reduced_to_the_role():
    """A person is named only when the company itself names them."""
    output = writer_output(people=[{"name": "Dana Ruiz", "role": "CIO", "note": "Runs IT.", "sources": [2]}])
    for kind in ("second_hand", "last_resort"):
        (person,) = _finalize(output, sources=_sources(source_type=kind))["people"]
        assert (person["name"], person["role"], person["note"]) == ("", "CIO", "Runs IT.")
    (named,) = _finalize(output)["people"]
    assert named["name"] == "Dana Ruiz"


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


def test_a_score_of_one_or_two_carries_no_angles():
    """The table says a 1 or 2 found no evidenced use case, so the brief presents none."""
    for low in (1, 2):
        doc = _finalize(writer_output(angles=[_angle([1]), _angle([2], title="Second")], fit={"score": low, "verdict": "v", "lead": "l"}))
        assert doc["angles"] == [] and doc["fit"]["score"] == low
    kept = _finalize(writer_output(angles=[_angle([1])], fit={"score": 3, "verdict": "v", "lead": "l"}))
    assert len(kept["angles"]) == 1


# ── The score cannot outrun the sources ──────────────────────────

FIVE = {"score": 5, "verdict": "Strong fit.", "lead": "Call the CIO."}


def test_an_angle_resting_on_second_hand_sources_holds_the_score_at_three_and_the_brief_says_why():
    doc = _finalize(writer_output(fit=FIVE), sources=_sources(source_type="second_hand"))
    assert doc["fit"]["score"] == 3 and len(doc["angles"]) == 2
    assert doc["fit"]["verdict"] == (
        "Strong fit. Score held at 3: no use case has first-hand evidence dated in the last two years."
    )


def test_a_use_case_whose_first_hand_source_is_undated_is_held_at_three():
    """A dated trade-press line keeps the angle standing. The undated posting cannot lift it."""
    angle = _angle([1])
    angle["evidence"].append({"text": "Trade press reports the SD-WAN rollout.", "date": "", "sources": [2]})
    sources = (
        _sources(1, dated="")[0],  # the company's own posting, with no date on it
        _sources(2, source_type="second_hand")[1],
    )
    doc = _finalize(writer_output(angles=[angle], fit=FIVE), sources=sources)
    assert len(doc["angles"]) == 1 and doc["fit"]["score"] == 3


def test_one_first_hand_use_case_holds_the_score_at_four_and_the_brief_says_why():
    doc = _finalize(writer_output(angles=[_angle([1])], fit=FIVE))
    assert doc["fit"]["score"] == 4
    assert doc["fit"]["verdict"].startswith("Strong fit. Score held at 4: a higher score needs two use cases")


def test_the_reason_is_given_in_the_language_of_the_brief():
    doc = _finalize(writer_output(angles=[_angle([1])], fit=FIVE), language="es")
    assert "Puntuación limitada a 4" in doc["fit"]["verdict"]


def test_a_score_the_sources_support_is_left_as_written_with_no_note():
    doc = _finalize(writer_output(fit=FIVE))
    assert doc["fit"] == FIVE
    lower = {"score": 3, "verdict": "A fair fit.", "lead": "l"}
    assert _finalize(writer_output(fit=lower))["fit"] == lower


# ── An evidence line carries its source's date, not one of the model's own ──

def _dated_line(written, cited, **kwargs):
    """The date the first line ends up with. A second, dated line keeps the angle standing."""
    angle = _angle(cited)
    angle["evidence"][0]["date"] = written
    angle["evidence"].append({"text": "A dated press release.", "date": "2026-08-15", "sources": [4]})
    fit = {"score": 3, "verdict": "v", "lead": "l"}
    return _finalize(writer_output(angles=[angle], fit=fit), **kwargs)["angles"][0]["evidence"][0]["date"]


def test_a_line_keeps_a_date_that_is_its_source_s_date():
    assert _dated_line("2026-09-01", [1]) == "2026-09-01"


def test_a_date_the_source_does_not_give_is_replaced_by_the_one_it_does():
    assert _dated_line("2026-10-04", [1]) == "2026-09-01"
    assert _dated_line("", [1]) == "2026-09-01"
    assert _dated_line("last month", [1]) == "2026-09-01"


def test_a_line_whose_sources_give_no_date_is_undated_whatever_the_model_wrote():
    assert _dated_line("2026-09-30", [1], sources=_sources(dates={1: "", 4: "2026-08-15"})) == ""


def test_a_source_dated_in_the_future_dates_nothing():
    assert _dated_line("2027-03-01", [1], sources=_sources(dates={1: "2027-03-01", 4: "2026-08-15"})) == ""


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


# ── Padding and noise are removed ────────────────────────────────

def _with_lines(*texts, use_case="m_and_a", sources=(2,)):
    angle = _angle(list(sources), title="Padded", use_case=use_case)
    angle["evidence"] = [{"text": text, "date": "2026-01-03", "sources": list(sources)} for text in texts]
    return angle


def test_risk_language_and_headcount_lines_are_removed_from_an_angle():
    angle = _with_lines(
        "Advance sold Worldpac and agreed the final working capital adjustment in January.",
        "The 10-K includes transition services risk language tied to the divestiture.",
        "The 10-K reports 28,274 full-time team members.",
    )
    doc = _finalize(writer_output(angles=[_angle([1]), angle], fit=THREE))
    assert [line["text"] for line in doc["angles"][1]["evidence"]] == [
        "Advance sold Worldpac and agreed the final working capital adjustment in January.",
    ]


def test_an_angle_built_only_from_risk_language_does_not_survive():
    padded = _with_lines(
        "The 10-K cites an aging technological infrastructure risk.",
        "The 10-K includes transition services risk language tied to the divestiture.",
    )
    doc = _finalize(writer_output(angles=[_angle([1], title="Real"), padded], fit=FIVE))
    assert [angle["title"] for angle in doc["angles"]] == ["Real"]
    assert doc["fit"]["score"] == 4  # one use case is left, and the score follows


def test_an_angle_with_no_dated_fact_does_not_survive():
    doc = _finalize(writer_output(angles=[_angle([1])], fit=THREE), sources=_sources(dated=""))
    assert doc["angles"] == [] and doc["fit"]["score"] == 2


def test_a_delivery_network_closing_buildings_is_not_a_network_modernization_angle():
    ups = _with_lines(
        "UPS closed 23 buildings and identified 27 more for closure under Network Reconfiguration.",
        "The proxy says the company strategy centres on network optimization.",
        use_case="network_modernization",
    )
    doc = _finalize(writer_output(angles=[ups, _angle([1], title="Real")], fit=THREE))
    assert [angle["title"] for angle in doc["angles"]] == ["Real"]
    as_sites = {**ups, "use_case": "site_rollout"}
    assert len(_finalize(writer_output(angles=[as_sites], fit=THREE))["angles"]) == 1


def test_a_plant_network_line_that_is_not_about_control_systems_becomes_not_found():
    output = writer_output()
    output["snapshot"]["plant_networks"] = {"text": "RFID sensing network with readers in package cars.", "sources": [1]}
    assert _finalize(output)["snapshot"]["plant_networks"] == {"text": "", "sources": []}
    output["snapshot"]["plant_networks"] = {"text": "OT networks at five refineries, segmented from IT.", "sources": [1]}
    assert _finalize(output)["snapshot"]["plant_networks"]["text"].startswith("OT networks")


# ── A story fits its angle's situation, and is told once ─────────

NO_STORY = {"id": "none", "customer": "", "result": ""}
THREE = {"score": 3, "verdict": "v", "lead": "l"}


def _stories(*angles):
    return [angle["story"] for angle in _finalize(writer_output(angles=list(angles), fit=THREE))["angles"]]


def test_a_story_about_another_situation_is_removed_from_the_angle():
    """The M&A story is not proof for a network-modernization angle."""
    (story,) = _stories(_angle([1], story_id="nemertes-4", use_case="network_modernization"))
    assert story == NO_STORY
    (kept,) = _stories(_angle([1], story_id="nemertes-4", use_case="m_and_a"))
    assert kept["id"] == "nemertes-4"


def test_every_story_in_the_table_is_accepted_for_each_of_its_own_situations_and_no_other():
    for known in case_studies.load_stories():
        for use_case in case_studies.SITUATIONS:
            (story,) = _stories(_angle([1], story_id=known.id, use_case=use_case))
            assert (story["id"] == known.id) is (use_case in known.situations), (known.id, use_case)


def test_a_story_is_told_once_in_a_brief():
    first, second = _stories(
        _angle([1], story_id="michaels", use_case="network_modernization"),
        _angle([2], title="Second", story_id="michaels", use_case="site_rollout"),
    )
    assert first["id"] == "michaels" and second == NO_STORY


def test_a_story_on_an_angle_that_was_removed_is_still_free_for_the_next_angle():
    (story,) = _stories(
        _angle([99], title="Invented", story_id="michaels"),
        _angle([2], title="Real", story_id="michaels"),
    )
    assert story["id"] == "michaels"


def test_an_angle_may_go_without_a_story():
    first, second = _stories(_angle([1], story_id="none"), _angle([2], title="Second", story_id="none"))
    assert first == NO_STORY and second == NO_STORY


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


# ── The ticker is stated one way ─────────────────────────────────

def test_the_ticker_is_stored_as_exchange_and_symbol_whatever_the_model_wrote():
    for written, stored_as in (
        ("AAP (NYSE)", "NYSE: AAP"),
        ("NYSE: NWE", "NYSE: NWE"),
        ("SHE:300866 (Shenzhen); also listed in Hong Kong since 2 July", "SHE: 300866"),
        ("Privately held", ""),
    ):
        company = {**SAMPLE_DOC["company"], "ticker": written}
        assert _finalize(writer_output(company=company))["company"]["ticker"] == stored_as


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
