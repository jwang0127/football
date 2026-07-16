#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import math
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any

from score_pool_model import calibrated_confidence, calibrated_score_pool

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "20260717"
MODEL_VERSION = "non-worldcup-multileague-20260717-v3"
MIN_COMBO_ODDS = 10.0
DISCLAIMER = "以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。"

LEAGUE_STYLES = {
    "欧罗巴联赛": {"class": "uel", "color": "#d85b17", "label": "欧联资格赛"},
    "欧洲冠军联赛": {"class": "ucl", "color": "#3157d5", "label": "欧冠资格赛"},
    "挪威超级联赛": {"class": "nor", "color": "#7a43b6", "label": "挪超"},
    "巴西甲级联赛": {"class": "bra", "color": "#17854b", "label": "巴甲"},
    "美国职业大联盟": {"class": "mls", "color": "#d56b18", "label": "美职"},
}

CONTEXT = {
    "202-20260717": "欧联资格赛首回合德里城客场2-3落后，回到主场必须主动追分；索菲亚中央陆军方向占优，但比赛被拉开放大双方进球与1-2、2-2路径。",
    "203-20260717": "欧联资格赛首回合费伦茨瓦罗斯客场2-1领先，回到主场且主胜低至1.25；保留控节奏小胜，同时覆盖对手压出后的2-0、3-1。",
    "204-20260717": "欧联资格赛首回合日利纳客场0-2落后，主队必须追分；海杜克客胜为市场主方向，追分空间支持0-1、1-2及更高尾部。",
    "201-20260716": "欧冠资格赛淘汰路径；克拉克斯维克为客场市场优势方，首回合需防主队保守拖平。",
    "202-20260716": "欧冠资格赛淘汰路径；阿拉木图凯拉特客胜优势清晰，但长途客场提高1-1保护。",
    "201-20260717": "挪足协确认在Intility Arena进行；两队排名11/12，奥勒松7月11日2-2战平莫尔德，最新主胜1.50仍是锚点但保留1-1。",
    "205-20260717": "巴甲世界杯暂停后重启；博塔弗戈最新主胜1.81，主场倾向明确，但长暂停降低大胜确定性。",
    "206-20260717": "巴甲重启；维多利亚最新主胜2.12，价格仍集中，低比分和平局保护不能删除。",
    "207-20260717": "加拿大德比；多伦多7人确定缺阵、5人存疑且萨金特大腿伤存疑，蒙特利尔最新主胜1.92。",
    "208-20260717": "温哥华西区领跑但Gauld等5人缺阵；芝加哥可能迎来莱万首秀。排名优势、伤停与新援变量相互抵消，平局升为主路径。",
    "209-20260717": "圣路易斯最新主胜1.30；但Bürki等3人存疑，Durkin停赛、Pompeu伤缺，保留主胜同时下调零封大胜权重。",
    "210-20260717": "西雅图最新主胜1.34；此前连续两场被零封且进球仅17个，波特兰两连败、换临时主帅且Chara伤缺，德比主胜保留但总进球下调。",
}

COMPLETED_RESULTS = [
    {
        "key": "201-20260716", "match": "周三201 比森阿泰尔 vs 克拉克斯维克", "score": "1-2",
        "aggregate": "2-4，克拉克斯维克晋级", "directionHit": True, "goalHit": True,
        "scoreHit": "保护比分1-2命中",
        "lesson": "客胜与3球正确；首回合领先方遇到主队追分时，反击扩大路径仍需保留。",
    },
    {
        "key": "202-20260716", "match": "周三202 苏捷斯卡 vs 阿拉木图凯拉特", "score": "0-2",
        "aggregate": "总比分1-4，阿拉木图凯拉特晋级", "directionHit": True, "goalHit": False,
        "scoreHit": "保护比分0-2命中",
        "lesson": "客胜方向和0-2保护命中，3球主选失误；领先方仍可能在下半场借实力、红牌和点球扩大，不能机械等同于守和。",
    },
]

MANUAL_OVERRIDES = {
    "208-20260717": {
        "direction": "draw", "mainScore": "1-1", "backupScores": ["1-2", "2-1", "0-1", "2-2"],
        "totalGoals": "3", "goalCandidates": ["3", "2", "4"], "confidenceDelta": -7,
        "reason": "温哥华实力与排名占优，但核心伤停较多；芝加哥新援首秀变量提高主队进球与平局权重。",
    },
    "210-20260717": {
        "direction": "home", "mainScore": "1-0", "backupScores": ["2-0", "1-1", "2-1", "0-1"],
        "totalGoals": "2", "goalCandidates": ["2", "3", "1"], "confidenceDelta": -3,
        "reason": "主胜赔率继续走低，但西雅图连续两场零进球；德比和重启不确定性支持1-0/2-0而非机械追3球。",
    },
}

SOURCES = [
    {"name": "Sporttery官方接口", "url": "https://webapi.sporttery.cn/gateway/uniform/football/getMatchCalculatorV1.qry?channel=c&poolCode=ttg,had,hhad,crs,hafu"},
    {"name": "UEFA欧联资格赛官方赛程", "url": "https://www.uefa.com/uefaeuropaleague/accesslist/"},
    {"name": "挪威足协赛程", "url": "https://www.fotball.no/eliteserien/"},
    {"name": "巴西足协第19轮官方赛程", "url": "https://www.cbf.com.br/futebol-brasileiro/noticias/campeonato-brasileiro-serie-a/a/brasileirao-de-volta-confira-o-retrospecto-dos-confrontos-da-19-rodada"},
    {"name": "MLS官方7月16日赛程", "url": "https://www.mlssoccer.com/news/mls-anuncia-el-calendario-completo-de-la-temporada-regular-2026"},
    {"name": "MLS官方复赛前瞻", "url": "https://www.mlssoccer.com/news/matchday-16-watch-guide-what-to-know-as-mls-returns"},
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
    return [
        match for match in read(DATA / "sporttery_20260717_latest.json")["matches"]
        if "世界杯" not in match.get("league", "") and match.get("league") in LEAGUE_STYLES
    ]


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
    result = {
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
    override = MANUAL_OVERRIDES.get(key)
    if override:
        result["direction"] = override["direction"]
        result["directionText"] = direction_label(override["direction"])
        result["mainScore"] = override["mainScore"]
        result["backupScores"] = override["backupScores"]
        result["totalGoals"] = override["totalGoals"]
        result["goalCandidates"] = override["goalCandidates"]
        result["confidenceScore"] = max(25, min(82, result["confidenceScore"] + override["confidenceDelta"]))
        result["confidence"] = "高" if result["confidenceScore"] >= 65 else "中" if result["confidenceScore"] >= 52 else "中低"
        result["reason"] = override["reason"]
    return result


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
    market_names = {"had": "胜平负", "ttg": "总进球", "crs": "比分"}
    rows = []
    for market in ("had", "ttg", "crs"):
        candidates = [leg(match, market) for match in matches]
        candidates = [item for item in candidates if item["odds"] and item["probability"]]
        market_rows = []
        max_legs = 5 if market == "had" else 3
        for size in range(2, max_legs + 1):
            for selected in combinations(candidates, size):
                item = combo(f"{market_names[market]}{size}串一", list(selected))
                if item["productOdds"] >= MIN_COMBO_ODDS:
                    item["category"] = market
                    market_rows.append(item)
        # 每个玩法保留置信度最高的三个，且避免完全重复。
        rows.extend(sorted(market_rows, key=lambda item: (-item["trustScore"], item["productOdds"]))[:3])
    rows = sorted(rows, key=lambda item: (-item["trustScore"], item["productOdds"]))
    for rank, item in enumerate(rows, 1):
        item["rank"] = rank
    return rows


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def render(payload: dict[str, Any]) -> str:
    active_leagues = dict.fromkeys(match["league"] for match in payload["matches"])
    legend = "".join(f'<span style="--c:{LEAGUE_STYLES[name]["color"]}">{esc(LEAGUE_STYLES[name]["label"])}</span>' for name in active_leagues)
    combo_cards = []
    for item in payload["combos"]:
        trs = "".join(f'<tr><td>{esc(x["match"])}</td><td>{esc(x["marketText"])}</td><td>{esc(x["pick"])}</td><td>{x["odds"]:.2f}</td></tr>' for x in item["legs"])
        combo_cards.append(f'<section class="combo {item["category"]}"><h3><span>#{item["rank"]} {esc(item["name"])}</span><b>置信度 {item["trustScore"]}/100</b></h3><table><tbody>{trs}</tbody></table><p>理论组合赔率：<strong>{item["productOdds"]:.2f}</strong>（仅展示 ≥ {MIN_COMBO_ODDS:g}）</p></section>')
    match_cards = []
    for m in payload["matches"]:
        p = m["probabilities"]
        had = m["odds"]["had"]
        pool = " / ".join([m["mainScore"], *m["backupScores"]])
        tails = " / ".join(m["tailRiskScores"]) or "无额外尾部入选"
        match_cards.append(f'''<section class="match {m['leagueStyle']['class']}" style="--league:{m['leagueStyle']['color']}"><div class="title"><h3>{esc(m['matchNumStr'])} {esc(m['home'])} vs {esc(m['away'])}</h3><span>{esc(m['leagueStyle']['label'])}</span></div><p><b>开赛：</b>{esc(m['kickoff'])}　<b>体彩胜平负：</b>{had['home']} / {had['draw']} / {had['away']}　<small>更新 {esc(had.get('updatedAt','-'))}</small></p><div class="grid"><div><small>胜平负</small><strong>{esc(m['directionText'])}</strong></div><div><small>总进球</small><strong>{esc(m['totalGoals'])}</strong></div><div><small>主比分</small><strong>{esc(m['mainScore'])}</strong></div><div><small>信任度</small><strong>{m['confidenceScore']}</strong></div></div><p>比分池：{esc(pool)}；尾部审计：{esc(tails)}；总进球候选：{esc(' / '.join(m['goalCandidates']))}</p><p>隐含概率：主 {p['home']:.1%} / 平 {p['draw']:.1%} / 客 {p['away']:.1%}；排名：{esc(m['homeRank'] or '-')} / {esc(m['awayRank'] or '-')}</p><p><b>信息面：</b>{esc(m['context'])}</p><p><b>模型解释：</b>{esc(m['reason'])}</p></section>''')
    sources = "".join(f'<li><a href="{esc(x["url"])}">{esc(x["name"])}</a></li>' for x in payload["sources"])
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>2026-07-17 足球预测</title><style>:root{{--ink:#17212b;--muted:#647383;--line:#dce4ea}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(135deg,#edf4f7,#f8f5ee);color:var(--ink);font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.65}}header,main{{max-width:1180px;margin:auto;padding:24px 16px}}header{{padding-top:34px}}nav a{{display:inline-block;margin-right:9px;padding:7px 12px;background:#fff;border:1px solid var(--line);border-radius:999px;color:#194f73;text-decoration:none}}h1{{font-size:clamp(28px,5vw,48px);margin:15px 0 4px}}.subtitle{{color:var(--muted)}}.legend span{{display:inline-block;margin:5px 8px 5px 0;padding:6px 11px;border-left:7px solid var(--c);background:#fff;border-radius:7px}}.match,.combo,.notice{{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px;margin:15px 0;box-shadow:0 8px 26px rgba(35,54,70,.06)}}.match{{border-left:10px solid var(--league)}}.title,.combo h3{{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}}.title span{{background:var(--league);color:#fff;padding:4px 11px;border-radius:999px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}}.grid div{{background:#f5f8fa;padding:10px;border-radius:8px}}small{{display:block;color:var(--muted)}}strong{{font-size:21px}}.combo{{border-top:6px solid #287d70}}.combo.ttg{{border-top-color:#355dc5}}.combo.crs{{border-top-color:#b35430}}.combo b{{color:#08704d}}table{{width:100%;border-collapse:collapse}}td{{padding:8px;border-bottom:1px solid #e7ecef}}a{{color:#175f9e}}@media(max-width:700px){{.grid{{grid-template-columns:1fr 1fr}}.combo{{overflow:auto}}}}</style></head><body><header><nav><a href="../index.html">日期首页</a><a href="../history/index.html">历史预测</a></nav><h1>07 月 17 日足球预测</h1><p class="subtitle">共 {len(payload['matches'])} 场 · 北京时间 · 体彩赔率更新至 {esc(payload['oddsUpdatedAt'])}</p><div class="legend">{legend}</div></header><main><section class="notice"><h2>串关置信度总榜</h2><p>覆盖胜平负、总进球、比分三类玩法；所有组合理论赔率均不低于 {MIN_COMBO_ODDS:g}，并按模型置信度由高到低排序。置信度是横向比较分，不是命中概率。</p></section>{''.join(combo_cards)}<h2>10 场逐场预测</h2>{''.join(match_cards)}<section class="notice"><h2>赛程与赔率来源</h2><ul>{sources}</ul><p>{DISCLAIMER}</p></section></main></body></html>'''


def render_dashboard() -> tuple[str, str]:
    cards = [
        ("2026-07-17", "10 场 · 欧联 / 挪超 / 巴甲 / 美职", "20260717/index.html", "最新"),
        ("2026-07-16—17", "欧冠复盘与首版跨日预测", "20260716_0717/index.html", "历史"),
        ("2026-07-12—14", "跨日预测与复盘", "20260712_0714/index.html", "历史"),
        ("2026-07-11—12", "韩职与瑞超预测", "20260711_0712/index.html", "历史"),
        ("2026-07-06", "单日预测", "20260706/index.html", "历史"),
        ("2026-07-05", "韩职与瑞超预测", "20260705/index.html", "历史"),
    ]
    def card(row: tuple[str, str, str, str], prefix: str = "") -> str:
        date, desc, href, badge = row
        return f'<a class="date-card" href="{prefix}{href}"><span>{badge}</span><h2>{date}</h2><p>{desc}</p><b>查看预测 →</b></a>'
    css = '''*{box-sizing:border-box}body{margin:0;background:#eef3f6;color:#18232d;font-family:"Microsoft YaHei",Arial,sans-serif}header,main{max-width:1120px;margin:auto;padding:28px 18px}header{padding-top:55px}h1{font-size:clamp(32px,6vw,56px);margin:0}.lead{color:#607180;font-size:18px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.date-card{display:block;background:#fff;border:1px solid #dce5eb;border-radius:16px;padding:20px;color:inherit;text-decoration:none;box-shadow:0 10px 30px rgba(32,55,70,.07);transition:.2s}.date-card:hover{transform:translateY(-3px);box-shadow:0 14px 34px rgba(32,55,70,.13)}.date-card span{display:inline-block;background:#1d6d65;color:#fff;border-radius:99px;padding:3px 9px;font-size:12px}.date-card h2{margin:12px 0 4px}.date-card p{color:#647383}.date-card b{color:#185b8a}.history{display:inline-block;margin-top:22px;color:#185b8a}footer{max-width:1120px;margin:auto;padding:20px 18px 40px;color:#6d7983}'''
    homepage = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>足球预测日期首页</title><style>{css}</style></head><body><header><h1>足球预测</h1><p class="lead">按日期选择预测页面，最新日期在前。</p></header><main><section class="cards">{''.join(card(row) for row in cards)}</section><a class="history" href="history/index.html">进入历史预测子页面 →</a></main><footer>{DISCLAIMER}</footer></body></html>'''
    history = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>历史预测</title><style>{css}</style></head><body><header><a href="../index.html">← 返回日期首页</a><h1>历史预测</h1><p class="lead">按日期倒序归档。</p></header><main><section class="cards">{''.join(card(row, "../") for row in cards[1:])}</section></main><footer>{DISCLAIMER}</footer></body></html>'''
    return homepage, history


def main() -> None:
    matches = [predict(m) for m in load_matches()]
    if len(matches) != 10:
        raise SystemExit(f"Expected 10 matches, got {len(matches)}")
    updated = max(pool.get("updatedAt", "") for m in matches for pool in m["odds"].values() if isinstance(pool, dict))
    payload = {"modelVersion": MODEL_VERSION, "generatedAt": datetime.now().isoformat(timespec="seconds"), "dates": ["2026-07-17"], "worldCupExcluded": True, "oddsUpdatedAt": updated, "leagueStyles": LEAGUE_STYLES, "matches": matches, "combos": build_combos(matches), "sources": SOURCES, "disclaimer": DISCLAIMER}
    DATA.joinpath("predictions_20260717.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT.mkdir(exist_ok=True)
    page = render(payload)
    OUT.joinpath("index.html").write_text(page, encoding="utf-8")
    OUT.joinpath("predict_20260717.html").write_text(page, encoding="utf-8")
    homepage, history = render_dashboard()
    ROOT.joinpath("index.html").write_text(homepage, encoding="utf-8")
    ROOT.joinpath("history").mkdir(exist_ok=True)
    ROOT.joinpath("history", "index.html").write_text(history, encoding="utf-8")
    print(f"Generated {len(matches)} matches and {len(payload['combos'])} ranked combos")


if __name__ == "__main__":
    main()
