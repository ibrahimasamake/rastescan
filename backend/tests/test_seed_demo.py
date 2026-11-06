import subprocess
import sys

from app.config import REPO_ROOT
from app.db import Database
from tests.conftest import submit

SCRIPT = str(REPO_ROOT / "scripts" / "seed_demo.py")


def run(data_dir, *args):
    env = {"DATA_DIR": str(data_dir), "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, env=env, timeout=120)


def test_seed_needs_flag_marks_rows_and_cleans_up(tmp_path):
    assert run(tmp_path).returncode != 0
    r = run(tmp_path, "--demo", "--count", "12")
    assert r.returncode == 0, r.stderr
    db = Database(tmp_path / "rastescan.db")
    assert db.scalar("SELECT COUNT(*) FROM reports") == 12
    assert db.scalar("SELECT COUNT(*) FROM reports WHERE is_demo = 0") == 0
    assert db.scalar("SELECT COUNT(*) FROM status_history") >= 24
    assert run(tmp_path, "--remove").returncode == 0
    assert db.scalar("SELECT COUNT(*) FROM reports") == 0


def test_seed_refuses_to_mix_with_real_reports(client):
    submit(client)
    r = run(client.app.state.ctx.settings.data_dir, "--demo", "--count", "3")
    assert r.returncode != 0 and "real reports" in r.stderr
