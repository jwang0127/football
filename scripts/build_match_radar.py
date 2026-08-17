"""Build a confirmed-facts-only match radar page from daily Sporttery data."""
from __future__ import annotations
import argparse, json, re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NEXT_MATCHES = {
    "2040914": {"text": "2026-08-23 15:00：HJK 主场 vs IF Gnistan", "source": "https://www.veikkausliiga.com/uutiset/2025/12/19/veikkausliigan-runkosarjan-2026-otteluohjelma-julkaistaan-ennatysellisen-varhain"},
    "2040915": {"text": "2026-08-21 19:00：IK Sirius 主场 vs BK Häcken", "source": "https://allsvenskan.se/nyheter/sa-spelas-omgang-18-23-av-allsvenskan/"},
    "2040916": {"text": "2026-08-22：Cardiff City 主场 vs Derby County", "source": "https://www.cardiffcity-mad.co.uk/news/tmnw/championship_fixtures_2026_27_989234/index.shtml"},
    "2040922": {"text": "2026-08-24 19:30：Málaga CF 主场 vs RC Deportivo", "source": "https://www.laliga.com/es-NG/clubes/rc-deportivo/proximos-partidos"},
    "2040917": {"text": "2026-08-23：Gil Vicente FC 主场 vs Casa Pia AC", "source": "https://www.casapiaac.pt/calendario.php"},
}
PROVIDERS = [
    {"name":"体彩 Sporttery", "role":"业务日、场次、赔率、竞彩编号", "status":"active", "url":"https://www.sporttery.cn/"},
    {"name":"ESPN / SofaScore", "role":"赛果与赛程兜底", "status":"fallback", "url":"https://www.sofascore.com/"},
    {"name":"API-Football", "role":"伤停、停赛、积分、未来赛程（需 key）", "status":"optional", "url":"https://www.api-football.com/documentation-v3"},
    {"name":"SportMonks", "role":"杯赛阶段、积分、伤停与赛程（需 token）", "status":"optional", "url":"https://docs.sportmonks.com/v3/"},
]

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}

def rank(value):
    m = re.search(r"(\d+)", str(value or ""))
    return int(m.group(1)) if m else None

def confirmed(value, fallback):
    text = str(value or "").strip()
    bad = ("未找到", "未核验", "待", "仍需", "无法", "不能", "未取得", "不作")
    return fallback if not text or any(x in text for x in bad) else text

def probs(odds):
    try:
        values = [1 / float(odds[k]) for k in ("home", "draw", "away")]
        total = sum(values)
        return {k: round(v / total * 100, 1) for k, v in zip(("home", "draw", "away"), values)}
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None

def build(source, contexts, external, enrichment):
    rows = []
    for m in source.get("matches", []):
        mid = str(m.get("matchId") or m.get("id"))
        c = contexts.get("matches", {}).get(mid, {})
        e = external.get("matches", {}).get(mid, {})
        api = enrichment.get("matches", {}).get(mid, {})
        injuries = confirmed(c.get("injuries"), "暂无已确认的官方伤停或首发信息")
        if api.get("status") == "ok":
            if api.get("injuryCount"):
                names = [f"{x.get('player')}（{x.get('status') or '状态记录'}）" for x in api.get("injuries", []) if x.get("player")]
                injuries = "API-Football 已返回 " + str(api.get("injuryCount")) + " 条伤停记录：" + "、".join(names[:8])
            else:
                injuries = "API-Football 本场伤停接口返回 0 条记录"
        api_evidence = (f"API-Football fixture {api.get('fixtureId')}；赛事轮次：{api.get('round') or '暂无'}；比赛状态：{((api.get('fixture') or {}).get('status') or {}).get('long') or '暂无'}" if api.get("status") == "ok" else "")
        next_override = NEXT_MATCHES.get(mid)
        next_match = next_override["text"] if next_override else confirmed(c.get("nextMatch"), "暂无已确认的本场赛后下一场赛程")
        rows.append({
            "id":mid, "lotteryNo":m.get("matchNumStr") or m.get("lotteryCode"), "league":m.get("league"),
            "kickoff":m.get("kickoff"), "home":m.get("home"), "away":m.get("away"),
            "homeRank":rank(m.get("homeRank")) or c.get("homeRank"), "awayRank":rank(m.get("awayRank")) or c.get("awayRank"),
            "prediction":m.get("prediction") or {}, "probabilities":probs((m.get("odds") or {}).get("had")),
            "oddsUpdatedAt":((m.get("odds") or {}).get("had") or {}).get("updatedAt"),
            "injuries":{"confirmed":bool(api.get("injuryCount")) or (api.get("status") != "ok" and not injuries.startswith("暂无")), "text":injuries},
            "rest":c.get("restDays") or {},
            "standings":(confirmed(c.get("ranking"), "暂无已确认的积分榜位置") + ("；" + api_evidence if api_evidence else "")),
            "competition":confirmed(c.get("motivation"), "暂无已确认的积分/晋级信息"),
            "stage":confirmed(c.get("stage"), "暂无已确认的赛事阶段"),
            "fixtureEvidence": {"provider": "API-Football" if api.get("status") == "ok" else "", "fixtureId": api.get("fixtureId"), "round": api.get("round"), "venue": (api.get("fixture") or {}).get("venue"), "referee": (api.get("fixture") or {}).get("referee"), "status": ((api.get("fixture") or {}).get("status") or {}).get("long")},
            "previous":confirmed(c.get("schedule"), "暂无已确认的上一场与休息间隔"),
            "next":{"confirmed":not next_match.startswith("暂无"), "text":next_match},
            "sources":list(dict.fromkeys([*e.get("sources", []), "https://www.sporttery.cn/", *([next_override["source"]] if next_override else [])]))
        })
    return {"version":"match-radar-v1", "generatedAt":datetime.now().isoformat(timespec="seconds"), "date":source.get("date"), "dateText":source.get("dateText"), "providers":PROVIDERS, "matches":rows, "disclaimer":"以上为已确认公开信息整理后的比赛环境雷达，不构成任何购彩建议；信息会随官方更新而变化。"}

def page(payload):
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    template = """<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"theme-color\" content=\"#0b1f2a\"><title>比赛雷达 · __DATE__</title><link rel=\"stylesheet\" href=\"../assets/site.css\"></head><body class=\"radar-page\"><header class=\"radar-hero\"><nav><a href=\"../index.html\">← 返回预测首页</a></nav><p class=\"radar-kicker\">SPORTTERY MATCH RADAR / __DATE__</p><h1>比赛雷达</h1><p class=\"radar-deck\">一场一张事实卡：伤停、赛程负荷、积分与赛果后的下一站，只展示已经落实的公开信息。</p><div class=\"radar-meta\"><span>__COUNT__ 场</span><span>体彩业务日 __DATE_TEXT__</span><span>生成 __GENERATED__</span></div></header><main><section class=\"radar-intro\"><div><p class=\"eyebrow\">确认制数据</p><h2>先看今天的比赛，再打开每场详情</h2></div><div class=\"coverage-grid\"><div><strong>__STANDINGS__</strong><span>已有排名</span></div><div><strong>__INJURIES__</strong><span>已有伤停</span></div><div><strong>__NEXT__</strong><span>已有下一场</span></div></div></section><section class=\"radar-toolbar\"><label>筛选赛事 <select id=\"leagueFilter\"><option value=\"all\">全部赛事</option></select></label><label>检索球队 <input id=\"teamSearch\" type=\"search\" placeholder=\"主队或客队\"></label><button id=\"expandAll\" type=\"button\">展开全部</button></section><section id=\"matchList\" class=\"radar-list\"></section><section class=\"provider-panel\"><div><p class=\"eyebrow\">接口地图</p><h2>数据来源</h2><p>体彩接口作为场次主表；伤停、下一场和杯赛阶段必须由外部 provider 返回可靠记录后才进入卡片。</p></div><div id=\"providerList\" class=\"provider-list\"></div></section><p class=\"radar-disclaimer\">__DISCLAIMER__</p></main><script>const RADAR=__DATA__;</script><script>
const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
const pct=p=>p?'主 '+p.home+'% · 平 '+p.draw+'% · 客 '+p.away+'%':'胜平负概率：暂无';
function card(m,i){const p=m.prediction||{},n=esc(m.next.text);return '<article class=\"radar-card\" data-league=\"'+esc(m.league)+'\" data-teams=\"'+esc(m.home+' '+m.away)+'\"><button class=\"card-toggle\" aria-expanded=\"'+(i===0)+'\" data-target=\"r-'+m.id+'\"><span class=\"match-index\">'+String(i+1).padStart(2,'0')+'</span><span class=\"fixture\"><small>'+esc(m.lotteryNo)+' · '+esc(m.league)+'</small><strong>'+esc(m.home)+' <em>vs</em> '+esc(m.away)+'</strong><time>'+esc(m.kickoff||'时间待确认')+'</time></span><span class=\"signal\"><b>'+esc(p.totalGoals||'—')+'</b><small>模型总进球</small></span><span class=\"chevron\">⌄</span></button><div id=\"r-'+m.id+'\" class=\"card-body\" '+(i===0?'':'hidden')+'><div class=\"radar-columns\"><div class=\"radar-block primary\"><p class=\"eyebrow\">赛前信号</p><h3>'+esc((p.scores||[]).join(' / ')||'暂无比分池')+' <small>'+esc(p.confidence||'未定')+'</small></h3><p>'+esc(pct(m.probabilities))+'</p><p class=\"muted\">赔率快照：'+esc(m.oddsUpdatedAt||'暂无记录')+'</p></div><div class=\"radar-block\"><p class=\"eyebrow\">阵容健康</p><h3>'+(m.injuries.confirmed?'已取得记录':'暂无已确认记录')+'</h3><p>'+esc(m.injuries.text)+'</p></div><div class=\"radar-block\"><p class=\"eyebrow\">积分 / 杯赛</p><h3>'+esc(m.standings)+'</h3><p>'+esc(m.competition)+'</p><p class=\"muted\">阶段：'+esc(m.stage)+'</p></div></div><div class=\"radar-columns secondary\"><div class=\"radar-block\"><p class=\"eyebrow\">上一场与休息</p><p>'+esc(m.previous)+'</p><p class=\"muted\">休息天数：'+esc(JSON.stringify(m.rest)||'暂无已确认记录')+'</p></div><div class=\"radar-block next-block\"><p class=\"eyebrow\">赛后下一站</p><h3>'+(m.next.confirmed?'已取得赛程':'暂无已确认赛程')+'</h3><p>'+n+'</p><div class=\"outcome-row\"><span><b>主胜</b>'+n+'</span><span><b>平局</b>'+n+'</span><span><b>客胜</b>'+n+'</span></div></div></div><details><summary>已采集来源</summary><p class=\"sources\">'+(m.sources.length?m.sources.map(u=>'<a href=\"'+esc(u)+'\" target=\"_blank\" rel=\"noreferrer\">来源</a>').join(' · '):'暂无已确认来源')+'</p></details></div></article>'}
function render(){const f=document.getElementById('leagueFilter').value,q=document.getElementById('teamSearch').value.trim().toLowerCase(),rows=RADAR.matches.filter(m=>(f==='all'||m.league===f)&&(!q||(m.home+' '+m.away).toLowerCase().includes(q)));document.getElementById('matchList').innerHTML=rows.length?rows.map(card).join(''):'<div class=\"empty-state\">没有匹配的场次。</div>';document.querySelectorAll('.card-toggle').forEach(b=>b.addEventListener('click',()=>{const x=document.getElementById(b.dataset.target),o=x.hidden;x.hidden=!o;b.setAttribute('aria-expanded',o)}))}
[...new Set(RADAR.matches.map(m=>m.league))].forEach(x=>document.getElementById('leagueFilter').insertAdjacentHTML('beforeend','<option>'+esc(x)+'</option>'));document.getElementById('leagueFilter').addEventListener('change',render);document.getElementById('teamSearch').addEventListener('input',render);document.getElementById('expandAll').addEventListener('click',()=>document.querySelectorAll('.card-body').forEach(x=>x.hidden=false));document.getElementById('providerList').innerHTML=RADAR.providers.map(p=>'<div class=\"provider\"><span class=\"dot '+p.status+'\"></span><div><b>'+esc(p.name)+'</b><small>'+esc(p.role)+'</small></div><a href=\"'+esc(p.url)+'\" target=\"_blank\">文档 ↗</a></div>').join('');render();</script></body></html>"""
    values = {"__DATE__":payload.get("date") or "", "__DATE_TEXT__":payload.get("dateText") or "", "__COUNT__":len(payload["matches"]), "__GENERATED__":payload["generatedAt"], "__STANDINGS__":sum(bool(m["homeRank"] and m["awayRank"]) for m in payload["matches"]), "__INJURIES__":sum(m["injuries"]["confirmed"] for m in payload["matches"]), "__NEXT__":sum(m["next"]["confirmed"] for m in payload["matches"]), "__DISCLAIMER__":payload["disclaimer"], "__DATA__":data}
    for key, value in values.items(): template = template.replace(key, str(value))
    return template

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--date", default=datetime.now().strftime("%Y%m%d")); a=ap.parse_args()
    source=read(DATA/f"sporttery_{a.date}_latest.json")
    if not source: raise SystemExit("missing Sporttery snapshot")
    payload=build(source, read(DATA/f"match_context_{a.date}.json"), read(DATA/f"external_context_{a.date}.json"), read(DATA/f"match_radar_enrichment_{a.date}.json"))
    (DATA/f"match_radar_{a.date}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    out=ROOT/"radar"/"index.html"; out.parent.mkdir(exist_ok=True); out.write_text(page(payload),encoding="utf-8")
    print(json.dumps({"date":a.date,"matches":len(payload["matches"]),"html":str(out)},ensure_ascii=False))

if __name__=="__main__": main()
