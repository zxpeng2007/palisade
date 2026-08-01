"""Game review: the engine's opinion of every move of a finished game.

The shape of the answer is API.md's "Game review" section; this module owns the
numbers in it.

Analysis is expensive and the box is small. The production server is two vCPUs
with no GPU, where the search runs at about 290 simulations a second, so a
55-move game at 600 simulations a position is roughly two minutes of compute --
and batching positions does not help, because on a saturated CPU a batch is the
same total work rather than a free ride the way it is on a GPU. So a review is
never a request: it is a stored job, drained by one background worker, and the
result is kept forever because a finished game cannot change its mind.

Cost also shapes the analysis itself. Position k of a game is both "after move
k" and "before move k+1", so one search per position serves twice -- it is the
evaluation the next mover faced, and it is what the previous move actually
achieved. That is why a review costs one search per ply rather than two.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from quoridor import fastrules as fr

from palisade import db, rules
from palisade.notation import legal_token_map, square_token, wall_token

# Where the production server keeps the network it publishes reviews with.
# Both env vars are honoured so a box that already runs the house bot needs no
# second copy, while a reviewer strong enough to be worth quoting can still be
# pointed at separately.
DEFAULT_CHECKPOINT = "/home/palisade/run/gen-010.pt"
DEFAULT_SIMS = 600


def checkpoint_path() -> str:
    return (os.environ.get("PALISADE_REVIEW_CHECKPOINT")
            or os.environ.get("PALISADE_BOT_CHECKPOINT")
            or DEFAULT_CHECKPOINT)


def configured_sims() -> int:
    try:
        return max(1, int(os.environ.get("PALISADE_REVIEW_SIMS", DEFAULT_SIMS)))
    except ValueError:
        return DEFAULT_SIMS


def engine_name() -> str:
    """The name a review is published under, e.g. ``gen-010``.

    Readable without loading anything, so a queued review can already say whose
    opinion it is going to be.
    """
    return Path(checkpoint_path()).stem or "unknown"


class ReviewError(RuntimeError):
    """A review that cannot be produced, with a message fit for the client."""


class EngineUnavailable(ReviewError):
    """No engine on this machine: no torch, or no checkpoint where it should be."""


class _Stopped(Exception):
    """The process is going down mid-review; the row goes back to pending."""


# Set on shutdown. A review is minutes of work in a thread that cannot be
# cancelled from outside, so the analysis checks this between positions and
# stands down rather than holding the process open.
_stop = threading.Event()


# ---------------------------------------------------------------- judgement

# Win-probability loss bands, from API.md. Upper bounds: a move sitting exactly
# on a boundary takes the kinder label.
BANDS = ((0.02, "excellent"), (0.05, "good"), (0.10, "inaccuracy"),
         (0.20, "mistake"))
BLUNDER = "blunder"
# A move is brilliant when the engine agreed with it, its own policy had all
# but dismissed it beforehand, and it wins by a distance -- a move that had to
# be found rather than followed. Both thresholds are from the contract, and the
# margin is in win probability like every other number here.
BRILLIANT_PRIOR = 0.02
BRILLIANT_MARGIN = 0.15


def win_probability(value: float) -> float:
    """An engine value in -1..1 as a win probability in 0..1.

    Losses are quoted in win probability rather than raw value because that is
    the scale a player experiences: the difference between +0.9 and +1.0 hardly
    matters, and the same size of drop around 0.0 decides the game.
    """
    return min(1.0, max(0.0, (float(value) + 1.0) / 2.0))


def classify(loss: float, is_best: bool, prior: float = 1.0,
             margin: float = 0.0) -> str:
    """Label one move. ``prior`` and ``margin`` describe the engine's own best.

    ``prior`` is the policy's probability for the move before any search, and
    ``margin`` is how far ahead of the engine's second choice it finished, both
    of which only mean anything when the player and the engine agreed.
    """
    if is_best:
        if prior < BRILLIANT_PRIOR and margin > BRILLIANT_MARGIN:
            return "brilliant"
        return "best"
    for limit, name in BANDS:
        if loss <= limit:
            return name
    return BLUNDER


# accuracy = 100 * exp(-k * mean_loss), k = -ln(0.85) / 0.05 = 3.25 to two
# decimals: a player whose average move costs 0.05 win probability -- the top
# of the "good" band, an entirely respectable game -- scores 85%. The
# exponential is what keeps the scale honest at both ends: it cannot exceed 100
# or fall below 0, one blunder in a clean game dents the score rather than
# destroying it, and a game of blunders keeps falling instead of bottoming out.
ACCURACY_K = 3.25


def accuracy(mean_loss: float) -> float:
    """Percentage in (0, 100] for a player's mean win-probability loss."""
    return 100.0 * math.exp(-ACCURACY_K * max(0.0, float(mean_loss)))


def eval_from_first(value: float, ply: int) -> float:
    """An engine value at ``ply`` (1-based) as seen by Player 1.

    The engine speaks from the mover's point of view, which alternates, so a
    graph drawn straight from it would zig-zag and read as nonsense for both
    players. Player 1 moves on odd plies, so even plies are the ones to negate;
    afterwards positive always means Player 1 is better.
    """
    return float(value) if ply % 2 == 1 else -float(value)


# ------------------------------------------------------------------- engine

@dataclass
class _Search:
    """What one search of one position had to say."""

    visits: np.ndarray      # root visit counts, the engine's preference order
    q: np.ndarray           # mean value per action, NaN where never visited
    priors: np.ndarray      # root policy, before any search
    value: float            # value of the position, from the mover's side


class _Engine:
    """The network and one search tree, loaded once and kept."""

    def __init__(self, path: str, sims: int):
        try:
            import torch
            from quoridor.mcts import BatchedMCTS
            from quoridor.net import NetEvaluator, load_checkpoint
        except ImportError as exc:
            raise EngineUnavailable(
                f"this server has no analysis engine installed ({exc})") from exc
        if not os.path.exists(path):
            raise EngineUnavailable(
                f"no engine checkpoint at {path}; set PALISADE_REVIEW_CHECKPOINT "
                f"to one this server has")
        # Leave a core for everything else. The same box serves the site and
        # usually runs the house bot, which is in the middle of a real game
        # with a clock running while reviews grind away behind it.
        torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
        device = "cuda" if torch.cuda.is_available() else "cpu"
        try:
            net, self.meta = load_checkpoint(path, device)
        except Exception as exc:
            raise EngineUnavailable(
                f"the engine checkpoint at {path} could not be loaded: {exc}") from exc
        self.path = path
        self.sims = sims
        self.name = Path(path).stem or "unknown"
        rules.warmup()
        # leaf_batch stays 1. Gathering several leaves per network call is a GPU
        # trick: it costs search quality, because every extra leaf in a batch is
        # chosen on statistics that do not yet include the others. On this CPU
        # it buys nothing back -- measured at 276 sims/s batched against ~300
        # sequential -- so the quality would be given away for free.
        self.mcts = BatchedMCTS(NetEvaluator(net, device=device), n_games=1,
                                max_nodes=sims + 256, leaf_batch=1)
        # The first search compiles the njit kernels and allocates the buffers.
        # Do it now, not against a progress bar somebody is watching.
        self.search(rules.new_state(), sims=8)

    def search(self, state: np.ndarray, sims: int | None = None) -> _Search:
        n = self.sims if sims is None else sims
        visits = self.mcts.search(state.reshape(1, -1).copy(), n)[0]
        # W/N at the root is what each move is worth to the mover -- the very
        # numbers the search chose on. Reading them out is free, where a second
        # search per move would double a two-minute job. They belong to this
        # search alone: the arrays are reused by the next one, so copy.
        w = self.mcts.node_W[0, 0]
        seen = visits > 0
        q = np.full(fr.NUM_ACTIONS, np.nan)
        q[seen] = w[seen] / visits[seen]
        total = float(visits.sum())
        value = float(w.sum() / total) if total > 0 else 0.0
        return _Search(visits.copy(), q, self.mcts.node_P[0, 0].copy(), value)


_engine: _Engine | None = None
_engine_lock = threading.Lock()


def get_engine() -> _Engine:
    """The loaded engine, loading it on first use. Raises EngineUnavailable.

    The configuration is re-read every time so an operator who fixes a wrong
    checkpoint path does not have to restart the server to unstick reviews; a
    reload costs a few seconds and happens once.
    """
    global _engine
    path, sims = checkpoint_path(), configured_sims()
    with _engine_lock:
        if _engine is None or (_engine.path, _engine.sims) != (path, sims):
            # On failure the previous engine, if any, stays loaded and usable.
            _engine = _Engine(path, sims)
        return _engine


# ----------------------------------------------------------------- analysis

def _replay(moves: list[str]) -> tuple[list[np.ndarray], list[int]]:
    """Every position of a game, plus the engine action each move was.

    The action numbers have to come from the same walk that builds the
    positions, because that is the vocabulary the search answers in.
    """
    st = rules.new_state()
    scratch = rules.make_scratch()
    states, actions = [st], []
    for token in moves:
        action = legal_token_map(st, scratch).get(token)
        if action is None:
            raise ReviewError(
                f"the game record contains a move that is not legal: {token}")
        st = st.copy()
        fr.apply_action(st, action, scratch)
        states.append(st)
        actions.append(action)
    return states, actions


def _token_for(st: np.ndarray, action: int, scratch: np.ndarray) -> str:
    """Engine action -> API token in the given position."""
    if action < fr.MOVE_BASE:
        return wall_token(action)
    # Pawn tokens name the destination square, and a jump makes the destination
    # depend on the position, so play it and see where the pawn landed.
    mover = int(st[fr.IDX_TURN])
    after = st.copy()
    fr.apply_action(after, action, scratch)
    return square_token(int(after[fr.IDX_P0 if mover == 0 else fr.IDX_P1]))


def _accuracy_of(losses: list[float]) -> float | None:
    """One player's accuracy, or None when they never moved.

    A game can end before a player has played anything (a resignation on ply
    1), and inventing a percentage for someone who made no decisions would be
    worse than admitting there is nothing to score.
    """
    if not losses:
        return None
    return round(accuracy(sum(losses) / len(losses)), 1)


def analyse(moves: list[str], on_progress=None) -> dict:
    """Search every position of a game and score every move.

    ``on_progress`` is called with the fraction of positions searched, so the
    endpoint has something to report while the job runs.
    """
    if not moves:
        # Nothing was played (a game resigned on the first ply). Report an
        # empty review rather than loading an engine to say so.
        return {"engine": engine_name(), "sims": configured_sims(),
                "accuracy": {"first": None, "second": None}, "moves": []}

    engine = get_engine()
    states, actions = _replay(moves)
    scratch = rules.make_scratch()

    searched: list[_Search | None] = []
    for k, position in enumerate(states):
        if _stop.is_set():
            raise _Stopped()
        # A finished position needs no search: the side to move has lost, and
        # asking the engine about it would return nothing but zeros anyway.
        searched.append(None if fr.winner(position) >= 0 else engine.search(position))
        if on_progress is not None:
            on_progress((k + 1) / len(states))

    entries = []
    for i, token in enumerate(moves):
        root = searched[i]
        if root is None or root.visits.sum() <= 0:
            raise ReviewError(f"the engine had no opinion about ply {i + 1}")
        order = np.argsort(-root.visits)
        best = int(order[0])
        played = actions[i]
        is_best = played == best
        # What the move actually achieved: the value of the position it led to,
        # searched in its own right, negated into the mover's terms.
        achieved = -_value_of(searched[i + 1])
        # An agreed move gave nothing up by definition; measuring it against a
        # deeper look at its own consequences would invent a loss the player
        # could not have avoided by playing better.
        loss = 0.0 if is_best else max(
            0.0, win_probability(root.q[best]) - win_probability(achieved))
        runner_up = int(order[1]) if root.visits[order[1]] > 0 else None
        margin = 0.0 if runner_up is None else (
            win_probability(root.q[best]) - win_probability(root.q[runner_up]))
        entries.append({
            "ply": i + 1,
            "move": token,
            "best": _token_for(states[i], best, scratch),
            # The evaluation of the position this move was played in, so the
            # graph starts at the opening position and every point is a
            # moment somebody had to make a decision.
            "eval": round(eval_from_first(root.value, i + 1), 4),
            "loss": round(loss, 4),
            "class": classify(loss, is_best, prior=float(root.priors[best]),
                              margin=margin),
        })

    return {
        "engine": engine.name,
        "sims": engine.sims,
        "accuracy": {
            "first": _accuracy_of([e["loss"] for e in entries if e["ply"] % 2]),
            "second": _accuracy_of([e["loss"] for e in entries if not e["ply"] % 2]),
        },
        "moves": entries,
    }


def _value_of(search: _Search | None) -> float:
    """A position's value to the player to move; a decided one is a loss."""
    return -1.0 if search is None else search.value


# --------------------------------------------------------------------- jobs

# Created by start(), so each process (and each test app) drains its own queue
# and never inherits ids from a previous event loop.
_queue: asyncio.Queue | None = None


def start() -> asyncio.Task:
    """Create the queue and the one worker task. Called from the app lifespan."""
    global _queue
    _stop.clear()
    _queue = asyncio.Queue()
    # A review interrupted by a restart is still wanted: the row is the record
    # of somebody asking, so pick it up rather than making them ask again.
    # 'running' means the process died mid-analysis, which is just 'pending'
    # with wasted work behind it.
    for row in db.query("SELECT game_id FROM reviews "
                        "WHERE status IN ('pending', 'running')"):
        db.run("""UPDATE reviews SET status = 'pending', progress = 0,
                  updated = datetime('now') WHERE game_id = ?""",
               (row["game_id"],))
        _queue.put_nowait(row["game_id"])
    return asyncio.get_running_loop().create_task(_worker())


def stop() -> None:
    """Ask a running analysis to put itself down at the next position."""
    _stop.set()


async def _worker() -> None:
    """Drain the queue, one review at a time, forever.

    One at a time on purpose: the search already uses every core the box can
    spare, so running two reviews at once would not finish two sooner -- it
    would make both slow and take time away from the games being played.
    """
    assert _queue is not None
    queue = _queue
    while True:
        game_id = await queue.get()
        try:
            # run() owns its failures; this is the net under the net, because a
            # worker that dies takes every future review with it.
            await asyncio.to_thread(run, game_id)
        except Exception as exc:
            print(f"palisade: review worker error on {game_id}: {exc!r}", flush=True)
        finally:
            queue.task_done()


def _enqueue(game_id: str) -> None:
    if _queue is not None:
        _queue.put_nowait(game_id)
    # With no worker running the row simply stays pending, and start() will
    # find it -- which is exactly what a restart does.


def request(game_id: str) -> dict:
    """Start a review of a finished game, or report the one already there."""
    name, sims = engine_name(), configured_sims()
    # The row is the job record, so creating it is what makes a request
    # idempotent: a second POST while one is queued or running finds the row,
    # starts nothing, and gets the same state back.
    if db.run("""INSERT OR IGNORE INTO reviews (game_id, status, engine, sims)
                 VALUES (?, 'pending', ?, ?)""", (game_id, name, sims)):
        _enqueue(game_id)
    elif db.one("SELECT status FROM reviews WHERE game_id = ?",
                (game_id,))["status"] == "failed":
        # A failure is a fact about the moment it happened -- a checkpoint that
        # was not there yet, a restart -- and not about the game, so asking
        # again tries again instead of replaying the old excuse. A finished
        # review, by contrast, is never recomputed.
        db.run("""UPDATE reviews SET status = 'pending', progress = 0,
                  error = NULL, engine = ?, sims = ?, updated = datetime('now')
                  WHERE game_id = ?""", (name, sims, game_id))
        _enqueue(game_id)
    return state(game_id)


def state(game_id: str) -> dict | None:
    """The review of a game as the API reports it, or None if none was asked for."""
    row = db.one("SELECT * FROM reviews WHERE game_id = ?", (game_id,))
    if row is None:
        return None
    out = {"status": row["status"], "engine": row["engine"], "sims": row["sims"]}
    if row["status"] == "done" and row["result"]:
        out.update(json.loads(row["result"]))
    elif row["status"] == "failed":
        out["error"] = row["error"] or "the review failed"
    else:
        out["progress"] = round(row["progress"] or 0.0, 3)
    return out


def _touch(game_id: str, **fields) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    db.run(f"UPDATE reviews SET {sets}, updated = datetime('now') WHERE game_id = ?",
           (*fields.values(), game_id))


def _fail(game_id: str, message: str) -> None:
    print(f"palisade: review of {game_id} failed: {message}", flush=True)
    _touch(game_id, status="failed", error=message)


def run(game_id: str) -> None:
    """Analyse one game and store the result. Runs in a thread; never raises."""
    game = db.one("SELECT status, moves FROM games WHERE id = ?", (game_id,))
    if game is None:
        _fail(game_id, "the game no longer exists")
        return
    if game["status"] != "finished":
        # Only reachable if the game was still running when the row was made,
        # which the endpoint refuses -- so this is a restart picking up a row
        # whose game was aborted in the meantime.
        _fail(game_id, "review is only available for finished games")
        return

    moves = game["moves"].split(",") if game["moves"] else []
    _touch(game_id, status="running", progress=0.0, error=None)
    started = time.monotonic()
    try:
        result = analyse(moves, on_progress=lambda f: _touch(game_id, progress=f))
    except _Stopped:
        # Shutdown, not failure: leave the row where start() will find it.
        _touch(game_id, status="pending", progress=0.0)
        return
    except ReviewError as exc:
        _fail(game_id, str(exc))
        return
    except Exception as exc:
        # Anything else is a bug or a broken engine. The server must survive
        # it, and whoever asked deserves to be told rather than left spinning.
        _fail(game_id, f"the analysis failed: {exc}")
        return

    _touch(game_id, status="done", progress=1.0, error=None,
           engine=result["engine"], sims=result["sims"],
           result=json.dumps({"accuracy": result["accuracy"],
                              "moves": result["moves"]}))
    print(f"palisade: reviewed {game_id}, {len(moves)} plies in "
          f"{time.monotonic() - started:.1f}s", flush=True)
