"""Settle the 14 August 2026 Sporttery business-day board and review parlays."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATE = "20260814"

# 90-minute scores cross-checked against public league scoreboards.
RESULTS = {
    "2040843": "1-3", "2040844": "1-3", "2040845": "0-1", "2040846": "2-2",
    "2040847": "2-1", "2040848": "3-0", "2040849": "2-1", "2040850": "4-2",
    "2040858": "4-2", "2040851": "1-3", "2040852": "0-1", "2040853": "2-0",
    "2040854": "0-0", "2040855": "1-0", "2040856": "3-1", "2040859": "2-2",
    "2040857": "1-3",
}
SOURCE_URL = "https://www.livescore.mobi/football/2026-08-14/?tz=2"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def outcome(score: str) -> str:
    home, away = map(int, score.split("-"))
    return "home" if home > away else "away" if home < away else "draw"


def main() -> None:
    source_path = DATA / f"sporttery_{DATE}_latest.json"
    prediction_path = DATA / f"predictions_{DATE}.json"
    source = read(source_path)
    prediction = read(prediction_path)
    source_by_id = {str(m.get("matchId") or m.get("id")): m for m in source["matches"]}
    prediction_by_id = {str(m.get("matchId") or m.get("id")): m for m in prediction["matches"]}
    if set(source_by_id) != set(RESULTS):
        raise SystemExit(f"source/result mismatch: {set(source_by_id) ^ set(RESULTS)}")

    settled = []
    reviews = []
    for match_id, score in RESULTS.items():
        home, away = map(int, score.split("-"))
        result = {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "public scoreboard cross-check", "url": SOURCE_URL}
        source_by_id[match_id]["result"] = result
        if match_id in prediction_by_id:
            row = prediction_by_id[match_id]
            row["result"] = result
            pool = [row.get("mainScore", ""), *row.get("backupScores", [])]
            total_goal = str(home + away)
            reviews.append({
                "matchId": match_id, "matchNumStr": row.get("matchNumStr", match_id),
                "home": row.get("home"), "away": row.get("away"), "score": score,
                "direction": outcome(score), "directionHit": row.get("direction") == outcome(score),
                "totalGoals": total_goal, "totalGoalsHit": str(row.get("totalGoals", "")) == total_goal,
                "mainScore": row.get("mainScore", ""), "mainHit": row.get("mainScore") == score,
                "poolHit": score in pool,
                "whyMissed": "爆冷/大球或低比分尾部未进入主线" if not (score in pool) else "比分池覆盖",
            })
        settled.append({"date": DATE, "matchId": match_id, "score": score, "source": "public scoreboard cross-check", "url": SOURCE_URL})

    write(DATA / f"settled_results_{DATE}_manual.json", {"settlementBasis": "90-minute result", "source": "LiveScore public scoreboard cross-check", "results": settled})
    write(source_path, source)
    write(prediction_path, prediction)

    by_league = defaultdict(list)
    for row in reviews:
        by_league[prediction_by_id[row["matchId"]].get("league", "unknown")].append(row)
    review_leagues = []
    for league, rows in sorted(by_league.items()):
        review_leagues.append({"league": league, "results": rows, "summary": f"方向 {sum(r['directionHit'] for r in rows)}/{len(rows)}；总进球 {sum(r['totalGoalsHit'] for r in rows)}/{len(rows)}；主比分 {sum(r['mainHit'] for r in rows)}/{len(rows)}；比分池 {sum(r['poolHit'] for r in rows)}/{len(rows)}", "modelAdjustment": "低置信场次不再重复堆入串关；总进球主线必须保留2球/3球保护，爆冷只作独立尾部，不与多个高波动腿叠加。"})
    review = {
        "reviewDate": DATE, "source": "LiveScore public scoreboard cross-check", "settlementBasis": "90-minute result",
        "allBoardResults": settled, "results": reviews, "reviews": review_leagues,
        "summary": f"看板覆盖 {len(reviews)}/{len(RESULTS)} 场；方向 {sum(r['directionHit'] for r in reviews)}/{len(reviews)}；总进球 {sum(r['totalGoalsHit'] for r in reviews)}/{len(reviews)}；主比分 {sum(r['mainHit'] for r in reviews)}/{len(reviews)}；比分池 {sum(r['poolHit'] for r in reviews)}/{len(reviews)}。",
        "parlayFailure": "昨日串关反复使用芬超/荷甲/瑞超等低置信总进球和半全场腿，且多腿共享同一市场偏差；证据门禁已标记blocked但未阻止展示，导致正常大球与爆冷路径同时失效。修正为按独立证据筛选，最多保留一条爆冷腿，混合串不把高赔率当作信心。",
        "modelAdjustment": "滚动校准采用保守收缩；扩大强队小胜与2-2/1-1保护，保留大球尾部但不追随单日大球；组合选择增加evidenceGate与最低概率约束。",
        "sources": [{"name": "LiveScore 2026-08-14 results", "url": SOURCE_URL}],
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
    }
    write(DATA / f"review_{DATE}_competitions.json", review)
    print(json.dumps({"board": len(RESULTS), "predictions": len(reviews), "direction": sum(r["directionHit"] for r in reviews), "totalGoals": sum(r["totalGoalsHit"] for r in reviews), "mainScore": sum(r["mainHit"] for r in reviews), "scorePool": sum(r["poolHit"] for r in reviews)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
