"""Government side: sign-in, the work queue, actions on tickets, analytics and crew work orders.

Every change is written to status_history with the officer's name, which is what the public timeline shows.
The shared DASHBOARD_PIN still works (X-Dashboard-Pin header) as an expo fallback and acts as "Duty officer".
"""
import json
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field

from . import auth, imaging, notify, triage
from . import services as svc
from .http import client_ip, get_ctx, no_store, read_photo
from .inspector import InspectionError, InspectorBusy
from .routes_public import filtered_rows
from .schema import HazardType, Inspection, urgency_for
from .services import Ctx

router = APIRouter(tags=["officer"])

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "RasteScan"


# ---------- who is calling ----------
def current_officer(request: Request, ctx: Ctx = Depends(get_ctx)) -> auth.Officer | None:
    if auth.pin_matches(ctx.settings.dashboard_pin, request.headers.get("x-dashboard-pin")):
        return auth.Officer(None, "Duty officer", "admin")
    header = request.headers.get("authorization", "")
    from_cookie = False
    if header.lower().startswith("bearer "):
        token = header[7:].strip()
    else:
        token = request.cookies.get(auth.COOKIE)
        from_cookie = True
    if not token:
        return None
    officer_id = auth.read_token(ctx.secret, token)
    row = ctx.db.one("SELECT * FROM officers WHERE id = ? AND active = 1", (officer_id,)) if officer_id else None
    if not row:
        return None
    # Cookies ride along with cross-site requests; a custom header cannot, so it proves the call came from our pages.
    if from_cookie and request.method not in ("GET", "HEAD") and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise HTTPException(403, "Missing request header. Reload the page and try again.")
    return auth.Officer(row["id"], row["name"], row["role"])


def require_officer(officer: auth.Officer | None = Depends(current_officer)) -> auth.Officer:
    if officer is None:
        raise HTTPException(401, "Sign in as an officer to do this.")
    return officer


def require_admin(officer: auth.Officer = Depends(require_officer)) -> auth.Officer:
    if not officer.is_admin:
        raise HTTPException(403, "Only an administrator can do this.")
    return officer


# ---------- sign in ----------
class Login(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=200)


def _secure_request(ctx: Ctx, request: Request) -> bool:
    proto = request.headers.get("cloudfront-forwarded-proto") or request.headers.get("x-forwarded-proto") or request.url.scheme
    return ctx.settings.cookie_secure and proto == "https"


@router.post("/api/v2/auth/login")
def login(body: Login, request: Request, response: Response, ctx: Ctx = Depends(get_ctx)):
    if not ctx.login_limiter.allow("login:" + client_ip(request)):
        raise HTTPException(429, "Too many sign-in attempts. Wait 15 minutes and try again.")
    row = ctx.db.one("SELECT * FROM officers WHERE email = ? AND active = 1", (body.email.strip().lower(),))
    if not auth.check_password(row["password_hash"] if row else None, body.password):
        raise HTTPException(401, "Email or password is not correct.")
    token = auth.issue_token(ctx.secret, row["id"], ctx.settings.session_hours)
    response.set_cookie(auth.COOKIE, token, max_age=ctx.settings.session_hours * 3600, httponly=True,
                        samesite="lax", secure=_secure_request(ctx, request), path="/")
    return {"name": row["name"], "role": row["role"], "token": token}


@router.post("/api/v2/auth/logout")
def logout(response: Response):
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@router.get("/api/v2/auth/me")
def me(officer: auth.Officer | None = Depends(current_officer)):
    if officer is None:
        return no_store({"signed_in": False})
    return no_store({"signed_in": True, "name": officer.name, "role": officer.role})


# ---------- queue ----------
def _queue_rows(ctx: Ctx, statuses: tuple[str, ...]) -> list[dict]:
    marks = ",".join("?" for _ in statuses)
    return ctx.db.query(svc.COUNTS_SQL + f" WHERE r.parent_id IS NULL AND r.status IN ({marks})", statuses)


def queue_payload(ctx: Ctx, ward: str | None = None, q: str | None = None, urgency: str | None = None,
                  overdue: bool = False, include_fixed: bool = True) -> dict:
    statuses = ("new", "assigned", "fixed") if include_fixed else ("new", "assigned")
    tickets = [svc.full_item(ctx, r) for r in _queue_rows(ctx, statuses)]
    if ward:
        tickets = [t for t in tickets if (t["ward"] or {}).get("code") == ward]
    if urgency:
        tickets = [t for t in tickets if t["urgency"] in urgency.split(",")]
    if overdue:
        tickets = [t for t in tickets if t["overdue"]]
    if q:
        tickets = [t for t in tickets if q.strip().upper() in t["code"]]
    tickets.sort(key=triage.queue_key)
    review = [svc.full_item(ctx, r) for r in ctx.db.query(
        svc.COUNTS_SQL + " WHERE r.status = 'review' ORDER BY r.id DESC")]
    by_urgency = {u: 0 for u in triage.URGENCY_RANK}
    for t in tickets:
        if t["status"] != "fixed":
            by_urgency[t["urgency"]] += 1
    verified = ctx.db.scalar("SELECT COUNT(*) FROM reports WHERE status = 'verified' AND parent_id IS NULL")
    return {"tickets": tickets, "review": review, "counts": by_urgency, "verified": verified,
            "overdue": sum(1 for t in tickets if t["overdue"]), "ai_mode": ctx.inspector.mode}


@router.get("/api/v2/officer/queue")
def officer_queue(ward: str | None = None, q: str | None = None, urgency: str | None = None, overdue: bool = False,
                  _: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    return no_store(queue_payload(ctx, ward, q, urgency, overdue))


@router.get("/api/v2/officer/reports/{code}")
def officer_report(code: str, _: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    row = svc.row_by_code(ctx, code)
    item = svc.full_item(ctx, row)
    item["duplicates"] = [d["code"] for d in ctx.db.query("SELECT code FROM reports WHERE parent_id = ? ORDER BY id", (row["id"],))]
    item["history"] = [{**h, "detail": json.loads(h["detail"]) if h["detail"] else None} for h in ctx.db.query(
        "SELECT at, event, actor, old_value, new_value, detail, public FROM status_history WHERE report_id = ? ORDER BY at, id",
        (row["id"],))]
    return no_store(item)


@router.get("/api/v2/officer/assignees")
def assignees(_: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    names = {r["assignee"] for r in ctx.db.query("SELECT DISTINCT assignee FROM reports WHERE assignee IS NOT NULL")}
    names |= {r["name"] for r in ctx.db.query("SELECT name FROM officers WHERE active = 1")}
    return sorted(names)


# ---------- actions ----------
def _notify(ctx: Ctx, tasks: BackgroundTasks, row: dict, kind: str, **extra) -> None:
    rows = ctx.db.query("SELECT contact_email FROM reports WHERE (id = ? OR parent_id = ?) AND contact_email IS NOT NULL",
                        (row["id"], row["id"]))
    for r in rows:
        tasks.add_task(notify.send, ctx.settings, r["contact_email"], kind, code=row["code"],
                       hazard=row["hazard_type"], **extra)


class Assign(BaseModel):
    assignee: str = Field(min_length=2, max_length=80)


@router.post("/api/v2/officer/reports/{code}/assign")
def assign(code: str, body: Assign, tasks: BackgroundTasks, officer: auth.Officer = Depends(require_officer),
           ctx: Ctx = Depends(get_ctx)):
    row = svc.row_by_code(ctx, code)
    if row["status"] not in ("new", "assigned", "review", "fixed"):
        raise HTTPException(409, "Only open reports can be assigned.")
    name = body.assignee.strip()
    ctx.db.execute("UPDATE reports SET assignee = ?, updated_at = ? WHERE id = ? OR parent_id = ?",
                   (name, svc.iso(svc.now()), row["id"], row["id"]))
    svc.record(ctx, row["id"], "assigned", officer.name, officer_id=officer.id, old=row.get("assignee"), new=name)
    if row["status"] in ("new", "review"):
        svc.set_status(ctx, row, "assigned", officer.name, officer.id)
    _notify(ctx, tasks, row, "assigned", assignee=name)
    return svc.full_item(ctx, svc.row_by_code(ctx, code))


class StatusChange(BaseModel):
    status: Literal["new", "assigned", "fixed", "verified", "dismissed"]
    reason: str | None = Field(default=None, max_length=300)


def _change_status(ctx: Ctx, tasks: BackgroundTasks, row: dict, change: StatusChange, officer: auth.Officer) -> None:
    if change.status == "dismissed":
        if not (change.reason or "").strip():
            raise HTTPException(400, "Give a reason for dismissing. It is shown to the public.")
        ctx.db.execute("UPDATE reports SET dismiss_reason = ? WHERE id = ?", (change.reason.strip(), row["id"]))
    if row["status"] == "review" and change.status in ("new", "assigned"):
        ctx.db.execute("UPDATE reports SET needs_review = 0, ai_pending = 0 WHERE id = ?", (row["id"],))
    detail = {"reason": change.reason.strip()} if change.reason and change.reason.strip() else None
    svc.set_status(ctx, row, change.status, officer.name, officer.id, detail=detail)
    if change.status in ("verified", "dismissed"):
        _notify(ctx, tasks, row, change.status, reason=(change.reason or "").strip())


@router.post("/api/v2/officer/reports/{code}/status")
def change_status(code: str, change: StatusChange, tasks: BackgroundTasks,
                  officer: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    row = svc.row_by_code(ctx, code)
    _change_status(ctx, tasks, row, change, officer)
    return svc.full_item(ctx, svc.row_by_code(ctx, code))


class Bulk(BaseModel):
    codes: list[str] = Field(min_length=1, max_length=200)
    status: Literal["new", "assigned", "fixed", "verified", "dismissed"]
    reason: str | None = Field(default=None, max_length=300)


@router.post("/api/v2/officer/bulk-status")
def bulk_status(body: Bulk, tasks: BackgroundTasks, officer: auth.Officer = Depends(require_officer),
                ctx: Ctx = Depends(get_ctx)):
    rows = [svc.row_by_code(ctx, c) for c in body.codes]
    for row in rows:
        _change_status(ctx, tasks, row, StatusChange(status=body.status, reason=body.reason), officer)
    return {"updated": len(rows)}


class Comment(BaseModel):
    body: str = Field(min_length=2, max_length=1000)


@router.post("/api/v2/officer/reports/{code}/comment")
def comment(code: str, body: Comment, officer: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    row = svc.row_by_code(ctx, code)
    ctx.db.insert("comments", {"report_id": row["id"], "officer_id": officer.id, "author": officer.name,
                               "body": body.body.strip(), "created_at": svc.iso(svc.now())})
    ctx.db.execute("UPDATE reports SET updated_at = ? WHERE id = ?", (svc.iso(svc.now()), row["id"]))
    return svc.full_item(ctx, svc.row_by_code(ctx, code))


class Review(BaseModel):
    hazard_type: HazardType
    severity_score: float = Field(ge=1, le=10)


@router.post("/api/v2/officer/reports/{code}/review")
def review(code: str, body: Review, officer: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    """Officer confirms or corrects the AI. Corrections are counted in the AI accuracy figures."""
    row = svc.row_by_code(ctx, code)
    if body.hazard_type == "None":
        raise HTTPException(400, "To reject a photo with no damage, dismiss it with a reason instead.")
    result = json.loads(row["ai_json"])
    result.update(hazard_type=body.hazard_type, severity_score=body.severity_score)
    urgency = urgency_for(Inspection.model_validate(result))
    changed = body.hazard_type != row["hazard_type"] or abs(body.severity_score - row["severity"]) >= 0.5
    status = "new" if row["status"] == "review" else row["status"]
    ctx.db.execute(
        "UPDATE reports SET hazard_type = ?, severity = ?, urgency = ?, needs_review = 0, ai_pending = 0, status = ?, "
        "due_at = ?, updated_at = ? WHERE id = ?",
        (body.hazard_type, body.severity_score, urgency, status,
         svc.iso(triage.due_at(svc.parse_iso(row["created_at"]), urgency)), svc.iso(svc.now()), row["id"]))
    svc.record(ctx, row["id"], "confirmed", officer.name, officer_id=officer.id,
               old=f'{row["hazard_type"]}|{row["severity"]}', new=f"{body.hazard_type}|{body.severity_score}",
               detail={"hazard_type": body.hazard_type, "severity": body.severity_score, "urgency": urgency,
                       "ai_hazard_type": row["hazard_type"], "ai_severity": row["severity"],
                       "ai_pending": bool(row.get("ai_pending")), "changed": changed})
    return svc.full_item(ctx, svc.row_by_code(ctx, code))


class Merge(BaseModel):
    into: str


@router.post("/api/v2/officer/reports/{code}/merge")
def merge(code: str, body: Merge, officer: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    row, target = svc.row_by_code(ctx, code), svc.row_by_code(ctx, body.into)
    if target["parent_id"]:
        target = svc.row_by_id(ctx, target["parent_id"])
    if row["id"] == target["id"]:
        raise HTTPException(400, "A report cannot be merged into itself.")
    ts = svc.iso(svc.now())
    ctx.db.execute("UPDATE reports SET parent_id = ?, status = ?, updated_at = ? WHERE id = ? OR parent_id = ?",
                   (target["id"], target["status"], ts, row["id"], row["id"]))
    svc.record(ctx, row["id"], "merged", officer.name, officer_id=officer.id, new=target["code"])
    svc.record(ctx, target["id"], "duplicate_added", officer.name, officer_id=officer.id, detail={"code": row["code"]})
    return svc.full_item(ctx, svc.row_by_code(ctx, code))


@router.post("/api/v2/officer/reports/{code}/unmerge")
def unmerge(code: str, officer: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    row = svc.row_by_code(ctx, code)
    if not row["parent_id"]:
        raise HTTPException(400, "This report is not merged into another one.")
    parent = svc.row_by_id(ctx, row["parent_id"])
    ctx.db.execute("UPDATE reports SET parent_id = NULL, status = 'new', updated_at = ? WHERE id = ?",
                   (svc.iso(svc.now()), row["id"]))
    svc.record(ctx, row["id"], "unmerged", officer.name, officer_id=officer.id, old=parent["code"])
    return svc.full_item(ctx, svc.row_by_code(ctx, code))


def repair_photo_flow(ctx: Ctx, tasks: BackgroundTasks, row: dict, raw: bytes, officer: auth.Officer) -> dict:
    """Crew's after photo is inspected again: clean → Resolved; damage still visible → reopened with the reason."""
    try:
        jpeg, _ = imaging.prepare(raw)
    except imaging.BadImage as exc:
        raise HTTPException(400, str(exc)) from exc
    key = svc.store_photo(ctx, jpeg)
    ts = svc.iso(svc.now())
    try:
        result = svc.inspect(ctx, jpeg)
    except InspectorBusy:
        ctx.db.execute("UPDATE reports SET after_photo_key = ?, updated_at = ? WHERE id = ?", (key, ts, row["id"]))
        svc.record(ctx, row["id"], "repair_photo", officer.name, officer_id=officer.id, detail={"checked": False})
        svc.set_status(ctx, svc.row_by_id(ctx, row["id"]), "fixed", svc.SYSTEM, detail={"reason": "ai_busy"})
        return svc.full_item(ctx, svc.row_by_id(ctx, row["id"]))
    except InspectionError as exc:
        raise HTTPException(502, "The AI inspector gave an answer we could not use. Try again in a moment.") from exc
    ctx.db.execute("UPDATE reports SET after_photo_key = ?, after_ai_json = ?, updated_at = ? WHERE id = ?",
                   (key, result.model_dump_json(), ts, row["id"]))
    svc.record(ctx, row["id"], "repair_photo", officer.name, officer_id=officer.id,
               detail={"checked": True, "hazard_type": result.hazard_type, "severity": result.severity_score})
    fresh = svc.row_by_id(ctx, row["id"])
    clean = result.hazard_type == "None" or urgency_for(result) == "LOW"
    if clean:
        svc.set_status(ctx, fresh, "verified", svc.AI, event="verified",
                       detail={"hazard_type": result.hazard_type, "severity": result.severity_score})
        _notify(ctx, tasks, fresh, "verified")
    else:
        svc.set_status(ctx, fresh, "assigned", svc.AI, event="reopened",
                       detail={"hazard_type": result.hazard_type, "severity": result.severity_score})
    return svc.full_item(ctx, svc.row_by_id(ctx, row["id"]))


@router.post("/api/v2/officer/reports/{code}/repair-photo")
async def repair_photo(code: str, tasks: BackgroundTasks, photo: UploadFile = File(...),
                       officer: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    row = svc.row_by_code(ctx, code)
    if row["status"] not in ("new", "assigned", "fixed"):
        raise HTTPException(409, "Repair photos can only be added to open reports.")
    return repair_photo_flow(ctx, tasks, row, await read_photo(ctx, photo), officer)


# ---------- work orders and analytics ----------
@router.get("/api/v2/officer/work-order")
def work_order(assignee: str = Query(..., min_length=2), _: auth.Officer = Depends(require_officer),
               ctx: Ctx = Depends(get_ctx)):
    rows = ctx.db.query(svc.COUNTS_SQL + " WHERE r.parent_id IS NULL AND r.status IN ('assigned', 'new') AND r.assignee = ?",
                        (assignee,))
    items = sorted((svc.full_item(ctx, r) for r in rows), key=triage.queue_key)
    stops = triage.route_order(items)
    return no_store({"assignee": assignee, "generated_at": svc.iso(svc.now()), "stops": stops,
                     "total_km": round(sum(s["leg_m"] or 0 for s in stops) / 1000, 1),
                     "total_hours": sum(s.get("estimated_repair_time_hours") or 0 for s in stops)})


@router.get("/api/v2/officer/analytics")
def analytics(days: int = Query(30, ge=7, le=365), _: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    t = svc.now()
    since = t - timedelta(days=days)
    rows = ctx.db.query("SELECT * FROM reports WHERE parent_id IS NULL AND status != 'no_damage'")
    recent = [r for r in rows if r["created_at"] >= svc.iso(since)]
    local_day = lambda iso_s: svc.parse_iso(iso_s).astimezone(ctx.tz).date().isoformat()  # noqa: E731
    reported = Counter(local_day(r["created_at"]) for r in recent)
    resolved_rows = [r for r in rows if r["status"] == "verified" and r["resolved_at"] and r["resolved_at"] >= svc.iso(since)]
    resolved = Counter(local_day(r["resolved_at"]) for r in resolved_rows)
    day_list = [(t - timedelta(days=i)).astimezone(ctx.tz).date().isoformat() for i in range(days - 1, -1, -1)]

    def avg_days(group):
        hrs = [(svc.parse_iso(r["resolved_at"]) - svc.parse_iso(r["created_at"])).total_seconds() / 3600 for r in group]
        return round(sum(hrs) / len(hrs) / 24, 1) if hrs else None

    by_urgency, by_ward = defaultdict(list), defaultdict(list)
    for r in resolved_rows:
        by_urgency[r["urgency"]].append(r)
        by_ward[r["ward_code"] or "none"].append(r)
    on_time = [r for r in resolved_rows if r["due_at"] and r["resolved_at"] <= r["due_at"]]
    confirmed = ctx.db.query("SELECT detail FROM status_history WHERE event = 'confirmed' AND at >= ?", (svc.iso(since),))
    checks = [json.loads(c["detail"]) for c in confirmed if c["detail"]]
    checks = [c for c in checks if not c.get("ai_pending")]
    overrides = sum(1 for c in checks if c.get("changed"))
    return no_store({
        "days": days,
        "per_day": [{"date": d, "reported": reported.get(d, 0), "resolved": resolved.get(d, 0)} for d in day_list],
        "avg_days_by_urgency": {u: avg_days(by_urgency[u]) for u in triage.URGENCY_RANK},
        "avg_days_by_ward": [{"code": w.code, "name": w.name, "avg_days": avg_days(by_ward[w.code]),
                              "resolved": len(by_ward[w.code])} for w in ctx.wards],
        "sla": {"resolved": len(resolved_rows), "on_time": len(on_time),
                "pct": round(100 * len(on_time) / len(resolved_rows)) if resolved_rows else None,
                "open_overdue": sum(1 for r in rows if svc.is_overdue(r, t))},
        "top_hazards": Counter(r["hazard_type"] for r in recent).most_common(),
        "ai_accuracy": {"checked": len(checks), "overridden": overrides,
                        "agreement_pct": round(100 * (len(checks) - overrides) / len(checks)) if checks else None},
        "totals": {"reported": len(recent), "resolved": len(resolved_rows)},
    })


# ---------- admin ----------
class NewOfficer(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    name: str = Field(min_length=2, max_length=80)
    role: Literal["officer", "admin"] = "officer"
    password: str = Field(min_length=10, max_length=200)


@router.get("/api/v2/admin/officers")
def list_officers(_: auth.Officer = Depends(require_admin), ctx: Ctx = Depends(get_ctx)):
    return no_store(ctx.db.query("SELECT id, email, name, role, active, created_at FROM officers ORDER BY name"))


@router.post("/api/v2/admin/officers")
def create_officer(body: NewOfficer, admin: auth.Officer = Depends(require_admin), ctx: Ctx = Depends(get_ctx)):
    email = body.email.strip().lower()
    if ctx.db.one("SELECT 1 FROM officers WHERE email = ?", (email,)):
        raise HTTPException(409, "An officer with this email already exists.")
    oid = ctx.db.insert("officers", {"email": email, "name": body.name.strip(), "role": body.role,
                                     "password_hash": auth.hash_password(body.password), "active": 1,
                                     "created_at": svc.iso(svc.now())})
    return {"id": oid, "email": email, "name": body.name.strip(), "role": body.role, "active": 1}


class OfficerUpdate(BaseModel):
    active: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=200)


@router.patch("/api/v2/admin/officers/{officer_id}")
def update_officer(officer_id: int, body: OfficerUpdate, admin: auth.Officer = Depends(require_admin),
                   ctx: Ctx = Depends(get_ctx)):
    if not ctx.db.one("SELECT 1 FROM officers WHERE id = ?", (officer_id,)):
        raise HTTPException(404, "No such officer.")
    if body.active is False and officer_id == admin.id:
        raise HTTPException(400, "You cannot deactivate your own account.")
    if body.active is not None:
        ctx.db.execute("UPDATE officers SET active = ? WHERE id = ?", (int(body.active), officer_id))
    if body.password:
        ctx.db.execute("UPDATE officers SET password_hash = ? WHERE id = ?", (auth.hash_password(body.password), officer_id))
    return ctx.db.one("SELECT id, email, name, role, active, created_at FROM officers WHERE id = ?", (officer_id,))


@router.get("/api/v2/admin/export.csv")
def admin_export(_: auth.Officer = Depends(require_admin), ctx: Ctx = Depends(get_ctx)):
    """Everything in the public export plus the citizen's note. Still no device id or contact address."""
    import csv
    import io

    rows, _ = filtered_rows(ctx)
    review = ctx.db.query(svc.COUNTS_SQL + " WHERE r.status IN ('review', 'no_damage')")
    buf = io.StringIO()
    fields = ["code", "created_at", "ward", "hazard_type", "severity", "urgency", "status", "reported_count",
              "assignee", "lat", "lng", "due_at", "resolved_at", "overdue", "is_demo", "note"]
    out = csv.DictWriter(buf, fieldnames=fields)
    out.writeheader()
    for r in rows + review:
        item = svc.full_item(ctx, r)
        out.writerow({**{k: item.get(k) for k in fields}, "ward": (item["ward"] or {}).get("name")})
    return Response(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="rastescan-all.csv"', "Cache-Control": "no-store"})


# ---------- legacy routes kept for the first Android build ----------
@router.get("/api/queue")
def legacy_queue(_: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    return no_store(queue_payload(ctx))


@router.patch("/api/reports/{code}")
def legacy_status(code: str, change: StatusChange, tasks: BackgroundTasks,
                  officer: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    if change.status == "dismissed" and not change.reason:
        change = StatusChange(status="dismissed", reason="Closed by the ward office.")
    row = svc.row_by_code(ctx, code)
    _change_status(ctx, tasks, row, change, officer)
    return svc.full_item(ctx, svc.row_by_code(ctx, code))


@router.post("/api/reports/{code}/after-photo")
async def legacy_after_photo(code: str, tasks: BackgroundTasks, photo: UploadFile = File(...),
                             officer: auth.Officer = Depends(require_officer), ctx: Ctx = Depends(get_ctx)):
    row = svc.row_by_code(ctx, code)
    return repair_photo_flow(ctx, tasks, row, await read_photo(ctx, photo), officer)
