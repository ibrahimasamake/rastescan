# RasteScan

AI road inspector for the TechKubik National Level Project Expo 2026 (HKBK College of Engineering, 5–6 November 2026).
A citizen photographs road damage; the backend classifies it, scores severity, and ranks it in a repair queue for the ward engineer.

## Stack
| Part | Choice |
|---|---|
| Web + Android app | React + Vite, wrapped with Capacitor for the Play internal testing track |
| Backend | Python FastAPI, SQLite, Pillow, OpenCV (privacy blur) |
| AI in production | Amazon Nova on Amazon Bedrock (called from the backend with the EC2 IAM role) |
| Hosting | EC2 t4g.small behind CloudFront, photos in S3 |
| Dev tooling | Claude Code is used to help write the code; it is not part of the running app |

## Layout
```
backend/        FastAPI service (POST /reports, GET /queue, PATCH /reports/{id})
web/            React app: citizen screen + ward dashboard
prompts/        Inspection prompt and JSON schema sent to Bedrock
test-photos/    Labelled evaluation photos (keep large files out of git; see .gitignore)
docs/design.html  Project design (architecture, triage rules, hosting, demo plan)
```

## Rules for contributors
- Never commit AWS keys, `.env` files or keystores. The server uses its IAM role.
- Work on a branch and open a pull request into `main`.
- Server-side validation is the source of truth for urgency, not the model.
