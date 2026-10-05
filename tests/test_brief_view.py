"""A JSON brief must fill every field the current front end reads."""

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


def test_the_six_snapshot_lines_all_reach_the_four_cells():
    infra = _detail()["infra"]
    assert infra["cloudPlatforms"] == "Azure is the primary cloud. [1]"
    assert infra["deployment"] == "ExpressRoute into a Virtual WAN hub-and-spoke. [1]"
    assert infra["onPrem"] == "Data centers: Not found Plant networks: Plant networks at five refineries. [2]"
    assert infra["complexity"] == "WAN: SD-WAN at refineries and terminals. [1] Firewalls: Palo Alto or Fortinet. [1]"


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
        "The same posting asks for ExpressRoute and BGP (Sep 23, 2026).",
        "The annual report describes separating the lubricants business (Feb 20, 2026).",
    ]


def test_the_entry_point_signal_holds_the_rest_of_the_evidence_and_never_repeats_the_dated_fact():
    point = _detail(angles=[_three_line_angle()])["entryPoints"][0]
    assert point["heading"] == "Hand-built Azure network"
    assert point["signal"] == (
        "A posting lists a Virtual WAN hub-and-spoke. The annual report describes a cloud migration (Feb 2026)."
    )
    assert point["solution"].startswith("Alkira replaces hand-built hubs")
    assert point["proof"].startswith("Koch Industries: Significant reduction")


def test_an_angle_with_a_single_fact_shows_it_once_under_signals_and_timing():
    data = _detail()
    assert data["signals"][0] == "A network engineer posting lists ExpressRoute and a Virtual WAN hub-and-spoke (Sep 23, 2026)."
    assert [point["signal"] for point in data["entryPoints"]] == ["", ""]


def test_no_citation_marker_or_undated_marker_reaches_the_page_text():
    data = _detail(angles=[_three_line_angle()])
    shown = " ".join([*data["signals"], *[p["signal"] for p in data["entryPoints"]]])
    assert "[1]" not in shown and "[2]" not in shown and "undated" not in shown


def test_a_date_the_sentence_already_gives_is_not_said_twice():
    angle = _three_line_angle()
    angle["evidence"][1]["text"] = "On September 23, 2026 the company posted a role asking for ExpressRoute."
    assert _detail(angles=[angle])["signals"] == [
        "On September 23, 2026 the company posted a role asking for ExpressRoute.",
    ]


def test_dates_are_written_the_spanish_way_in_a_spanish_brief():
    data = _detail(angles=[_three_line_angle()], language="es")
    assert data["signals"] == ["The same posting asks for ExpressRoute and BGP (23 sep 2026)."]
    assert data["entryPoints"][0]["signal"].endswith("(feb 2026).")


def test_starters_hold_people_the_lead_questions_and_what_is_unconfirmed():
    text = _detail()["startersMd"]
    assert text.startswith(
        "**Stakeholders:** Director of Network Engineering, Chief Information Officer (Dana Ruiz)"
    )
    assert "**Best First Question:** Lead with question 1." in text
    assert "Open with the Azure hub build" not in text  # the lead is in the score rationale, once
    assert '1. "Who builds a new Virtual WAN hub today, and how long does one take?"' in text
    assert "*(Listen for: hand-built hubs, weeks of lead time Alkira angle: A new region" in text
    assert "**What we couldn't confirm:**\n- Who owns the WAN contract." in text
    assert "**What would raise the score:**\n- A dated SD-WAN or MPLS renewal." in text


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
    assert brief_compat.evidence_text(line, i18n.LABELS["en"]) == "A posting lists ExpressRoute. (undated) [1]"


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


def test_a_story_of_none_leaves_the_proof_empty():
    angles = _one_angle()
    angles[0]["story"] = {"id": "none", "customer": "", "result": ""}
    assert _detail(angles=angles)["entryPoints"][0]["proof"] == ""


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
    assert "Centros de datos: No encontrado" in data["infra"]["onPrem"]
    assert "**Interlocutores:**" in data["startersMd"]


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
