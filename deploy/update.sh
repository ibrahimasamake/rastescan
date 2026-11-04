#!/usr/bin/env bash
# Pull the latest main and restart. Run on the server: bash /opt/rastescan/deploy/update.sh
set -euo pipefail
cd /opt/rastescan && git pull
backend/.venv/bin/pip install -q -r backend/requirements.txt
(cd web && npm ci && npx vite build)
sudo systemctl restart rastescan
sleep 2 && curl -s localhost:8000/api/health && echo
