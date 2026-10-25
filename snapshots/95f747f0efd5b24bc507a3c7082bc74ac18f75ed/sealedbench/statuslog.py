"""Append one Phase 2 status block. Used by the release pipeline."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

PATH = Path("/root/codes/sealedbench/STATUS.md")


def append_status(item: str, result: str, lines: list[str]) -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = "\n".join(f"- {line}" for line in lines)
    text = f"\n## {stamp} — {item} — {result}\n\n{body}\n"
    with PATH.open("a", encoding="utf-8") as handle:
        handle.write(text)


if __name__ == "__main__":
    item, result = sys.argv[1], sys.argv[2]
    append_status(item, result, sys.argv[3:])
