from tests.conftest import make_result, photo_bytes

PIN = {"X-Dashboard-Pin": "1234"}


def post(client, seed=0, lat=13.04, lng=77.62, device="d1"):
    data = {"device_id": device}
    if lat is not None:
        data.update(lat=str(lat), lng=str(lng))
    return client.post("/api/reports", files={"photo": ("p.jpg", photo_bytes(seed), "image/jpeg")}, data=data)


def test_report_is_created_and_urgency_recomputed(client, inspector):
    inspector.result = make_result(severity=9.3, urgency="HIGH")
    r = post(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] == "RS-0001"
    assert body["urgency"] == "CRITICAL" and body["model_urgency"] == "HIGH"
    assert body["status"] == "new"
    assert client.get(body["photo_url"]).status_code == 200


def test_nearby_same_hazard_is_merged(client):
    first = post(client, seed=1).json()
    second = post(client, seed=2, lat=13.04005, lng=77.62005).json()  # about 7 m away
    far = post(client, seed=3, lat=13.05, lng=77.62).json()
    assert second["merged_into"] == first["code"]
    assert far["merged_into"] is None
    q = client.get("/api/queue").json()
    codes = [t["code"] for t in q["tickets"]]
    assert codes.count(first["code"]) == 1 and second["code"] not in codes
    assert next(t for t in q["tickets"] if t["code"] == first["code"])["merged_count"] == 2


def test_queue_orders_by_urgency_then_severity(client, inspector):
    inspector.result = make_result(severity=4.5, urgency="MEDIUM")
    post(client, seed=1, lat=13.0)
    inspector.result = make_result(hazard="Open Manhole", severity=9.6, urgency="CRITICAL")
    post(client, seed=2, lat=13.1)
    inspector.result = make_result(severity=7.2, urgency="HIGH")
    post(client, seed=3, lat=13.2)
    q = client.get("/api/queue").json()
    assert [t["urgency"] for t in q["tickets"]] == ["CRITICAL", "HIGH", "MEDIUM"]
    assert q["counts"] == {"LOW": 0, "MEDIUM": 1, "HIGH": 1, "CRITICAL": 1}


def test_no_damage_and_low_confidence_stay_out_of_queue(client, inspector):
    inspector.result = make_result(hazard="None", severity=1.0, urgency="LOW", box=(0, 0, 0, 0))
    assert post(client, seed=1).json()["status"] == "no_damage"
    inspector.result = make_result(confidence=0.4)
    assert post(client, seed=2).json()["status"] == "review"
    q = client.get("/api/queue").json()
    assert q["tickets"] == [] and len(q["review"]) == 1


def test_same_photo_uses_cache(client, inspector):
    post(client, seed=7)
    post(client, seed=7, lat=14.0)
    assert inspector.calls == 1


def test_status_change_needs_pin_and_carries_to_duplicates(client):
    first = post(client, seed=1).json()
    dup = post(client, seed=2, lat=13.04001).json()
    assert client.patch(f"/api/reports/{first['code']}", json={"status": "assigned"}).status_code == 401
    r = client.patch(f"/api/reports/{first['code']}", json={"status": "assigned"}, headers=PIN)
    assert r.json()["status"] == "assigned"
    assert client.get(f"/api/reports/{dup['code']}").json()["status"] == "assigned"


def test_after_photo_verifies_when_damage_gone(client, inspector):
    code = post(client, seed=1).json()["code"]
    inspector.result = make_result(hazard="None", severity=1.0, urgency="LOW", box=(0, 0, 0, 0))
    r = client.post(f"/api/reports/{code}/after-photo", files={"photo": ("a.jpg", photo_bytes(9), "image/jpeg")}, headers=PIN)
    assert r.json()["status"] == "verified"
    assert r.json()["after_result"]["hazard_type"] == "None"


def test_rate_limit_per_device(client):
    codes = [post(client, seed=i, lat=10 + i).status_code for i in range(6)]
    assert codes == [200] * 5 + [429]


def test_rejects_non_image(client):
    r = client.post("/api/reports", files={"photo": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_report_without_gps_is_accepted(client):
    assert post(client, lat=None).json()["lat"] is None


def test_my_reports_lists_device_history(client):
    post(client, seed=1, device="abc")
    post(client, seed=2, device="other", lat=20)
    assert [r["code"] for r in client.get("/api/reports", params={"device_id": "abc"}).json()] == ["RS-0001"]


def test_fake_mode_reports_itself(fake_client):
    assert fake_client.get("/api/health").json()["ai_mode"] == "fake"
