"""Keep a running RasteScan alive during a demo: citizens report, crews are assigned, repairs are marked fixed.

Start the API with a higher report limit and a PIN, then run this in another terminal:

    REPORTS_PER_HOUR=2000 make api
    make live-demo                                   # or: backend/.venv/bin/python scripts/live_demo.py --every 8

Everything it creates is an ordinary report, so the live feed, map, impact page and queue all move. Photos are drawn
(no real roads), so use it on a demo database only (see `make seed-demo`). Stop with Ctrl+C.
"""
import argparse
import random
import sys
import time
import uuid
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
from seed_demo import CREWS, HAZARDS, W, H, asphalt, draw_hazard, jpeg  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000")
    ap.add_argument("--pin", default="1234", help="the DASHBOARD_PIN the API was started with")
    ap.add_argument("--every", type=float, default=8, help="seconds between events")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    rng = random.Random(args.seed)
    staff = {"X-Dashboard-Pin": args.pin, "X-Requested-With": "RasteScan"}
    weights = [HAZARDS[h][0] for h in HAZARDS]
    kinds = list(HAZARDS)

    with httpx.Client(base_url=args.api, timeout=120) as c:
        wards = c.get("/api/public/config").json()["wards"]
        print(f"Driving {args.api} with {len(wards)} wards. Ctrl+C to stop.")
        n = 0
        while True:
            n += 1
            try:
                # Most ticks a citizen reports; now and then a crew is assigned or a repair is finished.
                roll = rng.random()
                open_rows = c.get("/api/public/reports", params={"status": "open", "per_page": 200}).json()["items"]
                if roll < 0.6 or not open_rows:
                    ward = rng.choice(wards)
                    lat, lng = ward["lat"] + rng.uniform(-0.004, 0.004), ward["lng"] + rng.uniform(-0.004, 0.004)
                    img = asphalt(rng)
                    draw_hazard(img, rng.choices(kinds, weights)[0], rng)
                    r = c.post("/api/reports", data={"device_id": uuid.uuid4().hex, "lat": f"{lat:.6f}", "lng": f"{lng:.6f}"},
                               files={"photo": ("p.jpg", jpeg(img), "image/jpeg")})
                    print(f"[{n}] reported  -> {r.status_code} {r.json().get('code', r.text[:80]) if r.is_success else ''}")
                elif roll < 0.85:
                    pick = rng.choice([x for x in open_rows if x["public_status"] == "ai_verified"] or open_rows)
                    r = c.post(f"/api/v2/officer/reports/{pick['code']}/assign", json={"assignee": rng.choice(CREWS)}, headers=staff)
                    print(f"[{n}] assigned  -> {pick['code']} {r.status_code}")
                else:
                    pick = rng.choice([x for x in open_rows if x["public_status"] == "assigned"] or open_rows)
                    r = c.post(f"/api/v2/officer/reports/{pick['code']}/status", json={"status": "verified"}, headers=staff)
                    print(f"[{n}] resolved  -> {pick['code']} {r.status_code}")
            except httpx.HTTPError as exc:
                print(f"[{n}] API not reachable yet: {exc}")
            time.sleep(args.every)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
