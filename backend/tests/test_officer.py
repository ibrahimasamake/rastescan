from tests.conftest import ADMIN, login, make_result, photo_bytes, submit

CSRF = {"X-Requested-With": "RasteScan"}


def test_login_and_errors(officer_client):
    c = officer_client
    assert c.get("/api/v2/officer/queue").status_code == 401
    assert c.post("/api/v2/auth/login", json={"email": ADMIN["email"], "password": "wrong-password"}).status_code == 401
    assert c.post("/api/v2/auth/login", json={"email": "nobody@example.org", "password": "x"}).status_code == 401
    headers = login(c)
    assert c.get("/api/v2/auth/me", headers=headers).json() == {"signed_in": True, "name": "Asha Rao", "role": "admin"}
    assert c.get("/api/v2/officer/queue", headers=headers).status_code == 200


def test_login_rate_limit(officer_client):
    codes = [officer_client.post("/api/v2/auth/login", json={"email": "a@b.c", "password": "nope"}).status_code
             for _ in range(6)]
    assert codes == [401] * 5 + [429]


def test_cookie_session_needs_csrf_header_for_changes(officer_client):
    c = officer_client
    code = submit(c)["code"]
    login(c)  # sets the HttpOnly cookie on the test client
    assert c.get("/api/v2/officer/queue").status_code == 200
    assert c.post(f"/api/v2/officer/reports/{code}/comment", json={"body": "On it"}).status_code == 403
    assert c.post(f"/api/v2/officer/reports/{code}/comment", json={"body": "On it"}, headers=CSRF).status_code == 200


def test_pin_disabled_when_empty(officer_client):
    assert officer_client.get("/api/v2/officer/queue", headers={"X-Dashboard-Pin": ""}).status_code == 401


def test_assign_comment_and_public_timeline(officer_client):
    c = officer_client
    h = login(c)
    code = submit(c)["code"]
    r = c.post(f"/api/v2/officer/reports/{code}/assign", json={"assignee": "Crew 3 (Ravi)"}, headers=h)
    assert r.json()["status"] == "assigned" and r.json()["assignee"] == "Crew 3 (Ravi)"
    c.post(f"/api/v2/officer/reports/{code}/comment", json={"body": "Crew will reach by 4 pm."}, headers=h)
    public = c.get(f"/api/public/reports/{code}").json()
    events = [(e["event"], e["actor"]) for e in public["timeline"]]
    assert ("assigned", "Asha Rao") in events
    assert ("comment", "Asha Rao") in events
    assert public["assignee"] == "Crew 3 (Ravi)"
    assert ADMIN["email"] not in c.get(f"/api/public/reports/{code}").text


def test_dismiss_needs_public_reason(officer_client):
    c = officer_client
    h = login(c)
    code = submit(c)["code"]
    assert c.post(f"/api/v2/officer/reports/{code}/status", json={"status": "dismissed"}, headers=h).status_code == 400
    r = c.post(f"/api/v2/officer/reports/{code}/status",
               json={"status": "dismissed", "reason": "Private road, not maintained by the city."}, headers=h)
    assert r.json()["public_status"] == "dismissed"
    assert c.get(f"/api/public/reports/{code}").json()["dismiss_reason"] == "Private road, not maintained by the city."


def test_review_confirm_and_ai_accuracy(officer_client, inspector):
    c = officer_client
    h = login(c)
    inspector.result = make_result(confidence=0.4, severity=5.0, urgency="MEDIUM")
    code = submit(c)["code"]
    assert c.get(f"/api/public/reports/{code}").status_code == 404
    r = c.post(f"/api/v2/officer/reports/{code}/review", json={"hazard_type": "Open Manhole", "severity_score": 6}, headers=h)
    assert r.json()["status"] == "new" and r.json()["urgency"] == "CRITICAL"  # open manhole rule still applies
    assert c.get(f"/api/public/reports/{code}").status_code == 200
    stats = c.get("/api/v2/officer/analytics", headers=h).json()["ai_accuracy"]
    assert stats == {"checked": 1, "overridden": 1, "agreement_pct": 0}


def test_repair_photo_resolves_or_reopens(officer_client, inspector):
    c = officer_client
    h = login(c)
    code = submit(c)["code"]
    upload = lambda seed: c.post(f"/api/v2/officer/reports/{code}/repair-photo",  # noqa: E731
                                 files={"photo": ("a.jpg", photo_bytes(seed), "image/jpeg")}, headers=h).json()
    inspector.result = make_result(severity=6.2, urgency="MEDIUM")
    reopened = upload(50)
    assert reopened["status"] == "assigned"
    assert reopened["timeline"][-1]["event"] == "reopened"
    inspector.result = make_result(hazard="None", severity=1, urgency="LOW", box=(0, 0, 0, 0))
    resolved = upload(51)
    assert resolved["public_status"] == "resolved" and resolved["resolved_at"]
    assert resolved["after_result"]["hazard_type"] == "None"


def test_merge_and_unmerge(officer_client):
    c = officer_client
    h = login(c)
    a = submit(c, seed=1, lat=13.05)["code"]
    b = submit(c, seed=2, lat=13.07)["code"]
    merged = c.post(f"/api/v2/officer/reports/{b}/merge", json={"into": a}, headers=h).json()
    assert merged["merged_into"] == a
    assert c.get(f"/api/public/reports/{a}").json()["reported_count"] == 2
    assert c.get("/api/public/reports").json()["total"] == 1
    assert c.post(f"/api/v2/officer/reports/{b}/unmerge", headers=h).json()["merged_into"] is None
    assert c.get("/api/public/reports").json()["total"] == 2


def test_bulk_status_and_history_audit(officer_client):
    c = officer_client
    h = login(c)
    codes = [submit(c, seed=i, lat=13.0 + i / 100)["code"] for i in range(3)]
    assert c.post("/api/v2/officer/bulk-status", json={"codes": codes, "status": "assigned"}, headers=h).json() == {"updated": 3}
    history = c.get(f"/api/v2/officer/reports/{codes[0]}", headers=h).json()["history"]
    last = history[-1]
    assert (last["event"], last["actor"], last["old_value"], last["new_value"]) == ("status", "Asha Rao", "new", "assigned")


def test_queue_orders_by_urgency_then_deadline(officer_client, inspector):
    c = officer_client
    h = login(c)
    inspector.result = make_result(severity=7.2)
    later = submit(c, seed=1, lat=13.0)["code"]
    inspector.result = make_result(severity=8.5)
    sooner = submit(c, seed=2, lat=13.1)["code"]
    ctx = c.app.state.ctx
    ctx.db.execute("UPDATE reports SET due_at = '2030-01-02T00:00:00+00:00' WHERE code = ?", (later,))
    ctx.db.execute("UPDATE reports SET due_at = '2030-01-01T00:00:00+00:00' WHERE code = ?", (sooner,))
    inspector.result = make_result(hazard="Open Manhole", severity=9.6, urgency="CRITICAL")
    critical = submit(c, seed=3, lat=13.2)["code"]
    order = [t["code"] for t in c.get("/api/v2/officer/queue", headers=h).json()["tickets"]]
    assert order == [critical, sooner, later]


def test_work_order_route(officer_client):
    c = officer_client
    h = login(c)
    far = submit(c, seed=1, lat=13.10, lng=77.60)["code"]
    near = submit(c, seed=2, lat=13.051, lng=77.631)["code"]
    first = submit(c, seed=3, lat=13.05, lng=77.63)["code"]
    ctx = c.app.state.ctx
    ctx.db.execute("UPDATE reports SET due_at = '2020-01-01T00:00:00+00:00' WHERE code = ?", (first,))
    for code in (far, near, first):
        c.post(f"/api/v2/officer/reports/{code}/assign", json={"assignee": "Crew 1"}, headers=h)
    wo = c.get("/api/v2/officer/work-order", params={"assignee": "Crew 1"}, headers=h).json()
    assert [s["code"] for s in wo["stops"]] == [first, near, far]
    assert wo["stops"][0]["leg_m"] == 0 and wo["total_km"] > 5


def test_admin_manages_officers(officer_client):
    c = officer_client
    h = login(c)
    r = c.post("/api/v2/admin/officers", json={"email": "Ravi@Example.org", "name": "Ravi K", "password": "longenough123"},
               headers=h)
    assert r.json()["email"] == "ravi@example.org"
    officer = login(c, "ravi@example.org", "longenough123")
    assert c.get("/api/v2/admin/officers", headers=officer).status_code == 403
    assert c.get("/api/v2/officer/queue", headers=officer).status_code == 200
    c.patch(f"/api/v2/admin/officers/{r.json()['id']}", json={"active": False}, headers=h)
    assert c.get("/api/v2/officer/queue", headers=officer).status_code == 401
    assert "password_hash" not in c.get("/api/v2/admin/officers", headers=h).text


def test_admin_export_has_note_but_no_private_contact(officer_client):
    c = officer_client
    h = login(c)
    submit(c, note="Near the bus stop", contact_email="me@example.com", device="dev-secret-99")
    body = c.get("/api/v2/admin/export.csv", headers=h).text
    assert "Near the bus stop" in body
    assert "me@example.com" not in body and "dev-secret-99" not in body


def test_secret_key_file_is_created_outside_git(officer_client):
    ctx = officer_client.app.state.ctx
    assert (ctx.settings.data_dir / "secret.key").is_file()


def test_officer_can_resolve_after_ai_still_sees_damage_and_it_shows_as_recently_resolved(officer_client, inspector):
    c = officer_client
    h = login(c)
    code = submit(c)["code"]
    inspector.result = make_result(severity=6.2, urgency="MEDIUM")  # AI still sees damage in the repair photo
    c.post(f"/api/v2/officer/reports/{code}/repair-photo", files={"photo": ("a.jpg", photo_bytes(50), "image/jpeg")}, headers=h)
    assert c.get("/api/public/recently-resolved").json() == []
    done = c.post(f"/api/v2/officer/reports/{code}/status", json={"status": "verified"}, headers=h).json()
    assert done["public_status"] == "resolved"
    assert [r["code"] for r in c.get("/api/public/recently-resolved").json()] == [code]
    # Resolving with no photo at all also counts
    other = submit(c, seed=7, lat=13.2)["code"]
    c.post(f"/api/v2/officer/reports/{other}/status", json={"status": "verified"}, headers=h)
    assert other in [r["code"] for r in c.get("/api/public/recently-resolved").json()]


def test_rescan_fills_in_a_report_saved_while_the_ai_was_busy(officer_client, inspector):
    from app.inspector import InspectorBusy

    c = officer_client
    h = login(c)
    real = inspector.inspect

    def busy(jpeg):
        raise InspectorBusy("rate limited")

    inspector.inspect = busy
    r = submit(c)
    assert r["status"] == "review" and r["ai_pending"]
    code = r["code"]
    still = c.post(f"/api/v2/officer/reports/{code}/rescan", headers=h)
    assert still.status_code == 503
    inspector.inspect = real
    done = c.post(f"/api/v2/officer/reports/{code}/rescan", headers=h).json()
    assert done["status"] == "new" and not done["ai_pending"] and done["hazard_type"] == "Pothole"
    assert c.post(f"/api/v2/officer/reports/{code}/rescan", headers=h).status_code == 409


def test_model_lab_is_admin_only_and_tests_a_model_without_touching_reports(officer_client):
    c = officer_client
    assert c.get("/api/v2/admin/models").status_code == 401
    h = login(c)
    listing = c.get("/api/v2/admin/models", headers=h).json()
    ids = {m["id"] for m in listing["models"]}
    assert "fake:sample" in ids and "yolo:rdd2022-yolov8m" in ids and any(m["provider"] == "ollama" for m in listing["models"])
    r = c.post("/api/v2/admin/models/test", headers=h, data={"provider": "fake", "model": ""},
               files={"photo": ("p.jpg", photo_bytes(3), "image/jpeg")}).json()
    assert r["ok"] and r["result"]["hazard_type"] and r["seconds"] >= 0
    assert c.get("/api/public/reports").json()["total"] == 0  # nothing was saved
    bad = c.post("/api/v2/admin/models/test", headers=h, data={"provider": "nope"},
                 files={"photo": ("p.jpg", photo_bytes(3), "image/jpeg")})
    assert bad.status_code == 400
    assert c.post("/api/v2/admin/models/live", headers=h, json={"provider": "fake"}).json()["live"]["provider"] == "fake"


def test_model_pull_only_allows_recommended_tags(officer_client, monkeypatch):
    from app import routes_models

    c = officer_client
    h = login(c)
    assert c.post("/api/v2/admin/models/pull", json={"model": "evil/whatever:latest"}, headers=h).status_code == 400
    started = []
    monkeypatch.setattr(routes_models, "_download", lambda ctx, tag: started.append(tag))
    r = c.post("/api/v2/admin/models/pull", json={"model": "qwen2.5vl:3b"}, headers=h).json()
    assert r["running"] is True
    assert c.post("/api/v2/admin/models/pull", json={"model": "qwen2.5vl:3b"}, headers=h).json()["running"] is True
    assert len(started) <= 1  # a second click while running does not start a second download


def test_pending_reports_are_finished_by_the_background_pass(officer_client, inspector):
    from app.inspector import InspectorBusy
    from app.services import process_pending

    c = officer_client
    real = inspector.inspect
    inspector.inspect = lambda jpeg: (_ for _ in ()).throw(InspectorBusy("slow"))
    first, second = submit(c, seed=1)["code"], submit(c, seed=2, lat=13.4)["code"]
    ctx = c.app.state.ctx
    assert process_pending(ctx) == 0  # still busy: postponed, nothing lost
    inspector.inspect = real
    assert process_pending(ctx) == 2
    for code in (first, second):
        r = c.get(f"/api/public/reports/{code}").json()
        assert r["hazard_type"] == "Pothole" and r["public_status"] != "reported"
    assert process_pending(ctx) == 0
