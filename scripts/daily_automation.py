#!/usr/bin/env python3
"""Run the safe daily football workflow after 11:00 Beijing time.

The runner only publishes after every yesterday match has a verified 90-minute
result. Sporttery does not reliably expose historical business dates, so public
league scoreboards are used as a result cross-check.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import time
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HEADERS = {"User-Agent": "Mozilla/5.0 (football-prediction-daily-runner)"}
try:
    SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    # Windows Python installations may omit the optional tzdata package.
    SHANGHAI_TZ = timezone(timedelta(hours=8))
LEAGUE_ENDPOINTS = {"韩国职业联赛": "kor.1", "瑞典超级联赛": "swe.1", "挪威超级联赛": "nor.1", "芬兰超级联赛": "fin.1", "巴西甲级联赛": "bra.1", "日本职业联赛": "jpn.1", "美国职业大联盟": "usa.1"}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def norm(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value).lower())


def parse_score(value: object) -> tuple[int, int] | None:
    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else None


def parse_goal(value: object) -> int | None:
    match = re.fullmatch(r"\s*\d+\s*", str(value or ""))
    return int(match.group(0)) if match else None


def fetch_json(url: str) -> dict:
    last_error = None
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=30) as response:
                return json.load(response)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise last_error


def event_score(event: dict) -> tuple[int, int] | None:
    competitors = event.get("competitions", [{}])[0].get("competitors", [])
    values = {row.get("homeAway"): parse_goal(row.get("score")) for row in competitors}
    if values.get("home") is not None and values.get("away") is not None:
        return values["home"], values["away"]
    return None


def find_event(match: dict, events: list[dict]) -> tuple[int, int] | None:
    wanted = (norm(match.get("home", "")), norm(match.get("away", "")))
    candidates = []
    for event in events:
        competitors = event.get("competitions", [{}])[0].get("competitors", [])
        names = {row.get("homeAway"): norm(row.get("team", {}).get("displayName", "")) for row in competitors}
        if not names.get("home") or not names.get("away"):
            continue
        similarity = (difflib.SequenceMatcher(None, wanted[0], names["home"]).ratio() + difflib.SequenceMatcher(None, wanted[1], names["away"]).ratio()) / 2
        if wanted[0] in names["home"] or names["home"] in wanted[0]: similarity += .20
        if wanted[1] in names["away"] or names["away"] in wanted[1]: similarity += .20
        candidates.append((similarity, event))
    if not candidates:
        return None
    similarity, event = max(candidates, key=lambda item: item[0])
    if not event.get("status", {}).get("type", {}).get("completed") or similarity < .72:
        return None
    return event_score(event)


def collect_results(date: str, source: dict) -> dict[str, dict]:
    events_by_league: dict[str, list[dict]] = {}
    for league in {m.get("league") for m in source.get("matches", [])}:
        endpoint = LEAGUE_ENDPOINTS.get(league)
        if not endpoint:
            continue
        url = f"https://site.api.espn.com/apis/site/v2/sports/soccer/{endpoint}/scoreboard?dates={date}"
        try:
            events_by_league[league] = fetch_json(url).get("events", [])
        except Exception as exc:
            print(f"result source failed for {league}: {exc}", file=sys.stderr)
    results = {}
    matches_by_league = defaultdict(list)
    for match in source.get("matches", []):
        matches_by_league[match.get("league")].append(match)
    for match in source.get("matches", []):
        match_id = str(match.get("matchId") or match.get("id"))
        existing = match.get("result") or {}
        events = events_by_league.get(match.get("league"), [])
        found = parse_score(f"{existing.get('homeGoals')}-{existing.get('awayGoals')}") or find_event(match, events)
        # Some feeds use Chinese team names while ESPN uses English. A
        # one-match league/date board is still unambiguous, so allow a
        # completed-event fallback only in that narrow case.
        if not found and len(matches_by_league[match.get("league")]) == 1 and len(events) == 1:
            found = event_score(events[0]) if events[0].get("status", {}).get("type", {}).get("completed") else None
        if found:
            endpoint = LEAGUE_ENDPOINTS.get(match.get("league"), "")
            results[match_id] = {"date": date, "matchId": match_id, "score": f"{found[0]}-{found[1]}", "source": "ESPN public scoreboard / Sporttery retained result", "url": f"https://site.api.espn.com/apis/site/v2/sports/soccer/{endpoint}/scoreboard?dates={date}"}
    return results


def result_index() -> dict[str, tuple[int, int]]:
    index = {}
    for path in DATA.glob("settled_results_*.json"):
        for row in read(path).get("results", []):
            parsed = parse_score(row.get("score"))
            if parsed:
                index[str(row.get("matchId"))] = parsed
    return index


def build_review(date: str, source: dict, results: dict[str, dict]) -> dict:
    prediction_path = DATA / f"predictions_{date}.json"
    predictions = read(prediction_path) if prediction_path.exists() else source
    by_league = defaultdict(list)
    for match in source.get("matches", []):
        match_id = str(match.get("matchId") or match.get("id"))
        if match_id not in results:
            continue
        actual = parse_score(results[match_id]["score"])
        prediction = next((row for row in predictions.get("matches", []) if str(row.get("id") or row.get("matchId")) == match_id), match)
        direction = "home" if actual[0] > actual[1] else "away" if actual[0] < actual[1] else "draw"
        by_league[match.get("league", "未知赛事")].append({"matchId": match_id, "matchNumStr": match.get("matchNumStr", match_id), "home": match.get("home"), "away": match.get("away"), "score": results[match_id]["score"], "direction": direction, "directionHit": prediction.get("direction") == direction, "mainScore": prediction.get("mainScore", ""), "mainHit": prediction.get("mainScore") == results[match_id]["score"]})
    reviews = []
    for league, rows in sorted(by_league.items()):
        reviews.append({"league": league, "results": rows, "summary": f"方向命中 {sum(row['directionHit'] for row in rows)}/{len(rows)}；主比分命中 {sum(row['mainHit'] for row in rows)}/{len(rows)}", "modelAdjustment": "仅将本赛事结果纳入滚动校准；小样本收缩，不因单日结果大幅改参。"})
    return {"reviewDate": date, "source": "ESPN public scoreboard / Sporttery retained result", "reviews": reviews}


def optimize_models() -> None:
    from generate_date_pages import model_profile_for
    grouped = defaultdict(list)
    seen = set()
    # Use every verified result in retained Sporttery boards, not only matches
    # that previously appeared in a prediction page. This makes the historical
    # foundation representative of the competition rather than the board
    # selection policy.
    for path in sorted(DATA.glob("sporttery_*_latest.json")):
        try:
            payload = read(path)
        except (OSError, json.JSONDecodeError):
            continue
        board_date = str(payload.get("date", ""))[:8]
        for match in payload.get("matches", []):
            result = match.get("result") or {}
            if result.get("homeGoals") is None or result.get("awayGoals") is None:
                continue
            match_id = str(match.get("matchId") or match.get("id"))
            key = (match.get("league", "未知赛事"), match_id)
            if key in seen:
                continue
            seen.add(key)
            grouped[key[0]].append((board_date, match, (int(result["homeGoals"]), int(result["awayGoals"]))))
    # Keep manually settled matches useful when an old board did not retain a
    # result field, while still preventing duplicates.
    index = result_index()
    for path in sorted(DATA.glob("predictions_*.json")):
        date_match = re.search(r"(\d{8})", path.name)
        if not date_match:
            continue
        for match in read(path).get("matches", []):
            match_id = str(match.get("id") or match.get("matchId"))
            result = index.get(match_id)
            key = (match.get("league", "未知赛事"), match_id)
            if result and key not in seen:
                seen.add(key)
                grouped[key[0]].append((date_match.group(1), match, result))
    external_path = DATA / "external_league_history_2026.json"
    if external_path.exists():
        try:
            external = read(external_path).get("competitions", {})
        except (OSError, json.JSONDecodeError):
            external = {}
        for league, payload in external.items():
            for row in payload.get("matches", []):
                match_id = f"external-{payload.get('endpoint', league)}-{row.get('eventId')}"
                key = (league, match_id)
                if key in seen:
                    continue
                seen.add(key)
                grouped[league].append((str(row.get("date", ""))[:8], {"league": league, "matchId": match_id}, (int(row["homeGoals"]), int(row["awayGoals"]))))
    output = {"generatedAt": datetime.now().isoformat(timespec="seconds"), "method": "rolling verified 90-minute results with conservative shrinkage", "competitions": {}}
    for league, rows in grouped.items():
        rows = sorted(rows, key=lambda row: row[0])
        if len(rows) < 1:
            continue
        base = model_profile_for(league)
        counts = {key: 0 for key in ("home", "draw", "away")}
        for _, _, (home, away) in rows:
            counts["home" if home > away else "away" if home < away else "draw"] += 1
        empirical = [counts["home"] / len(rows), counts["draw"] / len(rows), counts["away"] / len(rows)]
        blend = min(.25, len(rows) / (len(rows) + 40))
        adjusted = [(1 - blend) * old + blend * new for old, new in zip(base["prior_probs"], empirical)]
        total_goals = [home + away for _, _, (home, away) in rows]
        avg_goals = sum(total_goals) / len(total_goals)
        observed_goal_shift = max(-.18, min(.18, (avg_goals - 2.5) * .12))
        base_version = str(base.get("version", "competition-model")).split("-auto-")[0]
        output["competitions"][league] = {
            "version": f"{base_version}-auto-{datetime.now():%m%d}",
            "review_sample": len(rows),
            "prior_probs": tuple(round(value, 4) for value in adjusted),
            "goal_shift": round(.70 * base.get("goal_shift", 0) + .30 * observed_goal_shift, 4),
            "average_total_goals": round(avg_goals, 3),
            "allHistoricalMatches": len(rows),
            "lesson": f"使用本赛事全部已核验历史赛果{len(rows)}场：主/平/客 {counts['home']}/{counts['draw']}/{counts['away']}，平均总进球{avg_goals:.2f}；参数做保守收缩。",
        }
    write(DATA / "auto_model_calibration.json", output)


def run(command: list[str]) -> None:
    print("$", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--yesterday", default="auto")
    parser.add_argument("--today", default="auto")
    args = parser.parse_args()
    now = datetime.now(SHANGHAI_TZ)
    yesterday = (now - timedelta(days=1)).strftime("%Y%m%d") if args.yesterday == "auto" else args.yesterday
    today = now.strftime("%Y%m%d") if args.today == "auto" else args.today
    source_path = DATA / f"sporttery_{yesterday}_latest.json"
    if not source_path.exists():
        source_path = DATA / f"{yesterday}.json"
    if not source_path.exists():
        raise SystemExit(f"missing yesterday board: {yesterday}")
    source = read(source_path)
    results = collect_results(yesterday, source)
    expected = {str(match.get("matchId") or match.get("id")) for match in source.get("matches", [])}
    missing = sorted(expected - set(results))
    if missing:
        raise SystemExit(f"results incomplete for {yesterday}; missing matchIds: {', '.join(missing)}")
    write(DATA / f"settled_results_{yesterday}_auto.json", {"settlementBasis": "90-minute result", "results": list(results.values())})
    for path in (source_path, DATA / f"{yesterday}.json", DATA / f"predictions_{yesterday}.json"):
        if not path.exists():
            continue
        payload = read(path)
        for match in payload.get("matches", []):
            row = results.get(str(match.get("matchId") or match.get("id")))
            if row:
                home, away = map(int, row["score"].split("-"))
                match["result"] = {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "verified daily runner"}
        write(path, payload)
    write(DATA / f"review_{yesterday}_competitions.json", build_review(yesterday, source, results))
    optimize_models()
    target = DATA / f"sporttery_{today}_latest.json"
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise SystemExit("PowerShell runtime not found; install PowerShell Core (pwsh) on the runner")
    run([shell, "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/fetch_sporttery.ps1"), "-Date", today, "-DateMode", "BusinessDate", "-OutFile", str(target), "-PoolCode", "ttg,had,hhad,crs,hafu", "-Force"])
    run([sys.executable, str(ROOT / "scripts/generate_date_pages.py"), "--date", today, "--source", str(target.relative_to(ROOT))])
    predictions = read(DATA / f"predictions_{today}.json")
    run([sys.executable, str(ROOT / "scripts/validate_date_pages.py"), "--date", today, "--expected-matches", str(len(predictions.get("matches", [])))])
    run([sys.executable, str(ROOT / "scripts/backtest_calibration.py")])
    print(json.dumps({"yesterday": yesterday, "today": today, "settled": len(results), "predictions": len(predictions.get("matches", [])), "status": "ok"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
