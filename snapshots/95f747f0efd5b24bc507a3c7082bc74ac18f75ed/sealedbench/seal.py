"""Build the generator tarball, seal it, and write both batch manifests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from sealedbench.manifest import build_manifest, git_commit, git_dirty, write_manifest
from sealedbench.tarball import build_generator_tarball

ROOT = Path("/root/codes/sealedbench")


def _md(manifest: dict) -> str:
    families = ", ".join(f"{row['name']}={row['n']}" for row in manifest["generator"]["families"])
    lines = [
        f"# {manifest['batch_id']} manifest",
        "",
        f"Protocol `{manifest['protocol_version']}`. Unlock {manifest['unlock_utc']} at round {manifest['release_round']}.",
        "",
        "Seed rule, verbatim:",
        "",
        "```",
        manifest["seed_rule"],
        "```",
        "",
        manifest["seed_rule_normalization"],
        "",
        f"Chain `{manifest['drand']['chain_hash']}` scheme `{manifest['drand']['scheme']}`.",
        f"Public key `{manifest['drand']['public_key']}`.",
        "",
        f"Generator commit `{manifest['generator']['git_commit']}`.",
        f"Generator sha256 `{manifest['generator']['generator_sha256']}` ({manifest['generator']['tarball_bytes']} bytes).",
        f"Ciphertext sha256 `{manifest['ciphertext']['sha256']}` ({manifest['ciphertext']['bytes']} bytes).",
        f"Families: {families}.",
        "",
        manifest["generator"]["item_ordering"],
        "",
        f"Grader sha256 `{manifest['grader']['sha256']}`.",
        "",
        "Extraction regexes:",
        "",
    ]
    for name, regex in manifest["grader"]["regexes"].items():
        lines.append(f"- `{name}`: `{regex}`")
    lines.extend(
        [
            "",
            f"Reference list sha256 `{manifest['reference']['list_sha256']}` over GSM8K-test indexes {manifest['reference']['indexes']}.",
            f"Source file sha256 `{manifest['reference']['source_sha256']}`.",
            "",
            "Models:",
            "",
            "| id | sha256 | chat-template capture |",
            "| --- | --- | --- |",
        ]
    )
    for model in manifest["models"]:
        cap = model["chat_template_capture"]["sha256"]
        lines.append(f"| {model['id']} | `{model['sha256']}` | `{cap}` |")
    runtime = manifest["runtime"]
    lines.extend(
        [
            "",
            f"llama.cpp `{runtime['llama_cpp_tag']}` `{runtime['llama_cpp_commit']}`.",
            f"Binary sha256 `{runtime['binary_sha256']}`.",
            f"Flags: -t {runtime['threads']} -tb {runtime['threads_batch']} -b {runtime['batch']} -ub {runtime['ubatch']}, "
            f"seed {runtime['seed']}, ctx {runtime['ctx']}, n_predict default {runtime['n_predict']['default']} "
            f"and code_output {runtime['n_predict']['code_output']}, temp {runtime['temp']}, top-k {runtime['top_k']}, "
            f"top-p {runtime['top_p']}, min-p {runtime['min_p']}, penalties "
            f"{runtime['repeat_penalty']}/{runtime['presence_penalty']}/{runtime['frequency_penalty']}, "
            f"reasoning {runtime['reasoning']}, jinja {runtime['jinja']}, prompt cache {runtime['prompt_cache']}.",
            "",
            f"Host `{manifest['host']['cpu_model']}` cgroup `{manifest['host']['cgroup']}` "
            f"cpu.max `{manifest['host']['cpu_max']}` memory.max `{manifest['host']['memory_max']}`.",
            "",
            manifest["reporting"]["inclusion_rule"],
            manifest["reporting"]["retries"],
            "",
            "Declared batches: " + ", ".join(manifest["declared_batches"]) + ".",
            "",
        ]
    )
    return "\n".join(lines)


def prepare_seal() -> int:
    if git_dirty():
        print("SEAL_FAIL sealed paths are dirty; commit them before sealing")
        return 2
    commit = git_commit()
    tarball = build_generator_tarball(ROOT)
    if len(tarball) > 100 * 1024:
        print(f"SEAL_FAIL tarball {len(tarball)} exceeds 100 KiB")
        return 2
    out = ROOT / "results" / "batches" / "generator.tar.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(tarball)
    print(f"TARBALL {len(tarball)} bytes", flush=True)
    proc = subprocess.run(["node", str(ROOT / "tools" / "m2_seal.mjs")], cwd=ROOT, check=False)
    if proc.returncode != 0:
        print(f"SEAL_FAIL encrypt exit {proc.returncode}")
        return proc.returncode
    meta = json.loads((ROOT / "results" / "batches" / "seal_hashes.json").read_text())
    by_id = {row["batch_id"]: row for row in meta["records"]}
    for batch_id, row in by_id.items():
        manifest = build_manifest(
            batch_id,
            generator_sha256=row["plaintext_sha256"],
            generator_bytes=row["plaintext_bytes"],
            ciphertext_sha256=row["ciphertext_sha256"],
            ciphertext_bytes=row["ciphertext_bytes"],
            git_commit_hash=commit,
        )
        directory = ROOT / "results" / "batches" / batch_id
        write_manifest(directory / "manifest.json", manifest)
        (directory / "MANIFEST.md").write_text(_md(manifest))
        print(f"MANIFEST {batch_id} cipher={row['ciphertext_sha256']}", flush=True)
    print(f"SEAL_PREPARED commit={commit}")
    return 0
