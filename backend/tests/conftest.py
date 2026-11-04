import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.inspector import FakeInspector, InspectorBusy
from app.main import create_app
from app.schema import Inspection


class FixedInspector:
    """Returns whatever result the test sets; counts calls. Set .busy to simulate a rate-limited provider."""

    mode = "fake"
    model = "fixed"
    busy = False

    def __init__(self):
        self.result = None
        self.calls = 0

    def inspect(self, jpeg):
        self.calls += 1
        if self.busy:
            raise InspectorBusy("rate limited")
        return Inspection.model_validate(self.result)


def make_result(hazard="Pothole", severity=7.6, urgency="HIGH", confidence=0.9, box=(520, 300, 800, 700)):
    return {
        "hazard_type": hazard, "confidence": confidence, "severity_score": severity, "urgency_level": urgency,
        "repair_recommendation": "Patch it.", "estimated_repair_time_hours": 3,
        "estimated_dimensions": {"width_cm": 60, "depth_category": "Deep"},
        "bounding_box": dict(zip(("ymin", "xmin", "ymax", "xmax"), box)),
    }


def photo_bytes(seed: int = 0) -> bytes:
    img = Image.new("RGB", (640, 480), (90 + seed % 100, 90, 90))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    return buf.getvalue()


@pytest.fixture
def inspector():
    fx = FixedInspector()
    fx.result = make_result()
    return fx


@pytest.fixture
def client(tmp_path, inspector):
    settings = Settings(ai_mode="fake", data_dir=tmp_path, web_dist=tmp_path / "nodist", dashboard_pin="1234", reports_per_hour=5)
    return TestClient(create_app(settings, inspector))


@pytest.fixture
def fake_client(tmp_path):
    settings = Settings(ai_mode="fake", data_dir=tmp_path, web_dist=tmp_path / "nodist")
    return TestClient(create_app(settings, FakeInspector()))


ADMIN = {"email": "admin@example.org", "password": "correct-horse-battery"}


@pytest.fixture
def officer_client(tmp_path, inspector):
    """Officer accounts enabled, PIN disabled, an admin seeded from settings."""
    settings = Settings(ai_mode="fake", data_dir=tmp_path, web_dist=tmp_path / "nodist", dashboard_pin="",
                        admin_email=ADMIN["email"], admin_password=ADMIN["password"], admin_name="Asha Rao",
                        reports_per_hour=100, logins_per_15min=5)
    return TestClient(create_app(settings, inspector))


def login(client, email=ADMIN["email"], password=ADMIN["password"]):
    r = client.post("/api/v2/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def submit(client, seed=0, lat=13.05, lng=77.63, device="dev-1", **extra):
    data = {"device_id": device, **extra}
    if lat is not None:
        data.update(lat=str(lat), lng=str(lng))
    r = client.post("/api/reports", files={"photo": ("p.jpg", photo_bytes(seed), "image/jpeg")}, data=data)
    assert r.status_code == 200, r.text
    return r.json()
