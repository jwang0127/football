#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from generate_homepage import generate_homepage

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def update_review_and_future(review_date: str, root: Path = ROOT) -> dict[str, list[str]]:
    review_day = datetime.strptime(review_date, "%Y%m%d")
    generated: list[str] = []
    skipped: list[str] = []
    for offset in (1, 2):
        compact = (review_day + timedelta(days=offset)).strftime("%Y%m%d")
        source = root / "data" / f"sporttery_{compact}_latest.json"
        if not source.exists():
            skipped.append(f"{compact}: 无官方数据文件")
            continue
        raw = json.loads(source.read_text(encoding="utf-8-sig"))
        if not raw.get("matches"):
            skipped.append(f"{compact}: 官方数据无比赛")
            continue
        subprocess.check_call([
            sys.executable,
            str(root / "scripts" / "generate_date_pages.py"),
            "--date", compact,
            "--source", str(source.relative_to(root)),
        ], cwd=root)
        generated.append(compact)
    generate_homepage(root)
    return {"generated": generated, "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description="复盘更新后生成未来两天独立预测页（有数据才生成）")
    parser.add_argument("--review-date", "--date", dest="review_date", required=True)
    args = parser.parse_args()
    result = update_review_and_future(args.review_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
