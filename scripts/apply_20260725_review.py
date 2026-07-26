#!/usr/bin/env python3
"""Persist verified 2026-07-25 results and competition-specific review."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = {
    "2040612": (3, 2),
    "2040613": (0, 2),
    "2040614": (0, 1),
    "2040615": (1, 1),
    "2040616": (2, 1),
    "2040617": (1, 3),
    "2040618": (2, 1),
    "2040619": (0, 2),
    "2040620": (2, 2),
    "2040621": (0, 1),
    "2040622": (1, 1),
}
SOURCES = [
    {"name": "ESPN官方赛果接口（巴甲、MLS、挪超）", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/usa.1/scoreboard?dates=20260725"},
    {"name": "ESPN官方赛果接口（瑞超）", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/swe.1/scoreboard?dates=20260725"},
    {"name": "K League公开赛果交叉核对", "url": "https://www.soccerstats.com/round_details.asp?league=southkorea&mrevid=m115&st1=5&st2=11"},
    {"name": "Veikkausliiga官方赛果", "url": "https://www.veikkausliiga.com/tilastot/2026/veikkausliiga/ottelut/4036949/raportti/"},
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
    source = ROOT / "data/sporttery_20260725_latest.json"
    history = ROOT / "data/20260725.json"
    history.write_text(source.read_text(encoding="utf-8-sig"), encoding="utf-8")
    for name in ("data/sporttery_20260725_latest.json", "data/20260725.json", "data/predictions_20260725.json"):
        path = ROOT / name
        if path.exists():
            update(path)
    review = {
        "reviewDate": "07-25",
        "source": "官方联赛赛果、ESPN赛果接口及公开赛果交叉核对",
        "sources": SOURCES,
        "reviews": [
            {"league": "韩国职业联赛", "results": [{"matchId": "2040612", "score": "3-2"}, {"matchId": "2040613", "score": "0-2"}], "summary": "方向1/2；总进球1/2；比分池1/2。", "modelAdjustment": "维持韩职独立模型；保留主场低比分与强队客胜路径，避免单日绝杀结果造成过度上调。"},
            {"league": "瑞典超级联赛", "results": [{"matchId": "2040614", "score": "0-1"}, {"matchId": "2040618", "score": "2-1"}], "summary": "方向2/2；总进球1/2；比分池1/2。", "modelAdjustment": "继续保留主场反向与零封路径；对热门主队不追加单场置信度。"},
            {"league": "芬兰超级联赛", "results": [{"matchId": "2040615", "score": "1-1"}, {"matchId": "2040617", "score": "1-3"}], "summary": "方向0/2；总进球1/2；比分池1/2。", "modelAdjustment": "小样本继续收缩：提高平局与客队反向路径权重，保留低比分保护，不追随单日大比分。"},
            {"league": "挪威超级联赛", "results": [{"matchId": "2040616", "score": "2-1"}], "summary": "方向1/1；总进球1/1；比分池1/1。", "modelAdjustment": "样本仍小，保持现有挪超参数，不将单场命中外推为稳定优势。"},
            {"league": "巴西甲级联赛", "results": [{"matchId": "2040619", "score": "0-2"}, {"matchId": "2040620", "score": "2-2"}], "summary": "方向1/2；总进球1/2；比分池1/2。", "modelAdjustment": "继续使用小样本收缩，保留客胜与平局保护，并扩大强弱差下的零封客胜尾部。"},
            {"league": "美国职业大联盟", "results": [{"matchId": "2040621", "score": "0-1"}, {"matchId": "2040622", "score": "1-1"}], "summary": "方向1/2；总进球1/2；比分池1/2。", "modelAdjustment": "维持MLS独立模型；保留客胜及平局保护，不因两场样本调整基础权重。"},
        ],
    }
    match_lookup = {str(m.get("matchId") or m.get("id")): m for m in load(source).get("matches", [])}
    for item in review["reviews"]:
        for row in item["results"]:
            match = match_lookup[row["matchId"]]
            row.update({
                "matchNumStr": match.get("matchNumStr", match.get("lotteryCode", row["matchId"])),
                "home": match["home"],
                "away": match["away"],
                "assessment": "按90分钟赛果核对方向、总进球和比分池覆盖。",
            })
    (ROOT / "data/review_20260725_competitions.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
