"""Titles: the thresholds, the established-rating rule, and where they surface.

The rules themselves are pure (murus/titles.py) and are exercised directly.
The award path is exercised through real rated games played over the API, with
the accounts' ratings driven into the interesting range first — climbing to
2200 by playing would take several hundred games and prove nothing extra.
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

import murus.db as db
from murus import titles
from murus.events import presence_dec, presence_inc
from murus.lobby import lobby

PASSWORD = "hunter22valid"
BLITZ = {"initial": 300, "increment": 3}


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    os.environ["MURUS_DB"] = str(tmp_path_factory.mktemp("db") / "test.db")
    db.reset_for_tests()
    from murus.app import app
    with TestClient(app) as c:
        yield c


def token_for(client, name):
    r = client.post("/api/register", json={
        "username": name, "password": PASSWORD, "email": f"{name}@example.test"})
    assert r.status_code == 200, r.text
    # Rated play is gated on a confirmed address; the verification flow itself
    # is test_email.py's business.
    db.execute("UPDATE users SET email_verified = 1 WHERE username = ?", (name,))
    r = client.post("/api/token", json={"name": "t", "scopes": ["play"]})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {token}"}


def place(name, rating, rd, title=None, peak=None):
    """Put an account where a few hundred rated games would eventually put it."""
    db.execute(
        "UPDATE users SET rating=?, rd=?, vol=0.06, peak_rating=?, title=? "
        "WHERE username=?",
        (rating, rd, rating if peak is None else peak, title, name))


def account(name):
    return db.one("SELECT * FROM users WHERE username = ?", (name,))


def play(client, h1, h2, second, rated=True):
    """A real game, won by the first player when the second resigns."""
    r = client.post(f"/api/challenge/{second}", headers=h1,
                    json={"rated": rated, "clock": BLITZ, "color": "first"})
    assert r.status_code == 200, r.text
    gid = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                      headers=h2).json()["game"]["id"]
    assert client.post(f"/api/game/{gid}/move/e2", headers=h1).status_code == 200
    assert client.post(f"/api/game/{gid}/move/e8", headers=h2).status_code == 200
    assert client.post(f"/api/game/{gid}/resign", headers=h2).status_code == 200
    return gid


# -- the rules ---------------------------------------------------------------

@pytest.mark.parametrize("rating, title", [
    (2199, None), (2200, "CM"),
    (2299, "CM"), (2300, "FM"),
    (2399, "FM"), (2400, "IM"),
    (2499, "IM"), (2500, "GM"),
    (1500, None), (0, None), (4000, "GM"),
])
def test_each_threshold_boundary(rating, title):
    assert titles.for_rating(rating) == title
    # And the same through the awarding rule, on a settled rating.
    assert titles.awarded(rating, 60.0, None) == title


def test_established_boundary():
    """RD 110 exactly is established; a hair above it is not."""
    assert titles.awarded(2500, 110.0, None) == "GM"
    assert titles.awarded(2500, 110.01, None) is None


@pytest.mark.parametrize("rating", [2200, 2300, 2400, 2500, 3000, 9999])
@pytest.mark.parametrize("rd", [110.5, 111, 150, 250, 350])
def test_no_title_on_an_unestablished_rating(rating, rd):
    assert titles.awarded(rating, rd, None) is None


def test_a_lucky_spike_earns_nothing():
    """The case most likely to be got wrong, stated on its own.

    A fresh account that wins twice against strong opposition can be shown at
    2600 with an RD of 300. That number is a guess nobody has checked; it is
    not a grandmaster.
    """
    assert titles.awarded(2600, 300, None) is None
    # Nor does merely playing on change that while the RD stays high.
    assert titles.awarded(2600, 180, None) is None
    # Once the rating settles, the same peak is worth the title.
    assert titles.awarded(2600, 105, None) == "GM"


def test_a_title_survives_a_long_fall():
    """Held titles outlast the rating that earned them, however far it drops."""
    assert titles.awarded(2500, 60, "GM") == "GM"
    # Even where the record of the peak itself is gone, the title stands: the
    # answer is never lower than what is already held.
    assert titles.awarded(1500, 60, "GM") == "GM"
    assert titles.awarded(1200, 350, "CM") == "CM"


def test_a_title_is_never_downgraded():
    """An international master who slips into master range stays an IM."""
    assert titles.awarded(2350, 60, "IM") == "IM"
    assert titles.awarded(2250, 60, "GM") == "GM"
    # Upgrades still happen, in the one direction they may.
    assert titles.awarded(2500, 60, "IM") == "GM"


def test_rank_orders_the_titles():
    assert titles.rank(None) == 0
    assert (titles.rank("CM") < titles.rank("FM")
            < titles.rank("IM") < titles.rank("GM"))


# -- awarding through a real game --------------------------------------------

def test_award_on_a_real_rated_result(client):
    h1 = token_for(client, "vera")
    h2 = token_for(client, "wolf")
    place("vera", 2450, 60)
    place("wolf", 2450, 60)
    assert account("vera")["title"] is None

    play(client, h1, h2, "wolf")

    # Both are established and above 2400 after the game, so both are IMs; the
    # winner's peak has moved up with the rating, the loser's has not.
    for name in ("vera", "wolf"):
        assert account(name)["title"] == "IM", name
    assert account("vera")["peak_rating"] > 2450
    assert account("vera")["peak_rating"] == pytest.approx(
        account("vera")["rating"])
    assert account("wolf")["rating"] < 2450
    assert account("wolf")["peak_rating"] == 2450


def test_the_title_outlives_the_rating_that_earned_it(client):
    """The loss that costs the threshold does not cost the title."""
    h1 = token_for(client, "xenia")
    h2 = token_for(client, "yuri")
    place("xenia", 2500, 60)
    place("yuri", 2500, 60)

    play(client, h1, h2, "yuri")
    assert account("yuri")["rating"] < 2500   # no longer grandmaster strength
    assert account("yuri")["title"] == "GM"   # grandmaster all the same

    # And a further defeat cannot take it away either.
    h3 = token_for(client, "zola")
    place("zola", 2500, 60)
    play(client, h3, h2, "yuri")
    assert account("yuri")["title"] == "GM"


def test_unestablished_players_earn_nothing_from_a_real_game(client):
    """Two accounts sky-high on a handful of games, playing a rated game."""
    h1 = token_for(client, "aki")
    h2 = token_for(client, "brix")
    place("aki", 2600, 300)
    place("brix", 2600, 300)

    play(client, h1, h2, "brix")

    for name in ("aki", "brix"):
        row = account(name)
        assert row["rd"] > titles.ESTABLISHED_RD, name
        assert row["title"] is None, f"{name} was titled on an unsettled rating"
    # And the peak does not move either. Recording it would only defer the
    # problem: the account could settle at an ordinary strength later and be
    # handed the title then, on the strength of a rating nobody believed when
    # it happened. The peak is the best rating actually held, not the highest
    # number ever touched.
    assert account("aki")["peak_rating"] == 2600
    assert account("brix")["peak_rating"] == 2600


def test_no_title_is_ever_lowered_by_a_later_game(client):
    """An IM whose peak record sits in master range plays on and stays an IM."""
    h1 = token_for(client, "cleo")
    h2 = token_for(client, "dmitri")
    place("cleo", 2600, 60)
    place("dmitri", 2350, 60, title="IM", peak=2350)

    play(client, h1, h2, "dmitri")

    assert account("dmitri")["rating"] < 2350
    assert account("dmitri")["title"] == "IM"
    assert account("cleo")["title"] == "GM"


def test_unrated_games_award_nothing(client):
    h1 = token_for(client, "elif")
    h2 = token_for(client, "faruk")
    place("elif", 2600, 60)
    place("faruk", 2600, 60)

    play(client, h1, h2, "faruk", rated=False)

    for name in ("elif", "faruk"):
        row = account(name)
        assert row["title"] is None, name
        assert row["rated_games"] == 0
        assert row["rating"] == 2600
        assert row["peak_rating"] == 2600


# -- where titles surface ----------------------------------------------------

def test_title_on_profile_leaderboard_and_game(client):
    h1 = token_for(client, "greta")
    h2 = token_for(client, "hugo")
    place("greta", 2550, 60)
    place("hugo", 2550, 60)
    gid = play(client, h1, h2, "hugo")

    profile = client.get("/api/user/greta").json()
    assert profile["title"] == "GM"
    assert profile["peak"] == round(account("greta")["peak_rating"])

    board = client.get("/api/leaderboard").json()["players"]
    row = next(p for p in board if p["username"] == "greta")
    assert row["title"] == "GM"
    # Untitled players carry the field too, as null rather than absent.
    untitled = [p for p in board if p["title"] is None]
    assert untitled, "the suite has no untitled players left to check"

    game = client.get(f"/api/game/{gid}").json()
    assert game["first"]["title"] == "GM"
    assert game["second"]["title"] == "GM"

    top = client.get("/api/games/top").json()
    played = [g for bucket in top["recent"].values() for g in bucket
              if g["id"] == gid]
    assert played and played[0]["first"]["title"] == "GM"

    account_json = client.get("/api/account", headers=h1).json()
    assert account_json["title"] == "GM"
    assert account_json["peak"] == profile["peak"]


def test_title_on_live_games_seeks_and_bots(client):
    h1 = token_for(client, "iris")
    h2 = token_for(client, "jonas")
    place("iris", 2450, 60)
    place("jonas", 2450, 60)
    play(client, h1, h2, "jonas")           # earns both an IM
    assert account("iris")["title"] == "IM"

    # A seek carries the title of whoever posted it. The clock is deliberately
    # unlike any other in the suite so this one sits in the pool unmatched.
    r = client.post("/api/seek", headers=h1,
                    json={"rated": True, "clock": {"initial": 900, "increment": 7}})
    assert r.json()["matched"] is False
    seek = next(s for s in lobby.snapshot()["seeks"] if s["username"] == "iris")
    assert seek["title"] == "IM"
    client.delete("/api/seek", headers=h1)

    # A live game's players, and an online bot in the lobby.
    r = client.post("/api/challenge/jonas", headers=h1,
                    json={"rated": True, "clock": BLITZ, "color": "first"})
    live = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                       headers=h2).json()["game"]
    assert live["first"]["title"] == "IM" and live["second"]["title"] == "IM"

    db.execute("UPDATE users SET is_bot = 1 WHERE username = 'jonas'")
    presence_inc(account("jonas")["id"])
    try:
        snap = lobby.snapshot()
        bot = next(b for b in snap["bots"] if b["username"] == "jonas")
        assert bot["title"] == "IM"
        game = next(g for g in snap["games"] if g["id"] == live["id"])
        assert game["first"]["title"] == "IM"
    finally:
        presence_dec(account("jonas")["id"])
        client.post(f"/api/game/{live['id']}/resign", headers=h2)


# -- migration ---------------------------------------------------------------

# The users table as it stood before titles: the live database's shape, email
# columns and all.
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
    created TEXT NOT NULL DEFAULT (datetime('now')),
    email TEXT,
    email_verified INTEGER NOT NULL DEFAULT 0
);
"""
LEGACY_USERS = [("Selina", 0, 1500.0), ("zhehanz", 0, 1643.0),
                ("Admin", 0, 1499.5), ("MurusBot", 1, 2712.0)]


def test_migration_adds_columns_and_seeds_peak(client, tmp_path, monkeypatch):
    """A database that predates titles gains them without losing anything.

    ``client`` is requested only so the module's own database is already
    connected and MURUS_DB already set: monkeypatch then puts the variable back
    afterwards and the rest of the suite carries on where it left off.
    """
    path = tmp_path / "legacy.db"
    old = sqlite3.connect(path)
    old.executescript(LEGACY_SCHEMA)
    old.executemany(
        "INSERT INTO users (username, pw_hash, salt, is_bot, rating, rated_games) "
        "VALUES (?, X'00', X'01', ?, ?, 40)", LEGACY_USERS)
    old.commit()
    old.close()

    monkeypatch.setenv("MURUS_DB", str(path))
    db.reset_for_tests()
    try:
        def accounts():
            return {r["username"]: r for r in db.query("SELECT * FROM users")}

        migrated = accounts()
        for name, is_bot, rating in LEGACY_USERS:
            row = migrated[name]
            # Seeded from the rating, because no history exists to do better.
            assert row["peak_rating"] == rating, name
            # Nobody is grandfathered into a title; MurusBot is above every
            # threshold and still has to earn it in a rated game.
            assert row["title"] is None, name
            assert row["rating"] == rating and row["is_bot"] == is_bot

        # Repeatable: reconnecting runs the migration again and changes nothing,
        # including on the account whose rating has since moved.
        db.execute("UPDATE users SET rating = 1400 WHERE username = 'zhehanz'")
        db.reset_for_tests()
        assert accounts()["zhehanz"]["peak_rating"] == 1643.0

        # A migrated database and a fresh one agree on the layout of users.
        migrated_columns = [r["name"] for r in
                            db.query("PRAGMA table_info(users)")]
        monkeypatch.setenv("MURUS_DB", str(tmp_path / "fresh.db"))
        db.reset_for_tests()
        assert [r["name"] for r in db.query("PRAGMA table_info(users)")] \
            == migrated_columns
    finally:
        db.reset_for_tests()


def test_a_provisional_spike_never_becomes_a_title_later(client):
    """The loophole worth closing: a spike must not be cashed in afterwards.

    An account that shoots far above its strength while still provisional and
    then settles somewhere ordinary must not collect a title on the strength
    of that spike. API.md awards on the first *established* rating to reach
    the mark, so the peak only moves while the rating is established -- which
    is why this account's peak never records the 2600 it briefly showed.
    """
    h1 = token_for(client, "spiker")
    h2 = token_for(client, "steady")
    # Grandmaster numbers on a handful of games. A real account arrives here
    # with its peak still at the starting rating, which is the point.
    place("spiker", 2600, 300, peak=1500)
    place("steady", 2600, 300, peak=1500)

    play(client, h1, h2, "steady")
    assert account("spiker")["peak_rating"] == 1500, (
        "an unsettled rating must not raise the peak, however high it reads")
    assert account("spiker")["title"] is None

    # The rating settles at a perfectly ordinary strength and play continues.
    # There is nothing banked to cash in.
    place("spiker", 1600, 80, peak=account("spiker")["peak_rating"])
    place("steady", 1600, 80, peak=account("steady")["peak_rating"])
    play(client, h1, h2, "steady")
    row = account("spiker")
    assert row["rd"] <= titles.ESTABLISHED_RD
    assert row["title"] is None, (
        "the spike happened while the rating was unsettled; settling later at "
        "an ordinary strength cannot turn it into a title")
