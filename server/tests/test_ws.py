"""WebSocket and concurrency tests: lobby snapshots, seeks, live play.

Same fixture pattern as test_api: one app and one temp database for the
module, unique usernames per test. TestClient runs the app on a portal
thread, so socket messages can interleave (lobby refreshes, our own move
echoes); recv_until / recv_many skip unrelated traffic instead of asserting
strict ordering. The active timer task is deliberately not tested here — the
lazy timeout path is covered in test_api.
"""

import contextlib

import pytest
from fastapi.testclient import TestClient

import murus.auth as auth
import murus.db as db


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    os.environ["MURUS_DB"] = str(tmp_path_factory.mktemp("db") / "test.db")
    db.reset_for_tests()
    from murus.app import app
    with TestClient(app) as c:
        yield c


def session_for(client, name, password="hunter22valid"):
    """Register and return the session as an explicit Cookie header.

    The client's cookie jar is cleared so the one shared TestClient can hold
    several logged-in identities at once.
    """
    r = client.post("/api/register", json={
        "username": name, "password": password,
        "email": f"{name}@example.test"})
    assert r.status_code == 200, r.text
    # Rated seeks are gated on a confirmed address; these tests are about the
    # socket, so confirm it directly. test_email.py owns the actual flow.
    db.execute("UPDATE users SET email_verified = 1 WHERE username = ?", (name,))
    sid = client.cookies.get(auth.SESSION_COOKIE)
    client.cookies.clear()
    return {"cookie": f"{auth.SESSION_COOKIE}={sid}"}


def connect_ws(stack, client, headers=None):
    # Copy the dict: websocket_connect mutates it (adds upgrade headers),
    # and callers reuse the same headers for REST requests.
    return stack.enter_context(
        client.websocket_connect("/ws", headers=dict(headers or {})))


def recv_until(sock, predicate, limit=20):
    """Next message satisfying predicate, skipping unrelated interleavings."""
    seen = []
    for _ in range(limit):
        msg = sock.receive_json()
        seen.append(msg.get("t"))
        if predicate(msg):
            return msg
    raise AssertionError(f"no matching message within {limit}; saw t={seen}")


def recv_many(sock, predicates, limit=20):
    """One message per named predicate, in whatever order they arrive.

    Needed where two messages race on different channels (e.g. the finished
    game state and the personal gameFinish): consuming them with two
    recv_until calls would deadlock if the second arrived first.
    """
    found = {}
    for _ in range(limit):
        msg = sock.receive_json()
        for key, pred in predicates.items():
            if key not in found and pred(msg):
                found[key] = msg
                break
        if len(found) == len(predicates):
            return found
    raise AssertionError(
        f"missing {sorted(set(predicates) - set(found))} within {limit} messages")


def start_ws_game(stack, client, name_a, name_b, clock):
    """Two users meet through ws seeks; sockets returned in seat order."""
    ha = session_for(client, name_a)
    hb = session_for(client, name_b)
    wa = connect_ws(stack, client, ha)
    wb = connect_ws(stack, client, hb)
    wa.send_json({"t": "seek", "rated": False, "clock": clock})
    wb.send_json({"t": "seek", "rated": False, "clock": clock})
    ga = recv_until(wa, lambda m: m.get("t") == "gameStart")["game"]
    gb = recv_until(wb, lambda m: m.get("t") == "gameStart")["game"]
    assert ga["id"] == gb["id"]
    assert {ga["color"], gb["color"]} == {"first", "second"}
    if ga["color"] == "first":
        return wa, wb, ga["id"], ha, hb
    return wb, wa, ga["id"], hb, ha


def test_anonymous_lobby_snapshot(client):
    client.cookies.clear()
    with client.websocket_connect("/ws") as sock:
        sock.send_json({"t": "sub", "ch": "lobby"})
        snap = recv_until(sock, lambda m: m.get("t") == "lobby")
        assert isinstance(snap["seeks"], list)
        assert isinstance(snap["games"], list)
        assert isinstance(snap["bots"], list)


def test_anonymous_move_rejected(client):
    client.cookies.clear()
    with client.websocket_connect("/ws") as sock:
        sock.send_json({"t": "move", "game": "whatever", "move": "e2"})
        err = recv_until(sock, lambda m: m.get("t") == "err")
        assert "sign in" in err["msg"]


def test_seek_over_ws_starts_game(client):
    with contextlib.ExitStack() as stack:
        ha = session_for(client, "ws_ana")
        hb = session_for(client, "ws_abe")
        wa = connect_ws(stack, client, ha)
        wb = connect_ws(stack, client, hb)
        clock = {"initial": 120, "increment": 1}
        wa.send_json({"t": "seek", "rated": False, "clock": clock})
        wb.send_json({"t": "seek", "rated": False, "clock": clock})
        ga = recv_until(wa, lambda m: m.get("t") == "gameStart")["game"]
        gb = recv_until(wb, lambda m: m.get("t") == "gameStart")["game"]
        assert ga["id"] == gb["id"]
        assert {ga["color"], gb["color"]} == {"first", "second"}
        assert ga["opponent"]["username"] == "ws_abe"
        assert gb["opponent"]["username"] == "ws_ana"
        assert ga["clock"] == clock


def test_legal_moves_only_for_the_mover(client):
    with contextlib.ExitStack() as stack:
        first, second, gid, _, _ = start_ws_game(
            stack, client, "ws_mia", "ws_max", {"initial": 130, "increment": 1})
        spectator = connect_ws(stack, client)
        for sock in (first, second, spectator):
            sock.send_json({"t": "sub", "ch": f"game:{gid}"})
        f_full = recv_until(first, lambda m: m.get("t") == "gameFull")
        s_full = recv_until(second, lambda m: m.get("t") == "gameFull")
        sp_full = recv_until(spectator, lambda m: m.get("t") == "gameFull")
        # On subscribe it is first's turn: only their snapshot carries legal.
        assert "e2" in f_full["state"]["legal"]
        assert "legal" not in s_full["state"]
        assert "legal" not in sp_full["state"]

        first.send_json({"t": "move", "game": gid, "move": "e2"})
        at_ply1 = lambda m: m.get("t") == "state" and m.get("moves") == "e2"
        st_second = recv_until(second, at_ply1)
        assert isinstance(st_second["legal"], list) and st_second["legal"]
        assert all(isinstance(tok, str) for tok in st_second["legal"])
        st_first = recv_until(first, at_ply1)
        assert "legal" not in st_first
        st_spec = recv_until(spectator, at_ply1)
        assert "legal" not in st_spec
        assert st_spec["game"] == gid
        assert st_spec["view"]["p1"] == "e2"


def test_illegal_ws_move_leaves_game_unchanged(client):
    with contextlib.ExitStack() as stack:
        first, second, gid, _, _ = start_ws_game(
            stack, client, "ws_ivan", "ws_iris", {"initial": 140, "increment": 1})
        first.send_json({"t": "move", "game": gid, "move": "e9"})
        err = recv_until(first, lambda m: m.get("t") == "err")
        assert "illegal" in err["msg"]
        second.send_json({"t": "move", "game": gid, "move": "e8"})
        err = recv_until(second, lambda m: m.get("t") == "err")
        assert "turn" in err["msg"]
        body = client.get(f"/api/game/{gid}").json()
        assert body["state"]["moves"] == ""
        assert body["state"]["status"] == "active"


def test_scripted_game_finished_by_resign(client):
    with contextlib.ExitStack() as stack:
        first, second, gid, _, _ = start_ws_game(
            stack, client, "ws_rex", "ws_ray", {"initial": 150, "increment": 1})
        for sock in (first, second):
            sock.send_json({"t": "sub", "ch": f"game:{gid}"})
            recv_until(sock, lambda m: m.get("t") == "gameFull")

        moves = ["e2", "e8", "e3", "he5"]
        socks = (first, second)
        for i, tok in enumerate(moves):
            socks[i % 2].send_json({"t": "move", "game": gid, "move": tok})
            # Wait until the next mover has seen this ply before they act,
            # otherwise their move could be processed first and be rejected.
            joined = ",".join(moves[:i + 1])
            recv_until(socks[(i + 1) % 2],
                       lambda m, j=joined: m.get("t") == "state" and m.get("moves") == j)

        second.send_json({"t": "resign", "game": gid})
        for sock in (first, second):
            got = recv_many(sock, {
                "state": lambda m: (m.get("t") == "state"
                                    and m.get("status") == "finished"),
                "finish": lambda m: m.get("t") == "gameFinish",
            })
            assert got["state"]["winner"] == "first"
            assert got["state"]["reason"] == "resign"
            assert got["state"]["moves"] == ",".join(moves)
            assert got["finish"]["game"]["id"] == gid
            assert got["finish"]["game"]["winner"] == "first"
            assert got["finish"]["game"]["reason"] == "resign"


def test_lobby_broadcast_on_new_seek(client):
    h = session_for(client, "ws_lou")
    with contextlib.ExitStack() as stack:
        watcher = connect_ws(stack, client)
        watcher.send_json({"t": "sub", "ch": "lobby"})
        snap = recv_until(watcher, lambda m: m.get("t") == "lobby")
        assert not any(s["username"] == "ws_lou" for s in snap["seeks"])

        r = client.post("/api/seek", headers=h, json={
            "rated": False, "clock": {"initial": 170, "increment": 5}})
        assert r.status_code == 200 and r.json()["matched"] is False
        update = recv_until(watcher, lambda m: m.get("t") == "lobby" and any(
            s["username"] == "ws_lou" for s in m["seeks"]))
        seek = next(s for s in update["seeks"] if s["username"] == "ws_lou")
        assert seek["clock"] == {"initial": 170, "increment": 5}
        assert seek["rated"] is False
    client.delete("/api/seek", headers=h)  # keep the shared lobby clean


def test_rest_move_appears_on_ws(client):
    h1 = session_for(client, "ws_pete")
    h2 = session_for(client, "ws_paula")
    r = client.post("/api/challenge/ws_paula", headers=h1, json={
        "rated": False, "clock": {"initial": 300, "increment": 3},
        "color": "first"})
    assert r.status_code == 200, r.text
    ch_id = r.json()["challenge"]["id"]
    r = client.post(f"/api/challenge/{ch_id}/accept", headers=h2)
    assert r.status_code == 200, r.text
    gid = r.json()["game"]["id"]

    with contextlib.ExitStack() as stack:
        sock = connect_ws(stack, client, h2)  # paula watches her own game
        sock.send_json({"t": "sub", "ch": f"game:{gid}"})
        recv_until(sock, lambda m: m.get("t") == "gameFull" and m.get("id") == gid)

        r = client.post(f"/api/game/{gid}/move/e2", headers=h1)
        assert r.status_code == 200, r.text
        st = recv_until(sock, lambda m: m.get("t") == "state"
                        and m.get("moves") == "e2")
        assert st["game"] == gid
        assert st["view"]["p1"] == "e2"
        assert st["legal"]  # paula to move, on her own authenticated socket


def test_unverified_cannot_open_a_rated_seek_over_the_socket(client):
    """The gate has to live on the socket too.

    The web client posts seeks and challenges over the websocket exclusively,
    so gating only the REST routes left the rule unenforced on the path
    everyone actually uses: an unverified account could sit in the lobby with
    a rated seek.
    """
    r = client.post("/api/register", json={
        "username": "ws_unverified", "password": "hunter22valid",
        "email": "ws_unverified@example.test"})
    assert r.status_code == 200, r.text
    sid = client.cookies.get(auth.SESSION_COOKIE)
    client.cookies.clear()
    headers = {"cookie": f"{auth.SESSION_COOKIE}={sid}"}

    with contextlib.ExitStack() as stack:
        sock = connect_ws(stack, client, headers)
        sock.send_json({"t": "sub", "ch": "lobby"})
        sock.send_json({"t": "seek", "rated": True,
                        "clock": {"initial": 300, "increment": 3}})
        msg = recv_until(sock, lambda m: m.get("t") == "err")
        assert "confirm your email" in msg["msg"].lower()

        # Casual play is deliberately still open, so the site stays usable
        # while the mail is in flight.
        sock.send_json({"t": "seek", "rated": False,
                        "clock": {"initial": 300, "increment": 3}})
        assert recv_until(sock, lambda m: m.get("t") == "lobby" and any(
            s["username"] == "ws_unverified" and not s["rated"]
            for s in m.get("seeks", [])))

        # And it opens the moment the address is confirmed — the gate reads
        # the flag fresh, so no reconnect is needed.
        db.execute("UPDATE users SET email_verified = 1 WHERE username = ?",
                   ("ws_unverified",))
        sock.send_json({"t": "seek", "rated": True,
                        "clock": {"initial": 600, "increment": 0}})
        assert recv_until(sock, lambda m: m.get("t") == "lobby" and any(
            s["username"] == "ws_unverified" and s["rated"]
            for s in m.get("seeks", [])))
