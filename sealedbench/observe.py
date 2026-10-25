"""One-shot observation of a data item: Turbo status, L1 block, payload bytes.

Inclusion proof prefers https://arweave.net/tx/<bundle>/status and
https://arweave.net/block/height/<h>. If that host returns 429, the same
paths on ar-io.dev are recorded and labeled. The payload check reads the
byte range startOffsetInRootBundle + payloadDataStart for
payloadContentLength bytes from ar-io.dev and compares sha256.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sealedbench.net import Fetcher

L1_HOSTS = ("https://arweave.net", "https://ar-io.dev")
PAYLOAD_HOST = "https://ar-io.dev"


def _iso(ts: float | int | None) -> str | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def observe_item(txid: str, expected_sha256: str, fetcher: Fetcher | None = None) -> dict:
    fetcher = fetcher or Fetcher()
    out = {
        "txid": txid,
        "expected_sha256": expected_sha256,
        "turbo": None,
        "l1": None,
        "block": None,
        "payload": None,
        "error": None,
    }
    code, _headers, body = fetcher.get(f"https://upload.ardrive.io/v1/tx/{txid}/status")
    if code != 200:
        out["error"] = f"turbo status HTTP {code}"
        out["turbo_http"] = code
        return out
    turbo = json.loads(body)
    out["turbo"] = {
        "http": code,
        "status": turbo.get("status"),
        "bundle_id": turbo.get("bundleId"),
        "info": turbo.get("info"),
        "start_offset_in_root_bundle": turbo.get("startOffsetInRootBundle"),
        "payload_data_start": turbo.get("payloadDataStart"),
        "payload_content_length": turbo.get("payloadContentLength"),
        "raw_content_length": turbo.get("rawContentLength"),
    }
    bundle = turbo.get("bundleId")
    if not bundle:
        out["error"] = "turbo status has no bundleId"
        return out
    l1_attempts = []
    chosen = None
    for host in L1_HOSTS:
        url = f"{host}/tx/{bundle}/status"
        status, _hdr, raw = fetcher.get(url)
        attempt = {"host": host, "http": status, "url": url}
        if status == 200:
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            attempt["block_height"] = parsed.get("block_height") if isinstance(parsed, dict) else None
            attempt["confirmations"] = parsed.get("number_of_confirmations") if isinstance(parsed, dict) else None
            if chosen is None and attempt["block_height"]:
                chosen = (host, parsed)
        l1_attempts.append(attempt)
        # One arweave.net request is enough. Do not retry it here.
        if host == "https://arweave.net" and status == 429:
            continue
    out["l1_attempts"] = l1_attempts
    if chosen is None:
        out["error"] = "no L1 block height"
        return out
    host, parsed = chosen
    height = int(parsed["block_height"])
    block_attempts = []
    block = None
    block_host = None
    for bhost in L1_HOSTS:
        url = f"{bhost}/block/height/{height}"
        status, _hdr, raw = fetcher.get(url)
        rec = {"host": bhost, "http": status}
        if status == 200:
            try:
                parsed_block = json.loads(raw)
            except json.JSONDecodeError:
                parsed_block = None
            if isinstance(parsed_block, dict) and "timestamp" in parsed_block:
                rec["timestamp"] = parsed_block["timestamp"]
                rec["indep_hash"] = parsed_block.get("indep_hash")
                if block is None:
                    block = parsed_block
                    block_host = bhost
        block_attempts.append(rec)
        if bhost == "https://arweave.net" and status == 429:
            continue
    out["block_attempts"] = block_attempts
    if block is None:
        out["error"] = "no block timestamp"
        out["l1"] = {
            "source": host,
            "height": height,
            "confirmations": parsed.get("number_of_confirmations"),
            "block_indep_hash": parsed.get("block_indep_hash"),
        }
        return out
    out["l1"] = {
        "source": host,
        "height": height,
        "confirmations": parsed.get("number_of_confirmations"),
        "block_indep_hash": parsed.get("block_indep_hash"),
    }
    out["block"] = {
        "source": block_host,
        "height": int(block.get("height", height)),
        "timestamp": int(block["timestamp"]),
        "timestamp_utc": _iso(block["timestamp"]),
        "indep_hash": block.get("indep_hash"),
    }
    start = turbo.get("startOffsetInRootBundle")
    rel = turbo.get("payloadDataStart")
    length = turbo.get("payloadContentLength")
    payload = {"ok": False}
    if isinstance(start, int) and isinstance(rel, int) and isinstance(length, int) and length >= 0:
        abs_off = start + rel
        end = abs_off + length - 1
        status, hdrs, raw = fetcher.get(
            f"{PAYLOAD_HOST}/{bundle}",
            headers={"Range": f"bytes={abs_off}-{end}"},
        )
        digest = hashlib.sha256(raw).hexdigest()
        payload = {
            "http": status,
            "host": PAYLOAD_HOST,
            "absolute_offset": abs_off,
            "length": length,
            "got_bytes": len(raw),
            "sha256": digest,
            "content_range": hdrs.get("Content-Range") or hdrs.get("content-range"),
            "ok": status in (200, 206) and len(raw) == length and digest == expected_sha256,
        }
    out["payload"] = payload
    return out


def before_unlock(observation: dict, unlock_unix: int) -> str:
    block = observation.get("block") or {}
    ts = block.get("timestamp")
    if ts is None:
        return "UNKNOWN"
    return "PASS" if int(ts) < int(unlock_unix) else "FAIL"
