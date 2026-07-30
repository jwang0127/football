#!/usr/bin/env python3
"""Apply a conservative, clearly-labelled update from the six 29 July results."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def outcome(score: str) -> str:
    home, away = (int(x) for x in score.split("-"))
    return "home" if home > away else "away" if home < away else "draw"


def main() -> None:
    results = read(DATA / "settled_results_20260729_special.json")["results"]
    calibration_path = DATA / "auto_model_calibration.json"
    calibration = read(calibration_path)
    adjustments = {}
    for league in ("欧洲冠军联赛", "巴西甲级联赛"):
        rows = [row for row in results if row["league"] == league]
        counts = {key: sum(outcome(row["score"]) == key for row in rows) for key in ("home", "draw", "away")}
        empirical = [counts["home"] / len(rows), counts["draw"] / len(rows), counts["away"] / len(rows)]
        current = calibration["competitions"][league]["prior_probs"]
        blend = min(0.12, len(rows) / (len(rows) + 40))
        adjusted = [round((1 - blend) * old + blend * new, 4) for old, new in zip(current, empirical)]
        calibration["competitions"][league]["prior_probs"] = adjusted
        calibration["competitions"][league]["version"] += "-special0729"
        calibration["competitions"][league]["lesson"] += f"；追加0729六场专项样本{len(rows)}场，主/平/客 {counts['home']}/{counts['draw']}/{counts['away']}，保守收缩。"
        adjustments[league] = {"sample": len(rows), "counts": counts, "blend": round(blend, 4), "prior_probs": adjusted}
    calibration["specialReview"] = {"date": "20260729", "method": "90-minute outcomes only; extra time and penalties excluded from direction", "adjustments": adjustments}
    calibration["generatedAt"] = datetime.now().isoformat(timespec="seconds")
    calibration_path.write_text(json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(adjustments, ensure_ascii=False))


if __name__ == "__main__":
    main()
