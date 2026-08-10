"""Persist the cross-checked 2026-08-09 90-minute results."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = {
    "2040773": "1-1", "2040774": "2-1", "2040799": "2-0",
    "2040775": "0-1", "2040800": "1-1", "2040776": "3-0",
    "2040777": "3-0", "2040778": "1-1", "2040779": "2-0",
    "2040780": "1-2", "2040781": "0-2", "2040782": "0-0",
    "2040783": "0-2", "2040784": "3-2", "2040785": "2-2",
    "2040786": "1-1", "2040787": "0-1", "2040788": "2-0",
    "2040789": "2-1", "2040801": "2-2", "2040790": "1-0",
    "2040791": "2-2", "2040792": "0-2", "2040793": "2-0",
}
SOURCES = [
    {"name": "Soccer Base 2026-08-09 results", "url": "https://www.soccerbase.com/matches/results.sd?date=2026-08-09"},
    {"name": "J.League official schedule/results", "url": "https://www.jleague.jp/match/search/all/aug/kawasakif/"},
    {"name": "Sporttery official odds snapshot", "url": "https://m.sporttery.cn/mjc/jsq/zqzjq/"},
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def result(score: str) -> dict:
    home, away = (int(x) for x in score.split("-"))
    return {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "Soccer Base / J.League public cross-check", "urls": [x["url"] for x in SOURCES]}


def update(path: Path) -> None:
    payload = load(path)
    for match in payload.get("matches", []):
        match_id = str(match.get("matchId") or match.get("id"))
        if match_id in RESULTS:
            match["result"] = result(RESULTS[match_id])
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    for name in ("data/sporttery_20260809_latest.json", "data/predictions_20260809.json"):
        path = ROOT / name
        if path.exists():
            update(path)
    settled = [{"date": "20260809", "matchId": mid, "score": score, "source": SOURCES[0]["name"], "url": SOURCES[0]["url"]} for mid, score in RESULTS.items()]
    (ROOT / "data/settled_results_20260809_manual.json").write_text(json.dumps({"settlementBasis": "90-minute result", "source": "public scoreboard cross-check", "results": settled}, ensure_ascii=False, indent=2), encoding="utf-8")

    predictions = load(ROOT / "data/predictions_20260809.json")
    by_id = {str(m.get("matchId") or m.get("id")): m for m in predictions["matches"]}
    rows = []
    for mid, score in RESULTS.items():
        m = by_id[mid]
        home, away = (int(x) for x in score.split("-"))
        actual = "home" if home > away else "away" if home < away else "draw"
        pool = [m["mainScore"], *m.get("backupScores", [])]
        rows.append({"matchId": mid, "matchNumStr": m["matchNumStr"], "league": m["league"], "home": m["home"], "away": m["away"], "score": score, "predictedDirection": m["direction"], "direction": actual, "directionHit": m["direction"] == actual, "mainScore": m["mainScore"], "mainHit": m["mainScore"] == score, "poolHit": score in pool, "assessment": "方向命中" if m["direction"] == actual else "方向未命中；实际赛果偏离主路径"})
    by_league = []
    for league in sorted({r["league"] for r in rows}):
        group = [r for r in rows if r["league"] == league]
        by_league.append({"league": league, "results": group, "summary": f"方向命中 {sum(r['directionHit'] for r in group)}/{len(group)}；主比分命中 {sum(r['mainHit'] for r in group)}/{len(group)}；比分池命中 {sum(r['poolHit'] for r in group)}/{len(group)}。", "modelAdjustment": "纳入滚动校准；本日小样本仅做轻量收缩，不追逐单日异常。"})
    review = {"reviewDate": "20260809", "source": "Soccer Base / J.League public cross-check", "sources": SOURCES, "reviews": by_league, "results": rows, "summary": f"方向命中 {sum(r['directionHit'] for r in rows)}/{len(rows)}；主比分命中 {sum(r['mainHit'] for r in rows)}/{len(rows)}；比分池命中 {sum(r['poolHit'] for r in rows)}/{len(rows)}。", "globalLesson": "昨日最主要的问题不是完全看错强弱，而是把市场主路径过早收缩成单一精确比分：平局与主客反转尾部覆盖不足，且德乙、芬超、挪超的实际低比分/客胜路径被主选压掉。模型只按滚动样本轻量收缩，并提高基本面核验、平局保护和比分池分散度；不因一天的赛果大幅改参数。"}
    (ROOT / "data/review_20260809_competitions.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"settled": len(RESULTS), "review": review["summary"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
