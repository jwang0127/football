#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--exclude", action="append", default=["世界杯"])
    args = parser.parse_args()
    excluded = set(args.exclude)
    for raw_path in args.paths:
        path = Path(raw_path)
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        before = len(payload.get("matches", []))
        payload["matches"] = [match for match in payload.get("matches", []) if match.get("league") not in excluded]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{path}: removed {before - len(payload['matches'])}, kept {len(payload['matches'])}")


if __name__ == "__main__":
    main()
