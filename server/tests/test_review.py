"""Game review: the numbers, the endpoints, and the job that produces them.

A real engine is optional here, and deliberately so. Everything that decides
what a review *says* -- the bands, the point of view, the accuracy curve -- is
arithmetic, and is tested directly. The machinery around it is tested against a
stand-in engine, so a machine with no checkpoint (CI, a laptop) still exercises
the endpoints, the worker, the sign convention and the terminal-position case.
Only the test that needs a real network to be loaded is skipped.
"""

import asyncio
import importlib.util
import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from quoridor import fastrules as fr

import palisade.db as db
from palisade import review, rules
from palisade.notation import legal_token_map


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    import os
    os.environ["PALISADE_DB"] = str(tmp_path_factory.mktemp("db") / "test.db")
    db.reset_for_tests()
    from palisade.app import app
    with TestClient(app) as c:
        yield c


def token_for(client, name):
    r = client.post("/api/register", json={
        "username": name, "password": "hunter22valid",
        "email": f"{name}@example.test"})
    assert r.status_code == 200, r.text
    r = client.post("/api/token", json={"name": "t", "scopes": ["play"]})
    tok = r.json()["token"]
    client.cookies.clear()
    return {"Authorization": f"Bearer {tok}"}


def start_game(client, a, b):
    """A live game between two fresh accounts, `a` on the first seat."""
    h1, h2 = token_for(client, a), token_for(client, b)
    r = client.post(f"/api/challenge/{b}", headers=h1, json={
        "rated": False, "clock": {"initial": 300, "increment": 3},
        "color": "first"})
    assert r.status_code == 200, r.text
    gid = client.post(f"/api/challenge/{r.json()['challenge']['id']}/accept",
                      headers=h2).json()["game"]["id"]
    return gid, (h1, h2)


# The same 15-ply win Player 1 scores in test_api: a race, one wall, and a
# diagonal jump-around at the end, so a review of it meets both kinds of move.
SCRIPT = ["e2", "ha1", "e3", "d9", "e4", "e9", "e5", "d9",
          "e6", "e9", "e7", "d9", "e8", "e9", "f9"]


def played_out(client, a, b):
    """A finished game, and its id."""
    gid, headers = start_game(client, a, b)
    for i, token in enumerate(SCRIPT):
        r = client.post(f"/api/game/{gid}/move/{token}", headers=headers[i % 2])
        assert r.status_code == 200, f"ply {i + 1} {token}: {r.text}"
    return gid


def wait_for(client, gid, statuses, timeout=120.0):
    body = None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        body = client.get(f"/api/game/{gid}/review").json()
        if body["status"] in statuses:
            return body
        time.sleep(0.02)
    raise AssertionError(f"review of {gid} never reached {statuses}: {body}")


# -- the numbers ------------------------------------------------------------

def test_bands_are_upper_bounds():
    """Every band from API.md, checked on both sides of its boundary."""
    assert review.classify(0.0, False) == "excellent"
    assert review.classify(0.02, False) == "excellent"
    assert review.classify(0.0201, False) == "good"
    assert review.classify(0.05, False) == "good"
    assert review.classify(0.0501, False) == "inaccuracy"
    assert review.classify(0.10, False) == "inaccuracy"
    assert review.classify(0.1001, False) == "mistake"
    assert review.classify(0.20, False) == "mistake"
    assert review.classify(0.2001, False) == "blunder"
    assert review.classify(1.0, False) == "blunder"


def test_agreeing_with_the_engine_is_best_whatever_the_loss():
    # A move the engine chose gave nothing up by definition; the loss argument
    # must not be able to talk the label down.
    assert review.classify(0.0, True) == "best"
    assert review.classify(0.9, True) == "best"


def test_brilliant_needs_both_a_dismissed_prior_and_a_wide_margin():
    dismissed, obvious = 0.019, 0.5
    wide, narrow = 0.16, 0.14
    assert review.classify(0.0, True, prior=dismissed, margin=wide) == "brilliant"
    assert review.classify(0.0, True, prior=obvious, margin=wide) == "best"
    assert review.classify(0.0, True, prior=dismissed, margin=narrow) == "best"
    # Both thresholds are exclusive: exactly at them is not brilliant.
    assert review.classify(0.0, True, prior=0.02, margin=0.5) == "best"
    assert review.classify(0.0, True, prior=0.001, margin=0.15) == "best"


def test_eval_is_always_from_the_first_players_point_of_view():
    # The engine speaks for whoever is to move. Player 1 moves on odd plies,
    # so a value at an even ply belongs to Player 2 and has to be turned round.
    assert review.eval_from_first(0.4, 1) == 0.4
    assert review.eval_from_first(0.4, 3) == 0.4
    # A position bad for Player 2, on Player 2's move, is good for Player 1.
    assert review.eval_from_first(-0.5, 2) == 0.5
    assert review.eval_from_first(0.5, 2) == -0.5
    assert review.eval_from_first(-0.5, 4) == 0.5
    # A won position reads +1 for Player 1 from either side of the board.
    assert review.eval_from_first(1.0, 1) == 1.0
    assert review.eval_from_first(-1.0, 2) == 1.0


def test_win_probability_maps_the_value_range_onto_zero_to_one():
    assert review.win_probability(-1.0) == 0.0
    assert review.win_probability(0.0) == 0.5
    assert review.win_probability(1.0) == 1.0
    # Values arrive from an average of network outputs and can overshoot.
    assert review.win_probability(-1.4) == 0.0
    assert review.win_probability(1.4) == 1.0


def test_accuracy_is_monotonic_bounded_and_anchored():
    losses = [i / 100 for i in range(0, 101)]
    scores = [review.accuracy(x) for x in losses]
    assert scores[0] == 100.0
    assert all(0.0 < s <= 100.0 for s in scores)
    assert all(a > b for a, b in zip(scores, scores[1:]))
    # The constant is chosen so an average cost of 0.05 win probability -- the
    # top of the "good" band -- reads as 85%.
    assert review.accuracy(0.05) == pytest.approx(85.0, abs=0.1)
    assert review.accuracy(0.20) < review.accuracy(0.10) < review.accuracy(0.05)


# -- the endpoints ----------------------------------------------------------

def test_review_of_a_live_game_is_refused(client):
    gid, headers = start_game(client, "livegame1", "livegame2")
    client.post(f"/api/game/{gid}/move/e2", headers=headers[0])
    r = client.post(f"/api/game/{gid}/review")
    assert r.status_code == 400
    assert "finished" in r.json()["error"]
    # And nothing was queued behind the refusal.
    assert db.one("SELECT 1 FROM reviews WHERE game_id = ?", (gid,)) is None


def test_review_of_an_unknown_game_is_not_found(client):
    """An unknown id is 404 on both verbs, as everywhere else on this API.

    Folding it into the 400 would leave a client unable to tell a mistyped
    game id from a game that is merely still being played.
    """
    r = client.post("/api/game/nosuchgame/review")
    assert r.status_code == 404 and "error" in r.json()
    assert client.get("/api/game/nosuchgame/review").status_code == 404


def test_get_before_any_request_says_there_is_none(client):
    gid = played_out(client, "nonereview1", "nonereview2")
    body = client.get(f"/api/game/{gid}/review").json()
    assert body["status"] == "none"
    # Even with nothing to show it names the engine a review would come from,
    # so a client can say what it is offering to run.
    assert body["engine"] == review.engine_name()
    assert body["sims"] == review.configured_sims()


def test_a_second_request_starts_nothing(client, monkeypatch):
    monkeypatch.setattr(review, "get_engine", lambda: StubEngine())
    gid = played_out(client, "idempotent1", "idempotent2")
    first = client.post(f"/api/game/{gid}/review")
    second = client.post(f"/api/game/{gid}/review")
    assert first.status_code == second.status_code == 200
    # The row is the job record, so one row means one job.
    assert len(db.query("SELECT 1 FROM reviews WHERE game_id = ?", (gid,))) == 1

    done = wait_for(client, gid, ("done", "failed"))
    assert done["status"] == "done"
    # A finished review is never recomputed: asking again hands back the
    # stored answer, untouched.
    again = client.post(f"/api/game/{gid}/review").json()
    assert again == done


def test_a_request_while_one_runs_does_not_queue_a_second(client):
    gid = played_out(client, "running1", "running2")
    db.execute("""INSERT INTO reviews (game_id, status, engine, sims, progress)
                  VALUES (?, 'running', 'gen-x', 600, 0.5)""", (gid,))
    # Reaching into the worker's queue is the only way to see the difference
    # between "started nothing" and "started something that finished fast".
    depth = review._queue.qsize()
    body = client.post(f"/api/game/{gid}/review").json()
    assert body["status"] == "running" and body["progress"] == 0.5
    assert review._queue.qsize() == depth
    assert db.one("SELECT status FROM reviews WHERE game_id = ?",
                  (gid,))["status"] == "running"


def test_a_review_interrupted_by_a_restart_is_picked_up_again(client, monkeypatch):
    """A row the last process died holding is queued again by the next one."""
    gid = played_out(client, "restart1", "restart2")
    db.execute("""INSERT INTO reviews (game_id, status, engine, sims, progress)
                  VALUES (?, 'running', 'stub', 32, 0.4)""", (gid,))
    # A game whose review is already an answer, for the negative case.
    settled, headers = start_game(client, "restart3", "restart4")
    client.post(f"/api/game/{settled}/resign", headers=headers[1])
    db.execute("""INSERT INTO reviews (game_id, status, engine, sims, progress,
                  result) VALUES (?, 'done', 'stub', 32, 1, '{}')""", (settled,))
    # start() installs a fresh queue; hand the old one back afterwards, since
    # the fixture's worker is still draining it.
    monkeypatch.setattr(review, "_queue", review._queue)

    async def restart():
        worker = review.start()
        # What is being tested is the row and the queue, not a second drain.
        worker.cancel()
        queued = []
        while not review._queue.empty():
            queued.append(review._queue.get_nowait())
        return queued

    queued = asyncio.run(restart())
    assert gid in queued
    row = db.one("SELECT status, progress FROM reviews WHERE game_id = ?", (gid,))
    # Half-finished work is not worth keeping: it starts again from the top.
    assert row["status"] == "pending" and row["progress"] == 0
    # A review that finished is an answer about a game that cannot change, so
    # no restart ever recomputes it.
    assert settled not in queued


def test_a_missing_engine_fails_the_review_and_not_the_server(client,
                                                              monkeypatch,
                                                              tmp_path):
    monkeypatch.setenv("PALISADE_REVIEW_CHECKPOINT", str(tmp_path / "absent.pt"))
    gid = played_out(client, "noengine1", "noengine2")
    assert client.post(f"/api/game/{gid}/review").status_code == 200
    body = wait_for(client, gid, ("done", "failed"), timeout=60.0)
    assert body["status"] == "failed"
    # Either flavour of missing engine -- no checkpoint here, or no torch at
    # all on a machine that never had one -- has to say so in the answer.
    assert "engine" in body["error"]
    # The server is still answering, and the game itself is untouched.
    assert client.get(f"/api/game/{gid}").status_code == 200


# -- the whole job, against a stand-in engine -------------------------------

class StubEngine:
    """An engine with fixed opinions, so the assembly can be tested without one.

    It prefers the lowest-numbered legal action -- which is a wall, and so
    rarely what a player did, but is exactly what the game's one wall move is.
    That gives a review containing both the agreed and the disagreed case. The
    value it reports is always from the mover's point of view, and always the
    same, which is what makes the point-of-view convention visible: a correct
    review must report it alternating.
    """

    name = "stub"
    sims = 32
    VALUE = 0.06

    def search(self, position):
        scratch = rules.make_scratch()
        legal = sorted(legal_token_map(position, scratch).values())
        best, second = legal[0], legal[1]
        visits = np.zeros(fr.NUM_ACTIONS, dtype=np.float32)
        visits[best], visits[second] = 24.0, 8.0
        q = np.full(fr.NUM_ACTIONS, np.nan)
        q[best], q[second] = self.VALUE, self.VALUE - 0.2
        priors = np.zeros(fr.NUM_ACTIONS, dtype=np.float32)
        priors[best], priors[second] = 0.5, 0.2
        return review._Search(visits, q, priors, self.VALUE)


def test_a_full_review_of_a_finished_game(client, monkeypatch):
    monkeypatch.setattr(review, "get_engine", lambda: StubEngine())
    gid = played_out(client, "stubbed1", "stubbed2")

    started = client.post(f"/api/game/{gid}/review").json()
    assert started["status"] in ("pending", "running", "done")
    body = wait_for(client, gid, ("done", "failed"))
    assert body["status"] == "done", body
    assert body["engine"] == "stub" and body["sims"] == 32

    moves = body["moves"]
    assert len(moves) == len(SCRIPT)
    for i, entry in enumerate(moves):
        assert entry["ply"] == i + 1
        assert entry["move"] == SCRIPT[i]
        assert entry["best"]
        assert 0.0 <= entry["loss"] <= 1.0
        assert entry["class"] in ("brilliant", "best", "excellent", "good",
                                  "inaccuracy", "mistake", "blunder")
        assert -1.0 <= entry["eval"] <= 1.0

    # The stand-in always speaks well of whoever is to move, so a review that
    # gets the point of view right reports it alternating around zero.
    assert [e["eval"] for e in moves[:4]] == [0.06, -0.06, 0.06, -0.06]

    # ha1 is the lowest-numbered legal action of its position, so the engine
    # agreed with it and with nothing else in the game.
    agreed = [e for e in moves if e["class"] in ("best", "brilliant")]
    assert [e["move"] for e in agreed] == ["ha1"]
    assert agreed[0]["best"] == "ha1" and agreed[0]["loss"] == 0.0

    # The last move ends the game, so there is no position after it to search:
    # the review has to score it from the result, which costs nothing.
    assert moves[-1]["move"] == "f9" and moves[-1]["loss"] == 0.0

    first, second = body["accuracy"]["first"], body["accuracy"]["second"]
    assert 0.0 < first <= 100.0 and 0.0 < second <= 100.0
    # Player 2 found the one move the engine liked, so scores higher on the
    # same fixed cost per move elsewhere.
    assert second > first


class SlowStubEngine(StubEngine):
    """The same opinions, delivered slowly enough to watch the job move."""

    def search(self, position):
        time.sleep(0.05)
        return super().search(position)


def test_progress_is_reported_while_the_job_runs(client, monkeypatch):
    monkeypatch.setattr(review, "get_engine", lambda: SlowStubEngine())
    gid = played_out(client, "progress1", "progress2")
    client.post(f"/api/game/{gid}/review")

    seen, body = [], None
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        body = client.get(f"/api/game/{gid}/review").json()
        if body["status"] == "running":
            seen.append(body["progress"])
        elif body["status"] in ("done", "failed"):
            break
        time.sleep(0.01)

    assert body["status"] == "done", body
    # A caller polling a two-minute job has to be able to tell how far in it
    # is, so the fraction has to move while the work happens.
    assert seen, "the job never reported itself running"
    assert all(0.0 <= p <= 1.0 for p in seen)
    assert seen == sorted(seen)
    assert any(0.0 < p < 1.0 for p in seen)


def test_a_resigned_game_is_reviewed_to_its_last_move(client, monkeypatch):
    """No mate means no terminal position: the last move is judged like any other."""
    monkeypatch.setattr(review, "get_engine", lambda: StubEngine())
    gid, headers = start_game(client, "resigned1", "resigned2")
    for i, token in enumerate(["e2", "e8", "e3"]):
        r = client.post(f"/api/game/{gid}/move/{token}", headers=headers[i % 2])
        assert r.status_code == 200, r.text
    assert client.post(f"/api/game/{gid}/resign",
                       headers=headers[1]).status_code == 200
    client.post(f"/api/game/{gid}/review")
    body = wait_for(client, gid, ("done", "failed"))

    assert body["status"] == "done", body
    assert [e["move"] for e in body["moves"]] == ["e2", "e8", "e3"]
    # The position the last move led to was searched in its own right, so the
    # move is scored on what it achieved rather than excused for being last.
    assert body["moves"][-1]["loss"] == pytest.approx(0.06, abs=1e-6)


def _no_engine():
    raise AssertionError("an empty game must not load an engine")


def test_an_empty_game_reviews_to_an_empty_answer(client, monkeypatch):
    """A game resigned before a move is played needs no engine at all."""
    monkeypatch.setattr(review, "get_engine", _no_engine)
    gid, headers = start_game(client, "empty1", "empty2")
    assert client.post(f"/api/game/{gid}/resign", headers=headers[1]).status_code == 200
    client.post(f"/api/game/{gid}/review")
    body = wait_for(client, gid, ("done", "failed"))
    assert body["status"] == "done"
    assert body["moves"] == []
    assert body["accuracy"] == {"first": None, "second": None}


# -- the real thing ---------------------------------------------------------

def _engine_present() -> bool:
    return (importlib.util.find_spec("torch") is not None
            and Path(review.checkpoint_path()).exists())


@pytest.mark.skipif(not _engine_present(),
                    reason="no engine checkpoint on this machine")
def test_a_full_review_with_the_real_engine(client, monkeypatch):
    # A short search: this test is about the engine being wired up correctly,
    # not about the quality of its opinions.
    monkeypatch.setenv("PALISADE_REVIEW_SIMS", "48")
    gid = played_out(client, "realengine1", "realengine2")
    assert client.post(f"/api/game/{gid}/review").status_code == 200
    body = wait_for(client, gid, ("done", "failed"), timeout=300.0)
    assert body["status"] == "done", body
    assert body["engine"] == review.engine_name() and body["sims"] == 48

    moves = body["moves"]
    assert len(moves) == len(SCRIPT)
    for i, entry in enumerate(moves):
        assert entry["ply"] == i + 1 and entry["move"] == SCRIPT[i]
        assert isinstance(entry["best"], str) and entry["best"]
        assert 0.0 <= entry["loss"] <= 1.0
        assert -1.0 <= entry["eval"] <= 1.0
        assert entry["class"] in ("brilliant", "best", "excellent", "good",
                                  "inaccuracy", "mistake", "blunder")
    # Player 1 walked in and won; whatever the engine thinks of the details,
    # the position it was handed at the end has to be good for Player 1.
    assert moves[-1]["eval"] > 0.0
    assert 0.0 < body["accuracy"]["first"] <= 100.0
    assert 0.0 < body["accuracy"]["second"] <= 100.0
