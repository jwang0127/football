"""Fetch concrete fixture metadata and fixture-level injury records for the radar."""
from __future__ import annotations
import argparse, json, os, time
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

TEAM_ALIASES = {
    ("GNI", "ILV"): ("Gnistan", "Ilves"),
    ("HAC", "HAL"): ("BK Hacken", "Halmstad"),
    ("CAR", "WRE"): ("Cardiff", "Wrexham"),
    ("DEP", "CFE"): ("Deportivo La Coruna", "Elche"),
    ("CAP", "BEN"): ("Casa Pia", "Benfica"),
    ("INT", "CBM"): ("Internacional", "Remo"),
}

def api(path: str, key: str):
    req = Request("https://v3.football.api-sports.io/" + path, headers={"x-apisports-key": key, "User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=45) as response:
        return json.loads(response.read())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    args = ap.parse_args()
    key = os.environ.get("API_FOOTBALL_KEY", "").strip().strip("'")
    if not key:
        raise SystemExit("API_FOOTBALL_KEY is not configured")
    source = json.loads((DATA / f"sporttery_{args.date}_latest.json").read_text(encoding="utf-8-sig"))
    fixtures = {}
    for day in (args.date[:4] + "-" + args.date[4:6] + "-" + args.date[6:8],):
        payload = api("fixtures?date=" + day, key)
        for item in payload.get("response", []):
            home = item.get("teams", {}).get("home", {}).get("name", "")
            away = item.get("teams", {}).get("away", {}).get("name", "")
            fixtures[(home.lower(), away.lower())] = item
    rows = {}
    for match in source.get("matches", []):
        aliases = TEAM_ALIASES.get((str(match.get("homeCode")), str(match.get("awayCode"))))
        item = fixtures.get(tuple(x.lower() for x in aliases)) if aliases else None
        if not item:
            rows[str(match.get("matchId") or match.get("id"))] = {"status": "fixture_not_matched", "teamAliases": aliases}
            continue
        fid = item["fixture"]["id"]
        try:
            injury_payload = api(f"injuries?fixture={fid}", key)
            injuries = [{"teamId": x.get("team", {}).get("id"), "team": x.get("team", {}).get("name"), "playerId": x.get("player", {}).get("id"), "player": x.get("player", {}).get("name"), "status": x.get("player", {}).get("type"), "reason": x.get("player", {}).get("reason")} for x in injury_payload.get("response", [])]
            unique = {}
            for injury in injuries:
                unique[(injury.get("teamId"), injury.get("playerId"), injury.get("status"), injury.get("reason"))] = injury
            injuries = list(unique.values())
        except Exception as exc:
            injuries = []
            injury_payload = {"errors": {"exception": str(exc)}}
        squad_positions = {}
        for team_id in [item.get("teams", {}).get("home", {}).get("id"), item.get("teams", {}).get("away", {}).get("id")]:
            try:
                squad = api(f"players/squads?team={team_id}", key)
                for player in (squad.get("response") or [{}])[0].get("players", []):
                    squad_positions[str(player.get("id"))] = player.get("position")
            except Exception:
                pass
        for injury in injuries:
            injury["position"] = squad_positions.get(str(injury.get("playerId")), "")
        try:
            odds_payload = api(f"odds?fixture={fid}", key)
            bookmaker = (odds_payload.get("response") or [{}])[0].get("bookmakers", [{}])[0]
            winner = next((bet for bet in bookmaker.get("bets", []) if bet.get("name") == "Match Winner"), {})
            market_odds = {str(value.get("value")): value.get("odd") for value in winner.get("values", [])}
            market = {"bookmaker": bookmaker.get("name"), "home": market_odds.get("Home"), "draw": market_odds.get("Draw"), "away": market_odds.get("Away")}
        except Exception:
            market = {}
        try:
            home_id = item.get("teams", {}).get("home", {}).get("id")
            away_id = item.get("teams", {}).get("away", {}).get("id")
            h2h_payload = api(f"fixtures/headtohead?h2h={home_id}-{away_id}", key)
            h2h = [{"date": x.get("fixture", {}).get("date", "")[:10], "home": x.get("teams", {}).get("home", {}).get("name"), "away": x.get("teams", {}).get("away", {}).get("name"), "homeGoals": x.get("goals", {}).get("home"), "awayGoals": x.get("goals", {}).get("away"), "league": x.get("league", {}).get("name")} for x in h2h_payload.get("response", []) if x.get("goals", {}).get("home") is not None and x.get("goals", {}).get("away") is not None]
        except Exception:
            h2h = []
        rows[str(match.get("matchId") or match.get("id"))] = {
            "status": "ok", "fixtureId": fid, "sourceUrl": f"https://v3.football.api-sports.io/fixtures?id={fid}",
            "league": item.get("league", {}), "round": item.get("league", {}).get("round"), "season": item.get("league", {}).get("season"),
            "teams": {"home": item.get("teams", {}).get("home"), "away": item.get("teams", {}).get("away")},
            "fixture": {"date": item.get("fixture", {}).get("date"), "status": item.get("fixture", {}).get("status"), "venue": item.get("fixture", {}).get("venue"), "referee": item.get("fixture", {}).get("referee")},
            "injuries": injuries, "injuryCount": len(injuries), "injuryApiErrors": injury_payload.get("errors", {}),
            "marketOdds": market,
            "h2h": h2h,
        }
        time.sleep(1)
    out = DATA / f"match_radar_enrichment_{args.date}.json"
    out.write_text(json.dumps({"version":"api-football-enrichment-v1", "date":args.date, "provider":"API-Football", "matches":rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"date": args.date, "matched": sum(x.get("status") == "ok" for x in rows.values()), "injuryRecords": sum(x.get("injuryCount", 0) for x in rows.values()), "output": str(out)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
