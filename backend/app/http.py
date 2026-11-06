"""Small HTTP helpers shared by the route modules."""
import hashlib
import json

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from .services import Ctx


def get_ctx(request: Request) -> Ctx:
    return request.app.state.ctx


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def client_key(request: Request, device_id: str | None) -> str:
    return f"dev:{device_id[:64]}" if device_id else "ip:" + client_ip(request)


async def read_photo(ctx: Ctx, photo: UploadFile) -> bytes:
    limit = ctx.settings.max_upload_mb * 1024 * 1024
    data = await photo.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Photo is larger than {ctx.settings.max_upload_mb} MB. Take it again at a lower resolution.")
    if not data:
        raise HTTPException(400, "The photo is empty.")
    return data


def cached_json(request: Request, payload, max_age: int = 30) -> Response:
    """Short public caching with an ETag, so phones on slow networks can skip unchanged data."""
    body = json.dumps(payload, separators=(",", ":"), default=str).encode()
    etag = '"' + hashlib.sha1(body).hexdigest()[:20] + '"'
    headers = {"ETag": etag, "Cache-Control": f"public, max-age={max_age}"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


def no_store(payload) -> JSONResponse:
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})
