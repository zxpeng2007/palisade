"""Move tokens <-> engine actions. The spec lives in API.md; this implements it.

The engine's 140-action space: actions 0-127 are walls (orientation * 64 +
slot, slot = rank_index * 8 + file_index, orientation 0 horizontal), actions
128-139 are pawn *directions*. Tokens name pawn moves by destination square,
so pawn conversion goes through the position: apply each legal pawn action and
read where the pawn landed.
"""

from __future__ import annotations

import numpy as np

from quoridor import fastrules as fr

FILES = "abcdefghi"


def square_token(cell: int) -> str:
    r, c = divmod(int(cell), 9)
    return f"{FILES[c]}{r + 1}"


def wall_token(action: int) -> str:
    orient, slot = divmod(int(action), fr.NUM_WALL_SLOTS)
    wr, wc = divmod(slot, 8)
    return ("h" if orient == 0 else "v") + FILES[wc] + str(wr + 1)


def parse_wall(token: str) -> int | None:
    """Wall token -> action int, or None if malformed. No legality check."""
    if len(token) != 3 or token[0] not in "hv":
        return None
    file_i = FILES.find(token[1])
    if file_i < 0 or file_i > 7 or not token[2].isdigit():
        return None
    rank_i = int(token[2]) - 1
    if not 0 <= rank_i <= 7:
        return None
    orient = 0 if token[0] == "h" else 1
    return orient * fr.NUM_WALL_SLOTS + rank_i * 8 + file_i


def legal_token_map(st: np.ndarray, scratch: np.ndarray) -> dict[str, int]:
    """Every legal move of the position, as token -> engine action."""
    mask = np.zeros(fr.NUM_ACTIONS, dtype=np.uint8)
    fr.legal_mask(st, mask, scratch)
    mover = int(st[fr.IDX_TURN])
    pawn_idx = fr.IDX_P0 if mover == 0 else fr.IDX_P1
    out: dict[str, int] = {}
    for a in np.nonzero(mask)[0]:
        a = int(a)
        if a < fr.MOVE_BASE:
            out[wall_token(a)] = a
        else:
            tmp = st.copy()
            fr.apply_action(tmp, a, scratch)
            out[square_token(int(tmp[pawn_idx]))] = a
    return out
