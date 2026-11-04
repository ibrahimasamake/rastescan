"""Inspection result schema. Mirrors prompts/inspection-prompt.md; the server, not the model, decides urgency."""
from typing import Literal
from pydantic import BaseModel, Field, model_validator

HazardType = Literal["Pothole", "Open Manhole", "Road Fissure", "Waterlogging", "Debris", "Slab Displacement", "None"]
Urgency = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]


class Dimensions(BaseModel):
    width_cm: int = Field(ge=0)
    depth_category: Literal["Shallow", "Moderate", "Deep", "Sub-base Breach"]


class BoundingBox(BaseModel):
    ymin: int = Field(ge=0, le=1000)
    xmin: int = Field(ge=0, le=1000)
    ymax: int = Field(ge=0, le=1000)
    xmax: int = Field(ge=0, le=1000)


class Detection(BaseModel):
    """One defect in a photo."""


    hazard_type: HazardType
    confidence: float = Field(ge=0, le=1)
    severity_score: float = Field(ge=1, le=10)
    urgency_level: Urgency
    repair_recommendation: str
    estimated_repair_time_hours: int = Field(ge=0)
    estimated_dimensions: Dimensions
    bounding_box: BoundingBox

    @model_validator(mode="after")
    def check_box(self):
        b = self.bounding_box
        if self.hazard_type != "None" and not (b.ymin < b.ymax and b.xmin < b.xmax):
            raise ValueError("bounding box is empty or inverted")
        return self


class Inspection(Detection):
    """The report headline (the worst defect in the photo) plus every defect found, worst first."""

    detections: list[Detection] = Field(default_factory=list)


MAX_DETECTIONS = 12


def _iou(a: BoundingBox, b: BoundingBox) -> float:
    w = min(a.xmax, b.xmax) - max(a.xmin, b.xmin)
    h = min(a.ymax, b.ymax) - max(a.ymin, b.ymin)
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    union = (a.xmax - a.xmin) * (a.ymax - a.ymin) + (b.xmax - b.xmin) * (b.ymax - b.ymin) - inter
    return inter / union if union else 0.0


def combine(items: list[Detection]) -> Inspection:
    """Merge the model's list of defects: drop "None" entries and repeats of the same box, recompute each urgency
    from its score, headline the worst defect, and add up the repair time (one crew visit fixes them all)."""
    real = sorted((d for d in items if d.hazard_type != "None"), key=lambda d: -d.severity_score)
    kept: list[Detection] = []
    for d in real:
        if not any(k.hazard_type == d.hazard_type and _iou(k.bounding_box, d.bounding_box) > 0.6 for k in kept):
            kept.append(d)
    kept = kept[:MAX_DETECTIONS]
    if not kept:
        return Inspection(**items[0].model_dump())
    kept = [d.model_copy(update={"urgency_level": urgency_for(d)}) for d in kept]
    head = kept[0].model_dump()
    head["estimated_repair_time_hours"] = sum(d.estimated_repair_time_hours for d in kept)
    return Inspection(**head, detections=kept)


def urgency_for(result: Detection) -> Urgency:
    """Recompute urgency from the score bands; an open manhole is always CRITICAL."""
    if result.hazard_type == "Open Manhole":
        return "CRITICAL"
    s = result.severity_score
    if s >= 9.0:
        return "CRITICAL"
    if s >= 7.0:
        return "HIGH"
    if s >= 4.0:
        return "MEDIUM"
    return "LOW"


def needs_human_review(result: Detection) -> bool:
    return result.confidence < 0.6
