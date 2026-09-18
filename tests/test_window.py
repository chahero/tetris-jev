import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest

from tetris_jev.app import Session, Window
from tetris_jev.policy import choose


@pytest.fixture
def window(tmp_path):
    session = Session(42, "heuristic", 20, tmp_path)
    view = Window(session, 1.0, None, False)
    yield view
    view.pg.quit()
    session.close()


def test_pause_freezes_completed_request_until_resumed(window):
    before = window.session.game.state()
    decision = choose(before, window.session.game.candidates(), "heuristic")
    window.before = before
    window.pending = True
    window.paused = True
    window.results.put((decision, None))
    window.update(2)
    assert not window.pending
    assert window.selected is not None
    assert window.session.game.state() == before
    window.control("pause")
    window.update(2)
    assert window.session.game.pieces == 1


def test_restart_is_blocked_during_request_and_clears_selected_move(window):
    window.pending = True
    window.control("restart")
    assert window.session.episode == 1
    window.pending = False
    window.selected = window.session.game.candidates()[0]
    window.control("restart")
    assert window.session.episode == 2
    assert window.selected is None
    assert window.session.game.pieces == 0


def test_failure_pauses_without_fallback_and_retry_clears_error(window):
    window.pending = True
    window.before = window.session.game.state()
    window.results.put((None, "TypeSafeAPITimeoutError"))
    window.update(1)
    assert window.paused and window.error == "TypeSafeAPITimeoutError"
    assert window.session.game.pieces == 0
    window.draw()
    window.control("pause")
    assert not window.paused and not window.error
