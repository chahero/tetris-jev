import json

import pytest

from tetris_jev.app import Session
from tetris_jev.policy import choose


def test_log_pairs_the_applied_decision_with_its_outcome(tmp_path):
    session = Session(42, "heuristic", 1, tmp_path)
    before = session.game.state()
    d = choose(before, session.game.candidates(), "heuristic")
    session.apply(d, before)
    assert session.end_reason() == "Piece limit reached"
    with pytest.raises(ValueError, match="outdated"):
        session.apply(d, before)
    session.close()
    events = [json.loads(line) for line in session.path.read_text().splitlines()]
    placement = events[1]
    assert placement["before"]["pieces"] == 0
    assert placement["after"]["pieces"] == 1
    assert placement["decision"]["choice"] == d.choice
    assert events[-1]["reason"] == "Piece limit reached"


def test_restart_preserves_seed_and_separates_episodes(tmp_path):
    session = Session(42, "heuristic", 10, tmp_path)
    before = session.game.state()
    session.apply(choose(before, session.game.candidates(), "heuristic"), before)
    session.restart()
    assert session.game.state() == before
    assert session.episode == 2
    session.close()
