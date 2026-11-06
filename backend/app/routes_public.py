"""Read-only public API: anyone can see every published report, its history, and how each ward performs.

Nothing here returns a device id, contact address, citizen note or officer email (see services.public_item).
"""
import csv
import io
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import services as svc
from .http import cached_json, client_key, get_ctx
from .schema import HazardType, Urgency
from .services import Ctx

router = APIRouter(prefix="/api/public", tags=["public"])

SORTS = {
    "newest": "r.created_at DESC",
    "oldest": "r.created_at ASC",
    "severity": "r.severity DESC, r.created_at DESC",
    "urgency": "CASE r.urgency WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END, r.due_at ASC",
    "due": "r.due_at IS NULL, r.due_at ASC",
    "reports": "(1 + dup_count + vote_count) DESC, r.created_at DESC",
}
STATUS_GROUPS = {
    "open": ("new", "assigned", "fixed"),
    "resolved": ("verified",),
    "dismissed": ("dismissed",),
    "ai_verified": ("new",),
    "assigned": ("assigned",),
    "repair_done": ("fixed",),
}


def _split(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def _day_start(ctx: Ctx, d: date) -> str:
    return datetime.combine(d, time.min, ctx.tz).astimezone(timezone.utc).isoformat()


def filtered_rows(ctx: Ctx, *, status=None, urgency=None, hazard=None, ward=None, date_from=None, date_to=None,
                  overdue=False, bbox=None, q=None, sort="newest", limit=None, offset=0) -> tuple[list[dict], int]:
    where = ["r.parent_id IS NULL", f"r.status IN ({','.join('?' for _ in svc.PUBLIC_INTERNAL)})"]
    args: list = list(svc.PUBLIC_INTERNAL)
    statuses = [s for v in _split(status) for s in STATUS_GROUPS.get(v, ())]
    if _split(status) and not statuses:
        raise HTTPException(400, "Unknown status filter. Use open, resolved, dismissed, ai_verified, assigned or repair_done.")
    if statuses:
        where.append(f"r.status IN ({','.join('?' for _ in statuses)})")
        args += statuses
    for col, values in (("r.urgency", _split(urgency)), ("r.hazard_type", _split(hazard)), ("r.ward_code", _split(ward))):
        if values:
            where.append(f"{col} IN ({','.join('?' for _ in values)})")
            args += values
    if date_from:
        where.append("r.created_at >= ?")
        args.append(_day_start(ctx, date_from))
    if date_to:
        where.append("r.created_at < ?")
        args.append(_day_start(ctx, date_to + timedelta(days=1)))
    if overdue:
        where.append("r.status IN ('new','assigned','fixed') AND r.due_at < ?")
        args.append(svc.iso(svc.now()))
    if bbox:
        try:
            min_lng, min_lat, max_lng, max_lat = (float(v) for v in bbox.split(","))
        except ValueError as exc:
            raise HTTPException(400, "bbox must be min_lng,min_lat,max_lng,max_lat") from exc
        where.append("r.lat BETWEEN ? AND ? AND r.lng BETWEEN ? AND ?")
        args += [min_lat, max_lat, min_lng, max_lng]
    if q:
        where.append("r.code LIKE ?")
        args.append(f"%{q.strip().upper()}%")
    sql_where = " WHERE " + " AND ".join(where)
    total = ctx.db.scalar("SELECT COUNT(*) FROM reports r" + sql_where, tuple(args))
    sql = svc.COUNTS_SQL + sql_where + " ORDER BY " + SORTS.get(sort, SORTS["newest"])
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        args += [limit, offset]
    return ctx.db.query(sql, tuple(args)), total


class ListParams:
    def __init__(
        self,
        status: str | None = Query(None, description="open, resolved, dismissed, ai_verified, assigned, repair_done (comma separated)"),
        urgency: str | None = Query(None, description="LOW, MEDIUM, HIGH, CRITICAL (comma separated)"),
        hazard: str | None = Query(None, description="Pothole, Open Manhole, ... (comma separated)"),
        ward: str | None = Query(None, description="Ward codes, comma separated"),
        date_from: date | None = Query(None, alias="from"),
        date_to: date | None = Query(None, alias="to"),
        overdue: bool = False,
        bbox: str | None = Query(None, description="min_lng,min_lat,max_lng,max_lat"),
        q: str | None = Query(None, description="Report code, e.g. RS-0012"),
        sort: str = Query("newest", description=", ".join(SORTS)),
    ):
        self.kw = dict(status=status, urgency=urgency, hazard=hazard, ward=ward, date_from=date_from, date_to=date_to,
                       overdue=overdue, bbox=bbox, q=q, sort=sort)


@router.get("/config")
def config(request: Request, ctx: Ctx = Depends(get_ctx)):
    return cached_json(request, {
        "site_name": ctx.settings.site_name,
        "ai_mode": ctx.inspector.mode,
        "hazards": list(HazardType.__args__),
        "urgencies": list(Urgency.__args__),
        "wards": [{"code": w.code, "name": w.name, "lat": w.centroid[0], "lng": w.centroid[1]} for w in ctx.wards],
    }, max_age=300)


@router.get("/reports")
def list_reports(request: Request, params: ListParams = Depends(), page: int = Query(1, ge=1),
                 per_page: int = Query(50, ge=1, le=1000), ctx: Ctx = Depends(get_ctx)):
    rows, total = filtered_rows(ctx, limit=per_page, offset=(page - 1) * per_page, **params.kw)
    return cached_json(request, {"items": [svc.public_item(ctx, r) for r in rows], "total": total,
                                 "page": page, "per_page": per_page})


@router.get("/reports/{code}")
def get_report(code: str, request: Request, ctx: Ctx = Depends(get_ctx)):
    row = svc.row_by_code(ctx, code)
    if row["status"] not in svc.PUBLIC_INTERNAL:
        raise HTTPException(404, f"Report {code.upper()} is waiting for a check and is not public yet.")
    return cached_json(request, svc.public_detail(ctx, row), max_age=15)


@router.get("/reports/{code}/address")
def get_address(code: str, request: Request, ctx: Ctx = Depends(get_ctx)):
    row = svc.row_by_code(ctx, code)
    if row["status"] not in svc.PUBLIC_INTERNAL:
        raise HTTPException(404, f"Report {code.upper()} is waiting for a check and is not public yet.")
    found = svc.address(ctx, row)
    return cached_json(request, found or {}, max_age=3600 if found else 30)


class Vote(BaseModel):
    device_id: str = Field(min_length=8, max_length=100)


@router.post("/reports/{code}/vote")
def vote(code: str, body: Vote, request: Request, ctx: Ctx = Depends(get_ctx)):
    if not ctx.limiter.allow(client_key(request, body.device_id) + ":vote"):
        raise HTTPException(429, "Too many requests from this device. Try again later.")
    row = svc.row_by_code(ctx, code)
    if row["status"] not in svc.OPEN:
        raise HTTPException(409, "This report is already closed.")
    added = svc.add_vote(ctx, row, body.device_id)
    fresh = svc.row_by_id(ctx, row["parent_id"] or row["id"])
    return {"added": added, "reported_count": svc.reported_count(fresh)}


@router.get("/stats")
def stats(request: Request, ctx: Ctx = Depends(get_ctx)):
    return cached_json(request, svc.stats(ctx))


@router.get("/impact")
def impact(request: Request, days: int = Query(14, ge=7, le=90), ctx: Ctx = Depends(get_ctx)):
    return cached_json(request, svc.impact(ctx, days), max_age=20)


@router.get("/activity")
def activity(request: Request, limit: int = Query(15, ge=1, le=50), ctx: Ctx = Depends(get_ctx)):
    return cached_json(request, svc.activity(ctx, limit), max_age=5)


@router.get("/wards")
def wards(request: Request, ctx: Ctx = Depends(get_ctx)):
    return cached_json(request, svc.ward_scoreboard(ctx), max_age=60)


@router.get("/recently-resolved")
def recently_resolved(request: Request, limit: int = Query(8, ge=1, le=30), ctx: Ctx = Depends(get_ctx)):
    rows = ctx.db.query(svc.COUNTS_SQL + " WHERE r.parent_id IS NULL AND r.status = 'verified' "
                        "ORDER BY r.resolved_at DESC LIMIT ?", (limit,))
    return cached_json(request, [svc.public_item(ctx, r) for r in rows], max_age=15)


CSV_FIELDS = ["code", "created_at", "ward_code", "ward_name", "pin_code", "state", "hazard_type", "severity", "urgency", "public_status",
              "reported_count", "lat", "lng", "due_at", "resolved_at", "overdue", "assignee", "is_demo", "url"]


@router.get("/export.csv")
def export_csv(params: ListParams = Depends(), ctx: Ctx = Depends(get_ctx)):
    rows, _ = filtered_rows(ctx, **params.kw)
    buf = io.StringIO()
    out = csv.DictWriter(buf, fieldnames=CSV_FIELDS)
    out.writeheader()
    base = ctx.settings.public_base_url
    for r in rows:
        item = svc.public_item(ctx, r)
        out.writerow({
            **{k: item.get(k) for k in CSV_FIELDS if k in item},
            "ward_code": (item["ward"] or {}).get("code"), "ward_name": (item["ward"] or {}).get("name"),
            "pin_code": (item["address"] or {}).get("pin"), "state": (item["address"] or {}).get("state"),
            "url": f"{base}/#/r/{item['code']}" if base else f"#/r/{item['code']}",
        })
    return Response(buf.getvalue(), media_type="text/csv", headers={
        "Content-Disposition": 'attachment; filename="rastescan-reports.csv"', "Cache-Control": "public, max-age=60"})
