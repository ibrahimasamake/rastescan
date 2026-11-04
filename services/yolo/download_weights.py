"""Downloads the road-damage weights (about 50 MB) from Hugging Face into services/yolo/weights/.

Source: https://huggingface.co/dronefreak/rdd2022-yolov8m  (YOLOv8m fine-tuned on RDD2022; licence AGPL-3.0).
"""
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

target = Path(__file__).parent / "weights" / "rdd2022-yolov8m.pt"
target.parent.mkdir(exist_ok=True)
shutil.copy(hf_hub_download("dronefreak/rdd2022-yolov8m", "best.pt"), target)
print(f"Saved {target} ({target.stat().st_size / 1e6:.0f} MB). Licence: AGPL-3.0; keep the source of any deployed changes available.")
