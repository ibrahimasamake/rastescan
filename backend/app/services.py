"""Report logic shared by the citizen, public and officer routes.

Everything that changes a report goes through here so the audit trail (status_history) is never skipped,
and everything that leaves the server through public_* functions so private fields never leak.
"""
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from . import triage
from .config import Settings
from .db import Database
from .inspector import Inspector, InspectionError, InspectorBusy
from .ratelimit import RateLimiter
from .schema import Inspection, needs_human_review, urgency_for
from .storage import LocalStorage
from .wards import Ward, ward_for

log = logging.getLogger("rastescan")

# Internal status -> what the public sees. "review" and "no_damage" are never published.
PUBLIC_STATUS = {
    "new": "ai_verified",
    "assigned": "assigned",
    "fixed": "repair_done",
    "verified": "resolved",
    "dismissed": "dismissed",
}
PUBLIC_INTERNAL = tuple(PUBLIC_STATUS)
OPEN = ("new", "assigned", "fixed")
OFFICER_STATUSES = ("new", "assigned", "fixed", "verified", "dismissed")
AI = "AI inspector"
CITIZEN = "Citizen"
SYSTEM = "System"

# Shown while a report waits for a person because the AI was busy.
PENDING_RESULT = {
    "hazard_type": "None", "confidence": 0.0, "severity_score": 1.0, "urgency_level": "LOW",
    "repair_recommendation": "Waiting for a ward engineer to check this photo.",
    "estimated_repair_time_hours": 0, "estimated_dimensions": {"width_cm": 0, "depth_category": "Shallow"},
    "bounding_box": {"ymin": 0, "xmin": 0, "ymax": 0, "xmax": 0},
}

COUNTS_SQL = """
SELECT r.*,
  (SELECT COUNT(*) FROM reports c WHERE c.parent_id = r.id) AS dup_count,
  (SELECT COUNT(*) FROM votes v WHERE v.report_id = r.id) AS vote_count
FROM reports r
"""


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


def parse_iso(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


@dataclass
class Ctx:
    settings: Settings
    db: Database
    storage: object
    inspector: Inspector
    wards: list[Ward]
    secret: str
    limiter: RateLimiter
    login_limiter: RateLimiter
    ward_names: dict[str, str] = field(default_factory=dict)

    @property
    def model_tag(self) -> str:
        # The prompt is part of the key, so changing it (e.g. to find every defect) never serves older cached answers.
        prompt = getattr(self.inspector, "prompt", "")
        return f"{self.inspector.mode}:{getattr(self.inspector, 'model', '')}:{hashlib.sha256(prompt.encode()).hexdigest()[:8]}"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.settings.timezone)


# ---------- history ----------
def record(ctx: Ctx, report_id: int, event: str, actor: str, *, officer_id: int | None = None,
           old: str | None = None, new: str | None = None, detail: dict | None = None,
           public: bool = True, at: datetime | None = None) -> None:
    ctx.db.insert("status_history", {
        "report_id": report_id, "at": iso(at or now()), "event": event, "actor": actor, "officer_id": officer_id,
        "old_value": old, "new_value": new, "detail": json.dumps(detail) if detail else None, "public": int(public),
    })


# ---------- AI ----------
def inspect(ctx: Ctx, jpeg: bytes, inspector: Inspector | None = None) -> Inspection:
    """Cached by photo hash so the same photo never costs a second model call."""
    sha = hashlib.sha256(jpeg).hexdigest()
    hit = ctx.db.cached(sha, ctx.model_tag)
    if hit:
        return Inspection.model_validate_json(hit)
    try:
        result = (inspector or ctx.inspector).inspect(jpeg)
    except (InspectionError, InspectorBusy):
        raise
    except Exception as exc:  # network, permissions, provider outage
        log.exception("inspection failed")
        raise HTTPException(503, "The AI inspector is not reachable right now. Try again in a moment.") from exc
    ctx.db.cache(sha, ctx.model_tag, result.model_dump_json())
    return result


def store_photo(ctx: Ctx, jpeg: bytes) -> str:
    key = f"{uuid.uuid4().hex}.jpg"
    ctx.storage.save(key, jpeg)
    return key


def photo_url(ctx: Ctx, key: str | None) -> str | None:
    return ctx.storage.url(key) if key else None


# ---------- reads ----------
def row_by_code(ctx: Ctx, code: str) -> dict:
    row = ctx.db.one(COUNTS_SQL + " WHERE r.code = ?", (code.upper(),))
    if not row:
        raise HTTPException(404, f"No report with code {code}.")
    return row


def row_by_id(ctx: Ctx, rid: int) -> dict:
    return ctx.db.one(COUNTS_SQL + " WHERE r.id = ?", (rid,))


def reported_count(row: dict) -> int:
    return 1 + (row.get("dup_count") or 0) + (row.get("vote_count") or 0)


def is_overdue(row: dict, at: datetime | None = None) -> bool:
    due = parse_iso(row.get("due_at"))
    return row["status"] in OPEN and due is not None and due < (at or now())


def ward_info(ctx: Ctx, code: str | None) -> dict | None:
    return {"code": code, "name": ctx.ward_names.get(code, code)} if code else None


def public_item(ctx: Ctx, row: dict) -> dict:
    """The only shape that leaves the server for anonymous readers. No device id, contact, note or officer email."""
    result = json.loads(row["ai_json"])
    return {
        "code": row["code"],
        "lat": row["lat"],
        "lng": row["lng"],
        "ward": ward_info(ctx, row.get("ward_code")),
        "hazard_type": row["hazard_type"],
        "severity": row["severity"],
        "urgency": row["urgency"],
        "status": row["status"],
        "public_status": PUBLIC_STATUS.get(row["status"], "reported"),
        "photo_url": photo_url(ctx, row["photo_key"]),
        "after_photo_url": photo_url(ctx, row.get("after_photo_key")),
        "repair_recommendation": result.get("repair_recommendation"),
        "estimated_repair_time_hours": result.get("estimated_repair_time_hours"),
        "reported_count": reported_count(row),
        "assignee": row.get("assignee"),
        "created_at": row["created_at"],
        "due_at": row["due_at"],
        "resolved_at": row.get("resolved_at"),
        "updated_at": row["updated_at"],
        "overdue": is_overdue(row),
        "is_demo": bool(row.get("is_demo")),
    }


def public_timeline(ctx: Ctx, report_id: int) -> list[dict]:
    events = [{
        "at": h["at"], "event": h["event"], "actor": h["actor"],
        "old_value": h["old_value"], "new_value": h["new_value"],
        "detail": json.loads(h["detail"]) if h["detail"] else None,
    } for h in ctx.db.query(
        "SELECT * FROM status_history WHERE report_id = ? AND public = 1 ORDER BY at, id", (report_id,))]
    comments = [{"at": c["created_at"], "event": "comment", "actor": c["author"], "old_value": None,
                 "new_value": None, "detail": {"text": c["body"]}}
                for c in ctx.db.query("SELECT * FROM comments WHERE report_id = ? ORDER BY created_at", (report_id,))]
    return sorted(events + comments, key=lambda e: e["at"])


def public_detail(ctx: Ctx, row: dict) -> dict:
    item = public_item(ctx, row)
    item["result"] = json.loads(row["ai_json"])
    item["after_result"] = json.loads(row["after_ai_json"]) if row.get("after_ai_json") else None
    item["confidence"] = row["confidence"]
    item["dismiss_reason"] = row.get("dismiss_reason")
    parent = ctx.db.one("SELECT code FROM reports WHERE id = ?", (row["parent_id"],)) if row.get("parent_id") else None
    item["merged_into"] = parent["code"] if parent else None
    item["timeline"] = public_timeline(ctx, row["id"])
    return item


def full_item(ctx: Ctx, row: dict) -> dict:
    """For the citizen who sent it and for officers: the public shape plus fields the old app used."""
    item = public_detail(ctx, row)
    item.update({
        "model_urgency": row["model_urgency"],
        "needs_review": bool(row["needs_review"]),
        "ai_pending": bool(row.get("ai_pending")),
        "merged_count": reported_count(row),
        "note": row.get("note"),
        "has_contact": bool(row.get("contact_email")),
    })
    return item


def citizen_item(ctx: Ctx, row: dict) -> dict:
    item = full_item(ctx, row)
    item.pop("has_contact")
    return item


# ---------- writes ----------
def set_status(ctx: Ctx, row: dict, status: str, actor: str, officer_id: int | None = None,
               detail: dict | None = None, event: str = "status") -> None:
    ts = now()
    resolved = iso(ts) if status == "verified" else None
    ctx.db.execute(
        "UPDATE reports SET status = ?, updated_at = ?, resolved_at = CASE WHEN ? IS NULL THEN NULL ELSE ? END "
        "WHERE id = ? OR parent_id = ?",
        (status, iso(ts), resolved, resolved, row["id"], row["id"]))
    record(ctx, row["id"], event, actor, officer_id=officer_id, old=row["status"], new=status, detail=detail, at=ts)


def create_report(ctx: Ctx, jpeg: bytes, lat: float | None, lng: float | None, device_id: str | None,
                  note: str | None = None, contact_email: str | None = None, is_demo: bool = False,
                  created: datetime | None = None, result: Inspection | None = None) -> dict:
    created = created or now()
    pending = False
    if result is None:
        try:
            result = inspect(ctx, jpeg)
        except InspectorBusy as exc:
            log.warning("AI busy, report saved for review: %s", exc)
            pending = True
            result = Inspection.model_validate(PENDING_RESULT)
        except InspectionError as exc:
            log.warning("model answer rejected: %s", exc)
            raise HTTPException(502, "The AI inspector gave an answer we could not use. Try again in a moment.") from exc

    urgency = urgency_for(result)
    review = pending or needs_human_review(result)
    if pending or (result.hazard_type == "None" and review):
        status = "review"  # possible screenshot or unclear photo: a person decides, nothing is published
    elif result.hazard_type == "None":
        status = "no_damage"
    else:
        status = "review" if review else "new"

    parent_id = None
    if status == "new":
        open_rows = ctx.db.query(
            "SELECT id, lat, lng, hazard_type FROM reports WHERE parent_id IS NULL AND status IN (?, ?)", ("new", "assigned"))
        dup = triage.find_duplicate(open_rows, lat, lng, result.hazard_type, ctx.settings.merge_radius_m)
        parent_id = dup["id"] if dup else None

    ward = ward_for(ctx.wards, lat, lng)
    rid = ctx.db.insert_report({
        "lat": lat, "lng": lng,
        "photo_key": store_photo(ctx, jpeg),
        "ai_json": result.model_dump_json(),
        "hazard_type": result.hazard_type,
        "severity": result.severity_score,
        "urgency": urgency,
        "model_urgency": result.urgency_level,
        "confidence": result.confidence,
        "needs_review": int(review),
        "ai_pending": int(pending),
        "parent_id": parent_id,
        "status": status,
        "device_id": device_id,
        "note": (note or "").strip()[:280] or None,
        "contact_email": (contact_email or "").strip()[:200] or None,
        "ward_code": ward.code if ward else None,
        "is_demo": int(is_demo),
        "created_at": iso(created),
        "due_at": iso(triage.due_at(created, urgency)) if status not in ("no_damage",) else None,
        "updated_at": iso(created),
    })
    record(ctx, rid, "reported", CITIZEN, new="review" if status == "review" else "reported", at=created)
    if pending:
        record(ctx, rid, "review_needed", SYSTEM, detail={"reason": "ai_busy"}, at=created)
    else:
        record(ctx, rid, "ai_assessed", AI, new=urgency, at=created, detail={
            "hazard_type": result.hazard_type, "severity": result.severity_score, "urgency": urgency,
            "model_urgency": result.urgency_level, "confidence": result.confidence,
        }, public=status != "no_damage")
        if status == "review":
            record(ctx, rid, "review_needed", AI, detail={"reason": "low_confidence"}, at=created, public=False)

    if parent_id:
        _raise_parent_priority(ctx, parent_id, urgency, result.severity_score, created)
        record(ctx, parent_id, "duplicate_added", CITIZEN, detail={"code": f"RS-{rid:04d}"}, at=created)
    return row_by_id(ctx, rid)


def rescan(ctx: Ctx, row: dict, inspector: Inspector | None = None) -> dict:
    """Ask the AI again about a stored photo whose first scan was refused or unclear. Raises like inspect() does."""
    result = inspect(ctx, ctx.storage.load(row["photo_key"]), inspector)
    urgency = urgency_for(result)
    review = needs_human_review(result)
    status = "review" if review else "no_damage" if result.hazard_type == "None" else "new"
    ts = iso(now())
    due = iso(triage.due_at(parse_iso(row["created_at"]), urgency)) if status != "no_damage" else None
    ctx.db.execute(
        "UPDATE reports SET ai_json = ?, hazard_type = ?, severity = ?, urgency = ?, model_urgency = ?, confidence = ?, "
        "needs_review = ?, ai_pending = 0, status = ?, due_at = ?, updated_at = ? WHERE id = ?",
        (result.model_dump_json(), result.hazard_type, result.severity_score, urgency, result.urgency_level,
         result.confidence, int(review), status, due, ts, row["id"]))
    record(ctx, row["id"], "ai_assessed", AI, new=urgency, detail={
        "hazard_type": result.hazard_type, "severity": result.severity_score, "urgency": urgency,
        "model_urgency": result.urgency_level, "confidence": result.confidence}, public=status != "no_damage")
    return row_by_id(ctx, row["id"])


def process_pending(ctx: Ctx) -> int:
    """Scan, oldest first, reports that were saved without an AI answer. Returns how many were finished.

    A slow model and a busy free tier both end up here: the citizen's report is saved at once
    and this fills in the answer. It stops at the first failure so a down or limited provider is not hammered.
    """
    patient = getattr(ctx.inspector, "patient", None)
    inspector = patient() if patient else None
    done = 0
    for row in ctx.db.query("SELECT * FROM reports WHERE status = 'review' AND ai_pending = 1 ORDER BY id LIMIT 20"):
        try:
            rescan(ctx, row, inspector)
            done += 1
        except Exception as exc:  # noqa: BLE001 - busy, down or unusable answer: try again next round
            log.warning("pending scan of %s postponed: %s", row["code"], exc)
            break
    return done


def _raise_parent_priority(ctx: Ctx, parent_id: int, urgency: str, severity: float, at: datetime) -> None:
    """A repeat report can raise the parent ticket's priority but never lower it."""
    parent = ctx.db.one("SELECT * FROM reports WHERE id = ?", (parent_id,))
    if triage.URGENCY_RANK[urgency] > triage.URGENCY_RANK[parent["urgency"]] or severity > parent["severity"]:
        new_urg = max(urgency, parent["urgency"], key=triage.URGENCY_RANK.get)
        ctx.db.execute(
            "UPDATE reports SET urgency = ?, severity = MAX(severity, ?), due_at = MIN(due_at, ?), updated_at = ? WHERE id = ?",
            (new_urg, severity, iso(triage.due_at(at, new_urg)), iso(at), parent_id))
        if new_urg != parent["urgency"]:
            record(ctx, parent_id, "priority_raised", SYSTEM, old=parent["urgency"], new=new_urg, at=at)


def device_hash(ctx: Ctx, device_id: str) -> str:
    return hashlib.sha256((ctx.secret + ":" + device_id).encode()).hexdigest()


def add_vote(ctx: Ctx, row: dict, device_id: str) -> bool:
    """One "I see this too" per device per report. Returns False if this device already voted."""
    target = row_by_id(ctx, row["parent_id"]) if row.get("parent_id") else row
    h = device_hash(ctx, device_id)
    if row.get("device_id") == device_id or ctx.db.one(
            "SELECT 1 FROM votes WHERE report_id = ? AND device_hash = ?", (target["id"], h)):
        return False
    ctx.db.insert("votes", {"report_id": target["id"], "device_hash": h, "created_at": iso(now())})
    return True


# ---------- stats ----------
def _local_day_start(ctx: Ctx, at: datetime) -> datetime:
    local = at.astimezone(ctx.tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


def stats(ctx: Ctx) -> dict:
    t = now()
    today = iso(_local_day_start(ctx, t))
    local = t.astimezone(ctx.tz)
    month = iso(local.replace(day=1, hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc))
    marks = ",".join("?" for _ in PUBLIC_INTERNAL)
    pub = f"parent_id IS NULL AND status IN ({marks})"
    db = ctx.db
    fixes = db.query(f"SELECT created_at, resolved_at FROM reports WHERE status = 'verified' AND parent_id IS NULL "
                     f"AND resolved_at >= ?", (iso(t - timedelta(days=90)),))
    days = [(parse_iso(f["resolved_at"]) - parse_iso(f["created_at"])).total_seconds() / 86400 for f in fixes]
    open_rows = db.query(f"SELECT due_at, status FROM reports WHERE parent_id IS NULL AND status IN ('new','assigned','fixed')")
    return {
        "reported_today": db.scalar(f"SELECT COUNT(*) FROM reports WHERE created_at >= ? AND status != 'no_damage'", (today,)),
        "open_now": len(open_rows),
        "overdue_now": sum(1 for r in open_rows if is_overdue(r, t)),
        "resolved_this_month": db.scalar("SELECT COUNT(*) FROM reports WHERE status = 'verified' AND parent_id IS NULL "
                                         "AND resolved_at >= ?", (month,)),
        "avg_days_to_fix": round(sum(days) / len(days), 1) if days else None,
        "total_public": db.scalar(f"SELECT COUNT(*) FROM reports WHERE {pub}", PUBLIC_INTERNAL),
        "demo_count": db.scalar("SELECT COUNT(*) FROM reports WHERE is_demo = 1"),
        "last_updated": db.scalar("SELECT MAX(updated_at) FROM reports"),
        "ai_mode": ctx.inspector.mode,
    }


def ward_scoreboard(ctx: Ctx) -> list[dict]:
    t = now()
    rows = ctx.db.query("SELECT ward_code, status, created_at, due_at, resolved_at FROM reports "
                        "WHERE parent_id IS NULL AND status IN ('new','assigned','fixed','verified','dismissed')")
    board = []
    for w in ctx.wards:
        mine = [r for r in rows if r["ward_code"] == w.code]
        open_rows = [r for r in mine if r["status"] in OPEN]
        resolved = [r for r in mine if r["status"] == "verified" and r["resolved_at"]]
        hours = [(parse_iso(r["resolved_at"]) - parse_iso(r["created_at"])).total_seconds() / 3600 for r in resolved]
        on_time = [r for r in resolved if r["due_at"] and r["resolved_at"] <= r["due_at"]]
        lat, lng = w.centroid
        board.append({
            "code": w.code, "name": w.name, "lat": lat, "lng": lng,
            "open": len(open_rows),
            "overdue": sum(1 for r in open_rows if is_overdue(r, t)),
            "resolved": len(resolved),
            "avg_days_to_resolve": round(sum(hours) / len(hours) / 24, 1) if hours else None,
            "pct_within_deadline": round(100 * len(on_time) / len(resolved)) if resolved else None,
        })
    board.sort(key=lambda b: (b["pct_within_deadline"] is None, -(b["pct_within_deadline"] or 0),
                              b["avg_days_to_resolve"] if b["avg_days_to_resolve"] is not None else 1e9, b["overdue"]))
    for rank, b in enumerate(board, start=1):
        b["rank"] = rank
    return board
