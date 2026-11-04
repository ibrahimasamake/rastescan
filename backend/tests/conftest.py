import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.inspector import FakeInspector
from app.main import create_app
from app.schema import Inspection


class FixedInspector:
    """Returns whatever result the test sets; counts calls."""

    mode = "fake"

    def __init__(self):
        self.result = None
        self.calls = 0

    def inspect(self, jpeg):
        self.calls += 1
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
