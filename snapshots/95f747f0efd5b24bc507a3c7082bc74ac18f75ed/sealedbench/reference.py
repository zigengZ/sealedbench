"""Freeze GSM8K-test indexes 0..119 from the Phase 1 source file."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sealedbench.items import canon
from sealedbench.protocol import GSM8K_PATH, GSM8K_URL, REFERENCE_INDEXES

ROOT = Path("/root/codes/sealedbench")


def load_rows() -> list[dict]:
    path = ROOT / GSM8K_PATH
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if len(rows) < 120:
        raise RuntimeError(f"GSM8K file has {len(rows)} rows")
    return rows


def row_sha256(row: dict) -> str:
    payload = canon({"answer": row["answer"], "question": row["question"]}).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def freeze_reference() -> dict:
    path = ROOT / GSM8K_PATH
    raw = path.read_bytes()
    rows = load_rows()
    items = []
    for index in REFERENCE_INDEXES:
        items.append({"index": index, "sha256": row_sha256(rows[index])})
    listing = canon(items).encode("utf-8")
    return {
        "dataset": "GSM8K-test",
        "source_file": GSM8K_PATH,
        "source_url": GSM8K_URL,
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw),
        "indexes": "0..119",
        "n": 120,
        "compare_family": "arith_word",
        "fresh_only_families": ["code_output", "graph_path"],
        "row_sha256_method": (
            "SHA-256 of canonical JSON {answer, question} with sorted keys, "
            "no extra whitespace, ensure_ascii true."
        ),
        "list_sha256": hashlib.sha256(listing).hexdigest(),
        "items": items,
    }


def reference_questions() -> list[dict]:
    """Return the 120 frozen rows with ids gsm8k-0000 and the gold integer."""
    from sealedbench.extract import extract_gold

    rows = load_rows()
    frozen = freeze_reference()
    out = []
    for spec in frozen["items"]:
        row = rows[spec["index"]]
        gold = extract_gold(row["answer"])
        if gold is None:
            raise RuntimeError(f"GSM8K index {spec['index']} has no #### gold")
        out.append(
            {
                "item_id": f"gsm8k-{spec['index']:04d}",
                "index": spec["index"],
                "question": row["question"],
                "answer_field": row["answer"],
                "oracle_answer": gold,
                "sha256": spec["sha256"],
                "family": "gsm8k",
            }
        )
    return out
