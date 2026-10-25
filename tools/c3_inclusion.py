#!/usr/bin/env python3
"""Poll L1 inclusion for b3 (and cap3 if present) on two independent gateways.

Uses sealedbench.v2's ANS-104 parser. Does not call arweave.net.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sealedbench.v2.verification import Network, inclusion

B1_UNLOCK = 1792314000


def one_pass(batches: list[str]) -> dict:
    network = Network()
    report = {"checked_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "batches": {}}
    for batch in batches:
        tx_path = ROOT / "results/batches" / batch / "txids.json"
        if not tx_path.exists():
            continue
        tx = json.loads(tx_path.read_text())
        manifest = json.loads((ROOT / "results/batches" / batch / "manifest.json").read_text())
        kinds = []
        for kind in ("generator-ciphertext", "reference", "manifest"):
            row = tx.get("items", {}).get(kind)
            if not row:
                continue
            rows = []
            timely = inclusion(
                network,
                row["txid"],
                row["sha256"],
                manifest["unlock_unix"],
                f"{batch} {kind}",
                rows,
                dry=False,
            )
            stamps = []
            for state, name, detail in rows:
                if "timestamp=" in detail:
                    for part in detail.split():
                        if part.startswith("timestamp="):
                            stamps.append(int(part.split("=", 1)[1]))
            kinds.append({
                "kind": kind,
                "txid": row["txid"],
                "sha256": row["sha256"],
                "timely_for_own_deadline": timely,
                "rows": [{"state": state, "name": name, "detail": detail} for state, name, detail in rows],
                "block_timestamps": stamps,
                "before_b1_unlock": [stamp < B1_UNLOCK for stamp in stamps],
            })
        report["batches"][batch] = kinds
    return report


def main() -> None:
    batches = ["b3"]
    if (ROOT / "results/batches/cap3/txids.json").exists():
        batches.append("cap3")
    deadline = int(sys.argv[1]) if len(sys.argv) > 1 else B1_UNLOCK - 60
    out = ROOT / "results/batches/b3/inclusion.json"
    while True:
        report = one_pass(batches)
        out.write_text(json.dumps(report, indent=2) + "\n")
        done = True
        for kinds in report["batches"].values():
            for kind in kinds:
                states = [row["state"] for row in kind["rows"] if row["name"].endswith("inclusion") or "inclusion" in row["name"]]
                if "PASS" not in states:
                    done = False
        print(report["checked_utc"], "done" if done else "waiting", flush=True)
        if done or time.time() >= deadline:
            return
        time.sleep(90)


if __name__ == "__main__":
    main()
