from uuid import uuid4

from tests.api_fakes import AUTH, OTHER, FakeRepo, make_client


def test_list_returns_only_my_briefs_newest_first():
    repo = FakeRepo()
    repo.seed("partner@example.com", company="Older", created_at="2026-10-01T00:00:00+00:00")
    repo.seed("partner@example.com", company="Newer", created_at="2026-10-03T00:00:00+00:00")
    repo.seed("someone@else.com", company="Not mine")
    data = make_client(repo).get("/api/brief/briefs", headers=AUTH).json()["data"]
    assert [b["company"] for b in data] == ["Newer", "Older"]
    assert set(data[0]) == {"id", "company", "score", "snippet", "language", "createdAt"}
    assert data[0]["score"] == 4
    assert data[0]["language"] == "en"
    assert data[0]["snippet"].startswith("TestCo runs production across Azure and AWS")
    assert "brief_md" not in data[0]


def test_list_requires_auth():
    assert make_client().get("/api/brief/briefs").status_code == 401


def test_detail_maps_every_section():
    repo = FakeRepo()
    row = repo.seed("partner@example.com")
    data = make_client(repo).get(f"/api/brief/briefs/{row['id']}", headers=AUTH).json()["data"]
    assert data["company"] == "TestCo Holdings"
    assert "Austin, TX" in data["statsLine"] and "**" not in data["statsLine"]
    assert data["score"] == 4
    assert data["scoreRationale"].startswith("TestCo runs production")
    assert data["infra"]["cloudPlatforms"].startswith("Azure (confirmed)")
    assert data["infra"]["complexity"] == "Two clouds plus acquired networks."
    assert data["signals"][0] == "Vendor consolidation initiative announced Q1 2026"
    assert len(data["signals"]) == 4
    assert [p["heading"] for p in data["entryPoints"]] == [
        "Multi-cloud connectivity", "Zero trust segmentation", "M&A integration",
    ]
    assert data["entryPoints"][0]["proof"] == "96% faster connection time."
    assert "Azure-AWS connectivity" in data["startersMd"]
    assert "https://example.com/10k" in data["referencesMd"]
    assert data["language"] == "en"
    assert data["labels"]["alkira_fit"] == "Alkira Fit"
    assert data["createdAt"] == row["created_at"]


def test_detail_of_someone_elses_brief_is_404():
    repo = FakeRepo()
    row = repo.seed("partner@example.com")
    resp = make_client(repo).get(f"/api/brief/briefs/{row['id']}", headers=OTHER)
    assert resp.status_code == 404
    assert resp.json() == {"success": False, "data": None, "error": "Brief not found"}


def test_detail_of_a_missing_brief_is_404():
    resp = make_client().get(f"/api/brief/briefs/{uuid4()}", headers=AUTH)
    assert resp.status_code == 404


def test_detail_with_a_malformed_id_is_422():
    resp = make_client().get("/api/brief/briefs/not-a-uuid", headers=AUTH)
    assert resp.status_code == 422


def test_detail_of_unparseable_brief_returns_empty_fields():
    repo = FakeRepo()
    row = repo.seed("partner@example.com", company="Typed Name", brief_md="The model wandered off.", score=0)
    resp = make_client(repo).get(f"/api/brief/briefs/{row['id']}", headers=AUTH)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["company"] == "Typed Name"
    assert data["score"] == 0
    assert data["signals"] == [] and data["entryPoints"] == []
    assert data["startersMd"] == "" and data["referencesMd"] == ""


def test_spanish_brief_gets_spanish_labels():
    spanish = "# ALKIRA OPPORTUNITY BRIEF\n*[Agosto 2026]*\n\n## Cemex\n\n**Alkira Fit Score: 3 / 5**\n\nBuen ajuste.\n"
    repo = FakeRepo()
    row = repo.seed("partner@example.com", company="Cemex", brief_md=spanish, score=3)
    client = make_client(repo)
    data = client.get(f"/api/brief/briefs/{row['id']}", headers=AUTH).json()["data"]
    assert data["language"] == "es"
    assert data["labels"]["alkira_fit"] != "Alkira Fit"
    listed = client.get("/api/brief/briefs", headers=AUTH).json()["data"]
    assert listed[0]["language"] == "es"
