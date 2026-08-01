"""Per-ply positions: ``views`` on the game endpoint, and /game/{id}/views.

A view is what the client draws from; ``views`` is one of them per ply, so a
spectator who arrives half way through a game can still scrub back through it
without owning a rules implementation. What is pinned here is the alignment
between the move list and the positions -- one more view than there are moves,
index ``k`` being the board after ``k`` moves -- because that is the part a
front end cannot check for itself: it has no way to tell a correct history
from a plausible one.

The two endpoints are exercised against live, finished and aborted games,
since each takes a different route to the move list (memory for the first,
the games table for the other two) and only agreement between them makes the
contract's "just the per-ply positions" true.

One module, one database, one shared TestClient; every account name in this
file is unique.
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


CLOCK = {"initial": 300, "increment": 3}

# The position before anyone has moved: pawns facing each other on the two
# home ranks, every wall still in hand, Player 1 to move.
START = {"p1": "e1", "p2": "e9", "wallsH": [], "wallsV": [],
         "wallsLeft": [10, 10], "turn": 1}

# A wall from each player among the pawn moves, so every field of a view --
# both pawns, both wall lists, both wall counts, the turn -- changes at a ply
# this file names.
WALL_SCRIPT = ["e2", "e8", "hc3", "vg6", "e3", "e7", "hb5", "d7"]

# The 15-ply win from test_api.py, kept in step with it deliberately: a game
# that ends by reaching the goal is the one case where the last position is
# terminal, and replaying into it must still produce a view.
MATE_SCRIPT = ["e2", "ha1", "e3", "d9", "e4", "e9", "e5", "d9",
               "e6", "e9", "e7", "d9", "e8", "e9", "f9"]


def register(client, name):
    r = client.post("/api/register", json={
        "username": name, "password": "hunter22valid",
        "email": f"{name}@example.test"})
    assert r.status_code == 200, r.text
    # Rated play is gated on a confirmed address; this file is about positions,
    # so it confirms directly. test_email.py owns the verification flow.
    db.execute("UPDATE users SET email_verified = 1 WHERE username = ?", (name,))


def token_for(client, name):
    """A new account and a bearer token, so one TestClient can be both seats."""
    register(client, name)
    r = client.post("/api/token", json={"name": "t", "scopes": ["play"]})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def start_game(client, challenger, dest_name, dest, rated=True):
    """Challenge and accept, leaving the game live. Challenger sits first."""
    r = client.post(f"/api/challenge/{dest_name}", headers=challenger, json={
        "rated": rated, "color": "first", "clock": CLOCK})
    assert r.status_code == 200, r.text
    r = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                    headers=dest)
    assert r.status_code == 200, r.text
    return r.json()["game"]["id"]


def seats(h1, h2):
    """Whose turn it is at each ply: Player 1 opens and they alternate."""
    return {0: h1, 1: h2}


def play(client, gid, headers, ply, token):
    r = client.post(f"/api/game/{gid}/move/{token}", headers=headers)
    assert r.status_code == 200, f"ply {ply + 1} {token}: {r.text}"


def game(client, gid):
    r = client.get(f"/api/game/{gid}")
    assert r.status_code == 200, r.text
    return r.json()


def views_endpoint(client, gid):
    r = client.get(f"/api/game/{gid}/views")
    assert r.status_code == 200, r.text
    return r.json()


def walls_on(view):
    """(horizontal, vertical) wall tokens of a position, order-independent.

    The contract names the walls on the board, not the sequence they were
    played in, so nothing here should depend on the list order.
    """
    return sorted(view["wallsH"]), sorted(view["wallsV"])


# -- shape ------------------------------------------------------------------

def test_finished_game_has_one_view_per_position(client):
    h1 = token_for(client, "vw_fin_a")
    h2 = token_for(client, "vw_fin_b")
    gid = start_game(client, h1, "vw_fin_b", h2)
    by_seat = seats(h1, h2)
    for i, token in enumerate(MATE_SCRIPT):
        play(client, gid, by_seat[i % 2], i, token)

    body = game(client, gid)
    assert body["state"]["status"] == "finished"
    assert body["state"]["reason"] == "mate"

    moves = body["state"]["moves"].split(",")
    assert moves == MATE_SCRIPT
    assert len(body["views"]) == len(moves) + 1

    assert body["views"][0] == START
    # The winning move leaves a terminal position; it is still a position, and
    # the last view has to be the one the response already reports as current.
    assert body["views"][-1] == body["view"] == body["state"]["view"]
    assert body["views"][-1]["p1"] == "f9"


def test_game_with_no_moves_yet_has_only_the_starting_view(client):
    h1 = token_for(client, "vw_empty_a")
    h2 = token_for(client, "vw_empty_b")
    gid = start_game(client, h1, "vw_empty_b", h2)

    body = game(client, gid)
    assert body["state"]["moves"] == ""
    assert body["views"] == [START]

    payload = views_endpoint(client, gid)
    assert payload == {"moves": "", "views": [START]}

    client.post(f"/api/game/{gid}/abort", headers=h1)


def test_unknown_game_is_404_on_both_endpoints(client):
    assert client.get("/api/game/no-such-game").status_code == 404
    r = client.get("/api/game/no-such-game/views")
    assert r.status_code == 404
    assert "error" in r.json()


# -- fidelity ---------------------------------------------------------------

def test_views_track_the_game_ply_by_ply(client):
    """Every field of every named position, not just the two endpoints.

    A history that is right at the start and right at the end can still be
    wrong in the middle -- an off-by-one in the replay would show exactly
    that -- so the interesting plies are spelled out one at a time.
    """
    h1 = token_for(client, "vw_track_a")
    h2 = token_for(client, "vw_track_b")
    gid = start_game(client, h1, "vw_track_b", h2)
    by_seat = seats(h1, h2)
    for i, token in enumerate(WALL_SCRIPT):
        play(client, gid, by_seat[i % 2], i, token)

    v = game(client, gid)["views"]
    assert len(v) == len(WALL_SCRIPT) + 1

    assert v[0] == START

    # Ply 1, Player 1's pawn steps up and the turn passes.
    assert (v[1]["p1"], v[1]["p2"]) == ("e2", "e9")
    assert v[1]["turn"] == 2
    assert v[1]["wallsLeft"] == [10, 10]

    # Ply 2, Player 2 answers: pawns have moved, walls have not.
    assert (v[2]["p1"], v[2]["p2"]) == ("e2", "e8")
    assert walls_on(v[2]) == ([], [])
    assert v[2]["turn"] == 1

    # Ply 3, Player 1 spends a wall: only the first hand shrinks.
    assert walls_on(v[3]) == (["hc3"], [])
    assert v[3]["wallsLeft"] == [9, 10]
    assert (v[3]["p1"], v[3]["p2"]) == ("e2", "e8"), "a wall moves no pawn"
    assert v[3]["turn"] == 2

    # Ply 4, Player 2 spends one too, on the other orientation.
    assert walls_on(v[4]) == (["hc3"], ["vg6"])
    assert v[4]["wallsLeft"] == [9, 9]
    assert v[4]["turn"] == 1

    # Ply 5, back to pawns: the walls of plies 3 and 4 are still standing.
    assert (v[5]["p1"], v[5]["p2"]) == ("e3", "e8")
    assert walls_on(v[5]) == (["hc3"], ["vg6"])
    assert v[5]["wallsLeft"] == [9, 9]
    assert v[5]["turn"] == 2

    # Ply 7, Player 1's second wall accumulates beside the first.
    assert walls_on(v[7]) == (["hb5", "hc3"], ["vg6"])
    assert v[7]["wallsLeft"] == [8, 9]
    assert v[7]["turn"] == 2

    # Ply 8, the last one played: Player 2 sidesteps, Player 1 is to move.
    assert (v[8]["p1"], v[8]["p2"]) == ("e3", "d7")
    assert v[8]["wallsLeft"] == [8, 9]
    assert v[8]["turn"] == 1

    # The turn alternates with every ply, wall or pawn alike.
    assert [x["turn"] for x in v] == [1 + i % 2 for i in range(len(v))]

    r = client.post(f"/api/game/{gid}/resign", headers=h2)
    assert r.status_code == 200, r.text


def test_live_game_views_grow_by_one_with_each_move(client):
    """The live history is append-only, which is what lets a client keep the
    views it has and add the one carried by each gameState."""
    h1 = token_for(client, "vw_live_a")
    h2 = token_for(client, "vw_live_b")
    gid = start_game(client, h1, "vw_live_b", h2)
    by_seat = seats(h1, h2)

    body = game(client, gid)
    assert body["state"]["status"] == "active"
    assert len(body["views"]) == 1

    seen = body["views"]
    for i, token in enumerate(WALL_SCRIPT):
        play(client, gid, by_seat[i % 2], i, token)
        body = game(client, gid)
        assert body["state"]["status"] == "active"
        assert len(body["views"]) == i + 2, f"after ply {i + 1}"
        # Nothing already published may change under the client's feet.
        assert body["views"][:len(seen)] == seen
        assert body["views"][-1] == body["view"]
        seen = body["views"]

    r = client.post(f"/api/game/{gid}/resign", headers=h2)
    assert r.status_code == 200, r.text
    # Retiring the game moves the move list from memory to the games table;
    # the history it yields must not change in the process.
    assert game(client, gid)["views"] == seen


def test_aborted_game_keeps_the_views_of_the_moves_it_had(client):
    h1 = token_for(client, "vw_abort_a")
    h2 = token_for(client, "vw_abort_b")
    gid = start_game(client, h1, "vw_abort_b", h2)
    play(client, gid, h1, 0, "e2")
    r = client.post(f"/api/game/{gid}/abort", headers=h2)
    assert r.status_code == 200, r.text

    body = game(client, gid)
    assert body["state"]["status"] == "aborted"
    assert body["state"]["moves"] == "e2"
    # An abort is not a position: the game stops after the move that was
    # actually played, and the history covers exactly that move.
    assert len(body["views"]) == 2
    assert body["views"][0] == START
    assert body["views"][1]["p1"] == "e2"
    assert body["views"][1]["p2"] == "e9"
    assert body["views"][1]["turn"] == 2
    assert body["views"][-1] == body["view"]
    assert views_endpoint(client, gid)["views"] == body["views"]


# -- the two endpoints agree ------------------------------------------------

def test_views_endpoint_matches_the_game_endpoint(client):
    h1 = token_for(client, "vw_agree_a")
    h2 = token_for(client, "vw_agree_b")
    gid = start_game(client, h1, "vw_agree_b", h2)
    by_seat = seats(h1, h2)
    for i, token in enumerate(WALL_SCRIPT[:5]):
        play(client, gid, by_seat[i % 2], i, token)

    # Live: the move list comes out of memory on both routes.
    body = game(client, gid)
    payload = views_endpoint(client, gid)
    assert payload["views"] == body["views"]
    assert payload["moves"] == body["state"]["moves"] == ",".join(WALL_SCRIPT[:5])
    assert set(payload) == {"moves", "views"}, "views endpoint carries nothing else"

    r = client.post(f"/api/game/{gid}/resign", headers=h2)
    assert r.status_code == 200, r.text

    # Finished: both routes now read the games table instead.
    body = game(client, gid)
    payload = views_endpoint(client, gid)
    assert payload["views"] == body["views"]
    assert payload["moves"] == body["state"]["moves"]
    assert len(payload["views"]) == 6
