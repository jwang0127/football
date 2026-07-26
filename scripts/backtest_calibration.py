#!/usr/bin/env python3
"""Backtest every archived daily board against verified results.

The daily reviews already record verified scores in three places:

- ``data/predictions_*.json``  → ``matches[].result`` written by the
  apply_*_review scripts;
- ``data/review_*_competitions.json`` → ``reviews[].results[]``;
- ``data/settled_results_*.json`` → ``results[]``.

This script merges them into one result index, replays each frozen daily
board and reports hit rates *and* probability quality (three-way Brier
score and log loss) overall, per competition and per business day, plus a
calibration table (claimed direction probability vs realised frequency).
The output feeds parameter reviews with evidence instead of single-day
anecdotes: a bucket whose realised frequency sits well below its claimed
probability is over-confident and needs shrinking, not a bigger lesson
string.

Usage:  python scripts/backtest_calibration.py [--json data/backtest_report.json]
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DAILY_RE = re.compile(r"predictions_(\d{8})\.json$")
BUCKETS = ((0.0, 0.35), (0.35, 0.45), (0.45, 0.55), (0.55, 0.65), (0.65, 1.01))


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def outcome(home: int, away: int) -> str:
    return "home" if home > away else "away" if home < away else "draw"


def parse_score(score: str) -> tuple[int, int] | None:
    try:
        home, away = (int(x) for x in str(score).replace(":", "-").split("-"))
        return home, away
    except (ValueError, AttributeError):
        return None


def build_result_index() -> dict[str, tuple[int, int]]:
    results: dict[str, tuple[int, int]] = {}

    def add(match_id: Any, score: tuple[int, int] | None) -> None:
        if match_id and score:
            results[str(match_id)] = score

    for path in sorted(DATA.glob("settled_results_*.json")):
        for row in read(path).get("results", []):
            add(row.get("matchId"), parse_score(row.get("score", "")))
    for path in sorted(DATA.glob("review_*_competitions.json")):
        payload = read(path)
        for review in payload.get("reviews", [payload]):
            for row in review.get("results", []):
                add(row.get("matchId"), parse_score(row.get("score", "")))
    for path in sorted(DATA.glob("predictions_*.json")):
        for match in read(path).get("matches", []):
            result = match.get("result") or {}
            if result.get("homeGoals") is not None and result.get("awayGoals") is not None:
                add(match.get("matchId") or match.get("id"), (int(result["homeGoals"]), int(result["awayGoals"])))
    return results


def evaluate(match: dict[str, Any], score: tuple[int, int]) -> dict[str, Any] | None:
    probs = match.get("probabilities") or {}
    direction = match.get("direction")
    main_score = match.get("mainScore")
    if not (direction and main_score and probs):
        return None
    home, away = score
    actual = outcome(home, away)
    pool = list(dict.fromkeys([main_score, *(match.get("backupScores") or [])]))
    actual_text = f"{home}-{away}"
    row = {
        "matchId": str(match.get("matchId") or match.get("id")),
        "league": match.get("league", "未知"),
        "match": f'{match.get("home")} vs {match.get("away")}',
        "actual": actual_text,
        "direction_hit": direction == actual,
        "main_hit": main_score == actual_text,
        "pool_hit": actual_text in pool,
        "goal_hit": str(match.get("totalGoals")) == str(min(home + away, 7)) or (match.get("totalGoals") == "7+" and home + away >= 7),
        "goal_candidates_hit": str(min(home + away, 7)) in [str(x) for x in match.get("goalCandidates") or []] or (home + away >= 7 and "7+" in (match.get("goalCandidates") or [])),
        "claimed_probability": float(probs.get(direction, 0.0)),
        "brier": sum((float(probs.get(key, 0.0)) - (1.0 if key == actual else 0.0)) ** 2 for key in ("home", "draw", "away")),
        "logloss": -math.log(max(float(probs.get(actual, 0.0)), 1e-6)),
    }
    return row


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    if not total:
        return {"settled": 0}
    return {
        "settled": total,
        "direction_rate": round(sum(r["direction_hit"] for r in rows) / total, 4),
        "main_score_rate": round(sum(r["main_hit"] for r in rows) / total, 4),
        "score_pool_rate": round(sum(r["pool_hit"] for r in rows) / total, 4),
        "total_goal_rate": round(sum(r["goal_hit"] for r in rows) / total, 4),
        "goal_candidates_rate": round(sum(r["goal_candidates_hit"] for r in rows) / total, 4),
        "avg_brier": round(sum(r["brier"] for r in rows) / total, 4),
        "avg_logloss": round(sum(r["logloss"] for r in rows) / total, 4),
    }


def calibration_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table = []
    for low, high in BUCKETS:
        bucket = [r for r in rows if low <= r["claimed_probability"] < high]
        if not bucket:
            continue
        table.append({
            "bucket": f"[{low:.2f}, {min(high, 1.0):.2f})",
            "matches": len(bucket),
            "claimed_mean": round(sum(r["claimed_probability"] for r in bucket) / len(bucket), 4),
            "realised_rate": round(sum(r["direction_hit"] for r in bucket) / len(bucket), 4),
        })
    return table


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default=str(DATA / "backtest_report.json"))
    args = parser.parse_args()
    results = build_result_index()
    all_rows: list[dict[str, Any]] = []
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_league: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for path in sorted(DATA.glob("predictions_*.json")):
        matched = DAILY_RE.fullmatch(path.name)
        if not matched:
            continue
        date = matched.group(1)
        for match in read(path).get("matches", []):
            score = results.get(str(match.get("matchId") or match.get("id")))
            if not score:
                continue
            row = evaluate(match, score)
            if not row:
                continue
            row["date"] = date
            all_rows.append(row)
            by_date[date].append(row)
            by_league[row["league"]].append(row)
    report = {
        "settledResults": len(results),
        "evaluatedPredictions": len(all_rows),
        "overall": aggregate(all_rows),
        "calibration": calibration_table(all_rows),
        "byCompetition": {name: aggregate(rows) for name, rows in sorted(by_league.items())},
        "byDate": {date: aggregate(rows) for date, rows in sorted(by_date.items())},
        "note": "avg_brier：三元Brier分，0完美、0.667为均匀基线；calibration把主方向声称概率分桶后对比实际命中频率，claimed_mean明显高于realised_rate说明该区间过度自信。",
    }
    Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    overall = report["overall"]
    print(f"results indexed: {len(results)}, predictions evaluated: {len(all_rows)}")
    if overall.get("settled"):
        print(f"direction {overall['direction_rate']:.1%} | pool {overall['score_pool_rate']:.1%} | goals {overall['total_goal_rate']:.1%} | brier {overall['avg_brier']} | logloss {overall['avg_logloss']}")
    for row in report["calibration"]:
        print(f"claimed {row['bucket']}: mean {row['claimed_mean']:.2f} vs realised {row['realised_rate']:.2f} over {row['matches']} matches")


if __name__ == "__main__":
    main()
