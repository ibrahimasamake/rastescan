"""Pixel-level analysis of a road photo, done before and after the AI looks at it.

Classical computer vision, no model and no network. It does three jobs:
  * finds the road surface (grey, unsaturated, connected to the bottom of the photo),
  * finds places on that surface that differ from the surrounding asphalt (dark pits, light water-filled holes),
  * checks and tightens the boxes the AI returns: a box on a car, the sky or intact road is rejected, a box that is
    a bit off is snapped to the damaged patch under it.
It is approximate (a grey car on the road can look like road), so the AI keeps the final say on what is a defect; this
only gives it better hints and removes boxes that have no pixel evidence at all.
All boxes use the app's 0-1000 coordinates: (ymin, xmin, ymax, xmax) from the top-left corner.
"""
from dataclasses import dataclass

import cv2
import numpy as np

from .schema import BoundingBox, Detection

WORK_SIDE = 640  # analysis runs on a copy no larger than this, so it costs milliseconds


@dataclass
class PixelMap:
    road: np.ndarray      # bool, True where the pixel looks like road surface
    anomaly: np.ndarray   # bool, road pixels that are much lighter or darker than the asphalt around them
    edges: np.ndarray     # bool, strong edges on the road (cracks, hole rims)
    strength: np.ndarray  # float, how far each pixel is from its local asphalt tone

    @property
    def size(self) -> tuple[int, int]:
        return self.road.shape[1], self.road.shape[0]

    # ---- helpers
    def _px(self, b: BoundingBox) -> tuple[int, int, int, int]:
        w, h = self.size
        return (max(0, round(b.ymin * h / 1000)), min(h, max(1, round(b.ymax * h / 1000))),
                max(0, round(b.xmin * w / 1000)), min(w, max(1, round(b.xmax * w / 1000))))

    def _box(self, y0: int, y1: int, x0: int, x1: int) -> BoundingBox:
        w, h = self.size
        return BoundingBox(ymin=round(1000 * y0 / h), xmin=round(1000 * x0 / w), ymax=round(1000 * y1 / h), xmax=round(1000 * x1 / w))

    # ---- candidates for the AI
    def candidates(self, limit: int = 12) -> list[BoundingBox]:
        """Compact patches of the road that look like holes or water-filled holes, biggest and strongest first."""
        h, w = self.road.shape
        mask = cv2.morphologyEx(self.anomaly.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        found = []
        for i in range(1, n):
            x, y, bw, bh, area = stats[i]
            share = area / (w * h)
            if not 0.0006 <= share <= 0.12 or area / max(1, bw * bh) < 0.28 or max(bw, bh) / max(1, min(bw, bh)) > 6:
                continue
            score = float(self.strength[labels == i].mean()) * area ** 0.5
            found.append((score, self._box(y, y + bh, x, x + bw)))
        return [b for _, b in sorted(found, key=lambda t: -t[0])[:limit]]

    def hint(self) -> str:
        boxes = self.candidates()
        if not boxes:
            return ""
        listed = "; ".join(f"[{b.ymin}, {b.xmin}, {b.ymax}, {b.xmax}]" for b in boxes)
        return ("Pixel analysis of this photo (approximate computer vision, not an AI) found these candidate patches on the road "
                f"surface as [ymin, xmin, ymax, xmax]: {listed}. Some may be vehicles, shadows, stains or road paint. Check each "
                "one yourself, keep only real defects with a tight box, and also report any real defect that is not listed.")

    # ---- checking the AI's boxes
    def evidence(self, b: BoundingBox) -> dict:
        y0, y1, x0, x1 = self._px(b)
        if y1 - y0 < 2 or x1 - x0 < 2:
            return {"road": 0.0, "anomaly": 0.0, "edges": 0.0}
        return {"road": float(self.road[y0:y1, x0:x1].mean()), "anomaly": float(self.anomaly[y0:y1, x0:x1].mean()),
                "edges": float(self.edges[y0:y1, x0:x1].mean())}

    def plausible(self, d: Detection) -> bool:
        """False for a box with no pixel evidence of road damage: not on the road, or nothing unusual inside it."""
        e = self.evidence(d.bounding_box)
        if e["road"] < 0.45:
            return False
        return e["anomaly"] >= 0.04 or e["edges"] >= 0.06

    def snap(self, d: Detection) -> Detection:
        """Tighten a box to the damaged patch under it, when the patch is close in size to the box the AI drew."""
        b = d.bounding_box
        y0, y1, x0, x1 = self._px(b)
        h, w = self.road.shape
        py, px = round((y1 - y0) * 0.15), round((x1 - x0) * 0.15)
        wy0, wy1, wx0, wx1 = max(0, y0 - py), min(h, y1 + py), max(0, x0 - px), min(w, x1 + px)
        window = cv2.morphologyEx(self.anomaly[wy0:wy1, wx0:wx1].astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        n, labels, stats, _ = cv2.connectedComponentsWithStats(window, connectivity=8)
        keep = []
        for i in range(1, n):
            x, y, bw, bh, area = stats[i]
            cy0, cx0 = y + wy0, x + wx0
            inside = max(0, min(cy0 + bh, y1) - max(cy0, y0)) * max(0, min(cx0 + bw, x1) - max(cx0, x0))
            if area >= 12 and inside / max(1, bw * bh) >= 0.4:
                keep.append((cy0, cy0 + bh, cx0, cx0 + bw))
        if not keep:
            return d
        ny0, ny1 = min(k[0] for k in keep), max(k[1] for k in keep)
        nx0, nx1 = min(k[2] for k in keep), max(k[3] for k in keep)
        ratio = ((ny1 - ny0) * (nx1 - nx0)) / max(1, (y1 - y0) * (x1 - x0))
        if not 0.35 <= ratio <= 2.0:
            return d
        my, mx = max(1, round((ny1 - ny0) * 0.04)), max(1, round((nx1 - nx0) * 0.04))
        return d.model_copy(update={"bounding_box": self._box(max(0, ny0 - my), min(h, ny1 + my), max(0, nx0 - mx), min(w, nx1 + mx))})

    def _patches_in(self, b: BoundingBox, patches: list[BoundingBox]) -> list[BoundingBox]:
        """The candidate patches that sit (mostly) inside the AI's box."""
        grow_y, grow_x = round((b.ymax - b.ymin) * 0.06), round((b.xmax - b.xmin) * 0.06)
        out = []
        for c in patches:
            inside = max(0, min(c.ymax, b.ymax + grow_y) - max(c.ymin, b.ymin - grow_y)) * max(0, min(c.xmax, b.xmax + grow_x) - max(c.xmin, b.xmin - grow_x))
            if inside / max(1, (c.ymax - c.ymin) * (c.xmax - c.xmin)) >= 0.6:
                out.append(c)
        return out

    def refine(self, d: Detection, patches: list[BoundingBox]) -> list[Detection]:
        """Turn one rough AI box into tight boxes on the real damaged patches inside it, keeping the AI's label.

        The AI is good at saying WHAT is wrong and how bad it is, and poor at saying exactly WHERE; the pixels are the
        opposite. For holes and water-filled holes the pixel patches therefore replace the AI's box (the biggest patch
        keeps the AI's severity, smaller ones are scaled down). Other kinds keep the AI's box, snapped to the damage."""
        if d.hazard_type not in ("Pothole", "Waterlogging"):
            return [self.snap(d)]
        inside = sorted(self._patches_in(d.bounding_box, patches), key=lambda c: -(c.ymax - c.ymin) * (c.xmax - c.xmin))[:4]
        if not inside:
            return [self.snap(d)]
        biggest = (inside[0].ymax - inside[0].ymin) * (inside[0].xmax - inside[0].xmin)
        out = []
        for c in inside:
            share = (c.ymax - c.ymin) * (c.xmax - c.xmin) / max(1, biggest)
            out.append(d.model_copy(update={"bounding_box": c, "severity_score": max(1.0, round(d.severity_score * (0.7 + 0.3 * min(1.0, share)), 1))}))
        return out

    def check(self, found: list[Detection]) -> list[Detection]:
        """Drop boxes with no pixel evidence, then put the rest on the real damaged patches. If that would drop everything,
        keep the AI's answer as it was."""
        patches = self.candidates(limit=24)
        good = [r for d in found if self.plausible(d) for r in self.refine(d, patches)]
        return good or found


def analyze(jpeg: bytes) -> PixelMap | None:
    img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = min(1.0, WORK_SIDE / max(h, w))
    if scale < 1:
        img = cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
        h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (3, 3), 0)

    # Road surface: unsaturated and neither near-black nor near-white, joined up from the bottom of the photo.
    s, v = hsv[..., 1], hsv[..., 2]
    colour = ((s < 90) & (v > 25) & (v < 225)).astype(np.uint8)
    colour = cv2.morphologyEx(colour, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    colour = cv2.morphologyEx(colour, cv2.MORPH_CLOSE, np.ones((max(3, w // 60),) * 2, np.uint8))
    n, labels, stats, _ = cv2.connectedComponentsWithStats(colour, connectivity=8)
    bottom = np.unique(labels[int(h * 0.9):, :])
    road = np.isin(labels, [i for i in bottom if i != 0 and stats[i, cv2.CC_STAT_AREA] > 0.01 * w * h])

    # Photos taken along a road show sky, then buildings and trees: road never starts above the horizon. The horizon is
    # taken as the low edge of the sky (bright, unsaturated, joined to the top of the photo), with a margin for what sits under it.
    sky = ((v > 165) & (s < 60)).astype(np.uint8)
    n_s, lab_s, st_s, _ = cv2.connectedComponentsWithStats(sky, connectivity=8)
    top = [i for i in np.unique(lab_s[:3, :]) if i != 0 and st_s[i, cv2.CC_STAT_AREA] > 0.06 * w * h]
    if top:
        sky_mask = np.isin(lab_s, top)
        lowest = [np.flatnonzero(sky_mask[:, x])[-1] for x in range(w) if sky_mask[:, x].any()]
        horizon = int(np.percentile(lowest, 90)) + round(h * 0.06)
        road[:horizon, :] = False

    # How far each pixel is from the typical asphalt tone around it (a large median window).
    k = max(31, (w // 8) | 1)
    background = cv2.medianBlur(gray, k).astype(np.int16)
    diff = gray.astype(np.int16) - background
    strength = np.abs(diff).astype(np.float32)
    anomaly = road & ((diff > 16) | (diff < -32))
    anomaly = cv2.morphologyEx(anomaly.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)

    edges = cv2.Canny(gray, 60, 140)
    edges = cv2.dilate(edges, np.ones((3, 3), np.uint8)) > 0
    return PixelMap(road=road, anomaly=anomaly, edges=edges & road, strength=strength)
