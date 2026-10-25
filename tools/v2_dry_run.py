#!/usr/bin/env python3
"""Past-round dry run: decrypt, generate, two Falcon items, grade.

Uses the published test secret and quicknet round 1000. Nothing is uploaded.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sealedbench.infer import completion_cmd, run_item  # noqa: E402
from sealedbench.v2.grade import grade_answer, is_truncated  # noqa: E402
from sealedbench.v2.spec import CHAIN_HASH, TEST_SECRET  # noqa: E402
from sealedbench.v2.tarball import build_v2_tarball  # noqa: E402

TLE = os.environ.get("TLE", "/root/.cache/sealedbench/gopath/bin/tle")
OUT = Path("/root/sbw/p2r/dryrun")


def main() -> None:
    import time
    from sealedbench.v2.spec import GENESIS, PERIOD_S

    OUT.mkdir(parents=True, exist_ok=True)
    plain = build_v2_tarball(ROOT, TEST_SECRET)
    # tle refuses a round that is already past. Seal to a round ~60 s ahead,
    # then decrypt once it is public. b2/cap2 early-decrypt refusal is separate.
    target = ((int(time.time()) - GENESIS) // PERIOD_S) + 1 + 20
    unlock = GENESIS + (target - 1) * PERIOD_S
    enc = subprocess.run(
        [TLE, "-e", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH, "-r", str(target), "-a"],
        input=plain,
        capture_output=True,
        check=False,
    )
    if enc.returncode != 0:
        raise SystemExit(enc.stderr.decode()[-300:])
    wait = unlock + 8 - time.time()
    if wait > 0:
        print(f"DRY wait {wait:.0f}s for round {target}", flush=True)
        time.sleep(wait)
    dec = subprocess.run(
        [TLE, "-d", "-n", "https://api.drand.sh/", "-c", CHAIN_HASH],
        input=enc.stdout,
        capture_output=True,
        check=False,
    )
    if dec.returncode != 0 or dec.stdout != plain:
        raise SystemExit(f"decrypt failed {dec.returncode} {dec.stderr.decode()[-200:]}")
    manifest = json.loads((ROOT / "results" / "batches" / "b2" / "manifest.json").read_text())
    # Two items from the published round-1000 vector's generator, test secret.
    from sealedbench.v2.generate import generate_batch
    from sealedbench.v2.spec import derive_seed

    import urllib.request

    beacon = json.loads(
        urllib.request.urlopen(f"https://api.drand.sh/{CHAIN_HASH}/public/{target}", timeout=30).read()
    )
    signature = bytes.fromhex(beacon["signature"])
    seed = derive_seed(CHAIN_HASH, target, signature, TEST_SECRET)
    items = generate_batch(seed, {"arith_word": 1, "code_output": 1, "graph_path": 0})
    # graph n=0 is allowed by generate_batch.
    model = next(row for row in manifest["models"] if row["id"] == "falcon3-1b-instruct")
    grades = []
    for item in items:
        if item.family == "graph_path":
            continue
        meta = run_item(manifest, model, item.item_id, item.family, item.prompt, OUT / "runs")
        raw = (OUT / "runs" / f"{item.item_id}.txt").read_text(encoding="utf-8", errors="replace")
        stderr = (OUT / "runs" / f"{item.item_id}.stderr").read_text(encoding="utf-8", errors="replace")
        from sealedbench.v2.scoring import _runs

        truncated = is_truncated(raw, _runs(stderr), int(manifest["runtime"]["n_predict"].get(item.family, 768)))
        graded = grade_answer(item.family, item.oracle_answer, raw, truncated=truncated)
        grades.append(
            {
                "item_id": item.item_id,
                "family": item.family,
                "returncode": meta.get("returncode"),
                "seconds": meta.get("seconds"),
                "correct": graded.correct,
                "invalid": graded.invalid,
                "truncated": graded.truncated,
                "parsed": graded.parsed,
                "oracle": graded.oracle,
            }
        )
        print(f"DRY {item.item_id} rc={meta.get('returncode')} correct={graded.correct} invalid={graded.invalid}", flush=True)
    # The command builder is what the batch will use. Touch it so a refactor cannot drop flags.
    sample = completion_cmd(manifest, model, items[0].prompt, items[0].family)
    if "-t" not in sample or "6" not in sample or "--temp" not in sample:
        raise SystemExit("dry run command is missing frozen flags")
    report = {"round": target, "decrypt": "PASS", "grades": grades, "model": model["id"]}
    (OUT / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    (ROOT / "results" / "batches" / "b2" / "dry_run.json").write_text(json.dumps(report, indent=2) + "\n")
    if any(row["returncode"] != 0 for row in grades):
        raise SystemExit("inference failed")
    print("DRY_RUN_OK", flush=True)


if __name__ == "__main__":
    main()
