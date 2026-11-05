"""Admin "Model lab": see which AI providers are set up, run any of them on one photo, and pick the live one.

Nothing here touches reports. A test run blurs the photo like a real report, calls the chosen model, and returns the
answer and the time taken. Switching the live model lasts until the server restarts; AI_MODE in the environment decides
what it starts with.
"""
import time

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import auth, imaging
from .http import get_ctx, read_photo
from .inspector import InspectionError, InspectorBusy, _why, build_inspector
from .routes_officer import require_admin
from .services import Ctx

router = APIRouter(tags=["models"])


def _live(ctx: Ctx) -> dict:
    return {"provider": ctx.inspector.mode, "model": getattr(ctx.inspector, "model", "") or ""}


@router.get("/api/v2/admin/models")
def list_models(officer: auth.Officer = Depends(require_admin), ctx: Ctx = Depends(get_ctx)):
    live = _live(ctx)
    s = ctx.settings
    models = [
        {"id": f"groq:{s.groq_model}", "provider": "groq", "model": s.groq_model, "label": f"Groq {s.groq_model}",
         "runnable": bool(s.groq_api_key),
         "note": "Hosted free tier with small per-minute limits." if s.groq_api_key else "Set GROQ_API_KEY to enable."},
        {"id": f"bedrock:{s.bedrock_model_id}", "provider": "bedrock", "model": s.bedrock_model_id,
         "label": f"Amazon Nova ({s.bedrock_model_id})", "runnable": True, "note": "Needs AWS access to Bedrock."},
        {"id": "fake:sample", "provider": "fake", "model": "", "label": "Sample answers (no AI)", "runnable": True,
         "note": "Canned results for testing the screens."},
    ]
    for m in models:
        m["live"] = m["provider"] == live["provider"] and (m["model"] == live["model"] or not live["model"])
    return {"live": live, "models": models}


@router.post("/api/v2/admin/models/test")
async def test_model(photo: UploadFile = File(...), provider: str = Form(...), model: str = Form(""),
                     officer: auth.Officer = Depends(require_admin), ctx: Ctx = Depends(get_ctx)):
    """Run one model on one photo. Always answers 200 with ok true or false so the page can show the reason."""
    raw = await read_photo(ctx, photo)
    try:
        jpeg, _ = imaging.prepare(raw)
        inspector = build_inspector(ctx.settings, provider, model or None)
    except (imaging.BadImage, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    started = time.monotonic()
    try:
        result = inspector.inspect(jpeg)
        ok, error = True, None
    except InspectionError as exc:
        result, ok, error = None, False, f"The model answered, but not in a usable format: {str(exc)[:200]}"
    except InspectorBusy as exc:
        result, ok, error = None, False, str(exc)
    except Exception as exc:  # noqa: BLE001 - show whatever went wrong
        result, ok, error = None, False, _why(exc) or exc.__class__.__name__
    return {"ok": ok, "error": error, "seconds": round(time.monotonic() - started, 1),
            "provider": provider, "model": model, "result": result.model_dump() if result else None}


class Live(BaseModel):
    provider: str
    model: str = ""


@router.post("/api/v2/admin/models/live")
def set_live(body: Live, officer: auth.Officer = Depends(require_admin), ctx: Ctx = Depends(get_ctx)):
    """Use this model for new reports until the server restarts."""
    try:
        ctx.inspector = build_inspector(ctx.settings, body.provider, body.model or None)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"live": _live(ctx)}
