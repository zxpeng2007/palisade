"""Regression tests for the pre-publish review findings.

Each test pins the fixed behaviour of one confirmed finding; the docstrings
name the failure mode so a regression is recognisable from the test name
alone.
"""

import pytest
from fastapi.testclient import TestClient

import palisade.db as db


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    os.environ["PALISADE_DB"] = str(tmp_path_factory.mktemp("db") / "test.db")
    db.reset_for_tests()
    from palisade.app import app
    with TestClient(app) as c:
        yield c


def register(client, name):
    r = client.post("/api/register",
                    json={"username": name, "password": "hunter22valid"})
    assert r.status_code == 200, r.text
    return r


def token_for(client, name):
    register(client, name)
    r = client.post("/api/token", json={"name": "t", "scopes": ["play", "bot"]})
    tok = r.json()["token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def start_game(client, h1, h2, name2, rated=True):
    r = client.post(f"/api/challenge/{name2}", headers=h1, json={
        "rated": rated, "clock": {"initial": 300, "increment": 3},
        "color": "first"})
    ch = r.json()["challenge"]["id"]
    return client.post(f"/api/challenge/{ch}/accept",
                       headers=h2).json()["game"]["id"]


def test_sequential_ratings_do_not_clobber(client):
    """Finding: ratings computed from stale snapshots and written absolutely.

    A challenge created before game 1 finishes used to carry a pre-game-1
    rating snapshot; accepting it after game 1 overwrote game 1's result.
    Two wins must be worth more than one.
    """
    h1 = token_for(client, "rita")
    h2 = token_for(client, "sam")
    # Challenge for game 2 is created BEFORE game 1 is played.
    r = client.post("/api/challenge/sam", headers=h1, json={
        "rated": True, "clock": {"initial": 300, "increment": 3},
        "color": "first"})
    ch2 = r.json()["challenge"]["id"]

    gid1 = start_game(client, h1, h2, "sam")
    client.post(f"/api/game/{gid1}/move/e2", headers=h1)
    client.post(f"/api/game/{gid1}/resign", headers=h2)
    after_one = client.get("/api/user/rita").json()["rating"]
    assert after_one > 1500

    gid2 = client.post(f"/api/challenge/{ch2}/accept",
                       headers=h2).json()["game"]["id"]
    client.post(f"/api/game/{gid2}/move/e2", headers=h1)
    client.post(f"/api/game/{gid2}/resign", headers=h2)
    after_two = client.get("/api/user/rita").json()["rating"]
    assert after_two > after_one, (
        f"second win must build on the first: {after_one} -> {after_two}")


def test_move_on_finished_game_is_400_not_404(client):
    h1 = token_for(client, "tess")
    h2 = token_for(client, "uma")
    gid = start_game(client, h1, h2, "uma", rated=False)
    client.post(f"/api/game/{gid}/move/e2", headers=h1)
    client.post(f"/api/game/{gid}/resign", headers=h2)
    r = client.post(f"/api/game/{gid}/move/e3", headers=h1)
    assert r.status_code == 400
    assert "over" in r.json()["error"]
    assert client.post("/api/game/definitely-not/move/e2",
                       headers=h1).status_code == 404


def test_token_minting_requires_session(client):
    """Finding: any bearer token could mint a token with any scopes."""
    h = token_for(client, "vera")
    r = client.post("/api/token", headers=h,
                    json={"name": "esc", "scopes": ["play", "bot"]})
    assert r.status_code == 401
    assert client.get("/api/token", headers=h).status_code == 401


def test_matching_seek_clears_your_parked_seek(client):
    """Finding: a match removed only the waiting player's seek, so the
    incoming player's earlier seek stayed parked and stacked games."""
    from palisade.lobby import lobby
    h1 = token_for(client, "walt")
    h2 = token_for(client, "xena")
    client.post("/api/seek", headers=h2,
                json={"clock": {"initial": 600, "increment": 0}})
    client.post("/api/seek", headers=h1,
                json={"clock": {"initial": 300, "increment": 3}})
    r = client.post("/api/seek", headers=h2,
                    json={"clock": {"initial": 300, "increment": 3}})
    assert r.json()["matched"] is True
    assert not lobby.seeks, f"seek pool should be empty: {lobby.seeks}"


def test_archived_game_state_includes_view(client):
    h1 = token_for(client, "yuri")
    h2 = token_for(client, "zoe")
    gid = start_game(client, h1, h2, "zoe", rated=False)
    client.post(f"/api/game/{gid}/move/e2", headers=h1)
    client.post(f"/api/game/{gid}/resign", headers=h2)
    body = client.get(f"/api/game/{gid}").json()
    assert body["state"]["view"]["p1"] == "e2"
    assert body["state"]["view"]["wallsLeft"] == [10, 10]


def test_moves_persisted_before_game_ends(client):
    """Finding: moves were only written at game end, so a crash lost every
    in-flight game record."""
    h1 = token_for(client, "abel")
    h2 = token_for(client, "bree")
    gid = start_game(client, h1, h2, "bree", rated=False)
    client.post(f"/api/game/{gid}/move/e2", headers=h1)
    client.post(f"/api/game/{gid}/move/e8", headers=h2)
    row = db.one("SELECT moves, status FROM games WHERE id = ?", (gid,))
    assert row["moves"] == "e2,e8"
    assert row["status"] == "active"


def test_restart_reconciliation(tmp_path):
    """Finding: rows left 'active' by a dead process were stuck forever."""
    import os
    os.environ["PALISADE_DB"] = str(tmp_path / "reboot.db")
    db.reset_for_tests()
    conn = db.connect()
    conn.execute("INSERT INTO users (id, username, pw_hash, salt) "
                 "VALUES (1, 'ghost1', X'00', X'00'), (2, 'ghost2', X'00', X'00')")
    conn.execute("INSERT INTO games (id, p1, p2, rated, initial, increment, "
                 "status, moves) VALUES ('stuckgame', 1, 2, 1, 300, 3, "
                 "'active', 'e2,e8')")
    conn.commit()
    from palisade.app import app
    with TestClient(app) as c:
        body = c.get("/api/game/stuckgame").json()
        assert body["state"]["status"] == "aborted"
        assert body["state"]["reason"] == "abort"
        # The record survived; the rating never moved.
        assert body["state"]["moves"] == "e2,e8"
    db.reset_for_tests()
