#!/usr/bin/env python3
"""Confirm L1 inclusion of the v2 uploads.

Turbo at most once per second. arweave.net at most once per 10 minutes.
ario.zigza.xyz is not queried.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHAIN_NOTE = "b1 unlock 1792314000"
B1_UNLOCK = 1792314000
INDEPENDENT = ("https://ar-io.dev", "https://turbo-gateway.com")
ARWEAVE = "https://arweave.net"
LAST_ARWEAVE = 0.0


def get(url: str, timeout: float = 60) -> tuple[int, bytes]:
    global LAST_ARWEAVE
    if url.startswith(ARWEAVE):
        wait = 600 - (time.time() - LAST_ARWEAVE)
        if LAST_ARWEAVE and wait > 0:
            time.sleep(wait)
        LAST_ARWEAVE = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "sealedbench-v2-inclusion"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read() if err.fp else b""
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc).encode()


def turbo(txid: str) -> dict:
    status, body = get(f"https://upload.ardrive.io/v1/tx/{txid}/status")
    time.sleep(1.1)
    out = {"http": status}
    if status == 200:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = {}
        out.update(
            {
                "status": parsed.get("status"),
                "bundle_id": parsed.get("bundleId"),
                "start": parsed.get("startOffsetInRootBundle"),
                "payload_start": parsed.get("payloadDataStart"),
                "payload_len": parsed.get("payloadContentLength"),
            }
        )
    return out


def l1(bundle: str, use_arweave: bool = True) -> dict:
    hosts = []
    host_list = (*INDEPENDENT, ARWEAVE) if use_arweave else INDEPENDENT
    for host in host_list:
        status, body = get(f"{host}/tx/{bundle}/status")
        row = {"host": host, "http": status}
        if status == 200:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {}
            row["block_height"] = parsed.get("block_height")
            row["confirmations"] = parsed.get("number_of_confirmations")
            row["block_indep_hash"] = parsed.get("block_indep_hash")
        hosts.append(row)
        if host != ARWEAVE:
            time.sleep(1.1)
    return {"hosts": hosts}


def block(height: int) -> dict:
    rows = []
    for host in INDEPENDENT:
        status, body = get(f"{host}/block/height/{height}")
        row = {"host": host, "http": status}
        if status == 200:
            try:
                parsed = json.loads(body)
            except json.JSONDecodeError:
                parsed = {}
            row["timestamp"] = parsed.get("timestamp")
            row["indep_hash"] = parsed.get("indep_hash")
            row["height"] = parsed.get("height")
            txs = parsed.get("txs")
            row["txs_present"] = isinstance(txs, list)
        rows.append(row)
        time.sleep(1.1)
    return {"hosts": rows}


def payload(host: str, bundle: str, start, rel, length, expected: str) -> dict:
    if not all(isinstance(value, int) for value in (start, rel, length)):
        return {"ok": False, "reason": "offset missing"}
    begin = start + rel
    end = begin + length - 1
    req = urllib.request.Request(
        f"{host}/{bundle}",
        headers={"User-Agent": "sealedbench-v2-inclusion", "Range": f"bytes={begin}-{end}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            code = resp.status
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "http": 0, "error": str(exc)[:200]}
    import hashlib

    digest = hashlib.sha256(raw).hexdigest()
    return {
        "host": host,
        "http": code,
        "bytes": len(raw),
        "sha256": digest,
        "ok": code in (200, 206) and len(raw) == length and digest == expected,
    }


def main() -> None:
    items = []
    for batch in ("b2", "cap2"):
        tx = json.loads((ROOT / "results" / "batches" / batch / "txids.json").read_text())
        for kind, row in tx["items"].items():
            items.append({"batch": batch, "kind": kind, "txid": row["txid"], "sha256": row["sha256"]})
    # The reference item lives on b2 and is cited by cap2.
    deadline = time.time() + 40 * 60
    latest = {}
    while time.time() < deadline:
        pending = False
        for item in items:
            info = turbo(item["txid"])
            item["turbo"] = info
            if not info.get("bundle_id"):
                pending = True
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"{stamp} bundles={sum(1 for item in items if item.get('turbo', {}).get('bundle_id'))}/{len(items)}", flush=True)
        if not pending:
            break
        time.sleep(20)
    bundles = {}
    first_l1 = True
    while time.time() < deadline:
        bundles = {}
        for item in items:
            bundle = (item.get("turbo") or {}).get("bundle_id")
            if bundle and bundle not in bundles:
                bundles[bundle] = {"l1": l1(bundle, use_arweave=first_l1)}
        first_l1 = False
        ready = True
        for rec in bundles.values():
            heights = [row.get("block_height") for row in rec["l1"]["hosts"] if row.get("block_height")]
            independent = [
                row.get("block_height")
                for row in rec["l1"]["hosts"]
                if row.get("block_height") and row["host"] in INDEPENDENT
            ]
            if len(independent) >= 2 and len(set(independent)) == 1:
                rec["block"] = block(int(independent[0]))
                stamps = [
                    row.get("timestamp")
                    for row in rec["block"]["hosts"]
                    if isinstance(row.get("timestamp"), int)
                ]
                if len(stamps) < 2 or len(set(stamps)) != 1:
                    ready = False
            else:
                ready = False
        if bundles and ready and all(rec.get("block") for rec in bundles.values()):
            break
        print("L1 not confirmed on two independent gateways yet", flush=True)
        time.sleep(30)
    for item in items:
        bundle = (item.get("turbo") or {}).get("bundle_id")
        turbo_row = item.get("turbo") or {}
        if bundle:
            item["payload"] = payload(
                "https://ar-io.dev",
                bundle,
                turbo_row.get("start"),
                turbo_row.get("payload_start"),
                turbo_row.get("payload_len"),
                item["sha256"],
            )
            time.sleep(1.1)
        block_rows = (bundles.get(bundle) or {}).get("block", {}).get("hosts", [])
        timestamps = [row.get("timestamp") for row in block_rows if isinstance(row.get("timestamp"), int)]
        agree = len(timestamps) >= 2 and len(set(timestamps)) == 1
        ts = timestamps[0] if agree else None
        item["inclusion"] = {
            "bundle_id": bundle,
            "timestamp": ts,
            "timestamp_utc": datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None,
            "two_gateways_agree": agree,
            "before_b1_unlock": None if ts is None else ts <= B1_UNLOCK - 600,
            "margin_vs_b1_s": None if ts is None else B1_UNLOCK - ts,
        }
    out = {
        "checked_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "b1_unlock": B1_UNLOCK,
        "note": CHAIN_NOTE,
        "bundles": bundles,
        "items": items,
    }
    path = ROOT / "results" / "batches" / "b2" / "inclusion.json"
    path.write_text(json.dumps(out, indent=2) + "\n")
    proven = [item["inclusion"]["before_b1_unlock"] for item in items]
    print(f"INCLUSION_WROTE {path} before_b1={proven}", flush=True)


if __name__ == "__main__":
    main()
