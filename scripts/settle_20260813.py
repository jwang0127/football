import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SCORES = {
    "2040832": "1-2", "2040821": "2-1", "2040822": "3-3", "2040833": "3-2",
    "2040823": "1-3", "2040824": "1-1", "2040825": "1-1", "2040826": "1-1",
    "2040827": "1-1", "2040828": "0-0",
}
SOURCE = "LiveScore.mobi daily scoreboard, cross-checked with FOX Sports/UEFA where available"

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def patch_matches(path):
    obj = read(path)
    for m in obj.get("matches", []):
        mid = str(m.get("matchId") or m.get("id"))
        if mid in SCORES:
            h, a = map(int, SCORES[mid].split("-"))
            m["result"] = {"homeGoals": h, "awayGoals": a, "status": "Finished", "source": SOURCE}
    write(path, obj)

def direction(score):
    h, a = map(int, score.split("-"))
    return "home" if h > a else "away" if h < a else "draw"

def review():
    source = read(DATA / "sporttery_20260813_latest.json")
    pred = read(DATA / "predictions_20260813.json")
    rows = []
    for m in source["matches"]:
        mid = str(m.get("matchId") or m.get("id"))
        score = SCORES[mid]
        p = next((x for x in pred.get("matches", []) if str(x.get("matchId") or x.get("id")) == mid), m)
        rows.append({"matchId": mid, "matchNumStr": m.get("matchNumStr"), "league": m.get("league"), "home": m.get("home"), "away": m.get("away"), "score": score, "predictedDirection": p.get("direction"), "direction": direction(score), "directionHit": p.get("direction") == direction(score), "mainScore": p.get("mainScore", ""), "mainHit": p.get("mainScore") == score, "poolHit": score in (p.get("scorePool") or p.get("scores") or [])})
    hits = sum(r["directionHit"] for r in rows)
    main = sum(r["mainHit"] for r in rows)
    pool = sum(r["poolHit"] for r in rows)
    grouped = {}
    for row in rows:
        grouped.setdefault(row["league"], []).append(row)
    reviews = []
    for league, group in grouped.items():
        reviews.append({"league": league, "results": group, "summary": f"方向命中 {sum(x['directionHit'] for x in group)}/{len(group)}；主比分命中 {sum(x['mainHit'] for x in group)}/{len(group)}；比分池命中 {sum(x['poolHit'] for x in group)}/{len(group)}", "modelAdjustment": "纳入滚动校准；淘汰赛增加平局与尾部高球保护，南美杯保留0-0/1-1保护。"})
    review = {"reviewDate": "20260813", "source": SOURCE, "settlementBasis": "90-minute result; extra time and penalties excluded", "results": rows, "reviews": reviews, "summary": f"方向命中 {hits}/{len(rows)}；主比分命中 {main}/{len(rows)}；比分池命中 {pool}/{len(rows)}", "globalLesson": "昨日失败不是单一爆冷：欧联首回合/次回合淘汰赛出现高比分平局与尾部大球，旧模型把市场主方向误当作比分确定性；南美两场则是低节奏平局。后续对淘汰赛提高平局与3球以上尾部覆盖，南美杯保留0-0/1-1保护，不把大球串与比分串共用同一套强信号。"}
    write(DATA / "review_20260813_competitions.json", review)
    write(DATA / "settled_results_20260813_auto.json", {"settlementBasis": "90-minute result", "source": SOURCE, "results": [{"date": "20260813", "matchId": k, "score": v, "source": SOURCE} for k, v in SCORES.items()]})

for path in [DATA / "sporttery_20260813_latest.json", DATA / "predictions_20260813.json"]:
    patch_matches(path)
review()
print("settled", len(SCORES))
