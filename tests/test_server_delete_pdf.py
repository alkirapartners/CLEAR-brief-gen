from datetime import datetime
from uuid import uuid4

from tests.api_fakes import AUTH, OTHER, FakeRepo, make_client


def test_delete_removes_my_brief():
    repo = FakeRepo()
    row = repo.seed("partner@example.com")
    resp = make_client(repo).delete(f"/api/brief/briefs/{row['id']}", headers=AUTH)
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "data": {"deleted": True}, "error": None}
    assert repo.rows == []


def test_delete_of_someone_elses_brief_is_404_and_keeps_it():
    repo = FakeRepo()
    row = repo.seed("partner@example.com")
    resp = make_client(repo).delete(f"/api/brief/briefs/{row['id']}", headers=OTHER)
    assert resp.status_code == 404
    assert len(repo.rows) == 1


def test_delete_requires_auth():
    assert make_client().delete(f"/api/brief/briefs/{uuid4()}").status_code == 401


def test_pdf_downloads_with_the_existing_filename_rule():
    repo = FakeRepo()
    row = repo.seed("partner@example.com")
    resp = make_client(repo).get(f"/api/brief/briefs/{row['id']}/pdf", headers=AUTH)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    period = datetime.now().strftime("%Y-%m")
    assert resp.headers["content-disposition"] == (
        f'attachment; filename="AlkiraBrief_TestCo-Holdings_{period}.pdf"'
    )
    assert resp.content.startswith(b"%PDF")


def test_pdf_of_someone_elses_brief_is_404():
    repo = FakeRepo()
    row = repo.seed("partner@example.com")
    resp = make_client(repo).get(f"/api/brief/briefs/{row['id']}/pdf", headers=OTHER)
    assert resp.status_code == 404


def test_pdf_of_unparseable_brief_still_downloads():
    repo = FakeRepo()
    row = repo.seed("partner@example.com", company="Typed Name",
                    brief_md="The model wandered off.", score=0)
    resp = make_client(repo).get(f"/api/brief/briefs/{row['id']}/pdf", headers=AUTH)
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")
    assert "AlkiraBrief_Typed-Name_" in resp.headers["content-disposition"]
