# Everyday commands for running RasteScan on a laptop. Deployment commands live in infra/Makefile.
PY := backend/.venv/bin/python
DATA ?= backend/data

.PHONY: lan share tunnel setup api web test seed-demo unseed-demo evaluate android

setup: ## Install backend and web dependencies
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd web && npm ci

api: ## Backend on :8000 (AI_MODE=fake by default; set AI_MODE=groq or azure for a real model). API_HOST=0.0.0.0 to open it to your network
	cd backend && AI_MODE=$${AI_MODE:-fake} DATA_DIR=$(abspath $(DATA)) DASHBOARD_PIN=$${DASHBOARD_PIN:-1234} CORS_ALLOW_LAN=$${CORS_ALLOW_LAN:-1} \
		.venv/bin/uvicorn app.main:create_app --factory --reload --host $${API_HOST:-127.0.0.1} --port 8000

web: ## Web app on :5173, proxying /api to :8000
	cd web && npm run dev

test: ## Backend tests, web lint, type-check and build
	cd backend && .venv/bin/python -m pytest -q
	cd web && npx eslint . && npx tsc -b && npx vite build

seed-demo: ## Add 40 demo reports (clearly marked) to DATA (default backend/data)
	DATA_DIR=$(abspath $(DATA)) $(PY) scripts/seed_demo.py --demo

unseed-demo: ## Take every demo report out of DATA again
	DATA_DIR=$(abspath $(DATA)) $(PY) scripts/seed_demo.py --remove

evaluate: ## Compare AI providers on test-photos/ (PROVIDERS=groq,bedrock PAUSE=2)
	$(PY) scripts/evaluate.py --providers $${PROVIDERS:-groq} --pause $${PAUSE:-0}

android: ## Build the web app for Android and copy it into web/android (then open it in Android Studio)
	cd web && npm run build:android

lan: ## Show the addresses other devices on your Wi-Fi can use while `make api` and `make web` run
	@IP=$$(ipconfig getifaddr en0 || ipconfig getifaddr en1); echo "Web app: http://$$IP:5173   (API is reached through it, so no CORS)"; echo "API directly: http://$$IP:8000 (start it with API_HOST=0.0.0.0 make api)"

share: ## One port for everyone on your network: builds the web app and serves it and the API on :8000 (no PIN unless DASHBOARD_PIN is set)
	cd web && npm run build
	@IP=$$(ipconfig getifaddr en0 || ipconfig getifaddr en1); echo ""; echo "On this Mac:                 http://localhost:8000"; echo "Phones/laptops on your Wi-Fi: http://$$IP:8000"; echo "(Allow incoming connections if macOS asks. Camera and GPS need https: use `make tunnel`.)"; echo ""
	cd backend && AI_MODE=$${AI_MODE:-fake} DATA_DIR=$(abspath $(DATA)) DASHBOARD_PIN=$${DASHBOARD_PIN:-} CORS_ALLOW_LAN=1 COOKIE_SECURE=false \
		.venv/bin/uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000

tunnel: ## Public https link (anyone with it can open the app, from anywhere). Run `make share` in another terminal first. Needs cloudflared
	cloudflared tunnel --url http://localhost:8000
