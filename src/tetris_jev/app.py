from __future__ import annotations

import argparse
import json
import os
import queue
import threading
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

from .engine import SHAPES, Game, features
from .policy import Decision, choose
from .recording import Recorder

ROOT = Path(__file__).resolve().parents[2]
COLORS = {
    "I": (79, 212, 233),
    "O": (244, 199, 80),
    "T": (178, 135, 250),
    "S": (109, 216, 164),
    "Z": (241, 113, 131),
    "J": (112, 155, 249),
    "L": (245, 166, 99),
}
BG = (12, 16, 25)
PANEL = (20, 27, 40)
INK = (228, 235, 247)
MUTED = (132, 150, 176)
ACCENT = (109, 216, 164)


class Session:
    def __init__(self, seed: int, policy: str, limit: int, artifacts: Path):
        self.seed, self.policy, self.limit = seed, policy, limit
        self.game = Game(seed)
        artifacts.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        self.path = artifacts / f"run-{stamp}.jsonl"
        self.log = self.path.open("w", encoding="utf-8")
        self.episode = 1
        self.last = None
        self.last_result = None
        self.event("start", seed=seed, policy=policy, max_pieces=limit)

    def event(self, kind, **data):
        self.log.write(json.dumps({"event": kind, "episode": self.episode, **data}) + "\n")
        self.log.flush()

    def apply(self, decision: Decision, before: dict):
        if before != self.game.state():
            raise ValueError("Discarded decision for an outdated board")
        result = self.game.commit(decision.choice)
        self.last, self.last_result = decision, result
        self.event(
            "placement",
            before=before,
            decision=decision.to_dict(),
            outcome=result,
            after=self.game.state(),
        )

    def end_reason(self):
        if not self.game.candidates():
            return "Top out"
        if self.game.pieces >= self.limit:
            return "Piece limit reached"
        return None

    def restart(self):
        self.event("restart", final_state=self.game.state())
        self.episode += 1
        self.game = Game(self.seed)
        self.last = self.last_result = None
        self.event("start", seed=self.seed, policy=self.policy, max_pieces=self.limit)

    def close(self):
        self.event("end", reason=self.end_reason() or "Closed", final_state=self.game.state())
        self.log.close()


class Window:
    CELL, BX, BY = 30, 340, 130

    def __init__(self, session: Session, speed: float, screenshot: Path | None, auto_exit: bool):
        import pygame as pg

        self.pg, self.session = pg, session
        pg.init()
        self.screen = pg.display.set_mode((1040, 810))
        pg.display.set_caption("Tetris / Jev")
        self.clock = pg.time.Clock()
        self.fonts = {size: pg.font.SysFont("Segoe UI", size) for size in (13, 15, 18, 24, 36, 52)}
        self.speed = speed
        self.screenshot, self.saved, self.auto_exit = screenshot, False, auto_exit
        self.paused = False
        self.error = ""
        self.pending = False
        self.results = queue.Queue()
        self.selected = None
        self.decision = None
        self.before = None
        self.animation = 0.0
        self.flash = 0.0
        self.status = "Ready to play"
        self.end_logged = False
        self.buttons = {}

    def text(self, value, x, y, size=18, color=INK):
        self.screen.blit(self.fonts[size].render(str(value), True, color), (x, y))

    def button(self, key, label, rect):
        pg = self.pg
        bounds = pg.Rect(rect)
        hover = bounds.collidepoint(pg.mouse.get_pos())
        pg.draw.rect(self.screen, (43, 58, 76) if hover else PANEL, bounds, border_radius=8)
        self.text(label, bounds.x + 14, bounds.y + 11, 15)
        self.buttons[key] = bounds

    def cell(self, x, y, piece, ghost=False, small=False):
        pg = self.pg
        size = 20 if small else self.CELL
        color = COLORS[piece]
        rect = pg.Rect(x + 1, y + 1, size - 2, size - 2)
        if ghost:
            pg.draw.rect(self.screen, color, rect, width=1, border_radius=4)
        else:
            pg.draw.rect(self.screen, color, rect, border_radius=4)
            shine = tuple(min(255, c + 35) for c in color)
            pg.draw.line(self.screen, shine, (x + 5, y + 4), (x + size - 6, y + 4), 2)

    def request(self):
        game = self.session.game
        options = game.candidates()
        self.before = game.state()
        state = self.before
        policy = self.session.policy
        self.pending = True
        self.status = "Jev is choosing a placement..." if policy == "jev" else "Evaluating board..."

        def worker():
            try:
                self.results.put((choose(state, options, policy), None))
            except Exception as exc:  # noqa: BLE001 - contain failures at the worker boundary
                # Do not show SDK exception bodies, which can contain request data.
                self.results.put((None, type(exc).__name__))

        threading.Thread(target=worker, daemon=True, name="jev-placement").start()

    def control(self, key):
        if key == "pause":
            if self.error:
                self.error = ""
                self.paused = False
            else:
                self.paused = not self.paused
        elif key == "restart" and not self.pending:
            self.session.restart()
            self.selected = self.decision = None
            self.error = ""
            self.paused = False
            self.end_logged = False
            self.status = "New run / same seed"
        elif key == "speed":
            self.speed = {0.5: 1.0, 1.0: 2.0, 2.0: 4.0, 4.0: 0.5}.get(self.speed, 1.0)

    def update(self, dt):
        if self.pending:
            try:
                result, error = self.results.get_nowait()
            except queue.Empty:
                pass
            else:
                self.pending = False
                if error:
                    self.error = error
                    self.paused = True
                    self.status = "Request failed / paused"
                    self.session.event("error", error_type=error, state=self.before)
                else:
                    self.decision = result
                    self.selected = next(
                        p for p in self.session.game.candidates() if p.key == result.choice
                    )
                    self.animation = 0.0
                    self.status = (
                        f"Selected column {self.selected.x + 1} / rotation {self.selected.rotation}"
                    )
        if self.paused:
            return
        self.flash = max(0, self.flash - dt)
        if self.selected:
            self.animation += dt * self.speed
            if self.animation >= 0.9:
                self.session.apply(self.decision, self.before)
                self.flash = 0.45 if self.selected.lines else 0
                self.selected = None
        elif not self.pending and not self.error:
            reason = self.session.end_reason()
            if reason:
                self.status = reason
                if not self.end_logged:
                    self.session.event("game_end", reason=reason, state=self.session.game.state())
                    self.end_logged = True
            else:
                self.request()

    def draw(self):
        pg, g = self.pg, self.session.game
        self.screen.fill(BG)
        self.text("TETRIS", 36, 24, 36)
        self.text("/ JEV", 166, 32, 24, ACCENT)
        self.text("AN AI AT THE CONTROLS", 37, 75, 13, MUTED)
        label = "Retry" if self.error else ("Resume" if self.paused else "Pause")
        self.button("pause", label, (665, 30, 100, 46))
        self.button("restart", "Wait..." if self.pending else "Restart", (777, 30, 110, 46))
        self.button("speed", f"{self.speed:g}x speed", (899, 30, 108, 46))
        self.text(
            "JEV AUTOPLAY" if self.session.policy == "jev" else "HEURISTIC / OFFLINE",
            38,
            134,
            15,
            ACCENT,
        )
        self.text("SCORE", 38, 181, 13, MUTED)
        self.text(f"{g.score:,}", 35, 200, 52)
        self.text("LINES", 38, 288, 13, MUTED)
        self.text(g.lines, 37, 307, 36)
        self.text("PIECES", 174, 288, 13, MUTED)
        self.text(f"{g.pieces} / {self.session.limit}", 172, 316, 18)
        self.text("UP NEXT", 38, 386, 13, MUTED)
        for i, piece in enumerate(g.queue[1:4]):
            for dx, dy in SHAPES[piece]:
                self.cell(40 + dx * 20, 420 + i * 70 + dy * 20, piece, small=True)
            self.text(piece, 156, 426 + i * 70, 18, MUTED)
        self.text(f"SEED {g.seed}", 38, 679, 13, MUTED)
        self.text("7-bag / 10 x 20", 38, 702, 15, MUTED)

        pg.draw.rect(self.screen, (28, 40, 57), (self.BX - 2, self.BY - 2, 304, 604), 2)
        for y, row in enumerate(g.board):
            for x, piece in enumerate(row):
                px, py = self.BX + x * 30, self.BY + y * 30
                pg.draw.rect(self.screen, (19, 27, 40), (px + 1, py + 1, 28, 28), border_radius=3)
                if piece:
                    self.cell(px, py, piece)
        for x in range(10):
            self.text(x + 1, self.BX + x * 30 + 9, 108, 13, MUTED)
        if self.selected:
            p = self.selected
            fall = min(1, max(0, (self.animation - 0.18) / 0.6))
            y = p.y * (1 - (1 - fall) ** 2)
            for dx, dy in p.cells:
                self.cell(self.BX + (p.x + dx) * 30, self.BY + (p.y + dy) * 30, g.piece, ghost=True)
            for dx, dy in p.cells:
                self.cell(self.BX + (p.x + dx) * 30, self.BY + (y + dy) * 30, g.piece)
        elif self.pending:
            for dx, dy in SHAPES[g.piece]:
                self.cell(self.BX + (3 + dx) * 30, self.BY + dy * 30, g.piece, ghost=True)
        if self.flash:
            pg.draw.rect(self.screen, ACCENT, (self.BX - 3, self.BY - 3, 306, 606), 3)
        reason = self.session.end_reason()
        if self.paused or reason:
            shade = pg.Surface((300, 120), pg.SRCALPHA)
            shade.fill((12, 16, 25, 235))
            self.screen.blit(shade, (self.BX, 365))
            self.text("PAUSED" if self.paused else "RUN COMPLETE", self.BX + 38, 384, 24)
            self.text(
                "Retry / resume to continue" if self.paused else reason,
                self.BX + 38,
                427,
                15,
                MUTED,
            )

        self.text("THE NEXT MOVE", 678, 133, 15, MUTED)
        if self.selected:
            self.text(f"COLUMN {self.selected.x + 1:02}", 676, 166, 36)
        elif self.pending:
            self.text("THINKING...", 676, 174, 24, ACCENT)
        else:
            self.text("BOARD LOCKED" if reason else "READY", 676, 174, 24)
        d = self.decision or self.session.last
        self.text("CONFIDENCE", 678, 241, 13, MUTED)
        self.text("LATENCY", 855, 241, 13, MUTED)
        self.text(f"{d.confidence:.0%}" if d and d.source == "jev" else "--", 678, 264, 24)
        self.text(f"{d.latency_ms:.0f} ms" if d else "--", 855, 264, 24)
        self.text("PLACEMENT PROBABILITIES", 678, 324, 13, MUTED)
        top = sorted(d.probabilities.items(), key=lambda kv: kv[1], reverse=True)[:5] if d else []
        if not top:
            self.text(
                "Waiting for Jev"
                if self.session.policy == "jev"
                else "Rule-based / no probabilities",
                678,
                360,
                15,
                MUTED,
            )
        for i, (key, probability) in enumerate(top):
            y = 357 + i * 48
            selected = key == d.choice
            self.text(key.replace("_", " / "), 678, y, 15, ACCENT if selected else INK)
            self.text(f"{probability:.0%}", 944, y, 15, MUTED)
            pg.draw.rect(self.screen, PANEL, (678, y + 26, 302, 5), border_radius=2)
            pg.draw.rect(
                self.screen,
                ACCENT if selected else (75, 103, 135),
                (678, y + 26, round(302 * probability), 5),
                border_radius=2,
            )
        f = features(g.board)
        self.text("BOARD HEALTH", 678, 628, 13, MUTED)
        self.text(f"Height {f['max_height']:02}/20     Holes {f['holes']}", 678, 651, 18)
        if self.error:
            self.text(self.error[:38], 678, 690, 15, (241, 113, 131))
            self.text("Check .env / connection; press Retry", 678, 711, 13, MUTED)
        else:
            self.text(
                "All legal drops / chosen by "
                + ("Jev" if self.session.policy == "jev" else "rules"),
                678,
                700,
                15,
                MUTED,
            )
        pg.draw.line(self.screen, (38, 48, 65), (36, 752), (1005, 752))
        self.text("Paused" if self.paused and not self.error else self.status, 38, 771, 15, ACCENT)
        self.text("SPACE pause   R restart   +/- speed   ESC quit", 652, 771, 13, MUTED)
        pg.display.flip()

    def run(self, record_path=None):
        pg = self.pg
        running = True
        recorder = Recorder(record_path, self.screen.get_size()) if record_path else None
        try:
            while running:
                dt = min(self.clock.tick(60) / 1000, 0.05)
                for event in pg.event.get():
                    if event.type == pg.QUIT:
                        running = False
                    elif event.type == pg.KEYDOWN:
                        if event.key in (pg.K_ESCAPE, pg.K_q):
                            running = False
                        elif event.key == pg.K_SPACE:
                            self.control("pause")
                        elif event.key == pg.K_r:
                            self.control("restart")
                        elif event.key in (pg.K_PLUS, pg.K_EQUALS, pg.K_MINUS):
                            self.control("speed")
                    elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
                        for key, rect in self.buttons.items():
                            if rect.collidepoint(event.pos):
                                self.control(key)
                if not running:
                    break
                self.update(dt)
                self.draw()
                if recorder:
                    recorder.capture(self.screen)
                if (
                    self.screenshot
                    and not self.saved
                    and (self.session.game.pieces >= 3 or self.error or self.session.end_reason())
                ):
                    self.screenshot.parent.mkdir(parents=True, exist_ok=True)
                    pg.image.save(self.screen, str(self.screenshot))
                    self.saved = True
                if self.auto_exit and (self.session.end_reason() or self.error):
                    break
        finally:
            try:
                if recorder:
                    recorder.close()
            finally:
                pg.quit()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Watch Jev play Tetris, one placement at a time.")
    parser.add_argument("--policy", choices=("jev", "heuristic"), default="jev")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-pieces", type=int, default=200)
    parser.add_argument("--speed", type=float, choices=(0.5, 1.0, 2.0, 4.0), default=1.0)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument(
        "--paused", action="store_true", help="Open the window without sending requests"
    )
    parser.add_argument("--exit-after", action="store_true", help="Close window at run end (QA)")
    parser.add_argument("--screenshot", type=Path)
    parser.add_argument(
        "--record", type=Path, help="Record the game window as MP4 (requires FFmpeg)"
    )
    parser.add_argument("--artifacts-dir", type=Path, default=ROOT / "artifacts")
    args = parser.parse_args(argv)
    if args.max_pieces < 1:
        parser.error("--max-pieces must be positive")
    if args.record and args.headless:
        parser.error("--record requires the rendered window; omit --headless")
    load_dotenv(ROOT / ".env", override=False)
    if args.policy == "jev" and not os.environ.get("TYPESAFE_API_KEY", "").strip():
        parser.error(f"Set TYPESAFE_API_KEY in {ROOT / '.env'} or use --policy heuristic")
    session = Session(args.seed, args.policy, args.max_pieces, args.artifacts_dir)
    code = 0
    try:
        if args.headless:
            while not session.end_reason():
                state = session.game.state()
                decision = choose(state, session.game.candidates(), args.policy)
                session.apply(decision, state)
            print(
                f"{session.end_reason()}: {session.game.pieces} pieces, "
                f"{session.game.lines} lines, score {session.game.score}"
            )
        else:
            window = Window(session, args.speed, args.screenshot, args.exit_after)
            window.paused = args.paused
            window.run(args.record)
            if window.error:
                code = 1
    except KeyboardInterrupt:
        pass
    except Exception as exc:  # noqa: BLE001 - report failures without leaking SDK request bodies
        session.event("error", error_type=type(exc).__name__)
        print(f"Run stopped: {type(exc).__name__}. Check configuration and connectivity.")
        code = 1
    finally:
        session.close()
    print(f"Log: {session.path}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
