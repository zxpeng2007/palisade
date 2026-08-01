"""Discovery endpoints: speed buckets, the Elo ladder, and top games.

The site's Human/Engine switch is assembled entirely from these three things,
so what is pinned here is what a front end cannot recover from on its own:
which bucket a time control falls into, who is allowed onto a ladder and in
what order, and when a game moves from ``live`` to ``recent``.

Ratings are earned by playing rated games through the API rather than written
into the users table. Hand-written Glicko-2 numbers would drift from what the
server actually produces, and the ordering guarantees are only worth testing
against ratings the server made itself.

One module, one database, one shared TestClient: every account name in this
file is unique, and every game started is finished before the test returns
unless the test is specifically about a game in progress.
"""

import pytest
from fastapi.testclient import TestClient

import murus.db as db
from murus import speed


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    os.environ["MURUS_DB"] = str(tmp_path_factory.mktemp("db") / "test.db")
    db.reset_for_tests()
    from murus.app import app
    with TestClient(app) as c:
        yield c


# Clocks chosen so each lands unambiguously in one bucket: 420s, 1300s, 1800s.
BLITZ = (300, 3)
RAPID = (900, 10)
CLASSICAL = (1800, 0)


def register(client, name):
    r = client.post("/api/register", json={
        "username": name, "password": "hunter22valid",
        "email": f"{name}@example.test"})
    assert r.status_code == 200, r.text
    # Leaderboards need rated games, which need a confirmed address. The
    # verification flow itself is covered in test_email.py.
    db.execute("UPDATE users SET email_verified = 1 WHERE username = ?", (name,))


def token_for(client, name):
    """A new account and a bearer token for it.

    The cookie jar is cleared afterwards so one TestClient can act as several
    identities at once; tokens carry the identity from here on.
    """
    register(client, name)
    r = client.post("/api/token", json={"name": "t", "scopes": ["play"]})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def bot_token_for(client, name):
    """Same, but the account is upgraded to an engine before it plays.

    The upgrade is only permitted at zero rated games, so it has to happen
    between registration and the first game.
    """
    register(client, name)
    r = client.post("/api/bot/upgrade")
    assert r.status_code == 200 and r.json()["bot"] is True, r.text
    r = client.post("/api/token", json={"name": "t", "scopes": ["play", "bot"]})
    tok = r.json()["token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def start_game(client, challenger, dest_name, dest, rated=True, clock=BLITZ):
    """Challenge and accept, leaving the game live. Challenger sits first."""
    r = client.post(f"/api/challenge/{dest_name}", headers=challenger, json={
        "rated": rated, "color": "first",
        "clock": {"initial": clock[0], "increment": clock[1]}})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                    headers=dest)
    assert r.status_code == 200, r.text
    return r.json()["game"]["id"]


def play_game(client, challenger, dest_name, dest, rated=True, clock=BLITZ,
              winner="challenger"):
    """A complete game, decided by the loser resigning."""
    gid = start_game(client, challenger, dest_name, dest, rated, clock)
    loser = dest if winner == "challenger" else challenger
    r = client.post(f"/api/game/{gid}/resign", headers=loser)
    assert r.status_code == 200, r.text
    return gid


def ladder(client, kind="all", limit=100, at_speed=None):
    url = f"/api/leaderboard?kind={kind}&limit={limit}"
    if at_speed is not None:
        url += f"&speed={at_speed}"
    r = client.get(url)
    assert r.status_code == 200, r.text
    return r.json()["players"]


def ranked_names(client, **kw):
    return [p["username"] for p in ladder(client, **kw)]


def top_games(client, kind="all", limit=30):
    r = client.get(f"/api/games/top?kind={kind}&limit={limit}")
    assert r.status_code == 200, r.text
    return r.json()


def locate(section, game_id):
    """(speed key, entry) for a game inside a live/recent section, or (None, None)."""
    for cat, games in section.items():
        for g in games:
            if g["id"] == game_id:
                return cat, g
    return None, None


def ids_in(section):
    return {g["id"] for games in section.values() for g in games}


# -- speed categories -------------------------------------------------------

# (initial, increment, estimated seconds, bucket). Every threshold is probed
# twice: once with the increment at zero and once with the same estimate
# reached through the 40x increment term, so a change to either half of
# `initial + 40 * increment` is caught.
BOUNDARIES = [
    (60, 0, 60, "bullet"),          # 1+0, the shortest clock the lobby takes
    (99, 2, 179, "bullet"),
    (179, 0, 179, "bullet"),        # last estimate that is still bullet
    (100, 2, 180, "blitz"),         # increment alone tips it over
    (180, 0, 180, "blitz"),         # 3+0
    (300, 3, 420, "blitz"),         # 5+3
    (399, 2, 479, "blitz"),
    (479, 0, 479, "blitz"),         # last estimate that is still blitz
    (400, 2, 480, "rapid"),
    (480, 0, 480, "rapid"),
    (900, 10, 1300, "rapid"),       # 15+10
    (1099, 10, 1499, "rapid"),
    (1499, 0, 1499, "rapid"),       # last estimate that is still rapid
    (1100, 10, 1500, "classical"),
    (1500, 0, 1500, "classical"),
    (1800, 0, 1800, "classical"),   # 30+0
]


@pytest.mark.parametrize("initial,increment,estimate,expected", BOUNDARIES)
def test_speed_category_boundaries(initial, increment, estimate, expected):
    assert initial + 40 * increment == estimate
    assert speed.category(initial, increment) == expected


def test_speed_order_runs_fastest_to_slowest():
    # The leaderboard validates ?speed= against this tuple and the client
    # renders its columns in this order.
    assert speed.ORDER == ("bullet", "blitz", "rapid", "classical")
    assert {b[3] for b in BOUNDARIES} == set(speed.ORDER)


# -- leaderboard ------------------------------------------------------------

def test_leaderboard_kind_splits_people_from_engines(client):
    h_human_a = token_for(client, "lb_human_a")
    h_human_b = token_for(client, "lb_human_b")
    h_bot_a = bot_token_for(client, "lb_bot_a")
    h_bot_b = bot_token_for(client, "lb_bot_b")
    play_game(client, h_human_a, "lb_human_b", h_human_b)
    play_game(client, h_bot_a, "lb_bot_b", h_bot_b)

    humans = ladder(client, kind="human")
    names = [p["username"] for p in humans]
    assert {"lb_human_a", "lb_human_b"} <= set(names)
    assert not {"lb_bot_a", "lb_bot_b"} & set(names)
    assert all(p["bot"] is False for p in humans)

    bots = ladder(client, kind="bot")
    names = [p["username"] for p in bots]
    assert {"lb_bot_a", "lb_bot_b"} <= set(names)
    assert not {"lb_human_a", "lb_human_b"} & set(names)
    assert all(p["bot"] is True for p in bots)

    everyone = set(ranked_names(client, kind="all"))
    assert {"lb_human_a", "lb_human_b", "lb_bot_a", "lb_bot_b"} <= everyone


def test_leaderboard_only_ranks_players_with_a_rated_game(client):
    h_idle = token_for(client, "lb_idle")
    h_foe = token_for(client, "lb_idle_foe")
    assert "lb_idle" not in ranked_names(client)

    play_game(client, h_foe, "lb_idle", h_idle, rated=False)
    assert "lb_idle" not in ranked_names(client), "unrated games must not rank"

    play_game(client, h_foe, "lb_idle", h_idle, rated=True)
    entry = next(p for p in ladder(client) if p["username"] == "lb_idle")
    assert entry["games"] == 1
    assert entry["provisional"] is True  # one game leaves RD far above 110


def test_leaderboard_orders_by_rating_descending(client):
    h_a = token_for(client, "lb_ord_a")
    h_b = token_for(client, "lb_ord_b")
    h_c = token_for(client, "lb_ord_c")
    play_game(client, h_a, "lb_ord_b", h_b)   # a beats b
    play_game(client, h_a, "lb_ord_c", h_c)   # a beats c
    play_game(client, h_b, "lb_ord_c", h_c)   # b beats c

    ratings = {n: client.get(f"/api/user/{n}").json()["rating"]
               for n in ("lb_ord_a", "lb_ord_b", "lb_ord_c")}
    assert ratings["lb_ord_a"] > ratings["lb_ord_b"] > ratings["lb_ord_c"]

    players = ladder(client)
    place = {p["username"]: i for i, p in enumerate(players)}
    assert place["lb_ord_a"] < place["lb_ord_b"] < place["lb_ord_c"]

    assert [p["rank"] for p in players] == list(range(1, len(players) + 1))
    # Established block first, each block sorted by rating descending.
    flags = [p["provisional"] for p in players]
    assert flags == sorted(flags), "provisional players must all come last"
    for group in (False, True):
        block = [p["rating"] for p in players if p["provisional"] is group]
        assert block == sorted(block, reverse=True)


def test_provisional_players_rank_below_established_ones(client):
    h_a = token_for(client, "lb_set_a")
    h_b = token_for(client, "lb_set_b")
    # Sixteen alternating results pull both RDs from 350 to about 100 while
    # leaving the ratings near 1500 -- an established pair with modest numbers,
    # which is exactly the case a rating-only sort would get wrong.
    for i in range(16):
        play_game(client, h_a, "lb_set_b", h_b,
                  winner="challenger" if i % 2 == 0 else "dest")

    h_new = token_for(client, "lb_new_a")
    h_prey = token_for(client, "lb_new_b")
    play_game(client, h_new, "lb_new_b", h_prey)  # one win, RD still ~290

    players = ladder(client)
    by_name = {p["username"]: p for p in players}
    place = {p["username"]: i for i, p in enumerate(players)}
    settled = by_name["lb_set_a"], by_name["lb_set_b"]
    newcomer = by_name["lb_new_a"]

    assert all(p["provisional"] is False for p in settled)
    assert newcomer["provisional"] is True
    assert newcomer["rating"] > max(p["rating"] for p in settled)
    assert place["lb_new_a"] > max(place["lb_set_a"], place["lb_set_b"]), (
        "a provisional 1600 must still rank below an established 1500")


def test_leaderboard_limit_is_respected_and_clamped(client):
    # The upper clamp needs more ranked players than any suite could play
    # games for, so these are the one set of rows written directly. They are
    # provisional and low-rated, so they sort behind every real account, and
    # they are deleted again before any other test can see them.
    padding = [f"pad_{i:03d}" for i in range(105)]
    try:
        for i, name in enumerate(padding):
            db.execute(
                """INSERT INTO users (username, pw_hash, salt, rating,
                   rated_games) VALUES (?, X'00', X'00', ?, 1)""",
                (name, 900 + i))
        assert len(ladder(client, limit=3)) == 3
        assert len(ladder(client, limit=0)) == 1, "limit is clamped up to 1"
        assert len(ladder(client, limit=500)) == 100, "and down to 100"
    finally:
        for name in padding:
            db.run("DELETE FROM users WHERE username = ?", (name,))
    assert not [n for n in ranked_names(client) if n.startswith("pad_")]


def test_leaderboard_speed_filter_needs_a_game_at_that_speed(client):
    h_fast_a = token_for(client, "lb_fast_a")
    h_fast_b = token_for(client, "lb_fast_b")
    h_slow_a = token_for(client, "lb_slow_a")
    h_slow_b = token_for(client, "lb_slow_b")
    play_game(client, h_fast_a, "lb_fast_b", h_fast_b, clock=BLITZ)
    play_game(client, h_slow_a, "lb_slow_b", h_slow_b, clock=CLASSICAL)

    blitz = set(ranked_names(client, at_speed="blitz"))
    assert {"lb_fast_a", "lb_fast_b"} <= blitz
    assert not {"lb_slow_a", "lb_slow_b"} & blitz

    classical = set(ranked_names(client, at_speed="classical"))
    assert {"lb_slow_a", "lb_slow_b"} <= classical
    assert not {"lb_fast_a", "lb_fast_b"} & classical

    r = client.get("/api/leaderboard?speed=blitz")
    assert r.json()["speed"] == "blitz"
    assert client.get("/api/leaderboard").json()["speed"] is None


def test_leaderboard_rejects_unknown_filters(client):
    assert client.get("/api/leaderboard?kind=android").status_code == 400
    assert client.get("/api/leaderboard?speed=hyperbullet").status_code == 400
    assert client.get("/api/leaderboard?kind=all&speed=rapid").status_code == 200
    body = client.get("/api/leaderboard?kind=bot").json()
    assert body["kind"] == "bot"


# -- top games --------------------------------------------------------------

def test_live_game_moves_to_recent_when_it_ends(client):
    h1 = token_for(client, "top_live_a")
    h2 = token_for(client, "top_live_b")
    gid = start_game(client, h1, "top_live_b", h2, clock=RAPID)

    top = top_games(client, kind="human")
    cat, entry = locate(top["live"], gid)
    assert cat == "rapid"
    assert entry["speed"] == "rapid"
    assert entry["ply"] == 0 and entry["rated"] is True
    assert entry["clock"] == {"initial": 900, "increment": 10}
    assert entry["first"]["username"] == "top_live_a"
    assert entry["second"]["username"] == "top_live_b"
    assert locate(top["recent"], gid) == (None, None)

    assert client.post(f"/api/game/{gid}/move/e2", headers=h1).status_code == 200
    _, entry = locate(top_games(client, kind="human")["live"], gid)
    assert entry["ply"] == 1, "ply tracks the game as it is played"

    assert client.post(f"/api/game/{gid}/resign", headers=h2).status_code == 200
    top = top_games(client, kind="human")
    assert locate(top["live"], gid) == (None, None), "a finished game is not live"
    cat, entry = locate(top["recent"], gid)
    assert cat == "rapid"
    assert entry["winner"] == "first" and entry["reason"] == "resign"
    assert entry["finished"]


def test_avg_rating_is_the_mean_of_both_players(client):
    h1 = token_for(client, "top_avg_a")
    h2 = token_for(client, "top_avg_b")
    play_game(client, h1, "top_avg_b", h2)  # pull the two ratings apart first
    r1 = client.get("/api/user/top_avg_a").json()["rating"]
    r2 = client.get("/api/user/top_avg_b").json()["rating"]
    assert r1 != r2

    gid = start_game(client, h1, "top_avg_b", h2, clock=RAPID)
    _, entry = locate(top_games(client, kind="human")["live"], gid)
    assert (entry["first"]["rating"], entry["second"]["rating"]) == (r1, r2)
    assert entry["avgRating"] == round((r1 + r2) / 2)

    client.post(f"/api/game/{gid}/resign", headers=h2)
    _, entry = locate(top_games(client, kind="human")["recent"], gid)
    # A finished game reports the ratings as they stood when it started, so
    # the average must be taken from those and not from the new ones.
    row = db.one("SELECT p1_rating, p2_rating FROM games WHERE id = ?", (gid,))
    assert entry["first"]["rating"] == round(row["p1_rating"])
    assert entry["second"]["rating"] == round(row["p2_rating"])
    assert entry["avgRating"] == round((row["p1_rating"] + row["p2_rating"]) / 2)


def test_top_games_kind_matches_on_at_least_one_player(client):
    """A person against an engine belongs to both audiences.

    Under a both-players rule those games appeared in no mode at all: on the
    live site four of five games were invisible in both human and engine
    mode. `kind` therefore selects games containing at least one player of
    that kind, and mixed games deliberately show up twice.
    """
    h_bot_1 = bot_token_for(client, "tg_bot_one")
    h_bot_2 = bot_token_for(client, "tg_bot_two")
    h_human_1 = token_for(client, "tg_human_one")
    h_human_2 = token_for(client, "tg_human_two")
    engines = play_game(client, h_bot_1, "tg_bot_two", h_bot_2, clock=RAPID)
    people = play_game(client, h_human_1, "tg_human_two", h_human_2, clock=RAPID)
    mixed = play_game(client, h_bot_1, "tg_human_two", h_human_2, clock=RAPID)

    bot_ids = ids_in(top_games(client, kind="bot")["recent"])
    assert engines in bot_ids and mixed in bot_ids
    assert people not in bot_ids

    human_ids = ids_in(top_games(client, kind="human")["recent"])
    assert people in human_ids and mixed in human_ids
    assert engines not in human_ids

    all_ids = ids_in(top_games(client, kind="all")["recent"])
    assert {engines, people, mixed} <= all_ids


def test_empty_speed_buckets_are_omitted(client):
    h1 = bot_token_for(client, "tg_empty_a")
    h2 = bot_token_for(client, "tg_empty_b")
    play_game(client, h1, "tg_empty_b", h2, clock=RAPID)

    top = top_games(client)
    assert all(games for games in top["live"].values())
    assert all(games for games in top["recent"].values())

    # The engine ladder is made entirely of games this file played, all of
    # them blitz or rapid, so the two unused speeds are missing keys rather
    # than empty lists -- and with every engine game finished, the live
    # section is an empty object rather than four empty buckets.
    bots = top_games(client, kind="bot")
    assert "rapid" in bots["recent"]
    assert "bullet" not in bots["recent"] and "classical" not in bots["recent"]
    assert bots["live"] == {}


def test_two_time_controls_land_in_two_buckets(client):
    h1 = token_for(client, "tg_two_a")
    h2 = token_for(client, "tg_two_b")
    quick = start_game(client, h1, "tg_two_b", h2, clock=RAPID)
    slow = start_game(client, h1, "tg_two_b", h2, clock=CLASSICAL)

    live = top_games(client, kind="human")["live"]
    assert locate(live, quick)[0] == "rapid"
    assert locate(live, slow)[0] == "classical"

    client.post(f"/api/game/{quick}/resign", headers=h2)
    client.post(f"/api/game/{slow}/resign", headers=h2)
    recent = top_games(client, kind="human")["recent"]
    assert locate(recent, quick)[0] == "rapid"
    assert locate(recent, slow)[0] == "classical"


def test_top_games_rejects_unknown_kind(client):
    assert client.get("/api/games/top?kind=cyborg").status_code == 400
    body = client.get("/api/games/top").json()
    assert set(body) == {"live", "recent"}
