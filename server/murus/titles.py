"""Titles: who is a master, and on what evidence.

API.md is the contract; this is its arithmetic, deliberately kept free of the
database so the rules can be read and tested on their own. Two facts do all the
work:

- a title is only ever awarded on an *established* rating — RD at or below 110,
  our stand-in for FIDE's minimum number of rated games;
- a title, once held, is permanent. FIDE does not revoke a grandmaster's title
  when their rating falls, and neither do we, so the answer here is never lower
  than what the account already holds.
"""

from __future__ import annotations

# Highest first: the first threshold a rating clears is the title it earns.
# These are FIDE's real numbers, not figures scaled to this site's population.
THRESHOLDS: tuple[tuple[int, str], ...] = (
    (2500, "GM"),   # Grandmaster
    (2400, "IM"),   # International Master
    (2300, "FM"),   # FIDE Master
    (2200, "CM"),   # Candidate Master
)

# The same figure the site already calls non-provisional.
ESTABLISHED_RD = 110.0

# Lowest first, so a title's position is its seniority.
RANKS: tuple[str, ...] = ("CM", "FM", "IM", "GM")


def for_rating(rating: float) -> str | None:
    """The title this rating is worth, considering nothing else."""
    for threshold, title in THRESHOLDS:
        if rating >= threshold:
            return title
    return None


def rank(title: str | None) -> int:
    """Seniority as a number, so two titles can be compared. Untitled is 0."""
    return RANKS.index(title) + 1 if title in RANKS else 0


def established(rd: float) -> bool:
    """Has this rating settled enough to be a claim about anybody?"""
    return rd <= ESTABLISHED_RD


def awarded(peak: float, rd: float, held: str | None) -> str | None:
    """The title an account should hold now.

    ``peak`` is the highest rating it has reached, ``rd`` its current rating
    deviation, ``held`` the title it already has. The result is never lower
    than ``held``.
    """
    if not established(rd):
        # Worth stating plainly, because it is the case that looks like an
        # oversight when it bites: an account two lucky wins into its life can
        # sit at 2600 with an RD of 300 and has earned nothing at all. That
        # rating is a guess the system has not yet checked against anyone.
        return held
    earned = for_rating(peak)
    return earned if rank(earned) > rank(held) else held
