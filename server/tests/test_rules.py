"""Notation and rules-bridge tests, anchored to a real recorded game."""

import pytest

from murus import rules
from murus.notation import legal_token_map, parse_wall, square_token, wall_token
from quoridor import fastrules as fr

# A complete ranked game from the wild (barricade.gg qj4ec3, 2026-07-31),
# known final position: P1 on a5 with 3 walls left, P2 wins on i1 with 0.
QJ4EC3 = (
    "e2,e8,e3,e7,e4,e6,hc3,vd4,e5,e4,e6,e3,he2,he3,e7,hd7,vd2,hh2,va3,hg3,"
    "f7,hf7,hh4,hh7,vf1,vg4,hg1,f3,e7,vc6,e6,hb5,d6,g3,d5,g2,c5,h2,b5,i2,a5,i1"
).split(",")


def test_initial_position():
    st = rules.new_state()
    assert square_token(int(st[fr.IDX_P0])) == "e1"
    assert square_token(int(st[fr.IDX_P1])) == "e9"
    m = legal_token_map(st, rules.make_scratch())
    assert len(m) == 131  # 128 walls + d1, f1, e2
    assert {"d1", "f1", "e2"} <= set(m)


def test_wall_tokens_round_trip():
    for action in range(128):
        assert parse_wall(wall_token(action)) == action


def test_parse_wall_rejects_garbage():
    for bad in ("", "e2", "ha9", "hi1", "xa1", "h a", "ha0", "haa"):
        assert parse_wall(bad) is None


def test_real_game_replays_to_known_result():
    st = rules.replay(QJ4EC3)
    assert rules.winner(st) == 1
    v = rules.view(st)
    assert v["p1"] == "a5"
    assert v["p2"] == "i1"
    assert v["wallsLeft"] == [3, 0]
    assert len(v["wallsH"]) == 11 and len(v["wallsV"]) == 6


def test_illegal_moves_raise():
    st = rules.new_state()
    sc = rules.make_scratch()
    with pytest.raises(rules.IllegalMove):
        rules.apply_token(st, "e9", sc)      # not reachable
    with pytest.raises(rules.IllegalMove):
        rules.apply_token(st, "zz9", sc)     # nonsense
    rules.apply_token(st, "e2", sc)          # fine
    with pytest.raises(rules.IllegalMove):
        rules.replay(QJ4EC3 + ["e2"])        # move after game end


def test_jump_and_diagonal():
    # March the pawns face to face; the mover must be offered the jump.
    st = rules.new_state()
    sc = rules.make_scratch()
    for t in ("e2", "e8", "e3", "e7", "e4", "e6", "e5"):
        rules.apply_token(st, t, sc)
    m = legal_token_map(st, sc)   # P2 on e6 faces P1 on e5
    assert "e4" in m              # jump straight over
