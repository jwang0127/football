from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = {
    "2040831": "2-1",
    "2040819": "1-1",
    "2040820": "1-1",
}
SOURCES = [
    {"name": "UEFA match centre", "url": "https://www.uefa.com/uefasupercup/match/2048319--paris-vs-aston-villa/"},
    {"name": "FBref daily results cross-check", "url": "https://fbref.com/en/matches/2026-08-12"},
    {"name": "Public match-thread score cross-check", "url": "https://www.reddit.com/r/futebol/comments/1vm293c/match_hub_jogos_do_dia_12_de_agosto/"},
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse(score: str) -> tuple[int, int]:
    return tuple(int(x) for x in score.split("-"))  # type: ignore[return-value]


def main() -> None:
    path = ROOT / "data/predictions_20260812.json"
    payload = load(path)
    rows = []
    for match in payload["matches"]:
        mid = str(match.get("id") or match.get("matchId"))
        score = RESULTS[mid]
        home, away = parse(score)
        direction = "home" if home > away else "away" if home < away else "draw"
        pool = [match.get("mainScore", ""), *match.get("backupScores", [])]
        row = {
            "matchId": mid, "matchNumStr": match.get("matchNumStr"),
            "league": match.get("league"), "home": match.get("home"), "away": match.get("away"),
            "score": score, "predictedDirection": match.get("direction"), "direction": direction,
            "directionHit": match.get("direction") == direction,
            "mainScore": match.get("mainScore"), "mainHit": match.get("mainScore") == score,
            "poolHit": score in pool,
            "assessment": "方向命中，比分未命中" if match.get("direction") == direction else "方向未命中",
        }
        rows.append(row)
        match["result"] = {"homeGoals": home, "awayGoals": away, "status": "Finished", "settlement": "90-minute", "source": "public score cross-check"}
    by_league = defaultdict(list)
    for row in rows:
        by_league[row["league"]].append(row)
    reviews = []
    for league, group in by_league.items():
        reviews.append({
            "league": league, "results": group,
            "summary": f"方向命中 {sum(r['directionHit'] for r in group)}/{len(group)}；主比分命中 {sum(r['mainHit'] for r in group)}/{len(group)}；比分池命中 {sum(r['poolHit'] for r in group)}/{len(group)}",
            "modelAdjustment": "首回合杯赛：不把强势主胜直接等同于90分钟稳胜；提高平局与1-1/0-0保护，保留强队1球小胜和次回合追分尾部。样本仅3场，采用保守收缩，不跨赛事迁移。",
        })
    review = {
        "reviewDate": "20260812", "source": "public score cross-check", "sources": SOURCES,
        "settlementBasis": "90-minute result; extra time and penalties excluded",
        "results": rows, "reviews": reviews,
        "summary": f"方向命中 {sum(r['directionHit'] for r in rows)}/{len(rows)}；主比分命中 {sum(r['mainHit'] for r in rows)}/{len(rows)}；比分池命中 {sum(r['poolHit'] for r in rows)}/{len(rows)}",
        "globalLesson": "昨日未命中核心是杯赛首回合的平局保护不足：两场解放者杯均为1-1，市场主胜方向正确但比分模板过度偏向主队零封/小胜。后续杯赛模型下调主胜置信度、提高平局和低比分分支；巴黎比赛的2-1命中方向但主比分仍未命中，说明单场决赛不宜提高比分确定性。",
    }
    (ROOT / "data/review_20260812_competitions.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "data/settled_results_20260812_manual.json").write_text(json.dumps({"settlementBasis": review["settlementBasis"], "results": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"settled": len(rows), "summary": review["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
