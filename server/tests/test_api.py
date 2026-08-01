"""Full-stack API tests over ASGI: accounts, challenges, a complete game.

One app instance and one temp database for the module; usernames are unique
per test. The scripted game exercises pawn racing, a wall, the face-to-face
diagonal, mate detection, and rating updates.
"""

import json
import time

import pytest
from fastapi.testclient import TestClient

import palisade.db as db


@pytest.fixture(scope="module")
def client(tmp_path_factory, module_mocker=None):
    import os
    os.environ["PALISADE_DB"] = str(tmp_path_factory.mktemp("db") / "test.db")
    db.reset_for_tests()
    from palisade.app import app
    with TestClient(app) as c:
        yield c


def register(client, name, password="hunter22valid"):
    r = client.post("/api/register", json={
        "username": name, "password": password,
        "email": f"{name}@example.test"})
    assert r.status_code == 200, r.text
    # These tests are about games, not about email. Rated play and bot
    # upgrades are gated on a confirmed address, so fixtures confirm it
    # directly; the verification flow itself is covered in test_email.py.
    db.execute("UPDATE users SET email_verified = 1 WHERE username = ?", (name,))
    return r


def token_for(client, name, scopes=("play", "bot")):
    register(client, name)
    r = client.post("/api/token", json={"name": "t", "scopes": list(scopes)})
    assert r.status_code == 200
    tok = r.json()["token"]
    assert tok.startswith("pal_")
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


# The 15-ply scripted win for Player 1, ending on a diagonal jump-around.
SCRIPT = ["e2", "ha1", "e3", "d9", "e4", "e9", "e5", "d9",
          "e6", "e9", "e7", "d9", "e8", "e9", "f9"]


def test_register_validation(client):
    good = {"username": "okname", "password": "hunter22valid",
            "email": "okname@example.test"}
    r = client.post("/api/register", json={**good, "username": "x"})
    assert r.status_code == 400 and "error" in r.json()
    r = client.post("/api/register", json={**good, "password": "short"})
    assert r.status_code == 400
    r = client.post("/api/register", json={**good, "email": "not-an-address"})
    assert r.status_code == 400
    register(client, "okname")
    # A distinct address, so this collides on the username and not the email.
    r = client.post("/api/register", json={
        "username": "OKNAME", "password": "hunter22valid",
        "email": "other@example.test"})
    assert r.status_code == 409  # case-insensitive collision
    client.cookies.clear()


def test_auth_required(client):
    assert client.get("/api/account").status_code == 401
    assert client.post("/api/game/nope/move/e2").status_code == 401


def test_scope_enforcement(client):
    h = token_for(client, "scopeless", scopes=("bot",))
    r = client.post("/api/seek", headers=h,
                    json={"clock": {"initial": 300, "increment": 3}})
    assert r.status_code == 403


def test_full_game_with_ratings(client):
    h1 = token_for(client, "alice")
    h2 = token_for(client, "bob")

    r = client.post("/api/challenge/bob", headers=h1, json={
        "rated": True, "clock": {"initial": 300, "increment": 3},
        "color": "first"})
    assert r.status_code == 200, r.text
    ch_id = r.json()["challenge"]["id"]

    r = client.post(f"/api/challenge/{ch_id}/accept", headers=h2)
    assert r.status_code == 200, r.text
    game = r.json()["game"]
    gid = game["id"]
    assert game["first"]["username"] == "alice"

    headers = {0: h1, 1: h2}
    for i, tok in enumerate(SCRIPT):
        r = client.post(f"/api/game/{gid}/move/{tok}", headers=headers[i % 2])
        assert r.status_code == 200, f"ply {i + 1} {tok}: {r.text}"

    r = client.get(f"/api/game/{gid}")
    body = r.json()
    assert body["state"]["status"] == "finished"
    assert body["state"]["winner"] == "first"
    assert body["state"]["reason"] == "mate"

    a = client.get("/api/user/alice").json()
    b = client.get("/api/user/bob").json()
    assert a["rating"] > 1500 > b["rating"]
    assert a["games"] == b["games"] == 1
    assert a["recent"][0]["id"] == gid


def test_wrong_turn_and_illegal(client):
    h1 = token_for(client, "carol")
    h2 = token_for(client, "dave")
    r = client.post("/api/challenge/dave", headers=h1, json={
        "clock": {"initial": 300, "increment": 3}, "color": "first"})
    gid = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                      headers=h2).json()["game"]["id"]
    r = client.post(f"/api/game/{gid}/move/e8", headers=h2)   # not dave's turn
    assert r.status_code == 400 and "turn" in r.json()["error"]
    r = client.post(f"/api/game/{gid}/move/e9", headers=h1)   # illegal
    assert r.status_code == 400 and "illegal" in r.json()["error"]
    r = client.post(f"/api/game/{gid}/move/e2", headers=h1)   # fine
    assert r.status_code == 200
    r = client.post(f"/api/game/{gid}/abort", headers=h2)     # ply 1 < 2: ok
    assert r.status_code == 200
    assert client.get(f"/api/game/{gid}").json()["state"]["status"] == "aborted"


def test_resign_and_unrated(client):
    h1 = token_for(client, "erin")
    h2 = token_for(client, "frank")
    r = client.post("/api/challenge/frank", headers=h1, json={
        "rated": False, "clock": {"initial": 300, "increment": 3}, "color": "first"})
    gid = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                      headers=h2).json()["game"]["id"]
    client.post(f"/api/game/{gid}/move/e2", headers=h1)
    client.post(f"/api/game/{gid}/move/e8", headers=h2)
    r = client.post(f"/api/game/{gid}/resign", headers=h2)
    assert r.status_code == 200
    body = client.get(f"/api/game/{gid}").json()
    assert body["state"]["winner"] == "first"
    assert body["state"]["reason"] == "resign"
    assert client.get("/api/user/erin").json()["rating"] == 1500  # unrated


def test_seek_matching(client):
    h1 = token_for(client, "gina")
    h2 = token_for(client, "hank")
    r = client.post("/api/seek", headers=h1,
                    json={"rated": False, "clock": {"initial": 180, "increment": 2}})
    assert r.json()["matched"] is False
    r = client.post("/api/seek", headers=h2,
                    json={"rated": False, "clock": {"initial": 180, "increment": 2}})
    assert r.json()["matched"] is True


def test_lazy_timeout(client):
    h1 = token_for(client, "ivy")
    h2 = token_for(client, "jack")
    r = client.post("/api/challenge/jack", headers=h1, json={
        "clock": {"initial": 60, "increment": 0}, "color": "first"})
    gid = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                      headers=h2).json()["game"]["id"]
    from palisade.games import manager
    game = manager.get(gid)
    game.remaining[0] = 0.05
    time.sleep(0.2)
    r = client.post(f"/api/game/{gid}/move/e2", headers=h1)
    assert r.status_code == 200  # accepted, but as a flag fall
    body = client.get(f"/api/game/{gid}").json()
    assert body["state"]["status"] == "finished"
    assert body["state"]["winner"] == "second"
    assert body["state"]["reason"] == "timeout"


def test_game_stream_and_events(client):
    h1 = token_for(client, "kate")
    h2 = token_for(client, "liam")
    r = client.post("/api/challenge/liam", headers=h1, json={
        "clock": {"initial": 300, "increment": 3}, "color": "first"})
    gid = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                      headers=h2).json()["game"]["id"]
    client.post(f"/api/game/{gid}/move/e2", headers=h1)
    client.post(f"/api/game/{gid}/resign", headers=h2)
    # Finished game: stream returns gameFull with final state, then closes.
    with client.stream("GET", f"/api/game/stream/{gid}") as s:
        lines = [json.loads(l) for l in s.iter_lines() if l.strip()]
    assert lines[0]["type"] == "gameFull"
    assert lines[0]["state"]["status"] == "finished"
    assert lines[0]["first"]["username"] == "kate"


def test_bot_upgrade_rules(client):
    h = token_for(client, "botty")
    r = client.post("/api/bot/upgrade", headers=h)
    assert r.status_code == 200 and r.json()["bot"] is True
    # alice has a rated game on the books by now
    r2 = client.post("/api/login", json={"username": "alice",
                                         "password": "hunter22valid"})
    assert r2.status_code == 200
    r2 = client.post("/api/bot/upgrade")
    assert r2.status_code == 400
    client.cookies.clear()
