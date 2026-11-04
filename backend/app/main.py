"""RasteScan API: citizen reports in, triaged repair queue out."""
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import imaging, triage
from .config import Settings
from .db import Database
from .inspector import BedrockInspector, FakeInspector, Inspector, InspectionError, OpenAICompatInspector, load_prompt
from .ratelimit import RateLimiter
from .schema import Inspection, needs_human_review, urgency_for
from .storage import LocalStorage, S3Storage

log = logging.getLogger("rastescan")


def now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(settings: Settings | None = None, inspector: Inspector | None = None) -> FastAPI:
    settings = settings or Settings()
    if inspector is None:
        if settings.ai_mode == "fake":
            inspector = FakeInspector()
        elif settings.ai_mode == "groq":
            if not settings.groq_api_key:
                raise RuntimeError("AI_MODE=groq needs GROQ_API_KEY.")
            inspector = OpenAICompatInspector("groq", "https://api.groq.com/openai/v1", settings.groq_model,
                                              load_prompt(settings.prompt_file), settings.groq_api_key)
        elif settings.ai_mode == "ollama":
            inspector = OpenAICompatInspector("ollama", settings.ollama_url, settings.ollama_model,
                                              load_prompt(settings.prompt_file), timeout=180)
        else:
            inspector = BedrockInspector(settings.bedrock_model_id, settings.bedrock_region, load_prompt(settings.prompt_file))
    model_tag = getattr(inspector, "model_id", "fake")
    db = Database(settings.data_dir / "rastescan.db")
    storage = S3Storage(settings.s3_bucket, settings.aws_region) if settings.s3_bucket else LocalStorage(settings.data_dir / "photos")
    limiter = RateLimiter(settings.reports_per_hour)

    app = FastAPI(title="RasteScan API")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])

    # ---------- helpers ----------
    def client_key(request: Request, device_id: str | None) -> str:
        if device_id:
            return f"dev:{device_id[:64]}"
        fwd = request.headers.get("x-forwarded-for", "")
        return "ip:" + (fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown"))

    async def read_photo(photo: UploadFile) -> bytes:
        limit = settings.max_upload_mb * 1024 * 1024
        data = await photo.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"Photo is larger than {settings.max_upload_mb} MB. Take it again at a lower resolution.")
        if not data:
            raise HTTPException(400, "The photo is empty.")
        return data

    def inspect(jpeg: bytes) -> Inspection:
        sha = hashlib.sha256(jpeg).hexdigest()
        hit = db.cached(sha, model_tag)
        if hit:
            return Inspection.model_validate_json(hit)
        try:
            result = inspector.inspect(jpeg)
        except InspectionError as exc:
            log.warning("model answer rejected: %s", exc)
            raise HTTPException(502, "The AI inspector gave an answer we could not use. Try again in a moment.") from exc
        except Exception as exc:  # network, throttling, permissions
            log.exception("inspection failed")
            raise HTTPException(503, "The AI inspector is not reachable right now. Try again in a moment.") from exc
        db.cache(sha, model_tag, result.model_dump_json())
        return result

    def store_photo(jpeg: bytes) -> str:
        key = f"{uuid.uuid4().hex}.jpg"
        storage.save(key, jpeg)
        return key

    def serialize(row: dict, merged_count: int | None = None) -> dict:
        parent = db.one("SELECT code FROM reports WHERE id = ?", (row["parent_id"],)) if row["parent_id"] else None
        if merged_count is None:
            merged_count = 1 + db.one("SELECT COUNT(*) AS n FROM reports WHERE parent_id = ?", (row["id"],))["n"]
        return {
            "code": row["code"],
            "lat": row["lat"],
            "lng": row["lng"],
            "photo_url": storage.url(row["photo_key"]),
            "after_photo_url": storage.url(row["after_photo_key"]) if row["after_photo_key"] else None,
            "result": json.loads(row["ai_json"]),
            "after_result": json.loads(row["after_ai_json"]) if row["after_ai_json"] else None,
            "hazard_type": row["hazard_type"],
            "severity": row["severity"],
            "urgency": row["urgency"],
            "model_urgency": row["model_urgency"],
            "confidence": row["confidence"],
            "needs_review": bool(row["needs_review"]),
            "status": row["status"],
            "merged_into": parent["code"] if parent else None,
            "merged_count": merged_count,
            "created_at": row["created_at"],
            "due_at": row["due_at"],
            "updated_at": row["updated_at"],
        }

    def get_row(code: str) -> dict:
        row = db.one("SELECT * FROM reports WHERE code = ?", (code.upper(),))
        if not row:
            raise HTTPException(404, f"No report with code {code}.")
        return row

    def require_pin(x_dashboard_pin: str | None = Header(default=None)) -> None:
        if settings.dashboard_pin and x_dashboard_pin != settings.dashboard_pin:
            raise HTTPException(401, "Enter the dashboard PIN to change tickets.")

    # ---------- routes ----------
    @app.get("/api/health")
    def health():
        return {"ok": True, "ai_mode": inspector.mode, "model": model_tag if inspector.mode != "fake" else None}

    @app.post("/api/reports")
    async def create_report(
        request: Request,
        photo: UploadFile = File(...),
        lat: float | None = Form(default=None),
        lng: float | None = Form(default=None),
        device_id: str | None = Form(default=None),
    ):
        if not limiter.allow(client_key(request, device_id)):
            raise HTTPException(429, "Too many reports from this device in the last hour. Try again later.")
        raw = await read_photo(photo)
        try:
            jpeg, exif_pos = imaging.prepare(raw)
        except imaging.BadImage as exc:
            raise HTTPException(400, str(exc)) from exc
        if (lat is None or lng is None) and exif_pos:
            lat, lng = exif_pos
        result = inspect(jpeg)
        urgency = urgency_for(result)
        review = needs_human_review(result)
        if urgency != result.urgency_level:
            log.info("urgency corrected from %s to %s", result.urgency_level, urgency)

        status = "no_damage" if result.hazard_type == "None" else ("review" if review else "new")
        parent_id = None
        if status == "new":
            open_rows = db.query(
                "SELECT id, lat, lng, hazard_type FROM reports WHERE parent_id IS NULL AND status IN (?, ?)",
                triage.OPEN_STATUSES)
            dup = triage.find_duplicate(open_rows, lat, lng, result.hazard_type, settings.merge_radius_m)
            parent_id = dup["id"] if dup else None

        created = now()
        rid = db.insert_report({
            "lat": lat, "lng": lng,
            "photo_key": store_photo(jpeg),
            "ai_json": result.model_dump_json(),
            "hazard_type": result.hazard_type,
            "severity": result.severity_score,
            "urgency": urgency,
            "model_urgency": result.urgency_level,
            "confidence": result.confidence,
            "needs_review": int(review),
            "parent_id": parent_id,
            "status": status,
            "device_id": device_id,
            "created_at": created.isoformat(),
            "due_at": triage.due_at(created, urgency).isoformat() if status != "no_damage" else None,
            "updated_at": created.isoformat(),
        })
        if parent_id:
            # A repeat report can raise the parent ticket's priority but never lower it.
            parent = db.one("SELECT * FROM reports WHERE id = ?", (parent_id,))
            if triage.URGENCY_RANK[urgency] > triage.URGENCY_RANK[parent["urgency"]] or result.severity_score > parent["severity"]:
                new_urg = max(urgency, parent["urgency"], key=triage.URGENCY_RANK.get)
                db.execute(
                    "UPDATE reports SET urgency = ?, severity = MAX(severity, ?), due_at = MIN(due_at, ?), updated_at = ? WHERE id = ?",
                    (new_urg, result.severity_score, triage.due_at(created, new_urg).isoformat(), created.isoformat(), parent_id))
        return serialize(db.one("SELECT * FROM reports WHERE id = ?", (rid,)))

    @app.get("/api/reports")
    def list_reports(device_id: str):
        rows = db.query("SELECT * FROM reports WHERE device_id = ? ORDER BY id DESC LIMIT 50", (device_id,))
        return [serialize(r) for r in rows]

    @app.get("/api/reports/{code}")
    def get_report(code: str):
        return serialize(get_row(code))

    @app.get("/api/queue")
    def queue():
        parents = db.query("SELECT * FROM reports WHERE parent_id IS NULL AND status IN ('new', 'assigned', 'fixed')")
        counts = {r["parent_id"]: r["n"] for r in db.query(
            "SELECT parent_id, COUNT(*) AS n FROM reports WHERE parent_id IS NOT NULL GROUP BY parent_id")}
        tickets = sorted((serialize(p, 1 + counts.get(p["id"], 0)) for p in parents), key=triage.queue_key)
        review = [serialize(r) for r in db.query("SELECT * FROM reports WHERE status = 'review' ORDER BY id DESC")]
        by_urgency = {u: 0 for u in triage.URGENCY_RANK}
        for t in tickets:
            if t["status"] != "fixed":
                by_urgency[t["urgency"]] += 1
        verified = db.one("SELECT COUNT(*) AS n FROM reports WHERE status = 'verified'")["n"]
        return {"tickets": tickets, "review": review, "counts": by_urgency, "verified": verified, "ai_mode": inspector.mode}

    class StatusChange(BaseModel):
        status: Literal["new", "assigned", "fixed", "verified", "dismissed"]

    @app.patch("/api/reports/{code}", dependencies=[Depends(require_pin)])
    def change_status(code: str, change: StatusChange):
        row = get_row(code)
        ts = now().isoformat()
        if row["status"] == "review" and change.status in ("new", "assigned"):
            db.execute("UPDATE reports SET needs_review = 0 WHERE id = ?", (row["id"],))
        db.execute("UPDATE reports SET status = ?, updated_at = ? WHERE id = ?", (change.status, ts, row["id"]))
        # Merged duplicates follow their ticket.
        db.execute("UPDATE reports SET status = ?, updated_at = ? WHERE parent_id = ?", (change.status, ts, row["id"]))
        return serialize(get_row(code))

    @app.post("/api/reports/{code}/after-photo", dependencies=[Depends(require_pin)])
    async def after_photo(code: str, photo: UploadFile = File(...)):
        """Field crew uploads a photo of the repair; it is inspected again before the ticket is verified."""
        row = get_row(code)
        try:
            jpeg, _ = imaging.prepare(await read_photo(photo))
        except imaging.BadImage as exc:
            raise HTTPException(400, str(exc)) from exc
        result = inspect(jpeg)
        fixed = result.hazard_type == "None" or urgency_for(result) == "LOW"
        status = "verified" if fixed else "assigned"
        ts = now().isoformat()
        db.execute(
            "UPDATE reports SET after_photo_key = ?, after_ai_json = ?, status = ?, updated_at = ? WHERE id = ?",
            (store_photo(jpeg), result.model_dump_json(), status, ts, row["id"]))
        db.execute("UPDATE reports SET status = ?, updated_at = ? WHERE parent_id = ?", (status, ts, row["id"]))
        return serialize(get_row(code))

    if isinstance(storage, LocalStorage):
        @app.get("/api/photos/{key}")
        def photo(key: str):
            path = storage.path(key)
            if "/" in key or ".." in key or not path.is_file():
                raise HTTPException(404, "Photo not found.")
            return FileResponse(path, media_type="image/jpeg")

    # ---------- web app ----------
    dist = settings.web_dist
    if dist.is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            file = (dist / path).resolve()
            if path and file.is_file() and dist.resolve() in file.parents:
                return FileResponse(file)
            return FileResponse(dist / "index.html")

    return app

