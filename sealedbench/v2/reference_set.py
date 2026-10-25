"""The GSM8K prefix that b2 and cap2 actually grade."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sealedbench.extract import extract_gold
from sealedbench.v2.spec import canon

N_REFERENCE = 80
SOURCE = Path("results/cpu/gsm8k_test.jsonl")


def build_reference(root: Path, n: int = N_REFERENCE) -> dict:
    raw = (root / SOURCE).read_bytes()
    rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if len(rows) < n:
        raise RuntimeError(f"GSM8K file has {len(rows)} rows")
    questions = []
    for index in range(n):
        row = rows[index]
        gold = extract_gold(row["answer"])
        if gold is None:
            raise RuntimeError(f"GSM8K index {index} has no gold")
        item = {
            "answer_field": row["answer"],
            "family": "gsm8k",
            "index": index,
            "item_id": f"gsm8k-{index:04d}",
            "oracle_answer": gold,
            "question": row["question"],
        }
        item["sha256"] = hashlib.sha256(canon({"answer": row["answer"], "question": row["question"]}).encode()).hexdigest()
        questions.append(item)
    body = {
        "dataset": "GSM8K-test",
        "indexes": f"0..{n - 1}",
        "n": n,
        "questions": questions,
        "source_file": str(SOURCE),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes": len(raw),
        "note": "Indexes 0..49 were used in Phase 1 to develop the prompt and the v1 extractor. This prefix is not difficulty-matched to arith_word.",
    }
    encoded = (canon(body) + "\n").encode("utf-8")
    # canon() of the whole body includes the hash of itself if we add it first.
    # Hash the canonical questions list, which is what the manifest pins, and
    # also the file bytes we upload.
    listing = canon(
        [
            {
                "answer_field": item["answer_field"],
                "index": item["index"],
                "item_id": item["item_id"],
                "oracle_answer": item["oracle_answer"],
                "question": item["question"],
                "sha256": item["sha256"],
            }
            for item in questions
        ]
    ).encode("utf-8")
    body["questions_sha256"] = hashlib.sha256(listing).hexdigest()
    file_bytes = (json.dumps(body, sort_keys=True, indent=2) + "\n").encode("utf-8")
    body_file_sha = hashlib.sha256(file_bytes).hexdigest()
    return {"record": body, "file_bytes": file_bytes, "file_sha256": body_file_sha}
