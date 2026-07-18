#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DISCLAIMER = "以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--expected-matches", required=True, type=int)
    args = parser.parse_args()
    payload = json.loads((ROOT / "data" / f"predictions_{args.date}.json").read_text(encoding="utf-8-sig"))
    html = (ROOT / args.date / "index.html").read_text(encoding="utf-8")
    mirror = (ROOT / args.date / f"predict_{args.date}.html").read_text(encoding="utf-8")
    matches = payload["matches"]
    assert len(matches) == args.expected_matches, (len(matches), args.expected_matches)
    assert len({match["id"] for match in matches}) == len(matches)
    assert len(payload["competitionModels"]) == len({match["league"] for match in matches})
    assert "法国 vs 英格兰" not in html
    assert DISCLAIMER in html and html == mirror
    assert html.count('<section class="match"') == len(matches)
    assert html.count('<section class="combo ') == len(payload["combos"])
    match_ids = {match["id"] for match in matches}
    for match in matches:
        profile = payload["competitionModels"][match["league"]]
        assert match["modelProfile"]["version"] == profile["version"]
        assert match["home"] in html and match["away"] in html
        assert match["tailRiskScores"] or any(score in {"0-0", "0-3", "1-3", "1-4", "2-2", "3-0"} for score in match["backupScores"])
    for combo in payload["combos"]:
        ids = [leg["matchId"] for leg in combo["legs"]]
        assert len(ids) == len(set(ids))
        assert set(ids) <= match_ids
        assert sum(leg["market"] == "had" for leg in combo["legs"]) <= 1
        assert combo["productOdds"] >= 10.0
        assert abs(combo["productOdds"] - round(math.prod(leg["odds"] for leg in combo["legs"]), 2)) <= 0.01
    print(f"{args.date}: {len(matches)} matches, {len(payload['competitionModels'])} competition models, "
          f"{len(payload['combos'])} parlays, min odds {min(row['productOdds'] for row in payload['combos']):.2f}, OK")


if __name__ == "__main__":
    main()
