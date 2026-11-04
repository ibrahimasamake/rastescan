"""Compare AI providers on your own labelled road photos, so the team picks one with evidence.

Put photos in test-photos/ and a test-photos/labels.csv with columns:
    file,hazard_type,urgency,severity
(severity is optional; hazard_type uses the schema names, e.g. Pothole, Open Manhole, None).

Run from the repo root:
    backend/.venv/bin/python scripts/evaluate.py --providers groq,ollama
    backend/.venv/bin/python scripts/evaluate.py --providers bedrock,groq,ollama,fake

Each provider reads its usual settings from the environment (GROQ_API_KEY, OLLAMA_URL, AWS_REGION,
BEDROCK_MODEL_ID, ...). Results for every photo go to test-photos/results-<provider>.csv and one summary table
is printed: hazard accuracy, urgency accuracy, mean absolute severity error, JSON failure rate, busy (rate-limited)
rate and median latency.
"""
import argparse
import csv
import statistics
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import imaging  # noqa: E402
from app.config import Settings  # noqa: E402
from app.inspector import InspectionError, InspectorBusy, make_inspector  # noqa: E402
from app.schema import urgency_for  # noqa: E402


def load_labels(folder: Path) -> list[dict]:
    path = folder / "labels.csv"
    if not path.is_file():
        sys.exit(f"Missing {path}. Create it with columns file,hazard_type,urgency,severity")
    rows = [r for r in csv.DictReader(path.open()) if r.get("file")]
    if not rows:
        sys.exit(f"{path} has no rows yet. Add your labelled photos first.")
    return rows


def evaluate(provider: str, labels: list[dict], folder: Path, pause_s: float) -> dict:
    inspector = make_inspector(replace(Settings(), ai_mode=provider))
    out, times = [], []
    hazard_ok = urgency_ok = invalid = busy = 0
    sev_err: list[float] = []
    for lab in labels:
        jpeg, _ = imaging.prepare((folder / lab["file"]).read_bytes())
        t0 = time.monotonic()
        row = {**lab, "got_hazard": "", "got_urgency": "", "got_severity": "", "seconds": "", "note": ""}
        try:
            r = inspector.inspect(jpeg)
        except InspectorBusy:
            busy += 1
            row["note"] = "rate limited"
        except InspectionError as exc:
            invalid += 1
            row["note"] = f"invalid JSON: {str(exc)[:120]}"
        except Exception as exc:  # network or auth problems: record and continue
            invalid += 1
            row["note"] = f"error: {str(exc)[:120]}"
        else:
            elapsed = time.monotonic() - t0
            times.append(elapsed)
            urg = urgency_for(r)
            hazard_ok += r.hazard_type == lab["hazard_type"]
            urgency_ok += urg == lab.get("urgency")
            if lab.get("severity"):
                sev_err.append(abs(r.severity_score - float(lab["severity"])))
            row.update(got_hazard=r.hazard_type, got_urgency=urg, got_severity=r.severity_score,
                       seconds=round(elapsed, 1), note=r.repair_recommendation[:120])
        out.append(row)
        print(f"  [{provider}] {lab['file']}: {row['got_hazard'] or row['note']}", flush=True)
        if pause_s:
            time.sleep(pause_s)  # stay under free-tier rate limits
    with (folder / f"results-{provider}.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    n = len(labels)
    return {
        "provider": f"{provider} ({getattr(inspector, 'model', '')})",
        "hazard": f"{hazard_ok}/{n} ({100 * hazard_ok // n}%)",
        "urgency": f"{urgency_ok}/{n} ({100 * urgency_ok // n}%)",
        "severity_mae": f"{statistics.mean(sev_err):.2f}" if sev_err else "–",
        "json_fail": f"{100 * invalid // n}%",
        "busy": f"{100 * busy // n}%",
        "median_s": f"{statistics.median(times):.1f}" if times else "–",
    }


def print_table(rows: list[dict]) -> None:
    headers = {"provider": "Provider", "hazard": "Hazard correct", "urgency": "Urgency correct",
               "severity_mae": "Severity error (MAE)", "json_fail": "JSON failures", "busy": "Rate limited",
               "median_s": "Median seconds"}
    widths = {k: max(len(h), *(len(str(r[k])) for r in rows)) for k, h in headers.items()}
    line = " | ".join(h.ljust(widths[k]) for k, h in headers.items())
    print("\n" + line + "\n" + "-+-".join("-" * widths[k] for k in headers))
    for r in rows:
        print(" | ".join(str(r[k]).ljust(widths[k]) for k in headers))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--providers", default="bedrock", help="comma separated: bedrock, groq, ollama, fake")
    ap.add_argument("--photos", default=str(ROOT / "test-photos"))
    ap.add_argument("--pause", type=float, default=0.0, help="seconds between calls (e.g. 2 for Groq's free tier)")
    args = ap.parse_args()
    folder = Path(args.photos)
    labels = load_labels(folder)
    rows = []
    for p in [p.strip() for p in args.providers.split(",") if p.strip()]:
        print(f"\n{p}: {len(labels)} photos")
        try:
            rows.append(evaluate(p, labels, folder, args.pause))
        except ValueError as exc:  # e.g. groq without a key
            print(f"  skipped: {exc}")
    if rows:
        print_table(rows)


if __name__ == "__main__":
    main()
