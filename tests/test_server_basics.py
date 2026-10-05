import json
from dataclasses import replace

from tests.api_fakes import AUTH, TEST_SETTINGS, make_client


def test_health_needs_no_auth():
    resp = make_client().get("/api/brief/health")
    assert resp.status_code == 200
    assert resp.json() == {"success": True, "data": {"status": "ok"}, "error": None}


def test_me_without_the_header_is_401_in_the_envelope():
    resp = make_client().get("/api/brief/me")
    assert resp.status_code == 401
    assert resp.json() == {"success": False, "data": None, "error": "Not signed in"}


def test_me_rejects_a_header_that_is_not_an_email():
    resp = make_client().get("/api/brief/me", headers={"X-Auth-Email": "nope"})
    assert resp.status_code == 401


def test_me_lowercases_the_email_and_reports_non_admin():
    resp = make_client().get("/api/brief/me", headers=AUTH)
    assert resp.json()["data"] == {"email": "partner@example.com", "isAdmin": False}


def test_me_reports_admin_from_the_admins_file(tmp_path):
    admins = tmp_path / "admins.json"
    admins.write_text(json.dumps(["Partner@Example.com"]))
    client = make_client(settings=replace(TEST_SETTINGS, admins_file=str(admins)))
    assert client.get("/api/brief/me", headers=AUTH).json()["data"]["isAdmin"] is True


def test_alkira_net_and_alkira_com_are_the_same_admin(tmp_path):
    admins = tmp_path / "admins.json"
    admins.write_text(json.dumps(["blake@alkira.net"]))
    client = make_client(settings=replace(TEST_SETTINGS, admins_file=str(admins)))
    resp = client.get("/api/brief/me", headers={"X-Auth-Email": "blake@alkira.com"})
    assert resp.json()["data"]["isAdmin"] is True


def test_a_malformed_admins_file_means_not_admin(tmp_path):
    admins = tmp_path / "admins.json"
    admins.write_text("{not json")
    client = make_client(settings=replace(TEST_SETTINGS, admins_file=str(admins)))
    assert client.get("/api/brief/me", headers=AUTH).json()["data"]["isAdmin"] is False


def test_unknown_routes_use_the_envelope():
    resp = make_client().get("/api/brief/nope", headers=AUTH)
    assert resp.status_code == 404
    assert resp.json()["success"] is False
