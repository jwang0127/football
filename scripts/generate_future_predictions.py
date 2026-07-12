#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate a rolling three-day Sporttery prediction board."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT_DIR = ROOT / "20260712_0714"
OUTPUT_JSON = DATA / "predictions_20260712_0714.json"
MODEL_VERSION = "three-day-review-0711-result-adjustment-v1"
NOW = datetime.fromisoformat("2026-07-12T10:30:00")
TARGET_DATES = {"2026-07-12", "2026-07-13", "2026-07-14"}

REVIEW = {
    "results": [
        "2026-07-11 光州FC 0-3 浦项制铁",
        "2026-07-11 金泉尚武 1-1 富川FC",
        "2026-07-11 蔚山现代 1-3 全北现代",
    ],
    "lessons": [
        "强势客队在低赔下仍可能打出0-3、1-3，保留客队大比分尾部，不把低总进球直接等同于小比分。",
        "均势韩职继续提高1-1保护，但不能压掉1-0、0-1等单球分胜负路径。",
        "赔率是锚点而非结论，方向、总进球和比分池分开校准。",
    ],
    "adjustments": {
        "away_blowout_tail": "+0.06",
        "draw_protection": "+0.04",
        "single_goal_paths": "+0.03",
        "exact_score_parlay_weight": "-0.05",
    },
}

def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

def num(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None

def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)

def label(direction: str) -> str:
    return {"home": "主胜", "draw": "平", "away": "客胜"}[direction]

def direction(score: str) -> str:
    home, away = (int(x) for x in score.split("-"))
    return "home" if home > away else "away" if home < away else "draw"

def implied(had: dict[str, Any]) -> dict[str, float]:
    raw = {key: 1 / num(had.get(key)) for key in ("home", "draw", "away") if num(had.get(key))}
    total = sum(raw.values())
    return {key: raw.get(key, 0) / total for key in ("home", "draw", "away")}

def score_rows(crs: dict[str, Any]) -> list[tuple[str, float]]:
    return sorted([(key, num(value)) for key, value in crs.items() if "-" in key and num(value)], key=lambda item: item[1])

def goal_rows(ttg: dict[str, Any]) -> list[tuple[str, float]]:
    rows = []
    for i in range(8):
        value = num(ttg.get(f"s{i}"))
        if value:
            rows.append(("7+" if i == 7 else str(i), value))
    return sorted(rows, key=lambda item: item[1])

def total(score: str) -> int:
    return sum(int(x) for x in score.split("-"))

def pick(match: dict[str, Any]) -> dict[str, Any]:
    odds = match["odds"]
    probs = implied(odds["had"])
    scores = score_rows(odds["crs"])
    goals = goal_rows(odds["ttg"])
    market = max(probs, key=probs.get)
    gap = abs(probs["home"] - probs["away"])
    draw_prob = probs["draw"]
    main = scores[0][0]
    reason = "按胜平负、比分和总进球赔率的交叉低赔排序。"
    if num(odds["crs"].get("1-1")) and (gap <= 0.12 or draw_prob >= 0.29):
        main = "1-1"
        reason = "复盘后对均势盘提高1-1保护，同时保留单球分胜负尾部。"
    elif market == "away" and gap >= 0.20:
        main = "0-1" if num(odds["crs"].get("0-1")) else main
        reason = "客胜赔率优势明确，主选低比分客胜；复盘保留客队扩大比分路径。"
    elif market == "home" and gap >= 0.20:
        main = "1-0" if num(odds["crs"].get("1-0")) else main
        reason = "主胜赔率优势明确，主选单球主胜并防范平局。"
    main_dir = direction(main)
    goal_pick = str(total(main))
    if goals and goals[0][0] in {"1", "2", "3"}:
        goal_pick = goals[0][0]
    if total(main) <= 2 and num(odds["ttg"].get("s2")):
        goal_pick = "2"
    backups = []
    allowed = {main_dir, market, "draw"}
    for score, _ in scores:
        if score != main and direction(score) in allowed and score not in backups:
            backups.append(score)
        if len(backups) == 2:
            break
    upset_dir = "draw" if main_dir != "draw" else ("away" if probs["away"] >= probs["home"] else "home")
    upset = next((s for s, _ in scores if direction(s) == upset_dir and s != main), backups[-1] if backups else main)
    confidence = "高" if gap >= 0.24 else "中"
    if main_dir == "draw" or draw_prob >= 0.29:
        confidence = "中低"
    return {
        "id": match["id"], "matchNumStr": match["matchNumStr"], "matchDate": match["matchDate"],
        "league": match["league"], "leagueCode": match["leagueCode"], "kickoff": match["kickoff"],
        "home": match["home"], "away": match["away"], "homeRank": match.get("homeRank", ""),
        "awayRank": match.get("awayRank", ""), "modelVersion": MODEL_VERSION,
        "probabilities": {key: round(value, 3) for key, value in probs.items()},
        "direction": main_dir, "directionText": label(main_dir), "marketFavorite": label(market),
        "mainScore": main, "backupScores": backups, "upsetScore": upset, "totalGoals": goal_pick,
        "goalCandidates": [x[0] for x in goals[:3]], "confidence": confidence, "reviewReason": reason,
        "odds": odds,
    }

def load_matches() -> list[dict[str, Any]]:
    matches = []
    for date in sorted(TARGET_DATES):
        path = DATA / ("sporttery_20260712_refresh.json" if date == "2026-07-12" else f"sporttery_{date.replace('-', '')}_latest.json")
        for match in read(path)["matches"]:
            kickoff = datetime.fromisoformat(match["kickoff"])
            if match["matchDate"] in TARGET_DATES and kickoff >= NOW:
                matches.append(match)
    return matches

def parlay(rows: list[dict[str, Any]], key: str, picks: list[str]) -> dict[str, Any]:
    items = []
    product = 1.0
    for match, selected in zip(rows, picks):
        odds = match["odds"][key]
        mapping = {"had": {"主胜": "home", "平": "draw", "客胜": "away"}, "ttg": {str(i): f"s{i}" for i in range(8)}}
        pool_key = mapping[key][selected]
        value = num(odds.get(pool_key))
        if value is None:
            continue
        product *= value
        items.append({"match": f"{match['matchNumStr']} {match['home']} vs {match['away']}", "pick": selected, "odds": value, "updatedAt": odds.get("updatedAt", "")})
    items.append({"match": "理论乘积", "pick": "", "odds": round(product, 2), "updatedAt": ""})
    return {"items": items, "product": round(product, 2)}

def custom_parlay(specs: list[tuple[dict[str, Any], str, str, str]]) -> dict[str, Any]:
    items = []
    product = 1.0
    for match, pool, selected, pool_key in specs:
        value = num(match["odds"][pool].get(pool_key))
        if value is None:
            continue
        product *= value
        items.append({
            "match": f"{match['matchNumStr']} {match['home']} vs {match['away']}",
            "pick": selected,
            "odds": value,
            "updatedAt": match["odds"][pool].get("updatedAt", ""),
        })
    items.append({"match": "理论乘积", "pick": "", "odds": round(product, 2), "updatedAt": ""})
    return {"items": items, "product": round(product, 2)}

def make_html(payload: dict[str, Any]) -> str:
    cards = []
    league_cls = {"KD1": "k", "SAL": "s", "NTL": "n"}
    for row in payload["matches"]:
        cls = league_cls.get(row["leagueCode"], "o")
        p = row["probabilities"]
        cards.append(f'''<section class="card {cls}"><div class="title"><h2>{esc(row["matchNumStr"])} {esc(row["home"])} vs {esc(row["away"])}</h2><span>{esc(row["league"])}</span></div><div class="grid"><div><small>方向</small><strong>{esc(row["directionText"])}</strong></div><div><small>总进球</small><strong>{esc(row["totalGoals"])}</strong></div><div><small>主比分</small><strong>{esc(row["mainScore"])}</strong></div><div><small>爆冷比分</small><strong>{esc(row["upsetScore"])}</strong></div></div><p class="muted">开球：{esc(row["kickoff"])}；隐含概率：主 {p["home"]:.1%} / 平 {p["draw"]:.1%} / 客 {p["away"]:.1%}；信心：{esc(row["confidence"])}</p><p>比分池：{esc(" / ".join([row["mainScore"], *row["backupScores"]]))}；总进球候选：{esc(" / ".join(row["goalCandidates"]))}</p><p><strong>复盘修正：</strong>{esc(row["reviewReason"])}</p></section>''')
    parlay_sections = []
    for name, value in payload["parlays"].items():
        rows = []
        for item in value["items"]:
            rows.append(
                f"<tr><td>{esc(item['match'])}</td><td>{esc(item['pick'])}</td>"
                f"<td>{item['odds']:.2f}</td><td>{esc(item['updatedAt'])}</td></tr>"
            )
        parlay_sections.append(
            f"<h3>{esc(name)}</h3><div class=\"table\"><table>"
            "<thead><tr><th>比赛</th><th>选择</th><th>赔率</th><th>更新时间</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )
    parlay_html = "".join(parlay_sections)
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>未来三天足球预测</title><style>body{{margin:0;background:#f6f8fb;color:#18202a;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.65}}header,main{{max-width:1180px;margin:auto;padding:22px 16px}}header{{background:#fff;border-bottom:1px solid #d8e0e8;position:sticky;top:0;z-index:2}}h1{{margin:0;font-size:29px}}h2{{margin:0 0 8px;font-size:20px}}h3{{margin:18px 0 8px}}.card{{background:#fff;border:1px solid #d8e0e8;border-left:8px solid #8794a3;border-radius:8px;padding:18px;margin:16px 0}}.k{{background:#f5fbff;border-left-color:#1683c7}}.s{{background:#fffaf0;border-left-color:#cf8a16}}.n{{background:#f6f3ff;border-left-color:#7454b3}}.o{{background:#f7f7f7}}.title{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}.title span{{padding:4px 9px;border-radius:999px;background:#2e3e4e;color:white;font-weight:700}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.grid div{{background:#fff;border:1px solid #dbe3ea;border-radius:6px;padding:10px}}small{{display:block;color:#66727d}}strong{{font-size:22px}}.muted{{color:#5f6f77}}pre{{white-space:pre-wrap;background:#fff;border:1px solid #d8e0e8;padding:12px;overflow:auto}}.notice{{border-left-color:#7a8ca0}}@media(max-width:760px){{.grid{{grid-template-columns:1fr 1fr}}h1{{font-size:24px}}}}</style></head><body><header><h1>未来三天足球预测（0712-0714）</h1><p class="muted">仅显示当前时间之后、未来三天内的 {len(payload["matches"])} 场比赛；赔率来源：Sporttery 官方接口，抓取时间：{esc(payload["fetchedAt"])}。</p></header><main><section class="card notice"><h2>赛果复盘与模型调整</h2><p>{esc("；".join(REVIEW["results"]))}</p><ul>{"".join(f"<li>{esc(x)}</li>" for x in REVIEW["lessons"])}</ul><p class="muted">以上仅为公开信息整理后的娱乐分析，不构成任何购买彩票建议，请理性参考。</p></section><section class="card"><h2>串关参考</h2>{parlay_html}</section>{"".join(cards)}<section class="card"><h2>数据来源</h2><p>竞彩赔率页：<a href="https://m.sporttery.cn/mjc/jsq/zqzjq/">https://m.sporttery.cn/mjc/jsq/zqzjq/</a></p><p>本页仅包含未来三天场次，已排除7月12日早间已经开赛的比赛。</p></section></main></body></html>'''

def main() -> None:
    matches = load_matches()
    if not matches:
        raise SystemExit("No future matches found")
    rows = [pick(match) for match in matches]
    timestamps = [
        value.get("updatedAt", "")
        for match in matches
        for pool in match["odds"].values()
        if isinstance(pool, dict)
        for value in [pool]
    ]
    fetched = max(timestamps, default="")
    payload = {"modelVersion": MODEL_VERSION, "generatedAt": datetime.now().isoformat(timespec="seconds"), "fetchedAt": fetched, "targetDates": sorted(TARGET_DATES), "review": REVIEW, "matches": rows, "parlays": {}}
    payload["parlays"] = {
        "胜平负三串一": parlay(rows[:3], "had", [x["directionText"] for x in rows[:3]]),
        "总进球三串一": parlay(rows[3:6], "ttg", [x["totalGoals"] for x in rows[3:6]]),
        "强方向三串一": parlay([rows[4], rows[6], rows[9]], "had", ["主胜", "客胜", "主胜"]),
        "强方向四串一": parlay([rows[4], rows[6], rows[9], rows[10]], "had", ["主胜", "客胜", "主胜", "主胜"]),
        "强方向五串一": parlay([rows[4], rows[6], rows[9], rows[10], rows[13]], "had", ["主胜", "客胜", "主胜", "主胜", "主胜"]),
        "总进球四串一": parlay([rows[3], rows[4], rows[6], rows[7]], "ttg", ["2", "2", "2", "2"]),
        "总进球二串一": parlay([rows[4], rows[6]], "ttg", ["2", "2"]),
        "总进球五串一": parlay([rows[3], rows[4], rows[6], rows[7], rows[9]], "ttg", ["2", "2", "2", "2", "2"]),
        "混合稳胆四串一": custom_parlay([
            (rows[4], "had", "主胜", "home"),
            (rows[6], "had", "客胜", "away"),
            (rows[7], "ttg", "2", "s2"),
            (rows[9], "had", "主胜", "home"),
        ]),
        "比分稳胆二串一": custom_parlay([
            (rows[4], "crs", rows[4]["mainScore"], rows[4]["mainScore"]),
            (rows[13], "crs", rows[13]["mainScore"], rows[13]["mainScore"]),
        ]),
        "比分主选三串一": custom_parlay([
            (rows[4], "crs", rows[4]["mainScore"], rows[4]["mainScore"]),
            (rows[6], "crs", rows[6]["mainScore"], rows[6]["mainScore"]),
            (rows[13], "crs", rows[13]["mainScore"], rows[13]["mainScore"]),
        ]),
        "比分三串一（高风险）": custom_parlay([
            (rows[4], "crs", rows[4]["upsetScore"], rows[4]["upsetScore"]),
            (rows[6], "crs", rows[6]["upsetScore"], rows[6]["upsetScore"]),
            (rows[13], "crs", rows[13]["upsetScore"], rows[13]["upsetScore"]),
        ]),
    }
    write(OUTPUT_JSON, payload)
    OUTPUT_DIR.mkdir(exist_ok=True)
    page = make_html(payload)
    (OUTPUT_DIR / "index.html").write_text(page, encoding="utf-8")
    (OUTPUT_DIR / "predict_20260712_0714.html").write_text(page, encoding="utf-8")
    (ROOT / "index.html").write_text(page, encoding="utf-8")
    print(f"Generated {len(rows)} future matches in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
