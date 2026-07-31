#!/usr/bin/env python3
"""Apply the verified 30 July review and conservatively refresh active models."""
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
    results = read(DATA / "settled_results_20260730_manual.json")["results"]
    by_id = {str(row["matchId"]): row for row in results}
    prediction_path = DATA / "predictions_20260730.json"
    predictions = read(prediction_path)
    review_rows = []
    for match in predictions["matches"]:
        row = by_id[str(match["id"])]
        home, away = (int(x) for x in row["score"].split("-"))
        match["result"] = {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "manual public cross-check", "extraTimeScore": row.get("extraTimeScore")}
        actual = direction(row["score"])
        pool = [match["mainScore"], *match.get("backupScores", [])]
        review_rows.append({
            "matchId": str(match["id"]), "matchNumStr": match["matchNumStr"], "league": match["league"], "home": match["home"], "away": match["away"],
            "score": row["score"], "extraTimeScore": row.get("extraTimeScore"), "direction": actual,
            "directionHit": match["direction"] == actual, "mainScore": match["mainScore"], "mainHit": match["mainScore"] == row["score"],
            "poolHit": row["score"] in pool,
        })
    write(prediction_path, predictions)
    source_path = DATA / "sporttery_20260730_latest.json"
    source = read(source_path)
    for match in source["matches"]:
        row = by_id.get(str(match["matchId"]))
        if row:
            home, away = (int(x) for x in row["score"].split("-"))
            match["result"] = {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "manual public cross-check", "extraTimeScore": row.get("extraTimeScore")}
    write(source_path, source)

    calibration_path = DATA / "auto_model_calibration.json"
    calibration = read(calibration_path)
    already_reviewed = "review0730" in calibration
    model_counts = {}
    for league in ("欧罗巴联赛", "巴西甲级联赛"):
        rows = [row for row in results if row["league"] == league]
        counts = Counter(direction(row["score"]) for row in rows)
        base = calibration["competitions"].get(league)
        if not base:
            from generate_date_pages import COMPETITION_MODELS
            base_model = COMPETITION_MODELS[league]
            base = {"version": base_model["version"], "prior_probs": list(base_model["prior_probs"]), "goal_shift": base_model.get("goal_shift", 0)}
            calibration["competitions"][league] = base
        current = base["prior_probs"]
        blend = calibration.get("review0730", {}).get("modelCounts", {}).get(league, {}).get("blend", min(0.12, len(rows) / (len(rows) + 40)))
        if already_reviewed:
            adjusted = current
        else:
            empirical = [counts["home"] / len(rows), counts["draw"] / len(rows), counts["away"] / len(rows)]
            adjusted = [round((1 - blend) * old + blend * new, 4) for old, new in zip(current, empirical)]
        base["prior_probs"] = adjusted
        base["version"] = f"{base['version']}-review0730"
        base["lesson"] = f"0730复盘：方向 {sum(r['directionHit'] for r in review_rows if r['league'] == league) if any(r['league'] == league for r in review_rows) else 0}/{len(rows)}；增加平局保护、0-2/2-2与强势方大比分尾部，避免只押主方向。"
        model_counts[league] = {"counts": dict(counts), "blend": round(blend, 4), "prior_probs": adjusted}
    calibration["review0730"] = {"method": "verified 90-minute results; extra time excluded from direction", "modelCounts": model_counts, "generatedAt": datetime.now().isoformat(timespec="seconds")}
    write(calibration_path, calibration)

    hits = {key: sum(bool(row[key]) for row in review_rows) for key in ("directionHit", "mainHit", "poolHit")}
    reviews = []
    for league in ("欧罗巴联赛", "巴西甲级联赛"):
        league_rows = [row for row in review_rows if row["league"] == league]
        reviews.append({"league": league, "results": league_rows, "summary": f"方向命中 {sum(row['directionHit'] for row in league_rows)}/{len(league_rows)}；主比分命中 {sum(row['mainHit'] for row in league_rows)}/{len(league_rows)}；比分池命中 {sum(row['poolHit'] for row in league_rows)}/{len(league_rows)}。", "modelAdjustment": "提高平局保护与强势方大比分尾部，保持小样本收缩；不把加时比分混入90分钟胜平负。"})
    review = {"reviewDate": "20260730", "source": "manual public cross-check", "reviews": reviews, "results": review_rows, "summary": f"方向命中 {hits['directionHit']}/{len(review_rows)}；主比分命中 {hits['mainHit']}/{len(review_rows)}；比分池命中 {hits['poolHit']}/{len(review_rows)}。", "modelAdjustment": "欧罗巴资格赛提高平局与强势方大比分尾部；巴甲维持低置信和平局保护；不把帕福斯加时4-0混入90分钟胜平负。", "sources": [{"url": row["sourceUrl"], "name": row["matchNumStr"]} for row in results]}
    write(DATA / "review_20260730_competitions.json", review)
    write(DATA / "settled_results_20260730_auto.json", {"settlementBasis": "90-minute result", "results": results})
    print(json.dumps({"review": hits, "models": model_counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
