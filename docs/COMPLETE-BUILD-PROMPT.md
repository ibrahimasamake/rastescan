# Full build prompt: RasteScan public road-repair portal

Paste everything below the line into Claude Code (cloud or desktop), or into any coding agent, with the repo checked out.
Work in phases and commit after each one.

---

You are the lead engineer finishing **RasteScan**, a civic app where citizens photograph road damage, an AI inspector
classifies and scores it, and the city government sees a ranked repair queue and fixes problems fast. **Everyone can see
everything**: every report, its urgency, who is handling it, and the repair proof. When a road is fixed the public page
shows it as **Resolved** with before and after photos.

Read the repo first (`README.md`, `docs/`, `backend/app/`, `web/src/`, `prompts/inspection-prompt.md`). Keep what works
(FastAPI + SQLite backend, React + Vite web app, Capacitor Android wrapper, Terraform + Ansible infra). Extend it; do not
rewrite it. Match the existing code style and comment density. Tests must pass at every commit:
`cd backend && .venv/bin/python -m pytest -q` and `cd web && npx eslint . && npx tsc -b && npx vite build`.

## 1. Who uses it
- **Citizen**: opens the app daily, reports a problem in under 30 seconds, tracks it, sees the city improving. No account
  needed to report or to browse. Optional phone-free "my reports" by device.
- **Public / journalists / councillors**: browse everything without logging in.
- **Ward engineer / officer**: logs in, sees the queue ordered by urgency and deadline, assigns crews, uploads the repair photo.
- **Commissioner / admin**: sees ward performance, overdue tickets, exports data.

## 2. Look and feel: official government portal
Make it look like a trustworthy municipal government website, not a startup landing page.
- Top strip: "Official civic service" with language switcher (English, ಕನ್ನಡ, हिन्दी) and text-size controls (A- A A+).
- Header: a **generic placeholder emblem** and the name "Municipal Road Services" (configurable by env). Never use a real
  government's emblem, name or logo.
- Calm palette: deep navy and white with one saffron accent, clear status colours (Critical red, High orange, Medium
  amber, Low grey-blue, Resolved green). Serif or humanist heading font, plain body font, generous spacing.
- Footer: about, how it works, privacy policy, accessibility statement, open data download, contact, last updated time.
- WCAG 2.1 AA: contrast, focus rings, keyboard use, labels, alt text, no information by colour alone (icons and words too).
- Mobile first (phones are the main device) and fast on slow networks (small bundle, lazy-load the map, compressed images).
- Skeleton loaders, friendly empty and error states, no jargon.

## 3. Public pages (no login)
1. **Home**: big "Report a road problem" button; live counters (reported today, open now, resolved this month, average days
   to fix); a map preview; "Recently resolved" strip with before/after thumbnails; a short "How it works" in 3 steps.
2. **Map of all reports** (Leaflet + OpenStreetMap tiles, free, no API key): colour-coded pins by urgency, grey-green for
   resolved, clustering when zoomed out, popup with photo, hazard, urgency, status, age. Filters: status, urgency, hazard,
   ward, date range, "overdue only". Shareable URLs for filters and for a single report.
3. **List / table** of the same data with sorting and pagination; CSV download button (open data).
4. **Report page** (`/#/r/RS-0001`), the heart of the transparency idea:
   - Big status badge: Reported, AI-verified, Assigned, Repair done, **Resolved (verified by AI)**, Dismissed.
   - **Timeline** with timestamps: reported, AI assessment, assigned to (crew or officer name), repair photo uploaded,
     verified resolved. Each step shows who and when.
   - **Before / after slider** once repaired. The AI re-inspection of the after photo is shown in plain words.
   - SLA clock: "Due in 18 hours" or "Overdue by 2 days" (red).
   - Urgency, severity, hazard type, the AI's repair recommendation, estimated repair time, location, ward, "N citizens
     reported this", and a **"I see this too" button** (one vote per device) that raises the merge count.
   - Share button (WhatsApp, copy link). Comments from officers shown as official updates.
5. **Ward scoreboard**: per ward, number open, resolved, average time to resolve, % within deadline, sorted best to worst.
   This is public on purpose.
6. **Open data and API page**: explain the JSON and CSV endpoints. Privacy and accessibility pages.

## 4. Citizen reporting flow
- Camera or gallery, GPS auto-filled (with manual pin-drop on the map if GPS is denied), optional one-line note.
- Show the AI result immediately in friendly language with the bounding box on the photo and the urgency.
- Report code and "Track this report" link at the end. "My reports" list by device, with status changes highlighted.
- Works offline: queue the report locally and send when the network returns (service worker + IndexedDB). Show queued state.
- Duplicate merge already exists: tell the citizen "Already reported by 3 others, your report adds weight".
- Privacy: faces and number plates are blurred on the server before storage and before any photo is sent to an AI. Never
  expose `device_id`. Round nothing about road location, but never publish anything personal.
- Abuse protection: existing rate limit stays; add a simple photo sanity check (reject screenshots/non-road scenes via the AI
  "None" result with low confidence going to the review queue, not auto-published as damage).

## 5. Government dashboard (login required)
Replace the single shared PIN with real officer accounts, but keep `DASHBOARD_PIN` working as a fallback for the expo demo.
- Accounts table with roles `officer`, `admin`; password hashing (argon2 or bcrypt), signed session tokens (JWT in an
  HttpOnly cookie or Authorization header), login rate limit. Seed an admin from env on first start. Never commit secrets.
- **Queue** ordered by urgency, then deadline, severity, merge count (the existing `triage.queue_key`). Columns: code, hazard,
  urgency, ward, age, SLA remaining, assignee, status. Overdue rows highlighted. Filters, search by code, ward filter.
- Actions: assign to a crew/person, change status, add an official comment (public), upload the **repair photo** (AI
  re-inspects; auto-verifies when clean; otherwise reopens with the reason), dismiss with a reason (public), merge/unmerge.
- **Review queue** for low-confidence AI results: officer confirms the hazard type and severity or dismisses.
- **Map view** of the queue and a printable **daily work order** per crew (sorted route by distance, simple nearest-neighbour).
- **Analytics**: reports per day, resolved per day, average time to resolve by urgency and ward, SLA compliance, top hazard
  types, AI accuracy (officer overrides vs AI). Simple charts, no heavy libraries.
- Audit trail: every status change and override stored with officer, time, old and new value (`status_history` table). The
  public timeline is generated from it.
- Notifications: email (SMTP env, optional) or web push to the citizen when their report is assigned and resolved. If no
  contact is given, the "my reports" screen highlights the change. Optional Telegram/WhatsApp link share only.

## 6. Backend work
- New tables with a lightweight migration step in `db.py`: `status_history`, `officers`, `wards`, `comments`, `votes`.
- **Wards**: load ward polygons from a GeoJSON file (`data/wards.geojson`, with a small sample included and documented)
  and assign each report to a ward by point-in-polygon at creation.
- Public read-only endpoints (no PIN): `GET /api/public/reports` (filters + pagination + bbox), `GET /api/public/reports/{code}`
  (with timeline), `GET /api/public/stats`, `GET /api/public/wards`, `GET /api/public/export.csv`. Never return
  `device_id`, officer emails or internal notes.
- Officer endpoints for assign, comment, dismiss, bulk status, analytics, work order.
- Keep `/api/reports` citizen endpoints working so the Android app does not break. Version new APIs under `/api/v2` if the shape changes.
- Cache headers on public GETs (short), ETag where cheap. SQLite WAL stays; add indexes for filters.
- Tests for every new endpoint, for ward lookup, for the public privacy rule (no `device_id` anywhere in public JSON), for
  status history, and for the SLA and queue order.

## 7. AI provider (any of these, chosen by `AI_MODE`)
The inspector layer already supports four modes in `backend/app/inspector.py`:
- `bedrock`: Amazon Nova (production when the AWS account is unlocked).
- `groq`: free Groq key. `export GROQ_API_KEY=...` then `AI_MODE=groq`. Model default
  `qwen/qwen3.8-27b`; if Groq has retired it, pick a current vision model from console.groq.com.
- `ollama`: fully local and free. `ollama pull qwen2.5vl:7b`, then `AI_MODE=ollama` (`OLLAMA_URL`, `OLLAMA_MODEL` to change).
- `fake`: canned results for UI work and tests; the app shows a "Test mode" banner.
Do not weaken the JSON schema in `schema.py`: the server recomputes urgency from the severity score and the model only
suggests. Add `scripts/evaluate.py` support to compare providers on `test-photos/` (accuracy of hazard type, mean absolute
severity error, JSON failure rate, latency) and print one table, so the team can choose the provider with evidence.
Free tiers have rate limits: keep the inspection cache by image hash, retry once with backoff on HTTP 429, and queue
overflow reports as `review` with a clear message instead of failing.

## 8. Languages
All user-facing text goes through one i18n dictionary (English, Kannada, Hindi). The AI's repair text stays English; show
hazard names and statuses translated. Date and number formats follow the language. Language choice is remembered.

## 9. Infra and delivery
- Keep Terraform + Ansible. Add `groq_api_key` to the Ansible env (already templated) and document how to deploy in each AI mode.
- Add `make seed-demo`: creates 40 realistic demo reports (varied hazards, wards, ages, some resolved with before/after
  pairs generated from the sample photos) so the portal looks alive at the expo without real data. Clearly mark demo data in
  the database and never mix it into production without the flag.
- Android: rebuild the Capacitor app after web changes, keep the Play internal-testing instructions current.
- README and `docs/` updated: architecture diagram refresh, "choose your AI" guide, officer guide (1 page), citizen FAQ.

## 10. Phases (commit after each, tests green)
1. Design system + home + report page with timeline and before/after (using current data).
2. Backend: status history, wards, public endpoints, tests.
3. Map, list, filters, CSV, ward scoreboard.
4. Officer login, assign, comments, repair-photo flow, review queue, audit trail.
5. Analytics, work orders, notifications.
6. i18n, accessibility pass, offline queue, performance pass.
7. AI provider evaluation script, rate-limit handling, demo seed, docs, Android rebuild.

## 11. Definition of done
- A stranger opens the public URL on a phone, sees live numbers and a map of every report, opens one and watches its full
  history, and can tell at a glance whether it is resolved.
- An officer logs in, works the queue top to bottom, uploads a repair photo, and the public page flips to **Resolved** with a
  before/after slider within seconds.
- The same flows work with `AI_MODE=fake`, `groq` and `ollama`, and with `bedrock` once AWS allows it.
- No secret, key, PIN or personal data in git or in any public API response. Lighthouse accessibility score at least 95 and
  performance at least 85 on mobile for the home page.
- All tests, lint, type-check and build pass; README explains running everything on a laptop in under 10 minutes.

Ask me only when blocked by something that needs my accounts or a decision about money. Otherwise make a sensible choice,
note it in the commit message, and keep going.
