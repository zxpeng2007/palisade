"""Glicko-2 against the worked example in Glickman's paper (2013 revision)."""

from palisade import glicko2


def test_paper_example():
    r, rd, vol = glicko2.update(
        1500.0, 200.0, 0.06,
        [(1400.0, 30.0, 1.0), (1550.0, 100.0, 0.0), (1700.0, 300.0, 0.0)],
    )
    assert abs(r - 1464.06) < 0.5
    assert abs(rd - 151.52) < 0.5
    assert abs(vol - 0.05999) < 0.001


def test_win_gains_loss_costs():
    (r1, rd1, _), (r2, rd2, _) = glicko2.duel(
        1500, 350, 0.06, 1500, 350, 0.06, score1=1.0)
    assert r1 > 1500 > r2
    assert rd1 < 350 and rd2 < 350
    assert abs((r1 - 1500) + (r2 - 1500)) < 1.0  # symmetric at equal ratings


def test_upset_moves_more():
    (strong, _, _), _ = glicko2.duel(1800, 60, 0.06, 1500, 60, 0.06, score1=1.0)
    _, (weak_after_win, _, _) = glicko2.duel(1800, 60, 0.06, 1500, 60, 0.06, score1=0.0)
    assert strong - 1800 < weak_after_win - 1500  # expected win < upset win


def test_no_games_inflates_rd_only():
    r, rd, vol = glicko2.update(1600.0, 80.0, 0.06, [])
    assert r == 1600.0
    assert rd > 80.0
    assert vol == 0.06
