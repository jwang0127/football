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
            injuries = [{"team": x.get("team", {}).get("name"), "player": x.get("player", {}).get("name"), "status": x.get("player", {}).get("type"), "reason": x.get("player", {}).get("reason")} for x in injury_payload.get("response", [])]
        except Exception as exc:
            injuries = []
            injury_payload = {"errors": {"exception": str(exc)}}
        rows[str(match.get("matchId") or match.get("id"))] = {
            "status": "ok", "fixtureId": fid, "sourceUrl": f"https://v3.football.api-sports.io/fixtures?id={fid}",
            "league": item.get("league", {}), "round": item.get("league", {}).get("round"), "season": item.get("league", {}).get("season"),
            "teams": {"home": item.get("teams", {}).get("home"), "away": item.get("teams", {}).get("away")},
            "fixture": {"date": item.get("fixture", {}).get("date"), "status": item.get("fixture", {}).get("status"), "venue": item.get("fixture", {}).get("venue"), "referee": item.get("fixture", {}).get("referee")},
            "injuries": injuries, "injuryCount": len(injuries), "injuryApiErrors": injury_payload.get("errors", {}),
        }
        time.sleep(1)
    out = DATA / f"match_radar_enrichment_{args.date}.json"
    out.write_text(json.dumps({"version":"api-football-enrichment-v1", "date":args.date, "provider":"API-Football", "matches":rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"date": args.date, "matched": sum(x.get("status") == "ok" for x in rows.values()), "injuryRecords": sum(x.get("injuryCount", 0) for x in rows.values()), "output": str(out)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
