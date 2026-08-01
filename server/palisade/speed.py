"""Time-control speed categories.

A game's speed comes from its estimated duration, ``initial + 40 * increment``
seconds -- forty moves being a reasonable game -- which is the rule Lichess
uses and the one players already have intuitions about. Deriving it on demand
rather than storing it means existing rows need no migration and the
thresholds can be retuned later without rewriting history.
"""

from __future__ import annotations

ORDER = ("bullet", "blitz", "rapid", "classical")


def category(initial: int, increment: int) -> str:
    estimate = initial + 40 * increment
    if estimate < 180:
        return "bullet"
    if estimate < 480:
        return "blitz"
    if estimate < 1500:
        return "rapid"
    return "classical"


def label(initial: int, increment: int) -> str:
    """Human-readable time control, e.g. 5+3 or 0.5+0."""
    minutes = initial / 60
    shown = int(minutes) if minutes == int(minutes) else round(minutes, 1)
    return f"{shown}+{increment}"
