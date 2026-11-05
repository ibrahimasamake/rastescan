"""Pixel analysis and the guided/zoomed scan, on small synthetic photos (no AI, no network)."""
import io

import cv2
import numpy as np
from PIL import Image

from app.inspector import GuidedInspector
from app.pixels import analyze
from app.schema import BoundingBox, Detection, Inspection, combine
from tests.conftest import make_result


def road_photo() -> bytes:
    """Sky on top, grey road, a dark hole low in the middle, and a red car higher up."""
    img = np.full((300, 400, 3), 110, np.uint8)               # grey asphalt (BGR)
    img[:60] = (240, 235, 230)                                # bright sky
    cv2.ellipse(img, (230, 225), (30, 24), 0, 0, 360, (40, 40, 40), -1)   # the hole: x 200-260, y 201-249
    cv2.rectangle(img, (60, 120), (140, 170), (30, 30, 200), -1)          # a red car
    ok, buf = cv2.imencode(".jpg", img)
    return buf.tobytes()


def det(box, hazard="Pothole", severity=7.0):
    d = make_result(hazard=hazard, severity=severity, box=box)
    return Detection.model_validate(d)


# box order in make_result is (ymin, xmin, ymax, xmax) in 0-1000 units
HOLE = (660, 490, 840, 660)
CAR = (390, 140, 580, 360)


def test_road_and_candidates_are_found():
    pm = analyze(road_photo())
    assert pm is not None and 0.5 < pm.road.mean() < 0.95          # road found, sky left out
    boxes = pm.candidates()
    hole = BoundingBox(ymin=HOLE[0], xmin=HOLE[1], ymax=HOLE[2], xmax=HOLE[3])
    from app.schema import _iou
    assert any(_iou(b, hole) > 0.4 for b in boxes)
    assert pm.hint().startswith("Pixel analysis")


def test_boxes_on_the_car_or_sky_are_rejected_and_the_hole_is_kept():
    pm = analyze(road_photo())
    assert pm.plausible(det(HOLE))
    assert not pm.plausible(det(CAR))                              # red car: not road colour
    assert not pm.plausible(det((0, 100, 150, 500)))               # sky
    kept = pm.check([det(CAR, severity=9.0), det(HOLE, severity=6.0)])
    assert len(kept) == 1 and kept[0].severity_score == 6.0


def test_a_loose_box_is_snapped_onto_the_hole():
    pm = analyze(road_photo())
    loose = det((640, 460, 860, 700))
    snapped = pm.snap(loose).bounding_box
    assert 650 <= snapped.ymin <= 680 and 820 <= snapped.ymax <= 855 and 475 <= snapped.xmin <= 505 and 645 <= snapped.xmax <= 675


def test_if_every_box_fails_the_check_the_ai_answer_is_kept():
    pm = analyze(road_photo())
    assert len(pm.check([det(CAR)])) == 1


def test_garbage_bytes_are_not_an_image():
    assert analyze(b"not an image") is None


def test_huge_or_tiny_boxes_and_repeats_are_dropped_by_combine():
    big = det((50, 50, 950, 950), severity=9.0)                    # covers 81% of the photo: a guess
    speck = det((500, 500, 510, 510), severity=8.0)
    a = det((600, 400, 760, 560), severity=7.0)
    again = det((610, 410, 750, 550), severity=6.5)                # same hole drawn twice
    inside = det((630, 430, 700, 500), severity=6.0)               # a small box wholly inside the first
    out = combine([big, speck, a, again, inside])
    assert [d.severity_score for d in out.detections] == [7.0]


class ZoomProbe:
    """Stands in for a model: finds nothing in the whole photo and one pothole in each zoomed region."""

    mode, model, prompt = "fake", "probe", ""

    def __init__(self):
        self.sizes = []

    def inspect(self, jpeg: bytes) -> Inspection:
        w, h = Image.open(io.BytesIO(jpeg)).size
        self.sizes.append((w, h))
        if w == 1000:
            return Inspection.model_validate(make_result(hazard="None", severity=1, box=(0, 0, 0, 0)))
        return Inspection.model_validate(make_result(box=(100, 100, 300, 300)))   # a hole in the region's top-left corner


def test_zoomed_regions_are_scanned_and_mapped_back_to_the_whole_photo():
    img = Image.new("RGB", (1000, 1000), (120, 120, 120))
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    probe = ZoomProbe()
    out = GuidedInspector(probe, tiles=True, pixels=False).inspect(buf.getvalue())
    assert sorted(set(probe.sizes)) == [(600, 600), (1000, 1000)] and len(probe.sizes) == 5
    boxes = {(d.bounding_box.ymin, d.bounding_box.xmin) for d in out.detections}
    assert boxes == {(60, 60), (60, 460), (460, 60), (460, 460)}   # region origin 0 or 400 + 100 * 0.6
