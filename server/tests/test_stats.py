"""Site statistics.

The counts that matter here are the windowed ones: a total says nothing about
whether the site is alive, and those are also the ones a wrong SQL comparison
would silently return zero for.
"""

import pytest
from fastapi.testclient import TestClient

import murus.db as db

PASSWORD = "hunter22valid"
BLITZ = {"initial": 300, "increment": 3}
RAPID = {"initial": 900, "increment": 10}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    os.environ["MURUS_DB"] = str(tmp_path_factory.mktemp("db") / "test.db")
    db.reset_for_tests()
    from murus.app import app
    with TestClient(app) as c:
        yield c


def token_for(client, name, bot=False):
    r = client.post("/api/register", json={
        "username": name, "password": PASSWORD, "email": f"{name}@example.test"})
    assert r.status_code == 200, r.text
    db.execute("UPDATE users SET email_verified = 1 WHERE username = ?", (name,))
    if bot:
        assert client.post("/api/bot/upgrade").status_code == 200
    tok = client.post("/api/token",
                      json={"name": "t", "scopes": ["play"]}).json()["token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def play(client, h1, h2, second, clock=BLITZ, rated=True):
    r = client.post(f"/api/challenge/{second}", headers=h1,
                    json={"rated": rated, "clock": clock, "color": "first"})
    assert r.status_code == 200, f"challenge: {r.status_code} {r.text}"
    a = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                    headers=h2)
    assert a.status_code == 200, f"accept: {a.status_code} {a.text}"
    gid = a.json()["game"]["id"]
    client.post(f"/api/game/{gid}/move/e2", headers=h1)
    client.post(f"/api/game/{gid}/move/e8", headers=h2)
    client.post(f"/api/game/{gid}/resign", headers=h2)
    return gid


def stats(client):
    r = client.get("/api/stats")
    assert r.status_code == 200, r.text
    return r.json()


def test_empty_site_reports_zeroes_not_errors(client):
    s = stats(client)
    assert s["users"]["total"] == 0
    assert s["games"]["total"] == 0
    assert s["games"]["bySpeed"] == {}
    assert s["games"]["longest"] is None
    assert s["ladder"] == []


def test_counts_follow_real_activity(client):
    h1 = token_for(client, "stat_ann")
    h2 = token_for(client, "stat_ben")
    hb = token_for(client, "stat_engine", bot=True)

    s = stats(client)
    assert s["users"]["total"] == 3
    assert s["users"]["human"] == 2 and s["users"]["bot"] == 1
    assert s["users"]["verified"] == 3
    # Registered just now, so both windows see them. This is the assertion
    # that catches a reversed date comparison, which would read zero forever.
    assert s["users"]["new24h"] == 3 and s["users"]["new7d"] == 3
    assert s["users"]["withRatedGames"] == 0

    play(client, h1, h2, "stat_ben")
    play(client, h1, hb, "stat_engine", clock=RAPID)

    s = stats(client)
    assert s["games"]["total"] == 2
    assert s["games"]["rated"] == 2
    assert s["games"]["finished24h"] == 2
    assert s["games"]["withEngine"] == 1, "one game had an engine in it"
    assert s["games"]["bySpeed"] == {"blitz": 1, "rapid": 1}
    assert s["games"]["byReason"] == {"resign": 2}
    assert s["games"]["longest"]["plies"] == 2
    assert s["users"]["withRatedGames"] == 3


def test_ladder_is_ordered_and_annotated(client):
    s = stats(client)
    ratings = [p["rating"] for p in s["ladder"]]
    assert ratings == sorted(ratings, reverse=True)
    by_name = {p["username"]: p for p in s["ladder"]}
    assert by_name["stat_engine"]["bot"] is True
    assert by_name["stat_ann"]["bot"] is False
    # Nobody here has played enough for a settled rating, let alone a title.
    assert all(p["provisional"] for p in s["ladder"])
    assert all(p["title"] is None for p in s["ladder"])


def test_live_games_are_counted_while_they_run(client):
    h1 = token_for(client, "stat_liv")
    h2 = token_for(client, "stat_lov")
    before = stats(client)["games"]["live"]
    r = client.post("/api/challenge/stat_lov", headers=h1,
                    json={"rated": False, "clock": BLITZ, "color": "first"})
    gid = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                      headers=h2).json()["game"]["id"]
    assert stats(client)["games"]["live"] == before + 1
    client.post(f"/api/game/{gid}/resign", headers=h2)
    assert stats(client)["games"]["live"] == before
    # A casual game leaves the rated count alone.
    assert stats(client)["games"]["rated"] == 2


def test_old_rows_fall_out_of_the_windows(client):
    """A window that never expires is a total wearing a disguise."""
    db.execute("UPDATE users SET created = datetime('now', '-30 days') "
               "WHERE username = 'stat_ann'")
    db.execute("UPDATE games SET finished = datetime('now', '-30 days') "
               "WHERE finished IS NOT NULL")
    s = stats(client)
    assert s["users"]["new24h"] < s["users"]["total"]
    assert s["games"]["finished24h"] == 0
    assert s["games"]["finished7d"] == 0
    assert s["games"]["total"] > 0, "the games themselves are still there"
