"""Three-layer football model: hard strength, tactical matchup, psychology.

The generator accepts a structured ``threeLayer`` object in each match context.
Each leaf may be a number or ``{"score": number, "source": str}``. Missing
leaves are neutral (50), are listed in the audit output, and reduce confidence.
Odds are deliberately not part of this module; the caller may use them only as
a secondary market check.
"""
from __future__ import annotations

import math
from typing import Any

VERSION = "three-layer-v1-evidence-first"
WEIGHTS = {"hardStrength": 0.40, "tacticalMatchup": 0.35, "psychologicalState": 0.25}
ITEMS = {
    "hardStrength": ("leagueRanking", "squadValue", "recentForm", "venueAttribute"),
    "tacticalMatchup": ("styleMatchup", "headToHead", "coreAvailability"),
    "psychologicalState": ("lastResult", "scheduleFitness", "motivation"),
}


def _score(value: Any) -> tuple[float, bool]:
    if isinstance(value, dict):
        value = value.get("score")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 50.0, False
    if not math.isfinite(number):
        return 50.0, False
    return max(0.0, min(100.0, number)), True


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _probabilities(home_total: float, away_total: float, caution: float) -> dict[str, float]:
    # Four points represent the normal home advantage.  Knockout first/second
    # legs may add draw caution supplied by the evidence layer.
    gap = (home_total + 4.0) - away_total
    draw = max(0.20, min(0.44, 0.30 - abs(gap) * 0.004 + caution))
    home_share = _sigmoid(gap / 12.0)
    return {
        "home": round((1.0 - draw) * home_share, 4),
        "draw": round(draw, 4),
        "away": round((1.0 - draw) * (1.0 - home_share), 4),
    }


def calculate_three_layer(context: dict[str, Any]) -> dict[str, Any]:
    evidence = context.get("threeLayer") or {}
    if not evidence.get("enabled"):
        return {"enabled": False, "version": VERSION, "reason": "no structured three-layer evidence"}

    layer_scores: dict[str, dict[str, float]] = {}
    item_scores: dict[str, dict[str, dict[str, float]]] = {}
    missing: list[str] = []
    total_items = sum(len(items) for items in ITEMS.values()) * 2
    present = 0
    for layer, items in ITEMS.items():
        layer_scores[layer] = {}
        item_scores[layer] = {}
        source_layer = evidence.get(layer) or {}
        for side in ("home", "away"):
            item_scores[layer][side] = {}
            side_values = source_layer.get(side) or {}
            for item in items:
                score, is_present = _score(side_values.get(item))
                item_scores[layer][side][item] = round(score, 2)
                if is_present:
                    present += 1
                else:
                    missing.append(f"{layer}.{side}.{item}")
            layer_scores[layer][side] = round(
                sum(item_scores[layer][side].values()) / len(items), 2
            )

    home_total = sum(WEIGHTS[layer] * layer_scores[layer]["home"] for layer in WEIGHTS)
    away_total = sum(WEIGHTS[layer] * layer_scores[layer]["away"] for layer in WEIGHTS)
    caution = float(evidence.get("drawCaution", 0.0) or 0.0)
    probabilities = _probabilities(home_total, away_total, max(0.0, min(0.10, caution)))
    completeness = round(present / total_items, 4) if total_items else 0.0
    confidence_penalty = -round((1.0 - completeness) * 12)
    return {
        "enabled": True,
        "version": VERSION,
        "weights": WEIGHTS,
        "itemScores": item_scores,
        "layerScores": layer_scores,
        "totalScores": {"home": round(home_total, 2), "away": round(away_total, 2)},
        "probabilities": probabilities,
        "dataCompleteness": completeness,
        "confidencePenalty": confidence_penalty,
        "missingItems": missing,
        "drawCaution": round(caution, 4),
        "method": "hard strength 40% + tactical matchup 35% + psychological state 25%; missing items use neutral 50",
    }
