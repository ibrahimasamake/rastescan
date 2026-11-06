"""Mark some DEMO reports as repaired, each with an after photo, so the portal can show finished work.

    backend/.venv/bin/python scripts/seed_fixed.py --demo             # about 45 repairs across the cities
    backend/.venv/bin/python scripts/seed_fixed.py --demo --count 20

What is real and what is not:
  * The after photos are SIMULATED: the report's own photo with the road inside its damage boxes resurfaced by this script.
    Nobody repaired these roads and no AI checked them. They show what the feature looks like, and are not evidence of a repair.
  * Only reports stored with is_demo = 1 are touched. They keep the Demo badge, and the report page says the photo is simulated.
  * `make unseed-demo` removes them along with the other demo reports.
Uses the same DATA_DIR / S3_BUCKET settings as the server. Safe to run while the server is running.
"""
import argparse
import json
import random
import sys
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from seed_demo import CREWS, OFFICER, clean_result  # noqa: E402

from app import services as svc  # noqa: E402
from app import triage  # noqa: E402
from app.config import Settings  # noqa: E402
from app.inspector import FakeInspector  # noqa: E402
from app.main import build_context  # noqa: E402

WARDS = ROOT / "data" / "wards-india.geojson"


def resurfaced(jpeg: bytes, boxes: list[dict], seed: int) -> bytes | None:
    """The same photo with fresh, darker, smoother asphalt on the road inside the boxes. Vehicles and verges keep their pixels,
    because only pixels that look like road surface are changed. None if the boxes hold too little road to look like a repair."""
    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    area = np.zeros((h, w), np.uint8)
    pad = int(0.012 * w)
    for b in boxes:
        top, left, bottom, right = b["ymin"] * h // 1000, b["xmin"] * w // 1000, b["ymax"] * h // 1000, b["xmax"] * w // 1000
        cv2.rectangle(area, (max(0, left - pad), max(0, top - pad)), (min(w - 1, right + pad), min(h - 1, bottom + pad)), 255, -1)
    if not area.any():
        return None
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    brightness = np.median(hsv[area > 0][:, 2])
    road = ((hsv[..., 1] < 48) & (np.abs(hsv[..., 2].astype(int) - brightness) < 55)).astype(np.uint8) * 255
    road = cv2.bitwise_and(road, area)
    round_11 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    road = cv2.morphologyEx(cv2.morphologyEx(road, cv2.MORPH_CLOSE, round_11), cv2.MORPH_OPEN, round_11)
    if road.mean() / 255 < 0.015:
        return None
    alpha = cv2.GaussianBlur(road.astype(np.float32) / 255, (0, 0), max(5, w / 90))[..., None]
    fresh = cv2.bilateralFilter(cv2.medianBlur(img, 31), 9, 40, 9).astype(np.float32) * 0.74
    fresh += np.random.default_rng(seed).normal(0, 4.5, (h, w, 1)).astype(np.float32)
    out = img.astype(np.float32) * (1 - alpha) + np.clip(fresh, 0, 255) * alpha
    ok, buf = cv2.imencode(".jpg", np.clip(out, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 86])
    return buf.tobytes() if ok else None


def pick(rows: list[dict], count: int, rng: random.Random) -> list[dict]:
    """Taken in turn from each ward, so repairs are spread across the cities rather than bunched in one."""
    by_ward: dict[str, list[dict]] = {}
    for row in rows:
        by_ward.setdefault(row["ward_code"] or "", []).append(row)
    for group in by_ward.values():
        rng.shuffle(group)
    order: list[dict] = []
    while any(by_ward.values()):
        for code in sorted(by_ward):
            if by_ward[code]:
                order.append(by_ward[code].pop())
    return order[:count * 2]  # spares, for photos with too little road to resurface


def repair(ctx: svc.Ctx, row: dict, after: bytes, rng: random.Random) -> None:
    rid = row["id"]
    now = svc.now()
    created = svc.parse_iso(row["created_at"])
    age_h = (now - created).total_seconds() / 3600
    sla_h = triage.SLA_HOURS[row["urgency"]]
    # Mostly within the deadline, some late, and never in the future.
    fix_h = sla_h * (rng.uniform(0.3, 0.95) if rng.random() < 0.8 else rng.uniform(1.05, 1.6))
    if fix_h >= age_h - 0.1:
        fix_h = age_h * rng.uniform(0.4, 0.9)
    t_fix: datetime = created + timedelta(hours=fix_h)

    crew = row["assignee"]
    if crew:
        assigned = ctx.db.one("SELECT at FROM status_history WHERE report_id = ? AND event = 'assigned' ORDER BY at DESC LIMIT 1", (rid,))
        t_assign = svc.parse_iso(assigned["at"]) if assigned else created
        if t_fix <= t_assign:
            t_fix = t_assign + (now - t_assign) * rng.uniform(0.3, 0.9)
    else:
        crew = rng.choice(CREWS)
        t_assign = created + (t_fix - created) * rng.uniform(0.15, 0.5)
        ctx.db.execute("UPDATE reports SET assignee = ?, status = 'assigned', updated_at = ? WHERE id = ?", (crew, svc.iso(t_assign), rid))
        svc.record(ctx, rid, "assigned", OFFICER, new=crew, at=t_assign)
        svc.record(ctx, rid, "status", OFFICER, old="new", new="assigned", at=t_assign)

    key = svc.store_photo(ctx, after)
    done = svc.iso(t_fix)
    ctx.db.execute("UPDATE reports SET after_photo_key = ?, after_ai_json = ? WHERE id = ?", (key, clean_result().model_dump_json(), rid))
    ctx.db.execute("UPDATE reports SET status = 'verified', resolved_at = ?, updated_at = ? WHERE id = ? OR parent_id = ?", (done, done, rid, rid))
    detail = {"checked": True, "hazard_type": "None", "severity": 1.0, "simulated": True}
    svc.record(ctx, rid, "repair_photo", crew, detail=detail, at=t_fix)
    svc.record(ctx, rid, "verified", svc.AI, old="assigned", new="verified", detail=detail, at=t_fix)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--demo", action="store_true", help="required: confirms you want DEMO data")
    ap.add_argument("--count", type=int, default=45, help="how many repaired demo reports there should be in the end")
    ap.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args()
    if not args.demo:
        ap.error("add --demo to confirm: these repairs and their after photos are simulated")
    ctx = build_context(replace(Settings(), ai_mode="fake", wards_file=WARDS), FakeInspector())
    have = ctx.db.one("SELECT COUNT(*) AS n FROM reports WHERE is_demo = 1 AND parent_id IS NULL AND status = 'verified' AND after_photo_key IS NOT NULL")["n"]
    wanted = args.count - have
    if wanted <= 0:
        print(f"Already {have} repaired demo reports; nothing to do.")
        return
    rng = random.Random(args.seed + have)
    # Old enough for a repair to be believable; the newest reports stay open.
    cutoff = svc.iso(svc.now() - timedelta(hours=12))
    rows = ctx.db.query("SELECT * FROM reports WHERE is_demo = 1 AND parent_id IS NULL AND status IN ('new', 'assigned') AND created_at < ?", (cutoff,))
    added = 0
    for row in pick(rows, wanted, rng):
        if added >= wanted:
            break
        result = json.loads(row["ai_json"])
        boxes = [d["bounding_box"] for d in result.get("detections") or [result]]
        after = resurfaced(ctx.storage.load(row["photo_key"]), boxes, args.seed + row["id"])
        if after is None:
            continue
        repair(ctx, row, after, rng)
        added += 1
    print(f"Marked {added} demo reports as repaired, with simulated after photos.")


if __name__ == "__main__":
    main()
