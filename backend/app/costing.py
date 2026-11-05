"""Indicative repair cost and materials for a defect, in Indian rupees.

Worked out by the server from the AI's measured size and depth, never by the model. The unit rates are rough
Indian municipal figures kept in one table so a city can replace them with its own schedule of rates.
These are budgeting estimates, not tenders.
"""
from .schema import Detection, Inspection

# Hot-mix asphalt, laid cost per tonne, and compacted density (tonnes per cubic metre).
ASPHALT_INR_PER_TONNE = 7500
ASPHALT_T_PER_M3 = 2.4
WASTAGE = 1.15
CREW_INR_PER_HOUR = 1200  # a three-person crew with a roller and a tipper
DEPTH_CM = {"Shallow": 3, "Moderate": 6, "Deep": 10, "Sub-base Breach": 20}
SEALANT_INR_PER_M = 180
MANHOLE_COVER_INR = 6500
BARRICADE_INR = 800
SLAB_INR_PER_M2 = 3500
DRAIN_CLEARING_INR = 2500
DEBRIS_REMOVAL_INR = 800


def _line(item: str, qty: float, unit: str, cost: float) -> dict:
    return {"item": item, "qty": round(qty, 2), "unit": unit, "cost_inr": round(cost)}


def estimate_defect(d: Detection) -> dict:
    """Materials, labour and total for one defect."""
    width_m = max(d.estimated_dimensions.width_cm, 10) / 100
    hours = d.estimated_repair_time_hours
    mats: list[dict] = []
    kind = d.hazard_type
    if kind == "Pothole":
        area = width_m * width_m * 0.8  # a pothole is roughly a rounded patch, not a full square
        tonnes = area * DEPTH_CM[d.estimated_dimensions.depth_category] / 100 * ASPHALT_T_PER_M3 * WASTAGE
        mats.append(_line("Hot-mix asphalt", tonnes, "tonne", tonnes * ASPHALT_INR_PER_TONNE))
    elif kind == "Road Fissure":
        mats.append(_line("Bitumen crack sealant", width_m, "m", width_m * SEALANT_INR_PER_M))  # width_cm is the crack's length
    elif kind == "Open Manhole":
        mats.append(_line("Heavy-duty cover and frame", 1, "set", MANHOLE_COVER_INR))
        mats.append(_line("Barricade and signage", 1, "set", BARRICADE_INR))
    elif kind == "Slab Displacement":
        area = width_m * width_m
        mats.append(_line("Re-laid concrete slab", area, "m²", area * SLAB_INR_PER_M2))
    elif kind == "Waterlogging":
        mats.append(_line("Drain clearing and flushing", 1, "job", DRAIN_CLEARING_INR))
    elif kind == "Debris":
        mats.append(_line("Debris removal", 1, "job", DEBRIS_REMOVAL_INR))
    labour = hours * CREW_INR_PER_HOUR
    total = sum(m["cost_inr"] for m in mats) + labour
    return {"hazard_type": kind, "materials": mats, "labour_inr": round(labour), "crew_hours": hours, "total_inr": round(total)}


def estimate(result: Inspection) -> dict:
    """The whole report: one crew visit fixes every defect, so labour is counted once for the visit."""
    defects = result.detections or ([result] if result.hazard_type != "None" else [])
    if not defects:
        return {"total_inr": 0, "materials_inr": 0, "labour_inr": 0, "crew_hours": 0, "lines": [], "indicative": True}
    parts = [estimate_defect(d) for d in defects]
    lines: list[dict] = []
    for p in parts:
        for m in p["materials"]:
            existing = next((x for x in lines if x["item"] == m["item"] and x["unit"] == m["unit"]), None)
            if existing:
                existing["qty"] = round(existing["qty"] + m["qty"], 2)
                existing["cost_inr"] += m["cost_inr"]
            else:
                lines.append(dict(m))
    materials = sum(x["cost_inr"] for x in lines)
    hours = sum(p["crew_hours"] for p in parts)
    labour = round(hours * CREW_INR_PER_HOUR)
    return {"total_inr": materials + labour, "materials_inr": materials, "labour_inr": labour,
            "crew_hours": hours, "lines": lines, "indicative": True}
