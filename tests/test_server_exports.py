"""The two download routes: the PDF of any brief, and the Word file of a JSON brief."""

import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pdf
from tests import export_readers as readers
from tests.api_fakes import AUTH, OTHER, SAMPLE_BRIEF, FakeRepo, make_client
from tests.brief_fixtures import SAMPLE_JSON_BRIEF, stored

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ZIP_MAGIC = b"PK\x03\x04"
REPO_ROOT = Path(__file__).parent.parent


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


def test_the_word_export_answers_503_when_its_renderer_cannot_be_loaded(monkeypatch, caplog):
    monkeypatch.setitem(sys.modules, "docx_doc", None)  # makes "import docx_doc" fail, as a broken install would
    repo, row = _seed()
    client = make_client(repo)
    with caplog.at_level(logging.ERROR):
        resp = client.get(f"/api/brief/briefs/{row['id']}/docx", headers=AUTH)
    assert resp.status_code == 503
    body = resp.json()
    assert body["success"] is False and body["data"] is None
    assert "Word" in body["error"] and "PDF" in body["error"]
    assert "docx_doc" not in body["error"]  # the detail is for the server's log, not the partner
    assert "docx_doc" in caplog.text
    # Nothing else is touched: the same brief still opens and still downloads as a PDF.
    assert client.get(f"/api/brief/briefs/{row['id']}", headers=AUTH).status_code == 200
    assert client.get(f"/api/brief/briefs/{row['id']}/pdf", headers=AUTH).status_code == 200


def test_a_legacy_brief_is_still_told_it_has_no_word_export_when_the_renderer_is_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "docx_doc", None)
    repo, row = _seed(brief_md=SAMPLE_BRIEF, company="TestCo Holdings")
    assert _docx(repo, row).status_code == 409


# Run in a fresh interpreter in which python-docx and lxml cannot be imported at all.
_WITHOUT_PYTHON_DOCX = """
import sys


class _NotInstalled:
    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in ("docx", "lxml"):
            raise ImportError(f"No module named {name!r}")
        return None


sys.meta_path.insert(0, _NotInstalled())

from tests.api_fakes import AUTH, FakeRepo, make_client
from tests.brief_fixtures import SAMPLE_JSON_BRIEF

repo = FakeRepo()
row = repo.seed("partner@example.com", brief_md=SAMPLE_JSON_BRIEF)
client = make_client(repo)
brief = f"/api/brief/briefs/{row['id']}"
print(
    client.get("/api/brief/health").status_code,
    client.get(brief, headers=AUTH).status_code,
    client.get(brief + "/pdf", headers=AUTH).status_code,
    client.get(brief + "/docx", headers=AUTH).status_code,
    "docx" in sys.modules,
)
"""


def test_the_api_starts_and_serves_briefs_and_pdfs_when_python_docx_cannot_be_imported():
    result = subprocess.run(
        [sys.executable, "-c", _WITHOUT_PYTHON_DOCX], capture_output=True, text=True, cwd=REPO_ROOT, timeout=120,
    )
    assert result.stdout.split() == ["200", "200", "200", "503", "False"], result.stderr[-3000:]
