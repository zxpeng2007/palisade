"""Shared in-memory rate limiting: token buckets keyed by account or address.

One module so the HTTP and WebSocket paths enforce the same budgets — the
contract's move limit applies to the account, not to the transport it used.
"""

from __future__ import annotations

import time


class Buckets:
    def __init__(self, burst: float, rate: float):
        self.burst, self.rate = burst, rate
        self.state: dict[object, tuple[float, float]] = {}

    def take(self, key: object) -> bool:
        level, at = self.state.get(key, (self.burst, time.monotonic()))
        now = time.monotonic()
        level = min(self.burst, level + (now - at) * self.rate)
        if level < 1.0:
            self.state[key] = (level, now)
            return False
        self.state[key] = (level - 1.0, now)
        return True


# Moves: burst 20, ~10/s sustained (API.md).
moves = Buckets(burst=20.0, rate=10.0)
# Credential attempts (register/login) per client address: slow and small,
# because each attempt costs a scrypt.
credentials = Buckets(burst=5.0, rate=0.2)
