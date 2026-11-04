# Everyday commands for running RasteScan on a laptop. Deployment commands live in infra/Makefile.
PY := backend/.venv/bin/python
DATA ?= backend/data

.PHONY: setup api web test seed-demo unseed-demo evaluate android yolo-setup yolo-weights yolo

setup: ## Install backend and web dependencies
	cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
	cd web && npm ci

api: ## Backend on :8000 (AI_MODE=fake by default; set AI_MODE=groq or ollama for a real model)
	cd backend && AI_MODE=$${AI_MODE:-fake} DATA_DIR=$(abspath $(DATA)) DASHBOARD_PIN=$${DASHBOARD_PIN:-1234} \
		.venv/bin/uvicorn app.main:create_app --factory --reload --port 8000

web: ## Web app on :5173, proxying /api to :8000
	cd web && npm run dev

test: ## Backend tests, web lint, type-check and build
	cd backend && .venv/bin/python -m pytest -q
	cd web && npx eslint . && npx tsc -b && npx vite build

seed-demo: ## Add 40 demo reports (clearly marked) to DATA (default backend/data)
	DATA_DIR=$(abspath $(DATA)) $(PY) scripts/seed_demo.py --demo

unseed-demo: ## Take every demo report out of DATA again
	DATA_DIR=$(abspath $(DATA)) $(PY) scripts/seed_demo.py --remove

evaluate: ## Compare AI providers on test-photos/ (PROVIDERS=groq,ollama PAUSE=2)
	$(PY) scripts/evaluate.py --providers $${PROVIDERS:-groq,ollama} --pause $${PAUSE:-0}

android: ## Build the web app for Android and copy it into web/android (then open it in Android Studio)
	cd web && npm run build:android

yolo-setup: ## Install the YOLO road-damage detector's own environment (services/yolo/.venv; large: installs torch)
	cd services/yolo && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

yolo-weights: ## Download the road-damage weights (about 50 MB, AGPL-3.0) from Hugging Face
	cd services/yolo && .venv/bin/python download_weights.py

yolo: ## Run the detector on :8020 (then AI_MODE=yolo for the main app, or pick it in the admin Model lab)
	cd services/yolo && .venv/bin/uvicorn app:app --port 8020
