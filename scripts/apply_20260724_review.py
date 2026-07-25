#!/usr/bin/env python3
"""Persist the verified 2026-07-24 results and league review."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = {"2040610": (2, 1), "2040611": (2, 0)}
SOURCES = [
    {"name": "Veikkausliiga/IFFHS：SJK 1-2 FF Jaro", "url": "https://iffhs.com/it/match/44330"},
    {"name": "瑞典媒体：Västerås 2-0 Örgryte", "url": "https://www.aftonbladet.se/sportbladet/fotboll/a/M79AoE/taonsas-succe-sankte-ois-med-dubbla-mal"},
]


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def result(match_id: str) -> dict:
    home, away = RESULTS[match_id]
    return {"homeGoals": home, "awayGoals": away, "status": "Finished", "source": "official/public result cross-check", "urls": [x["url"] for x in SOURCES]}


def update(path: Path) -> None:
    payload = load(path)
    for match in payload.get("matches", []):
        match_id = str(match.get("matchId") or match.get("id"))
        if match_id in RESULTS:
            match["result"] = result(match_id)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    source = ROOT / "data/sporttery_20260724_latest.json"
    history = ROOT / "data/20260724.json"
    if source.exists() and not history.exists():
        history.write_text(source.read_text(encoding="utf-8-sig"), encoding="utf-8")
    for name in ("data/sporttery_20260724_latest.json", "data/20260724.json", "data/predictions_20260724.json"):
        path = ROOT / name
        if path.exists():
            update(path)

    review = {
        "reviewDate": "07-24",
        "source": "芬超、瑞超公开完场报道交叉核对",
        "sources": SOURCES,
        "reviews": [
            {
                "league": "芬兰超级联赛",
                "results": [{"matchId": "2040610", "matchNumStr": "周五201", "home": "雅罗", "away": "塞伊奈约基", "score": "2-1", "assessment": "方向未命中；总进球命中；前三比分未覆盖"}],
                "summary": "方向0/1；总进球1/1；主比分0/1。",
                "modelAdjustment": "芬超继续小样本收缩：不追随客队低赔锚定，保留主场反向路径与低比分保护；短样本不提高方向置信度。",
            },
            {
                "league": "瑞典超级联赛",
                "results": [{"matchId": "2040611", "matchNumStr": "周五202", "home": "韦斯特罗斯", "away": "厄尔格里特", "score": "2-0", "assessment": "方向命中；总进球未命中；比分池覆盖2-0"}],
                "summary": "方向1/1；总进球0/1；主比分1/1。",
                "modelAdjustment": "瑞超维持主方向与零封路径，但下修单场总进球偏高倾向；2-0保护继续保留，不把单场命中当作稳定优势。",
            },
        ],
    }
    (ROOT / "data/review_20260724_competitions.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
