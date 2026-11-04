"""Admin "Model lab": see which AI models are available, run any of them on one photo, and pick the live one.

Nothing here touches reports. A test run blurs the photo like a real report, calls the chosen model, and returns the
answer and the time taken. Switching the live model lasts until the server restarts; AI_MODE in the environment decides
what it starts with.
"""
import json
import threading
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


def _ollama_base(ctx: Ctx) -> str:
    return ctx.settings.ollama_url.rstrip("/").removesuffix("/v1")


def _download(ctx: Ctx, tag: str) -> None:
    """Runs in a background thread: asks the local Ollama to download `tag` and records its progress."""
    state = ctx.pulls[tag]
    try:
        with httpx.stream("POST", f"{_ollama_base(ctx)}/api/pull", json={"model": tag, "stream": True}, timeout=None) as r:
            if r.status_code != 200:
                raise RuntimeError(f"Ollama answered HTTP {r.status_code}")
            for line in r.iter_lines():
                if not line:
                    continue
                msg = json.loads(line)
                if msg.get("error"):
                    raise RuntimeError(msg["error"])
                state["status"] = msg.get("status", "")
                if msg.get("total"):
                    state["percent"] = round(100 * msg.get("completed", 0) / msg["total"])
        state.update(running=False, percent=100, status="done")
    except Exception as exc:  # noqa: BLE001 - shown to the admin
        state.update(running=False, error=str(exc)[:200] or exc.__class__.__name__)


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
    yolo_up, yolo_has_weights = False, False
    try:
        h = httpx.get(s.yolo_url.rstrip("/") + "/health", timeout=2).json()
        yolo_up, yolo_has_weights = True, bool(h.get("weights"))
    except Exception:  # noqa: BLE001 - not running
        pass
    models.append({"id": "yolo:rdd2022-yolov8m", "provider": "yolo", "model": "rdd2022-yolov8m",
                   "label": "YOLO road-damage detector", "installed": yolo_up and yolo_has_weights,
                   "runnable": yolo_up and yolo_has_weights, "size_gb": 0.05, "pull": None,
                   "note": ("Finds potholes and cracks with boxes in under a second. Severity is estimated from size; it does not know "
                            "manholes, water or debris. AGPL-3.0 weights." if yolo_up and yolo_has_weights else
                            "Not running. Set up once: make yolo-setup && make yolo-weights, then start it with: make yolo")})
    for m in models:
        m["pull_state"] = ctx.pulls.get(m["model"]) if m["provider"] == "ollama" else None
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
        if hasattr(inspector, "patient"):
            inspector = inspector.patient()  # a lab run may take minutes on a laptop CPU
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


class Pull(BaseModel):
    model: str


@router.post("/api/v2/admin/models/pull")
def pull_model(body: Pull, officer: auth.Officer = Depends(require_admin), ctx: Ctx = Depends(get_ctx)):
    """Download one of the recommended models into the local Ollama. Only the tags in RECOMMENDED are allowed."""
    if body.model not in {tag for tag, _, _ in RECOMMENDED}:
        raise HTTPException(400, "Only the models listed in the Model lab can be downloaded from here.")
    if ctx.pulls.get(body.model, {}).get("running"):
        return ctx.pulls[body.model]
    ctx.pulls[body.model] = {"running": True, "percent": 0, "status": "starting", "error": None}
    threading.Thread(target=_download, args=(ctx, body.model), daemon=True).start()
    return ctx.pulls[body.model]
