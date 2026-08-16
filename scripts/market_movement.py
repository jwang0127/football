"""Audit opening/latest Sporttery snapshots without treating movement as a bet signal."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _num(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _prob(pool: dict[str, Any], keys: tuple[str, ...]) -> dict[str, float]:
    raw = {key: 1 / _num(pool.get(key)) for key in keys if _num(pool.get(key)) and _num(pool.get(key)) > 1}
    total = sum(raw.values())
    return {key: value / total for key, value in raw.items()} if total else {}


def _movement(opening: dict[str, Any], latest: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"opening": opening, "latest": latest, "delta": {}, "probabilityDelta": {}, "openingDefinition": "同日最早已观测快照，不等同于真实开盘；需从开售前持续采样才能确认初盘", "openingIsActual": False}
    for pool in ("had", "hhad", "ttg"):
        old, new = opening.get(pool) or {}, latest.get(pool) or {}
        delta = {}
        for key in set(old) | set(new):
            before, after = _num(old.get(key)), _num(new.get(key))
            if before is not None and after is not None and key not in ("updatedAt", "handicap"):
                delta[key] = round(after - before, 3)
        result["delta"][pool] = delta
    for keys, name in [
        (('home', 'draw', 'away'), 'had'),
        (('home', 'draw', 'away'), 'hhad'),
        (('s0', 's1', 's2', 's3', 's4', 's5', 's6', 's7'), 'ttg'),
    ]:
        before, after = _prob(opening.get(name) or {}, keys), _prob(latest.get(name) or {}, keys)
        result["probabilityDelta"][name] = {key: round(after.get(key, 0) - before.get(key, 0), 4) for key in set(before) | set(after)}
    had = result["probabilityDelta"].get("had", {})
    strongest = max(had, key=had.get) if had else None
    result["directionalSignal"] = strongest
    hhad = result["probabilityDelta"].get("hhad", {})
    handicap_signal = max(hhad, key=hhad.get) if hhad else None
    result["handicapSignal"] = handicap_signal
    result["interpretation"] = "胜平负与让球方向同步" if strongest and handicap_signal and had.get(strongest, 0) > .015 and hhad.get(handicap_signal, 0) > .015 and strongest == handicap_signal else (
        "让球盘出现独立变化，需结合基本面和比分矩阵复核" if handicap_signal and hhad.get(handicap_signal, 0) > .015 else
        "临场方向与初盘一致" if strongest and had[strongest] > .015 else "变盘不足以形成方向信号"
    )
    return result


def load_market_movement(root: Path, date: str) -> dict[str, dict[str, Any]]:
    folder = root / "data" / "odds_snapshots" / date
    paths = sorted(folder.glob("*.json")) if folder.exists() else []
    if len(paths) < 2:
        return {}
    snapshots = [json.loads(path.read_text(encoding="utf-8-sig")) for path in paths]
    by_id: dict[str, list[dict[str, Any]]] = {}
    for snapshot in snapshots:
        for match in snapshot.get("matches", []):
            key = str(match.get("matchId") or match.get("id"))
            by_id.setdefault(key, []).append(match)
    output = {}
    for key, rows in by_id.items():
        if len(rows) >= 2:
            output[key] = _movement(rows[0].get("odds", {}), rows[-1].get("odds", {}))
            output[key]["snapshotCount"] = len(rows)
            output[key]["openingCapturedAt"] = snapshots[0].get("capturedAt", snapshots[0].get("fetchedAt"))
            output[key]["latestCapturedAt"] = snapshots[-1].get("capturedAt", snapshots[-1].get("fetchedAt"))
    return output
