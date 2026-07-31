"""Accounts, sessions, and bearer tokens.

Passwords: scrypt from the standard library, per-user 16-byte salt.
Sessions: opaque random id in an httponly cookie, stored server-side.
API tokens: ``pal_`` + 32 hex chars, only the SHA-256 stored at rest, scopes
comma-joined. Nothing here ever logs or returns a secret after creation.
"""

from __future__ import annotations

import hashlib
import re
import secrets

from fastapi import HTTPException, Request

from palisade import db

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{2,20}$")
SESSION_COOKIE = "palisade_sid"

_N, _R, _P = 2**14, 8, 1


def _hash_pw(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)


def create_user(username: str, password: str, is_bot: bool = False) -> int:
    if not USERNAME_RE.match(username):
        raise HTTPException(400, "username must be 2-20 chars: letters, digits, _ or -")
    if len(password) < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    if db.one("SELECT id FROM users WHERE username = ?", (username,)):
        raise HTTPException(409, "username is taken")
    salt = secrets.token_bytes(16)
    return db.execute(
        "INSERT INTO users (username, pw_hash, salt, is_bot) VALUES (?, ?, ?, ?)",
        (username, _hash_pw(password, salt), salt, int(is_bot)),
    )


def check_login(username: str, password: str) -> dict:
    row = db.one("SELECT * FROM users WHERE username = ?", (username,))
    if row is None or not secrets.compare_digest(
        row["pw_hash"], _hash_pw(password, row["salt"])
    ):
        raise HTTPException(401, "invalid username or password")
    return dict(row)


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    return token


def drop_session(token: str) -> None:
    db.execute("DELETE FROM sessions WHERE token = ?", (token,))


def create_token(user_id: int, name: str, scopes: list[str]) -> str:
    allowed = {"play", "bot"}
    if not scopes or not set(scopes) <= allowed:
        raise HTTPException(400, f"scopes must be a non-empty subset of {sorted(allowed)}")
    plaintext = "pal_" + secrets.token_hex(16)
    db.execute(
        "INSERT INTO tokens (hash, user_id, name, scopes) VALUES (?, ?, ?, ?)",
        (hashlib.sha256(plaintext.encode()).hexdigest(), user_id, name, ",".join(scopes)),
    )
    return plaintext


def _user_by_id(user_id: int) -> dict | None:
    row = db.one("SELECT * FROM users WHERE id = ?", (user_id,))
    return dict(row) if row else None


def resolve(request: Request) -> tuple[dict, set[str]] | None:
    """(user, scopes) for this request, or None. Sessions get all scopes."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        h = hashlib.sha256(header[7:].strip().encode()).hexdigest()
        row = db.one("SELECT * FROM tokens WHERE hash = ?", (h,))
        if row is None:
            return None
        user = _user_by_id(row["user_id"])
        return (user, set(row["scopes"].split(","))) if user else None
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        row = db.one("SELECT user_id FROM sessions WHERE token = ?", (sid,))
        if row:
            user = _user_by_id(row["user_id"])
            if user:
                return user, {"play", "bot"}
    return None


def require(request: Request, scope: str | None = None) -> dict:
    got = resolve(request)
    if got is None:
        raise HTTPException(401, "authentication required")
    user, scopes = got
    if scope and scope not in scopes:
        raise HTTPException(403, f"token lacks the '{scope}' scope")
    return user
