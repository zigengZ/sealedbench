"""Entropy of a generator family across many seeds.

Seeds are SHA-256(ASCII("sealedbench/v1/entropy\\n" || family || "\\n" || index)).
That makes the report reproducible. The gate for 1000 seeds is at least 999
distinct question-set hashes.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from sealedbench.families import GENERATORS
from sealedbench.items import question_set_sha256

ROOT = Path("/root/codes/sealedbench")
TOKEN_RE = re.compile(r"[a-z0-9]+")


def entropy_seed(family: str, index: int) -> bytes:
    text = f"sealedbench/v1/entropy\n{family}\n{index}"
    return hashlib.sha256(text.encode("ascii")).digest()


def _tokens(prompt: str) -> set[str]:
    return set(TOKEN_RE.findall(prompt.lower()))


def _jaccard(prompts: list[str]) -> float:
    sets = [_tokens(prompt) for prompt in prompts]
    if len(sets) < 2:
        return 0.0
    total = 0.0
    pairs = 0
    for i in range(len(sets)):
        for j in range(i + 1, len(sets)):
            union = len(sets[i] | sets[j])
            total += (len(sets[i] & sets[j]) / union) if union else 0.0
            pairs += 1
    return total / pairs


def _one(payload: tuple) -> dict:
    family, index, n = payload
    items = GENERATORS[family](entropy_seed(family, index), n)
    return {
        "q": question_set_sha256(items),
        "prompts": [item.prompt for item in items],
        "answers": [item.oracle_answer for item in items],
        "jaccard": _jaccard([item.prompt for item in items]),
    }


def run_entropy(family: str, seeds: int, n: int, workers: int = 4) -> dict:
    if family not in GENERATORS:
        raise SystemExit(f"unknown family {family}")
    started = time.time()
    payloads = [(family, index, n) for index in range(seeds)]
    rows = [None] * seeds
    use_workers = workers if family == "code_output" else 1
    if use_workers == 1:
        for payload in payloads:
            rows[payload[1]] = _one(payload)
            if payload[1] % 50 == 0:
                print(f"entropy {family} {payload[1]}/{seeds}", flush=True)
    else:
        with ProcessPoolExecutor(max_workers=use_workers) as pool:
            futures = {pool.submit(_one, payload): payload[1] for payload in payloads}
            done = 0
            for future in as_completed(futures):
                index = futures[future]
                rows[index] = future.result()
                done += 1
                if done % 50 == 0 or done == seeds:
                    print(f"entropy {family} {done}/{seeds}", flush=True)
    set_hashes = [row["q"] for row in rows]
    prompts = [prompt for row in rows for prompt in row["prompts"]]
    answers = [answer for row in rows for answer in row["answers"]]
    counts = Counter(answers)
    distinct_sets = len(set(set_hashes))
    gate_need = seeds if seeds < 1000 else 999
    # The published gate is 999/1000. Smaller runs use the same ratio.
    if seeds >= 1000:
        passed = distinct_sets >= 999
    else:
        passed = distinct_sets >= max(1, seeds - 1) if seeds > 1 else True
    numeric = []
    for answer in answers:
        if re.fullmatch(r"-?\d+", answer):
            numeric.append(int(answer))
    top = [{"answer": value, "count": count} for value, count in counts.most_common(15)]
    report = {
        "family": family,
        "seeds": seeds,
        "n": n,
        "seed_rule": 'SHA-256(ASCII("sealedbench/v1/entropy\\n" || family || "\\n" || index))',
        "distinct_question_sets": distinct_sets,
        "distinct_prompts": len(set(prompts)),
        "prompt_count": len(prompts),
        "mean_pairwise_jaccard": sum(row["jaccard"] for row in rows) / len(rows),
        "jaccard_definition": (
            "Tokens are [a-z0-9]+ on the lowercased prompt. For each seed, the mean "
            "Jaccard over unordered prompt pairs is computed, then those means are averaged."
        ),
        "unique_answers": len(counts),
        "answer_top": top,
        "answer_min": min(numeric) if numeric else None,
        "answer_max": max(numeric) if numeric else None,
        "gate_distinct_sets_at_least": 999 if seeds >= 1000 else gate_need,
        "gate_pass": passed,
        "seconds": round(time.time() - started, 3),
    }
    return report


def write_report(report: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{report['family']}.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    summary = out_dir / "summary.md"
    rows = []
    if summary.exists():
        existing = summary.read_text()
    else:
        existing = ""
    # Rewrite the whole table from every family json so the file stays consistent.
    lines = [
        "# Generator entropy",
        "",
        "Seeds are `SHA-256(\"sealedbench/v1/entropy\\n\" || family || \"\\n\" || index)`.",
        "Jaccard is the mean, over seeds, of the mean pairwise Jaccard of prompt token sets.",
        "Gate: at least 999 distinct question-set hashes out of 1000 seeds.",
        "",
        "| family | seeds | n | distinct sets | distinct prompts | mean Jaccard | unique answers | seconds | gate |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    reports = []
    for file in sorted(out_dir.glob("*.json")):
        reports.append(json.loads(file.read_text()))
    for item in reports:
        flag = "PASS" if item["gate_pass"] else "FAIL"
        lines.append(
            f"| {item['family']} | {item['seeds']} | {item['n']} | "
            f"{item['distinct_question_sets']} | {item['distinct_prompts']} | "
            f"{item['mean_pairwise_jaccard']:.4f} | {item['unique_answers']} | "
            f"{item['seconds']} | {flag} |"
        )
    lines.append("")
    summary.write_text("\n".join(lines))
    del existing
