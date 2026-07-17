#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import math
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DISCLAIMER = "以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。"
MIN_COMBO_ODDS = 10.0
MARKET_TEXT = {"had": "胜平负", "ttg": "总进球", "crs": "比分", "hafu": "半全场"}
HAFU_TEXT = {"hh": "胜/胜", "hd": "胜/平", "ha": "胜/负", "dh": "平/胜", "dd": "平/平", "da": "平/负", "ah": "负/胜", "ad": "负/平", "aa": "负/负"}
EXCLUDED_BY_DATE: dict[str, dict[str, str]] = {
    "20260718": {"法国|英格兰": ""}
}
EXTRA_MATCHES_BY_DATE = {
    "20260718": ("data/sporttery_20260719_latest.json", "韩国职业联赛")
}


def load_base():
    path = ROOT / "scripts" / "generate_0716_0717_predictions.py"
    spec = importlib.util.spec_from_file_location("daily_base", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    module.LEAGUE_STYLES.update({
        "世界杯": {"class": "worldcup", "color": "#7b1f2e", "label": "世界杯季军赛"},
        "瑞典超级联赛": {"class": "swe", "color": "#176da3", "label": "瑞超"},
        "韩国职业联赛": {"class": "kor", "color": "#b33e5c", "label": "韩职"},
    })
    return module


def num(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def hafu_pick(match: dict[str, Any]) -> tuple[str, float | None, float]:
    final = {"home": "h", "draw": "d", "away": "a"}[match["direction"]]
    first = "d" if match["totalGoals"] in {"0", "1", "2"} or final == "d" else final
    key = first + final
    odds = num(match["odds"].get("hafu", {}).get(key))
    if not odds:
        available = [(k, num(v)) for k, v in match["odds"].get("hafu", {}).items() if k in HAFU_TEXT and num(v)]
        key, odds = min(available, key=lambda row: row[1]) if available else ("dd", None)
    return key, odds, min(0.30, 1 / odds) if odds else 0


def leg(match: dict[str, Any], market: str) -> dict[str, Any]:
    if market == "had":
        key = {"home": "home", "draw": "draw", "away": "away"}[match["direction"]]
        pick, odds, probability = match["directionText"], num(match["odds"]["had"].get(key)), match["probabilities"][key]
    elif market == "ttg":
        pick = match["totalGoals"]
        odds = num(match["odds"]["ttg"].get("s7" if pick == "7+" else f"s{pick}"))
        probability = min(0.42, 1 / odds) if odds else 0
    elif market == "crs":
        pick, odds = match["mainScore"], num(match["odds"]["crs"].get(match["mainScore"]))
        probability = min(0.24, 1 / odds) if odds else 0
    else:
        key, odds, probability = hafu_pick(match)
        pick = HAFU_TEXT[key]
    return {"matchId": match["id"], "match": f"{match['matchNumStr']} {match['home']} vs {match['away']}", "market": market, "marketText": MARKET_TEXT[market], "pick": pick, "odds": odds, "probability": probability}


def combo(name: str, legs: tuple[dict[str, Any], ...] | list[dict[str, Any]], category: str) -> dict[str, Any]:
    product = math.prod(row["odds"] for row in legs)
    joint = math.prod(row["probability"] for row in legs)
    trust = round(100 * joint ** (1 / len(legs)) * (0.94 ** (len(legs) - 1)))
    return {"name": name, "category": category, "legs": list(legs), "productOdds": round(product, 2), "trustScore": max(1, min(88, trust))}


def build_combos(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_legs = {market: [leg(m, market) for m in matches] for market in MARKET_TEXT}
    for market, candidates in all_legs.items():
        usable = [x for x in candidates if x["odds"] and x["probability"]]
        pool = []
        for size in range(2, min(4 if market == "had" else 3, len(usable)) + 1):
            for selected in combinations(usable, size):
                item = combo(f"{MARKET_TEXT[market]}{size}串一", selected, market)
                if item["productOdds"] >= MIN_COMBO_ODDS:
                    pool.append(item)
        rows.extend(sorted(pool, key=lambda x: (-x["trustScore"], x["productOdds"]))[:3])

    mixed = []
    candidates = [x for legs in all_legs.values() for x in legs if x["odds"] and x["probability"]]
    for size in (2, 3, 4):
        for selected in combinations(candidates, size):
            if len({x["matchId"] for x in selected}) != size or len({x["market"] for x in selected}) < 2:
                continue
            item = combo(f"混合{size}串一", selected, "mixed")
            if item["productOdds"] >= MIN_COMBO_ODDS:
                mixed.append(item)
    rows.extend(sorted(mixed, key=lambda x: (-x["trustScore"], x["productOdds"]))[:5])
    rows.sort(key=lambda x: (-x["trustScore"], x["productOdds"]))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def predict_with_market_fallback(base: Any, match: dict[str, Any]) -> dict[str, Any]:
    """Use the score matrix only for model probabilities when HAD is not offered."""
    cloned = json.loads(json.dumps(match, ensure_ascii=False))
    had = cloned.get("odds", {}).get("had") or {}
    has_had = all(num(had.get(key)) for key in ("home", "draw", "away"))
    if not has_had:
        totals = {"home": 0.0, "draw": 0.0, "away": 0.0}
        for score, price in cloned["odds"].get("crs", {}).items():
            if "-" not in score or not num(price):
                continue
            home, away = (int(x) for x in score.split("-"))
            key = "home" if home > away else "away" if home < away else "draw"
            totals[key] += 1 / float(price)
        total = sum(totals.values())
        if not total:
            raise ValueError(f"No HAD or score-matrix direction basis for {match.get('matchNumStr')}")
        cloned["odds"]["had"] = {key: round(1 / (value / total), 3) for key, value in totals.items() if value}
    predicted = base.predict(cloned)
    predicted["businessDate"] = match.get("businessDate", "")
    if not has_had:
        predicted["odds"]["had"] = {}
        predicted["marketBasis"] = "未开售胜平负；方向概率由官方比分矩阵归一化推导，不参与胜平负串关。"
        predicted["reason"] += " " + predicted["marketBasis"]
    else:
        predicted["marketBasis"] = "官方胜平负赔率"
    return predicted


def render(payload: dict[str, Any], styles: dict[str, dict[str, str]]) -> str:
    label = datetime.strptime(payload["date"], "%Y%m%d").strftime("%m-%d")
    extra_note = '<span style="--c:#b33e5c">含07-19两场韩职</span>' if payload["date"] == "20260718" else ""
    legends = f'<span style="--c:#17212b">按 Sporttery 竞彩业务日分组</span><span style="--c:#c38b16">串关理论赔率 ≥ {MIN_COMBO_ODDS:.0f}</span>{extra_note}' + "".join(f'<span style="--c:{styles[name]["color"]}">{esc(styles[name]["label"])}</span>' for name in dict.fromkeys(m["league"] for m in payload["matches"]))
    warnings = "".join(f"<li>{esc(x)}</li>" for x in payload["scheduleWarnings"])
    combos = []
    for c in payload["combos"]:
        legs = "".join(f'<tr><td>{esc(x["match"])}</td><td>{esc(x["marketText"])}</td><td>{esc(x["pick"])}</td><td>{x["odds"]:.2f}</td></tr>' for x in c["legs"])
        combos.append(f'<section class="combo {c["category"]}"><h3>#{c["rank"]} {esc(c["name"])} <b>{c["trustScore"]}/100</b></h3><table>{legs}</table><p>理论组合赔率：<strong>{c["productOdds"]:.2f}</strong></p></section>')
    cards = []
    for m in payload["matches"]:
        p, had = m["probabilities"], m["odds"]["had"]
        pool = " / ".join([m["mainScore"], *m["backupScores"]])
        hkey, _, _ = hafu_pick(m)
        cards.append(f'''<section class="match" style="--league:{m['leagueStyle']['color']}"><div class="title"><h3>{esc(m['matchNumStr'])} {esc(m['home'])} vs {esc(m['away'])}</h3><span>{esc(m['leagueStyle']['label'])}</span></div><p><b>北京时间：</b>{esc(m['kickoff'])}　<b>胜平负赔率：</b>{had.get('home','-')} / {had.get('draw','-')} / {had.get('away','-')}</p><div class="grid"><div><small>胜平负</small><strong>{esc(m['directionText'])}</strong></div><div><small>总进球</small><strong>{esc(m['totalGoals'])}</strong></div><div><small>比分</small><strong>{esc(m['mainScore'])}</strong></div><div><small>半全场</small><strong>{esc(HAFU_TEXT[hkey])}</strong></div></div><p>比分池：{esc(pool)}；尾部审计：{esc(' / '.join(m['tailRiskScores']) or '无额外尾部入选')}；总进球候选：{esc(' / '.join(m['goalCandidates']))}</p><p>隐含概率：主 {p['home']:.1%} / 平 {p['draw']:.1%} / 客 {p['away']:.1%}；模型信任度 {m['confidenceScore']}/100。</p><p>{esc(m['reason'])}</p></section>''')
    source_items = "".join(f'<li><a href="{esc(x["url"])}">{esc(x["name"])}</a></li>' for x in payload["sources"])
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>2026-{label}足球预测</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#eef4f6;color:#17212b;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.65}}header,main{{max-width:1180px;margin:auto;padding:24px 16px}}nav a{{margin-right:10px}}h1{{font-size:clamp(30px,5vw,48px)}}.legend span{{display:inline-block;margin:5px;padding:6px 11px;border-left:7px solid var(--c);background:white;border-radius:7px}}.notice,.match,.combo{{background:white;border:1px solid #dce4ea;border-radius:14px;padding:18px;margin:15px 0;box-shadow:0 8px 26px #2336460f}}.match{{border-left:10px solid var(--league)}}.title,.combo h3{{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}}.title span{{background:var(--league);color:white;padding:4px 11px;border-radius:99px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}}.grid div{{background:#f5f8fa;padding:10px;border-radius:8px}}small{{display:block;color:#657482}}strong{{font-size:21px}}.combo{{border-top:6px solid #287d70}}.combo.hafu{{border-top-color:#7a43b6}}.combo.crs{{border-top-color:#b35430}}.combo.ttg{{border-top-color:#355dc5}}.combo.mixed{{border-top-color:#c38b16}}table{{width:100%;border-collapse:collapse}}td{{padding:8px;border-bottom:1px solid #e7ecef}}@media(max-width:700px){{.grid{{grid-template-columns:1fr 1fr}}.combo{{overflow:auto}}}}</style></head><body><header><nav><a href="../index.html">日期首页</a><a href="../20260716/review.html">07-16复盘</a></nav><h1>{label}足球预测</h1><p>共 {len(payload['matches'])} 场 · 北京时间 · 赔率更新至 {esc(payload['oddsUpdatedAt'])}</p><div class="legend">{legends}</div></header><main>{f'<section class="notice"><h2>赛程冲突提示</h2><ul>{warnings}</ul></section>' if warnings else ''}<section class="notice"><h2>n串一总榜</h2><p>包含胜平负、总进球、比分、半全场及混合玩法；信任度仅用于模型横向比较，不等同于命中率。</p></section>{''.join(combos)}<h2>逐场预测</h2>{''.join(cards)}<section class="notice"><h2>赛程与赔率来源</h2><ul>{source_items}</ul><p>{DISCLAIMER}</p></section></main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    base = load_base()
    raw = json.loads((ROOT / args.source).read_text(encoding="utf-8-sig"))
    source_matches = list(raw["matches"])
    extra_config = EXTRA_MATCHES_BY_DATE.get(args.date)
    if extra_config:
        extra_path, extra_league = extra_config
        extra_raw = json.loads((ROOT / extra_path).read_text(encoding="utf-8-sig"))
        source_matches.extend(m for m in extra_raw["matches"] if m.get("league") == extra_league)
    excluded = EXCLUDED_BY_DATE.get(args.date, {})
    supported = set(base.LEAGUE_STYLES)
    matches = [predict_with_market_fallback(base, m) for m in source_matches if m.get("league") in supported and f"{m.get('home')}|{m.get('away')}" not in excluded]
    if not matches:
        raise SystemExit("No verified matches available")
    updated = max(pool.get("updatedAt", "") for m in matches for pool in m["odds"].values() if isinstance(pool, dict))
    sources = list(base.SOURCES) + [
        {"name": "瑞超官方赛程", "url": "https://allsvenskan.se/nyheter/sa-spelas-omgang-11-17-av-allsvenskan/"},
        {"name": "挪威足协赛程", "url": "https://www.fotball.no/eliteserien/"},
        {"name": "巴西足协赛程", "url": "https://www.cbf.com.br/futebol-brasileiro/jogos/campeonato-brasileiro/serie-a/2026"},
        {"name": "MLS官方赛程", "url": "https://www.mlssoccer.com/news/mls-unveils-2026-regular-season-schedule"},
        {"name": "K League官方赛程", "url": "https://tv.kleague.com/en-int/schedule"},
        {"name": "FIFA世界杯官方赛程", "url": "https://www.fifa.com/en/tournaments/mens/worldcup/canadamexicousa2026/scores-fixtures"},
    ]
    payload = {"date": args.date, "dateBasis": "Sporttery竞彩业务日；07-18页面按用户要求并入07-19两场韩职", "includedBusinessDates": sorted(set(m.get("businessDate", "") for m in matches)), "modelVersion": f"daily-multimarket-{args.date}-v3", "generatedAt": datetime.now().isoformat(timespec="seconds"), "oddsUpdatedAt": updated, "matches": matches, "combos": build_combos(matches), "scheduleWarnings": [reason for reason in excluded.values() if reason], "sources": sources, "disclaimer": DISCLAIMER}
    DATA.joinpath(f"predictions_{args.date}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out = ROOT / args.date
    out.mkdir(exist_ok=True)
    page = render(payload, base.LEAGUE_STYLES)
    out.joinpath("index.html").write_text(page, encoding="utf-8")
    out.joinpath(f"predict_{args.date}.html").write_text(page, encoding="utf-8")
    print(f"Generated {len(matches)} matches, {len(payload['combos'])} parlays, {len(excluded)} schedule warnings")


if __name__ == "__main__":
    main()
