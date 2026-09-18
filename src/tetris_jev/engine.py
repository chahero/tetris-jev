from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import pairwise

WIDTH, HEIGHT = 10, 20
SHAPES = {
    "I": ((0, 0), (1, 0), (2, 0), (3, 0)),
    "O": ((0, 0), (1, 0), (0, 1), (1, 1)),
    "T": ((1, 0), (0, 1), (1, 1), (2, 1)),
    "S": ((1, 0), (2, 0), (0, 1), (1, 1)),
    "Z": ((0, 0), (1, 0), (1, 1), (2, 1)),
    "J": ((0, 0), (0, 1), (1, 1), (2, 1)),
    "L": ((2, 0), (0, 1), (1, 1), (2, 1)),
}


def rotations(piece: str) -> tuple:
    cells = SHAPES[piece]
    result = []
    for _ in range(4):
        min_x, min_y = min(x for x, y in cells), min(y for x, y in cells)
        cells = tuple(sorted((x - min_x, y - min_y) for x, y in cells))
        if cells not in result:
            result.append(cells)
        cells = tuple((-y, x) for x, y in cells)
    return tuple(result)


def fits(board: list, cells: tuple, x: int, y: int) -> bool:
    return all(
        0 <= x + dx < WIDTH and 0 <= y + dy < HEIGHT and not board[y + dy][x + dx]
        for dx, dy in cells
    )


def features(board: list) -> dict:
    heights, holes = [], 0
    for x in range(WIDTH):
        top = next((y for y in range(HEIGHT) if board[y][x]), HEIGHT)
        heights.append(HEIGHT - top)
        holes += sum(not board[y][x] for y in range(top, HEIGHT))
    return {
        "column_heights": heights,
        "aggregate_height": sum(heights),
        "max_height": max(heights),
        "holes": holes,
        "bumpiness": sum(abs(a - b) for a, b in pairwise(heights)),
    }


@dataclass(frozen=True)
class Placement:
    key: str
    rotation: int
    x: int
    y: int
    cells: tuple
    board: tuple
    lines: int

    def describe(self) -> dict:
        return {
            "rotation_index": self.rotation,
            "left_column": self.x + 1,
            "landing_row": self.y + 1,
            "cleared_lines": self.lines,
            **features(self.board),
        }


def placements(board: list, piece: str) -> list[Placement]:
    result = []
    for rotation, cells in enumerate(rotations(piece)):
        for x in range(WIDTH - max(dx for dx, dy in cells)):
            if not fits(board, cells, x, 0):
                continue
            y = 0
            while fits(board, cells, x, y + 1):
                y += 1
            after = [list(row) for row in board]
            for dx, dy in cells:
                after[y + dy][x + dx] = piece
            remaining = [row for row in after if not all(row)]
            lines = HEIGHT - len(remaining)
            after = [[""] * WIDTH for _ in range(lines)] + remaining
            result.append(
                Placement(
                    f"r{rotation}_c{x + 1}",
                    rotation,
                    x,
                    y,
                    cells,
                    tuple(tuple(row) for row in after),
                    lines,
                )
            )
    return result


class Game:
    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.board = [[""] * WIDTH for _ in range(HEIGHT)]
        self.queue: list[str] = []
        self.score = self.lines = self.pieces = 0
        self.refill()

    def refill(self):
        while len(self.queue) < 8:
            bag = list(SHAPES)
            self.rng.shuffle(bag)
            self.queue.extend(bag)

    @property
    def piece(self):
        return self.queue[0]

    def candidates(self):
        return placements(self.board, self.piece)

    def state(self):
        return {
            "rules": "10 columns, 20 rows. Rows top to bottom; # occupied, . empty. "
            "Choose rotation and column before a vertical drop. No hold, tucks or wall kicks.",
            "board": ["".join("#" if c else "." for c in row) for row in self.board],
            "current_piece": self.piece,
            "next_pieces": self.queue[1:4],
            "lines": self.lines,
            "score": self.score,
            "pieces": self.pieces,
            **features(self.board),
        }

    def commit(self, key: str) -> dict:
        options = {p.key: p for p in self.candidates()}
        if key not in options:
            raise ValueError(f"Illegal placement: {key}")
        placement = options[key]
        level = self.lines // 10 + 1
        gained = (0, 100, 300, 500, 800)[placement.lines] * level
        self.board = [list(row) for row in placement.board]
        self.score += gained
        self.lines += placement.lines
        self.pieces += 1
        self.queue.pop(0)
        self.refill()
        return {"cleared_lines": placement.lines, "score_gained": gained}
