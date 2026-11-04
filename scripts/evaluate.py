"""Runs the inspector on labelled test photos and prints how often it agrees with you.

Put photos in test-photos/ and a test-photos/labels.csv with columns: file,hazard_type,urgency
Run from the repo root on a machine with Bedrock access:
    backend/.venv/bin/python scripts/evaluate.py
Writes test-photos/results.csv with every answer.
"""
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import imaging  # noqa: E402
from app.config import Settings  # noqa: E402
from app.inspector import BedrockInspector, InspectionError, load_prompt  # noqa: E402
from app.schema import urgency_for  # noqa: E402


def main() -> None:
    s = Settings()
    photos = ROOT / "test-photos"
    labels = list(csv.DictReader((photos / "labels.csv").open()))
    inspector = BedrockInspector(s.bedrock_model_id, s.aws_region, load_prompt(s.prompt_file))
    rows, type_ok, urg_ok, invalid, clean, false_alarm, times = [], 0, 0, 0, 0, 0, []
    for lab in labels:
        jpeg, _ = imaging.prepare((photos / lab["file"]).read_bytes())
        t0 = time.monotonic()
        try:
            r = inspector.inspect(jpeg)
        except InspectionError as exc:
            invalid += 1
            rows.append({**lab, "got_type": "INVALID", "got_urgency": "", "severity": "", "seconds": "", "note": str(exc)[:200]})
            continue
        times.append(time.monotonic() - t0)
        urg = urgency_for(r)
        type_ok += r.hazard_type == lab["hazard_type"]
        urg_ok += urg == lab["urgency"]
        if lab["hazard_type"] == "None":
            clean += 1
            false_alarm += r.hazard_type != "None"
        rows.append({**lab, "got_type": r.hazard_type, "got_urgency": urg, "severity": r.severity_score,
                     "seconds": round(times[-1], 1), "note": r.repair_recommendation})
        print(f"{lab['file']}: {r.hazard_type} {urg} (expected {lab['hazard_type']} {lab['urgency']})")
    with (photos / "results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    n = len(labels)
    times.sort()
    print(f"\nModel: {s.bedrock_model_id}  Photos: {n}")
    print(f"Hazard type correct: {type_ok}/{n}")
    print(f"Urgency correct:     {urg_ok}/{n}")
    print(f"Invalid answers:     {invalid}/{n}")
    if clean:
        print(f"False alarms on good roads: {false_alarm}/{clean}")
    if times:
        print(f"Median time per photo: {times[len(times) // 2]:.1f} s")


if __name__ == "__main__":
    main()
