"""RasteScan API: citizen reports in, a public record of every report, and a ranked repair queue for the city."""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import auth, routes_citizen, routes_models, routes_officer, routes_public
from . import services as svc
from .config import Settings
from .db import Database
from .inspector import Inspector, make_inspector
from .ratelimit import RateLimiter
from .storage import LocalStorage, S3Storage
from .wards import load_wards

log = logging.getLogger("rastescan")

# Browsers on a private network: localhost, the usual home/office address ranges, and <name>.local.
LAN_ORIGIN = (r"^https?://(localhost|127\.0\.0\.1|\[::1\]|[\w-]+\.local|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+"
              r"|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+)(:\d+)?$")


def seed_admin(ctx: svc.Ctx) -> None:
    """Create the first administrator from ADMIN_EMAIL / ADMIN_PASSWORD when no officer exists yet."""
    s = ctx.settings
    if not s.admin_email or not s.admin_password or ctx.db.scalar("SELECT COUNT(*) FROM officers"):
        return
    if not auth.valid_password(s.admin_password):
        log.warning("ADMIN_PASSWORD must be at least 10 characters; no admin was created")
        return
    ctx.db.insert("officers", {"email": s.admin_email.strip().lower(), "name": s.admin_name, "role": "admin",
                               "password_hash": auth.hash_password(s.admin_password), "active": 1,
                               "created_at": svc.iso(svc.now())})
    log.info("created admin account %s", s.admin_email)


def sync_wards(ctx: svc.Ctx) -> None:
    import json

    for w in ctx.wards:
        ctx.db.execute("INSERT OR REPLACE INTO wards (code, name, geometry) VALUES (?, ?, ?)",
                       (w.code, w.name, json.dumps(w.polygons)))
    ctx.ward_names.update({w.code: w.name for w in ctx.wards})


def build_context(settings: Settings, inspector: Inspector | None = None) -> svc.Ctx:
    db = Database(settings.data_dir / "rastescan.db")
    storage = S3Storage(settings.s3_bucket, settings.aws_region) if settings.s3_bucket else LocalStorage(settings.data_dir / "photos")
    ctx = svc.Ctx(
        settings=settings, db=db, storage=storage, inspector=inspector or make_inspector(settings),
        wards=load_wards(settings.wards_file), secret=auth.load_secret(settings.secret_key, settings.data_dir),
        limiter=RateLimiter(settings.reports_per_hour), login_limiter=RateLimiter(settings.logins_per_15min, 900),
    )
    sync_wards(ctx)
    seed_admin(ctx)
    return ctx


def create_app(settings: Settings | None = None, inspector: Inspector | None = None) -> FastAPI:
    settings = settings or Settings()
    ctx = build_context(settings, inspector)
    @asynccontextmanager
    async def lifespan(_app):
        stop = threading.Event()

        def worker():
            while not stop.wait(settings.rescan_every_s):
                try:
                    svc.process_pending(ctx)
                except Exception:  # noqa: BLE001 - never let the worker die
                    log.exception("pending-scan worker error")

        if settings.rescan_every_s > 0:
            threading.Thread(target=worker, name="pending-scan", daemon=True).start()
        yield
        stop.set()

    app = FastAPI(title="RasteScan API", description="Public road damage reports and the city's repair queue.", lifespan=lifespan)
    app.state.ctx = ctx
    cors = {"allow_origins": ["*"] if "*" in settings.cors_origins else settings.cors_origins,
            "allow_methods": ["*"], "allow_headers": ["*"], "expose_headers": ["ETag"]}
    if settings.cors_allow_lan:
        cors["allow_origin_regex"] = LAN_ORIGIN
    app.add_middleware(CORSMiddleware, **cors)
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def long_cache_for_built_assets(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/assets/") and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"  # file names carry a content hash
        return response
    app.include_router(routes_citizen.router)
    app.include_router(routes_public.router)
    app.include_router(routes_officer.router)
    app.include_router(routes_models.router)

    if isinstance(ctx.storage, LocalStorage):
        @app.get("/api/photos/{key}")
        def photo(key: str):
            path = ctx.storage.path(key)
            if "/" in key or ".." in key or not path.is_file():
                raise HTTPException(404, "Photo not found.")
            return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})

    # ---------- web app ----------
    dist = settings.web_dist
    if dist.is_dir():
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                raise HTTPException(404)
            file = (dist / path).resolve()
            if path and file.is_file() and dist.resolve() in file.parents:
                cache = "no-cache" if path in ("sw.js", "index.html") else "public, max-age=3600"
                return FileResponse(file, headers={"Cache-Control": cache})
            return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})

    return app
