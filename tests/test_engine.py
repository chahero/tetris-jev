import pytest

from tetris_jev.engine import SHAPES, Game, features, fits, placements, rotations
from tetris_jev.policy import choose


def test_unique_rotations_and_empty_board_candidates():
    board = [[""] * 10 for _ in range(20)]
    assert {p: len(rotations(p)) for p in SHAPES} == {
        "I": 2,
        "O": 1,
        "T": 4,
        "S": 2,
        "Z": 2,
        "J": 4,
        "L": 4,
    }
    assert len(placements(board, "I")) == 17
    assert len(placements(board, "O")) == 9
    assert len(placements(board, "T")) == 34
    for piece in SHAPES:
        for p in placements(board, piece):
            assert fits(board, p.cells, p.x, p.y)
            assert not fits(board, p.cells, p.x, p.y + 1)
            assert sum(bool(c) for row in p.board for c in row) == 4


def test_four_line_clear_and_score():
    g = Game()
    g.queue[0] = "I"
    for y in range(16, 20):
        g.board[y] = ["J"] * 9 + [""]
    p = next(p for p in g.candidates() if p.lines == 4)
    result = g.commit(p.key)
    assert result == {"cleared_lines": 4, "score_gained": 800}
    assert g.lines == 4 and g.score == 800 and g.pieces == 1
    assert all(not any(row) for row in g.board)


def test_holes_count_and_topout():
    board = [[""] * 10 for _ in range(20)]
    board[17][0] = "I"
    board[19][0] = "I"
    assert features(board)["holes"] == 1
    assert features(board)["max_height"] == 3
    assert not placements([["I"] * 10 for _ in range(20)], "T")


def test_invalid_commit_does_not_mutate_game():
    g = Game()
    before = g.state()
    with pytest.raises(ValueError):
        g.commit("not-a-placement")
    assert g.state() == before


def test_seven_bag_is_deterministic():
    a, b = Game(7), Game(7)
    assert a.queue == b.queue
    assert set(a.queue[:7]) == set(SHAPES)
    assert set(a.queue[7:14]) == set(SHAPES)


@pytest.mark.parametrize("seed", [1, 42, 123])
def test_long_run_conserves_cells_and_clears_rows(seed):
    g = Game(seed)
    for _ in range(250):
        options = g.candidates()
        if not options:
            break
        before_cells = sum(bool(c) for row in g.board for c in row)
        d = choose(g.state(), options, "heuristic")
        result = g.commit(d.choice)
        after_cells = sum(bool(c) for row in g.board for c in row)
        assert after_cells == before_cells + 4 - 10 * result["cleared_lines"]
        assert len(g.board) == 20 and all(len(row) == 10 for row in g.board)
        assert all(not all(row) for row in g.board)
    assert g.lines > 0
