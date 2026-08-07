"""Production gate for daily match dossiers and prediction evidence consistency."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED = {
    "previousMatch", "nextMatch", "ranking", "promotionRelegation", "coverRisk",
    "upsetRisk", "scheduleLoad", "availability", "completeness", "brief",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--root", default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = Path(args.root)
    path = root / "data" / f"predictions_{args.date}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    for match in payload.get("matches", []):
        label = match.get("matchNumStr", match.get("id"))
        brief = match.get("matchBrief") or {}
        missing = REQUIRED - set(brief)
        if missing:
            errors.append(f"{label}: missing brief fields {sorted(missing)}")
        gate = (match.get("reasoningContract") or {}).get("evidenceGate")
        verified = match.get("verifiedFactors") or []
        basis = str(match.get("analysisBasis", ""))
        analysis = str(match.get("integratedAnalysis", ""))
        if gate == "blocked" and verified:
            errors.append(f"{label}: evidenceGate blocked but verifiedFactors={verified}")
        if gate == "passed" and not verified:
            errors.append(f"{label}: evidenceGate passed without verifiedFactors")
        if gate == "blocked" and "已核验" in analysis:
            errors.append(f"{label}: blocked analysis claims verified evidence")
        if gate == "passed" and "未取得足够比赛级公开证据" in basis:
            errors.append(f"{label}: passed context still uses blocked analysis basis")
        if "已收集" in str(brief.get("ranking", "")) and not match.get("homeRank") and not match.get("awayRank"):
            errors.append(f"{label}: ranking says collected but has no concrete rank")
        if brief.get("completeness", 0) < 0.5:
            warnings.append(f"{label}: brief completeness={brief.get('completeness')}; unknown fields remain")
    if not payload.get("matches"):
        errors.append("no matches in production payload")
    print(f"brief audit {args.date}: matches={len(payload.get('matches', []))}, errors={len(errors)}, warnings={len(warnings)}")
    for item in warnings:
        print("WARN", item)
    for item in errors:
        print("ERROR", item)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
