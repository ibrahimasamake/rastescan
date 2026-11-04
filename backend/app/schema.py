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


class Inspection(BaseModel):
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


def urgency_for(result: Inspection) -> Urgency:
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


def needs_human_review(result: Inspection) -> bool:
    return result.confidence < 0.6
