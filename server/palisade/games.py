"""Live games: authoritative state, server-side clocks, results, ratings.

Everything that can end a game funnels through ``LiveGame._finish`` — moves
reaching the goal, resignation, timeout (both lazy, on move receipt, and
active, via a per-game timer task), and abort. A game's asyncio lock is held
for every mutation, so a timer firing while a move is being applied cannot
double-finish.

Clock model: ``remaining[seat]`` is what the mover had when their turn began;
the elapsed share is subtracted when they move, then the increment is added.
State messages report both clocks as of send time.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from dataclasses import dataclass

from palisade import db, glicko2, rules
from palisade.events import hub
from palisade.notation import legal_token_map

SEAT_NAMES = ("first", "second")


class GameError(Exception):
    pass


@dataclass
class Player:
    id: int
    username: str
    rating: float
    rd: float
    vol: float
    bot: bool

    @classmethod
    def from_row(cls, row: dict) -> "Player":
        return cls(row["id"], row["username"], row["rating"], row["rd"],
                   row["vol"], bool(row["is_bot"]))

    def public(self) -> dict:
        return {"username": self.username, "rating": round(self.rating),
                "provisional": self.rd > 110, "bot": self.bot}


class LiveGame:
    def __init__(self, game_id: str, players: tuple[Player, Player],
                 rated: bool, initial: int, increment: int):
        self.id = game_id
        self.players = players
        self.rated = rated
        self.initial = initial
        self.increment = increment
        self.st = rules.new_state()
        self.scratch = rules.make_scratch()
        self.moves: list[str] = []
        self.status = "active"
        self.winner: int | None = None
        self.reason: str | None = None
        self.remaining = [float(initial), float(initial)]
        self.turn_started = time.monotonic()
        self.lock = asyncio.Lock()
        self._timer: asyncio.Task | None = None

    # -- queries ------------------------------------------------------------

    def mover(self) -> int:
        return int(self.st[rules.fr.IDX_TURN])

    def seat_of(self, user_id: int) -> int | None:
        for i, p in enumerate(self.players):
            if p.id == user_id:
                return i
        return None

    def legal_tokens(self) -> list[str]:
        return sorted(legal_token_map(self.st, self.scratch))

    def clocks(self) -> tuple[float, float]:
        """Both clocks as of now (the mover's ticking down)."""
        out = list(self.remaining)
        if self.status == "active":
            m = self.mover()
            out[m] = max(0.0, out[m] - (time.monotonic() - self.turn_started))
        return out[0], out[1]

    def state_msg(self) -> dict:
        p1t, p2t = self.clocks()
        return {
            "type": "gameState",
            "moves": ",".join(self.moves),
            "view": rules.view(self.st),
            "p1time": round(p1t, 2),
            "p2time": round(p2t, 2),
            "status": self.status,
            "winner": SEAT_NAMES[self.winner] if self.winner is not None else None,
            "reason": self.reason,
        }

    def full_msg(self) -> dict:
        return {
            "type": "gameFull",
            "id": self.id,
            "rated": self.rated,
            "clock": {"initial": self.initial, "increment": self.increment},
            "first": self.players[0].public(),
            "second": self.players[1].public(),
            "state": self.state_msg(),
        }

    # -- mutations ----------------------------------------------------------

    async def move(self, user_id: int, token: str) -> None:
        async with self.lock:
            if self.status != "active":
                raise GameError("the game is over")
            seat = self.seat_of(user_id)
            if seat is None:
                raise GameError("you are not a player in this game")
            if seat != self.mover():
                raise GameError("not your turn")
            elapsed = time.monotonic() - self.turn_started
            if self.remaining[seat] - elapsed <= 0:
                self._finish(winner=1 - seat, reason="timeout")
                return
            action = legal_token_map(self.st, self.scratch).get(token)
            if action is None:
                raise GameError(f"illegal move: {token}")
            self.remaining[seat] += self.increment - elapsed
            rules.fr.apply_action(self.st, action, self.scratch)
            self.moves.append(token)
            self.turn_started = time.monotonic()
            if rules.winner(self.st) >= 0:
                self._finish(winner=seat, reason="mate")
            else:
                self._arm_timer()
                self._broadcast()

    async def resign(self, user_id: int) -> None:
        async with self.lock:
            if self.status != "active":
                raise GameError("the game is over")
            seat = self.seat_of(user_id)
            if seat is None:
                raise GameError("you are not a player in this game")
            self._finish(winner=1 - seat, reason="resign")

    async def abort(self, user_id: int) -> None:
        async with self.lock:
            if self.status != "active":
                raise GameError("the game is over")
            if self.seat_of(user_id) is None:
                raise GameError("you are not a player in this game")
            if len(self.moves) >= 2:
                raise GameError("too late to abort; resign instead")
            self.status = "aborted"
            self.reason = "abort"
            self._persist()
            self._announce_end()

    # -- internals (call with lock held) ------------------------------------

    def _arm_timer(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
        seat = self.mover()
        self._timer = asyncio.get_running_loop().create_task(
            self._deadline(seat, len(self.moves), self.remaining[seat])
        )

    async def _deadline(self, seat: int, ply: int, budget: float) -> None:
        try:
            await asyncio.sleep(budget + 0.05)
        except asyncio.CancelledError:
            return
        async with self.lock:
            if self.status == "active" and len(self.moves) == ply:
                self._finish(winner=1 - seat, reason="timeout")

    def _finish(self, winner: int, reason: str) -> None:
        self.status = "finished"
        self.winner = winner
        self.reason = reason
        m = self.mover()
        self.remaining[m] = max(
            0.0, self.remaining[m] - (time.monotonic() - self.turn_started))
        deltas = (None, None)
        if self.rated:
            deltas = self._apply_ratings()
        self._persist(deltas)
        self._announce_end()

    def _apply_ratings(self) -> tuple[float, float]:
        a, b = self.players
        score1 = 1.0 if self.winner == 0 else 0.0
        (r1, rd1, v1), (r2, rd2, v2) = glicko2.duel(
            a.rating, a.rd, a.vol, b.rating, b.rd, b.vol, score1)
        d1, d2 = r1 - a.rating, r2 - b.rating
        db.execute(
            "UPDATE users SET rating=?, rd=?, vol=?, rated_games=rated_games+1 WHERE id=?",
            (r1, rd1, v1, a.id))
        db.execute(
            "UPDATE users SET rating=?, rd=?, vol=?, rated_games=rated_games+1 WHERE id=?",
            (r2, rd2, v2, b.id))
        a.rating, a.rd, a.vol = r1, rd1, v1
        b.rating, b.rd, b.vol = r2, rd2, v2
        return d1, d2

    def _persist(self, deltas: tuple = (None, None)) -> None:
        db.execute(
            """UPDATE games SET moves=?, status=?, winner=?, reason=?,
               p1_delta=?, p2_delta=?, finished=datetime('now') WHERE id=?""",
            (",".join(self.moves), self.status, self.winner, self.reason,
             deltas[0], deltas[1], self.id))

    def _announce_end(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._broadcast()
        for seat, p in enumerate(self.players):
            hub.publish(f"user:{p.id}", {
                "type": "gameFinish",
                "game": {"id": self.id,
                         "winner": SEAT_NAMES[self.winner] if self.winner is not None else None,
                         "reason": self.reason},
            })
        manager.retire(self.id)

    def _broadcast(self) -> None:
        hub.publish(f"game:{self.id}", self.state_msg())


class GameManager:
    def __init__(self):
        self.live: dict[str, LiveGame] = {}

    def create(self, a: Player, b: Player, rated: bool,
               initial: int, increment: int, a_seat: int) -> LiveGame:
        """Start a game. ``a_seat`` 0 puts ``a`` on the first seat."""
        players = (a, b) if a_seat == 0 else (b, a)
        game_id = secrets.token_urlsafe(6)
        db.execute(
            """INSERT INTO games (id, p1, p2, rated, initial, increment, status,
               p1_rating, p2_rating) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?)""",
            (game_id, players[0].id, players[1].id, int(rated), initial,
             increment, players[0].rating, players[1].rating))
        game = LiveGame(game_id, players, rated, initial, increment)
        self.live[game_id] = game
        for seat, p in enumerate(players):
            opp = players[1 - seat]
            hub.publish(f"user:{p.id}", {
                "type": "gameStart",
                "game": {"id": game_id, "color": SEAT_NAMES[seat],
                         "opponent": opp.public(), "rated": rated,
                         "clock": {"initial": initial, "increment": increment}},
            })
        game._arm_timer()
        hub.publish("lobby", {"type": "lobbyChanged"})
        return game

    def retire(self, game_id: str) -> None:
        self.live.pop(game_id, None)
        hub.publish("lobby", {"type": "lobbyChanged"})

    def get(self, game_id: str) -> LiveGame | None:
        return self.live.get(game_id)


manager = GameManager()
