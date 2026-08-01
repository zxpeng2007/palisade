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
    created TEXT NOT NULL DEFAULT (datetime('now')),
    -- Nullable: the accounts that predate verification have no address, and
    -- ALTER TABLE cannot add these to an existing table any other way. Kept
    -- last so a migrated database and a fresh one have identical layouts.
    email TEXT,
    email_verified INTEGER NOT NULL DEFAULT 0
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
CREATE TABLE IF NOT EXISTS email_tokens (
    hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    purpose TEXT NOT NULL,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    expires TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS email_tokens_user ON email_tokens(user_id, purpose);
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
-- One row per reviewed game: the job record while it runs and the answer
-- afterwards. Keyed by game because a finished game never changes, so its
-- review is computed once and kept. `engine` and `sims` say which engine's
-- opinion this is, which is the only thing that makes the numbers meaningful.
CREATE TABLE IF NOT EXISTS reviews (
    game_id TEXT PRIMARY KEY REFERENCES games(id),
    status TEXT NOT NULL DEFAULT 'pending',
    engine TEXT,
    sims INTEGER,
    progress REAL NOT NULL DEFAULT 0,
    result TEXT,
    error TEXT,
    created TEXT NOT NULL DEFAULT (datetime('now')),
    updated TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS reviews_status ON reviews(status);
"""

# Columns of `reviews` as ALTER TABLE would add them: no `NOT NULL` without a
# default and no non-constant default, which is why `updated` is a plain TEXT
# here and a stamped column in _SCHEMA.
_REVIEW_COLUMNS = (
    ("status", "TEXT NOT NULL DEFAULT 'pending'"),
    ("engine", "TEXT"),
    ("sims", "INTEGER"),
    ("progress", "REAL NOT NULL DEFAULT 0"),
    ("result", "TEXT"),
    ("error", "TEXT"),
    ("created", "TEXT"),
    ("updated", "TEXT"),
)

_conn: sqlite3.Connection | None = None
_lock = threading.Lock()


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring an already-populated database up to the current schema.

    Every step is additive and guarded by its own presence check, so this runs
    on each startup, costs a PRAGMA, and never touches a row twice.
    """
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    if "email" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "email_verified" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 0")
        # Grandfathering, and the only moment it can happen: every account that
        # exists as the column is created signed up when no address was asked
        # for. Shutting them out of rated play to enforce a rule invented
        # afterwards would punish them for our change of mind. Accounts created
        # from here on land in the DEFAULT 0 and must confirm like everyone else.
        conn.execute("UPDATE users SET email_verified = 1")
    # Uniqueness lives in an index because ALTER TABLE cannot add a UNIQUE
    # column; a fresh database gets it here too so both routes agree. NULLs do
    # not collide in SQLite, which is exactly what the address-less
    # grandfathered accounts need.
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email "
                 "ON users(email COLLATE NOCASE)")

    # Reviews arrived long after the first deployment. The table itself comes
    # from _SCHEMA, but CREATE TABLE IF NOT EXISTS does nothing to a database
    # that already holds an earlier version of it, so anything added to the
    # table since needs the same treatment as users.email above.
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(reviews)")}
    for name, decl in _REVIEW_COLUMNS:
        if name not in columns:
            conn.execute(f"ALTER TABLE reviews ADD COLUMN {name} {decl}")


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
    _migrate(conn)
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


def run(sql: str, args: tuple = ()) -> int:
    """Like execute, but returns the affected row count."""
    with _lock:
        conn = connect()
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.rowcount
