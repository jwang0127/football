"""Persist cross-checked 2026-08-06 results and the review lessons."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = {
    "2040718": (4, 0),  # Vitoria 4-0 Athletico-PR
    "2040729": (1, 1),  # KuPS 1-1 U Craiova
    "2040724": (2, 1),  # Jagiellonia 2-1 Rangers
    "2040725": (0, 1),  # PAOK 0-1 Anderlecht
    "2040726": (6, 1),  # Benfica 6-1 Hearts
}
SOURCES = [
    {"name": "CBF official fixture/result", "url": "https://www.cbf.com.br/futebol-brasileiro/jogos/copa-do-brasil/profissional/2026/vitoria-x-athletico-paranaense/834862"},
    {"name": "UEFA/club result cross-checks", "url": "https://www.rangers.co.uk/article/uefa-europa-league-third-qualifying-round-draw/79Em7qqyIo1"},
    {"name": "Public match reports for Europa qualification", "url": "https://www.reddit.com/r/EuropaLeague/"},
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
    for name in ("data/sporttery_20260806_latest.json", "data/predictions_20260806.json"):
        path = ROOT / name
        if path.exists():
            update(path)
    review = {
        "reviewDate": "08-06",
        "source": "CBF官方赛果、俱乐部/赛事公开赛果与多方赛后报道交叉核对",
        "sources": SOURCES,
        "reviews": [
            {"league": "巴西杯", "results": [{"matchId": "2040718", "matchNumStr": "周四001", "home": "维多利亚", "away": "巴拉纳竞技", "score": "4-0", "assessment": "主胜方向未命中；总进球与比分池均未覆盖，属于淘汰赛首回合落后后的强动机高尾部。"}], "summary": "方向0/1；主比分0/1；比分池0/1。", "modelAdjustment": "杯赛两回合场景新增首回合落后/必须追分闸门；若盘口实力差与追分动机同时成立，放宽强侧4+球尾部，但只进尾部审计，不直接挤入前三。"},
            {"league": "欧洲冠军联赛", "results": [{"matchId": "2040729", "matchNumStr": "周四002", "home": "库奥皮奥", "away": "克拉约瓦大学", "score": "1-1", "assessment": "方向、主比分均未命中；平局保护未覆盖。"}], "summary": "方向0/1；主比分0/1；比分池0/1。", "modelAdjustment": "资格赛均势盘保留1-1/0-0平局保护；不因单场结果上调平局先验。"},
            {"league": "欧洲冠军联赛", "results": [{"matchId": "2040724", "matchNumStr": "周四003", "home": "比亚韦斯托克", "away": "格拉斯哥流浪者", "score": "2-1", "assessment": "方向命中；主比分未命中；比分池未覆盖。"}], "summary": "方向1/1；主比分0/1；比分池0/1。", "modelAdjustment": "欧战资格赛主场主动性可提高一球主胜路径；但不把单场2-1转成固定模板。"},
            {"league": "欧罗巴联赛", "results": [{"matchId": "2040725", "matchNumStr": "周四004", "home": "塞萨洛尼基", "away": "安德莱赫特", "score": "0-1", "assessment": "方向、主比分与比分池均未命中；客队反击尾部漏选。"}, {"matchId": "2040726", "matchNumStr": "周四005", "home": "本菲卡", "away": "哈茨", "score": "6-1", "assessment": "方向命中；主比分、比分池和总进球均明显偏低，属于实力差与比赛开放度叠加的极端大比分。"}], "summary": "方向1/2；主比分0/2；比分池0/2。", "modelAdjustment": "欧罗巴资格赛拆分为均势/强弱两类：强弱差明显且主队进攻侧赔率、总进球4+与半全场胜胜同时支持时，追加4-0/4-1/5-0/5-1/6-1尾部状态；只做风险覆盖，不将6-1当作常规主选。均势盘继续保留0-1/1-1反击与平局路径。"},
        ],
        "globalLesson": "AI收窄预测的主要问题不是不会选强弱方向，而是把比分分布压成一条最典型路径：一是没有把两回合追分动机和强弱差作为交互项，二是把总进球主选当成比分上限，三是尾部只展示固定模板。后续公开输出分为主选/备选/尾部审计三层；尾部由赔率矩阵中的4+球、其他比分桶、半全场强侧胜胜和已核验赛制情境共同触发。",
    }
    (ROOT / "data/review_20260806_competitions.json").write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
