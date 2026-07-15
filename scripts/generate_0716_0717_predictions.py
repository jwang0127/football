#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from score_pool_model import calibrated_confidence, calibrated_score_pool

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "20260716_0717"
MODEL_VERSION = "non-worldcup-multileague-20260715-v1"
DISCLAIMER = "以上仅为公开信息整理后的娱乐分析，不构成任何购买彩票建议，请理性参考。"

LEAGUE_STYLES = {
    "欧洲冠军联赛": {"class": "ucl", "color": "#3157d5", "label": "欧冠资格赛"},
    "挪威超级联赛": {"class": "nor", "color": "#7a43b6", "label": "挪超"},
    "巴西甲级联赛": {"class": "bra", "color": "#17854b", "label": "巴甲"},
    "美国职业大联盟": {"class": "mls", "color": "#d56b18", "label": "美职"},
}

CONTEXT = {
    "201-20260716": "欧冠资格赛淘汰路径；克拉克斯维克为客场市场优势方，首回合需防主队保守拖平。",
    "202-20260716": "欧冠资格赛淘汰路径；阿拉木图凯拉特客胜优势清晰，但长途客场提高1-1保护。",
    "201-20260717": "挪超官方赛程确认在Intility Arena进行；两队竞彩排名11/12，历史14次交锋瓦勒伦加7胜4平3负。",
    "205-20260717": "巴甲第19轮、世界杯暂停后重启；博塔弗戈主场且排名领先，重启战降低穿盘置信。",
    "206-20260717": "巴甲第19轮重启；双方排名接近且胜平负价格集中，低比分与平局权重较高。",
    "207-20260717": "美职重启后的加拿大德比；两队均在季后赛线外附近，德比波动与双方进球风险并存。",
    "208-20260717": "美职重启；温哥华排名第1、芝加哥第3，强强对话不把客胜优势等同于零封。",
    "209-20260717": "美职重启；圣路易斯主胜低赔，对手排名靠后，保留主胜扩大比分尾部。",
    "210-20260717": "卡斯卡迪亚德比；西雅图西区第6、波特兰第13，双方重启前均两连败，波特兰更换临时主帅。",
}

SOURCES = [
    {"name": "Sporttery官方接口", "url": "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=ttg,had,hhad,crs,hafu"},
    {"name": "UEFA资格赛赛程", "url": "https://www.uefa.com/uefachampionsleague/"},
    {"name": "挪威足协赛程", "url": "https://www.fotball.no/eliteserien/"},
    {"name": "巴西足协赛程", "url": "https://www.cbf.com.br/futebol-brasileiro/competicoes/campeonato-brasileiro-serie-a"},
    {"name": "MLS官方赛程与前瞻", "url": "https://www.mlssoccer.com/news/matchday-16-watch-guide-what-to-know-as-mls-returns"},
]


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def number(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def implied(had: dict[str, Any]) -> dict[str, float]:
    raw = {key: 1 / number(had[key]) for key in ("home", "draw", "away") if number(had.get(key))}
    total = sum(raw.values())
    return {key: raw.get(key, 0) / total for key in ("home", "draw", "away")}


def score_rows(crs: dict[str, Any]) -> list[tuple[str, float]]:
    rows = [(key, number(value)) for key, value in crs.items() if "-" in key and number(value)]
    return sorted(rows, key=lambda row: row[1])


def goal_rows(ttg: dict[str, Any]) -> list[tuple[str, float]]:
    rows = []
    for i in range(8):
        value = number(ttg.get(f"s{i}"))
        if value:
            rows.append(("7+" if i == 7 else str(i), value))
    return sorted(rows, key=lambda row: row[1])


def direction(score: str) -> str:
    home, away = (int(x) for x in score.split("-"))
    return "home" if home > away else "away" if home < away else "draw"


def direction_label(code: str) -> str:
    return {"home": "主胜", "draw": "平", "away": "客胜"}[code]


def load_matches() -> list[dict[str, Any]]:
    matches = []
    for date in ("20260716", "20260717"):
        for match in read(DATA / f"sporttery_{date}_latest.json")["matches"]:
            if "世界杯" in match.get("league", ""):
                continue
            if match.get("league") not in LEAGUE_STYLES:
                continue
            matches.append(match)
    return matches


def predict(match: dict[str, Any]) -> dict[str, Any]:
    odds = match["odds"]
    probs = implied(odds["had"])
    scores = score_rows(odds["crs"])
    goals = goal_rows(odds["ttg"])
    main, backups, tails, reason = calibrated_score_pool(scores, probs, goals)
    pick_direction = direction(main)
    market_direction = max(probs, key=probs.get)
    # Score selection can protect a draw; direction remains independently calibrated to 1X2.
    if probs[market_direction] - probs[pick_direction] >= 0.08:
        pick_direction = market_direction
    score_pool = [main, *backups]
    if direction(main) != pick_direction:
        aligned = next((score for score in score_pool if direction(score) == pick_direction), None)
        if aligned:
            score_pool.remove(aligned)
            main, backups = aligned, score_pool
    confidence = calibrated_confidence(probs, pick_direction)
    if match["league"] in {"巴西甲级联赛", "美国职业大联盟"}:
        confidence = max(35, confidence - 4)  # long World Cup pause/restart uncertainty
    goal_candidates = [row[0] for row in goals[:3]]
    goal_pick = goal_candidates[0]
    key = f"{match['id']}-{match['matchDate'].replace('-', '')}"
    return {
        "id": match["id"], "matchNumStr": match["matchNumStr"], "matchDate": match["matchDate"],
        "kickoff": match["kickoff"], "league": match["league"], "leagueStyle": LEAGUE_STYLES[match["league"]],
        "home": match["home"], "away": match["away"], "homeRank": match.get("homeRank", ""), "awayRank": match.get("awayRank", ""),
        "probabilities": {k: round(v, 4) for k, v in probs.items()},
        "direction": pick_direction, "directionText": direction_label(pick_direction),
        "mainScore": main, "backupScores": backups, "tailRiskScores": tails,
        "totalGoals": goal_pick, "goalCandidates": goal_candidates,
        "confidenceScore": confidence, "confidence": "高" if confidence >= 65 else "中" if confidence >= 52 else "中低",
        "reason": reason, "context": CONTEXT.get(key, "按官方赛程、竞彩赔率与比分矩阵交叉校准。"),
        "odds": odds,
    }


def leg(match: dict[str, Any], market: str) -> dict[str, Any]:
    if market == "had":
        pick = match["directionText"]
        key = {"主胜": "home", "平": "draw", "客胜": "away"}[pick]
        odd = number(match["odds"]["had"].get(key))
        probability = match["probabilities"][key]
    elif market == "ttg":
        pick = match["totalGoals"]
        key = "s7" if pick == "7+" else f"s{pick}"
        odd = number(match["odds"]["ttg"].get(key))
        probability = min(0.42, 1 / odd) if odd else 0
    else:
        pick = match["mainScore"]
        odd = number(match["odds"]["crs"].get(pick))
        probability = min(0.24, 1 / odd) if odd else 0
    return {"match": f"{match['matchNumStr']} {match['home']} vs {match['away']}", "market": market, "marketText": {"had":"胜平负","ttg":"总进球","crs":"比分"}[market], "pick": pick, "odds": odd, "probability": probability}


def combo(name: str, legs: list[dict[str, Any]]) -> dict[str, Any]:
    product = math.prod(row["odds"] for row in legs if row["odds"])
    joint = math.prod(row["probability"] for row in legs)
    geometric = joint ** (1 / len(legs))
    trust = round(100 * geometric * (0.94 ** (len(legs) - 1)))
    return {"name": name, "legs": legs, "productOdds": round(product, 2), "trustScore": max(1, min(88, trust))}


def build_combos(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_conf = sorted(matches, key=lambda m: m["confidenceScore"], reverse=True)
    by_goal = sorted(matches, key=lambda m: number(m["odds"]["ttg"].get("s7" if m["totalGoals"] == "7+" else f"s{m['totalGoals']}")) or 99)
    by_score = sorted(matches, key=lambda m: number(m["odds"]["crs"].get(m["mainScore"])) or 99)
    rows = [
        combo("胜平负稳健二串一", [leg(by_conf[0], "had"), leg(by_conf[1], "had")]),
        combo("胜平负均衡二串一", [leg(by_conf[2], "had"), leg(by_conf[3], "had")]),
        combo("胜平负三串一", [leg(by_conf[0], "had"), leg(by_conf[1], "had"), leg(by_conf[2], "had")]),
        combo("总进球稳健二串一", [leg(by_goal[0], "ttg"), leg(by_goal[1], "ttg")]),
        combo("总进球均衡二串一", [leg(by_goal[2], "ttg"), leg(by_goal[3], "ttg")]),
        combo("总进球三串一", [leg(by_goal[0], "ttg"), leg(by_goal[1], "ttg"), leg(by_goal[2], "ttg")]),
        combo("比分双选一", [leg(by_score[0], "crs")]),
        combo("比分双选二", [leg(by_score[1], "crs")]),
        combo("比分二串一高风险", [leg(by_score[0], "crs"), leg(by_score[1], "crs")]),
        combo("混合稳健三串一", [leg(by_conf[0], "had"), leg(by_conf[1], "had"), leg(by_goal[0], "ttg")]),
        combo("混合均衡三串一", [leg(by_conf[2], "had"), leg(by_goal[1], "ttg"), leg(by_score[0], "crs")]),
        combo("混合进取三串一", [leg(by_conf[3], "had"), leg(by_goal[2], "ttg"), leg(by_score[1], "crs")]),
    ]
    return sorted(rows, key=lambda row: row["trustScore"], reverse=True)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render(payload: dict[str, Any]) -> str:
    legend = "".join(f'<span style="--c:{s["color"]}">{esc(s["label"])}</span>' for s in LEAGUE_STYLES.values())
    combo_cards = []
    for rank, item in enumerate(payload["combos"], 1):
        trs = "".join(f'<tr><td>{esc(x["match"])}</td><td>{esc(x["marketText"])}</td><td>{esc(x["pick"])}</td><td>{x["odds"]:.2f}</td></tr>' for x in item["legs"])
        combo_cards.append(f'<section class="combo"><h3>#{rank} {esc(item["name"])} <b>{item["trustScore"]}/100</b></h3><table><tbody>{trs}</tbody></table><p>理论组合赔率：{item["productOdds"]:.2f}</p></section>')
    match_cards = []
    for m in payload["matches"]:
        p = m["probabilities"]
        pool = " / ".join([m["mainScore"], *m["backupScores"]])
        tails = " / ".join(m["tailRiskScores"]) or "无额外尾部入选"
        match_cards.append(f'''<section class="match {m['leagueStyle']['class']}" style="--league:{m['leagueStyle']['color']}"><div class="title"><h3>{esc(m['matchNumStr'])} {esc(m['home'])} vs {esc(m['away'])}</h3><span>{esc(m['leagueStyle']['label'])}</span></div><div class="grid"><div><small>胜平负</small><strong>{esc(m['directionText'])}</strong></div><div><small>总进球</small><strong>{esc(m['totalGoals'])}</strong></div><div><small>主比分</small><strong>{esc(m['mainScore'])}</strong></div><div><small>信任度</small><strong>{m['confidenceScore']}</strong></div></div><p>比分池：{esc(pool)}；尾部审计：{esc(tails)}；总进球候选：{esc(' / '.join(m['goalCandidates']))}</p><p>隐含概率：主 {p['home']:.1%} / 平 {p['draw']:.1%} / 客 {p['away']:.1%}；排名：{esc(m['homeRank'] or '-')} / {esc(m['awayRank'] or '-')}</p><p><b>信息面：</b>{esc(m['context'])}</p><p><b>模型解释：</b>{esc(m['reason'])}</p></section>''')
    sources = "".join(f'<li><a href="{esc(x["url"])}">{esc(x["name"])}</a></li>' for x in payload["sources"])
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>0716-0717 非世界杯足球预测</title><style>body{{margin:0;background:#f3f6f9;color:#19232d;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.65}}header,main{{max-width:1180px;margin:auto;padding:22px 16px}}header{{background:#fff;border-bottom:1px solid #d8e0e8}}h1{{margin:0}}.legend span{{display:inline-block;margin:5px 8px 5px 0;padding:5px 10px;border-left:7px solid var(--c);background:#eef2f5;border-radius:5px}}.match,.combo,.notice{{background:#fff;border:1px solid #d8e0e8;border-radius:9px;padding:17px;margin:15px 0}}.match{{border-left:9px solid var(--league)}}.title{{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}}.title span{{background:var(--league);color:#fff;padding:4px 10px;border-radius:999px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}}.grid div{{background:#f7f9fb;padding:10px;border-radius:6px}}small{{display:block;color:#687681}}strong{{font-size:22px}}.combo h3{{display:flex;justify-content:space-between}}.combo b{{color:#0a7142}}table{{width:100%;border-collapse:collapse}}td{{padding:7px;border-bottom:1px solid #e3e8ec}}a{{color:#175f9e}}@media(max-width:700px){{.grid{{grid-template-columns:1fr 1fr}}.combo{{overflow:auto}}}}</style></head><body><header><h1>0716–0717 非世界杯足球预测</h1><p>共 {len(payload['matches'])} 场；官方赔率更新时间截至 {esc(payload['oddsUpdatedAt'])}；世界杯已排除。</p><div class="legend">{legend}</div></header><main><section class="notice"><h2>串关信任度排序</h2><p>信任度用于模型内部横向排序，并非命中概率；比分组合天然高风险。</p></section>{''.join(combo_cards)}<h2>逐场预测</h2>{''.join(match_cards)}<section class="notice"><h2>来源</h2><ul>{sources}</ul><p>{DISCLAIMER}</p></section></main></body></html>'''


def main() -> None:
    matches = [predict(m) for m in load_matches()]
    if len(matches) != 9:
        raise SystemExit(f"Expected 9 non-World-Cup matches, got {len(matches)}")
    updated = max(pool.get("updatedAt", "") for m in matches for pool in m["odds"].values() if isinstance(pool, dict))
    payload = {"modelVersion": MODEL_VERSION, "generatedAt": datetime.now().isoformat(timespec="seconds"), "dates": ["2026-07-16", "2026-07-17"], "worldCupExcluded": True, "oddsUpdatedAt": updated, "leagueStyles": LEAGUE_STYLES, "matches": matches, "combos": build_combos(matches), "sources": SOURCES, "disclaimer": DISCLAIMER}
    DATA.joinpath("predictions_20260716_0717.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT.mkdir(exist_ok=True)
    page = render(payload)
    OUT.joinpath("index.html").write_text(page, encoding="utf-8")
    OUT.joinpath("predict_20260716_0717.html").write_text(page, encoding="utf-8")
    ROOT.joinpath("index.html").write_text(page, encoding="utf-8")
    print(f"Generated {len(matches)} matches and {len(payload['combos'])} ranked combos")


if __name__ == "__main__":
    main()
