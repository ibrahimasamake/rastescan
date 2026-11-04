"""SQLite storage for reports and the inspection cache."""
import sqlite3
from pathlib import Path
from threading import Lock

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  code TEXT UNIQUE,
  lat REAL, lng REAL,
  photo_key TEXT NOT NULL,
  after_photo_key TEXT,
  ai_json TEXT NOT NULL,
  after_ai_json TEXT,
  hazard_type TEXT NOT NULL,
  severity REAL NOT NULL,
  urgency TEXT NOT NULL,
  model_urgency TEXT NOT NULL,
  confidence REAL NOT NULL,
  needs_review INTEGER NOT NULL,
  parent_id INTEGER REFERENCES reports(id),
  status TEXT NOT NULL,
  device_id TEXT,
  created_at TEXT NOT NULL,
  due_at TEXT,
  updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS reports_parent ON reports(parent_id);
CREATE INDEX IF NOT EXISTS reports_device ON reports(device_id);
CREATE TABLE IF NOT EXISTS inspection_cache (
  sha256 TEXT PRIMARY KEY,
  model TEXT NOT NULL,
  ai_json TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.lock = Lock()

    def query(self, sql: str, args: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql: str, args: tuple = ()) -> dict | None:
        rows = self.query(sql, args)
        return rows[0] if rows else None

    def execute(self, sql: str, args: tuple = ()) -> int:
        with self.lock, self.conn:
            return self.conn.execute(sql, args).lastrowid

    def insert_report(self, fields: dict) -> int:
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        with self.lock, self.conn:
            rid = self.conn.execute(f"INSERT INTO reports ({cols}) VALUES ({marks})", tuple(fields.values())).lastrowid
            self.conn.execute("UPDATE reports SET code = ? WHERE id = ?", (f"RS-{rid:04d}", rid))
        return rid

    def cached(self, sha: str, model: str) -> str | None:
        row = self.one("SELECT ai_json FROM inspection_cache WHERE sha256 = ? AND model = ?", (sha, model))
        return row["ai_json"] if row else None

    def cache(self, sha: str, model: str, ai_json: str) -> None:
        self.execute("INSERT OR REPLACE INTO inspection_cache (sha256, model, ai_json) VALUES (?, ?, ?)", (sha, model, ai_json))
