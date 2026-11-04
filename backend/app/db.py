"""SQLite storage: reports, their public history, officers, wards, comments, votes and the inspection cache.

Migrations are numbered and tracked with PRAGMA user_version, so an existing database upgrades in place.
"""
import sqlite3
from pathlib import Path
from threading import Lock

BASE_SCHEMA = """
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

# Each entry runs once, in order. Column additions are guarded so a half-applied upgrade can be re-run.
MIGRATIONS: list[list[str]] = [
    # 1: public portal, officer accounts, wards, audit trail
    [
        "ALTER TABLE reports ADD COLUMN ward_code TEXT",
        "ALTER TABLE reports ADD COLUMN note TEXT",
        "ALTER TABLE reports ADD COLUMN contact_email TEXT",
        "ALTER TABLE reports ADD COLUMN assignee TEXT",
        "ALTER TABLE reports ADD COLUMN resolved_at TEXT",
        "ALTER TABLE reports ADD COLUMN dismiss_reason TEXT",
        "ALTER TABLE reports ADD COLUMN ai_pending INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE reports ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0",
        """CREATE TABLE IF NOT EXISTS status_history (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             report_id INTEGER NOT NULL REFERENCES reports(id),
             at TEXT NOT NULL,
             event TEXT NOT NULL,
             actor TEXT NOT NULL,
             officer_id INTEGER REFERENCES officers(id),
             old_value TEXT,
             new_value TEXT,
             detail TEXT,
             public INTEGER NOT NULL DEFAULT 1)""",
        """CREATE TABLE IF NOT EXISTS officers (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             email TEXT UNIQUE NOT NULL,
             name TEXT NOT NULL,
             role TEXT NOT NULL CHECK (role IN ('officer', 'admin')),
             password_hash TEXT NOT NULL,
             active INTEGER NOT NULL DEFAULT 1,
             created_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS wards (
             code TEXT PRIMARY KEY,
             name TEXT NOT NULL,
             geometry TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS comments (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             report_id INTEGER NOT NULL REFERENCES reports(id),
             officer_id INTEGER REFERENCES officers(id),
             author TEXT NOT NULL,
             body TEXT NOT NULL,
             created_at TEXT NOT NULL)""",
        """CREATE TABLE IF NOT EXISTS votes (
             report_id INTEGER NOT NULL REFERENCES reports(id),
             device_hash TEXT NOT NULL,
             created_at TEXT NOT NULL,
             PRIMARY KEY (report_id, device_hash))""",
        "CREATE INDEX IF NOT EXISTS history_report ON status_history(report_id, at)",
        "CREATE INDEX IF NOT EXISTS reports_ward ON reports(ward_code)",
        "CREATE INDEX IF NOT EXISTS reports_created ON reports(created_at)",
        "CREATE INDEX IF NOT EXISTS reports_urgency ON reports(urgency)",
        "CREATE INDEX IF NOT EXISTS reports_hazard ON reports(hazard_type)",
        "CREATE INDEX IF NOT EXISTS comments_report ON comments(report_id)",
    ],
]


class Database:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(BASE_SCHEMA)
        self.lock = Lock()
        self._migrate()

    def _migrate(self) -> None:
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for number, statements in enumerate(MIGRATIONS, start=1):
            if version >= number:
                continue
            with self.conn:
                for sql in statements:
                    try:
                        self.conn.execute(sql)
                    except sqlite3.OperationalError as exc:
                        if "duplicate column" not in str(exc):
                            raise
                self.conn.execute(f"PRAGMA user_version = {number}")

    @property
    def version(self) -> int:
        return self.conn.execute("PRAGMA user_version").fetchone()[0]

    def query(self, sql: str, args: tuple = ()) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def one(self, sql: str, args: tuple = ()) -> dict | None:
        rows = self.query(sql, args)
        return rows[0] if rows else None

    def scalar(self, sql: str, args: tuple = ()):
        with self.lock:
            row = self.conn.execute(sql, args).fetchone()
        return row[0] if row else None

    def execute(self, sql: str, args: tuple = ()) -> int:
        with self.lock, self.conn:
            return self.conn.execute(sql, args).lastrowid

    def insert(self, table: str, fields: dict) -> int:
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        return self.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(fields.values()))

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
