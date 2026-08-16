"""Fetch public season results to supplement sparse Sporttery boards."""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HEADERS = {"User-Agent": "Mozilla/5.0 (football-prediction-research)", "Accept": "application/json", "Referer": "https://www.espn.com/"}
LEAGUES = {
    "日本职业联赛": "jpn.1",
    "美国职业大联盟": "usa.1",
}


def fetch(league: str, endpoint: str, start: str, end: str) -> dict:
    start_date, end_date = datetime.strptime(start, "%Y%m%d"), datetime.strptime(end, "%Y%m%d")
    events = []
    cursor = start_date
    while cursor <= end_date:
        chunk_end = min(cursor + timedelta(days=6), end_date)
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{endpoint}/scoreboard?dates={cursor:%Y%m%d}-{chunk_end:%Y%m%d}&limit=1000"
        payload = None
        for attempt in range(4):
            try:
                with urlopen(Request(url, headers=HEADERS), timeout=90) as response:
                    payload = json.loads(response.read())
                break
            except Exception:
                if attempt == 3:
                    raise
                time.sleep(1.5 * (attempt + 1))
        events.extend(payload.get("events", []))
        cursor = chunk_end + timedelta(days=1)
    rows = []
    seen = set()
    for event in events:
        if event.get("id") in seen:
            continue
        seen.add(event.get("id"))
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors", [])
        by_side = {row.get("homeAway"): row for row in competitors}
        home, away = by_side.get("home", {}), by_side.get("away", {})
        status = event.get("status", {}).get("type", {})
        if not status.get("completed") or not str(home.get("score", "")).isdigit() or not str(away.get("score", "")).isdigit():
            continue
        rows.append({
            "eventId": str(event.get("id", "")),
            "date": str(event.get("date", ""))[:10],
            "competition": league,
            "endpoint": endpoint,
            "home": home.get("team", {}).get("displayName", ""),
            "away": away.get("team", {}).get("displayName", ""),
            "homeGoals": int(home["score"]),
            "awayGoals": int(away["score"]),
            "sourceUrl": url,
        })
    return {"competition": league, "endpoint": endpoint, "sourceUrl": url, "matches": rows}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="20260101")
    parser.add_argument("--end", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--output", default="data/external_league_history_2026.json")
    parser.add_argument("--only", nargs="*", choices=sorted(LEAGUES))
    args = parser.parse_args()
    selected = {league: endpoint for league, endpoint in LEAGUES.items() if not args.only or league in args.only}
    competitions = {league: fetch(league, endpoint, args.start, args.end) for league, endpoint in selected.items()}
    payload = {"generatedAt": datetime.now().isoformat(timespec="seconds"), "source": "ESPN public scoreboard", "dateRange": [args.start, args.end], "competitions": competitions}
    path = ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({league: len(data["matches"]) for league, data in competitions.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
