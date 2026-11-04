# RasteScan

AI road inspector for the TechKubik National Level Project Expo 2026 (HKBK College of Engineering, 5–6 November 2026).
A citizen photographs road damage; the backend blurs faces and plates, asks Amazon Nova on Bedrock to classify the
damage and score it, then ranks it in a repair queue for the ward engineer. Duplicate reports of the same spot merge
into one ticket, and a crew's after-photo is inspected again before the ticket is marked verified.

## Stack
| Part | Choice |
|---|---|
| Web app + Android app | React + Vite (`web/`), wrapped with Capacitor for the Play internal testing track (`web/android`) |
| Backend | Python FastAPI, SQLite, Pillow, OpenCV (privacy blur) (`backend/`) |
| AI in production | Amazon Nova on Amazon Bedrock, called with the EC2 IAM role (no keys in code) |
| Hosting | EC2 t4g.small behind CloudFront, photos in S3 (`deploy/`, `docs/aws-setup.md`) |
| Dev tooling | Claude Code helps write the code; it is not part of the running app |

## Run it on your laptop
Backend (Python 3.11+). `AI_MODE=fake` returns sample answers so you can work without AWS; the app shows a "Test mode" banner.
```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
AI_MODE=fake .venv/bin/uvicorn app.main:create_app --factory --reload --port 8000
```
With real Bedrock instead: `aws configure` with your own IAM user, then `AI_MODE=bedrock AWS_REGION=ap-south-1 BEDROCK_MODEL_ID=apac.amazon.nova-pro-v1:0 ...`.

Web app (Node 20+), in a second terminal:
```bash
cd web
npm ci
npm run dev        # http://localhost:5173, proxies /api to :8000
```
Citizen screen: `/#/`. Ward dashboard: `/#/dashboard` (PIN is `DASHBOARD_PIN`, empty locally).

Tests:
```bash
cd backend && .venv/bin/python -m pytest -q
cd web && npx eslint . && npx tsc -b && npx vite build
```

## Layout
```
backend/app/       FastAPI app: schema + rules, Bedrock inspector, imaging, triage, SQLite
backend/tests/     API and rule tests (run with the fake inspector)
web/src/           React app: pages/Report.tsx (citizen), pages/Dashboard.tsx (ward)
web/android/       Capacitor Android project
prompts/           Inspection prompt sent to Nova
scripts/evaluate.py  Accuracy check on labelled photos in test-photos/
deploy/            EC2 setup script, systemd unit, IAM policy
docs/              design.html, aws-setup.md, android.md
```

## API
| Method | Path | What it does |
|---|---|---|
| GET | `/api/health` | `{"ok": true, "ai_mode": "bedrock"}` |
| POST | `/api/reports` | multipart `photo`, optional `lat`, `lng`, `device_id` → report |
| GET | `/api/reports?device_id=` | a device's own reports |
| GET | `/api/reports/{code}` | one report, e.g. `RS-0007` |
| GET | `/api/queue` | open tickets sorted by urgency, severity, merged count; low-confidence reports for review |
| PATCH | `/api/reports/{code}` | `{"status": "assigned" \| "fixed" \| "dismissed" \| "new"}` (needs `X-Dashboard-Pin`) |
| POST | `/api/reports/{code}/after-photo` | crew's after photo; verified if the damage is gone (needs PIN) |

## Rules for contributors
- Never commit AWS keys, `.env` files, `.pem` files or Android keystores.
- Work on a branch and open a pull request into `main`.
- The server, not the model, decides urgency: it is recomputed from the severity score, and an open manhole is always critical.
