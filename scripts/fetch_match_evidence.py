"""Collect source-linked evidence for every match on a Sporttery business date.

The collector is deliberately conservative: a provider failure is recorded in
the output and never converted into a positive football fact.  Providers are
ordered by coverage and cost:

* Sporttery is the schedule/lottery source and is already fetched separately.
* ESPN and SofaScore are public scoreboard fallbacks for results and schedules.
* Open-Meteo is keyless weather/geocoding support when a venue or coordinates
  are available.
* football-data.org is an optional, token-based enrichment.

The output is a cache consumed by build_public_context.py and is safe to commit
as an input snapshot for a generated page.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (football-prediction-evidence/1.0)",
    "Accept": "application/json",
    "Referer": "https://m.sporttery.cn/mjc/jsq/zqzjq/",
}

ESPN_LEAGUES = {
    "韩国职业联赛": "kor.1", "瑞典超级联赛": "swe.1", "挪威超级联赛": "nor.1",
    "芬兰超级联赛": "fin.1", "巴西甲级联赛": "bra.1", "日本乙级联赛": "jpn.2",
    "美国职业大联盟": "usa.1", "英格兰冠军联赛": "eng.2", "荷兰甲级联赛": "ned.1",
    "葡萄牙超级联赛": "por.1", "西班牙甲级联赛": "esp.1", "英格兰社区盾杯": "eng.community.shield",
    "英格兰联赛杯": "eng.league_cup", "欧冠": "uefa.champions", "欧罗巴": "uefa.europa",
    "欧洲超级杯": "uefa.super_cup", "解放者杯": "conmebol.libertadores", "亚冠精英": "afc.champions",
}
FOOTBALL_DATA_CODES = {
    "英超": "PL", "德甲": "BL1", "西甲": "PD", "意甲": "SA", "法甲": "FL1",
    "日本职业联赛": "JPL", "巴西甲级联赛": "BSA",
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def normal(value: object) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").lower())


def http_json(url: str, headers: dict | None = None, timeout: int = 15) -> tuple[dict | None, dict]:
    last = ""
    for attempt in range(3):
        try:
            request = Request(url, headers={**HEADERS, **(headers or {})})
            with urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read())
                return payload, {"status": "ok", "http": response.status, "url": url}
        except Exception as exc:  # provider outages must not stop other providers
            last = f"{type(exc).__name__}: {exc}"
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    return None, {"status": "error", "url": url, "error": last}


def event_teams(event: dict) -> tuple[dict, dict]:
    rows = (event.get("competitions") or [{}])[0].get("competitors", [])
    by_side = {row.get("homeAway"): row for row in rows}
    return by_side.get("home", {}), by_side.get("away", {})


def event_row(event: dict, source_url: str) -> dict | None:
    home, away = event_teams(event)
    if not home or not away:
        return None
    status = event.get("status", {}).get("type", {})
    home_score = home.get("score")
    away_score = away.get("score")
    result = None
    if status.get("completed") and str(home_score).isdigit() and str(away_score).isdigit():
        result = {"homeGoals": int(home_score), "awayGoals": int(away_score)}
    return {
        "eventId": str(event.get("id", "")),
        "date": str(event.get("date", ""))[:10],
        "home": home.get("team", {}).get("displayName", ""),
        "away": away.get("team", {}).get("displayName", ""),
        "status": status.get("name") or status.get("description"),
        "result": result,
        "venue": ((event.get("competitions") or [{}])[0].get("venue") or {}),
        "sourceUrl": source_url,
    }


def fetch_espn(target: str, leagues: set[str]) -> tuple[list[dict], dict]:
    end = datetime.strptime(target, "%Y%m%d")
    start = end - timedelta(days=90)
    rows, states = [], {}
    for league in sorted(leagues):
        endpoint = ESPN_LEAGUES.get(league)
        if not endpoint:
            continue
        url = "https://site.api.espn.com/apis/site/v2/sports/soccer/{}/scoreboard?{}".format(
            endpoint, urlencode({"dates": f"{start:%Y%m%d}-{end:%Y%m%d}", "limit": 1000}))
        payload, state = http_json(url, timeout=15)
        states[league] = state
        for event in (payload or {}).get("events", []):
            row = event_row(event, url)
            if row:
                row["league"] = league
                rows.append(row)
    unique = {row["eventId"]: row for row in rows if row.get("eventId")}
    return list(unique.values()), {"provider": "ESPN", "leagues": states}


def fetch_sofascore(target: str) -> tuple[list[dict], dict]:
    url = f"https://api.sofascore.com/api/v1/sport/football/scheduled-events/{target[:4]}-{target[4:6]}-{target[6:8]}/inverse"
    payload, state = http_json(url, headers={"Referer": "https://www.sofascore.com/"}, timeout=15)
    rows = []
    for event in (payload or {}).get("events", []):
        home = event.get("homeTeam", {})
        away = event.get("awayTeam", {})
        if home and away:
            rows.append({"eventId": str(event.get("id", "")), "date": target[:4] + "-" + target[4:6] + "-" + target[6:8],
                         "home": home.get("name", ""), "away": away.get("name", ""),
                         "status": (event.get("status") or {}).get("description"),
                         "result": ({"homeGoals": event.get("homeScore", {}).get("current"),
                                     "awayGoals": event.get("awayScore", {}).get("current")}
                                    if (event.get("homeScore", {}).get("current") is not None and
                                        event.get("awayScore", {}).get("current") is not None) else None),
                         "venue": {}, "sourceUrl": url})
    return rows, {"provider": "SofaScore", "state": state}


def fetch_weather(match: dict) -> tuple[dict | None, dict]:
    coordinates = match.get("venueCoordinates") or {}
    lat, lon = coordinates.get("latitude"), coordinates.get("longitude")
    venue = match.get("venue") or ""
    if lat is None or lon is None:
        return None, {"status": "missing_coordinates", "reason": "Sporttery did not provide stadium coordinates", "venue": venue}
    params = {"latitude": lat, "longitude": lon,
              "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m",
              "timezone": "auto", "forecast_days": 2}
    url = "https://api.open-meteo.com/v1/forecast?" + urlencode(params)
    payload, state = http_json(url, timeout=30)
    return payload, state


def fetch_football_data(target: str, leagues: set[str]) -> tuple[list[dict], dict]:
    token = os.getenv("FOOTBALL_DATA_TOKEN", "").strip()
    if not token:
        return [], {"status": "disabled", "reason": "FOOTBALL_DATA_TOKEN is not configured"}
    end = datetime.strptime(target, "%Y%m%d")
    start = end - timedelta(days=90)
    rows, states = [], {}
    for league in sorted(leagues):
        code = FOOTBALL_DATA_CODES.get(league)
        if not code:
            continue
        query = urlencode({"dateFrom": f"{start:%Y-%m-%d}", "dateTo": f"{end:%Y-%m-%d}"})
        url = f"https://api.football-data.org/v4/competitions/{code}/matches?{query}"
        payload, state = http_json(url, headers={"X-Auth-Token": token}, timeout=15)
        states[league] = state
        for match in (payload or {}).get("matches", []):
            score = match.get("score", {}).get("fullTime", {})
            home, away = match.get("homeTeam", {}), match.get("awayTeam", {})
            rows.append({"eventId": str(match.get("id", "")), "date": str(match.get("utcDate", ""))[:10],
                         "home": home.get("name", ""), "away": away.get("name", ""),
                         "status": match.get("status"),
                         "result": ({"homeGoals": score.get("home"), "awayGoals": score.get("away")}
                                    if score.get("home") is not None and score.get("away") is not None else None),
                         "venue": {}, "sourceUrl": url, "league": league})
    return rows, {"provider": "football-data.org", "leagues": states}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Sporttery business date YYYYMMDD")
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    source = read(ROOT / args.source)
    matches = source.get("matches", [])
    leagues = {str(match.get("league", "")) for match in matches}
    espn_rows, espn_state = fetch_espn(args.date, leagues)
    sofa_rows, sofa_state = fetch_sofascore(args.date)
    football_data_rows, football_data_state = fetch_football_data(args.date, leagues)
    all_rows = espn_rows + sofa_rows + football_data_rows
    by_match = {}
    for match in matches:
        home, away = normal(match.get("home")), normal(match.get("away"))
        candidates = []
        for row in all_rows:
            rh, ra = normal(row.get("home")), normal(row.get("away"))
            if (home and away and ((home in rh or rh in home) and (away in ra or ra in away))):
                candidates.append(row)
        weather, weather_state = fetch_weather(match)
        by_match[str(match.get("matchId") or match.get("id"))] = {
            "scheduleResults": candidates,
            "weather": weather,
            "sources": [row.get("sourceUrl") for row in candidates if row.get("sourceUrl")],
            "providerStatus": {"weather": weather_state},
            "missing": ([] if candidates else ["recent_results_and_schedule"])
                       + ([] if weather else ["weather"]),
        }
    output = {"version": "match-evidence-v1", "date": args.date, "generatedAt": datetime.now().isoformat(timespec="seconds"),
              "providers": {"espn": espn_state, "sofascore": sofa_state, "footballData": football_data_state,
                            "openMeteo": {"docs": "https://open-meteo.com/en/docs"}},
              "matches": by_match}
    path = ROOT / (args.output or f"data/external_context_{args.date}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"matches": len(matches), "withExternalRows": sum(bool(v["scheduleResults"]) for v in by_match.values()),
                      "withWeather": sum(bool(v["weather"]) for v in by_match.values()),
                      "output": str(path)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
