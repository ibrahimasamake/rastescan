# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

RasteScan: a public road-repair portal. Citizens photograph road damage, an AI inspector classifies and scores it, and the city works a ranked repair queue. Everything is public (reports, urgency, assignee, before/after proof) except private fields (see Privacy rules below). Stack: FastAPI + SQLite backend (`backend/`), React 19 + Vite + TypeScript web app (`web/`, also wrapped as an Android app with Capacitor), Terraform + Ansible deploy (`infra/`).

## Commands

Everyday commands are in the root `Makefile` (deploy commands are in `infra/Makefile`).

```bash
make setup          # backend/.venv + pip install -r requirements-dev.txt, and npm ci in web/
make api            # API on :8000, AI_MODE=fake, DASHBOARD_PIN=1234, reload on (API_HOST=0.0.0.0 to expose on LAN)
make web            # Vite dev server on :5173, proxies /api to :8000
make test           # what CI runs: pytest, then eslint + tsc -b + vite build
make seed-demo      # 40 demo reports into backend/data (make unseed-demo removes them)
make share          # builds web, serves web + API on one port :8000 for other devices (make tunnel adds a public https link)
make seed-india     # ~200 DEMO reports from real RDD2022 photos (data/india-cases, CC BY, see ATTRIBUTION.md) spread over 20 Indian cities; locations/dates are made up, labels come from the dataset, no AI is run. `make api`/`share` use data/wards-india.geojson (Bengaluru wards + city boxes) via WARDS_FILE
make seed-fixed     # marks about 45 demo reports as repaired, with SIMULATED after photos made from their own photo (labelled on the report page and in the app)
make live-demo      # drives a running API (start it with REPORTS_PER_HOUR=2000 make api): new reports, assignments, fixes
make evaluate       # compare AI providers on test-photos/ (PROVIDERS=groq,bedrock)
make android        # vite build --mode android + cap sync
make apk            # builds the Flutter app and publishes it at /api/public/rastescan.apk (Home and footer link to it; the file stays out of git)
```

Single backend test (run from `backend/`):
```bash
cd backend && .venv/bin/python -m pytest tests/test_officer.py::test_name -q
```
Web checks individually, from `web/`: `npx eslint .`, `npx tsc -b`, `npx vite build`. There are no web unit tests.

Real AI: `AI_MODE=groq GROQ_API_KEY=... make api` (or `azure`, `bedrock`). Real officer accounts: `ADMIN_EMAIL=... ADMIN_PASSWORD=<10+ chars> make api`. All settings are env vars read in `backend/app/config.py` (documented in `backend/.env.example`). CI also runs `terraform fmt/validate` and `ansible-lint` on `infra/`.

## Backend architecture (`backend/app/`)

- **`main.py`**: `create_app(settings, inspector)` is an app factory (`uvicorn app.main:create_app --factory`). It builds a single `services.Ctx` (settings, SQLite `Database`, storage, inspector, wards, secret, rate limiters), stored on `app.state.ctx`; routes get it via `http.get_ctx`. It also seeds the first admin, syncs `data/wards.geojson` into the DB, starts a background thread that retries reports saved without an AI answer (`process_pending`, every `RESCAN_EVERY_S`), and, if `web/dist` exists, serves the built SPA with a catch-all route.
- **`services.py`**: all report business logic. Rules that matter:
  - Every change to a report must go through here so it lands in `status_history` (the audit trail, via `record()`).
  - Anything leaving the server for anonymous readers must go through `public_item` / `public_detail` (never expose device id, contact email, notes, officer emails). `full_item` / `citizen_item` add private fields for the reporter and officers.
  - Internal statuses (`new, assigned, fixed, verified, dismissed`, plus unpublished `review` and `no_damage`) map to public statuses via `PUBLIC_STATUS`.
  - `create_report` handles AI result -> urgency -> status (low confidence goes to `review`), duplicate merge (`triage.find_duplicate`, `parent_id`), and ward lookup. If the AI is busy the report is saved with `ai_pending=1` and filled in later by the worker.
- **Routes**: `routes_citizen.py` (`/api/reports`, health), `routes_public.py` (`/api/public/*`, cached JSON, CSV export), `routes_officer.py` (`/api/v2/auth`, `/api/v2/officer/*`, `/api/v2/admin/*`, plus a few legacy `/api/queue`-style routes), `routes_models.py` (admin AI model lab). Officer auth accepts a bearer token, an httpOnly cookie (non-GET requires the `X-Requested-With: RasteScan` CSRF header), or the shared `X-Dashboard-PIN` (expo fallback, treated as admin).
- **`inspector.py`**: AI providers (`BedrockInspector`, `GroqInspector`, `AzureInspector`, `FakeInspector`) behind an `Inspector` protocol. `build_inspector` wraps every real provider in `GuidedInspector`, which runs `pixels.analyze` (road-surface/damaged-patch detection) first to hint the model, optionally also scans four zoomed tiles (`SCAN_TILES`), then checks/snaps the model's boxes against pixels and adds pixel-only patches as unsure potholes. `InspectorBusy` (rate-limited) vs `InspectionError` (unusable answer) drive the pending/502 behaviour. Results are cached by photo SHA + `Ctx.model_tag` (mode, model, prompt hash), so editing `prompts/inspection-prompt.md` invalidates the cache.
- **`schema.py`**: pydantic `Inspection`/`Detection`, `combine()` (dedup, sanity-filter, headline the worst, sum repair time) and `urgency_for()`. **The server, not the model, decides urgency from the severity score** (open manhole is always CRITICAL); do not loosen this. Coordinates for bounding boxes are 0-1000.
- **`db.py`**: SQLite (WAL) with a base schema plus numbered `MIGRATIONS` tracked by `PRAGMA user_version`; add schema changes as a new migration entry, don't edit old ones.
- **`costing.py`**: deterministic ₹ repair estimate (materials + crew labour) from the AI's measured size/depth; unit rates live in one table at the top. Surfaced as `repair_estimate` in `public_detail` and summed by `services.impact()` (`/api/public/impact`). `services.activity()` feeds the live ticker (`/api/public/activity`, public-only fields).
- **Other**: `imaging.py` (EXIF GPS, face/number-plate blur before storing or sending to any AI), `storage.py` (local disk vs S3), `triage.py` (due dates, duplicates, queue/route order), `wards.py` (point-in-polygon), `geocode.py` (PIN code and state for a report's pin from OpenStreetMap Nominatim, one request a second, cached per location by `services.address`; `GEOCODE_URL` empty switches it off; a background thread runs `services.fill_addresses` so `public_item` can carry the kept `address` without ever calling the network), `notify.py` (optional SMTP), `ratelimit.py`, `auth.py`.

### Tests (`backend/tests/`)
`conftest.py` provides `client` (PIN mode with a `FixedInspector` whose `.result`/`.busy` tests set), `officer_client` (seeded admin, no PIN), `fake_client`, plus helpers `submit()`, `login()`, `make_result()`, `photo_bytes()`. Tests build the app with `Settings(...)` pointing `data_dir` at `tmp_path` and `web_dist` at a missing dir; they never call real AI.

## Web architecture (`web/src/`)

HashRouter SPA (works the same on web, CloudFront, and inside Capacitor). `main.tsx` lists all routes; non-home pages are lazy-loaded. `pages/` is the public portal, `officer/` the dashboard, `api.ts` the single API client, `i18n/` has en/kn/hi dictionaries (add strings to all three), `outbox.ts` queues reports for offline sending, `public/sw.js` is the offline service worker (production builds only). The Home banner (`components/HeroReel.tsx`) is a GSAP reel built from the worst live reports: photo tiles explode and re-assemble, the AI box is drawn from each report's `bounding_box`; the ticker is locked to 30 fps, it pauses off screen, and it falls back to a still photo under `prefers-reduced-motion` (append `?motion=on` to the URL to force it). `components/IntroVideo.tsx` plays `public/rastescan-intro.mp4` once per visit when a visit lands on Home, with a Skip button; it is skipped under reduced motion too, and gives up if the video has not started in 4 s. `vite.config.ts` uses `base: "./"` so the build also works in the Android app (`.env.android`).

## Mobile app (`mobile/`)

Flutter client for the same API (`--dart-define=API_BASE=...`, default the dev tunnel). `lib/api.dart` citizen API and models, `lib/officer_api.dart` officer API, `lib/ui.dart` the design system (asphalt, lane-paint yellow, Barlow Condensed via `display()`, corner-tick AI frames, `LaneLine`), `lib/pages/` the screens, `pages/intro.dart` the opening film. Checks from `mobile/`: `flutter analyze lib`, `flutter test`. Play release steps are in `mobile/README.md`; the keystore and `android/key.properties` are git-ignored. Every report carries `address` once its location is known; lists show PIN code and state from it (web `Place`, app `Report.place`). Report and result pages ask for it if it is not there yet (web `useAddress`, app `Api.address`).

## Rules from the project README
- Never commit secrets (AWS keys, `.env`, `terraform.tfvars`, `*.pem`, keystores, PINs, passwords).
- Work on a branch and PR into `main`; CI must be green.
- Use a generic site name and the placeholder emblem; never a real government's name, emblem, or logo.
