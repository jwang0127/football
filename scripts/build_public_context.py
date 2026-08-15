"""Build conservative, source-linked team context from retained public feeds."""
from __future__ import annotations

import argparse, json, re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def rank(value):
    match = re.search(r"(\d+)", str(value or ""))
    return int(match.group(1)) if match else None

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
        for side, team, gf, ga in (("home", match.get("homeCode"), home, away), ("away", match.get("awayCode"), away, home)):
            if team:
                by_team[str(team)].append({"date": match.get("matchDate", ""), "gf": gf, "ga": ga, "result": "W" if gf > ga else "D" if gf == ga else "L"})
    contexts = {}
    for key, match in current.items():
        factors = ["ranking_table"]
        home_code, away_code = str(match.get("homeCode", "")), str(match.get("awayCode", ""))
        rows = {}
        for code in (home_code, away_code):
            rows[code] = sorted(by_team.get(code, []), key=lambda x: x.get("date", ""), reverse=True)[:5]
        home_form, away_form = rows[home_code], rows[away_code]
        if home_form and away_form:
            factors.append("recent_performance")
        def form(rows):
            return "".join(row["result"] for row in rows) or "暂无已核验赛果"
        hp, ap = sum(3 if x["result"] == "W" else 1 if x["result"] == "D" else 0 for x in home_form), sum(3 if x["result"] == "W" else 1 if x["result"] == "D" else 0 for x in away_form)
        multipliers = {"home": 1.0, "draw": 1.0, "away": 1.0}
        if hp - ap >= 4: multipliers.update(home=1.06, away=.96)
        elif ap - hp >= 4: multipliers.update(home=.96, away=1.06)
        context = {
            "ranking": f"{match.get('home')} {match.get('homeRank') or '未提供'}；{match.get('away')} {match.get('awayRank') or '未提供'}",
            "homeRank": rank(match.get("homeRank")), "awayRank": rank(match.get("awayRank")),
            "recentForm": f"主队近{len(home_form)}场 {form(home_form)}；客队近{len(away_form)}场 {form(away_form)}",
            "motivation": "积分/晋级战意未从公开积分榜核验，不作方向性修正",
            "injuries": "未找到可核验的官方伤停或首发来源，不作方向性修正",
            "schedule": "已检查公开历史赛果；具体联赛轮次与下一场优先级仍需官方赛程确认",
            "outcomeMultipliers": multipliers, "confidenceDelta": -2,
            "verifiedFactors": factors, "evidenceStatus": "已接入公开赛果与竞彩赛程字段；伤停、轮次/战意缺少可核验来源时保持中性",
            "sources": [{"name": "Sporttery公开赛程/赔率接口", "url": "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=ttg,had,hhad,crs,hafu"}],
        }
        contexts[key] = context
    output = {"version": "public-context-v1", "generatedAt": datetime.now().isoformat(timespec="seconds"), "matches": contexts}
    (DATA / f"match_context_{args.date}.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated context for {len(contexts)} matches")

if __name__ == "__main__": main()
