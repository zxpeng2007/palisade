"""Game-state helpers over the ``quoridor`` rules engine.

The engine package (github.com/zxpeng2007/quoridor-alphazero) is the single
source of truth for legality; nothing here re-implements a rule. Positions are
reconstructed by replaying token lists, which keeps the database format
(comma-joined tokens) and the wire format identical.
"""

from __future__ import annotations

import numpy as np

from quoridor import fastrules as fr

from palisade.notation import FILES, legal_token_map, square_token, wall_token


class IllegalMove(ValueError):
    pass


def warmup() -> None:
    fr.warmup()


def new_state() -> np.ndarray:
    return fr.initial_state()


def make_scratch() -> np.ndarray:
    return fr.make_scratch()


def apply_token(st: np.ndarray, token: str, scratch: np.ndarray) -> None:
    """Apply one token in place; raise IllegalMove if it is not legal here."""
    action = legal_token_map(st, scratch).get(token)
    if action is None:
        raise IllegalMove(token)
    fr.apply_action(st, action, scratch)


def replay(tokens: list[str]) -> np.ndarray:
    """State after a token sequence from the initial position."""
    st = fr.initial_state()
    scratch = fr.make_scratch()
    for t in tokens:
        if fr.winner(st) >= 0:
            raise IllegalMove(f"move after game end: {t}")
        apply_token(st, t, scratch)
    return st


def replay_views(tokens: list[str]) -> list[dict]:
    """Every position of a game, oldest first, index 0 being the start.

    Lets a client show any earlier moment without implementing the rules —
    which matters most for a spectator who arrived half way through and has
    no other way to know what came before.
    """
    st = fr.initial_state()
    scratch = fr.make_scratch()
    out = [view(st)]
    for t in tokens:
        if fr.winner(st) >= 0:
            raise IllegalMove(f"move after game end: {t}")
        apply_token(st, t, scratch)
        out.append(view(st))
    return out


def winner(st: np.ndarray) -> int:
    """-1 while running, else 0 (Player 1) or 1 (Player 2)."""
    return int(fr.winner(st))


def view(st: np.ndarray) -> dict:
    """A JSON-friendly snapshot of a position (for the REST game endpoint)."""
    walls_h = [wall_token(s) for s in range(64) if st[fr.WH_OFF + s]]
    walls_v = [wall_token(64 + s) for s in range(64) if st[fr.WV_OFF + s]]
    return {
        "p1": square_token(int(st[fr.IDX_P0])),
        "p2": square_token(int(st[fr.IDX_P1])),
        "wallsH": walls_h,
        "wallsV": walls_v,
        "wallsLeft": [int(st[fr.IDX_WL0]), int(st[fr.IDX_WL1])],
        "turn": int(st[fr.IDX_TURN]) + 1,
    }
