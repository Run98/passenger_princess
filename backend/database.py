"""Postgres database setup for the EMT Report Assistant demo.

Uses DATABASE_URL (standard Postgres connection string -- Neon, Vercel
Postgres, Supabase, etc. all provide one). This replaces the original
SQLite file storage: Vercel's serverless functions have no persistent
writable disk between invocations, so demo data needs a real database
to survive from one request to the next.

The get_conn()/conn.execute(...) interface is kept identical to the old
sqlite3-based version on purpose, so main.py and seed_demo.py needed no
changes -- only this file did.
"""
import os
import re
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ["DATABASE_URL"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY,
    chief_complaint TEXT,
    patient_age INTEGER,
    patient_sex TEXT,
    narrative TEXT DEFAULT '',
    narrative_format TEXT DEFAULT 'standard',
    narrative_sections TEXT DEFAULT '{}',
    narrative_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'draft',
    finalized INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- narrative_format/narrative_sections replaced the old fixed
-- narrative_chief_complaint/assessment/treatment columns so any
-- documentation style (standard/SOAP/CHART) can be stored, not just a
-- hardcoded 3-section shape. ADD COLUMN IF NOT EXISTS so this upgrades an
-- existing production table in place rather than requiring a fresh one.
ALTER TABLE calls ADD COLUMN IF NOT EXISTS narrative_format TEXT DEFAULT 'standard';
ALTER TABLE calls ADD COLUMN IF NOT EXISTS narrative_sections TEXT DEFAULT '{}';

CREATE TABLE IF NOT EXISTS timestamps (
    id SERIAL PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES calls (id),
    label TEXT NOT NULL,
    recorded_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS vitals (
    id SERIAL PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES calls (id),
    bp TEXT,
    hr INTEGER,
    spo2 INTEGER,
    rr INTEGER,
    gcs INTEGER,
    glucose INTEGER,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dictations (
    id SERIAL PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES calls (id),
    text TEXT NOT NULL,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scribbles (
    id SERIAL PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES calls (id),
    image_data TEXT NOT NULL,
    caption TEXT DEFAULT '',
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS photos (
    id SERIAL PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES calls (id),
    image_data TEXT NOT NULL,
    caption TEXT DEFAULT '',
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS signatures (
    id SERIAL PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES calls (id),
    signer_name TEXT,
    image_data TEXT NOT NULL,
    signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_QMARK_RE = re.compile(r"\?")


class _ConnWrapper:
    """Makes a psycopg2 connection look like the old sqlite3.Connection
    call sites already use: conn.execute(sql_with_qmarks, params) ->
    cursor, and dict(row) on results (via RealDictCursor)."""

    def __init__(self, pg_conn):
        self._conn = pg_conn

    def execute(self, sql, params=()):
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(_QMARK_RE.sub("%s", sql), params)
        return cur

    def executescript(self, sql):
        cur = self._conn.cursor()
        cur.execute(sql)
        cur.close()

    def commit(self):
        self._conn.commit()

    def close(self):
        self._conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn():
    pg_conn = psycopg2.connect(DATABASE_URL)
    wrapper = _ConnWrapper(pg_conn)
    try:
        yield wrapper
        wrapper.commit()
    finally:
        wrapper.close()
