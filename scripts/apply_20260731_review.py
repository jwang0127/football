#!/usr/bin/env python3
"""Apply the verified 31 July review and refresh rolling calibration."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def direction(score: str) -> str:
    home, away = (int(x) for x in score.split("-"))
    return "home" if home > away else "away" if home < away else "draw"


def main() -> None:
    results = [
        {"matchId": "2040667", "matchNumStr": "周五001", "league": "挪威超级联赛", "score": "0-3", "sourceUrl": "https://site.api.espn.com/apis/site/v2/sports/soccer/nor.1/scoreboard?dates=20260731"},
        {"matchId": "2040668", "matchNumStr": "周五002", "league": "挪威超级联赛", "score": "4-0", "sourceUrl": "https://www.fotball.no/fotballdata/kamp/?fiksId=8986249"},
        {"matchId": "2040669", "matchNumStr": "周五003", "league": "美国职业大联盟", "score": "1-1", "sourceUrl": "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard?dates=20260731"},
    ]
    by_id = {row["matchId"]: row for row in results}
    prediction_path = DATA / "predictions_20260731.json"
    predictions = read(prediction_path)
    review_rows = []
    for match in predictions["matches"]:
        row = by_id[str(match["id"])]
        home, away = (int(x) for x in row["score"].split("-"))
        match["result"] = {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "ESPN/NFF public cross-check"}
        actual = direction(row["score"])
        pool = [match["mainScore"], *match.get("backupScores", [])]
        review_rows.append({
            "matchId": str(match["id"]), "matchNumStr": match["matchNumStr"], "league": match["league"], "home": match["home"], "away": match["away"],
            "score": row["score"], "direction": actual, "directionHit": match["direction"] == actual,
            "mainScore": match["mainScore"], "mainHit": match["mainScore"] == row["score"], "poolHit": row["score"] in pool,
        })
    write(prediction_path, predictions)
    source_path = DATA / "sporttery_20260731_latest.json"
    source = read(source_path)
    for match in source["matches"]:
        row = by_id[str(match["matchId"])]
        home, away = (int(x) for x in row["score"].split("-"))
        match["result"] = {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "ESPN/NFF public cross-check"}
    write(source_path, source)
    write(DATA / "settled_results_20260731_manual.json", {"settlementBasis": "90-minute result", "source": "ESPN/NFF public cross-check", "results": results})

    calibration_path = DATA / "auto_model_calibration.json"
    calibration = read(calibration_path) if calibration_path.exists() else {"competitions": {}}
    model_counts = {}
    for league in ("挪威超级联赛", "美国职业大联盟"):
        rows = [row for row in results if row["league"] == league]
        counts = Counter(direction(row["score"]) for row in rows)
        base = calibration.setdefault("competitions", {}).setdefault(league, {})
        current = base.get("prior_probs", [0.4, 0.3, 0.3])
        blend = min(0.12, len(rows) / (len(rows) + 40))
        empirical = [counts["home"] / len(rows), counts["draw"] / len(rows), counts["away"] / len(rows)]
        adjusted = [round((1 - blend) * old + blend * new, 4) for old, new in zip(current, empirical)]
        base["prior_probs"] = adjusted
        base["version"] = f"{base.get('version', 'rolling')}-review0731"
        base["lesson"] = f"0731复盘：方向命中 {sum(r['directionHit'] for r in review_rows if r['league'] == league)}/{len(rows)}；保留强势方大比分尾部、低比分保护与平局路径，单日小样本仅轻量收缩。"
        model_counts[league] = {"counts": dict(counts), "blend": round(blend, 4), "prior_probs": adjusted}
    for bad_key in ("鎸▉瓒呯骇鑱旇禌", "缇庡浗鑱屼笟澶ц仈鐩?:"):
        calibration.get("competitions", {}).pop(bad_key, None)
    calibration["review0731"] = {"method": "verified 90-minute results; rolling conservative shrinkage", "modelCounts": model_counts, "generatedAt": datetime.now().isoformat(timespec="seconds")}
    write(calibration_path, calibration)

    reviews = []
    for league in ("挪威超级联赛", "美国职业大联盟"):
        rows = [r for r in review_rows if r["league"] == league]
        reviews.append({"league": league, "results": rows, "summary": f"方向命中 {sum(r['directionHit'] for r in rows)}/{len(rows)}；主比分命中 {sum(r['mainHit'] for r in rows)}/{len(rows)}；比分池命中 {sum(r['poolHit'] for r in rows)}/{len(rows)}。", "modelAdjustment": "扩展强势方大比分尾部，同时保留0-0/1-1等低比分保护；不把单日大球机械外推到所有比赛。"})
    write(DATA / "review_20260731_competitions.json", {"reviewDate": "20260731", "source": "ESPN/NFF public cross-check", "reviews": reviews, "results": review_rows, "summary": f"方向命中 {sum(r['directionHit'] for r in review_rows)}/{len(review_rows)}；主比分命中 {sum(r['mainHit'] for r in review_rows)}/{len(review_rows)}；比分池命中 {sum(r['poolHit'] for r in review_rows)}/{len(review_rows)}。", "sources": [{"name": row["matchNumStr"], "url": row["sourceUrl"]} for row in results]})
    print(json.dumps({"review": {"direction": sum(r["directionHit"] for r in review_rows), "main": sum(r["mainHit"] for r in review_rows), "pool": sum(r["poolHit"] for r in review_rows)}, "models": model_counts}, ensure_ascii=True))


if __name__ == "__main__":
    main()
