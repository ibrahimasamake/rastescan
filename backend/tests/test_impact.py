from app import costing
from app.schema import Inspection

from .conftest import make_result, submit


def inspection(**kw) -> Inspection:
    return Inspection.model_validate(make_result(**kw))


def test_pothole_cost_has_asphalt_and_labour():
    est = costing.estimate(inspection())
    assert est["lines"][0]["item"] == "Hot-mix asphalt"
    assert est["labour_inr"] == 3 * costing.CREW_INR_PER_HOUR
    assert est["total_inr"] == est["materials_inr"] + est["labour_inr"] > 0
    assert est["indicative"] is True


def test_open_manhole_costs_cover_and_barricade():
    est = costing.estimate(inspection(hazard="Open Manhole", severity=9.6, urgency="CRITICAL"))
    assert {x["item"] for x in est["lines"]} == {"Heavy-duty cover and frame", "Barricade and signage"}
    assert est["materials_inr"] == costing.MANHOLE_COVER_INR + costing.BARRICADE_INR


def test_deeper_pothole_costs_more():
    shallow = make_result()
    shallow["estimated_dimensions"] = {"width_cm": 60, "depth_category": "Shallow"}
    deep = make_result()
    deep["estimated_dimensions"] = {"width_cm": 60, "depth_category": "Sub-base Breach"}
    assert costing.estimate(Inspection.model_validate(deep))["materials_inr"] > costing.estimate(Inspection.model_validate(shallow))["materials_inr"]


def test_no_damage_costs_nothing():
    est = costing.estimate(inspection(hazard="None", severity=1.0, urgency="LOW", box=(0, 0, 0, 0)))
    assert est["total_inr"] == 0 and est["lines"] == []


def test_public_detail_carries_estimate(client):
    code = submit(client)["code"]
    body = client.get(f"/api/public/reports/{code}").json()
    assert body["repair_estimate"]["total_inr"] > 0


def test_impact_counts_open_backlog(client):
    assert client.get("/api/public/impact").json()["tickets"] == 0
    submit(client, seed=1, lat=13.05, lng=77.63)
    submit(client, seed=2, lat=13.07, lng=77.65)
    body = client.get("/api/public/impact?days=7").json()
    assert body["tickets"] == 2 and body["open"] == 2 and body["fixed"] == 0
    assert body["open_backlog_inr"] > 0
    assert len(body["trend"]) == 7 and sum(d["reported"] for d in body["trend"]) == 2
    assert body["by_hazard"][0][0] == "Pothole"


def test_activity_feed_is_public_only(client):
    code = submit(client)["code"]
    items = client.get("/api/public/activity").json()
    assert items and all(i["code"] == code for i in items)
    text = str(items)
    assert "dev-1" not in text and "device" not in text
    assert {"reported", "ai_assessed"} <= {i["event"] for i in items}
