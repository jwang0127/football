"""Settle the 3 August 2026 board and record a multidimensional review."""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
sys.path.insert(0, str(Path(__file__).resolve().parent))

RESULTS = [
    {"matchId": "2040701", "score": "3-0", "sourceUrl": "https://www.sofascore.com/pt/football/match/sjk-hjk/RUsVXi"},
    {"matchId": "2040702", "score": "0-2", "sourceUrl": "https://www.sofascore.com/sv/football/match/ik-sirius-halmstads-bk/rKsTK"},
    {"matchId": "2040703", "score": "6-0", "sourceUrl": "https://www.sofascore.com/football/match/vasteras-sk-djurgardens-if/jKsAK"},
    {"matchId": "2040704", "score": "2-0", "sourceUrl": "https://www.cbf.com.br/futebol-brasileiro/jogos/copa-do-brasil/profissional/2026/athletico-paranaense-x-vitoria/834854"},
]

MISS_LESSONS = {
    "2040701": "原预测客胜、1-2；未识别主队主场人工草与HJK赛程/阵容状态的实际劣势，且把芬超近期客胜先验权重放得过高；3-0说明强度与主场情境应压过低比分保护。",
    "2040702": "原预测客胜、1-2；方向正确但主比分未中。天狼星联赛排名和不败趋势支持客胜，哈尔姆斯塔德进攻端弱；应把0-1/0-2的零封路径前移，而非只保留1-2。",
    "2040703": "原预测主胜、2-1；方向正确但主比分未中。佐加顿斯主场、实力和高位压迫兑现，韦斯特罗斯防线承压；模型对强弱差上限和半场领先后的扩大比分估计不足。",
    "2040704": "原预测主胜、2-0；方向与主比分均命中。杯赛首回合主场、晋级路径和防守控制逻辑有效；保留杯赛主场零封基线，但需继续核验伤停、裁判和第二回合策略。",
}

def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def direction(score: str) -> str:
    h, a = (int(x) for x in score.split("-"))
    return "home" if h > a else "away" if h < a else "draw"

def main() -> None:
    by_id = {row["matchId"]: row for row in RESULTS}
    source_path = DATA / "sporttery_20260803_latest.json"
    prediction_path = DATA / "predictions_20260803.json"
    source = read(source_path)
    predictions = read(prediction_path)
    source_matches = {str(row.get("matchId") or row.get("id")): row for row in source["matches"]}
    prediction_matches = {str(row.get("id") or row.get("matchId")): row for row in predictions["matches"]}
    if set(prediction_matches) != set(by_id):
        raise SystemExit(f"published board mismatch: predictions={set(prediction_matches)} results={set(by_id)}")

    review_rows = []
    for match_id, result in by_id.items():
        h, a = (int(x) for x in result["score"].split("-"))
        settled = {"homeGoals": h, "awayGoals": a, "status": "Finished", "source": "Sofascore / CBF public result cross-check"}
        source_matches[match_id]["result"] = settled
        prediction_matches[match_id]["result"] = settled
        prediction = prediction_matches[match_id]
        pool = [prediction.get("mainScore", ""), *prediction.get("backupScores", [])]
        actual = direction(result["score"])
        review_rows.append({
            "matchId": match_id, "matchNumStr": prediction["matchNumStr"], "league": prediction["league"],
            "home": prediction["home"], "away": prediction["away"], "score": result["score"],
            "direction": actual, "directionHit": prediction.get("direction") == actual,
            "mainScore": prediction.get("mainScore", ""), "mainHit": prediction.get("mainScore") == result["score"],
            "poolHit": result["score"] in pool, "whyMissed": MISS_LESSONS[match_id],
            "dimensionAudit": {
                "strength": "需提高强弱差与主场实力的非赔率权重" if match_id in {"2040701", "2040703"} else "已纳入或待保持",
                "injuries": "赛前未取得可核验伤停，不能强行修正" ,
                "referee": "未取得可核验裁判执法倾向，保持中性",
                "homeAway": "人工草/主场压迫与客场适应需单独建特征" if match_id == "2040701" else "主客场因素需和近期表现联合使用",
                "motivationOrPromotion": "杯赛首回合需增加晋级路径、领先后控节奏与零封权重" if match_id == "2040704" else "联赛积分动机与比赛阶段需核验",
            },
        })
    write(source_path, source)
    write(prediction_path, predictions)
    write(DATA / "settled_results_20260803_manual.json", {"settlementBasis": "90-minute result", "source": "Sofascore / CBF public result cross-check", "results": [{**row, "matchNumStr": prediction_matches[row["matchId"]]["matchNumStr"], "league": prediction_matches[row["matchId"]]["league"]} for row in RESULTS]})

    by_league = defaultdict(list)
    for row in review_rows:
        by_league[row["league"]].append(row)
    reviews = [{
        "league": league, "results": rows,
        "summary": f"方向命中 {sum(x['directionHit'] for x in rows)}/{len(rows)}；主比分命中 {sum(x['mainHit'] for x in rows)}/{len(rows)}；比分池命中 {sum(x['poolHit'] for x in rows)}/{len(rows)}。",
        "modelAdjustment": "提高实力差、主客场、近期状态和比赛动机的情境闸门；证据缺失时降置信度，不再用赔率低位或单一低比分先验替代球队信息。",
    } for league, rows in sorted(by_league.items())]
    write(DATA / "review_20260803_competitions.json", {
        "reviewDate": "20260803", "source": "Sofascore / CBF public result cross-check", "reviews": reviews,
        "results": review_rows,
        "summary": f"方向命中 {sum(x['directionHit'] for x in review_rows)}/{len(review_rows)}；主比分命中 {sum(x['mainHit'] for x in review_rows)}/{len(review_rows)}；比分池命中 {sum(x['poolHit'] for x in review_rows)}/{len(review_rows)}。",
        "modelLessons": [
            "强主场+明显实力差：提高主队大胜和零封尾部，避免被低比分保护锁死。",
            "客胜且对手进攻弱：0-1/0-2应进入主比分或前两备选，不只用1-2。",
            "伤停、裁判、赛程、战意无可核验来源时必须显式标记缺失并降权，不能伪造信息。",
            "杯赛首回合：单独建晋级路径与领先后节奏特征，90分钟结果和最终晋级分开。",
        ],
        "sources": [{"name": row["matchId"], "url": row["sourceUrl"]} for row in RESULTS],
    })

    from daily_automation import optimize_models
    optimize_models()
    print(json.dumps({"matches": len(review_rows), "direction": sum(x["directionHit"] for x in review_rows), "mainScore": sum(x["mainHit"] for x in review_rows), "scorePool": sum(x["poolHit"] for x in review_rows), "leagues": {k: len(v) for k, v in sorted(by_league.items())}}, ensure_ascii=False))

if __name__ == "__main__":
    main()
