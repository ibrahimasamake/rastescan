#!/usr/bin/env bash
# Run once on a fresh Ubuntu 24.04 EC2 instance (ARM t4g.small) as the ubuntu user:
#   curl -fsSL ... or copy this file, then: bash setup-ec2.sh https://github.com/ibrahimasamake/rastescan.git
# The repo is private: create a read-only deploy key or a fine-grained token first (docs/aws-setup.md, step 5).
set -euo pipefail
REPO_URL="${1:?usage: setup-ec2.sh <git clone url>}"

sudo apt-get update
sudo apt-get install -y python3-venv python3-pip git libgl1 libglib2.0-0 nodejs npm

sudo useradd --system --home /opt/rastescan --shell /usr/sbin/nologin rastescan 2>/dev/null || true
sudo mkdir -p /opt/rastescan /var/lib/rastescan
sudo chown "$USER" /opt/rastescan
git clone "$REPO_URL" /opt/rastescan || (cd /opt/rastescan && git pull)

cd /opt/rastescan/backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

cd /opt/rastescan/web
npm ci
npx vite build

sudo chown -R rastescan /var/lib/rastescan
if [ ! -f /etc/rastescan.env ]; then
  sudo cp /opt/rastescan/backend/.env.example /etc/rastescan.env
  echo ">>> Edit /etc/rastescan.env (S3_BUCKET, DASHBOARD_PIN, BEDROCK_MODEL_ID), then run: sudo systemctl restart rastescan"
fi
sudo cp /opt/rastescan/deploy/rastescan.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rastescan
sleep 2
curl -s localhost:8000/api/health && echo
