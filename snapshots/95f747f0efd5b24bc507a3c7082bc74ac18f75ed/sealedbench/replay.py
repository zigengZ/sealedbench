"""Re-run the first k sealed items and diff the raw completions.

`--txid` loads the index from gateways. `--batch` uses the local batch
directory. Both paths re-download the ciphertext and rebuild the items.
"""

from __future__ import annotations

import json
from pathlib import Path

from sealedbench.infer import batch_dir, run_item
from sealedbench.items import loads_jsonl, question_set_sha256
from sealedbench.net import Fetcher
from sealedbench.release import fetch_beacon, fetch_matching, regenerate, tle_decrypt

ROOT = Path("/root/codes/sealedbench")


def _load_from_txid(txid: str) -> tuple[dict, dict, str]:
    fetcher = Fetcher()
    hosts = ("https://ar-io.dev", "https://turbo-gateway.com", "https://ario.zigza.xyz")
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


def replay(model: str, k: int, txid: str | None = None, batch: str | None = None) -> int:
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
    beacon = fetch_beacon(manifest["release_round"], fetcher)
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
    for item in subset:
        meta = run_item(
            manifest,
            chosen,
            item.item_id,
            item.family,
            item.prompt,
            batch_dir(batch) / "replay" / model,
        )
        published = batch_dir(batch) / "runs" / model / f"{item.item_id}.txt"
        fresh = (batch_dir(batch) / "replay" / model / f"{item.item_id}.txt").read_bytes()
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
    }
    out = batch_dir(batch) / f"replay_{model}.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"REPLAY_DONE matches={matches}/{k} wrote {out.relative_to(ROOT)}")
    return 0 if matches == k else 2
