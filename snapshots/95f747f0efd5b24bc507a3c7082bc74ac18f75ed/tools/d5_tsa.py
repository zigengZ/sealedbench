#!/usr/bin/env python3
"""RFC 3161 timestamps for each probe ciphertext sha256.

Rate limits:
  freetsa  >= 1.2 s between requests (published cap is 1 req/s/IP)
  digicert >= 2 s
  sectigo  >= 16 s (published floor is 15 s between automated requests)
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/codes/sealedbench")
DAY1 = ROOT / "results" / "day1"
TSA = DAY1 / "tsa"
CA = TSA / "ca"
MANIFEST = json.loads((DAY1 / "manifest.json").read_text())

TSAS = [
    {
        "name": "freetsa",
        "url": "https://freetsa.org/tsr",
        "sleep_s": 1.2,
        "ca_urls": [
            ("https://freetsa.org/files/cacert.pem", "freetsa-cacert.pem"),
            ("https://freetsa.org/files/tsa.crt", "freetsa-tsa.crt"),
        ],
    },
    {
        "name": "digicert",
        "url": "http://timestamp.digicert.com",
        "sleep_s": 2.0,
        "ca_urls": [],
    },
    {
        "name": "sectigo",
        "url": "http://timestamp.sectigo.com",
        "sleep_s": 16.0,
        "ca_urls": [],
    },
]

SYSTEM_CA = Path("/etc/ssl/certs/ca-certificates.crt")


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def download_cas() -> None:
    CA.mkdir(parents=True, exist_ok=True)
    for tsa in TSAS:
        for url, name in tsa["ca_urls"]:
            dest = CA / name
            if dest.exists() and dest.stat().st_size > 0:
                continue
            req = urllib.request.Request(url, headers={"User-Agent": "sealedbench/0.0.1"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest.write_bytes(resp.read())
            print(f"saved {dest}", flush=True)


def openssl(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["openssl", *args],
        text=True,
        capture_output=True,
        check=check,
    )


def parse_gentime(text: str) -> str | None:
    for line in text.splitlines():
        if "Time stamp:" not in line and "Time stamp :" not in line:
            continue
        raw = line.split(":", 1)[1].strip()
        # "Oct 17 09:01:02 2026 GMT" or "Oct  7 ..."
        cleaned = " ".join(raw.split())
        for fmt in ("%b %d %H:%M:%S %Y GMT", "%b %d %H:%M:%S.%f %Y GMT"):
            try:
                dt = datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
        return raw
    return None


def verify(tsr: Path, data: Path) -> dict:
    attempts = []
    ca_candidates = []
    if (CA / "freetsa-cacert.pem").exists():
        ca_candidates.append(("freetsa-cacert", [str(CA / "freetsa-cacert.pem")]))
    if SYSTEM_CA.exists():
        ca_candidates.append(("system", [str(SYSTEM_CA)]))
    untrusted = []
    if (CA / "freetsa-tsa.crt").exists():
        untrusted = [str(CA / "freetsa-tsa.crt")]
    for label, cafiles in ca_candidates:
        for extra in ([], untrusted):
            cmd = ["ts", "-verify", "-in", str(tsr), "-data", str(data), "-CAfile", cafiles[0]]
            if extra:
                cmd += ["-untrusted", extra[0]]
            proc = openssl(cmd)
            attempts.append(
                {
                    "ca": label,
                    "untrusted": extra[0] if extra else None,
                    "code": proc.returncode,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip()[:500],
                }
            )
            if proc.returncode == 0 and "Verification: OK" in proc.stdout + proc.stderr:
                return {"ok": True, "attempts": attempts}
    return {"ok": False, "attempts": attempts}


def stamp_one(tsa: dict, probe: dict) -> dict:
    cipher = ROOT / probe["ciphertext_path"]
    out_dir = TSA / tsa["name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    tsq = out_dir / f"{probe['probe_id']}.tsq"
    tsr = out_dir / f"{probe['probe_id']}.tsr"
    q = openssl(["ts", "-query", "-data", str(cipher), "-sha256", "-cert", "-out", str(tsq)])
    if q.returncode != 0:
        return {
            "probe_id": probe["probe_id"],
            "tsa": tsa["name"],
            "ok": False,
            "stage": "query",
            "stderr": q.stderr.strip(),
        }
    body = tsq.read_bytes()
    req = urllib.request.Request(
        tsa["url"],
        data=body,
        headers={"Content-Type": "application/timestamp-query", "User-Agent": "sealedbench/0.0.1"},
        method="POST",
    )
    requested = utcnow()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            status = resp.status
    except Exception as exc:  # noqa: BLE001 - recorded as evidence
        return {
            "probe_id": probe["probe_id"],
            "tsa": tsa["name"],
            "ok": False,
            "stage": "http",
            "requested_utc": requested,
            "error": str(exc),
        }
    tsr.write_bytes(raw)
    text = openssl(["ts", "-reply", "-in", str(tsr), "-text"])
    gentime = parse_gentime(text.stdout) if text.returncode == 0 else None
    checked = verify(tsr, cipher)
    return {
        "probe_id": probe["probe_id"],
        "tsa": tsa["name"],
        "ok": checked["ok"],
        "http_status": status,
        "requested_utc": requested,
        "gen_time_utc": gentime,
        "ciphertext_sha256": probe["ciphertext_sha256"],
        "tsr": str(tsr.relative_to(ROOT)),
        "reply_text_ok": text.returncode == 0,
        "verify": checked,
        "reply_stderr": text.stderr.strip()[:400] if text.returncode != 0 else "",
    }


def main() -> None:
    TSA.mkdir(parents=True, exist_ok=True)
    download_cas()
    rows = []
    for tsa in TSAS:
        for i, probe in enumerate(MANIFEST["probes"]):
            if i:
                time.sleep(tsa["sleep_s"])
            row = stamp_one(tsa, probe)
            if not row.get("ok"):
                time.sleep(tsa["sleep_s"])
                retry = stamp_one(tsa, probe)
                retry["retry"] = True
                if retry.get("ok"):
                    row = retry
                else:
                    row["retry_result"] = retry
            rows.append(row)
            print(
                f"{row['tsa']} {row['probe_id']} ok={row.get('ok')} gen={row.get('gen_time_utc')}",
                flush=True,
            )
            (TSA / "partial.json").write_text(json.dumps(rows, indent=2) + "\n")
    (TSA / "summary.json").write_text(
        json.dumps({"finished_utc": utcnow(), "rows": rows}, indent=2) + "\n"
    )
    failed = [r for r in rows if not r.get("ok")]
    print(f"D5_DONE fail={len(failed)}/{len(rows)}", flush=True)
    if failed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
