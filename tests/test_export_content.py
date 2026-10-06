"""What the PDF and the Word document both say about a brief."""

import export_content
import i18n
import tech_terms
from tests.brief_fixtures import make_doc

EN = i18n.LABELS["en"]
ES = i18n.LABELS["es"]


def _keys(doc, labels=EN):
    return [section.key for section in export_content.outline(doc, labels)]


def test_the_outline_lists_the_sections_in_the_order_of_the_page():
    assert _keys(make_doc()) == [
        "fit", "why_now", "ask_this", "for_engineer", "who_to_talk_to",
        "unconfirmed", "raise_score", "references",
    ]


def test_the_outline_leaves_out_a_section_with_nothing_in_it():
    empty = make_doc(angles=[], questions=[], people=[], unconfirmed=[], raise_score=[], references=[])
    assert _keys(empty) == ["fit", "for_engineer"]


def test_the_outline_headings_follow_the_language():
    headings = [section.heading for section in export_content.outline(make_doc(), ES)]
    assert headings[:4] == ["Ajuste Alkira", "Por qué esta cuenta, por qué ahora", "Pregunte esto", "Para el ingeniero"]


def test_the_fit_label_says_how_strong_a_score_is():
    assert [export_content.fit_label(score, EN) for score in (1, 2, 3, 4, 5)] == [
        "Weak fit", "Weak fit", "Moderate fit", "Strong fit", "Strong fit",
    ]
    assert export_content.fit_label(3, ES) == "Ajuste moderado"


def test_the_lead_splits_into_what_to_open_with_and_whom_to_call():
    first, rest = export_content.split_lead("Open with the Azure hub build. Call the Director of Network Engineering.")
    assert first == "Open with the Azure hub build."
    assert rest == "Call the Director of Network Engineering."
    assert export_content.split_lead("One sentence only") == ("One sentence only", "")
    assert export_content.split_lead("Empiece con Azure. ¿Quién lo opera?") == ("Empiece con Azure.", "¿Quién lo opera?")


def test_a_use_case_is_named_in_the_language_and_an_unknown_one_in_plain_words():
    assert export_content.use_case_name("m_and_a", EN) == "M&A"
    assert export_content.use_case_name("m_and_a", ES) == "Fusiones y adquisiciones"
    assert export_content.use_case_name("edge_compute", EN) == "Edge compute"


def test_a_pending_deal_says_so_with_the_day_it_was_announced():
    angle = make_doc()["angles"][1]
    assert export_content.deal_parts(angle, EN, "en") == ("Pending deal", "announced 20 Feb 2026")
    assert export_content.deal_text(angle, EN, "en") == "Pending deal, announced 20 Feb 2026"
    assert export_content.deal_text(angle, ES, "es") == "Operación pendiente, anunciada el 20 feb 2026"


def test_a_completed_deal_gives_its_date_and_any_other_angle_gives_nothing():
    done = {**make_doc()["angles"][1], "deal_status": "completed", "deal_date": "2026-08"}
    assert export_content.deal_text(done, EN, "en") == "Deal completed, Aug 2026"
    assert export_content.deal_text({**done, "deal_date": ""}, EN, "en") == "Deal completed"
    assert export_content.deal_text(make_doc()["angles"][0], EN, "en") == ""


def test_an_evidence_line_is_dated_by_its_source_by_an_open_posting_or_not_at_all():
    doc = make_doc()
    line = doc["angles"][0]["evidence"][0]
    dated = export_content.evidence_date(line, doc["references"], EN, "en")
    assert (dated.kind, dated.stamp, dated.note) == ("dated", "23 Sep 2026", "source dated 23 Sep 2026")

    posting = [{**doc["references"][0], "open_posting": True}]
    seen = export_content.evidence_date(line, posting, EN, "en")
    assert (seen.kind, seen.stamp) == ("open", "Open posting, seen 23 Sep 2026")
    assert seen.note == "open posting, seen 23 Sep 2026"

    undated = export_content.evidence_date({**line, "date": ""}, doc["references"], EN, "en")
    assert (undated.kind, undated.stamp, undated.note) == ("undated", "Source undated", "source undated")


def test_a_line_that_says_it_is_undated_is_not_labelled_undated_as_well():
    line = {"text": "Anker uses Direct Connect (undated AWS case study).", "date": "", "sources": [1]}
    state = export_content.evidence_date(line, [], EN, "en")
    assert (state.kind, state.stamp, state.note) == ("undated", "", "")


def test_a_reference_says_what_kind_of_source_it_is_and_how_it_is_dated():
    reference = make_doc()["references"][0]
    assert export_content.source_type_label(reference, EN) == "First-hand"
    assert export_content.source_type_label({**reference, "source_type": "second_hand"}, EN) == "Second-hand"
    assert export_content.source_type_label({**reference, "source_type": "last_resort"}, ES) == "Fuente de último recurso"
    assert export_content.reference_date(reference, EN, "en").stamp == "23 Sep 2026"
    assert export_content.reference_date({**reference, "date": ""}, EN, "en").stamp == "Source undated"


def test_an_open_posting_is_said_once_not_in_the_title_as_well():
    reference = {
        **make_doc()["references"][0],
        "title": "Careers: Network Engineer (open posting, seen 2026-10-06)", "open_posting": True, "date": "2026-10-06",
    }
    assert export_content.reference_title(reference, EN) == "Careers: Network Engineer"
    assert export_content.reference_date(reference, EN, "en").stamp == "Open posting, seen 6 Oct 2026"


def test_only_a_public_web_address_is_ever_a_link():
    assert export_content.link_target("https://careers.northwind.example/job/123") == "https://careers.northwind.example/job/123"
    for bad in ("javascript:alert(1)", "file:///etc/passwd", "ftp://example.com/x", "http://127.0.0.1/admin",
                "https://user:pass@", "not a url", "", "https://exa mple.com"):
        assert export_content.link_target(bad) is None, bad


def test_an_address_is_shown_without_its_scheme():
    assert export_content.display_url("https://www.northwind.example/annual-report.pdf") == "northwind.example/annual-report.pdf"
    assert export_content.display_url("https://northwind.example/") == "northwind.example"
    assert export_content.display_url("javascript:alert(1)") == "javascript:alert(1)"


def test_a_named_customer_story_and_a_knowledge_base_figure_are_different_kinds_of_proof():
    story = export_content.proof({"id": "nemertes-4", "customer": "A software company (Nemertes study)",
                                  "result": "Integrated in days."}, EN)
    assert (story.kind, story.label, story.customer, story.qualifier) == (
        "story", "Customer story", "A software company", "Nemertes study",
    )
    assert story.note == ""

    metric = export_content.proof({"id": "metric", "customer": "",
                                   "result": "Network provisioning speed improvement: 80%."}, EN)
    assert (metric.kind, metric.label, metric.figure, metric.name) == (
        "metric", "Proof point", "80%", "Network provisioning speed improvement",
    )
    assert "No customer story matched" in metric.note
    assert export_content.proof({"id": "", "customer": "", "result": ""}, EN) is None


def test_a_result_with_no_customer_is_a_proof_point_without_the_headline_note():
    plain = export_content.proof({"id": "koch", "customer": "", "result": "Fewer firewalls."}, EN)
    assert (plain.kind, plain.figure, plain.result, plain.note) == ("metric", "", "Fewer firewalls.", "")


def test_the_numbers_in_a_result_are_marked_for_emphasis():
    parts = export_content.emphasise_numbers("About 1,400 stores connected in three weeks, a 1650% increase.")
    assert [text for text, strong in parts if strong] == ["1,400", "three weeks", "1650%"]
    assert "".join(text for text, _ in parts) == "About 1,400 stores connected in three weeks, a 1650% increase."


def test_the_identity_line_gives_the_entity_its_listing_and_its_site():
    identity = export_content.identity(make_doc(), EN)
    assert identity.facts == ("Northwind Energy Corporation", "Public (NYSE: NWE)")
    assert (identity.site, identity.site_url) == ("northwind.example", "https://www.northwind.example")
    assert identity.note.startswith("Researched Northwind Energy Corporation")


def test_the_identity_line_does_not_repeat_the_name_or_link_a_bad_address():
    company = {**make_doc()["company"], "legal_name": "northwind energy", "website": "javascript:alert(1)"}
    identity = export_content.identity(make_doc(company=company), EN)
    assert identity.facts == ("Public (NYSE: NWE)",)
    assert (identity.site, identity.site_url) == ("", None)


def test_the_stat_pills_leave_ownership_to_the_identity_line():
    assert export_content.stat_pills_for(make_doc(), EN) == [
        ("HQ", "Dallas, TX"), ("Revenue", "$28B"), ("Employees", "5,200"), ("Industry", "Refining"),
    ]


def test_initials_are_the_first_letters_of_the_first_two_names():
    assert export_content.initials("Dana Ruiz") == "DR"
    assert export_content.initials("gong yin li") == "GY"
    assert export_content.initials("") == ""


def test_the_research_note_counts_the_work_behind_the_brief():
    assert export_content.research_note(make_doc(), EN) == "21 searches, 17 pages opened, 203 seconds of research"


def test_technology_terms_are_found_and_everyday_capitals_are_not():
    tokens = tech_terms.tokenize("ExpressRoute into Azure Virtual WAN for the US CIO, with SSE/SASE and BGP.")
    assert [text for text, is_term in tokens if is_term] == ["ExpressRoute", "Azure Virtual WAN", "SSE/SASE", "BGP"]
    assert "".join(text for text, _ in tokens) == "ExpressRoute into Azure Virtual WAN for the US CIO, with SSE/SASE and BGP."
