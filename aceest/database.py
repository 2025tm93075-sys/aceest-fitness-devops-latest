"""
SQLite persistence layer.

The schema mirrors the legacy desktop app (users, clients, progress, workouts,
exercises, metrics). A connection is opened per request and closed on teardown.
"""

from __future__ import annotations

import os
import sqlite3

from flask import Flask, current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    username      TEXT PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'Trainer'
);

CREATE TABLE IF NOT EXISTS clients (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT UNIQUE NOT NULL,
    age              INTEGER,
    height           REAL,
    weight           REAL,
    program          TEXT,
    calories         INTEGER,
    target_weight    REAL,
    target_adherence INTEGER,
    membership_end   TEXT,
    created_at       TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS progress (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id   INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    week        TEXT NOT NULL,
    adherence   INTEGER NOT NULL CHECK (adherence BETWEEN 0 AND 100)
);

CREATE TABLE IF NOT EXISTS workouts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date         TEXT NOT NULL,
    workout_type TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    notes        TEXT
);

CREATE TABLE IF NOT EXISTS exercises (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    workout_id INTEGER NOT NULL REFERENCES workouts(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    sets       INTEGER NOT NULL,
    reps       INTEGER NOT NULL,
    weight     REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS metrics (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    date      TEXT NOT NULL,
    weight    REAL,
    waist     REAL,
    bodyfat   REAL
);
"""


def get_db() -> sqlite3.Connection:
    """Return the request-scoped database connection."""
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app: Flask) -> None:
    """Create tables and seed the default admin user (idempotent)."""
    path = app.config["DATABASE"]
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        # OR IGNORE keeps this safe when several gunicorn workers boot at once
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role) "
            "VALUES (?, ?, 'Admin')",
            (app.config["ADMIN_USER"], generate_password_hash(app.config["ADMIN_PASSWORD"])),
        )
        conn.commit()
    finally:
        conn.close()

    app.teardown_appcontext(close_db)
