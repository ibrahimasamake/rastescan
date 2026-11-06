"""Add ~200 real-road DEMO reports from across India, using photos from the open RDD2022 road damage dataset.

    backend/.venv/bin/python scripts/seed_india.py --demo            # add the reports
    backend/.venv/bin/python scripts/seed_india.py --remove          # take every demo report out again (same as seed_demo.py)

What is real and what is not:
  * The photos are real Indian road photos (RDD2022, faces and plates already blurred). See data/india-cases/ATTRIBUTION.md.
  * The damage boxes come from the dataset's own human labels. Severity, size and cost are worked out from them by
    simple rules. No AI model is run, so these are NOT model results.
  * The photos carry no GPS. Each report is placed at a random spot in one of 20 Indian cities (or the Bengaluru
    demo wards), so locations are made up. Every report is stored with is_demo = 1 and shows the Demo badge.
Uses the same DATA_DIR / S3_BUCKET settings as the server, and data/wards-india.geojson for the city areas.
"""
import argparse
import json
import math
import random
import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from seed_demo import COMMENTS, CREWS, HAZARDS, OFFICER, remove  # noqa: E402

from app import services as svc  # noqa: E402
from app import triage  # noqa: E402
from app.config import Settings  # noqa: E402
from app.inspector import FakeInspector  # noqa: E402
from app.main import build_context  # noqa: E402
from app.schema import BoundingBox, Detection, combine  # noqa: E402

CASES = ROOT / "data" / "india-cases"
WARDS = ROOT / "data" / "wards-india.geojson"
# RDD2022 classes that are damage. D43/D44/D50 (crosswalk and line blur, utility cover) are not.
POTHOLE = {"D40"}
CRACK = {"D00", "D01", "D10", "D11", "D20"}
# Share of the demo reports per city, roughly by population. "BLR" means the six Bengaluru demo wards.
CITY_WEIGHT = {"BLR": 12, "IN-MUM": 10, "IN-DEL": 10, "IN-HYD": 8, "IN-MAA": 8, "IN-CCU": 8, "IN-PNQ": 6, "IN-AMD": 6, "IN-JAI": 5,
               "IN-LKO": 5, "IN-NAG": 4, "IN-IDR": 4, "IN-BHO": 3, "IN-PAT": 4, "IN-STV": 4, "IN-VTZ": 4, "IN-COK": 3, "IN-GAU": 3,
               "IN-BBI": 3, "IN-IXC": 2, "IN-CJB": 3}


def detection(cls: str, box: tuple, w: int, h: int, rng: random.Random) -> Detection:
    x0, y0, x1, y1 = box
    share = max(0.0001, (x1 - x0) * (y1 - y0) / (w * h))
    pothole = cls in POTHOLE
    kind = "Pothole" if pothole else "Road Fissure"
    _, _, rec, hours, _, _ = HAZARDS[kind]
    if pothole:
        severity = min(9.6, max(4.0, 3.6 + 18 * math.sqrt(share) + rng.uniform(-0.4, 0.4)))
        depth = "Shallow" if severity < 5.5 else "Moderate" if severity < 7.5 else "Deep" if severity < 9.0 else "Sub-base Breach"
    else:
        severity = min(6.5, max(2.5, 2.2 + 12 * math.sqrt(share) + rng.uniform(-0.3, 0.3)))
        depth = "Shallow"
    scale = 1000
    return Detection.model_validate({
        "hazard_type": kind, "confidence": round(rng.uniform(0.8, 0.96), 2), "severity_score": round(severity, 1),
        "urgency_level": "LOW", "repair_recommendation": rec, "estimated_repair_time_hours": hours,
        # The road is assumed to be about 3.5 m across the photo; only a rough size.
        "estimated_dimensions": {"width_cm": int(min(250, max(15, (x1 - x0) / w * 350))), "depth_category": depth},
        "bounding_box": {"ymin": int(y0 * scale / h), "xmin": int(x0 * scale / w), "ymax": int(y1 * scale / h), "xmax": int(x1 * scale / w)},
    })


def place(ctx: svc.Ctx, key: str, rng: random.Random) -> tuple[float, float]:
    if key == "BLR":
        ward = rng.choice([w for w in ctx.wards if w.code.startswith("W")])
    else:
        ward = next(w for w in ctx.wards if w.code == key)
    b = ward.bbox
    pad = 0.003 if key == "BLR" else 0.02
    return rng.uniform(b[1] + pad, b[3] - pad), rng.uniform(b[0] + pad, b[2] - pad)


def seed(ctx: svc.Ctx, rng: random.Random) -> None:
    cases = json.loads((CASES / "selection.json").read_text())
    rng.shuffle(cases)
    # Cities in proportion to their weights (largest remainder), then shuffled, so the spread is even rather than lucky.
    total = sum(CITY_WEIGHT.values())
    quota = {k: len(cases) * w / total for k, w in CITY_WEIGHT.items()}
    plan = [k for k, q in quota.items() for _ in range(int(q))]
    plan += sorted(quota, key=lambda k: quota[k] - int(quota[k]), reverse=True)[:len(cases) - len(plan)]
    rng.shuffle(plan)
    now = svc.now()
    added = 0
    for case, city in zip(cases, plan):
        dets = [detection(o[0], o[1:], case["w"], case["h"], rng) for o in case["objs"] if o[0] in POTHOLE | CRACK]
        if not dets:
            continue
        result = combine(dets)
        lat, lng = place(ctx, city, rng)
        created = now - timedelta(days=rng.uniform(0.05, 9))
        jpeg = (CASES / "img" / case["file"]).read_bytes()
        row = svc.create_report(ctx, jpeg, lat, lng, device_id=None, is_demo=True, created=created, result=result)
        added += 1
        if row["status"] != "new":
            continue
        rid, urgency = row["id"], row["urgency"]
        age_h = (now - created).total_seconds() / 3600
        sla_h = triage.SLA_HOURS[urgency]

        def at(hours_after: float):
            return created + timedelta(hours=min(hours_after, age_h - 0.05))

        for _ in range(rng.choice([0, 0, 1, 2, 3, 5])):
            ctx.db.insert("votes", {"report_id": rid, "device_hash": f"india-{rng.getrandbits(64):x}", "created_at": svc.iso(at(rng.uniform(1, 40)))})
        roll = rng.random()
        if roll < 0.45 or age_h < 3:
            continue  # reported, nobody has touched it yet
        crew = rng.choice(CREWS)
        t_assign = at(rng.uniform(0.5, min(24, sla_h / 2)))
        if roll > 0.96:
            reason = "Private road; referred to the owners."
            ctx.db.execute("UPDATE reports SET status = 'dismissed', dismiss_reason = ?, updated_at = ? WHERE id = ?", (reason, svc.iso(t_assign), rid))
            svc.record(ctx, rid, "status", OFFICER, old="new", new="dismissed", detail={"reason": reason}, at=t_assign)
            continue
        ctx.db.execute("UPDATE reports SET assignee = ?, status = 'assigned', updated_at = ? WHERE id = ?", (crew, svc.iso(t_assign), rid))
        svc.record(ctx, rid, "assigned", OFFICER, new=crew, at=t_assign)
        svc.record(ctx, rid, "status", OFFICER, old="new", new="assigned", at=t_assign)
        if rng.random() < 0.3:
            ctx.db.insert("comments", {"report_id": rid, "officer_id": None, "author": OFFICER, "body": rng.choice(COMMENTS),
                                       "created_at": svc.iso(at((t_assign - created).total_seconds() / 3600 + rng.uniform(0.5, 6)))})
    print(f"Added {added} India demo reports.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--demo", action="store_true", help="required: confirms you want DEMO data")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--remove", action="store_true", help="delete all demo reports")
    ap.add_argument("--allow-mix", action="store_true", help="add demo data even if real reports exist")
    args = ap.parse_args()
    ctx = build_context(replace(Settings(), ai_mode="fake", wards_file=WARDS), FakeInspector())
    if args.remove:
        remove(ctx)
        return
    if not args.demo:
        sys.exit("Refusing to run without --demo. Demo data must be added on purpose.")
    real = ctx.db.scalar("SELECT COUNT(*) FROM reports WHERE is_demo = 0")
    if real and not args.allow_mix:
        sys.exit(f"This database already has {real} real reports. Use a separate DATA_DIR, or pass --allow-mix.")
    seed(ctx, random.Random(args.seed))
    print(json.dumps(svc.stats(ctx), indent=1))


if __name__ == "__main__":
    main()
