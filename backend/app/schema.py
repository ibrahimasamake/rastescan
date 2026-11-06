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


MAX_DETECTIONS = 8


def _area(b: BoundingBox) -> int:
    return max(0, b.xmax - b.xmin) * max(0, b.ymax - b.ymin)


def _overlap(a: BoundingBox, b: BoundingBox) -> int:
    w = min(a.xmax, b.xmax) - max(a.xmin, b.xmin)
    h = min(a.ymax, b.ymax) - max(a.ymin, b.ymin)
    return w * h if w > 0 and h > 0 else 0


def _iou(a: BoundingBox, b: BoundingBox) -> float:
    inter = _overlap(a, b)
    union = _area(a) + _area(b) - inter
    return inter / union if union else 0.0


def _sane(d: Detection) -> bool:
    """A box that covers over 40% of the photo, or is a speck, is the model guessing, not a located defect."""
    share = _area(d.bounding_box) / 1_000_000
    return 0.0004 <= share <= 0.4


def _repeat(d: Detection, k: Detection) -> bool:
    """Same kind of defect, and the boxes mostly cover the same spot (IoU above 0.4, or one sits inside the other)."""
    if k.hazard_type != d.hazard_type:
        return False
    inter = _overlap(k.bounding_box, d.bounding_box)
    small = min(_area(k.bounding_box), _area(d.bounding_box))
    return _iou(k.bounding_box, d.bounding_box) > 0.4 or (small > 0 and inter / small > 0.8)


def _plain(d: Detection) -> Detection:
    """One defect as a plain Detection, even if it arrived as a whole Inspection result."""
    if type(d) is Detection:
        return d
    return Detection.model_validate(d.model_dump(exclude={"detections"}))


def combine(items: list[Detection]) -> Inspection:
    """Merge the model's list of defects into one report result.

    Drops "None" entries, boxes that cannot be right (huge or tiny), and repeats of the same spot; recomputes each urgency
    from its score; keeps the 8 worst; headlines the worst; and adds up the repair time (one crew visit fixes them all)."""
    items = [_plain(d) for d in items]
    real = sorted((d for d in items if d.hazard_type != "None"), key=lambda d: -d.severity_score)
    kept: list[Detection] = []
    for d in real:
        if _sane(d) and not any(_repeat(d, k) for k in kept):
            kept.append(d)
    if not kept and real:
        kept = [real[0]]  # every box looked wrong, but something was found: keep the worst rather than say "no damage"
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
