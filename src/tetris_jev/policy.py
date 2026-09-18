from __future__ import annotations

import math
import time
from dataclasses import asdict, dataclass

from .engine import Placement


@dataclass
class Decision:
    choice: str
    probabilities: dict[str, float]
    confidence: float
    latency_ms: float
    source: str

    def to_dict(self):
        return asdict(self)


def choose(state: dict, options: list[Placement], policy: str) -> Decision:
    if not options:
        raise ValueError("No legal placements")
    if policy == "heuristic":

        def utility(p):
            f = p.describe()
            return (
                0.76 * p.lines
                - 0.51 * f["aggregate_height"]
                - 0.36 * f["holes"]
                - 0.18 * f["bumpiness"]
            )

        selected = max(options, key=utility)
        return Decision(selected.key, {}, 0.0, 0.0, "heuristic")

    from typesafe_sdk import Choice, RetryPolicy, TypeSafeClient

    started = time.perf_counter()
    with TypeSafeClient(timeout=15.0, retry=RetryPolicy(max_retries=0)) as client:
        response = client.system_one(
            state=state,
            questions={
                "placement": Choice(
                    instructions=(
                        "Choose the best legal placement for the current Tetris piece. "
                        "Survive and clear lines. Each option describes the resulting board "
                        "AFTER line clears. Avoid creating holes (empty cells below occupied "
                        "cells), keep stack height and bumpiness low, and prefer line clears. "
                        "Consider upcoming pieces as tie breakers. Choose among ALL provided "
                        "candidates; they are not pre-ranked. Rotation and movement are executed "
                        "by the game; inference does not advance game time."
                    ),
                    criteria={p.key: p.describe() for p in options},
                )
            },
        )
    answer = response.choices["placement"]
    key = str(answer.choice)
    valid = {p.key for p in options}
    probabilities = {str(k): float(v) for k, v in answer.probabilities.items()}
    confidence = float(answer.confidence)
    if key not in valid or not math.isfinite(confidence):
        raise ValueError("Invalid model choice or confidence")
    if any(
        k not in valid or not math.isfinite(v) or not 0 <= v <= 1 for k, v in probabilities.items()
    ):
        raise ValueError("Invalid model probability distribution")
    return Decision(key, probabilities, confidence, (time.perf_counter() - started) * 1000, "jev")
