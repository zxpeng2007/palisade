"""Reference bot: an AlphaZero engine on a Palisade server, via the public API.

This is the palisade analogue of lichess-bot and doubles as the house bot. It
talks to the server exclusively through the HTTP API described in API.md:
account events arrive on /api/stream/event, each game is followed on
/api/game/stream/{id}, and moves go back as plain POSTs. Positions are rebuilt
by replaying the move list through the rules engine, so the bot never trusts
its own bookkeeping over the server's.

    export PALISADE_TOKEN=pal_...
    python bot.py --checkpoint /path/to/best.pt --seek 300+3

One game at a time: challenges received while playing are declined, and any
gameStart that slips through anyway (a seek matching in the same instant) is
queued and played next.
"""

from __future__ import annotations

import argparse
import itertools
import json
import os
import re
import sys
import threading
import time
from collections import deque

import httpx
import numpy as np
import torch

from quoridor import fastrules as fr
from quoridor.mcts import BatchedMCTS
from quoridor.net import NetEvaluator, load_checkpoint

from palisade.notation import legal_token_map, square_token, wall_token

REST_TIMEOUT = 15.0


# ------------------------------------------------------------------ engine

class Engine:
    # Leaves gathered per network call. Raising this raises the raw simulation
    # rate, but a batch of N leaves is selected before any is evaluated, so the
    # extra simulations run on stale statistics. Measured head to head at equal
    # time, leaf_batch 1024 loses heavily to 32 despite searching ~1.5x more
    # nodes; 32 is the setting that actually wins games.
    LEAF = 32
    # Only a floor, for the case where the calibration below is somehow
    # unusable. The real starting rate is measured on this machine at startup.
    MIN_SIMS_PER_SEC = 50.0

    def __init__(self, checkpoint: str, device: str, max_sims: int,
                 think_seconds: float):
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = device
        torch.backends.cudnn.benchmark = True
        fr.warmup()
        net, self.meta = load_checkpoint(checkpoint, device)
        ev = NetEvaluator(net, device=device, graph_batches=(self.LEAF,))
        self.mcts = BatchedMCTS(ev, n_games=1,
                                max_nodes=max_sims + self.LEAF + 256,
                                leaf_batch=self.LEAF)
        self.max_sims = max_sims
        self.think_seconds = think_seconds

        # Warm up and calibrate in one step, while no clock is running. The
        # first search also compiles the njit kernels and captures the CUDA
        # graph, so it is timed separately from the measurement that follows.
        #
        # The rate is measured rather than assumed because it spans two orders
        # of magnitude across the hardware this bot legitimately runs on: a
        # discrete GPU manages ~22k simulations a second, a shared vCPU a few
        # hundred. A constant tuned on one is badly wrong on the other, and
        # wrong in the dangerous direction -- overshooting the clock. Seeding
        # from a real measurement makes the bot correct anywhere without a
        # flag anyone has to remember to set.
        start = fr.initial_state().reshape(1, -1)
        self.mcts.search(start, 512)                      # compile / capture
        probe = 2048
        t0 = time.perf_counter()
        self.mcts.search(start, probe)
        dt = time.perf_counter() - t0
        self.rate = max(self.MIN_SIMS_PER_SEC, probe / dt if dt > 0 else 0.0)

    # A game here runs about sixty plies, so thirty moves a side. Budgeting
    # against a few more than that leaves the clock with something in hand at
    # the point where games usually end, without hoarding time that is only
    # useful if the game is unusually long.
    EXPECTED_MOVES = 34
    # Never divide by fewer than this: as the estimate runs out the budget
    # becomes a fixed share of what is left, which decays but never reaches
    # zero, so the clock cannot be spent to nothing in one move.
    MIN_MOVES_LEFT = 8
    # Most of the increment is spendable — it arrives after every move — but
    # not all of it, or the clock never recovers from a slow patch.
    INCREMENT_SHARE = 0.8
    # Hard ceiling on any single move, whatever the arithmetic says.
    MAX_CLOCK_SHARE = 0.2

    def sims_for(self, clock: float | None, increment: float = 0.0,
                 ply: int = 0) -> int:
        """Simulations to fit a budget drawn from the actual time control.

        The old rule was a flat cap with a clock/20 floor, which ignored the
        increment and so treated 15+10 exactly like 5+3: it spent ten seconds
        a move in both, far too slow for the short one and leaving most of the
        long one unused. Time controls here span 1+0 to 15+10, a factor of
        twenty in what a move is worth.

        What a move is actually worth is the clock spread over the moves still
        to play, plus the increment, which is income rather than capital. The
        moves-left estimate shrinks as the game goes on, so the budget grows
        into the endgame the way a player's does.
        """
        if clock is None:
            # No clock on the wire — the archived-game case. Fall back to the
            # ceiling rather than guessing at a budget from nothing.
            target = self.think_seconds
        else:
            moves_left = max(self.MIN_MOVES_LEFT,
                             self.EXPECTED_MOVES - ply // 2)
            target = clock / moves_left + increment * self.INCREMENT_SHARE
            target = min(target, clock * self.MAX_CLOCK_SHARE)
        target = min(target, self.think_seconds)
        return int(max(256, min(self.max_sims, target * self.rate)))

    def choose(self, st: np.ndarray, sims: int) -> tuple[int, float, np.ndarray]:
        """Returns ``(action, value, visits)``; action is -1 if there is none.

        A search from an already-decided position returns zero visits
        everywhere, and argmax of an all-zero array is 0 -- which happens to
        be a wall placement. Report "no move" instead of inventing one.
        """
        t0 = time.perf_counter()
        visits = self.mcts.search(st.reshape(1, -1).copy(), sims)[0]
        dt = time.perf_counter() - t0
        if dt > 0.05:
            # Track observed throughput so the next move hits the target time.
            self.rate = 0.7 * self.rate + 0.3 * (sims / dt)
        if visits.sum() <= 0:
            return -1, 0.0, visits
        return int(visits.argmax()), float(self.mcts.root_value()[0]), visits


# ---------------------------------------------------------------- position

def replay(tokens: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """State + scratch after a token sequence from the initial position."""
    st = fr.initial_state()
    scratch = fr.make_scratch()
    for t in tokens:
        action = legal_token_map(st, scratch).get(t)
        if action is None:
            raise ValueError(f"server move list contains an illegal token: {t}")
        fr.apply_action(st, action, scratch)
    return st, scratch


def move_token(st: np.ndarray, action: int, scratch: np.ndarray) -> str:
    """Engine action -> API token in the given position."""
    if action < fr.MOVE_BASE:
        return wall_token(action)
    # Pawn tokens name the destination, and jumps make the destination depend
    # on the position -- so apply the action and read where the pawn landed.
    mover = int(st[fr.IDX_TURN])
    after = st.copy()
    fr.apply_action(after, action, scratch)
    return square_token(int(after[fr.IDX_P0 if mover == 0 else fr.IDX_P1]))


# --------------------------------------------------------------------- bot

SEEK_RE = re.compile(r"^(\d+)[x+](\d+)(?::(rated|casual))?$")


def parse_seek(spec: str) -> dict:
    m = SEEK_RE.match(spec.strip())
    if m is None:
        raise argparse.ArgumentTypeError(
            f"seek must look like 300+3 or 300x3 (optionally :rated/:casual): {spec!r}")
    return {"rated": m.group(3) != "casual",
            "clock": {"initial": int(m.group(1)), "increment": int(m.group(2))}}


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Bot:
    def __init__(self, args: argparse.Namespace, engine: Engine):
        self.engine = engine
        self.accept = args.accept
        self.seek_specs = itertools.cycle(args.seek) if args.seek else None
        self.seek_open = False
        self.http = httpx.Client(
            base_url=args.server.rstrip("/"),
            headers={"Authorization": f"Bearer {args.token}"},
            timeout=REST_TIMEOUT)
        self.username = ""
        self.game_thread: threading.Thread | None = None
        self.current_game: str | None = None
        self.pending: deque[dict] = deque()

    # -- account ------------------------------------------------------------

    def verify_account(self) -> None:
        r = self.http.get("/api/account")
        if r.status_code == 401:
            sys.exit("token rejected by the server (401): check --token / PALISADE_TOKEN")
        r.raise_for_status()
        acct = r.json()
        self.username = acct["username"]
        log(f"account: {acct['username']} (rating {acct['rating']}, "
            f"{acct['games']} rated games)")
        if not acct["bot"]:
            log("WARNING: this account is not flagged bot -- opponents cannot "
                "see they are playing an engine. POST /api/bot/upgrade while "
                "the account has no rated games.")

    # -- event stream -------------------------------------------------------

    def run(self) -> None:
        backoff = 1.0
        while True:
            try:
                with self.http.stream("GET", "/api/stream/event",
                                      timeout=None) as resp:
                    if resp.status_code == 401:
                        sys.exit("token rejected by the server (401)")
                    resp.raise_for_status()
                    log("event stream connected")
                    backoff = 1.0
                    # A reconnect loses track of any parked seek; posting a
                    # fresh one simply replaces it server-side.
                    self.seek_open = False
                    self.tick()
                    for line in resp.iter_lines():
                        # Keepalives arrive every few seconds, so this is also
                        # the idle heartbeat: notice finished games, start
                        # queued ones, keep a seek open.
                        self.tick()
                        if not line.strip():
                            continue
                        self.handle_event(json.loads(line))
            except httpx.HTTPError as exc:
                log(f"event stream dropped: {exc!r}")
            log(f"reconnecting in {backoff:.0f}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 30.0)

    def tick(self) -> None:
        if self.game_thread is not None and not self.game_thread.is_alive():
            self.game_thread = None
            self.current_game = None
        if self.game_thread is None and self.pending:
            self.start_game(self.pending.popleft())
        if self.game_thread is None and self.seek_specs and not self.seek_open:
            self.post_seek()

    def handle_event(self, ev: dict) -> None:
        kind = ev.get("type")
        if kind == "challenge":
            self.handle_challenge(ev["challenge"])
        elif kind == "gameStart":
            game = ev["game"]
            if game["id"] == self.current_game or any(
                    g["id"] == game["id"] for g in self.pending):
                return
            if self.game_thread is not None:
                log(f"game {game['id']} queued (already playing)")
                self.pending.append(game)
            else:
                self.start_game(game)
        elif kind == "gameFinish":
            g = ev["game"]
            log(f"gameFinish {g['id']}: winner {g.get('winner')} "
                f"({g.get('reason')})")

    def handle_challenge(self, ch: dict) -> None:
        busy = self.game_thread is not None or self.pending
        wanted = {"all": True, "rated": ch["rated"], "casual": not ch["rated"],
                  "none": False}[self.accept]
        verb = "accept" if wanted and not busy else "decline"
        why = "" if wanted and not busy else (" (busy)" if busy else " (policy)")
        log(f"challenge from {ch['challenger']} "
            f"({'rated' if ch['rated'] else 'casual'} "
            f"{ch['clock']['initial']}+{ch['clock']['increment']}): {verb}{why}")
        try:
            r = self.http.post(f"/api/challenge/{ch['id']}/{verb}")
            if r.status_code >= 400:
                log(f"  challenge {verb} failed: {r.text}")
        except httpx.HTTPError as exc:
            log(f"  challenge {verb} failed: {exc!r}")

    # -- seeks --------------------------------------------------------------

    def post_seek(self) -> None:
        spec = next(self.seek_specs)
        try:
            r = self.http.post("/api/seek", json=spec)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            log(f"seek failed: {exc!r}")
            return
        clock = spec["clock"]
        if r.json().get("matched"):
            log(f"seek {clock['initial']}+{clock['increment']} matched instantly")
            # The gameStart event carries the game; nothing is parked.
        else:
            self.seek_open = True
            log(f"seek open: {'rated' if spec['rated'] else 'casual'} "
                f"{clock['initial']}+{clock['increment']}")

    def cancel_seek(self) -> None:
        if not self.seek_open:
            return
        self.seek_open = False
        try:
            self.http.delete("/api/seek")
        except httpx.HTTPError:
            pass

    # -- playing ------------------------------------------------------------

    def start_game(self, game: dict) -> None:
        # A parked seek could otherwise match mid-game and stack a second game.
        self.cancel_seek()
        opp = game.get("opponent", {})
        log(f"game {game['id']} starting: {game['color']} vs "
            f"{opp.get('username', '?')} ({opp.get('rating', '?')})")
        self.current_game = game["id"]
        self.game_thread = threading.Thread(
            target=self.play_game, args=(game["id"], game["color"]), daemon=True)
        self.game_thread.start()

    def play_game(self, game_id: str, color: str) -> None:
        seat = 0 if color == "first" else 1
        backoff = 1.0
        while True:
            try:
                if self.stream_game(game_id, seat):
                    return
            except httpx.HTTPError as exc:
                log(f"game {game_id}: stream dropped: {exc!r}")
            # The stream ended without a result: reconnect. The first line is
            # always the full game, which resynchronises the position.
            time.sleep(backoff)
            backoff = min(backoff * 2, 15.0)

    def stream_game(self, game_id: str, seat: int) -> bool:
        """Follow one game to its end. True when a result (or 404) was seen."""
        with self.http.stream("GET", f"/api/game/stream/{game_id}",
                              timeout=None) as resp:
            if resp.status_code == 404:
                log(f"game {game_id}: gone (404)")
                return True
            resp.raise_for_status()
            increment = 0.0
            for line in resp.iter_lines():
                if not line.strip():
                    continue
                msg = json.loads(line)
                if msg.get("type") == "gameFull":
                    # Only this line carries the time control; later states
                    # report the clocks but not the increment.
                    increment = float(msg.get("clock", {}).get("increment", 0))
                    state = msg["state"]
                elif msg.get("type") == "gameState":
                    state = msg
                else:
                    continue
                if state["status"] != "active":
                    won = state.get("winner") == ("first", "second")[seat]
                    log(f"game {game_id}: {state['status']}, "
                        f"winner {state.get('winner')} ({state.get('reason')}) "
                        f"-- we {'won' if won else 'did not win'}")
                    return True
                self.consider_move(game_id, seat, state, increment)
        return False

    def consider_move(self, game_id: str, seat: int, state: dict,
                      increment: float = 0.0) -> None:
        moves = [t for t in state["moves"].split(",") if t]
        if (len(moves) % 2 == 0) != (seat == 0):
            return                      # opponent to move
        try:
            st, scratch = replay(moves)
        except ValueError as exc:
            # Either the server and engine disagree on the rules (a contract
            # violation worth a loud message) or this build is broken. Playing
            # on from a wrong position would be worse than losing on time.
            log(f"game {game_id}: cannot rebuild position: {exc}")
            return
        my_time = state.get("p1time" if seat == 0 else "p2time")
        sims = self.engine.sims_for(my_time, increment, len(moves))
        t0 = time.perf_counter()
        action, value, visits = self.engine.choose(st, sims)
        think = time.perf_counter() - t0
        if action < 0:
            return                      # position already decided
        token = move_token(st, action, scratch)
        share = float(visits[action] / max(visits.sum(), 1))
        log(f"game {game_id} ply {len(moves) + 1}: {token:<4} "
            f"[{sims} sims, {think:.1f}s, eval {value:+.2f}, {100 * share:.0f}%"
            + (f", clock {my_time:.0f}s" if my_time is not None else "") + "]")
        self.post_move(game_id, token)

    def post_move(self, game_id: str, token: str) -> None:
        for _ in range(3):
            try:
                r = self.http.post(f"/api/game/{game_id}/move/{token}")
            except httpx.HTTPError as exc:
                log(f"game {game_id}: move POST failed: {exc!r}")
                time.sleep(1.0)
                continue
            if r.status_code == 429:
                time.sleep(1.0)
                continue
            if r.status_code >= 400:
                # Usually a race: the game ended, or a reconnect replayed a
                # state we had already answered. The stream sorts it out.
                log(f"game {game_id}: move {token} rejected: {r.text}")
            return
        log(f"game {game_id}: giving up on move {token}")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--server", default="http://localhost:8000",
                    help="palisade server base URL (default %(default)s)")
    ap.add_argument("--token", default=os.environ.get("PALISADE_TOKEN"),
                    help="API token with the play scope "
                         "(default: env PALISADE_TOKEN)")
    ap.add_argument("--checkpoint", required=True,
                    help="torch checkpoint for the network")
    ap.add_argument("--think", type=float, default=3.0,
                    help="target seconds per move; the clock can shorten it "
                         "(default %(default)s)")
    ap.add_argument("--max-sims", type=int, default=200_000,
                    help="ceiling on simulations per move; the search tree is "
                         "preallocated to this size (default %(default)s)")
    ap.add_argument("--accept", choices=["all", "casual", "rated", "none"],
                    default="all", help="which challenges to accept "
                                        "(default %(default)s)")
    ap.add_argument("--seek", action="append", type=parse_seek, default=[],
                    metavar="INITIALxINCREMENT",
                    help="keep a seek with this clock open whenever idle, e.g. "
                         "300+3 or 300x3; rated unless suffixed :casual; "
                         "repeat to rotate through several time controls")
    ap.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    args = ap.parse_args()

    if not args.token:
        sys.exit("no API token: pass --token or set PALISADE_TOKEN")

    log("loading engine...")
    engine = Engine(args.checkpoint, args.device, args.max_sims, args.think)
    m = engine.meta
    log(f"engine: {m.get('checkpoint', args.checkpoint)} "
        f"(gen {m.get('iteration', '?')}, {m.get('elo', 0):+.0f} Elo internal, "
        f"device {engine.device})")
    log(f"calibrated at {engine.rate:,.0f} sims/s -> about "
        f"{min(args.max_sims, int(args.think * engine.rate)):,} sims per move "
        f"at a {args.think:.1f}s budget")

    bot = Bot(args, engine)
    bot.verify_account()
    try:
        bot.run()
    except KeyboardInterrupt:
        log("stopping")
        bot.cancel_seek()


if __name__ == "__main__":
    main()
