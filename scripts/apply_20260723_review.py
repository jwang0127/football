#!/usr/bin/env python3
"""Persist the verified 2026-07-23 results and competition review."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RESULTS = {
    "2040594": (3, 0),
    "2040593": (0, 0),
    "2040597": (1, 1),
    "2040603": (2, 1),
    "2040598": (1, 0),
    "2040599": (1, 2),
    "2040600": (2, 0),
}

SOURCES = [
    {"name": "Botafogo官方赛果：Botafogo 0-0 Vitória", "url": "https://botafogo.com.br/noticias/botafogo-0-x-0-vitoria-br26"},
    {"name": "Corinthians 3-0 Remo公开完场报道", "url": "https://www.gazetaesportiva.com/minuto-a-minuto/brasileiro-serie-a-2026/corinthians-x-remo/237742/"},
    {"name": "2026-07-23欧罗巴资格赛公开赛果汇总", "url": "https://www.footballwebpages.co.uk/20260723"},
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def result_payload(match_id: str) -> dict:
    home, away = RESULTS[match_id]
    return {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "official/public result cross-check", "urls": [x["url"] for x in SOURCES]}


def update_matches(path: Path) -> None:
    payload = load(path)
    for match in payload.get("matches", []):
        match_id = str(match.get("matchId") or match.get("id"))
        if match_id in RESULTS:
            match["result"] = result_payload(match_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    source = ROOT / "data/sporttery_20260723_latest.json"
    history = ROOT / "data/20260723.json"
    if source.exists() and not history.exists():
        history.write_text(source.read_text(encoding="utf-8-sig"), encoding="utf-8")
    for name in ("data/sporttery_20260723_latest.json", "data/20260723.json", "data/predictions_20260723.json"):
        path = ROOT / name
        if path.exists():
            update_matches(path)

    review = {
        "reviewDate": "07-23",
        "source": "俱乐部官方赛果、巴西公开完场报道及欧罗巴资格赛公开赛果交叉核对",
        "sources": SOURCES,
        "reviews": [
            {
                "league": "巴西甲级联赛",
                "results": [
                    {"matchId": "2040594", "matchNumStr": "周四201", "home": "科林蒂安", "away": "里莫", "score": "3-0", "assessment": "主胜方向命中；总进球与前三比分未覆盖"},
                    {"matchId": "2040593", "matchNumStr": "周四202", "home": "博塔弗戈", "away": "维多利亚", "score": "0-0", "assessment": "方向、总进球与前三比分均未命中"},
                ],
                "summary": "方向1/2；总进球0/2；主比分0/2。",
                "modelAdjustment": "巴甲继续小样本收缩：保留主场优势，但提高0-0/低比分保护，不因两场结果扩大参数。",
            },
            {
                "league": "欧罗巴联赛",
                "results": [
                    {"matchId": "2040597", "matchNumStr": "周四203", "home": "哈马比", "away": "安德莱赫特", "score": "1-1", "assessment": "平局方向未命中；总进球命中；三比分池覆盖1-1"},
                    {"matchId": "2040603", "matchNumStr": "周四204", "home": "圣加仑", "away": "本菲卡", "score": "2-1", "assessment": "方向、总进球与三比分池均未命中"},
                    {"matchId": "2040598", "matchNumStr": "周四205", "home": "贝西克塔斯", "away": "中日德兰", "score": "1-0", "assessment": "方向命中；总进球与三比分池未覆盖"},
                    {"matchId": "2040599", "matchNumStr": "周四206", "home": "特温特", "away": "费伦茨瓦罗斯", "score": "1-2", "assessment": "方向、总进球与三比分池均未命中"},
                    {"matchId": "2040600", "matchNumStr": "周四207", "home": "斯普利特海杜克", "away": "帕福斯", "score": "2-0", "assessment": "方向未命中；总进球命中；三比分池覆盖2-0"},
                ],
                "summary": "方向3/5；总进球2/5；三比分池覆盖2/5。",
                "modelAdjustment": "欧罗巴资格赛更新为小样本收缩：提高平局与零封低比分保护，下修总进球偏移；保留两回合追分导致的高比分尾部，不把5场样本视为稳定命中率。",
            },
        ],
    }
    (ROOT / "data/review_20260723_competitions.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
