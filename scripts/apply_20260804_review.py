from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))

RESULTS = {
    "2040716": "0-1",
    "2040727": "1-2",
    "2040728": "0-0",
    "2040720": "3-3",
    "2040721": "2-1",
}

LESSONS = {
    "2040716": "方向与主比分均命中；巴西杯首回合继续保留客胜与低比分零封路径。",
    "2040727": "原预测主胜 2-1，实际客胜 1-2；欧冠资格赛不能仅按主场和瑞超近期表现锁定主胜，应提高实力差、客队反击与零封客胜路径。",
    "2040728": "原预测主胜 2-0，实际 0-0；杯赛资格赛主场强势不等于高置信主胜，双方首回合应保留低比分平局与僵持路径。",
    "2040720": "原预测主胜 2-1，实际 3-3；两回合淘汰赛首回合需提高开放比赛、双方进球及高总进球尾部风险，不能只保留主胜小比分。",
    "2040721": "原预测客胜 1-2，实际主胜 2-1；欧冠资格赛主场与首回合节奏的权重不足，强队客场不应压过主场反向路径。",
}

def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def direction(score: str) -> str:
    home, away = map(int, score.split("-"))
    return "home" if home > away else "away" if home < away else "draw"

def main() -> None:
    source_path = DATA / "sporttery_20260804_latest.json"
    prediction_path = DATA / "predictions_20260804.json"
    source = read(source_path)
    predictions = read(prediction_path)
    source_by_id = {str(m.get("matchId") or m.get("id")): m for m in source["matches"]}
    prediction_by_id = {str(m.get("matchId") or m.get("id")): m for m in predictions["matches"]}
    if set(source_by_id) != set(RESULTS) or set(prediction_by_id) != set(RESULTS):
        raise SystemExit("0804 board/result ids do not match")

    rows = []
    for match_id, score in RESULTS.items():
        home, away = map(int, score.split("-"))
        settled = {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "public result cross-check"}
        source_by_id[match_id]["result"] = settled
        prediction_by_id[match_id]["result"] = settled
        prediction = prediction_by_id[match_id]
        pool = [prediction.get("mainScore", ""), *(prediction.get("backupScores") or [])]
        rows.append({
            "matchId": match_id,
            "matchNumStr": prediction.get("matchNumStr", match_id),
            "league": prediction.get("league"),
            "home": prediction.get("home"),
            "away": prediction.get("away"),
            "score": score,
            "direction": direction(score),
            "directionHit": prediction.get("direction") == direction(score),
            "mainScore": prediction.get("mainScore", ""),
            "mainHit": prediction.get("mainScore") == score,
            "poolHit": score in pool,
            "whyMissed": LESSONS[match_id],
        })

    write(source_path, source)
    write(prediction_path, predictions)
    write(DATA / "settled_results_20260804_manual.json", {
        "settlementBasis": "90-minute result",
        "source": "public result cross-check",
        "results": [{"matchId": key, "score": value} for key, value in RESULTS.items()],
    })
    by_league = defaultdict(list)
    for row in rows:
        by_league[row["league"]].append(row)
    reviews = []
    for league, league_rows in sorted(by_league.items()):
        reviews.append({
            "league": league,
            "results": league_rows,
            "summary": f"方向命中 {sum(x['directionHit'] for x in league_rows)}/{len(league_rows)}；主比分命中 {sum(x['mainHit'] for x in league_rows)}/{len(league_rows)}；比分池命中 {sum(x['poolHit'] for x in league_rows)}/{len(league_rows)}",
            "modelAdjustment": "仅将本次 90 分钟结果纳入滚动校准；资格赛小样本收缩，不因单日结果大幅改参。",
        })
    write(DATA / "review_20260804_competitions.json", {
        "reviewDate": "20260804",
        "source": "public result cross-check",
        "reviews": reviews,
        "results": rows,
        "modelLessons": [
            "欧冠资格赛首回合同时提高主场、实力差、平局和开放比赛的条件化分支，避免单一主胜锁定。",
            "客队实力与反击得到市场支持时，0-1/1-2/零封客胜必须进入前两位或尾部保护。",
            "两回合首回合的 0-0/低比分与 3-3/高比分是不同比赛状态，按盘口和比赛动机分别保留，不追随单一总进球先验。",
        ],
    })

    from daily_automation import optimize_models
    optimize_models()
    print(json.dumps({
        "matches": len(rows),
        "direction": sum(x["directionHit"] for x in rows),
        "mainScore": sum(x["mainHit"] for x in rows),
        "scorePool": sum(x["poolHit"] for x in rows),
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
