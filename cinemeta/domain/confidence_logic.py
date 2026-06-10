from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any


class AmpelStatus(Enum):
    GREEN = "GREEN"    # auto-accept
    YELLOW = "YELLOW"  # manual selection required
    RED = "RED"        # mandatory manual input


_GREEN_THRESHOLD = 0.85
_RED_THRESHOLD = 0.50
_MIN_DISTANCE = 0.15


@dataclass
class ConfidenceResult:
    status: AmpelStatus
    best: dict[str, Any] | None
    all_options: list[dict[str, Any]]
    distance: float  # gap between top-1 and top-2 score


def classify(options: list[dict[str, Any]]) -> ConfidenceResult:
    """Classify a list of scored options into an AmpelStatus.

    Each option must have a ``score`` key (float 0–1).
    """
    if not options:
        return ConfidenceResult(AmpelStatus.RED, None, [], 0.0)

    sorted_opts = sorted(options, key=lambda o: o["score"], reverse=True)
    best = sorted_opts[0]
    best_score: float = best["score"]

    distance = best_score - sorted_opts[1]["score"] if len(sorted_opts) > 1 else best_score

    if best_score < _RED_THRESHOLD:
        status = AmpelStatus.RED
    elif best_score >= _GREEN_THRESHOLD and distance >= _MIN_DISTANCE:
        status = AmpelStatus.GREEN
    else:
        status = AmpelStatus.YELLOW

    return ConfidenceResult(status, best, sorted_opts, distance)
