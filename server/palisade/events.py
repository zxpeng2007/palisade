"""In-process pub/sub fanning game and account events to streams and sockets.

Keys are strings: ``user:{id}`` for account event streams, ``game:{id}`` for
game state, ``lobby`` for the seek/game lists. A subscriber that stops
draining (bounded queue fills) is dropped rather than allowed to stall the
publisher; streams recover by resubscribing, which always begins with a full
snapshot.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict


class Hub:
    def __init__(self, maxsize: int = 512):
        self._subs: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._maxsize = maxsize

    def subscribe(self, key: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subs[key].add(q)
        return q

    def unsubscribe(self, key: str, q: asyncio.Queue) -> None:
        self._subs[key].discard(q)
        if not self._subs[key]:
            self._subs.pop(key, None)

    def publish(self, key: str, msg: dict) -> None:
        dead = []
        for q in self._subs.get(key, ()):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self.unsubscribe(key, q)


hub = Hub()

# Presence: users with at least one open event stream or websocket. The lobby
# uses this to list connectable bots.
_presence: dict[int, int] = defaultdict(int)


def presence_inc(user_id: int) -> None:
    _presence[user_id] += 1


def presence_dec(user_id: int) -> None:
    _presence[user_id] -= 1
    if _presence[user_id] <= 0:
        _presence.pop(user_id, None)


def online_ids() -> set[int]:
    return set(_presence)
