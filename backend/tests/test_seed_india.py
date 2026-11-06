import json
import subprocess
import sys

from app.config import REPO_ROOT
from app.db import Database

SCRIPT = str(REPO_ROOT / "scripts" / "seed_india.py")
CASES = REPO_ROOT / "data" / "india-cases"


def run(data_dir, *args):
    env = {"DATA_DIR": str(data_dir), "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env, timeout=300)


def test_photos_and_labels_match():
    cases = json.loads((CASES / "selection.json").read_text())
    assert len(cases) == 200
    assert all((CASES / "img" / c["file"]).is_file() for c in cases)
    assert (CASES / "ATTRIBUTION.md").is_file()


def test_india_seed_is_demo_only_spread_across_places_and_removable(tmp_path):
    assert run(tmp_path).returncode != 0  # needs --demo
    r = run(tmp_path, "--demo")
    assert r.returncode == 0, r.stderr
    db = Database(tmp_path / "rastescan.db")
    assert db.scalar("SELECT COUNT(*) FROM reports") == 200
    assert db.scalar("SELECT COUNT(*) FROM reports WHERE is_demo = 0") == 0
    assert db.scalar("SELECT COUNT(DISTINCT ward_code) FROM reports") >= 20
    assert db.scalar("SELECT COUNT(*) FROM reports WHERE hazard_type = 'Pothole'") > 60
    assert run(tmp_path, "--remove").returncode == 0
    assert db.scalar("SELECT COUNT(*) FROM reports") == 0
