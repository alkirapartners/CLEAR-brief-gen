"""A JSON brief must fill every field the current front end reads."""

import pytest

import brief_doc
import brief_view
import i18n
from tests.api_fakes import AUTH, FakeRepo, make_client
from tests.brief_fixtures import SAMPLE_DOC, SAMPLE_JSON_BRIEF, make_doc, stored

LEGACY_FIELDS = {
    "id", "company", "statsLine", "score", "scoreRationale", "infra", "signals",
    "entryPoints", "startersMd", "referencesMd", "language", "labels", "createdAt",
}


def _row(brief_md=SAMPLE_JSON_BRIEF, company="Northwind Energy", score=5):
    return {
        "id": "b-1", "email": "partner@example.com", "company": company, "score": score,
        "brief_md": brief_md, "created_at": "2026-10-05T12:00:00+00:00",
    }


def _detail(**changes):
    return brief_view.to_detail(_row(stored(**changes)))


def _one_angle():
    return make_doc()["angles"][:1]


# ── The fields the current page reads ────────────────────────────

def test_every_field_the_current_page_reads_is_present_and_filled():
    data = _detail()
    assert LEGACY_FIELDS <= set(data)
    assert data["company"] == "Northwind Energy"
    assert data["score"] == 5
    assert data["scoreRationale"].startswith("Strong fit: a hand-built Azure network")
    assert data["scoreRationale"].endswith("call the Director of Network Engineering.")
    assert data["createdAt"] == "2026-10-05T12:00:00+00:00"
    assert data["language"] == "en" and data["labels"] is i18n.LABELS["en"]


def test_the_stats_line_is_the_short_basics_the_page_shows_as_pills():
    line = _detail()["statsLine"]
    assert line == "HQ: Dallas, TX | Revenue: $28B | Employees: 5,200 | Industry: Refining | Ownership: Public (NYSE: NWE)"
    assert "Entity" not in line and "Cloud and network" not in line and "**" not in line


def test_long_basics_are_shortened_for_the_pills_and_kept_whole_in_the_document():
    stats = {
        **SAMPLE_DOC["stats"],
        "hq": "2323 Victory Avenue, Dallas, Texas",
        "revenue": "$26,869 million sales and other revenues, FY2025",
        "industry": "Independent energy company: refining and marketing of gasoline, diesel and jet fuel",
    }
    data = _detail(stats=stats)
    assert data["statsLine"].startswith(
        "HQ: Dallas, Texas | Revenue: $26.9B (FY2025) | Employees: 5,200 | Industry: Independent energy company |"
    )
    assert data["doc"]["stats"]["revenue"] == "$26,869 million sales and other revenues, FY2025"


def test_a_ticker_stored_the_old_way_is_still_printed_the_one_way():
    import brief_compat
    company = {**SAMPLE_DOC["company"], "legal_name": "Advance Auto Parts, Inc.", "ticker": "AAP (NYSE)"}
    assert brief_compat.entity_text(make_doc(company=company)) == "Advance Auto Parts, Inc. (NYSE: AAP)"
    unlisted = {**company, "ticker": "also listed in Hong Kong since July"}
    assert brief_compat.entity_text(make_doc(company=unlisted)) == "Advance Auto Parts, Inc."


def test_a_stat_that_was_not_found_is_left_out_of_the_stats_line():
    stats = {**SAMPLE_DOC["stats"], "revenue": "", "employees": " "}
    line = _detail(stats=stats)["statsLine"]
    assert "Revenue" not in line and "Employees" not in line and "| |" not in line


def _snapshot(**lines):
    snapshot = make_doc()["snapshot"]
    for key, text in lines.items():
        snapshot[key] = {"text": text, "sources": [1] if text else []}
    return snapshot


def test_the_six_snapshot_lines_reach_the_four_cells_as_sentences():
    infra = _detail(snapshot=_snapshot(data_centers="Two leased data centers in Dallas"))["infra"]
    assert infra == {
        "cloudPlatforms": "Azure is the primary cloud.",
        "onPrem": "Two leased data centers in Dallas. Plant networks at five refineries.",
        "deployment": "ExpressRoute into a Virtual WAN hub-and-spoke.",
        "complexity": "SD-WAN at refineries and terminals. Palo Alto or Fortinet.",
    }


def test_a_line_that_was_not_found_is_left_out_of_a_cell_that_has_something_to_say():
    infra = _detail(snapshot=_snapshot(wan=""))["infra"]
    assert infra["onPrem"] == "Plant networks at five refineries."  # the sample has no data-center line
    assert infra["complexity"] == "Palo Alto or Fortinet."
    assert "Not found" not in " ".join([infra["onPrem"], infra["complexity"]])


def test_a_cell_with_nothing_found_says_so_once():
    infra = _detail(snapshot=_snapshot(wan="", firewalls="", clouds=""))["infra"]
    assert infra["complexity"] == "Not found in public sources."
    assert infra["cloudPlatforms"] == "Not found in public sources."
    assert _detail(snapshot=_snapshot(wan="", firewalls=""), language="es")["infra"]["complexity"] == (
        "No se encontró en fuentes públicas."
    )


def test_when_nothing_at_all_was_found_the_cells_are_empty_and_the_page_closes_the_block():
    empty = _snapshot(clouds="", cloud_connectivity="", wan="", firewalls="", data_centers="", plant_networks="")
    assert set(_detail(snapshot=empty)["infra"].values()) == {""}


def test_no_citation_marker_reaches_the_infrastructure_cells():
    assert "[" not in " ".join(_detail()["infra"].values())


def _three_line_angle():
    """An angle as research writes it: a dated trigger and what supports it."""
    angle = make_doc()["angles"][0]
    angle["evidence"] = [
        {"text": "A posting lists a Virtual WAN hub-and-spoke", "date": "", "sources": [1]},
        {"text": "The same posting asks for ExpressRoute and BGP.", "date": "2026-09-23", "sources": [1]},
        {"text": "The annual report describes a cloud migration.", "date": "2026-02", "sources": [2, 1]},
    ]
    return angle


def test_signals_and_timing_carries_one_dated_fact_per_angle_with_the_date_in_words():
    data = _detail(angles=[_three_line_angle(), make_doc()["angles"][1]])
    assert data["signals"] == [
        "The same posting asks for ExpressRoute and BGP (source dated 23 Sep 2026).",
        "The annual report describes separating the lubricants business into a standalone company (source dated 20 Feb 2026).",
    ]


def test_the_entry_point_signal_holds_the_rest_of_the_evidence_and_never_repeats_the_dated_fact():
    point = _detail(angles=[_three_line_angle()])["entryPoints"][0]
    assert point["heading"] == "Hand-built Azure network"
    assert point["signal"] == (
        "A posting lists a Virtual WAN hub-and-spoke. The annual report describes a cloud migration (source dated Feb 2026)."
    )
    assert point["solution"].startswith("Alkira replaces hand-built hubs")
    assert point["proof"].startswith("Koch Industries: Significant reduction")


def test_an_angle_with_a_single_fact_repeats_it_as_its_signal_so_the_card_keeps_its_rows():
    """The page drops the row labels from a card with one row. A repeated fact is better than that."""
    data = _detail()
    fact = "A network engineer posting lists ExpressRoute and a Virtual WAN hub-and-spoke (source dated 23 Sep 2026)."
    assert data["signals"][0] == fact and data["entryPoints"][0]["signal"] == fact


def test_every_entry_point_has_a_signal_a_solution_and_a_proof():
    angles = make_doc()["angles"]
    angles[1]["story"] = {"id": "none", "customer": "", "result": ""}
    for language in ("en", "es"):
        for point in _detail(angles=angles, language=language)["entryPoints"]:
            assert point["signal"] and point["solution"] and point["proof"]


def test_no_citation_marker_or_undated_marker_reaches_the_page_text():
    data = _detail(angles=[_three_line_angle()])
    shown = " ".join([*data["signals"], *[p["signal"] for p in data["entryPoints"]]])
    assert "[1]" not in shown and "[2]" not in shown and "undated" not in shown


@pytest.mark.parametrize("text", [
    "On September 23, 2026 the company posted a role asking for ExpressRoute.",
    "It completed the acquisition for $38 million in the first quarter of 2026.",
    "The FY2025 filing describes a cloud migration.",
    "The deal closed in Q3.",
    "Sites will close in the second half of next year.",
    "The role was posted in March.",
], ids=["full-date", "quarter", "fiscal-year", "q3", "half", "month"])
def test_a_line_that_states_its_own_date_or_period_is_not_given_its_source_s_date(text):
    """ "first quarter of 2026 (Dec 31, 2025)" reads as a contradiction. The line's own period stands."""
    angle = _three_line_angle()
    angle["evidence"][1]["text"] = text
    assert _detail(angles=[angle])["signals"] == [text]


def test_dates_are_written_the_spanish_way_in_a_spanish_brief():
    data = _detail(angles=[_three_line_angle()], language="es")
    assert data["signals"] == ["The same posting asks for ExpressRoute and BGP (fuente con fecha 23 sep 2026)."]
    assert data["entryPoints"][0]["signal"].endswith("(fuente con fecha feb 2026).")


def test_starters_hold_people_the_first_question_pointer_and_the_questions():
    lines = _detail()["startersMd"].splitlines()
    assert lines[0] == "**Stakeholders:** Director of Network Engineering\u00a0· Chief Information Officer (Dana Ruiz)"
    assert lines[1] == "**Best First Question:** Lead with question 1."
    assert '1. "Who builds a new Virtual WAN hub today, and how long does one take?"' in lines
    assert "Open with the Azure hub build" not in "\n".join(lines)  # the lead is in the score rationale, once


def test_what_to_listen_for_and_the_alkira_angle_are_separate_sentences():
    """The page joins a question's notes with a space, so each has to end in a full stop."""
    lines = _detail()["startersMd"].splitlines()
    at = lines.index('1. "Who builds a new Virtual WAN hub today, and how long does one take?"')
    assert lines[at + 1 : at + 3] == [
        "   *(Listen for: hand-built hubs, weeks of lead time.)*",
        "   *(Alkira angle: A new region is a design change deployed in a day.)*",
    ]


def test_a_role_with_a_comma_in_it_cannot_be_mistaken_for_two_people():
    people = [
        {"name": "", "role": "EVP, Chief Digital and Technology Officer", "note": "", "sources": []},
        {"name": "", "role": "Head of network engineering", "note": "", "sources": []},
    ]
    first = _detail(people=people)["startersMd"].splitlines()[0]
    assert first == "**Stakeholders:** EVP, Chief Digital and Technology Officer\u00a0· Head of network engineering"
    assert " ·" not in first  # the dot never starts a line: the space before it does not break


def test_what_could_not_be_confirmed_becomes_the_validate_early_bullets():
    unconfirmed = ["Who owns the WAN contract.", "Whether a second cloud is in use", "The MPLS term.", "A fourth thing."]
    text = _detail(unconfirmed=unconfirmed)["startersMd"]
    assert text.endswith(
        "**Validate early:**\n- Who owns the WAN contract.\n- Whether a second cloud is in use.\n- The MPLS term."
    )
    assert "couldn't confirm" not in text and "A fourth thing" not in text


def test_what_would_raise_the_score_stays_out_of_the_page_and_in_the_document():
    data = _detail()
    assert "raise the score" not in data["startersMd"] and "A dated SD-WAN or MPLS renewal" not in data["startersMd"]
    assert data["doc"]["raiseScore"] == ["A dated SD-WAN or MPLS renewal."]


def test_a_brief_with_nothing_unconfirmed_has_no_validate_early_heading():
    assert "Validate early" not in _detail(unconfirmed=[])["startersMd"]


def test_references_are_one_per_line_with_their_urls():
    assert _detail()["referencesMd"].splitlines() == [
        "[1] Senior Network Engineer posting — https://careers.northwind.example/job/123",
        "[2] Annual report — https://www.northwind.example/annual-report.pdf",
    ]


def test_a_reference_that_is_not_first_hand_says_so():
    references = make_doc()["references"]
    references[0]["source_type"] = "last_resort"
    references[1]["source_type"] = "second_hand"
    lines = _detail(references=references)["referencesMd"].splitlines()
    assert "posting (last-resort source) — https://" in lines[0]
    assert "Annual report (second-hand) — https://" in lines[1]


def test_an_evidence_line_with_no_date_still_says_so_in_the_text_and_pdf_renderings():
    import brief_compat
    line = {"text": "A posting lists ExpressRoute.", "date": "", "sources": [1]}
    assert brief_compat.evidence_text(line, i18n.LABELS["en"]) == "A posting lists ExpressRoute. (source undated) [1]"


def test_a_line_resting_on_an_open_posting_says_so_and_when_it_was_seen():
    import brief_compat
    import brief_text
    doc = make_doc()
    doc["references"][0].update(date="2026-10-05", open_posting=True)
    doc["angles"][0]["evidence"][0]["date"] = "2026-10-05"
    data = brief_view.to_detail(_row(brief_doc.dump(doc)))
    expected = "A network engineer posting lists ExpressRoute and a Virtual WAN hub-and-spoke (open posting, seen 5 Oct 2026)."
    assert data["signals"][0] == expected
    assert "(open posting, seen 5 Oct 2026) [1]" in brief_text.render(doc)
    spanish = brief_view.to_detail(_row(brief_doc.dump({**doc, "language": "es"})))
    assert "(vacante abierta, vista el 5 oct 2026)" in spanish["signals"][0]


def test_the_text_and_pdf_renderings_date_a_line_the_same_way_the_page_does():
    import brief_compat
    en = i18n.LABELS["en"]
    plain = {"text": "A posting lists ExpressRoute.", "date": "2025-12-31", "sources": [3]}
    own = {"text": "It closed the deal in the first quarter of 2026.", "date": "2025-12-31", "sources": [3]}
    assert brief_compat.evidence_text(plain, en) == "A posting lists ExpressRoute. (source dated 31 Dec 2025) [3]"
    assert brief_compat.evidence_text(own, en) == "It closed the deal in the first quarter of 2026. [3]"
    assert brief_compat.evidence_text(plain, i18n.LABELS["es"], "es") == (
        "A posting lists ExpressRoute. (fuente con fecha 31 dic 2025) [3]"
    )


# ── Briefs with fewer angles are not padded ──────────────────────

def test_a_one_angle_brief_has_one_entry_point():
    data = _detail(angles=_one_angle())
    assert len(data["entryPoints"]) == 1 and len(data["signals"]) == 1


def test_a_brief_with_no_angles_has_no_entry_points_and_still_renders():
    fit = {"score": 2, "verdict": "A plausible Azure use case with no evidence found.", "lead": ""}
    data = _detail(angles=[], fit=fit, people=[], questions=[], unconfirmed=[], raise_score=[])
    assert data["entryPoints"] == [] and data["signals"] == []
    assert data["scoreRationale"] == "A plausible Azure use case with no evidence found."
    assert data["startersMd"] == ""


def test_an_angle_stored_with_no_story_shows_the_headline_metric_for_its_use_case():
    angles = _one_angle()
    angles[0]["story"] = {"id": "none", "customer": "", "result": ""}
    assert _detail(angles=angles)["entryPoints"][0]["proof"] == "Cloud connection time reduction: 96%."


def test_a_proof_point_is_shown_without_a_customer_and_labelled_as_one_in_the_text():
    import brief_text
    angles = _one_angle()
    angles[0]["story"] = {"id": "metric", "customer": "", "result": "Cloud connection time reduction: 96%."}
    assert _detail(angles=angles)["entryPoints"][0]["proof"] == "Cloud connection time reduction: 96%."
    text = brief_text.render(make_doc(angles=angles))
    assert "Proof point: Cloud connection time reduction: 96%." in text and "Customer story" not in text


# ── The new fields, alongside ────────────────────────────────────

def test_the_whole_document_is_returned_in_camel_case():
    data = _detail()
    assert data["format"] == 2
    doc = data["doc"]
    assert doc["company"]["legalName"] == "Northwind Energy Corporation"
    assert doc["angles"][0]["useCase"] == "multi_cloud"  # values are never rewritten
    assert doc["snapshot"]["cloudConnectivity"]["sources"] == [1]
    assert doc["questions"][0]["listenFor"] == "hand-built hubs, weeks of lead time"
    assert doc["raiseScore"] == ["A dated SD-WAN or MPLS renewal."]
    assert doc["references"][0]["sourceType"] == "first_hand"
    assert doc["research"]["stoppedBy"] == "finished"


def test_a_spanish_json_brief_gets_spanish_labels_inside_its_text():
    data = _detail(language="es")
    assert data["language"] == "es" and data["labels"] is i18n.LABELS["es"]
    assert data["statsLine"].startswith("Sede: Dallas, TX | Ingresos: ")
    assert data["infra"]["onPrem"] == "Plant networks at five refineries."
    assert "**Interlocutores:**" in data["startersMd"] and "**Validar primero:**" in data["startersMd"]
    assert "*(Qué escuchar: hand-built hubs, weeks of lead time.)*" in data["startersMd"]


def test_the_summary_reads_the_verdict_and_the_language_from_the_document():
    summary = brief_view.to_summary(_row(stored(language="es")))
    assert set(summary) == {"id", "company", "score", "snippet", "language", "createdAt"}
    assert summary["snippet"] == SAMPLE_DOC["fit"]["verdict"]
    assert summary["language"] == "es"


def test_a_long_verdict_is_cut_at_a_word_for_the_list():
    fit = {"score": 4, "verdict": "word " * 60, "lead": "Call the CIO."}
    snippet = brief_view.to_summary(_row(stored(fit=fit)))["snippet"]
    assert snippet.endswith("word...") and len(snippet) <= 123


# ── Legacy and damaged rows ──────────────────────────────────────

def test_a_legacy_brief_is_marked_as_format_one_with_no_document():
    repo = FakeRepo()
    row = repo.seed("partner@example.com")
    data = make_client(repo).get(f"/api/brief/briefs/{row['id']}", headers=AUTH).json()["data"]
    assert data["format"] == 1 and data["doc"] is None
    assert data["entryPoints"][0]["proof"] == "96% faster connection time."


def test_a_damaged_json_brief_returns_empty_fields_and_never_a_500():
    repo = FakeRepo()
    row = repo.seed("partner@example.com", company="Typed Name", brief_md=SAMPLE_JSON_BRIEF[:300], score=0)
    client = make_client(repo)
    resp = client.get(f"/api/brief/briefs/{row['id']}", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["company"] == "Typed Name" and data["score"] == 0
    assert data["entryPoints"] == [] and data["doc"] is None
    assert client.get("/api/brief/briefs", headers=AUTH).status_code == 200


def test_a_json_brief_is_served_through_the_api():
    repo = FakeRepo()
    row = repo.seed("partner@example.com", company="Northwind Energy", brief_md=SAMPLE_JSON_BRIEF, score=5)
    client = make_client(repo)
    data = client.get(f"/api/brief/briefs/{row['id']}", headers=AUTH).json()["data"]
    assert data["doc"]["fit"]["score"] == 5
    listed = client.get("/api/brief/briefs", headers=AUTH).json()["data"]
    assert listed[0]["snippet"].startswith("Strong fit")
