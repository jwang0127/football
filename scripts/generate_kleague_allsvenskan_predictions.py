#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TARGET_LEAGUES = {"韩国职业联赛", "瑞典超级联赛"}
MODEL_VERSION = "world-cup-v3-adapted-league-odds-20260705"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def odd(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def implied_1x2(had: dict[str, Any]) -> dict[str, float]:
    raw = {key: 1 / odd(had[key]) for key in ("home", "draw", "away") if odd(had.get(key))}
    total = sum(raw.values())
    if total <= 0:
        return {"home": 0.34, "draw": 0.30, "away": 0.36}
    return {key: raw.get(key, 0) / total for key in ("home", "draw", "away")}


def rank_number(rank_text: str) -> int | None:
    digits = "".join(ch for ch in str(rank_text) if ch.isdigit())
    return int(digits) if digits else None


def normalize_score_key(score: str) -> str:
    return str(score).replace(":", "-")


def score_total(score: str) -> int:
    left, right = normalize_score_key(score).split("-")
    return int(left) + int(right)


def score_direction(score: str) -> str:
    left, right = normalize_score_key(score).split("-")
    h, a = int(left), int(right)
    if h > a:
        return "home"
    if h < a:
        return "away"
    return "draw"


def result_label(direction: str) -> str:
    return {"home": "主胜", "draw": "平", "away": "客胜"}[direction]


def total_goal_candidates(ttg: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for idx in range(8):
        key = f"s{idx}"
        value = odd(ttg.get(key))
        if value:
            rows.append({"goals": "7+" if idx == 7 else str(idx), "odds": value})
    return sorted(rows, key=lambda row: row["odds"])


def crs_candidates(crs: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, value in crs.items():
        if "-" not in key:
            continue
        parsed = odd(value)
        if parsed:
            rows.append({"score": key, "odds": parsed, "total": score_total(key), "direction": score_direction(key)})
    return sorted(rows, key=lambda row: row["odds"])


def hafu_key(half: str, full: str) -> str:
    return {"home": "h", "draw": "d", "away": "a"}[half] + {"home": "h", "draw": "d", "away": "a"}[full]


def half_from_score(score: str) -> str:
    total = score_total(score)
    full = score_direction(score)
    if total <= 1:
        return "draw"
    if full == "draw":
        return "draw"
    return full if total >= 3 else "draw"


def product_odds(rows: list[dict[str, Any]]) -> float | None:
    product = 1.0
    for row in rows:
        if row.get("odds") is None:
            return None
        product *= float(row["odds"])
    return product


def fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def pick_match(match: dict[str, Any]) -> dict[str, Any]:
    odds = match["odds"]
    had = odds.get("had") or {}
    hhad = odds.get("hhad") or {}
    ttg = odds.get("ttg") or {}
    crs = odds.get("crs") or {}
    hafu = odds.get("hafu") or {}

    probs = implied_1x2(had)
    home_rank = rank_number(match.get("homeRank", ""))
    away_rank = rank_number(match.get("awayRank", ""))
    rank_note = ""
    if home_rank and away_rank:
      rank_note = f"排名信号：主队{home_rank}，客队{away_rank}。"

    full = max(probs, key=probs.get)
    ttg_top = total_goal_candidates(ttg)
    crs_top = crs_candidates(crs)
    main_pool = [row for row in crs_top if row["direction"] == full]
    if full != "draw" and probs.get("draw", 0) >= 0.28:
        main_pool = [row for row in crs_top if row["direction"] in {full, "draw"}]
    if not main_pool:
        main_pool = crs_top

    main_score = main_pool[0]["score"]
    main_direction = score_direction(main_score)
    if main_direction != full and main_direction == "draw":
        full = "draw"
    backups: list[str] = []
    for row in main_pool[1:] + crs_top:
        if row["score"] != main_score and row["score"] not in backups:
            backups.append(row["score"])
        if len(backups) == 2:
            break

    upset_direction = "draw" if full != "draw" else ("away" if probs["home"] >= probs["away"] else "home")
    upset_pool = [row for row in crs_top if row["direction"] == upset_direction and row["score"] != main_score]
    upset_score = upset_pool[0]["score"] if upset_pool else backups[-1]

    goal_pick = str(score_total(main_score))
    if ttg_top:
        market_goal = ttg_top[0]["goals"]
        if market_goal != goal_pick and ttg_top[0]["odds"] + 0.25 < (odd(ttg.get(f"s{goal_pick}")) or 99):
            goal_pick = market_goal
    goal_candidates = [row["goals"] for row in ttg_top[:3]]

    half = half_from_score(main_score)
    hafu_pick = hafu_key(half, full)
    score_odds = odd(crs.get(main_score))
    goal_key = "s7" if goal_pick == "7+" else f"s{goal_pick}"
    goal_odds = odd(ttg.get(goal_key))
    hafu_odds = odd(hafu.get(hafu_pick))

    favorite_gap = abs(probs["home"] - probs["away"])
    confidence = "高" if favorite_gap >= 0.22 and score_odds and score_odds <= 8 else "中"
    if favorite_gap < 0.10 or probs["draw"] >= 0.30:
        confidence = "中低"

    hhad_text = ""
    if hhad.get("home") and hhad.get("away"):
        hhad_text = f"让球池 {hhad.get('home')}/{hhad.get('draw')}/{hhad.get('away')}，用于压制过热穿盘。"

    return {
        "id": match["id"],
        "matchNumStr": match["matchNumStr"],
        "league": match["league"],
        "kickoff": match["kickoff"],
        "home": match["home"],
        "away": match["away"],
        "homeRank": match.get("homeRank"),
        "awayRank": match.get("awayRank"),
        "modelVersion": MODEL_VERSION,
        "direction": full,
        "directionText": result_label(full),
        "probabilities": {key: round(value, 3) for key, value in probs.items()},
        "totalGoals": goal_pick,
        "totalGoalCandidates": goal_candidates,
        "mainScore": main_score,
        "backupScores": backups,
        "upsetScore": upset_score,
        "halfDirection": half,
        "hafuPick": hafu_pick,
        "confidence": confidence,
        "odds": odds,
        "parlay": {
            "score": {"pick": main_score, "odds": score_odds, "updatedAt": crs.get("updatedAt")},
            "goals": {"pick": goal_pick, "odds": goal_odds, "updatedAt": ttg.get("updatedAt")},
            "hafu": {"pick": hafu_pick, "label": f"{result_label(half)}/{result_label(full)}", "odds": hafu_odds, "updatedAt": hafu.get("updatedAt")},
        },
        "marketRead": [
            f"胜平负隐含概率：主胜{probs['home']:.1%} / 平{probs['draw']:.1%} / 客胜{probs['away']:.1%}。",
            f"总进球低赔序列：{', '.join(row['goals'] + '球@' + fmt(row['odds']) for row in ttg_top[:3])}。",
            f"比分低赔序列：{', '.join(row['score'] + '@' + fmt(row['odds']) for row in crs_top[:5])}。",
            rank_note,
            hhad_text,
        ],
    }


def build_parlays(matches: list[dict[str, Any]]) -> dict[str, Any]:
    sorted_by_conf = sorted(matches, key=lambda item: {"高": 0, "中": 1, "中低": 2}.get(item["confidence"], 3))
    goals_matches = sorted_by_conf[:3]
    score_safe = sorted_by_conf[:3]
    score_upset = sorted(matches, key=lambda item: item["probabilities"]["draw"], reverse=True)[:3]

    def rows(kind: str, selected: list[dict[str, Any]], upset: bool = False) -> list[dict[str, Any]]:
        out = []
        for item in selected:
            if kind == "score":
                pick = item["upsetScore"] if upset else item["mainScore"]
                odds_value = odd(item["odds"]["crs"].get(pick))
                updated = item["odds"]["crs"].get("updatedAt")
            elif kind == "goals":
                pick = item["totalGoals"]
                key = "s7" if pick == "7+" else f"s{pick}"
                odds_value = odd(item["odds"]["ttg"].get(key))
                updated = item["odds"]["ttg"].get("updatedAt")
            else:
                pick = item["parlay"]["hafu"]["label"]
                odds_value = item["parlay"]["hafu"]["odds"]
                updated = item["parlay"]["hafu"]["updatedAt"]
            out.append({"match": f"{item['home']} vs {item['away']}", "pick": pick, "odds": odds_value, "updatedAt": updated})
        return out

    modules = {
        "totalGoals": rows("goals", goals_matches),
        "scoreSafe": rows("score", score_safe),
        "scoreUpset": rows("score", score_upset, upset=True),
        "hafu": rows("hafu", goals_matches),
    }
    for value in modules.values():
        for row in value:
            row["oddsText"] = fmt(row["odds"])
        value.append({"match": "理论乘积", "pick": "", "odds": product_odds(value), "oddsText": fmt(product_odds(value)), "updatedAt": ""})
    return modules


def render_table(rows: list[dict[str, Any]]) -> str:
    return "".join(
        f"<tr><td>{esc(row['match'])}</td><td>{esc(row['pick'])}</td><td>{esc(row['oddsText'])}</td><td>{esc(row.get('updatedAt',''))}</td></tr>"
        for row in rows
    )


def render_html(payload: dict[str, Any]) -> str:
    cards = []
    for item in payload["matches"]:
        reads = "".join(f"<li>{esc(text)}</li>" for text in item["marketRead"] if text)
        league_class = "kleague" if item["league"] == "韩国职业联赛" else "allsvenskan"
        league_short = "韩职" if item["league"] == "韩国职业联赛" else "瑞超"
        cards.append(f"""
        <section class="card match-card {league_class}">
          <div class="title-row"><h2>{esc(item['matchNumStr'])} {esc(item['home'])} vs {esc(item['away'])}</h2><span class="league-badge">{league_short}</span></div>
          <div class="grid">
            <div><span>方向</span><strong>{esc(item['directionText'])}</strong></div>
            <div><span>总进球</span><strong>{esc(item['totalGoals'])}</strong></div>
            <div><span>主比分</span><strong>{esc(item['mainScore'])}</strong></div>
            <div><span>冷门比分</span><strong>{esc(item['upsetScore'])}</strong></div>
          </div>
          <p class="muted">{esc(item['league'])}，北京时间 {esc(item['kickoff'])}，{esc(item['homeRank'])} vs {esc(item['awayRank'])}，信心：{esc(item['confidence'])}</p>
          <p>比分池：{esc(item['mainScore'])} / {esc(' / '.join(item['backupScores']))}，防冷：{esc(item['upsetScore'])}。总进球候选：{esc(' / '.join(item['totalGoalCandidates']))}。</p>
          <ul>{reads}</ul>
        </section>""")

    parlay = payload["parlays"]
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>20260705 韩职与瑞超预测</title>
<style>
body{{margin:0;background:#f6f7f8;color:#17201d;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.65}}
header,main{{max-width:1120px;margin:auto;padding:22px 16px}}
header{{border-bottom:1px solid #d9dfdd;background:#fff;position:sticky;top:0}}
h1{{margin:0;font-size:30px}} h2{{margin:0 0 10px;font-size:22px}}
.muted{{color:#5f6f69}} .card{{background:#fff;border:1px solid #d9dfdd;border-radius:8px;padding:18px;margin:16px 0}}
.match-card{{border-left-width:8px}}
.match-card.kleague{{background:#f5fbff;border-color:#b8ddf4;border-left-color:#1683c7}}
.match-card.allsvenskan{{background:#fff9ed;border-color:#f0d7a6;border-left-color:#d99416}}
.title-row{{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}}
.league-badge{{display:inline-flex;align-items:center;justify-content:center;min-width:52px;padding:6px 10px;border-radius:999px;font-weight:800;color:#fff}}
.kleague .league-badge{{background:#1683c7}}
.allsvenskan .league-badge{{background:#d99416}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0}}
.grid div{{border:1px solid #d9dfdd;border-radius:8px;padding:12px;background:#fbfcfc}}
.grid span{{display:block;color:#63736d;font-size:13px}} .grid strong{{display:block;font-size:24px;color:#0f6b4f}}
table{{width:100%;border-collapse:collapse;min-width:680px}} th,td{{border-bottom:1px solid #d9dfdd;padding:10px;text-align:left}} th{{background:#eef4f2}}
.table{{overflow-x:auto}} .warn{{border-left:4px solid #d99120}}
@media(max-width:760px){{.grid{{grid-template-columns:1fr 1fr}}}}
</style>
</head>
<body>
<header><h1>20260705 韩职与瑞超预测</h1><p class="muted">模型：世界杯 v3 赔率/EV/比分池流程迁移版；竞彩数据源：Sporttery getMatchCalculatorV1，更新时间 {esc(payload['lastUpdateTime'])}。</p></header>
<main>
<section class="card warn"><strong>明天核对：</strong>20260706 的 Sporttery 返回场次中没有韩职或瑞超，本页只生成 20260705 目标联赛 6 场。</section>
<section class="card"><h2>三个串</h2>
<h3>总进球三串一</h3><div class="table"><table><thead><tr><th>比赛</th><th>选择</th><th>赔率</th><th>更新</th></tr></thead><tbody>{render_table(parlay['totalGoals'])}</tbody></table></div>
<h3>比分三串一（稳胆）</h3><div class="table"><table><thead><tr><th>比赛</th><th>选择</th><th>赔率</th><th>更新</th></tr></thead><tbody>{render_table(parlay['scoreSafe'])}</tbody></table></div>
<h3>比分三串一（爆冷）</h3><div class="table"><table><thead><tr><th>比赛</th><th>选择</th><th>赔率</th><th>更新</th></tr></thead><tbody>{render_table(parlay['scoreUpset'])}</tbody></table></div>
<h3>半全场三串一</h3><div class="table"><table><thead><tr><th>比赛</th><th>选择</th><th>赔率</th><th>更新</th></tr></thead><tbody>{render_table(parlay['hafu'])}</tbody></table></div>
</section>
{''.join(cards)}
<section class="card"><h2>来源</h2><ul><li>竞彩赔率页面：https://m.sporttery.cn/mjc/jsq/zqzjq/</li><li>接口快照：data/sporttery_20260705.json、data/sporttery_20260706.json</li><li>世界杯模型参考：C:\\Users\\Administrator\\Documents\\世界杯预测\\knockout\\knockout_prediction_model_v3.md</li></ul><p class="muted">以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议。</p></section>
</main>
</body></html>"""


def main() -> int:
    today = read_json(DATA / "sporttery_20260705.json")
    tomorrow = read_json(DATA / "sporttery_20260706.json")
    matches = [pick_match(item) for item in today["matches"] if item.get("league") in TARGET_LEAGUES]
    payload = {
        "date": "20260705",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "modelVersion": MODEL_VERSION,
        "lastUpdateTime": today.get("lastUpdateTime"),
        "todayTargetMatchCount": len(matches),
        "tomorrowTargetMatchCount": sum(1 for item in tomorrow["matches"] if item.get("league") in TARGET_LEAGUES),
        "source": {
            "oddsPage": "https://m.sporttery.cn/mjc/jsq/zqzjq/",
            "api": "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=ttg,had,hhad,crs,hafu",
            "modelReference": r"C:\Users\Administrator\Documents\世界杯预测\knockout\knockout_prediction_model_v3.md",
        },
        "matches": matches,
        "parlays": build_parlays(matches),
    }
    write_json(DATA / "predictions_20260705.json", payload)
    page = render_html(payload)
    (ROOT / "20260705").mkdir(exist_ok=True)
    (ROOT / "20260705" / "index.html").write_text(page, encoding="utf-8")
    (ROOT / "20260705" / "predict_20260705.html").write_text(page, encoding="utf-8")
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    print(f"Generated {len(matches)} target predictions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
