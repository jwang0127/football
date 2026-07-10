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
MODEL_VERSION = "k-league-six-pack-0708-review-v1"
SOURCE_FILES = [DATA / "sporttery_20260711_latest.json", DATA / "sporttery_20260712_latest.json"]
OUTPUT_DATE = "20260711_0712"


REVIEW_0708 = {
    "date": "20260708",
    "sources": [
        "ESPN: Argentina 3-2 Egypt, July 7 2026",
        "ESPN: Switzerland 0-0 Colombia, July 7 2026",
        "AP: Argentina comeback from 0-2 to 3-2 vs Egypt",
    ],
    "lessons": [
        "阿根廷 3-2 埃及：强队最终方向可命中，但过程冷门领先和穿盘失败风险必须上调。",
        "瑞士 0-0 哥伦比亚：均势淘汰赛会显著压低节奏，0-0/1-1 不能被低估。",
        "迁移到韩职：强弱差距不大时，优先压低总进球；比分池优先 1-1、1-0、0-1、2-1，不追极端大比分。",
    ],
    "adjustments": {
        "draw_protection": "+0.06",
        "low_total_goals": "+0.05",
        "favorite_win_not_cover": "+0.04",
        "wide_score_suppression": "-0.05",
    },
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


def fmt(value: float | None) -> str:
    return "-" if value is None else f"{value:.2f}"


def product(rows: list[dict[str, Any]]) -> float | None:
    value = 1.0
    for row in rows:
        if row.get("odds") is None:
            return None
        value *= float(row["odds"])
    return value


def implied(had: dict[str, Any]) -> dict[str, float]:
    raw = {key: 1 / odd(had.get(key)) for key in ("home", "draw", "away") if odd(had.get(key))}
    total = sum(raw.values())
    if total <= 0:
        return {"home": 0.34, "draw": 0.30, "away": 0.36}
    return {key: raw.get(key, 0) / total for key in ("home", "draw", "away")}


def result_label(code: str) -> str:
    return {"home": "主胜", "draw": "平", "away": "客胜"}[code]


def score_direction(score: str) -> str:
    home, away = [int(part) for part in score.split("-")]
    if home > away:
        return "home"
    if home < away:
        return "away"
    return "draw"


def score_total(score: str) -> int:
    return sum(int(part) for part in score.split("-"))


def top_scores(crs: dict[str, Any]) -> list[tuple[str, float]]:
    rows = []
    for key, value in crs.items():
        if "-" in key and odd(value):
            rows.append((key, float(value)))
    return sorted(rows, key=lambda row: row[1])


def top_goals(ttg: dict[str, Any]) -> list[tuple[str, float]]:
    rows = []
    for idx in range(8):
        key = f"s{idx}"
        value = odd(ttg.get(key))
        if value:
            rows.append(("7+" if idx == 7 else str(idx), value))
    return sorted(rows, key=lambda row: row[1])


def rank_no(text: str) -> int | None:
    digits = "".join(ch for ch in str(text) if ch.isdigit())
    return int(digits) if digits else None


def hafu_key(half: str, full: str) -> str:
    letter = {"home": "h", "draw": "d", "away": "a"}
    return letter[half] + letter[full]


def pick_match(match: dict[str, Any]) -> dict[str, Any]:
    odds = match["odds"]
    probs = implied(odds["had"])
    scores = top_scores(odds["crs"])
    goals = top_goals(odds["ttg"])
    market_favorite = max(probs, key=probs.get)
    fav_gap = abs(probs["home"] - probs["away"])
    draw_prob = probs["draw"]
    home_rank = rank_no(match.get("homeRank", ""))
    away_rank = rank_no(match.get("awayRank", ""))
    rank_gap = abs(home_rank - away_rank) if home_rank and away_rank else 0

    low_score = scores[0][0]
    low_goal = goals[0][0] if goals else str(score_total(low_score))
    main_score = low_score
    direction = score_direction(main_score)
    review_reason = "按比分低赔与总进球低赔形成主线。"

    has_11 = odd(odds["crs"].get("1-1"))
    # 0708 review: improve draw/low-goal protection when market is close.
    if has_11 and (fav_gap <= 0.11 or draw_prob >= 0.285 or rank_gap <= 3):
        main_score = "1-1"
        direction = "draw"
        review_reason = "0708复盘后提高均势盘 1-1 权重。"
    elif market_favorite == "away" and fav_gap >= 0.24:
        main_score = "0-1"
        direction = "away"
        review_reason = "客胜优势清晰，但按0708复盘压低穿盘，只取小胜。"
    elif market_favorite == "home" and fav_gap >= 0.18:
        main_score = "1-0" if odd(odds["crs"].get("1-0")) else low_score
        direction = "home"
        review_reason = "主胜优势清晰，但不追穿盘。"

    total_goals = str(score_total(main_score))
    if low_goal == "2" or total_goals == "2":
        total_goals = "2"
    elif has_11 and odd(odds["crs"].get("1-1")) <= 6.0:
        total_goals = "2"

    backups: list[str] = []
    allowed = {direction, market_favorite, "draw"}
    for score, _price in scores:
        if score != main_score and score_direction(score) in allowed and score not in backups:
            backups.append(score)
        if len(backups) >= 2:
            break

    upset_dir = "draw" if direction != "draw" else ("away" if probs["away"] >= probs["home"] else "home")
    upset = next((score for score, _ in scores if score_direction(score) == upset_dir and score != main_score), backups[-1] if backups else main_score)

    half = "draw" if direction == "draw" or score_total(main_score) <= 2 else direction
    hafu = hafu_key(half, direction)
    total_key = "s7" if total_goals == "7+" else f"s{total_goals}"

    confidence = "高" if fav_gap >= 0.24 else "中"
    if direction == "draw" or draw_prob >= 0.29:
        confidence = "中低"

    return {
        "id": match["id"],
        "matchNumStr": match["matchNumStr"],
        "league": match["league"],
        "leagueCode": match["leagueCode"],
        "kickoff": match["kickoff"],
        "home": match["home"],
        "away": match["away"],
        "homeRank": match["homeRank"],
        "awayRank": match["awayRank"],
        "modelVersion": MODEL_VERSION,
        "probabilities": {key: round(value, 3) for key, value in probs.items()},
        "direction": direction,
        "directionText": result_label(direction),
        "marketFavorite": result_label(market_favorite),
        "mainScore": main_score,
        "backupScores": backups,
        "upsetScore": upset,
        "totalGoals": total_goals,
        "goalCandidates": [item[0] for item in goals[:3]],
        "confidence": confidence,
        "reviewReason": review_reason,
        "odds": odds,
        "parlay": {
            "had": {"pick": result_label(direction), "odds": odd(odds["had"].get({"home": "home", "draw": "draw", "away": "away"}[direction])), "updatedAt": odds["had"].get("updatedAt")},
            "goals": {"pick": total_goals, "odds": odd(odds["ttg"].get(total_key)), "updatedAt": odds["ttg"].get("updatedAt")},
            "score": {"pick": main_score, "odds": odd(odds["crs"].get(main_score)), "updatedAt": odds["crs"].get("updatedAt")},
            "upset": {"pick": upset, "odds": odd(odds["crs"].get(upset)), "updatedAt": odds["crs"].get("updatedAt")},
            "hafu": {"pick": hafu, "label": f"{result_label(half)}/{result_label(direction)}", "odds": odd(odds["hafu"].get(hafu)), "updatedAt": odds["hafu"].get("updatedAt")},
        },
        "marketRead": [
            f"胜平负隐含概率：主胜{probs['home']:.1%} / 平{probs['draw']:.1%} / 客胜{probs['away']:.1%}。",
            "比分低赔：" + "，".join(f"{score}@{price:.2f}" for score, price in scores[:5]) + "。",
            "总进球低赔：" + "，".join(f"{goal}球@{price:.2f}" for goal, price in goals[:3]) + "。",
        ],
    }


def load_matches() -> list[dict[str, Any]]:
    out = []
    for path in SOURCE_FILES:
        payload = read_json(path)
        for item in payload["matches"]:
            if item.get("leagueCode") == "KD1":
                out.append(item)
    return out


def row(match: dict[str, Any], kind: str) -> dict[str, Any]:
    value = match["parlay"][kind]
    return {
        "match": f"{match['matchNumStr']} {match['home']} vs {match['away']}",
        "pick": value.get("label") or value["pick"],
        "odds": value["odds"],
        "oddsText": fmt(value["odds"]),
        "updatedAt": value["updatedAt"],
    }


def add_product(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = list(rows)
    value = product(result)
    result.append({"match": "理论乘积", "pick": "", "odds": value, "oddsText": fmt(value), "updatedAt": ""})
    return result


def build_parlays(matches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    # Conservative order: clear favorite/low-goal signals first, then draw-protection pools.
    goals6 = [row(m, "goals") for m in matches]
    had3 = [row(matches[i], "had") for i in (0, 2, 5)]
    had4 = [row(matches[i], "had") for i in (0, 1, 2, 5)]
    score3 = [row(matches[i], "score") for i in (0, 2, 5)]
    upset3 = [row(matches[i], "upset") for i in (1, 3, 4)]
    mixed4 = [row(matches[0], "had"), row(matches[1], "goals"), row(matches[2], "score"), row(matches[5], "goals")]
    hafu3 = [row(matches[i], "hafu") for i in (0, 2, 5)]
    return {
        "总进球六串一": add_product(goals6),
        "胜平负三串一": add_product(had3),
        "胜平负四串一": add_product(had4),
        "比分稳胆三串一": add_product(score3),
        "比分爆冷三串一": add_product(upset3),
        "混合四串一": add_product(mixed4),
        "半全场三串一": add_product(hafu3),
    }


def render_table(rows: list[dict[str, Any]]) -> str:
    return "".join(
        f"<tr><td>{esc(item['match'])}</td><td>{esc(item['pick'])}</td><td>{esc(item['oddsText'])}</td><td>{esc(item['updatedAt'])}</td></tr>"
        for item in rows
    )


def render(payload: dict[str, Any]) -> str:
    review = "".join(f"<li>{esc(item)}</li>" for item in payload["review0708"]["lessons"])
    cards = []
    for item in payload["matches"]:
        reads = "".join(f"<li>{esc(text)}</li>" for text in item["marketRead"])
        cards.append(f"""
<section class="card kleague">
  <div class="title"><h2>{esc(item['matchNumStr'])} {esc(item['home'])} vs {esc(item['away'])}</h2><span>韩职</span></div>
  <div class="grid">
    <div><small>方向</small><strong>{esc(item['directionText'])}</strong></div>
    <div><small>总进球</small><strong>{esc(item['totalGoals'])}</strong></div>
    <div><small>主比分</small><strong>{esc(item['mainScore'])}</strong></div>
    <div><small>防冷比分</small><strong>{esc(item['upsetScore'])}</strong></div>
  </div>
  <p class="muted">开球：{esc(item['kickoff'])}；排名：{esc(item['homeRank'])} vs {esc(item['awayRank'])}；市场低赔方向：{esc(item['marketFavorite'])}；信心：{esc(item['confidence'])}</p>
  <p>比分池：{esc(item['mainScore'])} / {esc(' / '.join(item['backupScores']))}；防冷：{esc(item['upsetScore'])}；总进球候选：{esc(' / '.join(item['goalCandidates']))}。</p>
  <p><strong>复盘修正：</strong>{esc(item['reviewReason'])}</p>
  <ul>{reads}</ul>
</section>""")
    parlay_sections = []
    for name, rows in payload["parlays"].items():
        parlay_sections.append(f"<h3>{esc(name)}</h3><div class=\"table\"><table><thead><tr><th>比赛</th><th>选择</th><th>赔率</th><th>更新</th></tr></thead><tbody>{render_table(rows)}</tbody></table></div>")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>0711-0712 韩职六场预测</title>
<style>
body{{margin:0;background:#f6f8fb;color:#18202a;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.65}}header,main{{max-width:1160px;margin:auto;padding:22px 16px}}header{{background:#fff;border-bottom:1px solid #d8e0e8;position:sticky;top:0}}h1{{margin:0;font-size:30px}}h2{{margin:0 0 10px;font-size:22px}}h3{{margin:18px 0 8px}}.card{{background:#fff;border:1px solid #d8e0e8;border-radius:8px;padding:18px;margin:16px 0}}.kleague{{background:#f5fbff;border-color:#b8ddf4;border-left:8px solid #1683c7}}.title{{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}}.title span{{background:#1683c7;color:#fff;border-radius:999px;padding:6px 10px;font-weight:800}}.grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}}.grid div{{background:#fff;border:1px solid #d7eaf8;border-radius:8px;padding:12px}}.grid small{{display:block;color:#66727d}}.grid strong{{font-size:24px;color:#0f6b9f}}.muted{{color:#5f6f77}}table{{width:100%;border-collapse:collapse;min-width:720px}}th,td{{border-bottom:1px solid #dde5ec;padding:10px;text-align:left}}th{{background:#ecf6fd}}.table{{overflow-x:auto}}.notice{{border-left:8px solid #7a8ca0;background:#fbfcfd}}@media(max-width:760px){{.grid{{grid-template-columns:1fr 1fr}}}}
</style></head><body>
<header><h1>0711-0712 韩职六场预测</h1><p class="muted">仅显示网站当前 0711/0712 六场韩职；已排除世界杯和其他联赛。赔率来源：Sporttery getMatchCalculatorV1，更新时间 {esc(payload['lastUpdateTime'])}。</p></header>
<main>
<section class="card notice"><h2>0708 赛果复盘与模型优化</h2><ul>{review}</ul><p class="muted">参考来源：ESPN/AP 等公开赛果报道；本页把复盘结论迁移为韩职的低进球和平局保护修正。</p></section>
<section class="card"><h2>n 串组合</h2>{''.join(parlay_sections)}</section>
{''.join(cards)}
<section class="card"><h2>数据来源</h2><ul><li>竞彩赔率页面：https://m.sporttery.cn/mjc/jsq/zqzjq/</li><li>接口快照：data/sporttery_20260711_latest.json、data/sporttery_20260712_latest.json</li><li>0708 复盘参考：Argentina 3-2 Egypt；Switzerland 0-0 Colombia</li></ul><p class="muted">以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议。</p></section>
</main></body></html>"""


def main() -> int:
    raw_matches = load_matches()
    if len(raw_matches) != 6:
        raise RuntimeError(f"Expected 6 K League matches, got {len(raw_matches)}")
    predictions = [pick_match(item) for item in raw_matches]
    payload = {
        "date": OUTPUT_DATE,
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "modelVersion": MODEL_VERSION,
        "lastUpdateTime": max(read_json(path).get("lastUpdateTime", "") for path in SOURCE_FILES),
        "review0708": REVIEW_0708,
        "matches": predictions,
        "parlays": build_parlays(predictions),
    }
    write_json(DATA / f"predictions_{OUTPUT_DATE}.json", payload)
    day = ROOT / OUTPUT_DATE
    day.mkdir(exist_ok=True)
    html_text = render(payload)
    (day / "index.html").write_text(html_text, encoding="utf-8")
    (day / f"predict_{OUTPUT_DATE}.html").write_text(html_text, encoding="utf-8")
    (ROOT / "index.html").write_text(html_text, encoding="utf-8")
    print(f"Generated {len(predictions)} K League predictions for {OUTPUT_DATE}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
