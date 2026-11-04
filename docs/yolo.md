# YOLO road-damage detector (optional, free, no rate limits)

A separate service in `services/yolo/` that finds **potholes and cracks** and their boxes in under a second on a laptop CPU.
It runs on its own because `torch` needs an older numpy than the main app.

| | |
|---|---|
| Model | `dronefreak/rdd2022-yolov8m` on Hugging Face, YOLOv8m fine-tuned on RDD2022 (about 50 MB) |
| Classes | longitudinal, transverse and alligator cracks (shown as "Road fissure"), pothole |
| Licence | AGPL-3.0 (weights and Ultralytics). If you run a changed version for the public, offer its source. Check it suits your use. |
| Limits | It cannot see depth, so severity is **estimated from how much of the photo the defect covers**. It does not know open manholes, waterlogging or debris. Its confidence is often below 60%, so its reports can land in the review queue. |

## Set up (once)
```bash
make yolo-setup     # installs torch and ultralytics into services/yolo/.venv (large download)
make yolo-weights   # downloads best.pt (about 50 MB) from Hugging Face
make yolo           # starts the detector on http://localhost:8020
```
Or with Docker: `docker build -t rastescan-yolo services/yolo && docker run -p 8020:8020 rastescan-yolo`.

## Use it
- Admin → **AI models** → "YOLO road-damage detector" → pick a photo and click **Run**. Compare it with the Ollama models.
- Make it the default: `AI_MODE=yolo make api` (set `YOLO_URL` if it is not on port 8020).
- A good design for production is both: YOLO for fast boxes, a vision model for the scene and the repair advice.
