"""Reusable score-pool calibration rules distilled from daily reviews."""

from __future__ import annotations

from typing import Iterable

MAX_SCORE_POOL = 5


def lowest_available(candidates: Iterable[str], prices: dict[str, float]) -> str | None:
    available = [score for score in candidates if score in prices]
    return min(available, key=prices.get) if available else None


def calibrated_score_pool(
    scores: list[tuple[str, float]],
    probs: dict[str, float],
    goals: list[tuple[str, float]],
) -> tuple[str, list[str], list[str], str]:
    """Return main score, backups, audited tails and a human-readable reason."""
    if not scores:
        raise ValueError("score market is empty")
    prices = dict(scores)
    market = max(probs, key=probs.get)
    gap = abs(probs["home"] - probs["away"])
    balanced = gap <= 0.12 or probs["draw"] >= 0.29

    if balanced:
        main = lowest_available(("0-0", "1-1"), prices) or scores[0][0]
        required = ["0-0", "1-1", "1-0", "0-1"]
        reason = "均势低进球盘同时覆盖0-0、1-1及双向单球路径。"
    elif market == "home":
        main = lowest_available(("1-0", "2-0", "2-1"), prices) or scores[0][0]
        required = ["1-0", "2-0", "2-1", "1-1"]
        reason = "主胜同时保留单球、零封扩大比分和双方进球保护。"
    else:
        main = lowest_available(("0-1", "0-2", "1-2"), prices) or scores[0][0]
        required = ["0-1", "0-2", "1-2", "1-1"]
        reason = "客胜同时保留单球、零封扩大比分和双方进球保护。"

    tails: list[str] = []
    if market == "home" and probs["home"] >= 0.55:
        tails = [s for s in ("3-0", "3-1", "4-0", "4-1") if prices.get(s, 999) <= 35]
    elif market == "away" and probs["away"] >= 0.55:
        tails = [s for s in ("0-3", "1-3", "0-4", "1-4") if prices.get(s, 999) <= 35]

    ordered = [main]
    for score in required + tails + [score for score, _ in scores]:
        if score in prices and score not in ordered:
            ordered.append(score)
        if len(ordered) >= MAX_SCORE_POOL:
            break

    # Zero goals is a protection route only when the market is balanced/low scoring.
    low_goal = goals[0][0] if goals else "2"
    if balanced and low_goal in {"0", "1", "2"} and "0-0" in prices and "0-0" not in ordered:
        ordered[-1] = "0-0"
    return ordered[0], ordered[1:], tails, reason


def calibrated_confidence(probs: dict[str, float], predicted_direction: str) -> int:
    """Conservative pre-match confidence; deliberately capped below 90."""
    gap = abs(probs["home"] - probs["away"])
    top_probability = max(probs.values())
    score = round(42 + max(0, top_probability - 0.34) * 58 + gap * 20)
    if predicted_direction == "draw":
        score -= 5
    return max(35, min(88, score))
