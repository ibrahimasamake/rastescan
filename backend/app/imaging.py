"""Photo preparation: GPS from EXIF, rotation, resize, and blurring of faces and number plates."""
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_SIDE = 1024
_GPS_IFD = 0x8825

_face = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_plate = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_russian_plate_number.xml")


class BadImage(Exception):
    pass


def _to_degrees(values, ref) -> float | None:
    try:
        d, m, s = (float(v) for v in values)
    except (TypeError, ValueError):
        return None
    deg = d + m / 60 + s / 3600
    return -deg if ref in ("S", "W") else deg


def exif_gps(img: Image.Image) -> tuple[float, float] | None:
    gps = img.getexif().get_ifd(_GPS_IFD)
    if not gps or 2 not in gps or 4 not in gps:
        return None
    lat, lng = _to_degrees(gps[2], gps.get(1)), _to_degrees(gps[4], gps.get(3))
    if lat is None or lng is None or (lat == 0 and lng == 0):
        return None
    return lat, lng


def blur_people_and_plates(rgb: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    boxes = list(_face.detectMultiScale(gray, 1.1, 6, minSize=(24, 24)))
    boxes += list(_plate.detectMultiScale(gray, 1.1, 4, minSize=(30, 10)))
    for x, y, w, h in boxes:
        roi = rgb[y : y + h, x : x + w]
        k = max(15, (min(w, h) // 3) | 1)
        rgb[y : y + h, x : x + w] = cv2.GaussianBlur(roi, (k, k), 0)
    return rgb


def prepare(raw: bytes) -> tuple[bytes, tuple[float, float] | None]:
    """Returns a privacy-blurred JPEG (no EXIF) and the photo's GPS position if it had one."""
    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise BadImage("This file is not a photo we can read. Use a JPEG or PNG.") from exc
    gps = exif_gps(img)
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    rgb = blur_people_and_plates(np.array(img))
    out = BytesIO()
    Image.fromarray(rgb).save(out, "JPEG", quality=85)
    return out.getvalue(), gps
