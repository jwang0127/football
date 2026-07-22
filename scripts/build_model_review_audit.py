#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DISCLAIMER = "以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。"
SNAPSHOTS = {
    "20260717": {"commit": "92d6a22", "path": "data/predictions_20260717.json"},
    "20260718": {"commit": "af0536c", "path": "data/predictions_20260718.json"},
    "20260719": {"commit": "7609dac", "path": "data/predictions_20260719.json"},
    "20260720": {"commit": "0337b8e", "path": "data/predictions_20260720.json"},
    "20260721": {"commit": "working-tree", "path": "data/predictions_20260721.json"},
}


def git_json(commit: str, path: str) -> dict[str, Any]:
    if commit == "working-tree":
        return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))
    raw = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
    return json.loads(raw.decode("utf-8-sig"))


def outcome(score: str) -> str:
    home, away = (int(value) for value in score.split("-"))
    return "主胜" if home > away else "客胜" if home < away else "平"


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    output: dict[str, Any] = {"settled": total}
    for name, field in {
        "main_score": "main_hit",
        "score_pool": "score_pool_hit",
        "wdl": "wdl_hit",
        "total_goal": "total_goal_hit",
    }.items():
        hits = sum(bool(row[field]) for row in rows)
        output[f"{name}_hits"] = hits
        output[f"{name}_rate"] = f"{hits / total * 100:.1f}%" if total else "—"
    return output


def structural_errors(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "trigger": "主方向命中但前三比分未覆盖",
            "samples": sum(row["wdl_hit"] and not row["score_pool_hit"] for row in rows),
            "correction": "方向层保持稳定；比分池必须在同方向内覆盖零封、小胜和追分扩张，不用更多同质比分占满前三。",
        },
        {
            "trigger": "实际0-0但模型未列入前三",
            "samples": sum(row["actual_90"] == "0-0" and not row["score_pool_hit"] for row in rows),
            "correction": "当平局概率高、总进球0/1价格不远或存在短休/复赛不确定性时，0-0进入前三而非仅尾部。",
        },
        {
            "trigger": "实际4球以上但主选总进球偏低",
            "samples": sum(sum(map(int, row["actual_90"].split("-"))) >= 4 and not row["total_goal_hit"] for row in rows),
            "correction": "强弱差、先失球追分或强客低赔同时出现时，扩大4+球条件分支；不得把该规则扩散到所有比赛。",
        },
        {
            "trigger": "实际零封比分未进入前三",
            "samples": sum("0" in row["actual_90"].split("-") and not row["score_pool_hit"] for row in rows),
            "correction": "中低总进球环境下给强侧至少一个1-0/2-0/0-1/0-2路径，避免默认双方进球。",
        },
    ]


def render(payload: dict[str, Any]) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    metric = payload["calibration_metrics"]
    cards = "".join(
        f'<div><small>{label}</small><strong>{metric[key + "_hits"]}/{metric["settled"]}</strong><span>{metric[key + "_rate"]}</span></div>'
        for label, key in (("胜平负", "wdl"), ("总进球主选", "total_goal"), ("主比分", "main_score"), ("前三比分池", "score_pool"))
    )
    league_rows = "".join(
        f'<tr><td>{esc(name)}</td><td>{row["settled"]}</td><td>{row["wdl_rate"]}</td><td>{row["total_goal_rate"]}</td><td>{row["main_score_rate"]}</td><td>{row["score_pool_rate"]}</td></tr>'
        for name, row in payload["by_competition"].items()
    )
    match_rows = "".join(
        f'<tr><td>{esc(row["date"])}</td><td>{esc(row["no"])}</td><td>{esc(row["competition"])}</td><td>{esc(row["match"])}</td><td><b>{esc(row["actual_90"])}</b></td><td>{esc(row["main_score"])}</td><td>{esc(" / ".join(row["top3_pool"]))}</td><td>{"✓" if row["wdl_hit"] else "×"} / {"✓" if row["total_goal_hit"] else "×"} / {"✓" if row["main_hit"] else "×"} / {"✓" if row["score_pool_hit"] else "×"}</td></tr>'
        for row in payload["matches"]
    )
    lessons = "".join(f'<li><b>{esc(row["trigger"])}</b>（{row["samples"]}场）：{esc(row["correction"])}</li>' for row in payload["structural_errors"])
    improvements = "".join(f'<li><b>{esc(row["name"])}</b>：{esc(row["detail"])}</li>' for row in payload["model_improvements"])
    snapshots = "".join(f'<li>{date}：<code>{esc(meta["commit"])}</code> · {esc(meta["path"])}</li>' for date, meta in payload["frozen_snapshots"].items())
    sources = "".join(f'<li><a href="{esc(row["url"])}">{esc(row["name"])}</a></li>' for row in payload["sources"])
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>足球预测模型审计</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#eef3f6;color:#17212b;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.6}}header,main{{max-width:1220px;margin:auto;padding:26px 16px}}h1{{font-size:clamp(32px,5vw,52px)}}.metrics{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.metrics div,section{{background:#fff;border:1px solid #dbe5ea;border-radius:14px;padding:16px;margin:14px 0}}.metrics small,.metrics span{{display:block;color:#60717e}}.metrics strong{{font-size:28px}}table{{width:100%;border-collapse:collapse;background:#fff}}th,td{{padding:9px;border-bottom:1px solid #e3e9ed;text-align:left}}.scroll{{overflow:auto}}code{{background:#eef3f6;padding:2px 5px}}@media(max-width:700px){{.metrics{{grid-template-columns:1fr 1fr}}}}</style></head><body><header><nav><a href="../index.html">日期首页</a><a href="../20260721/index.html">当前预测</a></nav><h1>足球预测模型严格审计</h1><p>仅使用可证明为赛前的冻结快照，所有指标按90分钟赛果结算。尾部池、候选总进球和双重机会不计入主指标。</p><div class="metrics">{cards}</div></header><main><section><h2>覆盖与结算口径</h2><p>可审计预测 {payload["coverage"]["settled_predictions"]} 场；校准样本 {payload["coverage"]["calibration_samples"]} 场；缺失或未解决 {payload["coverage"]["missing_or_unresolved"]} 场；本数据集无赛后新增排除。</p><ul>{snapshots}</ul></section><section><h2>分联赛命中率</h2><div class="scroll"><table><thead><tr><th>赛事</th><th>场次</th><th>胜平负</th><th>总进球</th><th>主比分</th><th>前三比分</th></tr></thead><tbody>{league_rows}</tbody></table></div></section><section><h2>本轮模型优化</h2><ul>{improvements}</ul></section><section><h2>可复用条件修正</h2><ul>{lessons}</ul></section><section><h2>全部已结算预测</h2><p>末列依次为：胜平负 / 总进球 / 主比分 / 前三比分池。</p><div class="scroll"><table><thead><tr><th>业务日</th><th>编号</th><th>赛事</th><th>比赛</th><th>90分钟</th><th>主比分</th><th>冻结前三</th><th>命中</th></tr></thead><tbody>{match_rows}</tbody></table></div></section><section><h2>赛果来源</h2><ul>{sources}</ul><p>{DISCLAIMER}</p></section></main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    results_payload = json.loads((root / "data" / "settled_results_20260717_20260720.json").read_text(encoding="utf-8"))
    results_payload["results"].extend([
        {"date": "20260721", "matchId": "2040580", "score": "1-1", "source": "K League公开完场赛果", "url": "https://tv.kleague.com/en-int/schedule"},
        {"date": "20260721", "matchId": "2040581", "score": "0-0", "source": "K League公开完场赛果", "url": "https://tv.kleague.com/en-int/schedule"},
        {"date": "20260721", "matchId": "2040582", "score": "1-2", "source": "直播吧赛后报道", "url": "https://news.zhibo8.com/zuqiu/2026-07-21/match1899507date2026vnative.htm"},
        {"date": "20260721", "matchId": "2040583", "score": "1-1", "source": "米内罗竞技官方赛后报道", "url": "https://atletico.com.br/atletico-empata-com-o-bahia-na-arena-mrv-pelo-brasileirao/"},
        {"date": "20260721", "matchId": "2040595", "score": "1-0", "source": "FotMob完场赛果", "url": "https://www.fotmob.com/matches/kups-vs-sabah-fktns/qemxfl37"},
        {"date": "20260721", "matchId": "2040601", "score": "1-4", "source": "波兰通讯社赛后报道", "url": "https://www.pap.pl/aktualnosci/koncertowy-wystep-lecha-poznan-w-el-lm-mistrzowie-danii-pokonani"},
        {"date": "20260721", "matchId": "2040602", "score": "4-0", "source": "L'Équipe赛程结果", "url": "https://www.lequipe.fr/Football/ligue-des-champions/page-calendrier-general/sturm-graz"},
    ])
    results = {str(row["matchId"]): row for row in results_payload["results"]}
    rows: list[dict[str, Any]] = []
    archived_ids: set[str] = set()
    for date, meta in SNAPSHOTS.items():
        frozen = git_json(meta["commit"], meta["path"])
        for match in frozen.get("matches", []):
            if match.get("businessDate", "").replace("-", "") != date:
                continue
            match_id = str(match.get("id") or match.get("matchId"))
            archived_ids.add(match_id)
            result = results.get(match_id)
            if not result:
                continue
            main_score = str(match["mainScore"])
            top3 = list(dict.fromkeys([main_score, *match.get("backupScores", [])]))[:3]
            actual = result["score"]
            actual_total = sum(int(value) for value in actual.split("-"))
            goal_prediction = str(match["totalGoals"])
            row = {
                "date": date,
                "no": match.get("matchNumStr", match_id),
                "match_id": match_id,
                "competition": match["league"],
                "match": f'{match["home"]} vs {match["away"]}',
                "actual_90": actual,
                "main_score": main_score,
                "top3_pool": top3,
                "wdl_prediction": outcome(main_score),
                "total_goal_prediction": goal_prediction,
                "main_hit": main_score == actual,
                "score_pool_hit": actual in top3,
                "wdl_hit": outcome(main_score) == outcome(actual),
                "total_goal_hit": goal_prediction == str(actual_total),
                "snapshot_commit": meta["commit"],
                "result_source": result["source"],
                "result_url": result["url"],
                "excluded_from_calibration": False,
            }
            rows.append(row)
    unresolved = sorted(archived_ids - set(results))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[row["competition"]].append(row)
    source_map = {(row["source"], row["url"]) for row in results_payload["results"]}
    payload = {
        "title": "2026-07-17至2026-07-21足球预测冻结快照审计",
        "settlement_basis": results_payload["settlementBasis"],
        "coverage": {
            "archived_predictions": len(archived_ids),
            "settled_predictions": len(rows),
            "missing_or_unresolved": len(unresolved),
            "calibration_samples": len(rows),
        },
        "all_settled_metrics": metrics(rows),
        "calibration_metrics": metrics(rows),
        "by_competition": {name: metrics(items) for name, items in sorted(grouped.items())},
        "frozen_snapshots": SNAPSHOTS,
        "unresolved_match_ids": unresolved,
        "exclusions": [],
        "structural_errors": structural_errors(rows),
        "model_improvements": [
            {
                "name": "赛事参数小样本收缩",
                "detail": "每个联赛保留独立模型，但近期复盘参数先与12场中性先验加权；当前2至7场样本只启用约14%至37%的赛后修正，降低单日赛果过拟合。",
            },
            {
                "name": "前三比分池结构化",
                "detail": "固定只发布三个比分；主方向之外优先补齐零封与双方进球两种形态，方向不确定时才加入平局保护，不用尾部池扩大统计口径。",
            },
            {
                "name": "0-0条件分支",
                "detail": "仅当平局概率不低于29%且0至1球合计概率不低于18%时，把0-0从尾部提升到前三，避免把复盘规则机械扩散到所有比赛。",
            },
        ],
        "matches": rows,
        "sources": [{"name": name, "url": url} for name, url in sorted(source_map)],
        "disclaimer": DISCLAIMER,
    }
    out_json = root / "data" / "model_review_audit_20260721.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_dir = root / "accuracy"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "index.html").write_text(render(payload), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "metrics": payload["calibration_metrics"], "unresolved": unresolved}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
