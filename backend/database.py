"""SQLite database setup for the EMT Report Assistant demo."""
import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "emt_demo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY,
    chief_complaint TEXT,
    patient_age INTEGER,
    patient_sex TEXT,
    narrative TEXT DEFAULT '',
    finalized INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS timestamps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,
    label TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (call_id) REFERENCES calls (id)
);

CREATE TABLE IF NOT EXISTS vitals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,
    bp TEXT,
    hr INTEGER,
    spo2 INTEGER,
    rr INTEGER,
    gcs INTEGER,
    glucose INTEGER,
    recorded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (call_id) REFERENCES calls (id)
);

CREATE TABLE IF NOT EXISTS dictations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    call_id TEXT NOT NULL,
    text TEXT NOT NULL,
    recorded_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (call_id) REFERENCES calls (id)
);
"""


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
