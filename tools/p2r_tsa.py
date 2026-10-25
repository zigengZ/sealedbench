#!/usr/bin/env python3
"""RFC 3161 timestamps for the sealed b1 and cap manifests and ciphertexts.

Timestamps the file bytes. `openssl ts -query -sha256` puts SHA-256(file)
in the request, and `openssl ts -verify -data <file>` checks that digest.

Rate limits: FreeTSA >= 1.2 s, DigiCert >= 2 s, Sectigo >= 16 s.
A TSA that fails is recorded and does not stop the others.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "tsa" / "p2"
CA = OUT / "ca"
DAY1_CA = ROOT / "results" / "day1" / "tsa" / "ca"
SYSTEM_CA = Path("/etc/ssl/certs/ca-certificates.crt")

FILES = [
    {
        "id": "b1-manifest",
        "batch": "b1",
        "kind": "manifest",
        "path": "results/batches/b1/manifest.json",
        "sha256": "0b3e44d6223012cf86530325fb5d41d892a661726d435bcb9fb0d00ef2112022",
    },
    {
        "id": "b1-ciphertext",
        "batch": "b1",
        "kind": "generator-ciphertext",
        "path": "results/batches/b1/generator.tlock",
        "sha256": "e04228df5d103639a04c34250edfd07249da38ca9007d90fb1b15fb80f3e11fc",
    },
    {
        "id": "cap-manifest",
        "batch": "cap",
        "kind": "manifest",
        "path": "results/batches/cap/manifest.json",
        "sha256": "9ed1d0ae31c8a9a08caa26e50dc93646e094af161cbf3ec66769870ee69ab4b7",
    },
    {
        "id": "cap-ciphertext",
        "batch": "cap",
        "kind": "generator-ciphertext",
        "path": "results/batches/cap/generator.tlock",
        "sha256": "ae58d4306691970ce34394e85a413a39bf3fd46374eed53b9f1b0ca369b7068c",
    },
]

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


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def openssl(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["openssl", *args], text=True, capture_output=True, check=False)


def ensure_cas() -> None:
    CA.mkdir(parents=True, exist_ok=True)
    for name in ("freetsa-cacert.pem", "freetsa-tsa.crt"):
        src = DAY1_CA / name
        dest = CA / name
        if src.exists() and (not dest.exists() or dest.stat().st_size == 0):
            shutil.copyfile(src, dest)
    for tsa in TSAS:
        for url, name in tsa["ca_urls"]:
            dest = CA / name
            if dest.exists() and dest.stat().st_size > 0:
                continue
            req = urllib.request.Request(url, headers={"User-Agent": "sealedbench/0.1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                dest.write_bytes(resp.read())
            print(f"saved {dest}", flush=True)


def parse_gentime(text: str) -> str | None:
    for line in text.splitlines():
        if "Time stamp:" not in line and "Time stamp :" not in line:
            continue
        raw = line.split(":", 1)[1].strip()
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
        ca_candidates.append(("freetsa-cacert", str(CA / "freetsa-cacert.pem")))
    if SYSTEM_CA.exists():
        ca_candidates.append(("system", str(SYSTEM_CA)))
    untrusted = str(CA / "freetsa-tsa.crt") if (CA / "freetsa-tsa.crt").exists() else None
    for label, cafile in ca_candidates:
        extras = [None]
        if untrusted:
            extras.append(untrusted)
        for extra in extras:
            cmd = ["ts", "-verify", "-in", str(tsr), "-data", str(data), "-CAfile", cafile]
            if extra:
                cmd += ["-untrusted", extra]
            proc = openssl(cmd)
            attempts.append(
                {
                    "ca": label,
                    "untrusted": extra,
                    "code": proc.returncode,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip()[:500],
                }
            )
            if proc.returncode == 0 and "Verification: OK" in proc.stdout + proc.stderr:
                return {"ok": True, "attempts": attempts}
    return {"ok": False, "attempts": attempts}


def stamp_one(tsa: dict, item: dict) -> dict:
    data_path = ROOT / item["path"]
    out_dir = OUT / tsa["name"]
    out_dir.mkdir(parents=True, exist_ok=True)
    tsq = out_dir / f"{item['id']}.tsq"
    tsr = out_dir / f"{item['id']}.tsr"
    query = openssl(["ts", "-query", "-data", str(data_path), "-sha256", "-cert", "-out", str(tsq)])
    if query.returncode != 0:
        return {
            "id": item["id"],
            "batch": item["batch"],
            "kind": item["kind"],
            "tsa": tsa["name"],
            "ok": False,
            "stage": "query",
            "stderr": query.stderr.strip(),
            "sha256": item["sha256"],
        }
    body = tsq.read_bytes()
    req = urllib.request.Request(
        tsa["url"],
        data=body,
        headers={"Content-Type": "application/timestamp-query", "User-Agent": "sealedbench/0.1.0"},
        method="POST",
    )
    requested = utcnow()
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
            status = resp.status
    except Exception as exc:  # noqa: BLE001 - recorded
        return {
            "id": item["id"],
            "batch": item["batch"],
            "kind": item["kind"],
            "tsa": tsa["name"],
            "ok": False,
            "stage": "http",
            "requested_utc": requested,
            "error": str(exc),
            "sha256": item["sha256"],
        }
    tsr.write_bytes(raw)
    text = openssl(["ts", "-reply", "-in", str(tsr), "-text"])
    gentime = parse_gentime(text.stdout) if text.returncode == 0 else None
    checked = verify(tsr, data_path)
    return {
        "id": item["id"],
        "batch": item["batch"],
        "kind": item["kind"],
        "tsa": tsa["name"],
        "ok": checked["ok"],
        "http_status": status,
        "requested_utc": requested,
        "gen_time_utc": gentime,
        "sha256": item["sha256"],
        "path": item["path"],
        "tsq": str(tsq.relative_to(ROOT)),
        "tsr": str(tsr.relative_to(ROOT)),
        "reply_text_ok": text.returncode == 0,
        "verify": checked,
        "reply_stderr": text.stderr.strip()[:400] if text.returncode != 0 else "",
    }


def main() -> None:
    import hashlib

    OUT.mkdir(parents=True, exist_ok=True)
    for item in FILES:
        digest = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise SystemExit(f"sha256 mismatch for {item['path']}: {digest}")
    ensure_cas()
    rows = []
    partial = OUT / "partial.json"
    for tsa in TSAS:
        for index, item in enumerate(FILES):
            if index:
                time.sleep(tsa["sleep_s"])
            row = stamp_one(tsa, item)
            if not row.get("ok"):
                time.sleep(tsa["sleep_s"])
                retry = stamp_one(tsa, item)
                retry["retry"] = True
                if retry.get("ok"):
                    row = retry
                else:
                    row["retry_result"] = {
                        "ok": retry.get("ok"),
                        "stage": retry.get("stage"),
                        "error": retry.get("error"),
                        "http_status": retry.get("http_status"),
                    }
            rows.append(row)
            print(
                f"{row['tsa']} {row['id']} ok={row.get('ok')} gen={row.get('gen_time_utc')}",
                flush=True,
            )
            partial.write_text(json.dumps(rows, indent=2) + "\n")
    failed = [row for row in rows if not row.get("ok")]
    summary = {
        "finished_utc": utcnow(),
        "files": FILES,
        "ok": len(rows) - len(failed),
        "fail": len(failed),
        "rows": rows,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"T0_DONE ok={summary['ok']} fail={summary['fail']}", flush=True)


if __name__ == "__main__":
    main()
