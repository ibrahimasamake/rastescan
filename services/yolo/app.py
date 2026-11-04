"""RasteScan road-damage detector. A separate service: YOLO's heavy, AGPL-licensed libraries stay out of the main app.

POST /detect with a photo returns every pothole and crack it finds, with boxes in the same 0-1000 coordinates the
main app uses. Weights are not in git: run `make yolo-weights` once.
"""
import io
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

WEIGHTS = Path(os.getenv("YOLO_WEIGHTS", Path(__file__).parent / "weights" / "rdd2022-yolov8m.pt"))
MIN_CONFIDENCE = float(os.getenv("YOLO_CONF", "0.25"))

app = FastAPI(title="RasteScan YOLO detector")
_model = None


def model():
    global _model
    if _model is None:
        if not WEIGHTS.is_file():
            raise HTTPException(503, f"Weights not found at {WEIGHTS}. Run `make yolo-weights` first.")
        from ultralytics import YOLO

        _model = YOLO(str(WEIGHTS))
    return _model


@app.get("/health")
def health():
    return {"ok": True, "weights": WEIGHTS.is_file(), "model": WEIGHTS.stem}


@app.post("/detect")
async def detect(photo: UploadFile = File(...)):
    try:
        img = Image.open(io.BytesIO(await photo.read())).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(400, "Not a readable image.") from exc
    result = model()(img, conf=MIN_CONFIDENCE, verbose=False)[0]
    w, h = img.size
    found = []
    for (x1, y1, x2, y2), conf, cls in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(), result.boxes.cls.tolist()):
        found.append({
            "label": result.names[int(cls)], "confidence": round(float(conf), 3),
            "box": {"ymin": round(1000 * y1 / h), "xmin": round(1000 * x1 / w), "ymax": round(1000 * y2 / h), "xmax": round(1000 * x2 / w)},
        })
    return {"model": WEIGHTS.stem, "detections": found}
