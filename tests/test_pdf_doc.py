"""PDF for briefs stored as a JSON document."""

from datetime import datetime

import pytest

import pdf
import pdf_doc
from tests.api_fakes import AUTH, FakeRepo, make_client
from tests.brief_fixtures import SAMPLE_DOC, SAMPLE_JSON_BRIEF, make_doc, stored

WHEN = datetime(2026, 10, 5, 12, 0)


class _PlainPDF(pdf._BriefPDF):
    """Uncompressed, so the page text can be read straight from the bytes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_compression(False)


@pytest.fixture
def page_text(monkeypatch):
    monkeypatch.setattr(pdf_doc, "_BriefPDF", _PlainPDF)

    def render(doc, language=None):
        raw = pdf_doc.render(doc, WHEN, language).decode("latin-1")
        return raw.replace("\\(", "(").replace("\\)", ")")  # PDF strings escape brackets

    return render


def test_every_section_of_the_brief_is_printed(page_text):
    text = page_text(make_doc())
    for expected in (
        "Northwind Energy",
        "Entity: Northwind Energy Corporation (NYSE: NWE)",
        "Which company: Researched Northwind Energy Corporation",
        "ALKIRA FIT", "5 / 5",
        "Lead with: Open with the Azure hub build",
        "WHY THIS ACCOUNT, WHY NOW", "ANGLE 01", "ANGLE 02",
        "What Alkira does: Alkira replaces hand-built hubs",
        "Customer story: Koch Industries: Significant reduction",
        "TECHNICAL SNAPSHOT", "Cloud connectivity", "Plant networks",
        "WHO TO TALK TO", "Chief Information Officer (Dana Ruiz)",
        "QUESTIONS TO ASK", "Listen for: hand-built hubs", "Alkira angle: A new region",
        "WHAT WE COULDN'T CONFIRM", "WHAT WOULD RAISE THE SCORE",
        "REFERENCES", "https://careers.northwind.example/job/123",
    ):
        assert expected in text, f"missing from the PDF: {expected!r}"


def test_a_snapshot_line_with_no_source_prints_not_found(page_text):
    assert "Not found" in page_text(make_doc())


def test_a_one_angle_brief_prints_one_angle(page_text):
    text = page_text(make_doc(angles=make_doc()["angles"][:1]))
    assert "ANGLE 01" in text and "ANGLE 02" not in text


def test_a_brief_with_no_angles_leaves_the_section_out(page_text):
    fit = {"score": 1, "verdict": "No use case found.", "lead": ""}
    text = page_text(make_doc(angles=[], fit=fit, people=[], questions=[], unconfirmed=[], raise_score=[], references=[]))
    assert "1 / 5" in text and "No use case found." in text
    for absent in ("WHY THIS ACCOUNT", "WHO TO TALK TO", "QUESTIONS TO ASK", "REFERENCES", "Lead with"):
        assert absent not in text
    assert "TECHNICAL SNAPSHOT" in text  # always printed, found or not


def test_a_spanish_brief_prints_spanish_labels(page_text):
    text = page_text(make_doc(language="es"))
    for expected in ("AJUSTE ALKIRA", "PANORAMA T\xc9CNICO", "No encontrado", "CON QUI\xc9N HABLAR", "REFERENCIAS"):
        assert expected in text
    assert "TECHNICAL SNAPSHOT" not in text


def test_text_outside_latin_1_never_stops_the_pdf(page_text):
    company = {**SAMPLE_DOC["company"], "name": "Anker Innovations 安克创新", "identity_note": "“Anker” — not Ankercloud…"}
    text = page_text(make_doc(company=company))
    assert "Anker Innovations ????" in text
    assert '"Anker" -- not Ankercloud...' in text


def test_very_long_text_and_urls_flow_onto_more_pages():
    doc = make_doc()
    doc["unconfirmed"] = ["Whether the WAN contract renews. " * 12] * 40
    doc["references"][0]["url"] = "https://example.com/" + "a" * 400
    out = pdf_doc.render(doc, WHEN)
    assert out.startswith(b"%PDF-") and out.count(b"/Type /Page\n") >= 3


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
