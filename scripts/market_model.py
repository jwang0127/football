"""Shared market-probability toolkit for the prediction pipeline.

This module upgrades three places where the daily scripts previously used
ad-hoc arithmetic on raw odds:

1. De-vigging.  Proportional normalisation (``p ∝ 1/odds``) keeps the
   bookmaker's favourite–longshot bias: longshots stay over-priced after
   normalising.  ``implied_probabilities`` supports the *power* method
   (solve ``sum((1/o_i)^k) = 1``), which compresses longshot mass toward
   zero and is the standard low-cost correction for multi-outcome pools
   such as the correct-score matrix.

2. A coherent scoreline model.  ``fit_scoreline_model`` fits a
   Dixon-Coles adjusted Poisson model (lambda_home, lambda_away, rho) to
   the de-vigged correct-score matrix, including the ``homeOther`` /
   ``drawOther`` / ``awayOther`` aggregate buckets that the raw scripts
   ignored.  Direction, total-goals, exact-score and half/full-time
   probabilities can then all be derived from one joint distribution
   instead of four独立 heuristics that may contradict each other.

3. Half/full-time probabilities.  Derived from the fitted per-half goal
   rates (roughly 45% of goals fall before the break), replacing the old
   "totals<=2 means draw at half time" rule.

Everything is standard-library only so the scripts keep running on the
original Windows environment without extra dependencies.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Iterable

# Empirical share of goals scored before half time across major leagues.
FIRST_HALF_GOAL_SHARE = 0.45
# Cells fitted / reported for the full-time score grid.
MAX_GOALS = 8

__all__ = [
    "implied_probabilities",
    "expected_value",
    "fit_scoreline_model",
    "ScorelineModel",
    "FIRST_HALF_GOAL_SHARE",
]


def _to_float(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def implied_probabilities(odds: dict[str, Any], keys: Iterable[str] | None = None,
                          method: str = "power") -> dict[str, float]:
    """De-vig a market into probabilities that sum to one.

    ``keys`` restricts which entries are treated as outcomes (otherwise every
    numeric value except ``updatedAt`` counts).  ``method`` is ``"power"``
    (default, corrects favourite–longshot bias) or ``"proportional"``.
    """
    if keys is None:
        keys = [key for key in odds if key != "updatedAt"]
    inverse = {}
    for key in keys:
        price = _to_float(odds.get(key))
        if price and price > 1.0:
            inverse[key] = 1.0 / price
    if not inverse:
        return {}
    overround = sum(inverse.values())
    if method == "proportional" or overround <= 1.0 or len(inverse) < 2:
        return {key: value / overround for key, value in inverse.items()}
    # Power method: p_i = (1/o_i)^k with k solved so the mass is exactly one.
    lo, hi = 1.0, 6.0
    for _ in range(60):
        mid = (lo + hi) / 2
        mass = sum(value ** mid for value in inverse.values())
        if mass > 1.0:
            lo = mid
        else:
            hi = mid
    k = (lo + hi) / 2
    powered = {key: value ** k for key, value in inverse.items()}
    total = sum(powered.values())
    return {key: value / total for key, value in powered.items()}


def expected_value(probability: float | None, odds: float | None) -> float | None:
    """Return the expected profit per unit stake, or None when unpriceable."""
    if not probability or not odds:
        return None
    return round(probability * odds - 1.0, 4)


def _dixon_coles_tau(home: int, away: int, lam: float, mu: float, rho: float) -> float:
    if home == 0 and away == 0:
        return 1.0 - lam * mu * rho
    if home == 1 and away == 0:
        return 1.0 + mu * rho
    if home == 0 and away == 1:
        return 1.0 + lam * rho
    if home == 1 and away == 1:
        return 1.0 - rho
    return 1.0


def _poisson_row(lam: float, size: int) -> list[float]:
    probs = [math.exp(-lam)]
    for i in range(1, size + 1):
        probs.append(probs[-1] * lam / i)
    return probs


def _score_grid(lam: float, mu: float, rho: float, max_goals: int = MAX_GOALS) -> dict[tuple[int, int], float]:
    home_row = _poisson_row(lam, max_goals)
    away_row = _poisson_row(mu, max_goals)
    grid = {}
    for home in range(max_goals + 1):
        for away in range(max_goals + 1):
            value = home_row[home] * away_row[away] * _dixon_coles_tau(home, away, lam, mu, rho)
            grid[(home, away)] = max(value, 1e-12)
    total = sum(grid.values())
    return {cell: value / total for cell, value in grid.items()}


def _rho_bounds(lam: float, mu: float) -> tuple[float, float]:
    lo = max(-1.0 / lam if lam else -1.0, -1.0 / mu if mu else -1.0, -0.9)
    hi = min(1.0 / (lam * mu) if lam * mu else 1.0, 0.9)
    # Keep tau factors strictly positive.
    return lo * 0.95, hi * 0.95


def _nelder_mead(objective: Callable[[list[float]], float], start: list[float],
                 step: float = 0.25, iterations: int = 220) -> list[float]:
    """Tiny dependency-free Nelder-Mead for the 3-parameter scoreline fit."""
    dim = len(start)
    simplex = [list(start)]
    for i in range(dim):
        point = list(start)
        point[i] += step
        simplex.append(point)
    values = [objective(p) for p in simplex]
    for _ in range(iterations):
        order = sorted(range(len(simplex)), key=lambda i: values[i])
        simplex = [simplex[i] for i in order]
        values = [values[i] for i in order]
        if abs(values[-1] - values[0]) < 1e-9:
            break
        centroid = [sum(p[i] for p in simplex[:-1]) / dim for i in range(dim)]
        worst = simplex[-1]
        reflect = [centroid[i] + (centroid[i] - worst[i]) for i in range(dim)]
        reflect_value = objective(reflect)
        if reflect_value < values[0]:
            expand = [centroid[i] + 2 * (centroid[i] - worst[i]) for i in range(dim)]
            expand_value = objective(expand)
            if expand_value < reflect_value:
                simplex[-1], values[-1] = expand, expand_value
            else:
                simplex[-1], values[-1] = reflect, reflect_value
        elif reflect_value < values[-2]:
            simplex[-1], values[-1] = reflect, reflect_value
        else:
            contract = [centroid[i] + 0.5 * (worst[i] - centroid[i]) for i in range(dim)]
            contract_value = objective(contract)
            if contract_value < values[-1]:
                simplex[-1], values[-1] = contract, contract_value
            else:
                best = simplex[0]
                for idx in range(1, len(simplex)):
                    simplex[idx] = [best[i] + 0.5 * (simplex[idx][i] - best[i]) for i in range(dim)]
                    values[idx] = objective(simplex[idx])
    order = sorted(range(len(simplex)), key=lambda i: values[i])
    return simplex[order[0]]


class ScorelineModel:
    """Dixon-Coles adjusted Poisson scoreline distribution."""

    def __init__(self, lambda_home: float, lambda_away: float, rho: float,
                 kl_divergence: float = 0.0, max_goals: int = MAX_GOALS):
        self.lambda_home = lambda_home
        self.lambda_away = lambda_away
        self.rho = rho
        self.kl_divergence = kl_divergence
        self.max_goals = max_goals
        self.matrix = _score_grid(lambda_home, lambda_away, rho, max_goals)

    def outcome_probabilities(self) -> dict[str, float]:
        out = {"home": 0.0, "draw": 0.0, "away": 0.0}
        for (home, away), value in self.matrix.items():
            out["home" if home > away else "away" if home < away else "draw"] += value
        return out

    def total_goal_probabilities(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for (home, away), value in self.matrix.items():
            key = "7+" if home + away >= 7 else str(home + away)
            out[key] = out.get(key, 0.0) + value
        return out

    def score_probability(self, score: str) -> float:
        try:
            home, away = (int(x) for x in score.split("-"))
        except (ValueError, AttributeError):
            return 0.0
        return self.matrix.get((home, away), 0.0)

    def score_probabilities(self, scores: Iterable[str]) -> dict[str, float]:
        """Model probabilities renormalised over an offered score list."""
        raw = {score: self.score_probability(score) for score in scores}
        total = sum(raw.values())
        return {key: value / total for key, value in raw.items()} if total else raw

    def half_full_probabilities(self, first_half_share: float = FIRST_HALF_GOAL_SHARE) -> dict[str, float]:
        """Half-time/full-time distribution from per-half goal rates.

        Halves are treated as independent Poisson processes (the small
        Dixon-Coles correction is a full-time-only effect and would break
        the factorisation), which is accurate enough for pool ranking.
        """
        half_goals = 6
        first_home = _poisson_row(self.lambda_home * first_half_share, half_goals)
        first_away = _poisson_row(self.lambda_away * first_half_share, half_goals)
        second_home = _poisson_row(self.lambda_home * (1 - first_half_share), half_goals)
        second_away = _poisson_row(self.lambda_away * (1 - first_half_share), half_goals)
        letter = {"home": "h", "draw": "d", "away": "a"}
        out = {first + full: 0.0 for first in "hda" for full in "hda"}
        for h1 in range(half_goals + 1):
            for a1 in range(half_goals + 1):
                first_probability = first_home[h1] * first_away[a1]
                half = "home" if h1 > a1 else "away" if h1 < a1 else "draw"
                for h2 in range(half_goals + 1):
                    for a2 in range(half_goals + 1):
                        total_home, total_away = h1 + h2, a1 + a2
                        full = "home" if total_home > total_away else "away" if total_home < total_away else "draw"
                        out[letter[half] + letter[full]] += first_probability * second_home[h2] * second_away[a2]
        total = sum(out.values())
        return {key: value / total for key, value in out.items()}

    def summary(self) -> dict[str, float]:
        return {
            "lambdaHome": round(self.lambda_home, 3),
            "lambdaAway": round(self.lambda_away, 3),
            "rho": round(self.rho, 3),
            "klDivergence": round(self.kl_divergence, 4),
        }


def _parse_cells(score_probs: dict[str, float]) -> tuple[dict[tuple[int, int], float], dict[str, float]]:
    cells: dict[tuple[int, int], float] = {}
    buckets: dict[str, float] = {}
    for key, probability in score_probs.items():
        if probability <= 0:
            continue
        if key in ("homeOther", "drawOther", "awayOther"):
            buckets[key.removesuffix("Other")] = probability
            continue
        try:
            home, away = (int(x) for x in str(key).split("-"))
        except ValueError:
            continue
        cells[(home, away)] = probability
    return cells, buckets


def fit_scoreline_model(score_probs: dict[str, float], max_goals: int = MAX_GOALS) -> ScorelineModel | None:
    """Fit lambda/mu/rho to a de-vigged score distribution.

    ``score_probs`` maps ``"h-a"`` scores (plus optional ``homeOther`` /
    ``drawOther`` / ``awayOther`` aggregate buckets) to probabilities.  The
    fit minimises the cross-entropy between the market distribution and the
    model restricted to the same cells, so the ``Other`` buckets anchor the
    tail mass the listed scores leave out.
    """
    cells, buckets = _parse_cells(score_probs)
    if len(cells) < 4:
        return None
    listed_mass = sum(cells.values())
    bucket_mass = sum(buckets.values())
    total_mass = listed_mass + bucket_mass
    if total_mass <= 0:
        return None

    start_home = sum(home * p for (home, _), p in cells.items()) / listed_mass
    start_away = sum(away * p for (_, away), p in cells.items()) / listed_mass
    start = [math.log(max(start_home, 0.15)), math.log(max(start_away, 0.15)), 0.0]

    def decode(params: list[float]) -> tuple[float, float, float]:
        lam = min(math.exp(params[0]), 6.0)
        mu = min(math.exp(params[1]), 6.0)
        lo, hi = _rho_bounds(lam, mu)
        rho = lo + (hi - lo) / (1.0 + math.exp(-params[2]))
        return lam, mu, rho

    def objective(params: list[float]) -> float:
        lam, mu, rho = decode(params)
        grid = _score_grid(lam, mu, rho, max_goals)
        cost = 0.0
        for cell, probability in cells.items():
            cost -= probability / total_mass * math.log(grid.get(cell, 1e-12))
        if buckets:
            residual = {"home": 0.0, "draw": 0.0, "away": 0.0}
            for (home, away), value in grid.items():
                if (home, away) in cells:
                    continue
                residual["home" if home > away else "away" if home < away else "draw"] += value
            for key, probability in buckets.items():
                cost -= probability / total_mass * math.log(max(residual.get(key, 0.0), 1e-12))
        return cost

    best = _nelder_mead(objective, start)
    lam, mu, rho = decode(best)
    entropy = 0.0
    for probability in list(cells.values()) + list(buckets.values()):
        share = probability / total_mass
        entropy -= share * math.log(share)
    kl = max(0.0, objective(best) - entropy)
    return ScorelineModel(lam, mu, rho, kl_divergence=kl, max_goals=max_goals)
