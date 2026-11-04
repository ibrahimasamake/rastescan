import pytest

from app.inspector import InspectionError, parse_inspection
from app.schema import Inspection, needs_human_review, urgency_for
from tests.conftest import make_result

import json


def test_urgency_comes_from_score_bands():
    assert urgency_for(Inspection.model_validate(make_result(severity=3.9, urgency="HIGH"))) == "LOW"
    assert urgency_for(Inspection.model_validate(make_result(severity=4.0, urgency="LOW"))) == "MEDIUM"
    assert urgency_for(Inspection.model_validate(make_result(severity=8.9, urgency="LOW"))) == "HIGH"
    assert urgency_for(Inspection.model_validate(make_result(severity=9.0, urgency="LOW"))) == "CRITICAL"


def test_open_manhole_is_always_critical():
    r = Inspection.model_validate(make_result(hazard="Open Manhole", severity=5.0, urgency="MEDIUM"))
    assert urgency_for(r) == "CRITICAL"


def test_low_confidence_needs_review():
    assert needs_human_review(Inspection.model_validate(make_result(confidence=0.59)))
    assert not needs_human_review(Inspection.model_validate(make_result(confidence=0.6)))


def test_parse_strips_code_fences_and_chatter():
    text = "Here you go:\n```json\n" + json.dumps(make_result()) + "\n```"
    assert parse_inspection(text).hazard_type == "Pothole"


@pytest.mark.parametrize("bad", [
    "no json here",
    json.dumps({**make_result(), "hazard_type": "Crater"}),
    json.dumps({**make_result(), "severity_score": 11}),
    json.dumps(make_result(box=(800, 300, 500, 700))),
])
def test_parse_rejects_invalid(bad):
    with pytest.raises(InspectionError):
        parse_inspection(bad)


def test_none_hazard_allows_empty_box():
    assert parse_inspection(json.dumps(make_result(hazard="None", severity=1.0, urgency="LOW", box=(0, 0, 0, 0)))).hazard_type == "None"
