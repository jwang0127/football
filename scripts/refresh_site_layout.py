#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r'<link rel="stylesheet" href="[^"]*assets/site\.css">')
REVIEW_LINK_RE = re.compile(r'<a\s+href="[^"]*review\.html">[^<]*</a>')


def refresh(root: Path = ROOT) -> list[str]:
    changed: list[str] = []
    for path in root.rglob("*.html"):
        if ".git" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        relative_css = Path(os.path.relpath(root / "assets" / "site.css", path.parent)).as_posix()
        link = f'<link rel="stylesheet" href="{relative_css}">'
        updated = LINK_RE.sub(link, text)
        if "assets/site.css" not in updated:
            updated = updated.replace("</head>", f"{link}</head>", 1)
        updated = REVIEW_LINK_RE.sub("", updated)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path.relative_to(root).as_posix())
    return changed


if __name__ == "__main__":
    files = refresh()
    print(f"Updated layout links in {len(files)} HTML files")
