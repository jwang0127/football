"""Build conservative, source-linked team context from retained public feeds."""
from __future__ import annotations

import argparse, json, re
from datetime import datetime, date
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def rank(value):
    match = re.search(r"(\d+)", str(value or ""))
    return int(match.group(1)) if match else None


def name_key(value):
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").lower())


def parse_date(value):
    text = str(value or "")[:10]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def team_stats(rows, venue=None, limit=5):
    selected = [row for row in rows if venue is None or row.get("venue") == venue]
    selected = sorted(selected, key=lambda row: row.get("date", ""), reverse=True)[:limit]
    if not selected:
        return {"sample": 0, "gf": None, "ga": None, "points": None, "scoringRate": None,
                "cleanSheetRate": None, "bttsRate": None, "over25Rate": None, "lastDate": None}
    total = len(selected)
    points = sum(3 if row["result"] == "W" else 1 if row["result"] == "D" else 0 for row in selected)
    return {
        "sample": total,
        "gf": round(sum(row["gf"] for row in selected) / total, 3),
        "ga": round(sum(row["ga"] for row in selected) / total, 3),
        "points": round(points / total, 3),
        "scoringRate": round(sum(row["gf"] >= 1 for row in selected) / total, 3),
        "cleanSheetRate": round(sum(row["ga"] == 0 for row in selected) / total, 3),
        "bttsRate": round(sum(row["gf"] >= 1 and row["ga"] >= 1 for row in selected) / total, 3),
        "over25Rate": round(sum(row["gf"] + row["ga"] >= 3 for row in selected) / total, 3),
        "lastDate": selected[0].get("date"),
    }


def clamp(value, low, high):
    return max(low, min(high, value))


def fundamental_layer(match, home_rows, away_rows, target_date, league):
    home = team_stats(home_rows)
    away = team_stats(away_rows)
    home_home = team_stats(home_rows, "home")
    away_away = team_stats(away_rows, "away")
    home_rank, away_rank = rank(match.get("homeRank")), rank(match.get("awayRank"))
    values = {"home": 1.0, "draw": 1.0, "away": 1.0}
    factors = []
    if home_rank is not None and away_rank is not None:
        rank_gap = clamp(away_rank - home_rank, -10, 10)
        values["home"] *= 1 + 0.012 * rank_gap
        values["away"] *= 1 - 0.012 * rank_gap
        factors.append("ranking_table")
    if home["sample"] and away["sample"]:
        form_gap = clamp(home["points"] - away["points"], -2.0, 2.0)
        attack_gap = clamp((home["gf"] - home["ga"]) - (away["gf"] - away["ga"]), -2.0, 2.0)
        values["home"] *= 1 + 0.035 * form_gap + 0.025 * attack_gap
        values["away"] *= 1 - 0.035 * form_gap - 0.025 * attack_gap
        factors.append("recent_performance")
    if home_home["sample"] and away_away["sample"]:
        venue_gap = clamp(home_home["points"] - away_away["points"], -2.0, 2.0)
        values["home"] *= 1.04 + 0.025 * venue_gap
        values["away"] *= 1 - 0.025 * venue_gap
        factors.append("home_away")
    values["draw"] *= 1.0 + (0.08 if home["gf"] is not None and away["gf"] is not None and home["gf"] + away["gf"] <= 2.35 else 0.0)
    probabilities = values

    target = parse_date(target_date) or date.today()
    rest = {}
    for name, rows in (("home", home_rows), ("away", away_rows)):
        latest = team_stats(rows).get("lastDate")
        last = parse_date(latest)
        rest[name] = (target - last).days if last else None
    if rest["home"] is not None or rest["away"] is not None:
        factors.append("schedule_load")
    rest_gap = (rest["home"] or 0) - (rest["away"] or 0)
    if abs(rest_gap) >= 2:
        better = "home" if rest_gap > 0 else "away"
        tired = "away" if better == "home" else "home"
        probabilities[better] *= 1.04
        probabilities[tired] *= 0.96

    attack_samples = [x for x in (home_home, away_away, home, away) if x["gf"] is not None]
    if attack_samples:
        components = [value for value in (
            home_home["gf"] if home_home["gf"] is not None else home["gf"],
            away_away["gf"] if away_away["gf"] is not None else away["gf"],
            home_home["ga"] if home_home["ga"] is not None else home["ga"],
            away_away["ga"] if away_away["ga"] is not None else away["ga"],
        ) if value is not None]
        expected_total = sum(components) / max(2, len(components) / 2)
        goal_shift = clamp((expected_total - 2.55) * 0.20, -0.22, 0.22)
    else:
        goal_shift = 0.0

    score_boosts = {}
    if home["cleanSheetRate"] is not None and away["scoringRate"] is not None:
        if home["cleanSheetRate"] >= .45 and away["scoringRate"] <= .60:
            score_boosts.update({"1-0": 1.14, "2-0": 1.12})
    if away["cleanSheetRate"] is not None and home["scoringRate"] is not None:
        if away["cleanSheetRate"] >= .45 and home["scoringRate"] <= .60:
            score_boosts.update({"0-1": 1.14, "0-2": 1.12})
    if home["bttsRate"] is not None and away["bttsRate"] is not None and (home["bttsRate"] + away["bttsRate"]) / 2 >= .58:
        score_boosts.update({"1-1": 1.12, "2-1": 1.10, "1-2": 1.10, "2-2": 1.08})
    if home["over25Rate"] is not None and away["over25Rate"] is not None and (home["over25Rate"] + away["over25Rate"]) / 2 >= .60:
        score_boosts.update({"2-1": 1.12, "1-2": 1.12, "2-2": 1.10, "3-1": 1.08, "1-3": 1.08})

    is_cup = any(token in str(league) for token in ("杯", "冠军联赛", "欧罗巴", "解放者", "超级杯"))
    cup_inputs = None
    if is_cup:
        cup_inputs = {
            "ninetyMinuteSettlementSeparate": True,
            "extraTimePenaltyPath": "需与90分钟赛果分开记录",
            "rotationRisk": "未取得官方首发/轮换名单，赛前必须复核",
            "tieFormat": "当前数据未核验单回合/两回合及首回合比分",
            "varianceRule": "双方进球率、追分和首发确认后再放大4+球或爆冷尾部",
        }

    def fmt(label, stats):
        if not stats["sample"]:
            return f"{label}暂无已核验样本"
        return (f"{label}近{stats['sample']}场{stats['gf']:.2f}进/{stats['ga']:.2f}失，积分{stats['points']:.2f}/场，"
                f"进球率{stats['scoringRate']:.0%}，零封率{stats['cleanSheetRate']:.0%}，双方进球率{stats['bttsRate']:.0%}，"
                f"大于2.5球率{stats['over25Rate']:.0%}")

    summary = "；".join([fmt("主队", home), fmt("客队", away), fmt("主队主场", home_home), fmt("客队客场", away_away)])
    upset = "；".join([
        "若弱侧近况与主客场进球率不弱，保留弱侧先入球/平局路径",
        "若弱侧进球率低于50%且强侧零封率高，爆冷大球不主动放大",
        "若双方双方进球率和大于2.5球率同时偏高，保留2-2、1-3或3-1追分路径",
    ])
    return {
        "fundamentalProbabilities": probabilities,
        "fundamentalStats": {"home": home, "away": away, "homeHome": home_home, "awayAway": away_away},
        "fundamentalSummary": summary,
        "upsetTriggers": upset,
        "goalShift": goal_shift,
        "scoreBoosts": score_boosts,
        "restDays": rest,
        "cupModelInputs": cup_inputs,
        "verifiedFactors": factors,
    }


def head_to_head(match, history):
    """Build a current-home-team perspective from all retained meetings."""
    home_code, away_code = str(match.get("homeCode", "")), str(match.get("awayCode", ""))
    if not home_code or not away_code:
        return {"sample": 0, "status": "missing_team_codes", "summary": "暂无可核验的双方历史交手"}
    rows = []
    seen = set()
    for item in history:
        result = item.get("result") or {}
        if result.get("homeGoals") is None or result.get("awayGoals") is None:
            continue
        item_home, item_away = str(item.get("homeCode", "")), str(item.get("awayCode", ""))
        if {item_home, item_away} != {home_code, away_code}:
            continue
        match_id = str(item.get("matchId") or item.get("id") or f"{item.get('matchDate')}:{item_home}:{item_away}")
        if match_id in seen:
            continue
        seen.add(match_id)
        home_goals, away_goals = int(result["homeGoals"]), int(result["awayGoals"])
        if item_home == home_code:
            gf, ga = home_goals, away_goals
        else:
            gf, ga = away_goals, home_goals
        rows.append({"date": (item.get("matchDate") or item.get("kickoff", ""))[:10], "gf": gf, "ga": ga,
                     "result": "W" if gf > ga else "D" if gf == ga else "L", "league": item.get("league", ""),
                     "home": item.get("home", ""), "away": item.get("away", "")})
    rows.sort(key=lambda row: row.get("date", ""), reverse=True)
    if not rows:
        return {"sample": 0, "status": "no_verified_meetings", "summary": "暂无可核验的双方历史交手"}
    wins = sum(row["result"] == "W" for row in rows)
    draws = sum(row["result"] == "D" for row in rows)
    losses = sum(row["result"] == "L" for row in rows)
    unbeaten = losses == 0
    streak = 0
    for row in rows:
        if row["result"] == "L":
            break
        streak += 1
    summary = f"历史交手{len(rows)}场，当前主队视角{wins}胜{draws}平{losses}负；进{sum(r['gf'] for r in rows)}球、失{sum(r['ga'] for r in rows)}球"
    if unbeaten:
        summary += f"，近{streak}次交手未负"
    return {"sample": len(rows), "wins": wins, "draws": draws, "losses": losses,
            "goalsFor": sum(row["gf"] for row in rows), "goalsAgainst": sum(row["ga"] for row in rows),
            "unbeaten": unbeaten, "unbeatenStreak": streak, "lastMeetings": rows[:5], "summary": summary,
            "status": "verified_retained_results"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    source = read(ROOT / args.source)
    current = {str(m.get("matchId")): m for m in source.get("matches", [])}
    history = []
    for path in sorted(DATA.glob("sporttery_*_latest.json")) + sorted(DATA.glob("20????????.json")):
        try:
            payload = read(path)
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("date", "") >= args.date:
            continue
        history.extend(payload.get("matches", []))
    by_team = defaultdict(list)
    for match in history:
        result = match.get("result") or {}
        if not isinstance(result, dict) or result.get("homeGoals") is None:
            continue
        home, away = int(result["homeGoals"]), int(result["awayGoals"])
        match_date = (match.get("matchDate") or match.get("kickoff", ""))[:10]
        for side, team, opponent, gf, ga in (("home", match.get("homeCode"), match.get("awayCode"), home, away), ("away", match.get("awayCode"), match.get("homeCode"), away, home)):
            if team:
                by_team[str(team)].append({"date": match_date, "gf": gf, "ga": ga,
                                            "result": "W" if gf > ga else "D" if gf == ga else "L",
                                            "venue": side, "opponent": opponent, "league": match.get("league", "")})
    external_by_team = defaultdict(list)
    external_path = DATA / "external_league_history_2026.json"
    if external_path.exists():
        try:
            external_payload = read(external_path)
        except (OSError, json.JSONDecodeError):
            external_payload = {}
        for league, payload in external_payload.get("competitions", {}).items():
            for row in payload.get("matches", []):
                home, away = int(row["homeGoals"]), int(row["awayGoals"])
                for side, team, opponent, gf, ga in (("home", row.get("home"), row.get("away"), home, away), ("away", row.get("away"), row.get("home"), away, home)):
                    if team:
                        external_by_team[name_key(team)].append({"date": row.get("date", ""), "gf": gf, "ga": ga,
                                                                  "result": "W" if gf > ga else "D" if gf == ga else "L",
                                                                  "venue": side, "opponent": opponent, "league": league, "source": row.get("sourceUrl")})
    contexts = {}
    for key, match in current.items():
        home_code, away_code = str(match.get("homeCode", "")), str(match.get("awayCode", ""))
        rows = {}
        for code in (home_code, away_code):
            rows[code] = sorted(by_team.get(code, []), key=lambda x: x.get("date", ""), reverse=True)[:5]
        home_form, away_form = rows[home_code], rows[away_code]
        def form(rows):
            return "".join(row["result"] for row in rows) or "暂无已核验赛果"
        home_rows = by_team.get(home_code, []) + external_by_team.get(name_key(match.get("home")), [])
        away_rows = by_team.get(away_code, []) + external_by_team.get(name_key(match.get("away")), [])
        fundamental = fundamental_layer(match, home_rows, away_rows, args.date, match.get("league", ""))
        h2h = head_to_head(match, history)
        factors = fundamental.pop("verifiedFactors", [])
        multipliers = {"home": 1.0, "draw": 1.0, "away": 1.0}
        if fundamental["fundamentalStats"]["home"]["sample"] and fundamental["fundamentalStats"]["away"]["sample"]:
            home_points = fundamental["fundamentalStats"]["home"]["points"]
            away_points = fundamental["fundamentalStats"]["away"]["points"]
            if home_points - away_points >= 1.0: multipliers.update(home=1.04, away=.98)
            elif away_points - home_points >= 1.0: multipliers.update(home=.98, away=1.04)
        context = {
            "ranking": f"{match.get('home')} {match.get('homeRank') or '未提供'}；{match.get('away')} {match.get('awayRank') or '未提供'}",
            "homeRank": rank(match.get("homeRank")), "awayRank": rank(match.get("awayRank")),
            "recentForm": f"主队近{len(home_form)}场 {form(home_form)}；客队近{len(away_form)}场 {form(away_form)}",
            "motivation": "积分/晋级战意与杯赛轮次未从官方竞赛文件完整核验，不作硬性方向修正",
            "injuries": "未找到可核验的官方伤停或首发来源，不作方向性修正",
            "schedule": "已从历史赛果计算最近比赛与休息间隔；具体杯赛轮次、首回合比分和下一场优先级仍需官方赛程确认",
            "outcomeMultipliers": multipliers, "confidenceDelta": -2,
            **fundamental,
            "headToHead": h2h,
            "headToHeadSummary": h2h.get("summary", "暂无可核验的双方历史交手"),
            "verifiedFactors": factors, "evidenceStatus": "已接入排名、近5场进失球、主客场拆分与休息间隔；伤停、首发、战术和杯赛战意仍保持证据闸门",
            "analysisBasis": "竞彩赔率/比分矩阵作为市场层；排名、近况、进失球、主客场和赛程间隔作为基本面层；伤停、首发、战术和晋级动机未核验时不作硬修正。",
            "sources": [{"name": "Sporttery公开赛程/赔率接口", "url": "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=ttg,had,hhad,crs,hafu"}],
        }
        contexts[key] = context
    output = {"version": "public-context-v1", "generatedAt": datetime.now().isoformat(timespec="seconds"), "matches": contexts}
    (DATA / f"match_context_{args.date}.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated context for {len(contexts)} matches")

if __name__ == "__main__": main()
