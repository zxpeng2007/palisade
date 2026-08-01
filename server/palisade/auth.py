"""Accounts, sessions, bearer tokens, and email verification.

Passwords: scrypt from the standard library, per-user 16-byte salt.
Sessions: opaque random id in an httponly cookie, stored server-side.
API tokens: ``pal_`` + 32 hex chars, only the SHA-256 stored at rest, scopes
comma-joined. Verification tokens work the same way — random, hashed at rest,
single use — because a mail link is a credential like any other.
Nothing here ever logs or returns a secret after creation.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3

from fastapi import HTTPException, Request

from palisade import db

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{2,20}$")
SESSION_COOKIE = "palisade_sid"

# Conservative on purpose: a local part of the ordinary characters, dotted
# labels, and a real alphabetic TLD. We would rather turn away an exotic but
# legal address — whose owner can mail the operator — than accept something
# the provider bounces, which strands the account with no way to confirm it.
_LOCAL = r"[A-Za-z0-9._%+-]+"
_LABEL = r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
EMAIL_RE = re.compile(rf"^{_LOCAL}@{_LABEL}(?:\.{_LABEL})*\.[A-Za-z]{{2,}}$")
EMAIL_MAX = 254  # RFC 5321's longest deliverable path

# SQLite date modifier; API.md promises 24 hours.
EMAIL_TOKEN_TTL = "+24 hours"

_N, _R, _P = 2**14, 8, 1


def _hash_pw(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_email(email: str) -> str:
    """Validate a submitted address and return it as it will be stored.

    Case is preserved — some mailboxes care — while uniqueness is decided
    case-insensitively by the index on the column.
    """
    email = email.strip()
    if len(email) > EMAIL_MAX or not EMAIL_RE.match(email):
        raise HTTPException(400, "that does not look like an email address")
    return email


def _email_taken(email: str, except_user: int | None = None) -> bool:
    row = db.one("SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,))
    return row is not None and row["id"] != except_user


def create_user(username: str, password: str, email: str | None = None,
                is_bot: bool = False) -> int:
    if not USERNAME_RE.match(username):
        raise HTTPException(400, "username must be 2-20 chars: letters, digits, _ or -")
    if len(password) < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    if email is not None:
        email = check_email(email)
    if db.one("SELECT id FROM users WHERE username = ?", (username,)):
        raise HTTPException(409, "username is taken")
    # Said plainly rather than hidden behind "check your mail": usernames
    # already reveal who is registered, so the address buys an enumerator
    # nothing, and a signup that appears to succeed and then never arrives is
    # a worse thing to do to someone than a clear answer.
    if email is not None and _email_taken(email):
        raise HTTPException(409, "that email is already registered")
    salt = secrets.token_bytes(16)
    try:
        return db.execute(
            "INSERT INTO users (username, pw_hash, salt, is_bot, email) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, _hash_pw(password, salt), salt, int(is_bot), email),
        )
    except sqlite3.IntegrityError as e:
        # Two signups can pass the checks above and collide at the index. The
        # index is the real arbiter; the checks only exist for the wording.
        raise HTTPException(409, "that email is already registered"
                            if "email" in str(e) else "username is taken")


def set_email(user_id: int, email: str) -> str:
    """Point an account at a new address, unverified until the link is used."""
    email = check_email(email)
    if _email_taken(email, except_user=user_id):
        raise HTTPException(409, "that email is already registered")
    try:
        db.execute("UPDATE users SET email = ?, email_verified = 0 WHERE id = ?",
                   (email, user_id))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "that email is already registered")
    return email


def check_login(username: str, password: str) -> dict:
    row = db.one("SELECT * FROM users WHERE username = ?", (username,))
    if row is None or not secrets.compare_digest(
        row["pw_hash"], _hash_pw(password, row["salt"])
    ):
        raise HTTPException(401, "invalid username or password")
    return dict(row)


def verify_password(user_id: int, password: str) -> None:
    """Re-prove an already-signed-in account. 403, not 401: the session is
    perfectly good, it is this one action that is being refused."""
    row = db.one("SELECT pw_hash, salt FROM users WHERE id = ?", (user_id,))
    if row is None or not secrets.compare_digest(
        row["pw_hash"], _hash_pw(password, row["salt"])
    ):
        raise HTTPException(403, "that password is not right")


# -- email verification -----------------------------------------------------

def issue_email_token(user_id: int, purpose: str = "verify") -> str:
    """A fresh single-use token, retiring any earlier one for this purpose.

    Old links have to die when a new one is issued, because a token names an
    account and not an address. Left alive, a link mailed to the address an
    account used yesterday would confirm whatever address it holds today —
    a way to have someone else's address marked verified without ever reading
    their mail.
    """
    db.execute("DELETE FROM email_tokens WHERE user_id = ? AND purpose = ?",
               (user_id, purpose))
    plaintext = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO email_tokens (hash, user_id, purpose, expires) "
        "VALUES (?, ?, ?, datetime('now', ?))",
        (_hash_token(plaintext), user_id, purpose, EMAIL_TOKEN_TTL))
    return plaintext


def verify_email_token(token: str) -> dict:
    """Consume a verification link and mark its account verified."""
    row = db.one(
        "SELECT user_id, expires <= datetime('now') AS expired "
        "FROM email_tokens WHERE hash = ?", (_hash_token(token),))
    if row is None:
        raise HTTPException(400, "that verification link is not valid")
    # Consumed either way: an expired token is spent, not retryable.
    db.execute("DELETE FROM email_tokens WHERE hash = ?", (_hash_token(token),))
    if row["expired"]:
        raise HTTPException(400, "that verification link has expired; "
                                 "sign in and ask for another")
    user = _user_by_id(row["user_id"])
    if user is None:
        raise HTTPException(400, "that verification link is not valid")
    db.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user["id"],))
    return user


def is_verified(user_id: int) -> bool:
    row = db.one("SELECT email_verified FROM users WHERE id = ?", (user_id,))
    return bool(row and row["email_verified"])


def require_verified(user: dict, action: str) -> None:
    """Gate for rated play and bot upgrades — the two places where an account
    makes a claim about itself that outlives the game.

    Reads the flag fresh instead of trusting the caller's row: a websocket
    holds the account it authenticated with for the life of the connection,
    and someone who confirms their address in another tab should not have to
    reconnect before the site believes them.
    """
    if not is_verified(user["id"]):
        raise HTTPException(403, f"confirm your email address before {action}")


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


def require_session(request: Request, what: str = "manage tokens") -> dict:
    """Cookie-session auth only. Token management uses this so a leaked or
    limited token can never mint further tokens (scope escalation); the email
    endpoints use it so that changing where an account's mail goes needs the
    browser session, not a token a bot process leaves lying in a config file."""
    sid = request.cookies.get(SESSION_COOKIE)
    if sid:
        row = db.one("SELECT user_id FROM sessions WHERE token = ?", (sid,))
        if row:
            user = _user_by_id(row["user_id"])
            if user:
                return user
    raise HTTPException(401, f"a logged-in session is required to {what}")
