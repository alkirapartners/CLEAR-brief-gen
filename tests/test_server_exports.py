"""The two download routes: the PDF of any brief, and the Word file of a JSON brief."""

from datetime import datetime
from uuid import uuid4

import pdf
from tests import export_readers as readers
from tests.api_fakes import AUTH, OTHER, SAMPLE_BRIEF, FakeRepo, make_client
from tests.brief_fixtures import SAMPLE_JSON_BRIEF, stored

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ZIP_MAGIC = b"PK\x03\x04"


def _seed(brief_md=SAMPLE_JSON_BRIEF, company="Northwind Energy"):
    repo = FakeRepo()
    row = repo.seed("partner@example.com", company=company, brief_md=brief_md, score=5)
    return repo, row


def _docx(repo, row, headers=AUTH):
    return make_client(repo).get(f"/api/brief/briefs/{row['id']}/docx", headers=headers)


def test_the_word_export_downloads_as_an_attachment_that_is_never_cached():
    repo, row = _seed()
    resp = _docx(repo, row)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == DOCX_TYPE
    assert resp.headers["cache-control"] == "no-store"
    period = datetime.now().strftime("%Y-%m")
    assert resp.headers["content-disposition"] == f'attachment; filename="AlkiraBrief_Northwind-Energy_{period}.docx"'
    assert resp.content.startswith(ZIP_MAGIC)
    assert "Why this account, why now" in readers.docx_text(resp.content)


def test_the_word_file_is_named_the_way_the_pdf_is():
    repo, row = _seed(brief_md=stored(language="es"))
    client = make_client(repo)
    word = client.get(f"/api/brief/briefs/{row['id']}/docx", headers=AUTH).headers["content-disposition"]
    portable = client.get(f"/api/brief/briefs/{row['id']}/pdf", headers=AUTH).headers["content-disposition"]
    assert word.endswith('_ES.docx"')
    assert word.removesuffix('.docx"') == portable.removesuffix('.pdf"')
    assert "Pregunte esto" in readers.docx_text(client.get(f"/api/brief/briefs/{row['id']}/docx", headers=AUTH).content)


def test_the_file_name_never_carries_what_the_model_wrote_unsanitised():
    hostile = stored(company={
        "name": 'Evil"; filename="x.exe\r\nSet-Cookie: a=b', "legal_name": "", "ticker": "", "website": "",
        "identity_note": "",
    })
    repo, row = _seed(brief_md=hostile)
    disposition = _docx(repo, row).headers["content-disposition"]
    period = datetime.now().strftime("%Y-%m")
    assert disposition == f'attachment; filename="AlkiraBrief_Evil-filenamexexe-Set-Cookie-ab_{period}.docx"'


def test_the_word_export_requires_sign_in():
    assert make_client().get(f"/api/brief/briefs/{uuid4()}/docx").status_code == 401


def test_the_word_export_of_a_missing_brief_is_404_in_the_api_envelope():
    resp = make_client().get(f"/api/brief/briefs/{uuid4()}/docx", headers=AUTH)
    assert resp.status_code == 404
    assert resp.json() == {"success": False, "data": None, "error": "Brief not found"}


def test_the_word_export_of_someone_elses_brief_is_404():
    repo, row = _seed()
    assert _docx(repo, row, headers=OTHER).status_code == 404


def test_the_word_export_of_a_bad_id_is_a_validation_error():
    assert make_client().get("/api/brief/briefs/not-a-uuid/docx", headers=AUTH).status_code == 422


def test_a_legacy_markdown_brief_has_no_word_export_and_says_so():
    repo, row = _seed(brief_md=SAMPLE_BRIEF, company="TestCo Holdings")
    resp = _docx(repo, row)
    assert resp.status_code == 409
    body = resp.json()
    assert body["success"] is False and body["data"] is None
    assert "Word" in body["error"] and "PDF" in body["error"]
    assert resp.headers["content-type"].startswith("application/json")


def test_a_damaged_json_brief_has_no_word_export_either():
    repo, row = _seed(brief_md=SAMPLE_JSON_BRIEF[:300])
    assert _docx(repo, row).status_code == 409


def test_the_pdf_route_still_serves_both_stored_formats():
    for brief_md, marker in ((SAMPLE_JSON_BRIEF, "Why this account, why now"), (SAMPLE_BRIEF, "ALKIRA")):
        repo, row = _seed(brief_md=brief_md)
        resp = make_client(repo).get(f"/api/brief/briefs/{row['id']}/pdf", headers=AUTH)
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.headers["cache-control"] == "no-store"
        assert resp.headers["content-disposition"].endswith('.pdf"')
        assert marker in readers.pdf_text(resp.content)


def test_build_filename_takes_another_extension_and_keeps_pdf_as_its_own():
    assert pdf.build_filename("Cemex", "2026-08", "es") == "AlkiraBrief_Cemex_2026-08_ES.pdf"
    assert pdf.build_filename("Cemex", "2026-08", "es", extension="docx") == "AlkiraBrief_Cemex_2026-08_ES.docx"
