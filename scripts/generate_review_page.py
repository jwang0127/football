#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()
    payload = json.loads((ROOT / "data" / f"review_{args.date}.json").read_text(encoding="utf-8-sig"))
    summary = payload["summary"]
    cards = []
    for competition, block in payload["byCompetition"].items():
        rows = []
        for match in block["matches"]:
            marks = " / ".join([
                f"方向{'✓' if match['directionHit'] else '×'}",
                f"进球{'✓' if match['goalHit'] else '×'}",
                f"主比分{'✓' if match['exactHit'] else '×'}",
                f"比分池{'✓' if match['poolHit'] else '×'}",
            ])
            rows.append(f'''<article><h3>{esc(match['match'])} <b>{esc(match['result'])}</b></h3><p>原预测：{esc(match['prediction'])}</p><p class="marks">{esc(marks)}</p><p>{esc(match['lesson'])}</p></article>''')
        cards.append(f'''<section><h2>{esc(competition)}独立复盘</h2><p class="update">{esc(block['modelUpdate'])}</p>{''.join(rows)}</section>''')
    sources = "".join(f'<li><a href="{esc(row["url"])}">{esc(row["name"])}</a></li>' for row in payload["sources"])
    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{args.date}足球复盘</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#eef3f6;color:#17212b;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.65}}header,main{{max-width:1100px;margin:auto;padding:25px 16px}}nav a{{margin-right:12px}}h1{{font-size:clamp(30px,5vw,48px)}}.summary{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}}.summary div,section,article{{background:white;border:1px solid #dce5ea;border-radius:13px;padding:15px;margin:12px 0}}.summary strong{{display:block;font-size:25px}}section{{border-left:9px solid #287d70}}article{{background:#f8fafb}}article h3{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}.update{{color:#185b8a;font-weight:700}}.marks{{color:#516674}}@media(max-width:680px){{.summary{{grid-template-columns:1fr 1fr}}}}</style></head><body><header><nav><a href="../index.html">日期首页</a><a href="index.html">07-17预测原页</a><a href="../20260718/index.html">07-18预测</a><a href="../20260719/index.html">07-19预测</a></nav><h1>07-17赛果复盘</h1><p>按 Sporttery 竞彩业务日、按赛事分别复盘；延期场不计，本日无延期。</p><div class="summary"><div>方向<strong>{summary['directionHits']}/{summary['matches']}</strong></div><div>总进球<strong>{summary['totalGoalHits']}/{summary['matches']}</strong></div><div>主比分<strong>{summary['exactScoreHits']}/{summary['matches']}</strong></div><div>比分池<strong>{summary['scorePoolHits']}/{summary['matches']}</strong></div></div></header><main>{''.join(cards)}<section><h2>赛果来源</h2><ul>{sources}</ul><p>{esc(payload['disclaimer'])}</p></section></main></body></html>'''
    out = ROOT / args.date
    out.mkdir(exist_ok=True)
    (out / "review.html").write_text(page, encoding="utf-8")
    print(f"Generated review for {args.date}: {summary['matches']} matches")


if __name__ == "__main__":
    main()
