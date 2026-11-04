"""Admin "Model lab": see which AI models are available, run any of them on one photo, and pick the live one.

Nothing here touches reports. A test run blurs the photo like a real report, calls the chosen model, and returns the
answer and the time taken. Switching the live model lasts until the server restarts; AI_MODE in the environment decides
what it starts with.
"""
import time

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from . import auth, imaging
from .http import get_ctx, read_photo
from .inspector import InspectionError, InspectorBusy, _why, build_inspector
from .routes_officer import require_admin
from .services import Ctx

router = APIRouter(tags=["models"])

# Worth trying, in the order to try them. Shown with the pull command when they are not installed yet.
RECOMMENDED = [
    ("qwen2.5vl:3b", "Qwen2.5-VL 3B", "About 3.2 GB. Fast on a CPU and trained to give boxes: start here."),
    ("qwen3.5:4b", "Qwen3.5 4B", "About 3.3-4 GB. Newer model with image understanding; compare it with the one above."),
    ("qwen3.5:9b", "Qwen3.5 9B", "About 6.6-7.6 GB. Better reasoning, slower on a CPU."),
    ("qwen2.5vl:7b", "Qwen2.5-VL 7B", "About 6 GB. Best box accuracy of the Qwen2.5-VL sizes."),
    ("gemma3:4b", "Gemma 3 4B", "About 3.4 GB. Alternative vision model; often weaker at box positions."),
]


def _ollama(ctx: Ctx) -> tuple[bool, list[dict]]:
    """Installed Ollama models with their vision flag, or (False, []) when Ollama is not running."""
    base = ctx.settings.ollama_url.rstrip("/").removesuffix("/v1")
    try:
        with httpx.Client(timeout=4) as http:
            tags = http.get(f"{base}/api/tags").json().get("models", [])
            out = []
            for m in tags:
                try:
                    caps = http.post(f"{base}/api/show", json={"model": m["name"]}).json().get("capabilities") or []
                except Exception:  # noqa: BLE001 - an old Ollama has no capabilities; treat as unknown
                    caps = []
                out.append({"model": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 1), "vision": "vision" in caps})
            return True, out
    except Exception:  # noqa: BLE001 - not running, wrong URL, timeout
        return False, []


def _live(ctx: Ctx) -> dict:
    return {"provider": ctx.inspector.mode, "model": getattr(ctx.inspector, "model", "") or ""}


@router.get("/api/v2/admin/models")
def list_models(officer: auth.Officer = Depends(require_admin), ctx: Ctx = Depends(get_ctx)):
    live = _live(ctx)
    up, installed = _ollama(ctx)
    have = {m["model"] for m in installed}
    models = []
    for m in installed:
        models.append({"id": f"ollama:{m['model']}", "provider": "ollama", "model": m["model"], "label": m["model"],
                       "installed": True, "runnable": m["vision"], "size_gb": m["size_gb"],
                       "note": "Local and free." if m["vision"] else "Text-only model: it cannot read photos.", "pull": None})
    for tag, label, note in RECOMMENDED:
        if tag not in have:
            models.append({"id": f"ollama:{tag}", "provider": "ollama", "model": tag, "label": label, "installed": False,
                           "runnable": False, "size_gb": None, "note": note, "pull": f"ollama pull {tag}"})
    s = ctx.settings
    models.append({"id": f"groq:{s.groq_model}", "provider": "groq", "model": s.groq_model, "label": f"Groq {s.groq_model}",
                   "installed": bool(s.groq_api_key), "runnable": bool(s.groq_api_key), "size_gb": None,
                   "note": "Hosted free tier with small per-minute limits." if s.groq_api_key else "Set GROQ_API_KEY to enable.",
                   "pull": None})
    models.append({"id": f"bedrock:{s.bedrock_model_id}", "provider": "bedrock", "model": s.bedrock_model_id,
                   "label": f"Amazon Nova ({s.bedrock_model_id})", "installed": True, "runnable": True, "size_gb": None,
                   "note": "Needs AWS access to Bedrock.", "pull": None})
    models.append({"id": "fake:sample", "provider": "fake", "model": "", "label": "Sample answers (no AI)", "installed": True,
                   "runnable": True, "size_gb": None, "note": "Canned results for testing the screens.", "pull": None})
    models.append({"id": "yolo:road", "provider": "yolo", "model": "", "label": "YOLO road-damage detector", "installed": False,
                   "runnable": False, "size_gb": None, "pull": None,
                   "note": "Fast box detector for potholes and cracks. Not installed: it would run as a separate service."})
    for m in models:
        m["live"] = m["provider"] == live["provider"] and (m["model"] == live["model"] or not live["model"])
    return {"live": live, "ollama_running": up, "ollama_url": s.ollama_url, "models": models}


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
