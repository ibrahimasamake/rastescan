"""Citizen API: send a report, see your own reports. No account needed; a random device id links them."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from . import imaging
from . import services as svc
from .http import client_key, get_ctx, no_store, read_photo
from .services import Ctx

router = APIRouter(tags=["citizen"])


@router.get("/api/health")
def health(ctx: Ctx = Depends(get_ctx)):
    model = getattr(ctx.inspector, "model", None)
    return {"ok": True, "ai_mode": ctx.inspector.mode, "model": None if ctx.inspector.mode == "fake" else model}


@router.post("/api/reports")
async def create_report(
    request: Request,
    photo: UploadFile = File(...),
    lat: float | None = Form(default=None),
    lng: float | None = Form(default=None),
    device_id: str | None = Form(default=None),
    note: str | None = Form(default=None),
    contact_email: str | None = Form(default=None),
    ctx: Ctx = Depends(get_ctx),
):
    if not ctx.limiter.allow(client_key(request, device_id)):
        raise HTTPException(429, "Too many reports from this device in the last hour. Try again later.")
    if (lat is None) != (lng is None) or (lat is not None and not (-90 <= lat <= 90 and -180 <= lng <= 180)):
        raise HTTPException(400, "The location is not valid. Drop the pin on the map again.")
    if contact_email and ("@" not in contact_email or len(contact_email) > 200):
        raise HTTPException(400, "That email address does not look right.")
    raw = await read_photo(ctx, photo)
    try:
        jpeg, exif_pos = imaging.prepare(raw)
    except imaging.BadImage as exc:
        raise HTTPException(400, str(exc)) from exc
    if lat is None and exif_pos:
        lat, lng = exif_pos
    row = svc.create_report(ctx, jpeg, lat, lng, device_id, note=note, contact_email=contact_email)
    return svc.citizen_item(ctx, row)


@router.get("/api/reports")
def my_reports(device_id: str, ctx: Ctx = Depends(get_ctx)):
    rows = ctx.db.query(svc.COUNTS_SQL + " WHERE r.device_id = ? ORDER BY r.id DESC LIMIT 50", (device_id,))
    return no_store([svc.citizen_item(ctx, r) for r in rows])


@router.get("/api/reports/{code}")
def get_report(code: str, ctx: Ctx = Depends(get_ctx)):
    return svc.citizen_item(ctx, svc.row_by_code(ctx, code))
