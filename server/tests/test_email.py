"""Email verification: registration, links, the rated-play gate, migration.

The suite runs in console mode — no PALISADE_RESEND_KEY — so every message
lands in ``mail.outbox`` and the link can be read back out of it, which is
also how a developer works. Sessions are carried as explicit Cookie headers so
one TestClient can hold several identities without a shared jar.
"""

import hashlib
import io
import re
import secrets
import sqlite3
import sys

import pytest
from fastapi.testclient import TestClient

import palisade.db as db
from palisade import auth, mail

PASSWORD = "hunter22valid"
# Seeks pair up on the time control, so the one test that parks a seek uses a
# clock of its own rather than this shared one.
BLITZ = {"initial": 300, "increment": 3}

# The 15-ply scripted win for Player 1, as in test_api.
SCRIPT = ["e2", "ha1", "e3", "d9", "e4", "e9", "e5", "d9",
          "e6", "e9", "e7", "d9", "e8", "e9", "f9"]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    os.environ["PALISADE_DB"] = str(tmp_path_factory.mktemp("db") / "test.db")
    db.reset_for_tests()
    from palisade.app import app
    with TestClient(app) as c:
        yield c


def register(client, name, email=None, password=PASSWORD):
    mail.outbox.clear()
    return client.post("/api/register", json={
        "username": name, "password": password,
        "email": f"{name}@example.test" if email is None else email})


def session_for(client, name, email=None):
    """Register and return (account json, Cookie header for that session)."""
    r = register(client, name, email)
    assert r.status_code == 200, r.text
    sid = client.cookies.get(auth.SESSION_COOKIE)
    client.cookies.clear()
    return r.json(), {"cookie": f"{auth.SESSION_COOKIE}={sid}"}


def token_for(client, name):
    _, cookie = session_for(client, name)
    r = client.post("/api/token", headers=cookie,
                    json={"name": "t", "scopes": ["play", "bot"]})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def sent_token():
    """The verification token from the most recent message."""
    assert mail.outbox, "no mail was sent"
    match = re.search(r"/#/verify/(\S+)", mail.outbox[-1]["text"])
    assert match, mail.outbox[-1]["text"]
    return match.group(1)


def verify_latest(client):
    return client.post("/api/email/verify", json={"token": sent_token()})


def test_registration_requires_a_valid_address(client):
    missing = client.post("/api/register",
                          json={"username": "noaddr", "password": PASSWORD})
    assert missing.status_code == 400 and "email" in missing.json()["error"]
    for bad in ["not-an-address", "who@localhost", "a b@example.test",
                "@example.test", "spaced out@example.test",
                "x" * 250 + "@example.test"]:
        r = register(client, "badaddr", email=bad)
        assert r.status_code == 400, f"{bad!r} was accepted"
    assert not mail.outbox, "a rejected signup must not send mail"

    r = register(client, "goodaddr", email="Good.Addr+tag@example.test")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == "Good.Addr+tag@example.test"
    assert body["emailVerified"] is False
    assert mail.outbox[-1]["to"] == "Good.Addr+tag@example.test"
    client.cookies.clear()


def test_duplicate_address_is_refused(client):
    session_for(client, "dupe_one", email="mia@example.test")
    r = register(client, "dupe_two", email="MIA@Example.Test")
    assert r.status_code == 409
    assert "already registered" in r.json()["error"]
    client.cookies.clear()


def test_link_verifies_exactly_once(client):
    _, cookie = session_for(client, "verifier")
    token = sent_token()

    r = client.post("/api/email/verify", json={"token": token})
    assert r.status_code == 200, r.text
    assert r.json()["username"] == "verifier"
    assert client.get("/api/account", headers=cookie).json()["emailVerified"] is True

    again = client.post("/api/email/verify", json={"token": token})
    assert again.status_code == 400
    assert "not valid" in again.json()["error"]
    assert client.post("/api/email/verify", json={"token": "nonsense"}).status_code == 400


def test_expired_link_is_refused(client):
    account, cookie = session_for(client, "tardy")
    stale = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO email_tokens (hash, user_id, purpose, expires) "
        "VALUES (?, ?, 'verify', datetime('now', '-1 hour'))",
        (hashlib.sha256(stale.encode()).hexdigest(), account["id"]))

    r = client.post("/api/email/verify", json={"token": stale})
    assert r.status_code == 400 and "expired" in r.json()["error"]
    assert client.get("/api/account", headers=cookie).json()["emailVerified"] is False
    # Spent either way, so a stale link cannot be hammered.
    assert db.one("SELECT 1 FROM email_tokens WHERE hash = ?",
                  (hashlib.sha256(stale.encode()).hexdigest(),)) is None


def test_unverified_plays_casual_but_not_rated(client):
    h1 = token_for(client, "unconfirmed")
    h2 = token_for(client, "opponent")

    seek = client.post("/api/seek", headers=h1,
                       json={"rated": True, "clock": BLITZ})
    assert seek.status_code == 403
    assert "email" in seek.json()["error"]

    rated = client.post("/api/challenge/opponent", headers=h1,
                        json={"rated": True, "clock": BLITZ, "color": "first"})
    assert rated.status_code == 403 and "email" in rated.json()["error"]

    upgrade = client.post("/api/bot/upgrade", headers=h1)
    assert upgrade.status_code == 403 and "email" in upgrade.json()["error"]

    # An unconfirmed account is a player, not a spectator: a casual game runs
    # from challenge to mate with nothing in the way.
    r = client.post("/api/challenge/opponent", headers=h1,
                    json={"rated": False, "clock": BLITZ, "color": "first"})
    assert r.status_code == 200, r.text
    gid = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                      headers=h2).json()["game"]["id"]
    seats = {0: h1, 1: h2}
    for i, token in enumerate(SCRIPT):
        move = client.post(f"/api/game/{gid}/move/{token}", headers=seats[i % 2])
        assert move.status_code == 200, f"ply {i + 1} {token}: {move.text}"
    state = client.get(f"/api/game/{gid}").json()["state"]
    assert state["status"] == "finished" and state["winner"] == "first"


def test_confirmed_account_may_play_rated(client):
    _, cookie = session_for(client, "confirmed")
    assert verify_latest(client).status_code == 200
    r = client.post("/api/token", headers=cookie,
                    json={"name": "t", "scopes": ["play", "bot"]})
    headers = {"Authorization": f"Bearer {r.json()['token']}"}

    seek = client.post("/api/seek", headers=headers,
                       json={"rated": True, "clock": {"initial": 61, "increment": 0}})
    assert seek.status_code == 200, seek.text
    assert client.delete("/api/seek", headers=headers).status_code == 200
    assert client.post("/api/bot/upgrade", headers=headers).status_code == 200


def test_rated_challenge_needs_both_seats_confirmed(client):
    _, cookie = session_for(client, "host")
    assert verify_latest(client).status_code == 200
    r = client.post("/api/token", headers=cookie,
                    json={"name": "t", "scopes": ["play"]})
    host = {"Authorization": f"Bearer {r.json()['token']}"}
    guest = token_for(client, "guest")

    r = client.post("/api/challenge/guest", headers=host,
                    json={"rated": True, "clock": BLITZ, "color": "first"})
    assert r.status_code == 200, r.text
    accept = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                         headers=guest)
    assert accept.status_code == 403 and "email" in accept.json()["error"]


def test_resend_is_rate_limited(client):
    _, cookie = session_for(client, "impatient")
    first = sent_token()

    r = client.post("/api/email/resend", headers=cookie)
    assert r.status_code == 200 and r.json()["sent"] is True
    fresh = sent_token()
    assert fresh != first

    again = client.post("/api/email/resend", headers=cookie)
    assert again.status_code == 429 and "minute" in again.json()["error"]

    # Superseding the link is the point of reissuing it: the old one is dead.
    assert client.post("/api/email/verify", json={"token": first}).status_code == 400
    assert client.post("/api/email/verify", json={"token": fresh}).status_code == 200

    mail.outbox.clear()
    settled = client.post("/api/email/resend", headers=cookie)
    assert settled.status_code == 200 and settled.json()["sent"] is False
    assert not mail.outbox, "a verified account must not be mailed again"


def test_change_email_checks_the_password_and_clears_verified(client):
    account, cookie = session_for(client, "mover")
    assert verify_latest(client).status_code == 200
    mail.outbox.clear()

    wrong = client.post("/api/email/change", headers=cookie,
                        json={"email": "elsewhere@example.test",
                              "password": "not-the-password"})
    assert wrong.status_code == 403
    assert client.get("/api/account", headers=cookie).json() == {
        **account, "emailVerified": True}
    assert not mail.outbox

    taken = client.post("/api/email/change", headers=cookie,
                        json={"email": "mia@example.test", "password": PASSWORD})
    assert taken.status_code == 409

    ok = client.post("/api/email/change", headers=cookie,
                     json={"email": "elsewhere@example.test", "password": PASSWORD})
    assert ok.status_code == 200, ok.text
    assert ok.json()["email"] == "elsewhere@example.test"
    assert ok.json()["emailVerified"] is False
    assert mail.outbox[-1]["to"] == "elsewhere@example.test"

    # Back to unconfirmed means back behind the gate.
    assert verify_latest(client).status_code == 200
    assert client.get("/api/account", headers=cookie).json()["emailVerified"] is True


def test_console_mode_is_captured_not_swallowed(client, capsys):
    assert mail.console_mode(), "the suite must run without a Resend key"
    session_for(client, "loud")
    printed = capsys.readouterr().out
    link = mail.verification_link(sent_token())

    assert mail.outbox[-1]["console"] is True
    assert link in printed
    assert "console mode" in printed
    assert "loud@example.test" in printed


def test_a_failed_send_is_reported_not_hidden(client, monkeypatch):
    async def refuse(*args, **kwargs):
        raise mail.MailError("mail provider refused the message (HTTP 422)")

    monkeypatch.setattr(mail, "send_verification", refuse)
    r = register(client, "unreachable")
    assert r.status_code == 502
    assert "could not be sent" in r.json()["error"]
    assert db.one("SELECT email_verified FROM users WHERE username = 'unreachable'"
                  )["email_verified"] == 0
    client.cookies.clear()


def test_resend_api_call_and_its_failures(monkeypatch):
    """The provider path, stubbed at httpx: what goes out, and what a refusal
    does. Console mode covers every other test in this file, so this is the
    only place the production transport is exercised."""
    import asyncio

    import httpx

    seen: dict = {}
    reply: tuple = (200, "{}")

    class StubResponse:
        def __init__(self, status_code, text):
            self.status_code, self.text = status_code, text

    class StubClient:
        def __init__(self, timeout=None):
            seen["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, headers=None):
            seen.update(url=url, json=json, headers=headers)
            if isinstance(reply, Exception):
                raise reply
            return StubResponse(*reply)

    monkeypatch.setattr(httpx, "AsyncClient", StubClient)
    monkeypatch.setenv("PALISADE_RESEND_KEY", "re_pretend_secret")
    monkeypatch.setenv("PALISADE_MAIL_FROM", "Palisade <hello@murus.net>")
    mail.outbox.clear()

    asyncio.run(mail.send_verification("her@example.test", "her", "tok"))
    assert seen["url"] == mail.RESEND_ENDPOINT
    assert seen["timeout"] == mail.TIMEOUT
    assert seen["headers"]["Authorization"] == "Bearer re_pretend_secret"
    assert seen["json"]["from"] == "Palisade <hello@murus.net>"
    assert seen["json"]["to"] == ["her@example.test"]
    assert "/#/verify/tok" in seen["json"]["text"]
    assert "/#/verify/tok" in seen["json"]["html"]
    assert mail.outbox[-1]["console"] is False

    for reply in [(422, '{"message":"the domain is not verified"}'),
                  httpx.ConnectError("no route to host")]:
        mail.outbox.clear()
        with pytest.raises(mail.MailError) as refused:
            asyncio.run(mail.send_verification("her@example.test", "her", "tok"))
        assert "re_pretend_secret" not in str(refused.value)
        assert not mail.outbox, "a message that did not go must not look sent"

    # A key with no sender address is a misconfiguration, and saying so beats
    # letting the provider reject every message for a reason nobody reads.
    reply = (200, "{}")
    monkeypatch.delenv("PALISADE_MAIL_FROM")
    with pytest.raises(mail.MailError):
        asyncio.run(mail.send_verification("her@example.test", "her", "tok"))


def test_console_copy_survives_a_narrow_stdout(monkeypatch):
    # A terminal opened in a legacy encoding must not turn the dash in the
    # message into a UnicodeEncodeError, and a failed signup.
    narrow = io.TextIOWrapper(io.BytesIO(), encoding="ascii")
    monkeypatch.setattr(sys, "stdout", narrow)
    safe = mail._console_safe(mail._bodies("dash", "tok", changed=False)[0])
    monkeypatch.undo()
    safe.encode("ascii")  # raises if anything unprintable survived
    assert "/#/verify/tok" in safe


def test_base_url_drives_the_link(monkeypatch):
    monkeypatch.setenv("PALISADE_BASE_URL", "http://localhost:8000/")
    assert mail.verification_link("abc") == "http://localhost:8000/#/verify/abc"
    monkeypatch.delenv("PALISADE_BASE_URL")
    assert mail.verification_link("abc").startswith("https://murus.net/")


# The schema as it stood before verification existed, with the accounts that
# were live on murus.net at the time.
LEGACY_SCHEMA = """
CREATE TABLE users (
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
"""
LEGACY_USERS = [("Selina", 0, 1500.0), ("zhehanz", 0, 1643.0),
                ("Admin", 0, 1500.0), ("PalisadeBot", 1, 1712.0)]


def test_migration_grandfathers_existing_accounts(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    old = sqlite3.connect(path)
    old.executescript(LEGACY_SCHEMA)
    old.executemany(
        "INSERT INTO users (username, pw_hash, salt, is_bot, rating, rated_games) "
        "VALUES (?, X'00', X'01', ?, ?, 12)", LEGACY_USERS)
    old.commit()
    old.close()

    monkeypatch.setenv("PALISADE_DB", str(path))
    db.reset_for_tests()
    try:
        def accounts():
            return {r["username"]: r for r in db.query("SELECT * FROM users")}

        migrated = accounts()
        assert set(migrated) == {name for name, _, _ in LEGACY_USERS}
        for name, is_bot, rating in LEGACY_USERS:
            row = migrated[name]
            assert row["email"] is None
            assert row["email_verified"] == 1, f"{name} lost its grandfathering"
            # Untouched otherwise: the migration adds columns, it does not
            # rewrite accounts.
            assert row["is_bot"] == is_bot
            assert row["rating"] == rating
            assert row["rated_games"] == 12

        # Repeatable: reconnecting runs the migration again and changes nothing.
        db.reset_for_tests()
        assert {n: dict(r) for n, r in accounts().items()} == \
               {n: dict(r) for n, r in migrated.items()}

        # An account created after the migration confirms like everyone else,
        # and a later run must not sweep it up in the grandfathering.
        auth.create_user("newcomer", PASSWORD, "newcomer@example.test")
        db.reset_for_tests()
        assert accounts()["newcomer"]["email_verified"] == 0

        # Addresses are unique case-insensitively on a migrated database too,
        # while the four address-less accounts sit alongside each other.
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("UPDATE users SET email = 'NEWCOMER@EXAMPLE.TEST' "
                       "WHERE username = 'Admin'")
    finally:
        db.reset_for_tests()
