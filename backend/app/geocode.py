"""PIN code, state, district and road for a point, from OpenStreetMap's public Nominatim service.

Nominatim's usage policy allows at most one request a second, with the application identified. Every lookup here is spaced out
under one lock, and services.address keeps the answers, so each location is only ever asked for once.
"""
from __future__ import annotations

import logging
import threading
import time

import httpx

log = logging.getLogger("rastescan.geocode")

MIN_GAP_S = 1.1
WAIT_FOR_TURN_S = 10.0
_turn = threading.Lock()
_last = 0.0


def _first(address: dict, *keys: str) -> str | None:
    for key in keys:
        if address.get(key):
            return str(address[key])
    return None


def reverse(url: str, lat: float, lng: float) -> dict | None:
    """The nearest known address to a point, or None if the service did not answer. Failures are not errors for the reader."""
    global _last
    if not _turn.acquire(timeout=WAIT_FOR_TURN_S):
        return None
    try:
        wait = MIN_GAP_S - (time.monotonic() - _last)
        if wait > 0:
            time.sleep(wait)
        try:
            res = httpx.get(
                url,
                params={"format": "jsonv2", "zoom": 18, "addressdetails": 1, "accept-language": "en", "lat": lat, "lon": lng},
                headers={"User-Agent": "RasteScan/1.0 (public road repair portal)"},
                timeout=8,
            )
            res.raise_for_status()
            found = res.json().get("address")
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("address lookup failed: %s", type(exc).__name__)
            return None
        finally:
            _last = time.monotonic()
    finally:
        _turn.release()
    if not isinstance(found, dict):
        found = {}  # the service answered and knows nothing here (open water, say): keep that, so this point is not asked again
    return {
        "pin": _first(found, "postcode"),
        "state": _first(found, "state", "territory"),
        "district": _first(found, "state_district", "county", "city_district"),
        "city": _first(found, "city", "town", "municipality"),
        "area": _first(found, "suburb", "neighbourhood", "village", "hamlet", "quarter"),
        "road": _first(found, "road"),
    }
