from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = {
    "2040811": "0-0",  # Gangwon 0-1 Gamba after extra time; 90-minute settlement is 0-0.
    "2040829": "0-1",
    "2040812": "3-2",
    "2040813": "4-0",
    "2040814": "2-1",
    "2040830": "2-0",
    "2040815": "2-0",
    "2040816": "0-1",
    "2040817": "3-0",
    "2040818": "0-0",
}

SOURCES = [
    {"name": "UEFA/public match reports and scoreboards", "url": "https://www.uefa.com/uefachampionsleague/"},
    {"name": "AFC/J.League public match listings", "url": "https://www.jleague.jp/en/acle/match/"},
    {"name": "CONMEBOL/public match reports", "url": "https://gol.conmebol.com/libertadores/"},
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def result(score: str) -> dict:
    home, away = (int(x) for x in score.split("-"))
    return {"homeGoals": home, "awayGoals": away, "status": "Finished", "settlement": "90-minute", "source": "public score cross-check", "urls": [s["url"] for s in SOURCES]}


def update(path: Path) -> None:
    payload = load(path)
    for match in payload.get("matches", []):
        mid = str(match.get("matchId") or match.get("id"))
        if mid in RESULTS:
            match["result"] = result(RESULTS[mid])
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    for name in ("data/sporttery_20260811_latest.json", "data/predictions_20260811.json"):
        path = ROOT / name
        if path.exists():
            update(path)
    prediction = load(ROOT / "data/predictions_20260811.json")
    rows = []
    for match in prediction["matches"]:
        mid = str(match.get("matchId") or match.get("id"))
        score = RESULTS[mid]
        home, away = (int(x) for x in score.split("-"))
        actual = "home" if home > away else "away" if home < away else "draw"
        pool = [match.get("mainScore", ""), *match.get("backupScores", [])]
        rows.append({"matchId": mid, "matchNumStr": match.get("matchNumStr", mid), "league": match.get("league"), "home": match.get("home"), "away": match.get("away"), "score": score, "predictedDirection": match.get("direction"), "direction": actual, "directionHit": match.get("direction") == actual, "mainScore": match.get("mainScore"), "mainHit": match.get("mainScore") == score, "poolHit": score in pool, "assessment": "方向命中" if match.get("direction") == actual else "方向未命中"})
    reviews = []
    for league in sorted({r["league"] for r in rows}):
        group = [r for r in rows if r["league"] == league]
        reviews.append({"league": league, "results": group, "summary": f"方向命中 {sum(r['directionHit'] for r in group)}/{len(group)}；主比分命中 {sum(r['mainHit'] for r in group)}/{len(group)}；比分池命中 {sum(r['poolHit'] for r in group)}/{len(group)}", "modelAdjustment": "杯赛小样本仅做保守收缩：提高平局/低比分保护，保留次回合领先方控场与尾部客胜路径；不因单日结果大幅改参。"})
    review = {"reviewDate": "20260811", "source": "public score cross-check", "sources": SOURCES, "settlementBasis": "90-minute result; Gangwon-Gamba extra-time result kept separate", "reviews": reviews, "results": rows, "summary": f"方向命中 {sum(r['directionHit'] for r in rows)}/{len(rows)}；主比分命中 {sum(r['mainHit'] for r in rows)}/{len(rows)}；比分池命中 {sum(r['poolHit'] for r in rows)}/{len(rows)}", "globalLesson": "欧冠资格赛未命中主要来自次回合情境权重不足：萨巴赫4-0、里昂3-0和奈梅亨2-1显示主场追分/晋级压力可放大进攻尾部；同时江原-大阪钢巴90分钟平局提醒模型必须分离90分钟结算与加时晋级。优化仅提高杯赛平局、低比分与高动机追分的保护，不把加时赛果倒灌进90分钟模型。"}
    (ROOT / "data/review_20260811_competitions.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"settled": len(rows), "review": review["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
