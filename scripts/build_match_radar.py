"""Build a confirmed-facts-only match radar page from daily Sporttery data."""
from __future__ import annotations
import argparse, json, re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
NEXT_MATCHES = {
    "2040914": {"homeNext": {"text": "赫尔辛基 vs 格尼斯坦", "date": "2026-08-23 15:00"}, "awayNext": {"text": "伊尔维斯 vs 瓦萨", "date": "2026-08-22 17:00"}, "source": "https://www.veikkausliiga.com/uutiset/2025/12/19/veikkausliigan-runkosarjan-2026-otteluohjelma-julkaistaan-ennatysellisen-varhain"},
    "2040915": {"homeNext": {"text": "天狼星 vs 赫根", "date": "2026-08-21 19:00"}, "awayNext": {"text": "奥尔格里特 vs 哈尔姆斯塔德", "date": "2026-08-22 15:00"}, "source": "https://allsvenskan.se/nyheter/sa-spelas-omgang-18-23-av-allsvenskan/"},
    "2040916": {"homeNext": {"text": "加的夫城 vs 谢菲尔德联", "date": "2026-08-29 15:00"}, "awayNext": {"text": "雷克瑟姆 vs 沃特福德", "date": "2026-08-22 14:00"}, "source": "https://www.wrexhamafc.co.uk/"},
    "2040922": {"homeNext": {"text": "马拉加 vs 拉科鲁尼亚", "date": "2026-08-24 19:30"}, "awayNext": {"text": "埃尔切 vs 巴塞罗那", "date": "2026-08-23 21:30"}, "source": "https://www.laliga.com/es-CO/clubes/rc-deportivo/proximos-partidos"},
    "2040917": {"homeNext": {"text": "吉维森特 vs 卡萨皮亚", "date": "2026-08-23 时间待官方公布"}, "awayNext": {"text": "莫雷伦斯 vs 本菲卡", "date": "2026-08-23 17:00"}, "source": "https://www.casapiaac.pt/calendario.php"},
}
TEAM_ZH = {
    "Ilves": "伊尔维斯", "Gnistan": "格尼斯坦", "Halmstad": "哈尔姆斯塔德", "BK Hacken": "赫根",
    "Deportivo La Coruna": "拉科鲁尼亚", "Elche": "埃尔切", "Casa Pia": "卡萨皮亚", "Benfica": "本菲卡",
    "Remo": "里莫", "Internacional": "巴西国际", "HJK Helsinki": "赫尔辛基", "Gnistan Helsinki": "格尼斯坦",
    "Ilves Tampere": "伊尔维斯", "Vaasa VPS": "瓦萨", "Halmstads": "哈尔姆斯塔德", "Hacken": "赫根",
    "IK Sirius": "天狼星", "Sirius": "天狼星", "Orgryte IS": "奥尔格里特", "Örgryte IS": "奥尔格里特",
    "Cardiff City": "加的夫城", "Sheffield United": "谢菲尔德联", "Wrexham": "雷克瑟姆", "Watford": "沃特福德",
    "Malaga CF": "马拉加", "Málaga CF": "马拉加", "RC Deportivo": "拉科鲁尼亚", "Barcelona": "巴塞罗那",
    "Gil Vicente FC": "吉维森特", "Moreirense": "莫雷伦斯",
    "Internacional - RS": "巴西国际", "Atlético Mineiro - MG": "米内罗竞技", "Fluminense - RJ": "弗鲁米嫩塞", "Remo - PA": "里莫",
    "Vitoria Guimaraes": "吉马良斯", "Levante": "莱万特", "Villarreal CF": "比利亚雷亚尔",
    "Independ. Rivadavia": "里独立", "Fluminense": "弗鲁米嫩塞", "Levski Sofia": "索列夫",
    "AEK Athens FC": "雅典AEK", "Dinamo Zagreb": "萨格勒布迪纳摩", "Viking": "维京",
    "Fenerbahçe": "费内巴切", "Fenerbahce": "费内巴切", "Lyon": "里昂", "CA Independiente": "独立队",
    "AEK Athens": "雅典AEK", "NK Osijek": "奥西耶克", "Brodd": "布罗德", "Spartak Varna": "瓦尔纳斯巴达",
    "Iraklis": "伊拉克里斯", "Gaziantep Futbol Kulübü": "加济安泰普",
}
REASON_ZH = {
    "Injury": "伤病", "Shoulder Injury": "肩部伤病", "Groin Injury": "腹股沟伤病", "Knee Injury": "膝部伤病",
    "Muscle Injury": "肌肉伤病", "Hamstring Injury": "大腿后侧肌肉伤病", "Ankle Injury": "脚踝伤病",
    "Lower Back Injury": "下背部伤病", "Inactive": "未激活",
}
LEAGUE_ZH = {
    "Veikkausliiga": "芬兰超级联赛", "Friendlies Clubs": "俱乐部友谊赛", "Suomen Cup": "芬兰杯",
    "Allsvenskan": "瑞典超级联赛", "Svenska Cupen": "瑞典杯", "Segunda División": "西乙",
    "La Liga": "西甲", "Primeira Liga": "葡萄牙超级联赛", "Copa Do Brasil": "巴西杯", "Serie A": "巴西甲",
    "CONMEBOL Libertadores": "解放者杯", "UEFA Champions League": "欧冠",
    "CONMEBOL Libertadores": "解放者杯", "UEFA Champions League": "欧冠",
}
INJURY_REVIEWS = {
    "2040914": {
        "text": "已复核：暂无公开可核验的具体伤停名单",
        "note": "芬兰官方比赛页面说明首发通常在开赛前约 1 小时公布；当前未列出具体伤停，不能把未进名单直接等同于伤停。",
        "source": "https://www.veikkausliiga.com/tilastot/2026/veikkausliiga/ottelut/4036971/kokoonpanot/",
    },
    "2040916": {
        "text": "已复核：暂无公开可核验的具体伤停名单",
        "note": "截至本次抓取，双方官方渠道未发布本场具体伤停名单；等待赛前球队公告或官方首发后再更新，暂不作阵容完整判断。",
        "source": "https://www.cardiffcityfc.co.uk/",
    },
    "2040917": {
        "text": "已复核：暂无公开可核验的具体伤停名单",
        "note": "卡萨皮亚官方赛程已确认本场，但当前页面未发布具体伤停名单；未获得球员级证据前不填入推测记录。",
        "source": "https://www.casapiaac.pt/",
    },
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

def probs(odds, fallback=None):
    try:
        values = [1 / float(odds[k]) for k in ("home", "draw", "away")]
        total = sum(values)
        return {k: round(v / total * 100, 1) for k, v in zip(("home", "draw", "away"), values)}
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return fallback

def position_zh(value):
    return {"Goalkeeper":"门将", "Defender":"后卫", "Midfielder":"中场", "Attacker":"前锋"}.get(value, value or "位置待确认")

def status_zh(value):
    return {"Missing Fixture":"缺席", "Questionable":"出场存疑", "Suspended":"停赛"}.get(value, value or "状态记录")

def name_zh(value):
    return TEAM_ZH.get(value, value or "球队待确认")

def reason_zh(value):
    return REASON_ZH.get(value, value or "原因未记录")

def confidence_zh(value):
    return {"high":"高", "medium":"中", "low":"低"}.get(value, value or "未定")

def league_zh(value):
    return LEAGUE_ZH.get(value, value or "赛事待确认")

def importance_text(rank_value):
    if not rank_value:
        return "当前排名待更新，比赛结果将影响后续联赛形势。"
    if rank_value >= 13:
        return f"当前第 {rank_value}，需要积分摆脱下游。"
    if rank_value <= 6:
        return f"当前第 {rank_value}，争取保持上半区位置。"
    return f"当前第 {rank_value}，争取提升排名。"

def competition_text(league, round_value):
    if league in ("欧冠", "解放者杯"):
        return f"{league}{round_zh(round_value)}，本场结果将影响后续晋级形势。"
    return "暂无已确认的积分/晋级信息"

def sportscore_next_zh(value):
    if not value or not value.get("time"):
        return None
    try:
        dt = datetime.fromisoformat(value["time"].replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=8)))
        date_text = dt.strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        date_text = "时间待确认"
    return {"text":f"{name_zh(value.get('home'))} vs {name_zh(value.get('away'))}", "date":date_text, "source":value.get("source")}

def round_zh(value):
    text = str(value or "").replace("Regular Season - ", "第 ").replace(" - ", " · ")
    return (text + " 轮") if text.startswith("第 ") else (text or "赛事阶段待确认")

def build(source, contexts, external, enrichment):
    rows = []
    supplement = read(DATA / f"match_radar_supplement_{source.get('date')}.json")
    for m in source.get("matches", []):
        mid = str(m.get("matchId") or m.get("id"))
        c = contexts.get("matches", {}).get(mid, {})
        e = external.get("matches", {}).get(mid, {})
        api = enrichment.get("matches", {}).get(mid, {})
        supp = (supplement.get("matches") or {}).get(mid, {})
        supp_count = len(supp.get("home", [])) + len(supp.get("away", []))
        injuries = confirmed(c.get("injuries"), "暂无已确认的官方伤停或首发信息")
        if api.get("status") == "ok":
            if api.get("injuryCount"):
                injuries = "API已取得 " + str(api.get("injuryCount")) + " 条记录"
            else:
                injuries = "本场暂无伤停记录"
        if supp_count:
            injuries = (injuries + "；另有 " + str(supp_count) + " 条第三方赛前记录") if api.get("injuryCount") else ("已收集 " + str(supp_count) + " 条第三方赛前记录，待官方确认")
        api_evidence = (f"{api.get('round') or '赛事轮次待确认'} · {((api.get('fixture') or {}).get('status') or {}).get('long') or '状态待更新'}" if api.get("status") == "ok" else "")
        injury_rows = {"home": list(supp.get("home", [])), "away": list(supp.get("away", []))}
        if api.get("status") == "ok":
            home_api = ((api.get("teams") or {}).get("home") or {}).get("id")
            for item in api.get("injuries", []):
                side = "home" if item.get("teamId") == home_api else "away"
                row = {"player": item.get("player"), "position": position_zh(item.get("position")), "status": status_zh(item.get("status")), "reason": reason_zh(item.get("reason"))}
                if not any(x.get("player") == row.get("player") for x in injury_rows[side]):
                    injury_rows[side].append(row)
        api_odds = api.get("marketOdds") or {}
        injury_review = INJURY_REVIEWS.get(mid, {})
        injury_note = (supplement.get("sourceLabel") + "；图片记录不等同于官方最终确认。") if supp_count else (injury_review.get("note") if not api.get("injuryCount") and injury_review else ("当前伤停接口未返回本场条目；这只表示暂无可展示记录，不等同于确认阵容完整。" if not api.get("injuryCount") else ""))
        if not api.get("injuryCount") and injury_review:
            injuries = injury_review["text"]
        next_override = NEXT_MATCHES.get(mid)
        next_match = (next_override.get("homeNext", {}).get("text") if next_override else confirmed(c.get("nextMatch"), "暂无已确认的本场赛后下一场赛程"))
        sportscore_data = api.get("sportscoreNext") or {}
        sport_home_next = sportscore_next_zh(sportscore_data.get("home"))
        sport_away_next = sportscore_next_zh(sportscore_data.get("away"))
        home_next = ((next_override or {}).get("homeNext")) or sport_home_next
        away_next = ((next_override or {}).get("awayNext")) or sport_away_next
        home_rank = rank(m.get("homeRank")) or rank(c.get("homeRank"))
        away_rank = rank(m.get("awayRank")) or rank(c.get("awayRank"))
        rows.append({
            "id":mid, "lotteryNo":m.get("matchNumStr") or m.get("lotteryCode"), "league":m.get("league"),
            "kickoff":m.get("kickoff"), "home":m.get("home"), "away":m.get("away"),
            "homeRank":home_rank, "awayRank":away_rank,
            "prediction":{**(m.get("prediction") or {}), "confidence":confidence_zh((m.get("prediction") or {}).get("confidence"))}, "probabilities":probs((m.get("odds") or {}).get("had") or api_odds, probs((m.get("odds") or {}).get("hhad") or api_odds)),
            "marketOdds":{"bookmaker":api_odds.get("bookmaker"), "home":api_odds.get("home"), "draw":api_odds.get("draw"), "away":api_odds.get("away")},
            "oddsUpdatedAt":((m.get("odds") or {}).get("had") or {}).get("updatedAt"),
            "injuries":{"confirmed":bool(api.get("injuryCount")), "reviewed":bool(injury_review or supp_count), "text":injuries, "note":injury_note, "home":injury_rows["home"], "away":injury_rows["away"]},
            "rest":c.get("restDays") or {},
            "standings":confirmed(c.get("ranking"), "暂无已确认的积分榜位置"),
            "standingsBrief":{"home":home_rank, "away":away_rank},
            "rankText":f"当前联赛排名：主队第{home_rank or '—'}名 · 客队第{away_rank or '—'}名",
            "competition":confirmed(c.get("motivation"), competition_text(m.get("league"), api.get("round"))),
            "competitionBrief":round_zh(api.get("round")) + (" · 未开赛" if api.get("status") == "ok" else ""),
            "competitionPath":"杯赛走向：赛后按晋级结果读取下一轮对阵" if m.get("league") in ("欧冠", "解放者杯") or "杯" in str(m.get("league")) else "杯赛走向：本场为常规联赛，不产生杯赛晋级路径",
            "stage":confirmed(c.get("stage"), "暂无已确认的赛事阶段"),
            "fixtureEvidence": {"provider": "API-Football" if api.get("status") == "ok" else "", "fixtureId": api.get("fixtureId"), "round": api.get("round"), "venue": (api.get("fixture") or {}).get("venue"), "referee": (api.get("fixture") or {}).get("referee"), "status": ((api.get("fixture") or {}).get("status") or {}).get("long")},
            "previous":confirmed(c.get("schedule"), "暂无已确认的上一场与休息间隔"),
            "next":{"confirmed":bool(home_next or away_next), "text":(home_next or {}).get("text") if home_next else next_match, "home":home_next, "away":away_next, "homeImportance":importance_text(home_rank), "awayImportance":importance_text(away_rank)},
            "h2h":[{**x, "home":name_zh(x.get("home")), "away":name_zh(x.get("away")), "league":league_zh(x.get("league"))} for x in api.get("h2h", []) if x.get("homeGoals") is not None and x.get("awayGoals") is not None],
            "sources":list(dict.fromkeys([*e.get("sources", []), "https://www.sporttery.cn/", *([next_override["source"]] if next_override else []), *([injury_review["source"]] if injury_review else []), *(["https://sportscore.com/developers/"] if sport_home_next or sport_away_next else [])]))
        })
    return {"version":"match-radar-v1", "generatedAt":datetime.now().isoformat(timespec="seconds"), "date":source.get("date"), "dateText":source.get("dateText"), "providers":PROVIDERS, "matches":rows, "disclaimer":"以上为已确认公开信息整理后的比赛环境雷达，不构成任何购彩建议；信息会随官方更新而变化。"}

def page(payload):
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    template = """<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><meta name=\"theme-color\" content=\"#0b1f2a\"><title>比赛雷达 · __DATE__</title><link rel=\"stylesheet\" href=\"../assets/site.css\"></head><body class=\"radar-page\"><header class=\"radar-hero\"><nav><a href=\"../index.html\">← 返回预测首页</a></nav><p class=\"radar-kicker\">SPORTTERY MATCH RADAR / __DATE__</p><h1>比赛雷达</h1><p class=\"radar-deck\">一场一张事实卡：伤停、赛程负荷、积分与赛果后的下一站，只展示已经落实的公开信息。</p><div class=\"radar-meta\"><span>__COUNT__ 场</span><span>体彩业务日 __DATE_TEXT__</span><span>生成 __GENERATED__</span></div></header><main><section class=\"radar-intro\"><div><p class=\"eyebrow\">确认制数据</p><h2>先看今天的比赛，再打开每场详情</h2></div><div class=\"coverage-grid\"><div><strong>__STANDINGS__</strong><span>已有排名</span></div><div><strong>__INJURIES__</strong><span>已有伤停</span></div><div><strong>__NEXT__</strong><span>已有下一场</span></div></div></section><section class=\"radar-toolbar\"><label>筛选赛事 <select id=\"leagueFilter\"><option value=\"all\">全部赛事</option></select></label><label>检索球队 <input id=\"teamSearch\" type=\"search\" placeholder=\"主队或客队\"></label><button id=\"expandAll\" type=\"button\">展开全部</button></section><section id=\"matchList\" class=\"radar-list\"></section><section class=\"provider-panel\"><div><p class=\"eyebrow\">接口地图</p><h2>数据来源</h2><p>体彩接口作为场次主表；伤停、下一场和杯赛阶段必须由外部 provider 返回可靠记录后才进入卡片。</p></div><div id=\"providerList\" class=\"provider-list\"></div></section><p class=\"sportscore-credit\">赛程补充数据由 <a href=\"https://sportscore.com/\" target=\"_blank\" rel=\"noreferrer\">SportScore</a> 提供。</p><p class=\"radar-disclaimer\">__DISCLAIMER__</p></main><script>const RADAR=__DATA__;</script><script>
const esc=v=>String(v??'').replace(/[&<>\"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[c]));
const pct=p=>p?'主 '+p.home+'% · 平 '+p.draw+'% · 客 '+p.away+'%':'胜平负概率：暂无';
function card(m,i){const p=m.prediction||{},n=esc(m.next.text);return '<article class=\"radar-card\" data-league=\"'+esc(m.league)+'\" data-teams=\"'+esc(m.home+' '+m.away)+'\"><button class=\"card-toggle\" aria-expanded=\"'+(i===0)+'\" data-target=\"r-'+m.id+'\"><span class=\"match-index\">'+String(i+1).padStart(2,'0')+'</span><span class=\"fixture\"><small>'+esc(m.lotteryNo)+' · '+esc(m.league)+'</small><strong>'+esc(m.home)+' <em>vs</em> '+esc(m.away)+'</strong><time>'+esc(m.kickoff||'时间待确认')+'</time></span><span class=\"signal\"><b>'+esc(p.totalGoals||'—')+'</b><small>模型总进球</small></span><span class=\"chevron\">⌄</span></button><div id=\"r-'+m.id+'\" class=\"card-body\" '+(i===0?'':'hidden')+'><div class=\"radar-columns\"><div class=\"radar-block primary\"><p class=\"eyebrow\">赛前信号</p><h3>'+esc((p.scores||[]).join(' / ')||'暂无比分池')+' <small>'+esc(p.confidence||'未定')+'</small></h3><p>'+esc(pct(m.probabilities))+'</p><p class=\"muted\">赔率快照：'+esc(m.oddsUpdatedAt||'暂无记录')+'</p></div><div class=\"radar-block\"><p class=\"eyebrow\">阵容健康</p><h3>'+(m.injuries.confirmed?'已取得记录':'暂无已确认记录')+'</h3><p>'+esc(m.injuries.text)+'</p></div><div class=\"radar-block\"><p class=\"eyebrow\">积分 / 杯赛</p><h3>'+esc(m.standings)+'</h3><p>'+esc(m.competition)+'</p><p class=\"muted\">阶段：'+esc(m.stage)+'</p></div></div><div class=\"radar-columns secondary\"><div class=\"radar-block\"><p class=\"eyebrow\">上一场与休息</p><p>'+esc(m.previous)+'</p><p class=\"muted\">休息天数：'+esc(JSON.stringify(m.rest)||'暂无已确认记录')+'</p></div><div class=\"radar-block next-block\"><p class=\"eyebrow\">赛后下一站</p><h3>'+(m.next.confirmed?'已取得赛程':'暂无已确认赛程')+'</h3><p>'+n+'</p><div class=\"outcome-row\"><span><b>主胜</b>'+n+'</span><span><b>平局</b>'+n+'</span><span><b>客胜</b>'+n+'</span></div></div></div><details><summary>已采集来源</summary><p class=\"sources\">'+(m.sources.length?m.sources.map(u=>'<a href=\"'+esc(u)+'\" target=\"_blank\" rel=\"noreferrer\">来源</a>').join(' · '):'暂无已确认来源')+'</p></details></div></article>'}
function render(){const f=document.getElementById('leagueFilter').value,q=document.getElementById('teamSearch').value.trim().toLowerCase(),rows=RADAR.matches.filter(m=>(f==='all'||m.league===f)&&(!q||(m.home+' '+m.away).toLowerCase().includes(q)));document.getElementById('matchList').innerHTML=rows.length?rows.map(card).join(''):'<div class=\"empty-state\">没有匹配的场次。</div>';document.querySelectorAll('.card-toggle').forEach(b=>b.addEventListener('click',()=>{const x=document.getElementById(b.dataset.target),o=x.hidden;x.hidden=!o;b.setAttribute('aria-expanded',o)}))}
[...new Set(RADAR.matches.map(m=>m.league))].forEach(x=>document.getElementById('leagueFilter').insertAdjacentHTML('beforeend','<option>'+esc(x)+'</option>'));document.getElementById('leagueFilter').addEventListener('change',render);document.getElementById('teamSearch').addEventListener('input',render);document.getElementById('expandAll').addEventListener('click',()=>document.querySelectorAll('.card-body').forEach(x=>x.hidden=false));document.getElementById('providerList').innerHTML=RADAR.providers.map(p=>'<div class=\"provider\"><span class=\"dot '+p.status+'\"></span><div><b>'+esc(p.name)+'</b><small>'+esc(p.role)+'</small></div><a href=\"'+esc(p.url)+'\" target=\"_blank\">文档 ↗</a></div>').join('');render();</script></body></html>"""
    values = {"__DATE__":payload.get("date") or "", "__DATE_TEXT__":payload.get("dateText") or "", "__COUNT__":len(payload["matches"]), "__GENERATED__":payload["generatedAt"], "__STANDINGS__":sum(bool(m["homeRank"] and m["awayRank"]) for m in payload["matches"]), "__INJURIES__":sum(bool(m["injuries"]["confirmed"] or m["injuries"].get("reviewed")) for m in payload["matches"]), "__NEXT__":sum(m["next"]["confirmed"] for m in payload["matches"]), "__DISCLAIMER__":payload["disclaimer"], "__DATA__":data}
    for key, value in values.items(): template = template.replace(key, str(value))
    template = template.replace('content="#0b1f2a"', 'content="#f5f2eb"')
    template = template.replace('SPORTTERY MATCH RADAR', '体彩比赛雷达')
    template = template.replace('<html lang="zh-CN">', '<html lang="zh-CN" class="radar-html">')
    template = template.replace('<span>已有伤停</span>', '<span>伤停状态已核验</span>')
    template = template.replace('<body class="radar-page">', '<body class="radar-page"><a class="skip-link" href="#matchList">跳到比赛列表</a>')
    template = template.replace('id="teamSearch" type="search" placeholder="主队或客队"', 'id="teamSearch" name="team" type="search" autocomplete="off" aria-label="检索球队" placeholder="例如：本菲卡…"')
    template = template.replace('<section class="provider-panel">', '<section class="provider-panel" aria-hidden="true">')
    readable_script = r'''<script>
function radarRestText(rest){
  if(!rest || typeof rest !== 'object') return '暂无已确认记录';
  const h = rest.home != null ? '主队 '+rest.home+' 天' : '';
  const a = rest.away != null ? '客队 '+rest.away+' 天' : '';
  return [h,a].filter(Boolean).join(' · ') || '暂无已确认记录';
}
function readableCard(m,i){
  const p=m.prediction||{}, n=esc(m.next.text), ev=m.fixtureEvidence||{};
  const injuryLabel=m.injuries.confirmed?'已取得 API 记录':(m.injuries.reviewed?'已收集第三方记录，待官方确认':'暂无已确认记录');
  const market=m.marketOdds||{};
  const oddsText=(market.home&&market.draw&&market.away)?('参考水位：'+esc(market.home)+' / '+esc(market.draw)+' / '+esc(market.away)):'参考水位：暂无';
  const injuryList=(rows)=>rows&&rows.length?'<ul class="injury-list">'+rows.map(x=>'<li><strong>'+esc(x.player)+'</strong><span>'+esc(x.position)+' · '+esc(x.status)+' · '+esc(x.reason)+'</span></li>').join('')+'</ul>':'<p class="quiet">暂无已确认记录</p>';
   const history=m.h2h&&m.h2h.length?'<div class="history-list">'+m.h2h.slice(-5).reverse().map(x=>{const hg=Number(x.homeGoals),ag=Number(x.awayGoals),score=hg===ag?hg+'–'+ag:(hg>ag?'<strong>'+hg+'</strong>–'+ag:hg+'–<strong>'+ag+'</strong>');return '<span>'+esc(x.date)+' · '+esc(x.home)+' vs '+esc(x.away)+' · '+score+'</span>';}).join('')+'</div>':'<p class="quiet">暂无已取得交手记录</p>';
  const nextItem=(label,item)=>item?'<div><b>'+label+'</b><strong>'+esc(item.text)+'</strong><span>时间：'+esc(item.date)+'</span></div>':'<div><b>'+label+'</b><span>暂无已核验赛程</span></div>';
  const fixtureStatus={"Not Started":"未开赛","First Half":"上半场","Second Half":"下半场","Match Finished":"已结束","Postponed":"延期","Cancelled":"取消"};
  const fixtureLine=ev.fixtureId ? '比赛状态：'+(fixtureStatus[ev.status]||'待更新') : '比赛状态待更新';
  return '<article class="radar-card" data-league="'+esc(m.league)+'" data-teams="'+esc(m.home+' '+m.away)+'">'
   +'<button class="card-toggle" aria-expanded="'+(i===0)+'" data-target="r2-'+m.id+'"><span class="match-index">'+String(i+1).padStart(2,'0')+'</span><span class="fixture"><small>'+esc(m.lotteryNo)+' · '+esc(m.league)+'</small><strong>'+esc(m.home)+' <em>vs</em> '+esc(m.away)+'</strong><time>'+esc(m.kickoff||'时间待确认')+'</time></span><span class="signal"><b>'+esc(p.totalGoals||'—')+'</b><small>模型总进球</small></span><span class="chevron">⌄</span></button>'
   +'<div id="r2-'+m.id+'" class="card-body" '+(i===0?'':'hidden')+'><div class="radar-columns">'
   +'<div class="radar-block primary"><p class="eyebrow">赛前信号</p><h3>'+esc((p.scores||[]).join(' / ')||'暂无比分池')+' <small>'+esc(p.confidence||'未定')+'</small></h3><p>'+esc(pct(m.probabilities))+'</p><p class="odds-line">'+oddsText+'</p><p class="quiet">竞彩快照：'+esc(m.oddsUpdatedAt||'暂无记录')+'</p></div>'
   +'<div class="radar-block injury-block"><p class="eyebrow">伤停 · 主客分栏</p><h3>'+injuryLabel+'</h3><div class="injury-sides"><div><b>主队 · '+esc(m.home)+'</b>'+injuryList(m.injuries.home)+'</div><div><b>客队 · '+esc(m.away)+'</b>'+injuryList(m.injuries.away)+'</div></div>'+(m.injuries.note?'<p class="quiet injury-note">'+esc(m.injuries.note)+'</p>':'')+'</div>'
   +'<div class="radar-block"><p class="eyebrow">积分 / 赛事</p><h3>'+esc(m.rankText||'排名待确认')+'</h3><p>'+esc(m.competition)+'</p><p class="quiet">'+fixtureLine+' · '+esc(m.competitionBrief||'赛事阶段待确认')+'</p><p class="quiet">'+esc(m.competitionPath||'')+'</p></div></div>'
   +'<div class="radar-columns secondary"><div class="radar-block"><p class="eyebrow">上一场与休息</p><p>'+esc(m.previous)+'</p><p class="rest-display">'+radarRestText(m.rest)+'</p></div>'
   +'<div class="radar-block next-block"><p class="eyebrow">赛后下一站</p><h3>'+(m.next.confirmed?'主客队分别的下一场':'暂无已确认赛程')+'</h3><div class="next-sides">'+nextItem('主队 · '+m.home,m.next.home)+' '+nextItem('客队 · '+m.away,m.next.away)+'</div></div></div>'
   +'<div class="radar-block importance-block"><p class="eyebrow">本场积分意义</p><div class="importance-sides"><div><b>主队 · '+esc(m.home)+'</b><span>'+esc(m.next.homeImportance||'比赛结果将影响后续联赛形势。')+'</span></div><div><b>客队 · '+esc(m.away)+'</b><span>'+esc(m.next.awayImportance||'比赛结果将影响后续联赛形势。')+'</span></div></div></div>'
   +'<div class="radar-block history-block"><p class="eyebrow">历史交手 · 最近 5 次</p>'+history+'</div><details><summary>展开来源</summary><p class="sources">'+(m.sources.length?m.sources.map(u=>'<a href="'+esc(u)+'" target="_blank" rel="noreferrer">打开</a>').join(' · '):'暂无已确认来源')+'</p></details></div></article>';
}
card=readableCard; render();
</script></body></html>'''
    return template.replace('</body></html>', readable_script)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--date", default=datetime.now().strftime("%Y%m%d")); a=ap.parse_args()
    source=read(DATA/f"sporttery_{a.date}_latest.json")
    if not source: raise SystemExit("missing Sporttery snapshot")
    payload=build(source, read(DATA/f"match_context_{a.date}.json"), read(DATA/f"external_context_{a.date}.json"), read(DATA/f"match_radar_enrichment_{a.date}.json"))
    (DATA/f"match_radar_{a.date}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    out=ROOT/"radar"/"index.html"; out.parent.mkdir(exist_ok=True); out.write_text(page(payload),encoding="utf-8")
    print(json.dumps({"date":a.date,"matches":len(payload["matches"]),"html":str(out)},ensure_ascii=False))

if __name__=="__main__": main()
