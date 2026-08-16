"""Build a competition-specific research pack before a new model is created."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


OFFICIAL_SOURCES = {
    "日本职业联赛": ["https://www.jleague.jp/j1/standings/2026/", "https://www.jleague.jp/en/j1/match/"],
    "日本乙级联赛": ["https://www.jleague.jp/en/j2/standings/2026/", "https://www.jleague.jp/en/j2/match/"],
    "美国职业大联盟": ["https://www.mlssoccer.com/news/mls-announces-2026-regular-season-schedule", "https://www.mlssoccer.com/league-reports/competition-guidelines/"],
    "欧洲冠军联赛": ["https://www.uefa.com/uefachampionsleague/", "https://www.uefa.com/uefachampionsleague/fixtures-results/"],
    "欧罗巴联赛": ["https://www.uefa.com/uefaeuropaleague/", "https://www.uefa.com/uefaeuropaleague/fixtures-results/"],
    "欧洲超级杯": ["https://www.uefa.com/uefasupercup/"],
    "亚洲冠军精英联赛": ["https://www.the-afc.com/en/club/afc_champions_league_elite/fixtures__standings.html"],
    "南美解放者杯": ["https://www.conmebol.com/libertadores/"],
    "巴西杯": ["https://www.cbf.com.br/futebol-brasileiro/tabelas/copa-do-brasil/profissional/2026"],
    "英格兰联赛杯": ["https://www.efl.com/competitions/carabao-cup/"],
    "英格兰社区盾杯": ["https://www.thefa.com/competitions/the-fa-community-shield"],
}


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def collect_research_pack(competition: str) -> dict:
    matches = []
    for path in sorted(DATA.glob("sporttery_*_latest.json")):
        try:
            payload = _read(path)
        except (OSError, json.JSONDecodeError):
            continue
        for match in payload.get("matches", []):
            if match.get("league") == competition:
                matches.append(match)

    external_path = DATA / "external_league_history_2026.json"
    external = {}
    if external_path.exists():
        try:
            external = _read(external_path).get("competitions", {}).get(competition, {})
        except (OSError, json.JSONDecodeError):
            external = {}

    results = []
    teams = set()
    for match in matches:
        teams.update([str(match.get("home", "")), str(match.get("away", ""))])
        result = match.get("result") or {}
        if result.get("homeGoals") is None or result.get("awayGoals") is None:
            continue
        home, away = int(result["homeGoals"]), int(result["awayGoals"])
        results.append({"date": match.get("matchDate", ""), "home": home, "away": away, "total": home + away})
    external_results = [{"date": row.get("date", ""), "home": int(row["homeGoals"]), "away": int(row["awayGoals"]), "total": int(row["homeGoals"]) + int(row["awayGoals"])} for row in external.get("matches", [])]
    results.extend(external_results)
    for row in external.get("matches", []):
        teams.update([str(row.get("home", "")), str(row.get("away", ""))])

    outcome = Counter("home" if row["home"] > row["away"] else "draw" if row["home"] == row["away"] else "away" for row in results)
    n = len(results)
    avg_total = round(sum(row["total"] for row in results) / n, 3) if n else None
    prior = {
        "home": round((outcome["home"] + 2) / (n + 6), 4),
        "draw": round((outcome["draw"] + 2) / (n + 6), 4),
        "away": round((outcome["away"] + 2) / (n + 6), 4),
    }
    missing = [
        "official_stage_and_tie_format",
        "official_lineups_and_injuries",
        "team_strength_and_standings",
        "travel_weather_pitch",
    ]
    if results:
        missing.remove("team_strength_and_standings")
    completeness = round(min(0.75, 0.20 + min(n, 20) / 40 + (0.15 if competition in OFFICIAL_SOURCES else 0)), 3)
    return {
        "competition": competition,
        "localMatchCount": len(matches),
        "verifiedResultCount": n,
        "externalResultCount": len(external_results),
        "teamsObserved": sorted(team for team in teams if team),
        "dateRange": [min((row["date"] for row in results), default=None), max((row["date"] for row in results), default=None)],
        "outcomes": dict(outcome),
        "outcomePriorWithShrinkage": prior,
        "averageTotalGoals": avg_total,
        "officialSources": OFFICIAL_SOURCES.get(competition, []),
        "externalSources": [external.get("sourceUrl")] if external.get("sourceUrl") else [],
        "missingDimensions": missing,
        "researchCompleteness": completeness,
        "status": "research_pack_ready_but_needs_matchday_refresh" if n else "no_verified_local_results_neutral_start",
    }


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--competition", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(collect_research_pack(args.competition), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
