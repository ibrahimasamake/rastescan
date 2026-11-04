"""Deadlines, duplicate merging and queue order."""
import math
from datetime import datetime, timedelta

SLA_HOURS = {"LOW": 24 * 90, "MEDIUM": 24 * 7, "HIGH": 48, "CRITICAL": 24}
URGENCY_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
OPEN_STATUSES = ("new", "assigned")


def due_at(created: datetime, urgency: str) -> datetime:
    return created + timedelta(hours=SLA_HOURS[urgency])


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def find_duplicate(candidates: list[dict], lat: float | None, lng: float | None, hazard: str, radius_m: float) -> dict | None:
    """Nearest open ticket of the same hazard type within radius_m, or None."""
    if lat is None or lng is None or hazard == "None":
        return None
    best, best_d = None, radius_m
    for c in candidates:
        if c["hazard_type"] != hazard or c["lat"] is None or c["lng"] is None:
            continue
        d = distance_m(lat, lng, c["lat"], c["lng"])
        if d <= best_d:
            best, best_d = c, d
    return best


def queue_key(ticket: dict):
    """Urgency, then severity, then number of merged reports, then oldest first."""
    return (-URGENCY_RANK[ticket["urgency"]], -ticket["severity"], -ticket["merged_count"], ticket["created_at"])
