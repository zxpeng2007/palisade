"""SQLite persistence. Deliberately stdlib-only.

One process, one connection, WAL mode, a lock around writes: at arena scale
every operation is microseconds, and keeping the storage layer boring keeps it
auditable. All live-game state lives in memory (games.py); the database holds
accounts, tokens, and finished games.
"""

from __future__ import annotations

import os
import sqlite3
import threading

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    pw_hash BLOB NOT NULL,
    salt BLOB NOT NULL,
    is_bot INTEGER NOT NULL DEFAULT 0,
    rating REAL NOT NULL DEFAULT 1500,
    rd REAL NOT NULL DEFAULT 350,
    vol REAL NOT NULL DEFAULT 0.06,
    rated_games INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    created TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS tokens (
    hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    scopes TEXT NOT NULL,
    created TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    p1 INTEGER NOT NULL REFERENCES users(id),
    p2 INTEGER NOT NULL REFERENCES users(id),
    rated INTEGER NOT NULL,
    initial INTEGER NOT NULL,
    increment INTEGER NOT NULL,
    moves TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    winner INTEGER,
    reason TEXT,
    p1_rating REAL, p2_rating REAL,
    p1_delta REAL, p2_delta REAL,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    finished TEXT
);
CREATE INDEX IF NOT EXISTS games_p1 ON games(p1, created DESC);
CREATE INDEX IF NOT EXISTS games_p2 ON games(p2, created DESC);
"""

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def connect(path: str | None = None) -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    path = path or os.environ.get("PALISADE_DB", "palisade.db")
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    conn.commit()
    _conn = conn
    return conn


def reset_for_tests() -> None:
    global _conn
    if _conn is not None:
        _conn.close()
    _conn = None


def query(sql: str, args: tuple = ()) -> list[sqlite3.Row]:
    with _lock:
        return connect().execute(sql, args).fetchall()


def one(sql: str, args: tuple = ()) -> sqlite3.Row | None:
    rows = query(sql, args)
    return rows[0] if rows else None


def execute(sql: str, args: tuple = ()) -> int:
    with _lock:
        conn = connect()
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
