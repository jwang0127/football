#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import importlib.util
import json
import math
from datetime import datetime, timedelta
from itertools import combinations
from pathlib import Path
from typing import Any

from generate_homepage import generate_homepage

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DISCLAIMER = "以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。"
MIN_COMBO_ODDS = 15.0
MAX_PARLAYS = 10
HIGH_ODDS_THRESHOLD = 20.0
HIGH_ODDS_SLOTS = 5
REVIEW_SHRINKAGE_PRIOR = 12
ANALYSIS_DIMENSIONS = (
    "schedule_load", "rest_fatigue", "travel_home_advantage", "squad_availability",
    "recent_performance", "coach_tactics", "motivation_competition", "weather_pitch",
    "set_piece_transition", "market_contradiction",
)
MARKET_TEXT = {"had": "胜平负", "ttg": "总进球", "crs": "比分", "hafu": "半全场"}
HAFU_TEXT = {"hh": "胜/胜", "hd": "胜/平", "ha": "胜/负", "dh": "平/胜", "dd": "平/平", "da": "平/负", "ah": "负/胜", "ad": "负/平", "aa": "负/负"}
EXCLUDED_BY_DATE: dict[str, dict[str, str]] = {
    "20260718": {"法国|英格兰": ""}
}
EXCLUDED_LEAGUES = {"世界杯"}

# Each competition has its own calibration.  The weights are deliberately kept
# here (rather than hidden in one global predictor) so a review changes only the
# competition that produced the evidence.
COMPETITION_MODELS: dict[str, dict[str, Any]] = {
    "韩国职业联赛": {"version": "k-league-v7-review-0722", "review_sample": 12, "had": .30, "crs": .47, "prior": .23,
                 "prior_probs": (.46, .29, .25), "goal_shift": .00, "draw_boost": 1.06,
                 "clean_sheet_boost": 1.08, "confidence_delta": -2,
                 "lesson": "07-21韩职复盘：新增3场方向0/3、总进球1/3、前三比分1/3；降低方向锚定权重，继续保留低进球与1-1/0-0平局保护，并把1-2反向路径纳入条件尾部。"},
    "瑞典超级联赛": {"version": "allsvenskan-v9-review-0724", "review_sample": 9, "had": .34, "crs": .49, "prior": .17,
                 "prior_probs": (.37, .30, .33), "goal_shift": -0.10, "draw_boost": 1.12,
                 "clean_sheet_boost": 1.22, "confidence_delta": -3,
                 "lesson": "07-24瑞超复盘：方向1/1、总进球0/1、比分池覆盖1/1；下修总进球偏高倾向，继续保留主胜与零封路径。"},
    "挪威超级联赛": {"version": "eliteserien-v6-review-0722", "review_sample": 9, "had": .42, "crs": .45, "prior": .13,
                 "prior_probs": (.44, .26, .30), "goal_shift": -0.04, "draw_boost": 1.05,
                 "clean_sheet_boost": 1.12, "confidence_delta": -2,
                 "lesson": "07-18挪超复盘：方向4/6、主比分2/6；保留0-0零封分支，同时放宽客胜3球以上长尾，避免统一压低进球均值。"},
    "芬兰超级联赛": {"version": "veikkausliiga-v7-review-0724", "review_sample": 7, "had": .35, "crs": .50, "prior": .15,
                 "prior_probs": (.38, .31, .31), "goal_shift": -0.16, "draw_boost": 1.14,
                 "clean_sheet_boost": 1.22, "confidence_delta": -4,
                 "lesson": "07-24芬超复盘：方向0/1、总进球1/1；不追随客队低赔锚定，保留主场反向路径、低比分保护与追分尾部。"},
    "巴西甲级联赛": {"version": "brasileirao-v7-review-0722", "review_sample": 3, "had": .36, "crs": .47, "prior": .17,
                 "prior_probs": (.43, .31, .26), "goal_shift": -0.10, "draw_boost": 1.16,
                 "clean_sheet_boost": 1.09, "confidence_delta": -3,
                 "lesson": "07-21巴甲复盘：米内罗竞技1-1巴伊亚，主胜锚定未覆盖平局；单场样本仅轻量提升1-1与平局保护，继续小样本收缩。"},
    "美国职业大联盟": {"version": "mls-v6-review-0722", "review_sample": 3, "had": .41, "crs": .45, "prior": .14,
                 "prior_probs": (.43, .25, .32), "goal_shift": -0.05, "draw_boost": .98,
                 "clean_sheet_boost": 1.18, "confidence_delta": -3,
                 "lesson": "07-17美职复盘：方向2/2，但1-0与0-3零封路径漏选，提高零封尾部。"},
    "欧罗巴联赛": {"version": "uel-qualifying-v4-review-0723", "review_sample": 5, "had": .39, "crs": .45, "prior": .16,
                "prior_probs": (.42, .30, .28), "goal_shift": -.08, "draw_boost": 1.10,
                "clean_sheet_boost": 1.10, "confidence_delta": -4,
                "lesson": "07-23欧罗巴复盘：方向3/5、总进球2/5、三比分池覆盖2/5；小样本提高平局与零封低比分保护，下修总进球偏移，保留两回合追分高比分尾部。"},
    "欧洲冠军联赛": {"version": "ucl-qualifying-v6-review-0722", "review_sample": 4, "had": .39, "crs": .44, "prior": .17,
                 "prior_probs": (.44, .29, .27), "goal_shift": .10, "draw_boost": 1.06,
                 "clean_sheet_boost": 1.08, "confidence_delta": -4,
                 "lesson": "07-21欧冠资格赛复盘：1-0、1-4、4-0，方向2/3但总进球0/3；扩大4+球与强侧零封/强客4球路径，同时保留低比分控节奏分支。"},
}
EXTRA_MATCHES_BY_DATE = {
    "20260718": ("data/sporttery_20260719_latest.json", "韩国职业联赛")
}


def load_base():
    path = ROOT / "scripts" / "generate_0716_0717_predictions.py"
    spec = importlib.util.spec_from_file_location("daily_base", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    module.LEAGUE_STYLES.update({
        "瑞典超级联赛": {"class": "swe", "color": "#176da3", "label": "瑞超"},
        "韩国职业联赛": {"class": "kor", "color": "#b33e5c", "label": "韩职"},
        "芬兰超级联赛": {"class": "fin", "color": "#16766c", "label": "芬超"},
    })
    return module


def num(value: Any) -> float | None:
    try:
        return None if value in (None, "") else float(value)
    except (TypeError, ValueError):
        return None


def normalized(values: dict[str, float]) -> dict[str, float]:
    total = sum(values.values())
    return {key: (value / total if total else 0.0) for key, value in values.items()}


def latest_competition_review(target_date: str, data_dir: Path = DATA) -> dict[str, Any] | None:
    """Return the newest completed review strictly before the target board."""
    candidates: list[tuple[str, Path]] = []
    for path in data_dir.glob("review_*_competitions.json"):
        compact = path.stem.removeprefix("review_").removesuffix("_competitions")
        if len(compact) == 8 and compact.isdigit() and compact < target_date:
            candidates.append((compact, path))
    if not candidates:
        return None
    _, path = max(candidates)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def shrink_review_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Temper post-match adjustments until a competition has enough evidence.

    Twelve neutral pseudo-matches keep a two-to-seven-match review from making
    a full-strength parameter jump.  The league prior remains league-specific;
    only parameters changed by recent result reviews are shrunk.
    """
    sample = max(0, int(profile.get("review_sample", 0)))
    strength = sample / (sample + REVIEW_SHRINKAGE_PRIOR) if sample else 0.0
    effective = dict(profile)
    for key, neutral in (("had", .40), ("crs", .45), ("prior", .15)):
        effective[key] = neutral + strength * (float(profile[key]) - neutral)
    effective["goal_shift"] = strength * float(profile.get("goal_shift", 0.0))
    effective["draw_boost"] = 1.0 + strength * (float(profile.get("draw_boost", 1.0)) - 1.0)
    effective["clean_sheet_boost"] = 1.0 + strength * (float(profile.get("clean_sheet_boost", 1.0)) - 1.0)
    effective["confidence_delta"] = round(strength * int(profile.get("confidence_delta", 0)))
    effective["review_strength"] = round(strength, 4)
    return effective


def inverse_market(rows: dict[str, Any], keys: tuple[str, ...]) -> dict[str, float]:
    return normalized({key: 1 / num(rows.get(key)) for key in keys if num(rows.get(key))})


def competition_direction_probabilities(match: dict[str, Any], profile: dict[str, Any]) -> dict[str, float]:
    had = inverse_market(match.get("odds", {}).get("had") or {}, ("home", "draw", "away"))
    crs_totals = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for score, price in (match.get("odds", {}).get("crs") or {}).items():
        if "-" not in score or not num(price):
            continue
        home, away = (int(value) for value in score.split("-"))
        crs_totals["home" if home > away else "away" if home < away else "draw"] += 1 / float(price)
    crs = normalized(crs_totals)
    prior = dict(zip(("home", "draw", "away"), profile["prior_probs"]))
    # If HAD is not offered, its weight is reassigned to the score matrix.
    had_weight = profile["had"] if len(had) == 3 else 0.0
    crs_weight = profile["crs"] + (profile["had"] - had_weight)
    blended = {key: had_weight * had.get(key, 0) + crs_weight * crs.get(key, 0) + profile["prior"] * prior[key]
               for key in ("home", "draw", "away")}
    blended["draw"] *= profile["draw_boost"]
    return normalized(blended)


def apply_match_context(probabilities: dict[str, float], context: dict[str, Any]) -> dict[str, float]:
    """Apply evidence-backed, match-specific factors after the market/league baseline."""
    multipliers = context.get("outcomeMultipliers", {})
    adjusted = {
        key: probabilities[key] * max(0.55, min(2.00, float(multipliers.get(key, 1.0))))
        for key in ("home", "draw", "away")
    }
    return normalized(adjusted)


def market_volatility_audit(match: dict[str, Any], probabilities: dict[str, float], goal_probs: dict[str, float]) -> dict[str, Any]:
    """Describe measurable cup volatility without making misconduct allegations."""
    if match.get("league") != "欧洲冠军联赛":
        return {
            "level": "常规",
            "factors": ["联赛模型按常规盘口与比分矩阵校准"],
            "confidencePenalty": 0,
            "note": "未触发杯赛高波动附加层。",
        }
    ordered = sorted(probabilities.items(), key=lambda row: row[1], reverse=True)
    gap = ordered[0][1] - ordered[1][1]
    low_mass = sum(goal_probs.get(str(i), 0.0) for i in range(3))
    high_mass = sum(goal_probs.get(str(i), 0.0) for i in range(4, 7)) + goal_probs.get("7+", 0.0)
    factors = ["杯赛/资格赛存在两回合策略和领先后控节奏路径"]
    if gap <= .10:
        factors.append("胜平负方向接近，意外结果风险按平局保护处理")
    if low_mass >= .42:
        factors.append("0至2球市场质量较高，保留0-0/1-0式受控比分")
    if high_mass >= .24:
        factors.append("4球以上尾部不可忽略，保留追分导致的大比分路径")
    return {
        "level": "高" if gap <= .10 or (low_mass >= .42 and high_mass >= .24) else "中高",
        "factors": factors,
        "confidencePenalty": -3 if gap <= .10 else -2,
        "note": "仅依据官方赔率、比分矩阵和总进球分布审计盘口分歧；无公开证据时不认定假球、故意输或故意平。",
    }


def competition_goal_probabilities(match: dict[str, Any], profile: dict[str, Any], context: dict[str, Any]) -> dict[str, float]:
    market = inverse_market(match.get("odds", {}).get("ttg") or {}, tuple(f"s{i}" for i in range(8)))
    if not market:
        return {"2": 1.0}
    mean = sum((7 if key == "s7" else int(key[1:])) * value for key, value in market.items())
    target = mean + profile["goal_shift"] + float(context.get("goalShift", 0.0))
    adjusted = {}
    for key, value in market.items():
        goals = 7 if key == "s7" else int(key[1:])
        adjusted["7+" if goals == 7 else str(goals)] = value * math.exp(-0.18 * (goals - target) ** 2)
    return normalized(adjusted)


def competition_score_pool(match: dict[str, Any], probabilities: dict[str, float], goal_probs: dict[str, float], profile: dict[str, Any], context: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    ranked: list[tuple[str, float]] = []
    for score, price in (match.get("odds", {}).get("crs") or {}).items():
        if "-" not in score or not num(price):
            continue
        home, away = (int(value) for value in score.split("-"))
        outcome = "home" if home > away else "away" if home < away else "draw"
        goals = home + away
        goal_key = "7+" if goals >= 7 else str(goals)
        likelihood = (1 / float(price)) * (0.55 + probabilities[outcome]) * (0.55 + goal_probs.get(goal_key, 0))
        if home == 0 or away == 0:
            likelihood *= profile["clean_sheet_boost"]
        likelihood *= max(0.65, min(1.75, float(context.get("scoreBoosts", {}).get(score, 1.0))))
        ranked.append((score, likelihood))
    ranked.sort(key=lambda row: row[1], reverse=True)
    if not ranked:
        return "1-1", ["1-0", "0-1", "2-1"], []
    direction = max(probabilities, key=probabilities.get)
    def outcome(score: str) -> str:
        home, away = (int(value) for value in score.split("-"))
        return "home" if home > away else "away" if home < away else "draw"

    aligned = [score for score, _ in ranked if outcome(score) == direction]
    main = aligned[0] if aligned else ranked[0][0]
    ordered = [score for score, _ in ranked if score != main]

    # The public pool stays at exactly three scores, but avoids spending both
    # alternatives on the same goal shape.  For a home/away call, first cover
    # the opposite clean-sheet/BTTS path inside that direction.  The last slot
    # is a draw hedge only when the direction is genuinely uncertain.
    backups: list[str] = []
    main_home, main_away = (int(value) for value in main.split("-"))
    main_clean_sheet = main_home == 0 or main_away == 0
    if direction != "draw":
        contrast = next((score for score in ordered
                         if outcome(score) == direction
                         and ((int(score.split("-")[0]) == 0 or int(score.split("-")[1]) == 0) != main_clean_sheet)), None)
        if contrast:
            backups.append(contrast)

    low_goal_mass = sum(goal_probs.get(str(goals), 0.0) for goals in (0, 1))
    if probabilities.get("draw", 0.0) >= .29 and low_goal_mass >= .18 and "0-0" in ordered:
        backups.append("0-0")

    prefer_hedge = probabilities[direction] < .48
    if len(backups) < 2:
        for score in ordered:
            if score in backups:
                continue
            if prefer_hedge and not any(outcome(item) != direction for item in backups):
                if outcome(score) == direction:
                    continue
            backups.append(score)
            if len(backups) == 2:
                break
    for score in ordered:
        if len(backups) == 2:
            break
        if score not in backups:
            backups.append(score)
    tails = [score for score, _ in ranked[6:]
             if score in {"0-0", "0-3", "1-3", "1-4", "2-2", "3-0"}
             and score not in {main, *backups}][:3]
    return main, backups, tails


def predict_by_competition(base: Any, match: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    source_profile = COMPETITION_MODELS[match["league"]]
    profile = shrink_review_profile(source_profile)
    predicted = base.predict(match)
    market_probabilities = competition_direction_probabilities(match, profile)
    probabilities = apply_match_context(market_probabilities, context)
    goal_probs = competition_goal_probabilities(match, profile, context)
    volatility = market_volatility_audit(match, probabilities, goal_probs)
    main, backups, tails = competition_score_pool(match, probabilities, goal_probs, profile, context)
    preferred_scores = [score for score in context.get("preferredScores", []) if num(match.get("odds", {}).get("crs", {}).get(score))]
    if len(preferred_scores) >= 3:
        main, backups = preferred_scores[0], preferred_scores[1:3]
    direction = max(probabilities, key=probabilities.get)
    # Public pages intentionally show exactly three confidence-ranked scores:
    # the primary score plus the two strongest remaining alternatives. Tail
    # risks stay in their own audit field and do not inflate the recommendation.
    backups = backups[:2]
    reasoning = build_reasoning_contract(match, direction, context, main, backups)
    predicted.update({
        "probabilities": {key: round(value, 4) for key, value in probabilities.items()},
        "direction": direction,
        "directionText": {"home": "主胜", "draw": "平", "away": "客胜"}[direction],
        "mainScore": main,
        "backupScores": backups,
        "tailRiskScores": tails,
        "totalGoals": max(goal_probs, key=goal_probs.get),
        "goalCandidates": sorted(goal_probs, key=goal_probs.get, reverse=True)[:3],
        "marketBaselineProbabilities": {key: round(value, 4) for key, value in market_probabilities.items()},
        "confidenceScore": max(25, min(82, predicted["confidenceScore"] + profile["confidence_delta"] + volatility["confidencePenalty"] + int(context.get("confidenceDelta", 0)))),
        "modelProfile": {**{key: profile[key] for key in ("version", "had", "crs", "prior", "goal_shift", "review_sample", "review_strength")}, "contextLayer": "evidence-chain-v2", "reviewMethod": "12场中性先验收缩 + 多维证据闸门"},
        "modelLesson": source_profile["lesson"],
        "contextFactors": {key: context.get(key, "资料不足，保持中性") for key in ("stage", "schedule", "motivation", "weather", "teamNews", "coach", "upsetPath")},
        "contextSources": context.get("sources", []),
        "evidenceStatus": context.get("evidenceStatus", "比赛级公开证据不足；情境层保持中性"),
        "verifiedFactors": context.get("verifiedFactors", []),
        "reasoningMethod": "evidence-chain-v2",
        "reasoningContract": reasoning,
        "analysisDimensions": reasoning["dimensionReport"]["dimensions"],
        "missingAnalysisDimensions": reasoning["dimensionReport"]["missingDimensions"],
        "analysisCompleteness": reasoning["dimensionReport"]["completeness"],
        "marketRiskLevel": volatility["level"],
        "marketRiskFactors": volatility["factors"],
        "marketRiskNote": volatility["note"],
        "reason": context.get("judgement") or f"盘口、比分矩阵与总进球模型综合后主方向为{ {'home': '主胜', 'draw': '平', 'away': '客胜'}[direction] }；未核实的传闻不进入模型。",
    })
    predicted["confidence"] = "高" if predicted["confidenceScore"] >= 65 else "中" if predicted["confidenceScore"] >= 52 else "中低"
    return predicted


def context_for_match(match: dict[str, Any], raw_context: dict[str, Any]) -> dict[str, Any]:
    """Make the evidence gate explicit for every match.

    A missing match report is not permission to invent injuries, motivation or
    tactics.  The market and score matrix remain usable, while the qualitative
    layer stays neutral and confidence is reduced until match-level evidence is
    sourced and checked.
    """
    def sanitize(value: Any) -> Any:
        if isinstance(value, str):
            return value.replace("图片", "未核实资料").replace("截图", "未核实资料")
        if isinstance(value, dict):
            return {key: sanitize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [sanitize(item) for item in value]
        return value

    context = sanitize(dict(raw_context or {}))
    if context.get("sources"):
        context.setdefault("evidenceStatus", "已取得比赛级公开来源；方向性修正仅使用可核验因素")
        context.setdefault("verifiedFactors", [key for key in ("stage", "schedule", "motivation", "weather", "teamNews", "coach", "upsetPath") if context.get(key)])
        context.setdefault("analysisBasis", "Sporttery赔率与比分矩阵为市场基线；赛程、积分动机、状态、伤停或战术因素仅在公开来源可核验时进入情境层。")
    else:
        context.update({
            "evidenceStatus": "比赛级公开证据不足；情境层保持中性",
            "verifiedFactors": [],
            "confidenceDelta": min(int(context.get("confidenceDelta", 0)), -8),
            "analysisBasis": "Sporttery赔率、比分矩阵与联赛模型为基线；未取得足够比赛级公开证据，未对动机、伤停、轮换或战术作方向性修正。",
            "judgement": "先用市场与比分矩阵给出基线，等待官方首发、球队公告或可交叉验证的赛前资料后再更新。",
            "sources": [],
        })
    if context.get("sources") and context.get("verifiedFactors"):
        # Structured rest data is a causal input, not a prose decoration.
        home_rest = num(context.get("homeRestDays"))
        away_rest = num(context.get("awayRestDays"))
        if home_rest is not None and away_rest is not None and abs(home_rest - away_rest) >= 2:
            advantage = "home" if home_rest > away_rest else "away"
            tired = "away" if advantage == "home" else "home"
            multipliers = dict(context.get("outcomeMultipliers", {}))
            multipliers[advantage] = float(multipliers.get(advantage, 1.0)) * 1.04
            multipliers[tired] = float(multipliers.get(tired, 1.0)) * 0.96
            context["outcomeMultipliers"] = multipliers
            context.setdefault("goalShift", 0.0)
            context["goalShift"] = float(context["goalShift"]) - 0.04
            context.setdefault("restFatigue", f"休息天数：主队{home_rest:g}天、客队{away_rest:g}天；体能优势偏向{advantage}，疲劳风险偏向{tired}。")
    return context


def build_dimension_report(match: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Build the causal evidence layer behind the final prediction.

    The context file may provide structured values such as rest days,
    travel, absences, tactical matchup and weather.  Free text is retained
    for audit, but a missing value is never inferred from odds alone.
    """
    defaults = {
        "schedule_load": "未核验上场比赛时间、赛程密度与下一场任务。",
        "rest_fatigue": "未核验双方实际休息天数、加时赛和高强度出场时间。",
        "travel_home_advantage": "未核验旅行距离、时区、主客场连续性与场地适应。",
        "squad_availability": "未核验官方伤停、停赛、首发和轮换信息。",
        "recent_performance": "未核验近期机会质量、失球方式、零封和进攻转化，不能只用胜负串替代。",
        "coach_tactics": "未核验教练近期阵型、压迫/退防和针对性部署。",
        "motivation_competition": "未核验积分、保级、晋级、两回合策略或必须抢分条件。",
        "weather_pitch": "未核验当地天气、草皮和比赛时段对节奏的影响。",
        "set_piece_transition": "未核验定位球、反击、边路防守和转换攻防的具体相克关系。",
        "market_contradiction": "未核验市场方向与球队真实表现是否冲突；不把低赔当作因果。",
    }
    aliases = {
        "schedule_load": ("schedule", "stage"),
        "rest_fatigue": ("restFatigue", "restDays", "fatigue"),
        "travel_home_advantage": ("travel", "homeAdvantage", "venue"),
        "squad_availability": ("teamNews", "injuries", "suspensions", "lineups"),
        "recent_performance": ("recentForm", "recentPerformance", "form"),
        "coach_tactics": ("coach", "tactics", "tacticalMatchup"),
        "motivation_competition": ("motivation", "competitionLogic"),
        "weather_pitch": ("weather", "pitch"),
        "set_piece_transition": ("setPieceTransition", "transition", "matchup"),
        "market_contradiction": ("upsetPath", "marketContradiction"),
    }
    dimensions = {}
    missing = []
    for key in ANALYSIS_DIMENSIONS:
        value = next((context.get(alias) for alias in aliases[key] if context.get(alias)), None)
        dimensions[key] = value or defaults[key]
        if not value:
            missing.append(key)
    return {
        "dimensions": dimensions,
        "missingDimensions": missing,
        "completeness": round((len(ANALYSIS_DIMENSIONS) - len(missing)) / len(ANALYSIS_DIMENSIONS), 2),
        "adjustmentGate": "passed" if context.get("sources") and context.get("verifiedFactors") else "blocked",
    }


def build_reasoning_contract(match: dict[str, Any], direction: str, context: dict[str, Any], main: str, backups: list[str]) -> dict[str, Any]:
    """Force every prediction through the five football-logic questions.

    Odds are only the market baseline.  Directional changes require a source
    backed context; otherwise each question stays explicitly unknown instead
    of being filled with invented injuries, motivation or tactical claims.
    """
    labels = {"home": "主队", "draw": "平局", "away": "客队"}
    side = labels[direction]
    dimension_report = build_dimension_report(match, context)
    has_evidence = dimension_report["adjustmentGate"] == "passed"
    if not has_evidence:
        unknown = "未取得足够比赛级公开证据；不把赔率排序改写成球队原因，等待官方赛程、球队公告、近期状态或首发信息交叉核验。"
        return {
            "whyWin": unknown,
            "whyMustWin": "未核验积分、赛制或晋级压力，不能声称任何一方必须赢。",
            "whyLose": "未知；没有足够的球队、教练、阵容和比赛计划证据支持具体输球叙事。",
            "whyNotLose": "仅保留比分矩阵中的低比分、平局和一球差保护，不把它们宣称为已验证事实。",
            "whyDraw": "未知；平局只作为结构性保护路径，不是由赔率低赔直接推导。",
            "decision": f"{side}为市场与联赛基线下的暂定方向，主比分{main}，备选{'/'.join(backups)}；证据不足，置信度下调。",
            "dimensionReport": dimension_report,
            "evidenceGate": "blocked",
        }
    return {
        "whyWin": context.get("whyWin") or f"支持{side}的可核验逻辑：{context.get('coach') or context.get('teamNews') or context.get('motivation') or '已有比赛级来源，但尚未拆出明确兑现条件。'}",
        "whyMustWin": context.get("whyMustWin") or context.get("motivation") or "来源未确认必须赢的赛制或积分条件，因此只作弱动机处理。",
        "whyLose": context.get("whyLose") or context.get("upsetPath") or "若对手先取得进球、比赛节奏被拉高或已核验的阵容因素失效，主方向会进入输球路径。",
        "whyNotLose": context.get("whyNotLose") or context.get("upsetPath") or "保留主方向不败的一球差和低比分路径，但不把保护路径当成事实。",
        "whyDraw": context.get("whyDraw") or f"平局机制：{context.get('coach') or context.get('motivation') or '双方比赛目标与风险控制存在拉扯'}；对应比分池保留低比分平局。",
        "decision": context.get("judgement") or f"综合证据后暂定{side}，主比分{main}，备选{'/'.join(backups)}；同时保留反向路径。",
        "dimensionReport": dimension_report,
        "evidenceGate": "passed",
    }


def hafu_pick(match: dict[str, Any]) -> tuple[str, float | None, float]:
    final = {"home": "h", "draw": "d", "away": "a"}[match["direction"]]
    first = "d" if match["totalGoals"] in {"0", "1", "2"} or final == "d" else final
    key = first + final
    odds = num(match["odds"].get("hafu", {}).get(key))
    if not odds:
        available = [(k, num(v)) for k, v in match["odds"].get("hafu", {}).items() if k in HAFU_TEXT and num(v)]
        key, odds = min(available, key=lambda row: row[1]) if available else ("dd", None)
    return key, odds, min(0.30, 1 / odds) if odds else 0


def leg(match: dict[str, Any], market: str) -> dict[str, Any]:
    if market == "had":
        key = {"home": "home", "draw": "draw", "away": "away"}[match["direction"]]
        pick, odds, probability = match["directionText"], num(match["odds"]["had"].get(key)), match["probabilities"][key]
    elif market == "ttg":
        pick = match["totalGoals"]
        odds = num(match["odds"]["ttg"].get("s7" if pick == "7+" else f"s{pick}"))
        probability = min(0.42, 1 / odds) if odds else 0
    elif market == "crs":
        pick, odds = match["mainScore"], num(match["odds"]["crs"].get(match["mainScore"]))
        probability = min(0.24, 1 / odds) if odds else 0
    else:
        key, odds, probability = hafu_pick(match)
        pick = HAFU_TEXT[key]
    return {"matchId": match["id"], "match": f"{match['matchNumStr']} {match['home']} vs {match['away']}", "market": market, "marketText": MARKET_TEXT[market], "pick": pick, "odds": odds, "probability": probability}


def combo(name: str, legs: tuple[dict[str, Any], ...] | list[dict[str, Any]], category: str) -> dict[str, Any]:
    product = math.prod(row["odds"] for row in legs)
    joint = math.prod(row["probability"] for row in legs)
    trust = round(100 * joint ** (1 / len(legs)) * (0.94 ** (len(legs) - 1)))
    return {"name": name, "category": category, "legs": list(legs), "productOdds": round(product, 2), "trustScore": max(1, min(88, trust))}


def build_combos(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    all_legs = {market: [leg(m, market) for m in matches] for market in MARKET_TEXT}
    # Pure HAD parlays are intentionally disabled: every displayed combo may contain at most one HAD leg.
    for market in ("ttg", "crs", "hafu"):
        candidates = all_legs[market]
        usable = [x for x in candidates if x["odds"] and x["probability"]]
        pool = []
        for size in range(2, min(4 if market == "had" else 3, len(usable)) + 1):
            for selected in combinations(usable, size):
                item = combo(f"{MARKET_TEXT[market]}{size}串一", selected, market)
                if item["productOdds"] >= MIN_COMBO_ODDS:
                    pool.append(item)
        keep = 5 if market in {"ttg", "crs"} else 3
        rows.extend(sorted(pool, key=lambda x: (-x["trustScore"], x["productOdds"]))[:keep])

    mixed = []
    candidates = [x for legs in all_legs.values() for x in legs if x["odds"] and x["probability"]]
    for size in (2, 3, 4):
        for selected in combinations(candidates, size):
            if len({x["matchId"] for x in selected}) != size or len({x["market"] for x in selected}) < 2:
                continue
            if sum(x["market"] == "had" for x in selected) > 1:
                continue
            item = combo(f"混合{size}串一", selected, "mixed")
            if item["productOdds"] >= MIN_COMBO_ODDS:
                mixed.append(item)
    rows.extend(sorted(mixed, key=lambda x: (-x["trustScore"], x["productOdds"]))[:8])
    rows.sort(key=lambda x: (-x["trustScore"], len(x["legs"]), x["productOdds"]))
    high_odds = sorted(
        (row for row in rows if row["productOdds"] > HIGH_ODDS_THRESHOLD),
        key=lambda x: (-x["trustScore"], len(x["legs"]), x["productOdds"]),
    )[:HIGH_ODDS_SLOTS]
    selected = list(high_odds)
    selected_keys = {tuple((leg["matchId"], leg["market"], leg["pick"]) for leg in row["legs"]) for row in selected}
    for row in rows:
        key = tuple((leg["matchId"], leg["market"], leg["pick"]) for leg in row["legs"])
        if key in selected_keys:
            continue
        selected.append(row)
        selected_keys.add(key)
        if len(selected) >= MAX_PARLAYS:
            break
    rows = sorted(selected, key=lambda x: (-x["trustScore"], len(x["legs"]), x["productOdds"]))
    for rank, row in enumerate(rows, 1):
        row["rank"] = rank
    return rows


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def predict_with_market_fallback(base: Any, match: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Use the score matrix only for model probabilities when HAD is not offered."""
    cloned = json.loads(json.dumps(match, ensure_ascii=False))
    had = cloned.get("odds", {}).get("had") or {}
    has_had = all(num(had.get(key)) for key in ("home", "draw", "away"))
    if not has_had:
        totals = {"home": 0.0, "draw": 0.0, "away": 0.0}
        for score, price in cloned["odds"].get("crs", {}).items():
            if "-" not in score or not num(price):
                continue
            home, away = (int(x) for x in score.split("-"))
            key = "home" if home > away else "away" if home < away else "draw"
            totals[key] += 1 / float(price)
        total = sum(totals.values())
        if not total:
            raise ValueError(f"No HAD or score-matrix direction basis for {match.get('matchNumStr')}")
        cloned["odds"]["had"] = {key: round(1 / (value / total), 3) for key, value in totals.items() if value}
    predicted = predict_by_competition(base, cloned, context)
    predicted["businessDate"] = match.get("businessDate", "")
    hkey, hodds, _ = hafu_pick(predicted)
    requested_hafu = context.get("halfFullKey")
    requested_odds = num(predicted["odds"].get("hafu", {}).get(requested_hafu)) if requested_hafu else None
    if requested_hafu in HAFU_TEXT and requested_odds:
        hkey, hodds = requested_hafu, requested_odds
    predicted["halfFullKey"] = hkey
    predicted["halfFullText"] = HAFU_TEXT[hkey]
    predicted["halfFullOdds"] = hodds
    had = predicted["odds"].get("had", {})
    scores = " / ".join([predicted["mainScore"], *predicted["backupScores"]])
    ranks = "、".join(value for value in (predicted.get("homeRank"), predicted.get("awayRank")) if value) or "排名信息未作为强制修正"
    half_full_text = f"{predicted['halfFullText']}（{hodds:.2f}）" if hodds else predicted["halfFullText"]
    default_analysis = (
        f"结论：{predicted['directionText']}，总进球重点{predicted['totalGoals']}球，比分关注{scores}，"
        f"半全场为{half_full_text}；当前仅有{ranks}与市场/比分矩阵支持，尚未取得足够的球队、赛程、阵容或战术证据，"
        "故只作低置信基线，主要反向路径为平局及一球差。"
    )
    # Web copy is intentionally one result paragraph. The full five-question
    # contract and ten causal dimensions remain in JSON for audit/backtesting.
    predicted["integratedAnalysis"] = " ".join(str(context.get("integratedAnalysis", default_analysis)).split())
    predicted["analysisBasis"] = context.get("analysisBasis", "体彩官方赔率、比分矩阵与总进球分布的综合模拟；没有把未核实的阵容传闻当作事实。")
    if not has_had:
        predicted["odds"]["had"] = {}
        predicted["marketBasis"] = "未开售胜平负；方向概率由官方比分矩阵归一化推导，不参与胜平负串关。"
        predicted["reason"] += " " + predicted["marketBasis"]
    else:
        predicted["marketBasis"] = "官方胜平负赔率"
    return predicted


def render(payload: dict[str, Any], styles: dict[str, dict[str, str]]) -> str:
    label = datetime.strptime(payload["date"], "%Y%m%d").strftime("%m-%d")
    extra_note = '<span style="--c:#b33e5c">含07-19两场韩职</span>' if payload["date"] == "20260718" else ""
    legends = f'<span style="--c:#17212b">按 Sporttery 竞彩业务日分组</span><span style="--c:#7a43b6">赔率仅作市场基线</span><span style="--c:#c38b16">串关理论赔率 ≥ {MIN_COMBO_ODDS:.0f}</span><span style="--c:#287d70">每串最多1个胜平负</span>{extra_note}' + "".join(f'<span style="--c:{styles[name]["color"]}">{esc(styles[name]["label"])}</span>' for name in dict.fromkeys(m["league"] for m in payload["matches"]))
    warnings = "".join(f"<li>{esc(x)}</li>" for x in payload["scheduleWarnings"])
    review = payload.get("competitionReview")
    review_html = ""
    if review:
        reviews = review.get("reviews", [review])
        blocks = []
        for item in reviews:
            result_rows = "".join(
                f'<tr><td>{esc(row["matchNumStr"])}</td><td>{esc(row["home"])} {esc(row["score"])} {esc(row["away"])}</td><td>{esc(row["assessment"])}</td></tr>'
                for row in item["results"]
            )
            blocks.append(f'''<h3>{esc(item["league"])}赛果</h3><table>{result_rows}</table><p><b>模型复盘：</b>{esc(item["summary"])}</p><p><b>独立调整：</b>{esc(item["modelAdjustment"])}</p>''')
        result_sources = "".join(f'<li><a href="{esc(row["url"])}">{esc(row["name"])}</a></li>' for row in review.get("sources", []))
        review_html = f'''<section class="notice"><h2>{esc(review.get("reviewDate", "07-18"))} 分赛事赛果复盘</h2>{"".join(blocks)}{f'<h3>赛果核对来源</h3><ul>{result_sources}</ul>' if result_sources else ''}</section>'''
    combos = []
    for c in payload["combos"]:
        legs = "".join(f'<tr><td>{esc(x["match"])}</td><td>{esc(x["marketText"])}</td><td>{esc(x["pick"])}</td><td>{x["odds"]:.2f}</td></tr>' for x in c["legs"])
        combos.append(f'<section class="combo {c["category"]}"><h3>#{c["rank"]} {esc(c["name"])} <b>{c["trustScore"]}/100</b></h3><table>{legs}</table><p>理论组合赔率：<strong>{c["productOdds"]:.2f}</strong></p></section>')
    cards = []
    for m in payload["matches"]:
        p, had = m["probabilities"], m["odds"]["had"]
        score_ranking = " / ".join(
            [f'① {m["mainScore"]}（主比分）', *[f'{rank} {score}' for rank, score in zip(("②", "③"), m["backupScores"])]]
        )
        hkey = m.get("halfFullKey") or hafu_pick(m)[0]
        half_full_odds = m.get("halfFullOdds")
        cards.append(f'''<section class="match" style="--league:{m['leagueStyle']['color']}"><div class="title"><h3>{esc(m['matchNumStr'])} {esc(m['home'])} vs {esc(m['away'])}</h3><span>{esc(m['leagueStyle']['label'])}</span></div><p><b>北京时间：</b>{esc(m['kickoff'])}　<b>胜平负赔率：</b>{had.get('home','-')} / {had.get('draw','-')} / {had.get('away','-')}</p><p><b>独立模型：</b>{esc(m['modelProfile']['version'])} + 综合情境模拟层</p><div class="grid"><div><small>胜平负</small><strong>{esc(m['directionText'])}</strong></div><div><small>总进球</small><strong>{esc(m['totalGoals'])}</strong></div><div><small>主比分</small><strong>{esc(m['mainScore'])}</strong></div><div><small>半全场</small><strong>{esc(HAFU_TEXT[hkey])}</strong>{f'<small>赔率 {half_full_odds:.2f}</small>' if half_full_odds else ''}</div></div><p><b>三个比分（置信度从高到低）：</b>{esc(score_ranking)}</p><div class="factors"><p><b>综合性分析：</b>{esc(m['integratedAnalysis'])}</p></div><p><b>分析口径：</b>{esc(m['analysisBasis'])}</p><p><b>盘口波动审计（{esc(m['marketRiskLevel'])}）：</b>{esc('；'.join(m['marketRiskFactors']))}。{esc(m['marketRiskNote'])}</p><p>尾部审计：{esc(' / '.join(m['tailRiskScores']) or '无额外尾部入选')}；总进球候选：{esc(' / '.join(m['goalCandidates']))}</p><p>情境修正后概率：主 {p['home']:.1%} / 平 {p['draw']:.1%} / 客 {p['away']:.1%}；模型信任度 {m['confidenceScore']}/100。</p></section>''')
    source_items = "".join(f'<li><a href="{esc(x["url"])}">{esc(x["name"])}</a></li>' for x in payload["sources"])
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#116b62"><title>2026-{label}足球预测</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#eef4f6;color:#17212b;font-family:"Microsoft YaHei",Arial,sans-serif;line-height:1.65}}header,main{{max-width:1180px;margin:auto;padding:24px 16px}}nav a{{margin-right:10px}}h1{{font-size:clamp(30px,5vw,48px)}}.legend span{{display:inline-block;margin:5px;padding:6px 11px;border-left:7px solid var(--c);background:white;border-radius:7px}}.notice,.match,.combo{{background:white;border:1px solid #dce4ea;border-radius:14px;padding:18px;margin:15px 0;box-shadow:0 8px 26px #2336460f}}.notice{{overflow-x:auto}}.match{{border-left:10px solid var(--league);overflow-wrap:anywhere}}.title,.combo h3{{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap}}.title span{{background:var(--league);color:white;padding:4px 11px;border-radius:99px}}.grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:9px}}.grid div{{background:#f5f8fa;padding:10px;border-radius:8px}}.factors{{background:#f5f8fa;border-radius:10px;padding:10px 14px;margin:12px 0}}.factors p{{margin:5px 0}}.sources{{font-size:13px;color:#657482}}small{{display:block;color:#657482}}strong{{font-size:21px}}.combo{{border-top:6px solid #287d70}}.combo.hafu{{border-top-color:#7a43b6}}.combo.crs{{border-top-color:#b35430}}.combo.ttg{{border-top-color:#355dc5}}.combo.mixed{{border-top-color:#c38b16}}table{{width:100%;border-collapse:collapse}}td{{padding:8px;border-bottom:1px solid #e7ecef}}@media(max-width:700px){{.grid{{grid-template-columns:1fr 1fr}}.combo{{overflow:auto}}}}</style><link rel="stylesheet" href="../assets/site.css"></head><body><header><nav><a href="../index.html">日期首页</a><a href="../history/index.html">历史归档</a></nav><h1>{label}足球预测</h1><p>共 {len(payload['matches'])} 场 · 北京时间 · 赔率更新至 {esc(payload['oddsUpdatedAt'])}</p><div class="legend">{legends}</div></header><main>{review_html}{f'<section class="notice"><h2>赛程冲突提示</h2><ul>{warnings}</ul></section>' if warnings else ''}<section class="notice"><h2>模型方法</h2><p>每场只展示一段综合性分析，并明确给出胜平负、总进球、比分和半全场。赔率与比分矩阵是市场基线；赛程、积分动机、状态、伤停和战术只有在公开来源可核验时才进入情境层，证据不足则保持中性并降低信任度。杯赛额外检查平局保护、受控小比分与追分大比分，未经核验的信息不作为事实下结论。</p></section><section class="notice"><h2>精选n串一</h2><p>仅保留 {len(payload['combos'])} 组，全部理论组合赔率不低于 {MIN_COMBO_ODDS:.0f}，且每串最多一个胜平负选项；模型信任度高的优先排列，同时保留理论赔率超过 {HIGH_ODDS_THRESHOLD:.0f} 的高赔率组合。信任度仅用于模型横向比较，不等同于命中率。</p></section>{''.join(combos)}<h2>逐场预测</h2>{''.join(cards)}<section class="notice"><h2>赛程与赔率来源</h2><ul>{source_items}</ul><p>{DISCLAIMER}</p></section></main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--target-league", help="只重算指定联赛，其他联赛沿用现有预测结果")
    args = parser.parse_args()
    base = load_base()
    raw = json.loads((ROOT / args.source).read_text(encoding="utf-8-sig"))
    context_path = DATA / f"match_context_{args.date}.json"
    context_payload = json.loads(context_path.read_text(encoding="utf-8")) if context_path.exists() else {"matches": {}}
    contexts = context_payload.get("matches", {})
    extra_context_path = DATA / f"match_context_{args.date}_extra.json"
    if extra_context_path.exists():
        extra_context = json.loads(extra_context_path.read_text(encoding="utf-8"))
        contexts.update(extra_context.get("matches", {}))
    source_matches = list(raw["matches"])
    extra_config = EXTRA_MATCHES_BY_DATE.get(args.date)
    if extra_config:
        extra_path, extra_league = extra_config
        extra_raw = json.loads((ROOT / extra_path).read_text(encoding="utf-8-sig"))
        source_matches.extend(m for m in extra_raw["matches"] if m.get("league") == extra_league)
    excluded = EXCLUDED_BY_DATE.get(args.date, {})
    supported = set(base.LEAGUE_STYLES)
    eligible = [m for m in source_matches if m.get("league") in supported and m.get("league") not in EXCLUDED_LEAGUES and f"{m.get('home')}|{m.get('away')}" not in excluded]
    existing_path = DATA / f"predictions_{args.date}.json"
    existing_by_id: dict[str, dict[str, Any]] = {}
    if args.target_league and existing_path.exists():
        existing_payload = json.loads(existing_path.read_text(encoding="utf-8"))
        existing_by_id = {str(m.get("matchId") or m.get("id")): m for m in existing_payload.get("matches", [])}
    matches = []
    for match in eligible:
        existing = existing_by_id.get(str(match.get("matchId")))
        if args.target_league and match.get("league") != args.target_league and existing:
            matches.append(existing)
        else:
            match_context = context_for_match(match, contexts.get(str(match.get("matchId")), {}))
            matches.append(predict_with_market_fallback(base, match, match_context))
    if not matches:
        raise SystemExit("No verified matches available")
    updated = max(pool.get("updatedAt", "") for m in matches for pool in m["odds"].values() if isinstance(pool, dict))
    sources = list(base.SOURCES) + [
        {"name": "瑞超官方赛程", "url": "https://allsvenskan.se/nyheter/sa-spelas-omgang-11-17-av-allsvenskan/"},
        {"name": "挪威足协赛程", "url": "https://www.fotball.no/eliteserien/"},
        {"name": "巴西足协赛程", "url": "https://www.cbf.com.br/futebol-brasileiro/jogos/campeonato-brasileiro/serie-a/2026"},
        {"name": "MLS官方赛程", "url": "https://www.mlssoccer.com/news/mls-unveils-2026-regular-season-schedule"},
        {"name": "K League官方赛程", "url": "https://tv.kleague.com/en-int/schedule"},
    ]
    competition_review = latest_competition_review(args.date)
    payload = {"date": args.date, "dateBasis": "Sporttery竞彩业务日；07-18页面按用户此前要求并入07-19两场韩职" if args.date == "20260718" else "Sporttery竞彩业务日", "includedBusinessDates": sorted(set(m.get("businessDate", "") for m in matches)), "modelVersion": f"competition-specific-evidence-chain-{args.date}-v10", "contextVersion": context_payload.get("version", "evidence-chain-v2"), "competitionModels": {league: shrink_review_profile(COMPETITION_MODELS[league]) for league in dict.fromkeys(m["league"] for m in matches)}, "competitionReview": competition_review, "generatedAt": datetime.now().isoformat(timespec="seconds"), "oddsUpdatedAt": updated, "matches": matches, "combos": build_combos(matches), "scheduleWarnings": [reason for reason in excluded.values() if reason], "sources": sources, "disclaimer": DISCLAIMER}
    DATA.joinpath(f"predictions_{args.date}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out = ROOT / args.date
    out.mkdir(exist_ok=True)
    page = render(payload, base.LEAGUE_STYLES)
    out.joinpath("index.html").write_text(page, encoding="utf-8")
    out.joinpath(f"predict_{args.date}.html").write_text(page, encoding="utf-8")
    generate_homepage(ROOT)
    print(f"Generated {len(matches)} matches, {len(payload['combos'])} parlays, {len(excluded)} schedule warnings")


if __name__ == "__main__":
    main()
