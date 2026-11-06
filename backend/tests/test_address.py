import httpx
from fastapi.testclient import TestClient

from app import geocode
from app.config import Settings
from app.inspector import FakeInspector
from app.main import create_app

from .conftest import make_result, submit

DELHI = {"pin": "110004", "state": "Delhi", "district": "New Delhi", "city": "New Delhi", "area": "Raisina Hill", "road": "Mother Teresa Crescent"}


def fake_lookup(monkeypatch, answer):
    calls = []

    def reverse(url, lat, lng):
        calls.append((url, lat, lng))
        return answer

    monkeypatch.setattr(geocode, "reverse", reverse)
    return calls


def test_address_is_looked_up_once_and_kept(client, monkeypatch):
    calls = fake_lookup(monkeypatch, DELHI)
    code = submit(client)["code"]
    for _ in range(3):
        r = client.get(f"/api/public/reports/{code}/address")
        assert r.status_code == 200
        assert r.json() == DELHI
    assert len(calls) == 1
    assert calls[0][1:] == (13.05, 77.63)


def test_failed_lookup_is_not_kept(client, monkeypatch):
    fake_lookup(monkeypatch, None)
    code = submit(client)["code"]
    assert client.get(f"/api/public/reports/{code}/address").json() == {}
    calls = fake_lookup(monkeypatch, DELHI)
    assert client.get(f"/api/public/reports/{code}/address").json() == DELHI
    assert len(calls) == 1


def test_report_without_a_pin_has_no_address(client, monkeypatch):
    calls = fake_lookup(monkeypatch, DELHI)
    code = submit(client, lat=None)["code"]
    assert client.get(f"/api/public/reports/{code}/address").json() == {}
    assert calls == []


def test_unpublished_report_has_no_address(client, inspector, monkeypatch):
    calls = fake_lookup(monkeypatch, DELHI)
    inspector.result = make_result(confidence=0.3)
    code = submit(client)["code"]
    assert client.get(f"/api/public/reports/{code}/address").status_code == 404
    assert calls == []


def test_lookup_can_be_switched_off(tmp_path, monkeypatch):
    calls = fake_lookup(monkeypatch, DELHI)
    settings = Settings(ai_mode="fake", data_dir=tmp_path, web_dist=tmp_path / "nodist", geocode_url="")
    off = TestClient(create_app(settings, FakeInspector()))
    code = submit(off)["code"]
    assert off.get(f"/api/public/reports/{code}/address").json() == {}
    assert calls == []


def test_reverse_reads_an_indian_address_and_survives_failure(monkeypatch):
    monkeypatch.setattr(geocode, "MIN_GAP_S", 0)
    answer = {"address": {"road": "Mother Teresa Crescent", "suburb": "Raisina Hill", "city": "New Delhi", "state_district": "New Delhi", "state": "Delhi", "postcode": "110004"}}

    def good(url, **kw):
        assert kw["headers"]["User-Agent"].startswith("RasteScan")
        return httpx.Response(200, json=answer, request=httpx.Request("GET", url))

    monkeypatch.setattr(geocode.httpx, "get", good)
    assert geocode.reverse("https://geo.test/reverse", 28.6, 77.2) == DELHI

    def down(url, **kw):
        raise httpx.ConnectTimeout("no route")

    monkeypatch.setattr(geocode.httpx, "get", down)
    assert geocode.reverse("https://geo.test/reverse", 28.6, 77.2) is None
