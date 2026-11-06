"""Fill the portal with realistic DEMO reports for the expo, so it looks alive without real data.

Every row is stored with is_demo = 1 and shows a "Demo data" badge and a banner on the portal.
No AI calls are made: photos are drawn here and the inspection results are written directly.

    backend/.venv/bin/python scripts/seed_demo.py --demo            # add 40 demo reports
    backend/.venv/bin/python scripts/seed_demo.py --demo --count 60
    backend/.venv/bin/python scripts/seed_demo.py --remove          # delete every demo report again

It refuses to add demo data next to real reports unless you also pass --allow-mix.
Uses the same DATA_DIR / S3_BUCKET / WARDS_FILE settings as the server.
"""
import argparse
import io
import json
import math
import random
import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import services as svc  # noqa: E402
from app import triage  # noqa: E402
from app.config import Settings  # noqa: E402
from app.inspector import FakeInspector  # noqa: E402
from app.main import build_context  # noqa: E402
from app.schema import Inspection, urgency_for  # noqa: E402

W, H = 1024, 768
CREWS = ["Crew 1 (Ravi)", "Crew 2 (Meena)", "Crew 3 (Imran)", "Night crew (Suresh)"]
OFFICER = "Ward engineer (demo)"
HAZARDS = {
    # hazard: (weight, severity range, repair text, hours, width range, depth)
    "Pothole": (10, (4.5, 8.8), "Saw-cut to a rectangle, clean, tack coat, hot-mix asphalt in layers, roller compaction.", 3, (40, 120), "Deep"),
    "Open Manhole": (3, (9.2, 9.9), "Barricade now; install a heavy-duty ductile iron cover and frame, re-bed in rapid-set mortar.", 6, (55, 70), "Sub-base Breach"),
    "Road Fissure": (6, (2.0, 5.5), "Rout and seal cracks with hot-poured bitumen sealant.", 2, (80, 300), "Shallow"),
    "Waterlogging": (4, (5.0, 9.3), "Clear the side drain and inlet, then inspect the surface for hidden potholes.", 4, (150, 500), "Moderate"),
    "Debris": (3, (2.5, 6.0), "Remove debris and sweep the lane; check for damage underneath.", 1, (60, 200), "Shallow"),
    "Slab Displacement": (3, (4.0, 7.5), "Lift and re-bed the displaced slabs on a fresh mortar bed; grout joints.", 5, (60, 150), "Moderate"),
}
COMMENTS = [
    "Crew will reach the site by 4 pm today.",
    "Material ordered; repair planned for tomorrow morning.",
    "Barricades placed. Permanent repair scheduled.",
    "Drain cleared; checking the road surface after the water goes down.",
]


def asphalt(rng: random.Random) -> Image.Image:
    base = rng.randint(78, 98)
    img = Image.new("RGB", (W, H), (base, base + 2, base + 4))
    d = ImageDraw.Draw(img)
    for _ in range(26000):
        v = base + rng.randint(-28, 28)
        x, y = rng.randrange(W), rng.randrange(H)
        d.point((x, y), (v, v, v + 2))
    d.rectangle((W // 2 - 8, 0, W // 2 + 8, H), fill=(214, 178, 40))
    for y in range(0, H, 140):
        d.rectangle((W // 2 - 8, y + 80, W // 2 + 8, y + 140), fill=(base, base + 2, base + 4))
    return img


def draw_hazard(img: Image.Image, hazard: str, rng: random.Random) -> tuple[int, int, int, int]:
    """Draws the damage and returns its box in the model's 0-1000 (ymin, xmin, ymax, xmax) coordinates."""
    d = ImageDraw.Draw(img)
    cx, cy = rng.randint(300, 720), rng.randint(420, 600)
    if hazard == "Pothole":
        rx, ry = rng.randint(110, 200), rng.randint(60, 110)
        pts = [(cx + rx * (1 + rng.uniform(-0.2, 0.2)) * math.cos(a / 20 * 6.283),
                cy + ry * (1 + rng.uniform(-0.2, 0.2)) * math.sin(a / 20 * 6.283)) for a in range(20)]
        d.polygon(pts, fill=(118, 112, 100))
        d.polygon([(cx + (x - cx) * 0.8, cy + (y - cy) * 0.75) for x, y in pts], fill=(32, 32, 30))
        box = (cx - rx, cy - ry, cx + rx, cy + ry)
    elif hazard == "Open Manhole":
        r = rng.randint(80, 100)
        d.ellipse((cx - r, cy - r * 0.8, cx + r, cy + r * 0.8), fill=(140, 140, 136))
        d.ellipse((cx - r * 0.82, cy - r * 0.65, cx + r * 0.82, cy + r * 0.65), fill=(8, 8, 8))
        box = (cx - r, cy - r * 0.8, cx + r, cy + r * 0.8)
    elif hazard == "Road Fissure":
        x, y = cx - 260, cy
        xs, ys = [x], [y]
        while x < cx + 260:
            x += rng.randint(15, 35)
            y += rng.randint(-18, 18)
            xs.append(x)
            ys.append(y)
        d.line(list(zip(xs, ys)), fill=(28, 28, 26), width=7)
        box = (min(xs), min(ys) - 12, max(xs), max(ys) + 12)
    elif hazard == "Waterlogging":
        rx, ry = rng.randint(250, 340), rng.randint(90, 140)
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(92, 112, 128))
        d.ellipse((cx - rx * 0.6, cy - ry * 0.5, cx + rx * 0.2, cy - ry * 0.1), fill=(150, 170, 185))
        box = (cx - rx, cy - ry, cx + rx, cy + ry)
    elif hazard == "Debris":
        pts = []
        for _ in range(14):
            x, y, r = cx + rng.randint(-170, 170), cy + rng.randint(-70, 70), rng.randint(18, 40)
            shade = rng.randint(110, 170)
            d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=(shade, shade - 15, shade - 35))
            pts.append((x, y, r))
        box = (min(p[0] - p[2] for p in pts), min(p[1] - p[2] for p in pts), max(p[0] + p[2] for p in pts), max(p[1] + p[2] for p in pts))
    else:  # Slab Displacement
        x0, y0 = cx - 220, cy - 110
        for i in range(3):
            off = rng.randint(-14, 14) if i == 1 else 0
            d.rectangle((x0 + i * 150, y0 + off, x0 + i * 150 + 140, y0 + 220 + off), fill=(176, 172, 162), outline=(70, 70, 66), width=4)
        box = (x0, y0 - 14, x0 + 440, y0 + 234)
    x0, y0, x1, y1 = box
    clamp = lambda v: max(0, min(1000, int(v)))  # noqa: E731
    return clamp(y0 / H * 1000), clamp(x0 / W * 1000), clamp(y1 / H * 1000), clamp(x1 / W * 1000)


def repaired(img: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """The same scene with a fresh, darker patch where the damage was."""
    after = img.copy()
    ymin, xmin, ymax, xmax = box
    d = ImageDraw.Draw(after)
    d.rectangle((xmin / 1000 * W - 20, ymin / 1000 * H - 20, xmax / 1000 * W + 20, ymax / 1000 * H + 20), fill=(52, 54, 56))
    return after.filter(ImageFilter.GaussianBlur(0.6))


def jpeg(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return buf.getvalue()


def clean_result() -> Inspection:
    return Inspection.model_validate({
        "hazard_type": "None", "confidence": 0.9, "severity_score": 1.0, "urgency_level": "LOW",
        "repair_recommendation": "No repair needed.", "estimated_repair_time_hours": 0,
        "estimated_dimensions": {"width_cm": 0, "depth_category": "Shallow"},
        "bounding_box": {"ymin": 0, "xmin": 0, "ymax": 0, "xmax": 0},
    })


def seed(ctx: svc.Ctx, count: int, rng: random.Random) -> None:
    if not ctx.wards:
        sys.exit("No wards loaded; demo reports need data/wards.geojson (or WARDS_FILE).")
    now = svc.now()
    names = list(HAZARDS)
    weights = [HAZARDS[h][0] for h in names]
    for i in range(count):
        hazard = rng.choices(names, weights)[0]
        _, (lo, hi), rec, hours, (w0, w1), depth = HAZARDS[hazard]
        severity = round(rng.uniform(lo, hi), 1)
        img = asphalt(rng)
        box = draw_hazard(img, hazard, rng)
        result = Inspection.model_validate({
            "hazard_type": hazard, "confidence": round(rng.uniform(0.78, 0.97), 2), "severity_score": severity,
            "urgency_level": "LOW", "repair_recommendation": rec, "estimated_repair_time_hours": hours,
            "estimated_dimensions": {"width_cm": rng.randint(w0, w1), "depth_category": depth},
            "bounding_box": dict(zip(("ymin", "xmin", "ymax", "xmax"), box)),
        })
        result = result.model_copy(update={"urgency_level": urgency_for(result)})
        ward = rng.choice(ctx.wards)
        b = ward.bbox
        lat, lng = rng.uniform(b[1] + 0.002, b[3] - 0.002), rng.uniform(b[0] + 0.002, b[2] - 0.002)
        created = now - timedelta(days=rng.uniform(0.05, 28))
        row = svc.create_report(ctx, jpeg(img), lat, lng, device_id=None, is_demo=True, created=created, result=result)
        if row["status"] != "new":
            continue
        rid, urgency = row["id"], row["urgency"]
        sla_h = triage.SLA_HOURS[urgency]
        age_h = (now - created).total_seconds() / 3600
        roll = rng.random()

        def at(hours_after: float):
            return created + timedelta(hours=min(hours_after, age_h - 0.05))

        for _ in range(rng.choice([0, 0, 1, 2, 4])):
            ctx.db.insert("votes", {"report_id": rid, "device_hash": f"demo-{rng.getrandbits(64):x}", "created_at": svc.iso(at(rng.uniform(1, 30)))})
        if roll < 0.12 or age_h < 3:
            continue  # brand new, nobody has touched it yet
        crew = rng.choice(CREWS)
        t_assign = at(rng.uniform(0.5, min(12, sla_h / 3)))
        ctx.db.execute("UPDATE reports SET assignee = ?, status = 'assigned', updated_at = ? WHERE id = ?", (crew, svc.iso(t_assign), rid))
        svc.record(ctx, rid, "assigned", OFFICER, new=crew, at=t_assign)
        svc.record(ctx, rid, "status", OFFICER, old="new", new="assigned", at=t_assign)
        if rng.random() < 0.35:
            t_c = at((t_assign - created).total_seconds() / 3600 + rng.uniform(0.5, 6))
            ctx.db.insert("comments", {"report_id": rid, "officer_id": None, "author": OFFICER, "body": rng.choice(COMMENTS), "created_at": svc.iso(t_c)})
        if roll < 0.22:
            continue  # assigned, still waiting
        if roll < 0.27:
            t_d = at(rng.uniform(2, 24))
            reason = "Private road inside a layout; referred to the owners' association."
            ctx.db.execute("UPDATE reports SET status = 'dismissed', dismiss_reason = ?, updated_at = ? WHERE id = ?", (reason, svc.iso(t_d), rid))
            svc.record(ctx, rid, "status", OFFICER, old="assigned", new="dismissed", detail={"reason": reason}, at=t_d)
            continue
        # Repaired: mostly within the deadline, some late.
        fix_h = sla_h * (rng.uniform(0.3, 0.95) if rng.random() < 0.8 else rng.uniform(1.05, 1.6))
        if fix_h >= age_h - 0.1:
            continue  # not repaired yet; may already be past its deadline
        t_fix = at(fix_h)
        after_key = svc.store_photo(ctx, jpeg(repaired(img, box)))
        ctx.db.execute("UPDATE reports SET after_photo_key = ?, after_ai_json = ?, status = 'verified', resolved_at = ?, updated_at = ? WHERE id = ?",
                       (after_key, clean_result().model_dump_json(), svc.iso(t_fix), svc.iso(t_fix), rid))
        svc.record(ctx, rid, "repair_photo", crew, detail={"checked": True, "hazard_type": "None", "severity": 1.0}, at=t_fix)
        svc.record(ctx, rid, "verified", svc.AI, old="assigned", new="verified", detail={"hazard_type": "None", "severity": 1.0}, at=t_fix)
    print(f"Added {count} demo reports.")


def remove(ctx: svc.Ctx) -> None:
    ids = [r["id"] for r in ctx.db.query("SELECT id FROM reports WHERE is_demo = 1")]
    if not ids:
        print("No demo reports found.")
        return
    marks = ",".join("?" for _ in ids)
    for table in ("status_history", "comments", "votes"):
        ctx.db.execute(f"DELETE FROM {table} WHERE report_id IN ({marks})", tuple(ids))
    ctx.db.execute(f"UPDATE reports SET parent_id = NULL WHERE parent_id IN ({marks})", tuple(ids))
    ctx.db.execute(f"DELETE FROM reports WHERE id IN ({marks})", tuple(ids))
    print(f"Removed {len(ids)} demo reports.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--demo", action="store_true", help="required: confirms you want DEMO data")
    ap.add_argument("--count", type=int, default=40)
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--remove", action="store_true", help="delete all demo reports")
    ap.add_argument("--allow-mix", action="store_true", help="add demo data even if real reports exist")
    args = ap.parse_args()
    # No AI is used here, whatever AI_MODE says.
    ctx = build_context(replace(Settings(), ai_mode="fake"), FakeInspector())
    if args.remove:
        remove(ctx)
        return
    if not args.demo:
        sys.exit("Refusing to run without --demo. Demo data must be added on purpose.")
    real = ctx.db.scalar("SELECT COUNT(*) FROM reports WHERE is_demo = 0")
    if real and not args.allow_mix:
        sys.exit(f"This database already has {real} real reports. Use a separate DATA_DIR, or pass --allow-mix.")
    seed(ctx, args.count, random.Random(args.seed))
    print(json.dumps(svc.stats(ctx), indent=1))


if __name__ == "__main__":
    main()
