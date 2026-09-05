"""Web API parity: every screen action goes through the same services as MCP and the CLI, and
roles gate writes (viewer reads only, entry logs and corrects, admin manages)."""
import pytest
from fastapi.testclient import TestClient

from app import users
from app.main import app

PW = "password123"


@pytest.fixture
def clients():
    app.state.limiter.enabled = False          # login is rate-limited per IP; tests share one
    for role in ("admin", "entry", "viewer"):
        users.create_user(f"{role}@example.com", role.title(), PW, role)
    out = {}
    for role in ("admin", "entry", "viewer"):
        c = TestClient(app)
        r = c.post("/auth/login", json={"email": f"{role}@example.com", "password": PW})
        assert r.status_code == 200, r.text
        out[role] = c
    out["anon"] = TestClient(app)
    return out


def _project(admin):
    r = admin.post("/api/projects", json={"id": "TST", "name": "Test Line", "kind": "company", "line": "TST"})
    assert r.status_code == 201, r.text
    assert admin.post("/api/projects/TST/locations", json={"name": "Yard A"}).status_code == 201


def test_roles_and_auth(clients):
    a, e, v, anon = clients["admin"], clients["entry"], clients["viewer"], clients["anon"]
    _project(a)
    assert anon.get("/api/projects").status_code == 401
    assert v.get("/api/projects").status_code == 200
    body = {"date": "2026-06-01", "ties": 100, "relay_ties": 40, "location": "Yard A"}
    assert v.post("/api/projects/TST/log", json=body).status_code == 403
    assert e.post("/api/projects/TST/log", json=body).status_code == 201
    assert e.post("/api/projects", json={"id": "X", "name": "x"}).status_code == 403
    assert e.get("/api/admin/users").status_code == 403
    assert v.get("/api/admin/settings").status_code == 403
    assert e.post("/api/projects/TST/status", json={"status": "complete"}).status_code == 403


def test_daily_log_correction(clients):
    a, e = clients["admin"], clients["entry"]
    _project(a)
    e.post("/api/projects/TST/log", json={"date": "2026-06-01", "ties": 100, "relay_ties": 40})
    e.post("/api/projects/TST/log", json={"date": "2026-06-02", "ties": 50})
    r = e.patch("/api/projects/TST/log/2026-06-01", json={"new_ties": 120, "relay_ties": 50})
    assert r.status_code == 200 and r.json()["ties"] == 120 and r.json()["relay_ties"] == 50
    log = a.get("/api/projects/TST").json()["daily_log"]
    assert [x["running_total"] for x in log] == [120, 170]
    assert e.patch("/api/projects/TST/log/2026-06-09", json={"new_ties": 1}).status_code == 409
    assert e.post("/api/projects/TST/log", json={"date": "2026-06-01", "ties": 5}).status_code == 409
    assert e.post("/api/projects/TST/log", json={"date": "2026-06-03", "ties": 5, "location": "Nowhere"}).status_code == 409
    assert e.patch("/api/projects/TST/log/2026-06-02", json={"new_ties": 10, "relay_ties": 20}).status_code == 409


def test_switches_derails_locations(clients):
    a, e = clients["admin"], clients["entry"]
    _project(a)
    r = e.post("/api/projects/TST/switches", json={
        "name": "North Main", "date": "2026-06-03",
        "timbers": [{"length": 9, "planned": 2, "actual": 3}], "location": "Yard A"})
    assert r.status_code == 201 and r.json()["location"] == "yard-a"
    sid = r.json()["id"]
    r = e.patch(f"/api/projects/TST/switches/{sid}", json={"new_name": "North Main Switch", "location": ""})
    assert r.status_code == 200 and r.json()["name"] == "North Main Switch" and r.json()["location"] is None
    assert e.patch(f"/api/projects/TST/switches/{sid}", json={}).status_code == 409
    assert e.delete("/api/projects/TST/switches/nope").status_code == 404
    assert e.delete(f"/api/projects/TST/switches/{sid}").status_code == 200
    assert e.post("/api/projects/TST/switches", json={"name": "x", "date": "2026-06-03", "timbers": []}).status_code == 422

    r = e.post("/api/projects/TST/derails", json={"name": "South Derail", "date": "2026-06-04", "derail_type": "portable"})
    assert r.status_code == 201
    did = r.json()["id"]
    r = e.patch(f"/api/projects/TST/derails/{did}", json={
        "derail_type": "stationary", "timbers": [{"length": 12, "planned": 2, "actual": 2, "head_block": True}]})
    assert r.json()["derail_type"] == "stationary" and r.json()["timbers"][0]["head_block"] is True
    assert e.delete(f"/api/projects/TST/derails/{did}").status_code == 200

    e.post("/api/projects/TST/log", json={"date": "2026-06-01", "ties": 10, "location": "Yard A"})
    assert e.delete("/api/projects/TST/locations/yard-a").status_code == 409
    r = e.patch("/api/projects/TST/locations/yard-a", json={"new_name": "Yard B"})
    assert r.status_code == 200 and r.json()["id"] == "yard-a" and r.json()["name"] == "Yard B"
    assert e.post("/api/projects/TST/locations", json={"name": "yard b"}).status_code == 409
    assert e.post("/api/projects/TST/locations", json={"name": "Siding"}).status_code == 201
    assert e.delete("/api/projects/TST/locations/siding").status_code == 200


def test_downtime(clients):
    a, e = clients["admin"], clients["entry"]
    _project(a)
    r = e.post("/api/projects/TST/downtime", json={"incidents": [
        {"date": "2026-06-05", "machine": "Tamper", "down_at": "08:00", "resumed": "09:30", "notes": "leak"},
        {"date": "2026-06-05", "machine": "Tamper", "down_at": "13:00"}]})
    assert r.status_code == 201 and r.json()[0]["duration_minutes"] == 90
    assert e.patch("/api/projects/TST/downtime/2026-06-05", json={"machine": "Tamper", "notes": "x"}).status_code == 409
    r = e.patch("/api/projects/TST/downtime/2026-06-05",
                json={"machine": "Tamper", "match_down_at": "13:00", "resumed": "14:00"})
    assert r.status_code == 200 and r.json()["duration_minutes"] == 60
    assert e.delete("/api/projects/TST/downtime/2026-06-05", params={"machine": "Tamper"}).status_code == 409
    assert e.delete("/api/projects/TST/downtime/2026-06-05", params={"machine": "Tamper", "down_at": "08:00"}).status_code == 200
    assert e.delete("/api/projects/TST/downtime/2026-06-09", params={"machine": "Tamper"}).status_code == 404
    assert e.patch("/api/projects/TST/downtime/2026-06-05", json={"machine": "Tamper", "down_at": "25:99"}).status_code == 422


def test_project_lifecycle(clients):
    a = clients["admin"]
    _project(a)
    assert a.post("/api/projects", json={"id": "TST", "name": "dup"}).status_code == 409
    assert a.post("/api/projects", json={"id": "bad id!", "name": "x"}).status_code == 422
    assert a.post("/api/projects", json={"id": "S1", "name": "Sponsored", "kind": "sponsored", "goal_ties": 1000}).status_code == 201
    assert a.get("/api/projects/TST").json()["project"]["status"] == "complete"
    assert a.post("/api/projects/TST/status", json={"status": "active"}).status_code == 200
    assert a.get("/api/projects/S1").json()["project"]["status"] == "complete"
    assert a.post("/api/projects/TST/status", json={"status": "bogus"}).status_code == 422
    r = a.patch("/api/projects/TST", json={"daily_target": 60})
    assert r.status_code == 200 and r.json()["project"]["daily_target"] == 60
    assert a.patch("/api/projects/TST", json={}).status_code == 409


def test_admin_users_settings_scheduler(clients):
    a = clients["admin"]
    r = a.get("/api/admin/users")
    assert r.status_code == 200 and len(r.json()) == 3
    r = a.post("/api/admin/users", json={"email": "gang@example.com", "name": "Gang", "role": "entry", "password": PW})
    assert r.status_code == 201 and r.json()["role"] == "entry"
    assert a.post("/api/admin/users", json={"email": "gang@example.com", "name": "Dup", "password": PW}).status_code == 409
    assert a.post("/api/admin/users", json={"email": "z@example.com", "name": "Z", "password": "short"}).status_code == 422
    r = a.patch("/api/admin/users/gang@example.com", json={"role": "viewer"})
    assert r.status_code == 200 and r.json()["role"] == "viewer"
    assert a.patch("/api/admin/users/ghost@example.com", json={"name": "x"}).status_code == 404
    assert a.delete("/api/admin/users/gang@example.com").status_code == 200
    assert a.patch("/api/admin/users/admin@example.com", json={"role": "viewer"}).status_code == 409
    assert a.delete("/api/admin/users/admin@example.com").status_code == 409

    r = a.post("/api/admin/settings/test-email", json={"to": "someone@example.com"})
    assert r.status_code == 503                      # mail not configured yet, never touches the network
    r = a.get("/api/admin/settings")
    assert r.status_code == 200 and r.json()["smtp"]["password_set"] is False
    r = a.put("/api/admin/settings", json={
        "report_recipients": ["rt@example.com"],
        "smtp": {"host": "smtp.example.com", "user": "u", "password": "secret"},
        "schedule": {"day_of_week": "mon", "hour": 6}})
    assert r.status_code == 200
    assert r.json()["smtp"]["password"] == "" and r.json()["smtp"]["password_set"] is True
    r = a.put("/api/admin/settings", json={"smtp": {"host": "smtp2.example.com", "password": ""}})
    body = r.json()
    assert body["smtp"]["host"] == "smtp2.example.com" and body["smtp"]["user"] == "u"     # untouched fields kept
    assert body["smtp"]["password_set"] is True and body["schedule"]["day_of_week"] == "mon"
    assert a.put("/api/admin/settings", json={"schedule": {"hour": 99}}).status_code == 422
    r = a.get("/api/admin/scheduler")
    assert r.status_code == 200 and r.json()["schedule"]["hour"] == 6


def test_admin_mcp_tokens(clients):
    a, e = clients["admin"], clients["entry"]
    assert e.get("/api/admin/mcp-tokens").status_code == 403
    r = a.get("/api/admin/mcp-tokens")
    assert r.status_code == 200 and r.json()["tokens"] == [] and r.json()["enabled"] is False
    r = a.post("/api/admin/mcp-tokens", json={"email": "entry@example.com", "label": "Claude", "days": 30})
    assert r.status_code == 201 and r.json()["token"].count(".") == 2
    jti = r.json()["record"]["id"]
    assert a.post("/api/admin/mcp-tokens", json={"email": "ghost@example.com", "label": "x"}).status_code == 404
    assert a.post("/api/admin/mcp-tokens", json={"email": "entry@example.com", "label": "x", "days": 0}).status_code == 422
    assert [t["id"] for t in a.get("/api/admin/mcp-tokens").json()["tokens"]] == [jti]
    assert a.delete(f"/api/admin/mcp-tokens/{jti}").status_code == 200
    assert a.get("/api/admin/mcp-tokens").json()["tokens"][0]["revoked"] is True
    assert a.delete("/api/admin/mcp-tokens/nope").status_code == 404
