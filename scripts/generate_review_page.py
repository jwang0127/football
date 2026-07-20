#!/usr/bin/env python3
"""Compatibility entrypoint for the consolidated review workflow.

Reviews are embedded at the beginning of the following prediction page.  This
command therefore generates up to two future daily pages when official source
files exist, instead of creating another standalone review.html page.
"""
from __future__ import annotations

import argparse
import json

from update_review_and_future import update_review_and_future


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="已完成复盘的竞彩业务日 YYYYMMDD")
    args = parser.parse_args()
    result = update_review_and_future(args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
