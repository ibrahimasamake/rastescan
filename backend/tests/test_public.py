import json
from datetime import datetime, timedelta, timezone

from app.db import Database
from tests.conftest import make_result, photo_bytes, submit

PIN = {"X-Dashboard-Pin": "1234"}
SECRET_DEVICE = "very-secret-device-id-42"
EMAIL = "citizen@example.com"
NOTE = "near my house number 12"


def public_payloads(client, code):
    return [
        client.get("/api/public/reports").text,
        client.get(f"/api/public/reports/{code}").text,
        client.get("/api/public/stats").text,
        client.get("/api/public/wards").text,
        client.get("/api/public/recently-resolved").text,
        client.get("/api/public/export.csv").text,
        client.get("/api/public/config").text,
    ]


def test_public_json_never_contains_private_fields(client):
    r = submit(client, device=SECRET_DEVICE, note=NOTE, contact_email=EMAIL)
    for body in public_payloads(client, r["code"]):
        assert SECRET_DEVICE not in body
        assert EMAIL not in body
        assert NOTE not in body
        assert "device_id" not in body and "contact_email" not in body


def test_report_gets_ward_and_timeline(client):
    code = submit(client, lat=13.05, lng=77.63)["code"]
    detail = client.get(f"/api/public/reports/{code}").json()
    assert detail["ward"] == {"code": "W02", "name": "Nagawara"}
    assert [e["event"] for e in detail["timeline"]] == ["reported", "ai_assessed"]
    assert detail["public_status"] == "ai_verified"
    assert detail["timeline"][1]["detail"]["urgency"] == "HIGH"


def test_review_and_no_damage_are_not_public(client, inspector):
    inspector.result = make_result(confidence=0.4)
    review = submit(client, seed=1)
    inspector.result = make_result(hazard="None", severity=1, urgency="LOW", confidence=0.9, box=(0, 0, 0, 0))
    clean = submit(client, seed=2)
    assert review["status"] == "review" and clean["status"] == "no_damage"
    assert client.get("/api/public/reports").json()["total"] == 0
    assert client.get(f"/api/public/reports/{review['code']}").status_code == 404


def test_unsure_none_result_goes_to_review_not_no_damage(client, inspector):
    inspector.result = make_result(hazard="None", severity=1, urgency="LOW", confidence=0.3, box=(0, 0, 0, 0))
    assert submit(client)["status"] == "review"


def test_busy_ai_saves_report_for_review(client, inspector):
    inspector.busy = True
    r = submit(client)
    assert r["status"] == "review" and r["ai_pending"] is True
    queue = client.get("/api/v2/officer/queue", headers=PIN).json()
    assert queue["review"][0]["code"] == r["code"]


def test_filters_pagination_and_sorting(client, inspector):
    inspector.result = make_result(severity=9.5, urgency="CRITICAL", hazard="Open Manhole")
    a = submit(client, seed=1, lat=13.05, lng=77.63)
    inspector.result = make_result(severity=4.5, urgency="MEDIUM", hazard="Road Fissure")
    b = submit(client, seed=2, lat=13.01, lng=77.66)
    inspector.result = make_result(severity=7.5)
    submit(client, seed=3, lat=13.07, lng=77.59)
    get = lambda **p: client.get("/api/public/reports", params=p).json()  # noqa: E731
    assert get()["total"] == 3
    assert [i["code"] for i in get(urgency="CRITICAL")["items"]] == [a["code"]]
    assert [i["code"] for i in get(hazard="Road Fissure")["items"]] == [b["code"]]
    assert [i["code"] for i in get(ward="W02")["items"]] == [a["code"]]
    assert get(sort="urgency")["items"][0]["code"] == a["code"]
    assert len(get(per_page=2, page=2)["items"]) == 1
    assert get(bbox="77.62,13.04,77.64,13.06")["total"] == 1
    assert get(q=a["code"][-2:])["total"] >= 1
    assert get(status="resolved")["total"] == 0
    assert client.get("/api/public/reports", params={"status": "bogus"}).status_code == 400


def test_overdue_filter(client):
    code = submit(client)["code"]
    ctx = client.app.state.ctx
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    ctx.db.execute("UPDATE reports SET due_at = ? WHERE code = ?", (past, code))
    items = client.get("/api/public/reports", params={"overdue": "true"}).json()["items"]
    assert [i["code"] for i in items] == [code] and items[0]["overdue"] is True


def test_vote_once_per_device(client):
    r = submit(client, device="owner-device")
    url = f"/api/public/reports/{r['code']}/vote"
    assert client.post(url, json={"device_id": "owner-device"}).json()["added"] is False
    first = client.post(url, json={"device_id": "neighbour-device"}).json()
    again = client.post(url, json={"device_id": "neighbour-device"}).json()
    assert first == {"added": True, "reported_count": 2}
    assert again == {"added": False, "reported_count": 2}


def test_etag_returns_304(client):
    submit(client)
    first = client.get("/api/public/stats")
    second = client.get("/api/public/stats", headers={"If-None-Match": first.headers["etag"]})
    assert second.status_code == 304
    assert "max-age" in first.headers["cache-control"]


def test_stats_and_scoreboard_after_resolution(client, inspector):
    code = submit(client, lat=13.05, lng=77.63)["code"]
    submit(client, seed=5, lat=13.01, lng=77.66)
    inspector.result = make_result(hazard="None", severity=1, urgency="LOW", box=(0, 0, 0, 0))
    r = client.post(f"/api/reports/{code}/after-photo", files={"photo": ("a.jpg", photo_bytes(99), "image/jpeg")}, headers=PIN)
    assert r.json()["public_status"] == "resolved"
    stats = client.get("/api/public/stats").json()
    assert stats["open_now"] == 1 and stats["resolved_this_month"] == 1 and stats["reported_today"] == 2
    assert stats["avg_days_to_fix"] is not None
    board = client.get("/api/public/wards").json()
    assert board[0]["code"] == "W02" and board[0]["pct_within_deadline"] == 100 and board[0]["rank"] == 1
    resolved = client.get("/api/public/recently-resolved").json()
    assert resolved[0]["code"] == code and resolved[0]["after_photo_url"]
    timeline = client.get(f"/api/public/reports/{code}").json()["timeline"]
    assert [e["event"] for e in timeline][-2:] == ["repair_photo", "verified"]


def test_csv_export(client):
    code = submit(client)["code"]
    lines = client.get("/api/public/export.csv").text.strip().splitlines()
    assert lines[0].startswith("code,created_at,ward_code")
    assert lines[1].startswith(code)


def test_old_database_upgrades_in_place(tmp_path):
    import sqlite3
    from app.db import BASE_SCHEMA
    conn = sqlite3.connect(tmp_path / "old.db")
    conn.executescript(BASE_SCHEMA)
    conn.execute("INSERT INTO reports (code, photo_key, ai_json, hazard_type, severity, urgency, model_urgency, confidence,"
                 " needs_review, status, created_at, updated_at) VALUES ('RS-0001','k','{}','Pothole',7,'HIGH','HIGH',0.9,0,"
                 "'new','2026-01-01T00:00:00+00:00','2026-01-01T00:00:00+00:00')")
    conn.commit()
    conn.close()
    db = Database(tmp_path / "old.db")
    assert db.version == 1
    row = db.one("SELECT code, ward_code, is_demo FROM reports")
    assert row == {"code": "RS-0001", "ward_code": None, "is_demo": 0}
    Database(tmp_path / "old.db")  # second open is a no-op
    assert json.loads(json.dumps(db.query("SELECT * FROM status_history"))) == []
