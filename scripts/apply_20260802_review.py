#!/usr/bin/env python3
"""Apply the verified 2 August review for the published 12-match board."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))


RESULTS = [
    {"matchId": "2040688", "score": "3-1", "sourceUrl": "https://www.fotmob.com/matches/ulsan-hd-fc-vs-fc-anyang/20w6nu1w"},
    {"matchId": "2040689", "score": "3-3", "sourceUrl": "https://www.fotmob.com/matches/incheon-united-vs-jeju-sk/gh07y5f"},
    {"matchId": "2040690", "score": "2-0", "sourceUrl": "https://www.fotmob.com/matches/daejeon-hana-citizen-vs-gwangju-fc/x4u63k4"},
    {"matchId": "2040691", "score": "2-1", "sourceUrl": "https://site.api.espn.com/apis/site/v2/sports/soccer/swe.1/scoreboard?dates=20260802"},
    {"matchId": "2040692", "score": "0-2", "sourceUrl": "https://site.api.espn.com/apis/site/v2/sports/soccer/swe.1/scoreboard?dates=20260802"},
    {"matchId": "2040693", "score": "0-1", "sourceUrl": "https://www.fotmob.com/matches/fc-inter-turku-vs-sirius/1g81e4"},
    {"matchId": "2040694", "score": "1-0", "sourceUrl": "https://www.fotmob.com/matches/ac-oulu-vs-ilves/6di10jr"},
    {"matchId": "2040695", "score": "3-0", "sourceUrl": "https://site.api.espn.com/apis/site/v2/sports/soccer/swe.1/scoreboard?dates=20260802"},
    {"matchId": "2040696", "score": "1-2", "sourceUrl": "https://site.api.espn.com/apis/site/v2/sports/soccer/nor.1/scoreboard?dates=20260802"},
    {"matchId": "2040697", "score": "3-3", "sourceUrl": "https://site.api.espn.com/apis/site/v2/sports/soccer/nor.1/scoreboard?dates=20260802"},
    {"matchId": "2040698", "score": "6-2", "sourceUrl": "https://site.api.espn.com/apis/site/v2/sports/soccer/nor.1/scoreboard?dates=20260802"},
    {"matchId": "2040699", "score": "2-3", "sourceUrl": "https://site.api.espn.com/apis/site/v2/sports/soccer/nor.1/scoreboard?dates=20260802"},
]


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def direction(score: str) -> str:
    home, away = (int(value) for value in score.split("-"))
    return "home" if home > away else "away" if home < away else "draw"


def main() -> None:
    by_id = {row["matchId"]: row for row in RESULTS}
    source_path = DATA / "sporttery_20260802_latest.json"
    prediction_path = DATA / "predictions_20260802.json"
    source = read(source_path)
    predictions = read(prediction_path)
    source_matches = {str(row.get("matchId") or row.get("id")): row for row in source["matches"]}
    prediction_matches = {str(row.get("id") or row.get("matchId")): row for row in predictions["matches"]}
    if set(prediction_matches) != set(by_id):
        raise SystemExit(f"published board mismatch: predictions={len(prediction_matches)} results={len(by_id)}")

    review_rows = []
    for match_id, result in by_id.items():
        home, away = (int(value) for value in result["score"].split("-"))
        result_payload = {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "FotMob / ESPN public scoreboard cross-check"}
        source_matches[match_id]["result"] = result_payload
        prediction_matches[match_id]["result"] = result_payload
        prediction = prediction_matches[match_id]
        pool = [prediction.get("mainScore", ""), *prediction.get("backupScores", [])]
        actual = direction(result["score"])
        review_rows.append({
            "matchId": match_id,
            "matchNumStr": prediction["matchNumStr"],
            "league": prediction["league"],
            "home": prediction["home"],
            "away": prediction["away"],
            "score": result["score"],
            "direction": actual,
            "directionHit": prediction.get("direction") == actual,
            "mainScore": prediction.get("mainScore", ""),
            "mainHit": prediction.get("mainScore") == result["score"],
            "poolHit": result["score"] in pool,
        })

    write(source_path, source)
    write(prediction_path, predictions)
    write(DATA / "settled_results_20260802_manual.json", {
        "settlementBasis": "90-minute result",
        "source": "FotMob / ESPN public scoreboard cross-check",
        "results": [
            {**row, "matchNumStr": prediction_matches[row["matchId"]]["matchNumStr"], "league": prediction_matches[row["matchId"]]["league"]}
            for row in RESULTS
        ],
    })

    by_league = defaultdict(list)
    for row in review_rows:
        by_league[row["league"]].append(row)
    reviews = []
    for league, rows in sorted(by_league.items()):
        reviews.append({
            "league": league,
            "results": rows,
            "summary": f"方向命中 {sum(row['directionHit'] for row in rows)}/{len(rows)}；主比分命中 {sum(row['mainHit'] for row in rows)}/{len(rows)}；比分池命中 {sum(row['poolHit'] for row in rows)}/{len(rows)}。",
            "modelAdjustment": "仅纳入滚动校准；继续保留强势方大比分尾部、平局保护和低比分路径，不因单日样本过度改参。",
        })
    write(DATA / "review_20260802_competitions.json", {
        "reviewDate": "20260802",
        "source": "FotMob / ESPN public scoreboard cross-check",
        "reviews": reviews,
        "results": review_rows,
        "summary": f"方向命中 {sum(row['directionHit'] for row in review_rows)}/{len(review_rows)}；主比分命中 {sum(row['mainHit'] for row in review_rows)}/{len(review_rows)}；比分池命中 {sum(row['poolHit'] for row in review_rows)}/{len(review_rows)}。",
        "sources": [{"name": row["matchId"], "url": row["sourceUrl"]} for row in RESULTS],
    })

    from daily_automation import optimize_models
    optimize_models()
    print(json.dumps({
        "matches": len(review_rows),
        "direction": sum(row["directionHit"] for row in review_rows),
        "mainScore": sum(row["mainHit"] for row in review_rows),
        "scorePool": sum(row["poolHit"] for row in review_rows),
        "leagues": {league: len(rows) for league, rows in sorted(by_league.items())},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
