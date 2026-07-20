#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DISCLAIMER = "以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。"
DAILY_RE = re.compile(r"predictions_(\d{8})\.json$")
ARCHIVES = [
    ("20260716_0717", "07-16—07-17", "首版跨日预测与复盘存档"),
    ("20260712_0714", "07-12—07-14", "三日预测历史存档"),
    ("20260711_0712", "07-11—07-12", "韩职与瑞超历史存档"),
]


def load_daily_rows(root: Path = ROOT) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in (root / "data").glob("predictions_*.json"):
        match = DAILY_RE.fullmatch(path.name)
        if not match:
            continue
        compact = match.group(1)
        page = root / compact / "index.html"
        if not page.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        matches = payload.get("matches", [])
        leagues = list(dict.fromkeys(row.get("league", "") for row in matches if row.get("league")))
        rows.append({
            "date": compact,
            "label": datetime.strptime(compact, "%Y%m%d").strftime("%Y-%m-%d"),
            "href": f"{compact}/index.html",
            "description": f"{len(matches)} 场 · {' / '.join(leagues) if leagues else '赛程预测'}",
        })
        seen.add(compact)
    # Preserve older single-day pages whose historical JSON used a prefixed
    # filename such as predictions_non_worldcup_YYYYMMDD.json.
    for page in root.glob("????????/index.html"):
        compact = page.parent.name
        if compact in seen or not compact.isdigit():
            continue
        candidates = sorted((root / "data").glob(f"predictions_*{compact}*.json"))
        payload = json.loads(candidates[0].read_text(encoding="utf-8-sig")) if candidates else {"matches": []}
        matches = payload.get("matches", [])
        leagues = list(dict.fromkeys(row.get("league", "") for row in matches if row.get("league")))
        rows.append({
            "date": compact,
            "label": datetime.strptime(compact, "%Y%m%d").strftime("%Y-%m-%d"),
            "href": f"{compact}/index.html",
            "description": f"{len(matches)} 场 · {' / '.join(leagues) if leagues else '历史单日预测'}",
        })
    return sorted(rows, key=lambda row: row["date"], reverse=True)


def render(root: Path = ROOT) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    daily = load_daily_rows(root)
    items: list[str] = []
    for index, row in enumerate(daily):
        badge = "最新更新" if index == 0 else "每日预测"
        items.append(
            f'<a class="date-row" href="{esc(row["href"])}"><span class="badge">{badge}</span>'
            f'<h2>竞彩业务日 {esc(row["label"])}</h2><p>{esc(row["description"])}</p><b>预测、复盘与串关 →</b></a>'
        )
    for folder, label, description in ARCHIVES:
        if (root / folder / "index.html").exists():
            items.append(
                f'<a class="date-row" href="{folder}/index.html"><span class="badge">历史存档</span>'
                f'<h2>{label}</h2><p>{esc(description)}</p><b>查看历史页面 →</b></a>'
            )
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#116b62"><title>足球预测日期首页</title><link rel="stylesheet" href="assets/site.css"></head><body><header><h1>足球预测</h1><p class="lead">按 Sporttery 竞彩业务日倒序排列；每日页面开头包含上一业务日复盘，随后是当日预测与串关。</p></header><main><section class="date-list">{''.join(items)}</section><a class="history" href="history/index.html">进入完整历史归档 →</a></main><footer>{DISCLAIMER}</footer></body></html>'''


def generate_homepage(root: Path = ROOT) -> Path:
    path = root / "index.html"
    path.write_text(render(root), encoding="utf-8")
    return path


if __name__ == "__main__":
    output = generate_homepage()
    print(f"Generated {output}")
