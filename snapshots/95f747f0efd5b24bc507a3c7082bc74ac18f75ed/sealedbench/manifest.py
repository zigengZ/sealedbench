"""Build a batch manifest from measured files and the protocol constants."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from sealedbench.protocol import (
    APP_VERSION,
    BATCHES,
    CHAIN_HASH,
    CHAIN_PUBKEY,
    DECLARED_BATCHES,
    DRAND_URL,
    GENESIS,
    GRADER_FILES,
    ITEM_ORDERING_TEXT,
    MODELS,
    PERIOD_S,
    PROTOCOL_VERSION,
    REGEXES,
    REPORTING,
    RUNTIME,
    SCHEME,
    SEED_RULE_TEXT,
    SYSTEM_PROMPTS,
)
from sealedbench.reference import freeze_reference
from sealedbench.tarball import SEALED_PATHS

ROOT = Path("/root/codes/sealedbench")
CACHE = Path("/root/.cache/sealedbench")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_named_files(rels: list[str]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(rels):
        data = (ROOT / rel).read_bytes()
        digest.update(rel.encode("utf-8") + b"\0" + data + b"\0")
    return digest.hexdigest()


def git_commit() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def git_dirty() -> bool:
    proc = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    # Sealed paths must be clean. Other dirty files are reported by the caller.
    dirty = []
    for line in proc.stdout.splitlines():
        path = line[3:]
        if path in SEALED_PATHS or path.startswith("sealedbench/families/"):
            dirty.append(path)
    return bool(dirty)


def read_host() -> dict:
    cpu = ""
    for line in Path("/proc/cpuinfo").read_text().splitlines():
        if line.startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
    cgroup = Path("/sys/fs/cgroup/system.slice/sealedbench-p2.scope")
    return {
        "cpu_model": cpu,
        "cgroup": "sealedbench-p2.scope",
        "cpu_max": (cgroup / "cpu.max").read_text().strip(),
        "memory_max": (cgroup / "memory.max").read_text().strip(),
        "note": (
            "Phase 2 runs inside sealedbench-p2.scope. The quotas match Phase 1 "
            "sealedbench-p1.scope: 600000/100000 CPU (about 6 CPUs) and 18 GiB."
        ),
    }


def measured_models() -> list[dict]:
    models = []
    for spec in MODELS:
        path = CACHE / "models" / spec["file"]
        digest = sha256_file(path)
        if digest != spec["sha256"]:
            raise RuntimeError(f"{spec['file']} sha256 {digest} != {spec['sha256']}")
        rendered = ROOT / spec["rendered_prompt_path"]
        rendered_sha = sha256_file(rendered)
        if rendered_sha != spec["rendered_prompt_sha256"]:
            raise RuntimeError(f"rendered prompt hash changed for {spec['id']}")
        if rendered.stat().st_size != spec["rendered_prompt_bytes"]:
            raise RuntimeError(f"rendered prompt size changed for {spec['id']}")
        models.append(
            {
                "id": spec["id"],
                "file": spec["file"],
                "sha256": digest,
                "bytes": path.stat().st_size,
                "source_url": spec["url"],
                "chat_template_capture": {
                    "path": spec["rendered_prompt_path"],
                    "sha256": rendered_sha,
                    "bytes": spec["rendered_prompt_bytes"],
                    "note": (
                        "SHA-256 of the Phase 1 debug prompt captured with --jinja "
                        "for the first GSM8K question. It fingerprints the chat "
                        "template together with that system prompt and question."
                    ),
                },
            }
        )
    return models


def measured_runtime() -> dict:
    binary = Path(RUNTIME["binary_path"])
    digest = sha256_file(binary)
    if digest != RUNTIME["binary_sha256"]:
        raise RuntimeError(f"llama-completion sha256 {digest}")
    runtime = json.loads(json.dumps(RUNTIME))
    runtime["binary_sha256"] = digest
    runtime["binary_bytes"] = binary.stat().st_size
    return runtime


def build_manifest(
    batch_id: str,
    *,
    generator_sha256: str,
    generator_bytes: int,
    ciphertext_sha256: str | None,
    ciphertext_bytes: int | None,
    git_commit_hash: str,
) -> dict:
    spec = BATCHES[batch_id]
    return {
        "protocol_version": PROTOCOL_VERSION,
        "app_version": APP_VERSION,
        "batch_id": batch_id,
        "seed_rule": SEED_RULE_TEXT,
        "seed_rule_normalization": (
            "chain_hash_hex and randomness_hex are stripped and lowercased. "
            "ascii(round) is the decimal round with no sign and no leading zeros. "
            "The four pieces are concatenated as ASCII. seed_bytes is the raw "
            "32-byte SHA-256 digest."
        ),
        "drand": {
            "chain_hash": CHAIN_HASH,
            "public_key": CHAIN_PUBKEY,
            "scheme": SCHEME,
            "genesis_unix": GENESIS,
            "period_s": PERIOD_S,
            "beacon_url_template": f"{DRAND_URL}/public/{{round}}",
        },
        "release_round": spec["release_round"],
        "unlock_unix": spec["unlock_unix"],
        "unlock_utc": spec["unlock_utc"],
        "generator": {
            "git_commit": git_commit_hash,
            "generator_sha256": generator_sha256,
            "tarball_bytes": generator_bytes,
            "tarball_encoding": "ustar, mtime 0, uid 0, gid 0, then gzip -n (mtime 0, no filename)",
            "sealed_paths": list(SEALED_PATHS),
            "python": "3.12.3",
            "families": spec["families"],
            "item_ordering": ITEM_ORDERING_TEXT,
        },
        "ciphertext": {
            "sha256": ciphertext_sha256,
            "bytes": ciphertext_bytes,
            "armor": True,
            "tool": "github.com/drand/tlock/cmd/tle@v1.2.0",
        },
        "grader": {
            "sha256": hash_named_files(GRADER_FILES),
            "sha256_method": "SHA-256 over sorted relative paths, each as path bytes, NUL, file bytes, NUL",
            "files": list(GRADER_FILES),
            "regexes": dict(REGEXES),
            "integer_normalization": "strip commas; strip a trailing .0; exact string match",
            "code_normalization": (
                "last fenced block; CRLF to LF; rstrip each line; drop one trailing empty line"
            ),
            "invalid_policy": "unparseable output is invalid and counts as wrong",
        },
        "reference": freeze_reference(),
        "models": measured_models(),
        "system_prompts": dict(SYSTEM_PROMPTS),
        "runtime": measured_runtime(),
        "host": read_host(),
        "reporting": dict(REPORTING),
        "declared_batches": list(DECLARED_BATCHES),
    }


def write_manifest(path: Path, manifest: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
