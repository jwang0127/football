#!/usr/bin/env python3
"""Persist verified 2026-07-26 results and competition-specific review."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RESULTS = {
    "2040623": (1, 3),
    "2040624": (1, 1),
    "2040625": (1, 2),
    "2040626": (2, 1),
    "2040627": (1, 1),
    "2040628": (1, 4),
    "2040629": (0, 2),
    "2040630": (1, 0),
    "2040631": (3, 2),
    "2040632": (1, 0),
    "2040633": (1, 1),
    "2040634": (2, 1),
    "2040635": (0, 1),
    "2040636": (4, 2),
    "2040637": (3, 0),
    "2040638": (1, 1),
    "2040639": (1, 1),
    "2040640": (1, 1),
}

SOURCES = [
    {"name": "ESPN官方赛果接口（瑞超、挪超、巴甲）", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/swe.1/scoreboard?dates=20260726"},
    {"name": "ESPN官方赛果接口（挪超）", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/nor.1/scoreboard?dates=20260726"},
    {"name": "ESPN官方赛果接口（巴甲）", "url": "https://site.api.espn.com/apis/site/v2/sports/soccer/bra.1/scoreboard?dates=20260726"},
    {"name": "K League公开赛果交叉核对：首尔-蔚山", "url": "https://www.chosun.com/english/sports-en/2026/07/26/FOIXGLXXEBDFBAAAQ2PBYMAYZI/"},
    {"name": "K League公开赛果交叉核对：仁川-富川", "url": "https://iffhs.com/en/match/13566"},
    {"name": "K League公开赛果交叉核对：光州-济州", "url": "https://www.headlinejeju.co.kr/news/articleView.html?idxno=596487"},
    {"name": "K League公开赛果交叉核对：安养-江原", "url": "https://www.mk.co.kr/en/sports/12107860"},
    {"name": "Veikkausliiga官方赛事资料", "url": "https://www.veikkausliiga.com/tilastot/2026/veikkausliiga/ottelut/4036953/ennakko/"},
    {"name": "芬超赛果交叉核对：伊尔维斯-拉赫蒂", "url": "https://statsbet.org/football/matches/ilves-vs-lahti-2026-07-26"},
    {"name": "芬超赛果交叉核对：赫尔辛基-TPS", "url": "https://www.sportytrader.com/en/results-live/hjk-helsinki-tps-turku-8032435/"},
    {"name": "芬超赛果交叉核对：国际图尔库-格尼斯坦", "url": "https://www.livesoccertv.com/match/inter-turku-vs-gnistan/1cyrgv"},
]

REVIEW_ROWS = [
    {
        "league": "韩国职业联赛",
        "results": [("2040623", "1-3"), ("2040624", "1-1"), ("2040625", "1-2"), ("2040626", "2-1")],
        "summary": "方向1/4；总进球1/4；前三比分池1/4。",
        "modelAdjustment": "韩职本轮暴露主胜锚定和强队控场过度问题：增加平局与强队客胜反向路径，保留1-1、1-2和1-3条件尾部；小样本不直接抬高整体进球均值。",
    },
    {
        "league": "瑞典超级联赛",
        "results": [("2040627", "1-1"), ("2040628", "1-4"), ("2040633", "1-1"), ("2040634", "2-1")],
        "summary": "方向1/4；总进球1/4；前三比分池1/4。",
        "modelAdjustment": "瑞超同时出现两场平局和1-4尾部：提高均势盘平局保护，继续保留低比分零封，同时在强弱差和追分条件成立时审计1-3/1-4，不把单场大比分扩散到所有比赛。",
    },
    {
        "league": "芬兰超级联赛",
        "results": [("2040629", "0-2"), ("2040630", "1-0"), ("2040632", "1-0")],
        "summary": "方向2/3；总进球0/3；前三比分池1/3。",
        "modelAdjustment": "芬超本轮三个总进球预测全部偏高，降低联赛总进球偏移并提高1-0、0-1、0-2等受控比分权重；保留客队反向路径，不把零封结果解释为必然趋势。",
    },
    {
        "league": "挪威超级联赛",
        "results": [("2040631", "3-2"), ("2040635", "0-1"), ("2040636", "4-2"), ("2040637", "3-0"), ("2040638", "1-1")],
        "summary": "方向1/5；总进球1/5；前三比分池0/5。",
        "modelAdjustment": "挪超本轮方向和比分池均偏窄，结果覆盖从0-1到4-2；降低强方向置信度，扩大主客两侧追分与大比分尾部，均势盘继续保留1-1，不把联赛统一压到3球。",
    },
    {
        "league": "巴西甲级联赛",
        "results": [("2040639", "1-1"), ("2040640", "1-1")],
        "summary": "方向0/2；总进球1/2；前三比分池0/2。",
        "modelAdjustment": "巴甲两场均为1-1，样本不足以重塑基础分布；只提高均势盘平局保护和1-1/2-2审计，降低本轮主胜置信度，不把两场平局外推为全联赛小球。",
    },
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
    source = ROOT / "data/sporttery_20260726_latest.json"
    history = ROOT / "data/20260726.json"
    history.write_text(source.read_text(encoding="utf-8-sig"), encoding="utf-8")
    for name in ("data/sporttery_20260726_latest.json", "data/20260726.json", "data/predictions_20260726.json"):
        path = ROOT / name
        if path.exists():
            update(path)

    reviews = []
    match_lookup = {str(m.get("matchId") or m.get("id")): m for m in load(source).get("matches", [])}
    for item in REVIEW_ROWS:
        rows = []
        for match_id, score in item["results"]:
            match = match_lookup[match_id]
            rows.append({
                "matchId": match_id,
                "matchNumStr": match.get("matchNumStr", match_id),
                "home": match["home"],
                "away": match["away"],
                "score": score,
                "assessment": "按90分钟赛果核对方向、总进球和比分池覆盖。",
            })
        reviews.append({**item, "results": rows})
    review = {
        "reviewDate": "07-26",
        "source": "官方联赛赛果接口及公开赛果交叉核对",
        "sources": SOURCES,
        "reviews": reviews,
    }
    (ROOT / "data/review_20260726_competitions.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    settled = {
        "settlementBasis": "2026-07-26 90分钟赛果；不含加时赛或点球晋级结算",
        "sources": SOURCES,
        "results": [{"date": "20260726", "matchId": mid, "score": f"{score[0]}-{score[1]}", "source": "official/public result cross-check", "url": SOURCES[0]["url"]} for mid, score in RESULTS.items()],
    }
    (ROOT / "data/settled_results_20260726_extra.json").write_text(json.dumps(settled, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
