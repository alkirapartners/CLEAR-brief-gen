"""PDF for briefs stored as a JSON document: the designed layout, read back from the file."""

import copy
import json
from datetime import datetime

import pytest

import brief_doc
import docx_doc
import export_content
import i18n
import pdf
import pdf_doc
from tests import export_readers as readers
from tests.api_fakes import AUTH, FakeRepo, make_client
from tests.brief_fixtures import SAMPLE_DOC, SAMPLE_JSON_BRIEF, make_doc, stored

WHEN = datetime(2026, 10, 5, 12, 0)
EN = i18n.LABELS["en"]
LETTER_POINTS = (612.0, 792.0)


def _render(doc, language=None):
    return pdf_doc.render(doc, WHEN, language)


def _text(doc, language=None):
    return readers.pdf_text(_render(doc, language))


def _three_angles():
    third = {
        **copy.deepcopy(SAMPLE_DOC["angles"][0]),
        "title": "Firewalls copied per hub",
        "use_case": "firewall_consolidation",
        "story": {"id": "metric", "customer": "", "result": "Firewall reduction: 73% (up to 82% in some accounts)."},
    }
    return make_doc(angles=[*copy.deepcopy(SAMPLE_DOC["angles"]), third])


def test_every_part_of_the_brief_is_in_the_pdf():
    text = _text(make_doc())
    for expected in (
        "Northwind Energy", "Northwind Energy Corporation", "Public (NYSE: NWE)", "northwind.example",
        "Which company: Researched Northwind Energy Corporation",
        "HQ Dallas, TX", "Revenue $28B", "Employees 5,200", "Industry Refining",
        "ALKIRA FIT", "5 / 5", "Strong fit", "Strong fit: a hand-built Azure network",
        "LEAD WITH", "Open with the Azure hub build", "CLOUD AND NETWORK", "Azure, ExpressRoute and Virtual WAN, SD-WAN",
        "Why this account, why now", "Hand-built Azure network", "Lubricants separation",
        "Multi-cloud", "M&A", "Pending deal", "announced 20 Feb 2026",
        "The separation is expected to be completed over the next 12-18 months.",
        "WHAT ALKIRA DOES", "Alkira replaces hand-built hubs with one design deployed per region.",
        "CUSTOMER STORY", "Koch Industries", "Significant reduction in network complexity",
        "A software company", "Nemertes study",
        "EVIDENCE", "23 Sep 2026", "A network engineer posting lists ExpressRoute",
        "Ask this", "Who builds a new Virtual WAN hub today, and how long does one take?",
        "LISTEN FOR", "hand-built hubs, weeks of lead time", "ALKIRA ANGLE", "A new region is a design change",
        "TECHNICAL SNAPSHOT", "For the engineer", "CLOUD CONNECTIVITY", "PLANT NETWORKS",
        "ExpressRoute into a Virtual WAN hub-and-spoke.", "Not found in public sources.",
        "Who to talk to", "Dana Ruiz", "Chief Information Officer", "Director of Network Engineering",
        "Named in the annual report.",
        "What we couldn't confirm", "Who owns the WAN contract.",
        "What would raise the score", "A dated SD-WAN or MPLS renewal.",
        "References", "Senior Network Engineer posting", "careers.northwind.example/job/123", "First-hand",
        "21 searches, 17 pages opened, 203 seconds of research",
    ):
        assert expected in text, f"missing from the PDF: {expected!r}"


def test_the_sections_come_in_the_order_of_the_page():
    doc = make_doc()
    text = _text(doc)
    headings = [section.heading for section in export_content.outline(doc, EN)]
    found = [text.casefold().index(heading.casefold()) for heading in headings]
    assert found == sorted(found), dict(zip(headings, found))


def test_the_pdf_is_us_letter_set_in_the_site_fonts():
    out = _render(make_doc())
    assert readers.pdf_page_size(out) == LETTER_POINTS
    fonts = readers.pdf_fonts_used(out)
    assert any("Inter" in name for name in fonts) and any("JetBrainsMono" in name for name in fonts)
    assert not any("Helvetica" in name for name in fonts)


def test_the_pdf_names_its_brief_and_its_author():
    metadata = readers.pdf_metadata(_render(make_doc()))
    assert metadata["/Title"] == "Northwind Energy: Alkira opportunity brief"
    assert metadata["/Author"] == "Alkira"


def test_every_page_carries_the_confidentiality_mark_the_page_count_and_the_date():
    doc = make_doc()
    doc["unconfirmed"] = ["Whether the WAN contract renews. " * 12] * 40
    pages = readers.pdf_pages(_render(doc))
    assert len(pages) >= 3
    for number, page in enumerate(pages, start=1):
        assert "CONFIDENTIAL" in page
        assert f"Page {number} of {len(pages)}" in page
        assert "Generated 5 Oct 2026" in page
    assert "Northwind Energy · CONFIDENTIAL" in pages[1]  # later pages say whose brief it is


def test_a_one_angle_brief_prints_one_angle():
    text = _text(make_doc(angles=make_doc()["angles"][:1]))
    assert "Hand-built Azure network" in text and "Lubricants separation" not in text


def test_a_three_angle_brief_prints_all_three_and_tells_a_figure_from_a_customer():
    text = _text(_three_angles())
    for title in ("Hand-built Azure network", "Lubricants separation", "Firewalls copied per hub"):
        assert title in text
    assert "PROOF POINT" in text and "73%" in text and "Firewall reduction" in text
    assert "No customer story matched this angle." in text


def test_an_open_posting_is_dated_by_the_day_it_was_seen_and_says_so_once():
    doc = make_doc()
    doc["references"][0].update(
        title="Senior Network Engineer posting (open posting, seen 2026-09-23)", open_posting=True,
    )
    doc["angles"][0]["evidence"][0]["sources"] = [1, 2]
    text = _text(doc)
    assert text.count("Open posting, seen 23 Sep 2026") == 2  # on the evidence line and on the reference
    assert "(open posting, seen 2026-09-23)" not in text


def test_a_proof_plate_is_as_tall_as_what_it_holds_however_long_the_angle_beside_it():
    doc = make_doc(angles=make_doc()["angles"][:1])
    doc["angles"][0]["alkira"] = "Alkira replaces hand-built hubs with one design deployed per region. " * 8
    heights = readers.pdf_heights(_render(doc))
    label, customer = heights["CUSTOMER STORY"], heights["Koch Industries"]
    # The customer's name follows its label directly: no empty plate between them.
    assert 0 < label - customer < 30, label - customer


def test_a_brief_with_no_angles_leaves_the_section_out():
    fit = {"score": 1, "verdict": "No use case found.", "lead": ""}
    text = _text(make_doc(angles=[], fit=fit, people=[], questions=[], unconfirmed=[], raise_score=[], references=[]))
    assert "1 / 5" in text and "Weak fit" in text and "No use case found." in text
    for absent in ("Why this account", "Who to talk to", "Ask this", "References", "LEAD WITH", "What would raise"):
        assert absent not in text
    assert "TECHNICAL SNAPSHOT" in text  # always printed, found or not


def test_a_brief_with_its_optional_fields_empty_still_renders():
    doc = make_doc(
        company={"name": "", "legal_name": "", "ticker": "", "website": "", "identity_note": ""},
        stats={key: "" for key in SAMPLE_DOC["stats"]},
        snapshot={key: {"text": "", "sources": []} for key in SAMPLE_DOC["snapshot"]},
        people=[{"name": "", "role": "", "note": "", "sources": []}],
    )
    doc["angles"][0].update(title="", alkira="", evidence=[], story={"id": "", "customer": "", "result": ""})
    doc["questions"][0].update(listen_for="", alkira_angle="", angle=0)
    doc["references"][0].update(title="", url="", date="")
    text = _text(doc)
    assert "Alkira opportunity brief" in text  # stands in for the missing company name
    assert text.count("Not found in public sources.") == 6
    assert "Source undated" in text


def test_a_document_stored_by_older_code_renders():
    old = make_doc()
    del old["version"]
    for angle in old["angles"]:
        for key in ("deal_date", "deal_status", "deal_pending_quote"):
            del angle[key]
    for question in old["questions"]:
        del question["angle"]
    for reference in old["references"]:
        del reference["source_type"], reference["open_posting"]
    doc = brief_doc.load(json.dumps(old))
    assert doc is not None
    text = _text(doc)
    assert "Lubricants separation" in text and "Pending deal" not in text and "Second-hand" in text


def test_a_spanish_brief_prints_spanish_labels_with_their_accents():
    doc = make_doc(language="es")
    doc["questions"][0]["question"] = "¿Quién construye hoy un hub de Virtual WAN, y cuánto tarda?"
    text = _text(doc)
    for expected in (
        "AJUSTE ALKIRA", "Ajuste fuerte", "EMPIECE CON", "Por qué esta cuenta, por qué ahora", "QUÉ HACE ALKIRA",
        "Operación pendiente", "anunciada el 20 feb 2026", "Pregunte esto", "QUÉ ESCUCHAR", "ÁNGULO ALKIRA",
        "PANORAMA TÉCNICO", "Para el ingeniero", "No se encontró en fuentes públicas.", "Con quién hablar",
        "Lo que no pudimos confirmar", "Qué subiría la puntuación", "Referencias", "Fuente directa",
        "¿Quién construye hoy un hub de Virtual WAN, y cuánto tarda?",
        "CONFIDENCIAL", "Página 1 de", "Generado el 5 oct 2026",
    ):
        assert expected in text, f"missing from the Spanish PDF: {expected!r}"
    assert "TECHNICAL SNAPSHOT" not in text and "Ask this" not in text


def test_the_language_asked_for_wins_over_the_language_of_the_document():
    assert "Pregunte esto" in _text(make_doc(), "es")


def test_typographic_punctuation_is_printed_as_written():
    company = {**SAMPLE_DOC["company"], "identity_note": "“Northwind” — not Northwind Traders… £5 × 3"}
    assert "“Northwind” — not Northwind Traders… £5 × 3" in _text(make_doc(company=company))


def test_text_the_fonts_cannot_set_never_stops_the_pdf():
    company = {**SAMPLE_DOC["company"], "name": "Anker Innovations 安克创新", "identity_note": "Known as Anker 🚀"}
    people = [
        {"name": "Gong Yin (龚银)", "role": "CIO (首席信息官)", "note": "Quoted in the case study → see [1]", "sources": [1]},
        {"name": "张三", "role": "网络总监", "note": "", "sources": []},
    ]
    doc = make_doc(company=company, people=people)
    doc["stats"]["hq"] = "深圳"
    doc["snapshot"]["wan"]["text"] = "SD-WAN 覆盖 300 sites"
    doc["angles"][0]["story"]["result"] = "安克 cut firewalls from 120 to 12."
    text = _text(doc)
    assert "Anker Innovations Northwind" in text  # the name, then the legal entity: nothing stands where 安克创新 was
    assert "Gong Yin CIO Quoted in the case study -> see [1]" in text
    assert "Known as Anker" in text and "SD-WAN 300 sites" in text and "cut firewalls from 120 to 12." in text
    # The mark stands only where nothing of a value was left: the second person's name and role, and the city.
    assert text.count("[…]") == 3 and "HQ […]" in text
    for left_behind in ("()", "( )", "([…])", "Yin ["):
        assert left_behind not in text, left_behind


def test_the_word_export_keeps_every_character_the_pdf_has_to_leave_out():
    people = [{"name": "Gong Yin (龚银)", "role": "CIO (首席信息官)", "note": "", "sources": []}]
    doc = make_doc(people=people)
    assert "Gong Yin (龚银), CIO (首席信息官)" in readers.docx_text(docx_doc.render(doc, WHEN))
    assert "[…]" not in readers.docx_text(docx_doc.render(doc, WHEN))


def test_very_long_text_and_urls_flow_onto_more_pages_and_lose_nothing():
    doc = make_doc()
    doc["unconfirmed"] = [f"Item {number}: whether the WAN contract renews. " * 6 for number in range(40)]
    doc["references"][0]["url"] = "https://example.com/" + "a" * 400
    doc["angles"][0]["title"] = "Unbroken" + "x" * 300
    out = _render(doc)
    pages = readers.pdf_pages(out)
    text = " ".join(pages)
    assert len(pages) >= 3
    for number in range(40):
        assert f"Item {number}:" in text


def test_reference_addresses_are_real_links_and_source_markers_jump_to_them():
    out = _render(make_doc())
    links = readers.pdf_web_links(out)
    assert "https://careers.northwind.example/job/123" in links
    assert "https://www.northwind.example/annual-report.pdf" in links
    assert "https://www.northwind.example" in links  # the company's own site
    assert readers.pdf_jumps(out) >= 8  # every source marker in the angles, the sheet and the people


@pytest.mark.parametrize("address", [
    "javascript:alert(document.domain)", "file:///etc/passwd", "ftp://example.com/x", "//example.com/x",
    "http://127.0.0.1/admin", "https://internal.corp/wiki", "mailto:someone@example.com", "#top",
])
def test_an_address_that_is_not_a_public_web_page_is_never_a_link(address):
    doc = make_doc()
    doc["references"][0]["url"] = address
    doc["company"]["website"] = address
    out = _render(doc)
    links = readers.pdf_web_links(out)
    assert links == ["https://www.northwind.example/annual-report.pdf"]
    assert address in readers.pdf_text(out)  # still shown, as plain text


def _page_of(pages, needle):
    found = [number for number, page in enumerate(pages) if needle in page]
    assert found, f"not in the PDF: {needle!r}"
    return found


def test_a_list_cut_over_pages_puts_each_line_in_the_file_once():
    doc = make_doc()
    doc["unconfirmed"] = [f"Unconfirmed item number {number}." for number in range(70)]
    doc["references"] = [
        {**doc["references"][0], "n": number, "title": f"Reference title number {number}."} for number in range(1, 61)
    ]
    pages = readers.pdf_pages(_render(doc))
    text = " ".join(pages)
    assert len(pages) >= 4
    for number in range(70):
        assert text.count(f"Unconfirmed item number {number}.") == 1
    for number in range(1, 61):
        assert text.count(f"Reference title number {number}.") == 1


def test_a_long_company_name_never_pushes_the_confidentiality_mark_off_the_header():
    doc = make_doc()
    doc["company"]["name"] = "Northwind Energy Holdings International " * 4
    doc["unconfirmed"] = [f"Item {number}." for number in range(80)]
    pages = readers.pdf_pages(_render(doc))
    assert len(pages) >= 2
    assert all("CONFIDENTIAL" in page for page in pages)
    assert "Northwind Energy Holdings International" in pages[1].split("CONFIDENTIAL")[0]


def test_an_address_with_accents_is_linked_in_plain_ascii_and_shown_as_written():
    doc = make_doc()
    doc["references"][0]["url"] = "https://es.wikipedia.example/wiki/México"
    out = _render(doc)
    assert "https://es.wikipedia.example/wiki/M%C3%A9xico" in readers.pdf_web_links(out)
    assert "es.wikipedia.example/wiki/México" in readers.pdf_text(out)


def test_a_question_is_never_split_across_pages():
    doc = make_doc()
    doc["questions"] = [
        {
            "question": f"Question {number} start. " + "How is the network run today? " * 6 + f"Question {number} end.",
            "listen_for": f"Listen {number} start. " + "Manual changes and long lead times. " * 5 + f"Listen {number} end.",
            "alkira_angle": f"Angle {number} start. " + "One fabric with one policy model. " * 5 + f"Angle {number} end.",
            "angle": 1,
        }
        for number in range(12)
    ]
    pages = readers.pdf_pages(_render(doc))
    assert len(pages) >= 3
    for number in range(12):
        marks = [f"Question {number} start.", f"Question {number} end.", f"Listen {number} start.",
                 f"Angle {number} start.", f"Angle {number} end."]
        assert len({tuple(_page_of(pages, mark)) for mark in marks}) == 1, f"question {number} is split"


def test_an_angle_that_fits_on_a_page_is_never_split_and_keeps_its_proof():
    doc = _three_angles()
    for number, angle in enumerate(doc["angles"]):
        angle["title"] = f"Angle {number} title"
        angle["alkira"] = f"Answer {number}. " + "Alkira runs it as one fabric. " * 12
        angle["evidence"] = [
            {"text": f"Fact {number}.{row}. " + "The posting lists the hub design. " * 6, "date": "2026-09-23", "sources": [1]}
            for row in range(4)
        ]
    pages = readers.pdf_pages(_render(doc))
    for number in range(3):
        marks = [f"Angle {number} title", f"Answer {number}.", f"Fact {number}.0.", f"Fact {number}.3."]
        assert len({tuple(_page_of(pages, mark)) for mark in marks}) == 1, f"angle {number} is split"


def test_an_angle_longer_than_a_page_breaks_between_its_evidence_lines():
    doc = make_doc(angles=make_doc()["angles"][:1])
    doc["angles"][0]["evidence"] = [
        {"text": f"Fact {row} start. " + "The posting lists the hub design in detail. " * 9 + f"Fact {row} end.",
         "date": "2026-09-23", "sources": [1]}
        for row in range(30)
    ]
    pages = readers.pdf_pages(_render(doc))
    assert len(pages) >= 3
    for row in range(30):
        assert _page_of(pages, f"Fact {row} start.") == _page_of(pages, f"Fact {row} end."), f"fact {row} is split"


def test_a_heading_is_never_left_at_the_foot_of_a_page():
    for filler in range(0, 40, 3):
        doc = make_doc()
        doc["unconfirmed"] = [f"Filler {number}." for number in range(filler)]
        pages = readers.pdf_pages(_render(doc))
        for heading, first in (
            ("Why this account, why now", "Hand-built Azure network"),
            ("Ask this", "Who builds a new Virtual WAN hub today"),
            ("Who to talk to", "Owns the Azure network."),
            ("References", "Senior Network Engineer posting"),
            ("What would raise the score", "A dated SD-WAN or MPLS renewal."),
        ):
            assert _page_of(pages, heading)[0] == _page_of(pages, first)[0], f"{heading!r} orphaned at {filler}"


def _with_references(count, filler):
    doc = make_doc()
    doc["unconfirmed"] = [f"Filler {number}." for number in range(filler)]
    doc["references"] = [
        {**doc["references"][0], "n": number, "title": f"Source title {number:02d}.",
         "url": f"https://careers.northwind.example/job/{number:02d}"}
        for number in range(1, count + 1)
    ]
    return doc


def test_references_flow_over_a_page_break_between_rows_and_never_inside_one():
    flowed = 0
    for filler in range(0, 48, 2):
        pages = readers.pdf_pages(_render(_with_references(8, filler)))
        heading = next(number for number, page in enumerate(pages) if "References" in page)
        rows = [_page_of(pages, f"Source title {number:02d}.") for number in range(1, 9)]
        addresses = [_page_of(pages, f"careers.northwind.example/job/{number:02d}") for number in range(1, 9)]
        assert rows == addresses, f"a reference is split at {filler}"
        assert rows[0] == rows[1] == [heading], f"the heading lost its first two rows at {filler}"
        assert [page for row in rows for page in row] == sorted(page for row in rows for page in row)
        flowed += len({tuple(row) for row in rows}) > 1
    assert flowed, "the list never ran over a page: it is still moved whole"


def test_a_list_of_two_references_is_kept_with_its_heading():
    for filler in range(0, 48, 2):
        pages = readers.pdf_pages(_render(_with_references(2, filler)))
        heading = next(number for number, page in enumerate(pages) if "References" in page)
        assert _page_of(pages, "Source title 01.") == _page_of(pages, "Source title 02.") == [heading]


def test_rendering_does_not_change_the_document_it_is_given():
    doc = make_doc()
    before = copy.deepcopy(doc)
    _render(doc)
    assert doc == before


def test_the_public_entry_point_sends_json_briefs_to_this_renderer(monkeypatch):
    seen = []

    def fake_render(doc, when, language):
        seen.append((doc["company"]["name"], when, language))
        return b"%PDF-from-the-document-renderer"

    monkeypatch.setattr(pdf_doc, "render", fake_render)
    out = pdf.generate_brief_pdf(SAMPLE_JSON_BRIEF, "Northwind Energy", 5, WHEN, "es")
    assert out == b"%PDF-from-the-document-renderer"
    assert seen == [("Northwind Energy", WHEN, "es")]


def test_a_damaged_json_brief_still_downloads_as_an_empty_legacy_pdf():
    out = pdf.generate_brief_pdf(SAMPLE_JSON_BRIEF[:300], "Typed Name", 0, WHEN, "en")
    assert out.startswith(b"%PDF-")


def test_the_pdf_route_names_the_file_from_the_document():
    repo = FakeRepo()
    row = repo.seed("partner@example.com", company="Northwind Energy", brief_md=stored(language="es"), score=5)
    resp = make_client(repo).get(f"/api/brief/briefs/{row['id']}/pdf", headers=AUTH)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF-")
    disposition = resp.headers["content-disposition"]
    assert "AlkiraBrief_Northwind-Energy_" in disposition and disposition.endswith('_ES.pdf"')
    assert "Pregunte esto" in readers.pdf_text(resp.content)
