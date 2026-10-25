"""Re-run the first k sealed items and diff the raw completions.

`--txid` loads the index from gateways. `--batch` uses the local batch
directory. Both paths re-download the ciphertext and rebuild the items.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sealedbench.infer import batch_dir, run_item
from sealedbench.items import loads_jsonl, question_set_sha256
from sealedbench.net import Fetcher
from sealedbench.release import fetch_agreed_beacon, fetch_matching, regenerate, tle_decrypt

from sealedbench.paths import repo_root

ROOT = repo_root()


def _load_from_txid(txid: str) -> tuple[dict, dict, str]:
    fetcher = Fetcher()
    hosts = ("https://ar-io.dev", "https://turbo-gateway.com")
    body = None
    agreed = []
    for host in hosts:
        status, _headers, raw = fetcher.get(f"{host}/{txid}")
        if status == 200 and raw:
            agreed.append(raw)
            body = raw
    if body is None or len({raw for raw in agreed}) != 1 or len(agreed) < 2:
        raise RuntimeError("index was not byte-identical on two gateways")
    index = json.loads(body)
    manifest_got = fetch_matching(index["manifest_txid"], index["manifest_sha256"], fetcher)
    return json.loads(manifest_got["body"]), index, index["ciphertext_txid"]


def fresh_replay_dir(batch: str, model: str) -> Path:
    """A new directory for this replay. Existing completions are not reused.

    run_item returns a previous meta file when returncode is 0. The b1 pipeline
    replays qwen3 twice into the same folder, so the second call would report
    the first call's bytes. Each invocation gets its own timestamped directory.
    """
    base = batch_dir(batch) / "replay" / model
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for suffix in range(1000):
        name = stamp if suffix == 0 else f"{stamp}-{suffix}"
        path = base / name
        try:
            path.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        return path
    raise RuntimeError(f"could not allocate a fresh replay directory under {base}")


def replay(model: str, k: int, txid: str | None = None, batch: str | None = None) -> int:
    if batch and not txid:
        manifest_path = batch_dir(batch) / "manifest.json"
        if manifest_path.exists():
            header = json.loads(manifest_path.read_text())
            if header.get("protocol_version") == "sealedbench/v2":
                from sealedbench.v2.replay_run import replay_v2

                return replay_v2(model, k, batch)
    if not txid and not batch:
        print("replay needs --txid or --batch")
        return 2
    fetcher = Fetcher()
    index = None
    if txid:
        manifest, index, cipher_id = _load_from_txid(txid)
        batch = index.get("batch_id", batch or "b1")
        expected_q = index.get("question_set_sha256")
    else:
        manifest = json.loads((batch_dir(batch) / "manifest.json").read_text())
        txids = json.loads((batch_dir(batch) / "txids.json").read_text())
        cipher_id = txids["items"]["generator-ciphertext"]["txid"]
        release = json.loads((batch_dir(batch) / "release.json").read_text())
        expected_q = release["question_set_sha256"]
    armor = fetch_matching(cipher_id, manifest["ciphertext"]["sha256"], fetcher)["body"]
    beacon, beacon_meta = fetch_agreed_beacon(manifest["release_round"], fetcher)
    code, plain, err = tle_decrypt(armor)
    if code != 0:
        print(f"REPLAY_FAIL decrypt {err[-300:]}")
        return 2
    counts = {row["name"]: int(row["n"]) for row in manifest["generator"]["families"]}
    jsonl = regenerate(
        plain,
        manifest["drand"]["chain_hash"],
        manifest["release_round"],
        beacon["randomness"],
        counts,
    )
    items = loads_jsonl(jsonl)
    qhash = question_set_sha256(items)
    if qhash != expected_q:
        print(f"REPLAY_FAIL question set {qhash} != {expected_q}")
        return 2
    chosen = next(row for row in manifest["models"] if row["id"] == model)
    subset = items[:k]
    matches = 0
    diffs = []
    out_dir = fresh_replay_dir(batch, model)
    for item in subset:
        meta = run_item(
            manifest,
            chosen,
            item.item_id,
            item.family,
            item.prompt,
            out_dir,
        )
        published = batch_dir(batch) / "runs" / model / f"{item.item_id}.txt"
        fresh = (out_dir / f"{item.item_id}.txt").read_bytes()
        old = published.read_bytes() if published.exists() else None
        same = old is not None and old == fresh
        if same:
            matches += 1
        diffs.append(
            {
                "item_id": item.item_id,
                "byte_match": same,
                "published_bytes": None if old is None else len(old),
                "replay_bytes": len(fresh),
                "returncode": meta.get("returncode"),
            }
        )
        print(f"REPLAY {item.item_id} match={same} rc={meta.get('returncode')}", flush=True)
    report = {
        "batch_id": batch,
        "model": model,
        "k": k,
        "txid": txid,
        "matches": matches,
        "items": diffs,
        "question_set_sha256": qhash,
        "output_dir": str(out_dir),
        "beacon_relays_ok": beacon_meta.get("relays_ok"),
    }
    out = batch_dir(batch) / f"replay_{model}.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"REPLAY_DONE matches={matches}/{k} wrote {out.relative_to(ROOT)}")
    return 0 if matches == k else 2
