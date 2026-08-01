"""Glicko-2 rating update (Glickman 2013), applied per game.

One game = one rating period with a single opponent, the same simplification
Lichess uses. New accounts start at 1500 with RD 350 and volatility 0.06; an
RD above 110 renders as provisional.
"""

from __future__ import annotations

import math

SCALE = 173.7178
TAU = 0.5
EPS = 1e-6

DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOL = 0.06


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / math.pi**2)


def _e(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def update(
    rating: float, rd: float, vol: float,
    opponents: list[tuple[float, float, float]],
    tau: float = TAU,
) -> tuple[float, float, float]:
    """One rating period. ``opponents`` = [(their_rating, their_rd, score)],
    score 1.0 win / 0.5 draw / 0.0 loss. Returns (rating', rd', vol')."""
    mu = (rating - DEFAULT_RATING) / SCALE
    phi = rd / SCALE
    if not opponents:
        phi_star = math.sqrt(phi * phi + vol * vol)
        return rating, min(phi_star * SCALE, DEFAULT_RD), vol

    v_inv = 0.0
    delta_sum = 0.0
    for r_j, rd_j, score in opponents:
        mu_j = (r_j - DEFAULT_RATING) / SCALE
        phi_j = rd_j / SCALE
        g_j = _g(phi_j)
        e_j = _e(mu, mu_j, phi_j)
        v_inv += g_j * g_j * e_j * (1.0 - e_j)
        delta_sum += g_j * (score - e_j)
    v = 1.0 / v_inv
    delta = v * delta_sum

    # Volatility: Illinois-variant iteration from the Glicko-2 paper.
    a = math.log(vol * vol)

    def f(x: float) -> float:
        ex = math.exp(x)
        num = ex * (delta * delta - phi * phi - v - ex)
        den = 2.0 * (phi * phi + v + ex) ** 2
        return num / den - (x - a) / (tau * tau)

    big_a = a
    if delta * delta > phi * phi + v:
        big_b = math.log(delta * delta - phi * phi - v)
    else:
        k = 1
        while f(a - k * tau) < 0:
            k += 1
        big_b = a - k * tau
    fa, fb = f(big_a), f(big_b)
    while abs(big_b - big_a) > EPS:
        big_c = big_a + (big_a - big_b) * fa / (fb - fa)
        fc = f(big_c)
        if fc * fb <= 0:
            big_a, fa = big_b, fb
        else:
            fa = fa / 2.0
        big_b, fb = big_c, fc
    vol_new = math.exp(big_a / 2.0)

    phi_star = math.sqrt(phi * phi + vol_new * vol_new)
    phi_new = 1.0 / math.sqrt(1.0 / (phi_star * phi_star) + 1.0 / v)
    mu_new = mu + phi_new * phi_new * delta_sum
    return mu_new * SCALE + DEFAULT_RATING, phi_new * SCALE, vol_new


def duel(
    r1: float, rd1: float, v1: float,
    r2: float, rd2: float, v2: float,
    score1: float,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Update both sides of one game. ``score1`` is Player 1's score."""
    n1 = update(r1, rd1, v1, [(r2, rd2, score1)])
    n2 = update(r2, rd2, v2, [(r1, rd1, 1.0 - score1)])
    return n1, n2
