#!/usr/bin/env python3
"""Write auditable positive and pure-upset variants for a daily board."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def upset_score(match: dict, direction: str) -> str:
    if direction == "away":
        return {"home": "0-1", "away": "1-2"}.get(match["direction"], "0-1")
    if direction == "home":
        return {"home": "2-1", "away": "1-0"}.get(match["direction"], "1-0")
    return "1-1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "data" / f"predictions_{args.date}.json"
    payload = json.loads(source.read_text(encoding="utf-8-sig"))
    positive = []
    pure_upset = []
    for row in payload["matches"]:
        positive.append({
            "matchNumStr": row["matchNumStr"], "home": row["home"], "away": row["away"],
            "kickoff": row["kickoff"], "direction": row["direction"],
            "directionText": row["directionText"], "mainScore": row["mainScore"],
            "backupScores": row["backupScores"], "probabilities": row["probabilities"],
            "risk": row.get("marketRiskLevel", "unknown"),
            "analysisCompleteness": row.get("analysisCompleteness"),
            "missingAnalysisDimensions": row.get("missingAnalysisDimensions", []),
        })
        reverse = "away" if row["direction"] == "home" else "home"
        pure_upset.append({
            "matchNumStr": row["matchNumStr"], "home": row["home"], "away": row["away"],
            "kickoff": row["kickoff"], "direction": reverse,
            "directionText": "客胜（纯爆冷）" if reverse == "away" else "主胜（纯爆冷）",
            "mainScore": upset_score(row, reverse),
            "backupScores": ["1-1", "2-2"], "baseProbabilities": row["probabilities"],
            "basis": "反转基础模型方向，仅作尾部风险情景，不代表模型主判断",
        })
    output = {
        "date": args.date, "source": str(source.relative_to(root)),
        "disclaimer": "仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。",
        "positive": positive, "pureUpset": pure_upset,
    }
    target = root / "data" / f"prediction_variants_{args.date}.json"
    target.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {target} ({len(positive)} positive, {len(pure_upset)} pure-upset)")


if __name__ == "__main__":
    main()
