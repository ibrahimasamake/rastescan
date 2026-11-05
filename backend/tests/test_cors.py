"""CORS: strict by default, open to private-network pages when CORS_ALLOW_LAN is on, and '*' on request."""
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def preflight(client, origin):
    r = client.options("/api/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET",
                                               "Access-Control-Request-Headers": "authorization,content-type"})
    return r.headers.get("access-control-allow-origin")


def make(tmp_path, **kw):
    return TestClient(create_app(Settings(ai_mode="fake", data_dir=tmp_path, web_dist=tmp_path / "x", **kw)))


def test_default_allows_only_the_listed_origins(tmp_path):
    c = make(tmp_path)
    assert preflight(c, "http://localhost:5173") == "http://localhost:5173"
    assert preflight(c, "http://192.168.1.20:5173") is None
    assert preflight(c, "https://evil.example.com") is None


def test_lan_mode_allows_private_network_pages_but_not_the_internet(tmp_path):
    c = make(tmp_path, cors_allow_lan=True)
    for origin in ("http://192.168.1.20:5173", "http://10.0.0.7:5173", "http://172.20.10.3:5173",
                   "http://172.31.0.1", "http://my-mac.local:5173", "http://localhost:3000", "http://127.0.0.1:8000"):
        assert preflight(c, origin) == origin, origin
    for origin in ("https://evil.example.com", "http://172.32.0.1:5173", "http://192.168.1.20.evil.com", "http://11.0.0.1"):
        assert preflight(c, origin) is None, origin


def test_star_allows_any_origin(tmp_path):
    assert preflight(make(tmp_path, cors_origins=["*"]), "https://anything.example") == "*"
