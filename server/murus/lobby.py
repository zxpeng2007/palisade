"""Seeks and challenges: how games begin.

A seek is anonymous matchmaking: same time control, same rated flag, first
compatible pair plays (colors random). A challenge is directed at a named
account and carries a color preference. Both live purely in memory; a restart
clears the lobby, which is the correct behaviour.
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from random import Random

from fastapi import HTTPException

from murus import speed
from murus.events import hub, online_ids
from murus.games import Player, manager

_rng = Random()

CHALLENGE_TTL = 120.0      # seconds before an unanswered challenge lapses
MAX_OPEN_CHALLENGES = 5    # per challenger

VALID_INITIAL = range(60, 3601)
VALID_INCREMENT = range(0, 61)


def check_clock(clock: dict) -> tuple[int, int]:
    try:
        initial, increment = int(clock["initial"]), int(clock["increment"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(400, "clock must be {initial, increment} in seconds")
    if initial not in VALID_INITIAL or increment not in VALID_INCREMENT:
        raise HTTPException(400, "initial must be 60-3600, increment 0-60")
    return initial, increment


@dataclass
class Seek:
    player: Player
    rated: bool
    initial: int
    increment: int

    def public(self) -> dict:
        return {"username": self.player.username,
                "rating": round(self.player.rating), "rated": self.rated,
                "bot": self.player.bot,
                "speed": speed.category(self.initial, self.increment),
                "clock": {"initial": self.initial, "increment": self.increment}}


@dataclass
class Challenge:
    id: str
    challenger: Player
    dest: Player
    rated: bool
    initial: int
    increment: int
    color: str  # random | first | second, challenger's seat
    created: float = field(default_factory=time.monotonic)

    def public(self) -> dict:
        return {"id": self.id, "challenger": self.challenger.username,
                "destUser": self.dest.username, "rated": self.rated,
                "clock": {"initial": self.initial, "increment": self.increment},
                "color": self.color}


class Lobby:
    def __init__(self):
        self.seeks: dict[int, Seek] = {}          # user_id -> seek (one each)
        self.challenges: dict[str, Challenge] = {}

    # -- seeks --------------------------------------------------------------

    def add_seek(self, player: Player, rated: bool, initial: int, increment: int):
        """Match instantly if a compatible seek waits, else park it.

        A new seek always replaces the poster's previous one — including on an
        instant match, where leaving the old seek parked would let a single
        account stack games it never asked for.
        """
        self.seeks.pop(player.id, None)
        for uid, s in list(self.seeks.items()):
            if (uid != player.id and s.rated == rated
                    and s.initial == initial and s.increment == increment):
                del self.seeks[uid]
                a_seat = _rng.randint(0, 1)
                game = manager.create(s.player, player, rated, initial,
                                      increment, a_seat)
                self._changed()
                return game
        self.seeks[player.id] = Seek(player, rated, initial, increment)
        self._changed()
        return None

    def cancel_seek(self, user_id: int) -> None:
        if self.seeks.pop(user_id, None) is not None:
            self._changed()

    # -- challenges ---------------------------------------------------------

    def _sweep(self) -> None:
        cutoff = time.monotonic() - CHALLENGE_TTL
        for cid in [c for c, ch in self.challenges.items() if ch.created < cutoff]:
            ch = self.challenges.pop(cid)
            hub.publish(f"user:{ch.dest.id}",
                        {"type": "challengeCanceled", "challenge": ch.public()})

    def challenge(self, challenger: Player, dest: Player, rated: bool,
                  initial: int, increment: int, color: str) -> Challenge:
        self._sweep()
        if color not in ("random", "first", "second"):
            raise HTTPException(400, "color must be random, first, or second")
        if dest.id == challenger.id:
            raise HTTPException(400, "you cannot challenge yourself")
        open_count = sum(1 for c in self.challenges.values()
                         if c.challenger.id == challenger.id)
        if open_count >= MAX_OPEN_CHALLENGES:
            raise HTTPException(429, "too many open challenges")
        ch = Challenge(secrets.token_urlsafe(6), challenger, dest, rated,
                       initial, increment, color)
        self.challenges[ch.id] = ch
        hub.publish(f"user:{dest.id}", {"type": "challenge", "challenge": ch.public()})
        return ch

    def _take(self, challenge_id: str, user_id: int, who: str) -> Challenge:
        self._sweep()
        ch = self.challenges.get(challenge_id)
        if ch is None:
            raise HTTPException(404, "no such challenge")
        expect = ch.dest.id if who == "dest" else ch.challenger.id
        if user_id != expect:
            raise HTTPException(403, "not your challenge")
        del self.challenges[challenge_id]
        return ch

    def accept(self, challenge_id: str, user_id: int):
        ch = self._take(challenge_id, user_id, "dest")
        color = ch.color if ch.color != "random" else _rng.choice(["first", "second"])
        a_seat = 0 if color == "first" else 1
        return manager.create(ch.challenger, ch.dest, ch.rated, ch.initial,
                              ch.increment, a_seat)

    def decline(self, challenge_id: str, user_id: int) -> None:
        ch = self._take(challenge_id, user_id, "dest")
        hub.publish(f"user:{ch.challenger.id}",
                    {"type": "challengeDeclined", "challenge": ch.public()})

    def cancel(self, challenge_id: str, user_id: int) -> None:
        ch = self._take(challenge_id, user_id, "challenger")
        hub.publish(f"user:{ch.dest.id}",
                    {"type": "challengeCanceled", "challenge": ch.public()})

    # -- snapshots ----------------------------------------------------------

    def snapshot(self) -> dict:
        from murus import db
        online = online_ids()
        bots = []
        if online:
            marks = ",".join("?" * len(online))
            for row in db.query(
                f"SELECT * FROM users WHERE is_bot=1 AND id IN ({marks})",
                tuple(online),
            ):
                bots.append(Player.from_row(dict(row)).public())
        games = []
        for g in manager.live.values():
            games.append({"id": g.id,
                          "first": g.players[0].public(),
                          "second": g.players[1].public(),
                          "rated": g.rated, "ply": len(g.moves),
                          "speed": speed.category(g.initial, g.increment),
                          "clock": {"initial": g.initial, "increment": g.increment}})
        return {"type": "lobby",
                "seeks": [s.public() for s in self.seeks.values()],
                "games": games, "bots": bots}

    def _changed(self) -> None:
        hub.publish("lobby", {"type": "lobbyChanged"})


lobby = Lobby()
