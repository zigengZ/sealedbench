"""Replay v2 items into a fresh directory and compare bytes."""

from __future__ import annotations

import json

from sealedbench.infer import batch_dir, run_item, _lock
import fcntl
from sealedbench.replay import fresh_replay_dir
from sealedbench.v2.run_release import release_batch


def replay_v2(model: str, k: int, batch: str) -> int:
    directory = batch_dir(batch)
    if not (directory / "items.jsonl").exists():
        code = release_batch(batch)
        if code != 0:
            return code
    manifest = json.loads((directory / "manifest.json").read_text())
    items = [json.loads(line) for line in (directory / "items.jsonl").read_text().splitlines() if line.strip()]
    chosen = next(row for row in manifest["models"] if row["id"] == model)
    out_dir = fresh_replay_dir(batch, model)
    matches = 0
    rows = []
    subset = items[:k]
    lock = _lock()
    try:
        return _compare(manifest, chosen, subset, out_dir, directory, model, k, batch)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _compare(manifest, chosen, subset, out_dir, directory, model, k, batch):
    matches = 0
    rows = []
    for item in subset:
        meta = run_item(manifest, chosen, item["item_id"], item["family"], item["prompt"], out_dir)
        fresh = (out_dir / f"{item['item_id']}.txt").read_bytes()
        published = directory / "runs" / model / f"{item['item_id']}.txt"
        old = published.read_bytes() if published.exists() else None
        same = meta.get("returncode") == 0 and old is not None and old == fresh
        matches += int(same)
        rows.append({"item_id": item["item_id"], "byte_match": same, "returncode": meta.get("returncode")})
        print(f"REPLAY {item['item_id']} match={same}", flush=True)
    report = {
        "batch_id": batch,
        "model": model,
        "k": k,
        "compared": len(subset),
        "matches": matches,
        "output_dir": str(out_dir),
        "items": rows,
    }
    (directory / f"replay_{model}.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"REPLAY_DONE matches={matches}/{len(subset)}")
    return 0 if matches == len(subset) and len(subset) > 0 else 2
