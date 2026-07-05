#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE_FILE = DATA / "sporttery_20260707_latest.json"
OUTPUT_DATE = "20260706"
MODEL_VERSION = "non-worldcup-review-adjusted-20260706"


TODAY_REVIEW = {
    "date": "20260705",
    "settled": [
        {"match": "首尔FC vs 仁川联", "prediction": "1-0", "result": "1-0", "lesson": "低赔主胜小比分命中，强队穿盘仍需谨慎。"},
        {"match": "光州FC vs 蔚山现代", "prediction": "0-1", "result": "1-1", "lesson": "低赔客胜被主队拖平，客胜热度高时要提高 1-1 权重。"},
        {"match": "金泉尚武 vs 济州SK", "prediction": "1-1", "result": "1-1", "lesson": "均势盘优先 1-1 有效。"},
        {"match": "卡尔马 vs 厄尔格里特", "prediction": "2-1", "result": "1-0", "lesson": "瑞超主胜命中方向但总进球偏高，主胜盘总进球下修。"},
        {"match": "IFK哥德堡 vs AIK索尔纳", "prediction": "2-1", "result": "1-1", "lesson": "瑞超中下游均势盘主胜高估，平局保护上调。"},
    ],
    "pending": ["埃尔夫斯堡 vs 哈马比：生成时 Sporttery 仍未回填完场结果，不纳入本轮参数修正。"],
    "adjustments": [
        "瑞超均势盘：若胜负隐含概率差小于 8%，主方向不直接压主胜/客胜，优先检查 1-1。",
        "瑞超总进球：市场 3 球低赔但 1-1 同时为比分低赔时，总进球从 3 下修到 2。",
        "客胜热度：客胜低赔但让球保护反向明显时，比分池加入 1-1 作为主防线。",
    ],
}


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


def implied(had: dict[str, Any]) -> dict[str, float]:
    raw = {key: 1 / odd(had[key]) for key in ("home", "draw", "away") if odd(had.get(key))}
    total = sum(raw.values())
    return {key: raw.get(key, 0) / total for key in ("home", "draw", "away")} if total else {"home": 0.34, "draw": 0.30, "away": 0.36}


def direction(score: str) -> str:
    h, a = [int(part) for part in score.split("-")]
    if h > a:
        return "home"
    if h < a:
        return "away"
    return "draw"


def score_total(score: str) -> int:
    return sum(int(part) for part in score.split("-"))


def label(direction_code: str) -> str:
    return {"home": "主胜", "draw": "平", "away": "客胜"}[direction_code]


def sorted_scores(crs: dict[str, Any]) -> list[tuple[str, float]]:
    rows = []
    for key, value in crs.items():
        if "-" in key and odd(value):
            rows.append((key, float(value)))
    return sorted(rows, key=lambda row: row[1])


def sorted_goals(ttg: dict[str, Any]) -> list[tuple[str, float]]:
    rows = []
    for idx in range(8):
        key = f"s{idx}"
        value = odd(ttg.get(key))
        if value:
            rows.append(("7+" if idx == 7 else str(idx), value))
    return sorted(rows, key=lambda row: row[1])


def pick(match: dict[str, Any]) -> dict[str, Any]:
    odds = match["odds"]
    probs = implied(odds["had"])
    score_rows = sorted_scores(odds["crs"])
    goal_rows = sorted_goals(odds["ttg"])
    favorite = max(probs, key=probs.get)
    spread = abs(probs["home"] - probs["away"])

    low_score = score_rows[0][0]
    main_score = low_score
    total_goals = str(score_total(main_score))
    direction_code = direction(main_score)

    # Review adjustment: 20260705 Swedish matches over-weighted 2-1/3 goals.
    if match["league"] == "瑞典超级联赛":
        if spread < 0.08 and odd(odds["crs"].get("1-1")):
            main_score = "1-1"
            total_goals = "2"
            direction_code = "draw"
        elif goal_rows and goal_rows[0][0] == "3" and odd(odds["crs"].get("1-1")) and odd(odds["crs"].get("1-1")) <= 7.5:
            main_score = "1-1"
            total_goals = "2"
            direction_code = "draw"
        elif favorite == "away" and probs["draw"] >= 0.27:
            main_score = "1-1"
            total_goals = "2"
            direction_code = "draw"

    if main_score == low_score and direction_code != favorite:
        direction_code = direction(main_score)

    backups: list[str] = []
    preferred_dirs = {direction_code, favorite, "draw"}
    for score, _ in score_rows:
        if score != main_score and direction(score) in preferred_dirs and score not in backups:
            backups.append(score)
        if len(backups) == 2:
            break

    upset_dir = "away" if direction_code in {"home", "draw"} else "draw"
    upset = next((score for score, _ in score_rows if direction(score) == upset_dir and score != main_score), backups[-1] if backups else main_score)

    half = "draw" if direction_code == "draw" or score_total(main_score) <= 2 else direction_code
    hafu_key = {"home": "h", "draw": "d", "away": "a"}[half] + {"home": "h", "draw": "d", "away": "a"}[direction_code]
    total_key = "s7" if total_goals == "7+" else f"s{total_goals}"

    return {
        "id": match["id"],
        "matchNumStr": match["matchNumStr"],
        "league": match["league"],
        "businessDate": match["businessDate"],
        "kickoff": match["kickoff"],
        "home": match["home"],
        "away": match["away"],
        "homeRank": match["homeRank"],
        "awayRank": match["awayRank"],
        "probabilities": {key: round(value, 3) for key, value in probs.items()},
        "direction": direction_code,
        "directionText": label(direction_code),
        "mainScore": main_score,
        "backupScores": backups,
        "upsetScore": upset,
        "totalGoals": total_goals,
        "totalGoalCandidates": [item[0] for item in goal_rows[:3]],
        "confidence": "中" if spread >= 0.08 else "中低",
        "odds": odds,
        "parlay": {
            "score": {"pick": main_score, "odds": odd(odds["crs"].get(main_score)), "updatedAt": odds["crs"].get("updatedAt")},
            "goals": {"pick": total_goals, "odds": odd(odds["ttg"].get(total_key)), "updatedAt": odds["ttg"].get("updatedAt")},
            "hafu": {"pick": hafu_key, "label": f"{label(half)}/{label(direction_code)}", "odds": odd(odds["hafu"].get(hafu_key)), "updatedAt": odds["hafu"].get("updatedAt")},
        },
        "marketRead": [
            f"胜平负隐含概率：主胜{probs['home']:.1%} / 平{probs['draw']:.1%} / 客胜{probs['away']:.1%}。",
            "比分低赔：" + "，".join(f"{score}@{price:.2f}" for score, price in score_rows[:5]) + "。",
            "总进球低赔：" + "，".join(f"{goals}球@{price:.2f}" for goals, price in goal_rows[:3]) + "。",
        ],
    }


def fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def render_rows(rows: list[dict[str, Any]]) -> str:
    return "".join(f"<tr><td>{esc(row['match'])}</td><td>{esc(row['pick'])}</td><td>{esc(row['oddsText'])}</td><td>{esc(row['updatedAt'])}</td></tr>" for row in rows)


def parlays(matches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {"goals": [], "score": [], "upset": [], "hafu": []}
    for item in matches:
        name = f"{item['home']} vs {item['away']}"
        out["goals"].append({"match": name, "pick": item["totalGoals"], **item["parlay"]["goals"]})
        out["score"].append({"match": name, "pick": item["mainScore"], **item["parlay"]["score"]})
        out["upset"].append({"match": name, "pick": item["upsetScore"], "odds": odd(item["odds"]["crs"].get(item["upsetScore"])), "updatedAt": item["odds"]["crs"].get("updatedAt")})
        out["hafu"].append({"match": name, "pick": item["parlay"]["hafu"]["label"], "odds": item["parlay"]["hafu"]["odds"], "updatedAt": item["parlay"]["hafu"]["updatedAt"]})
    for rows in out.values():
        product = 1.0
        for row in rows:
            row["oddsText"] = fmt(row.get("odds"))
            if row.get("odds"):
                product *= float(row["odds"])
        rows.append({"match": "理论乘积", "pick": "", "odds": product, "oddsText": fmt(product), "updatedAt": ""})
    return out


def render(payload: dict[str, Any]) -> str:
    review_items = "".join(f"<li>{esc(item['match'])}：预测 {esc(item['prediction'])}，赛果 {esc(item['result'])}。{esc(item['lesson'])}</li>" for item in TODAY_REVIEW["settled"])
    adjustments = "".join(f"<li>{esc(item)}</li>" for item in TODAY_REVIEW["adjustments"])
    cards = []
    for item in payload["matches"]:
        reads = "".join(f"<li>{esc(text)}</li>" for text in item["marketRead"])
        cards.append(f"""
<section class="card allsvenskan">
  <div class="title"><h2>{esc(item['matchNumStr'])} {esc(item['home'])} vs {esc(item['away'])}</h2><span>瑞超</span></div>
  <div class="grid"><div><small>方向</small><strong>{esc(item['directionText'])}</strong></div><div><small>总进球</small><strong>{esc(item['totalGoals'])}</strong></div><div><small>主比分</small><strong>{esc(item['mainScore'])}</strong></div><div><small>防冷</small><strong>{esc(item['upsetScore'])}</strong></div></div>
  <p class="muted">开球：{esc(item['kickoff'])}；排名：{esc(item['homeRank'])} vs {esc(item['awayRank'])}；信心：{esc(item['confidence'])}</p>
  <p>比分池：{esc(item['mainScore'])} / {esc(' / '.join(item['backupScores']))}；冷门比分：{esc(item['upsetScore'])}；总进球候选：{esc(' / '.join(item['totalGoalCandidates']))}。</p>
  <ul>{reads}</ul>
</section>""")
    p = payload["parlays"]
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>20260706 非世界杯预测</title>
<style>
body{{margin:0;background:#f7f8f8;color:#18211e;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.65}}header,main{{max-width:1120px;margin:auto;padding:22px 16px}}header{{background:#fff;border-bottom:1px solid #d9dfdd;position:sticky;top:0}}h1{{margin:0;font-size:30px}}h2{{margin:0 0 10px;font-size:22px}}.card{{background:#fff;border:1px solid #d9dfdd;border-radius:8px;padding:18px;margin:16px 0}}.allsvenskan{{background:#fff9ed;border-color:#f0d7a6;border-left:8px solid #d99416}}.title{{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}}.title span{{background:#d99416;color:#fff;border-radius:999px;padding:6px 10px;font-weight:800}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}.grid div{{background:#fff;border:1px solid #e8d3a7;border-radius:8px;padding:12px}}.grid small{{display:block;color:#766a54}}.grid strong{{font-size:24px;color:#875a07}}.muted{{color:#5f6f69}}table{{width:100%;border-collapse:collapse;min-width:680px}}th,td{{border-bottom:1px solid #e0ddd5;padding:10px;text-align:left}}th{{background:#fbefd7}}.table{{overflow-x:auto}}@media(max-width:760px){{.grid{{grid-template-columns:1fr 1fr}}}}
</style></head><body>
<header><h1>20260706 下一竞彩日非世界杯预测</h1><p class="muted">竞彩业务日 2026-07-06；比赛开球为北京时间 2026-07-07 01:00。已排除世界杯，只保留网站当前非世界杯比赛。</p></header>
<main>
<section class="card"><h2>今日赛果复盘修正</h2><ul>{review_items}</ul><h3>模型修正</h3><ul>{adjustments}</ul><p class="muted">{esc('；'.join(TODAY_REVIEW['pending']))}</p></section>
<section class="card"><h2>二串一模块</h2><h3>总进球</h3><div class="table"><table><thead><tr><th>比赛</th><th>选择</th><th>赔率</th><th>更新</th></tr></thead><tbody>{render_rows(p['goals'])}</tbody></table></div><h3>比分稳胆</h3><div class="table"><table><thead><tr><th>比赛</th><th>选择</th><th>赔率</th><th>更新</th></tr></thead><tbody>{render_rows(p['score'])}</tbody></table></div><h3>比分爆冷</h3><div class="table"><table><thead><tr><th>比赛</th><th>选择</th><th>赔率</th><th>更新</th></tr></thead><tbody>{render_rows(p['upset'])}</tbody></table></div><h3>半全场</h3><div class="table"><table><thead><tr><th>比赛</th><th>选择</th><th>赔率</th><th>更新</th></tr></thead><tbody>{render_rows(p['hafu'])}</tbody></table></div></section>
{''.join(cards)}
<section class="card"><h2>来源</h2><ul><li>竞彩页面：https://m.sporttery.cn/mjc/jsq/zqzjq/</li><li>接口快照：data/sporttery_20260707_latest.json</li><li>生成模型：{esc(MODEL_VERSION)}</li></ul><p class="muted">以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议。</p></section>
</main></body></html>"""


def main() -> int:
    raw = read_json(SOURCE_FILE)
    selected = [pick(item) for item in raw["matches"] if item.get("league") != "世界杯"]
    payload = {
        "date": OUTPUT_DATE,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "modelVersion": MODEL_VERSION,
        "sourceFile": str(SOURCE_FILE.relative_to(ROOT)),
        "review": TODAY_REVIEW,
        "matches": selected,
    }
    payload["parlays"] = parlays(selected)
    write_json(DATA / f"predictions_non_worldcup_{OUTPUT_DATE}.json", payload)
    day = ROOT / OUTPUT_DATE
    day.mkdir(exist_ok=True)
    html_text = render(payload)
    (day / "index.html").write_text(html_text, encoding="utf-8")
    (day / f"predict_{OUTPUT_DATE}.html").write_text(html_text, encoding="utf-8")
    (ROOT / "index.html").write_text(html_text, encoding="utf-8")
    print(f"Generated {len(selected)} non-World-Cup predictions for {OUTPUT_DATE}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
