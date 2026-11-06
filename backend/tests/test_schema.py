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


def test_several_defects_are_combined_worst_first():
    from app.inspector import parse_inspection
    import json
    from tests.conftest import make_result
    a = make_result(severity=5.2, urgency="MEDIUM", box=(600, 560, 780, 760))
    b = make_result(severity=7.6, box=(520, 120, 760, 380))
    dup = make_result(severity=7.0, box=(525, 125, 755, 375))  # same pothole again
    none = make_result(hazard="None", severity=1.2, box=(0, 0, 0, 0))
    r = parse_inspection(json.dumps({"detections": [a, b, dup, none]}))
    assert [d.severity_score for d in r.detections] == [7.6, 5.2]
    assert r.severity_score == 7.6 and r.estimated_repair_time_hours == 6
    assert [d.urgency_level for d in r.detections] == ["HIGH", "MEDIUM"]


def test_single_object_answer_still_works_and_all_none_stays_none():
    from app.inspector import parse_inspection
    import json
    from tests.conftest import make_result
    one = parse_inspection(json.dumps(make_result()))
    assert one.hazard_type == "Pothole" and len(one.detections) == 1
    clean = parse_inspection(json.dumps({"detections": [make_result(hazard="None", severity=1.2, box=(0, 0, 0, 0))]}))
    assert clean.hazard_type == "None" and clean.detections == []
