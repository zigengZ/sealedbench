"""Template-diversity gate for a v2 generator.

The gate runs the same generate_batch the sealed tarball runs. Callers that
check sealed bytes extract the tarball, put the throwaway test secret in
place, and invoke this module from that tree.
"""

from __future__ import annotations

import hashlib
from collections import Counter

from sealedbench.items import question_set_sha256
from sealedbench.v2.generate import generate_batch
from sealedbench.v2.spec import CHAIN_HASH, TEST_SECRET, derive_seed

COUNTS = {"arith_word": 80, "code_output": 30, "graph_path": 30}


def seed_for_index(index: int, secret: bytes = TEST_SECRET) -> bytes:
    signature = hashlib.sha256(b"sealedbench/v2/diversity" + index.to_bytes(8, "big")).digest()
    return derive_seed(CHAIN_HASH, 1000 + index, signature, secret)


def _family_report(items: list) -> dict:
    counts = Counter(item.params["template_id"] for item in items)
    n = len(items)
    top = max(counts.values()) if counts else 0
    return {
        "n": n,
        "distinct_templates": len(counts),
        "max_share": 0 if n == 0 else top / n,
        "max_template": None if not counts else counts.most_common(1)[0][0],
    }


def draw_ok(items: list) -> tuple[bool, dict]:
    by_family = {name: [] for name in ("arith_word", "code_output", "graph_path")}
    for item in items:
        by_family[item.family].append(item)
    detail = {name: _family_report(rows) for name, rows in by_family.items()}
    arith = detail["arith_word"]
    code = detail["code_output"]
    graph = detail["graph_path"]
    ok = (
        arith["distinct_templates"] >= 12
        and arith["max_share"] <= 0.30
        and code["distinct_templates"] >= 6
        and code["max_share"] <= 0.40
        and graph["distinct_templates"] >= 3
    )
    return ok, detail


def gate_sealed_bytes(tarball: bytes, seeds: int = 1000) -> dict:
    """Run the gate from the tarball bytes, with the test secret, not the sealed one."""
    import gzip
    import io
    import json
    import os
    import subprocess
    import sys
    import tarfile
    import tempfile
    from pathlib import Path

    raw = gzip.decompress(tarball)
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
            tar.extractall(dest)
        secret_file = dest / "sealedbench" / "v2" / "batch_secret.bin"
        secret_file.write_bytes(TEST_SECRET)
        script = (
            "import json, sys\n"
            "from sealedbench.v2.diversity import run_gate\n"
            "from sealedbench.v2.spec import TEST_SECRET\n"
            "json.dump(run_gate(int(sys.argv[1]), TEST_SECRET), sys.stdout)\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(dest)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, "-c", script, str(seeds)],
            cwd=str(dest),
            env=env,
            capture_output=True,
            check=False,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr[-2000:])
        report = json.loads(proc.stdout)
        report["sealed_bytes"] = True
        report["test_secret_only"] = True
        return report


def run_gate(seeds: int = 1000, secret: bytes = TEST_SECRET, counts: dict | None = None) -> dict:
    counts = counts or COUNTS
    set_hashes = []
    prompt_hashes = set()
    failures = []
    worst = {"arith_word": 0.0, "code_output": 0.0, "graph_path": 0}
    min_distinct = {"arith_word": 10**9, "code_output": 10**9, "graph_path": 10**9}
    for index in range(seeds):
        items = generate_batch(seed_for_index(index, secret), counts)
        digest = question_set_sha256(items)
        set_hashes.append(digest)
        for item in items:
            prompt_hashes.add(hashlib.sha256(item.prompt.encode("utf-8")).hexdigest())
        ok, detail = draw_ok(items)
        for name, row in detail.items():
            worst[name] = max(worst[name], row["max_share"] if name != "graph_path" else row["distinct_templates"])
            if name == "graph_path":
                min_distinct[name] = min(min_distinct[name], row["distinct_templates"])
            else:
                min_distinct[name] = min(min_distinct[name], row["distinct_templates"])
                worst[name] = max(worst[name], row["max_share"])
        if not ok:
            failures.append({"index": index, "detail": detail})
            if len(failures) > 20:
                break
    distinct_sets = len(set(set_hashes))
    gate = distinct_sets >= seeds - 1 and not failures and seeds >= 1
    # The published gate requires >= 999/1000. Smaller pilots only check draws.
    if seeds >= 1000:
        gate = distinct_sets >= 999 and not failures
    return {
        "seeds": seeds,
        "secret": "test" if secret == TEST_SECRET else "other",
        "counts": counts,
        "distinct_question_sets": distinct_sets,
        "distinct_prompts": len(prompt_hashes),
        "min_distinct_templates": min_distinct,
        "worst_max_share_arith": worst["arith_word"],
        "worst_max_share_code": worst["code_output"],
        "min_graph_node_bins": min_distinct["graph_path"],
        "draw_failures": len(failures),
        "failure_examples": failures[:5],
        "gate_pass": gate,
    }
