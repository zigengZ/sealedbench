"""Run one llama-completion process at a time under the frozen manifest."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

from sealedbench.reference import reference_questions

from sealedbench.paths import cache_root, repo_root

ROOT = repo_root()
CACHE = cache_root()
LOCK_PATH = CACHE / "llama.lock"

PROMPT_TPS_RE = re.compile(
    r"prompt eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens\b.*?([\d.]+)\s*tokens per second"
)
GEN_TPS_RE = re.compile(
    r"(?<!prompt )eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*runs\b.*?([\d.]+)\s*tokens per second"
)


def batch_dir(batch: str) -> Path:
    return ROOT / "results" / "batches" / batch


def _v2_reference(manifest: dict, batch: str) -> list[dict]:
    expected = manifest["reference"]["sha256"]
    candidates = [
        batch_dir(batch) / "reference.json",
        ROOT / "results" / "batches" / "b2" / "reference.json",
    ]
    for path in candidates:
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            return json.loads(path.read_text())["questions"]
    raise FileNotFoundError(f"v2 reference sha256 {expected} not found")


def resolve_binary(manifest: dict) -> Path:
    expected = manifest["runtime"]["binary_sha256"]
    candidates = []
    if os.environ.get("LLAMA_COMPLETION"):
        candidates.append(Path(os.environ["LLAMA_COMPLETION"]))
    candidates.append(CACHE / "llama.cpp" / "build" / "bin" / "llama-completion")
    candidates.append(Path(manifest["runtime"]["binary_path"]))
    for path in candidates:
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            return path
    raise FileNotFoundError(f"llama-completion sha256 {expected} not found")


def load_manifest(batch: str) -> dict:
    return json.loads((batch_dir(batch) / "manifest.json").read_text())


def n_predict_for(manifest: dict, family: str) -> int:
    table = manifest["runtime"]["n_predict"]
    if family == "gsm8k" and manifest.get("protocol_version") != "sealedbench/v2":
        return int(table["default"])
    return int(table.get(family, table["default"]))


def system_prompt_for(manifest: dict, family: str) -> str:
    if family == "gsm8k":
        return manifest["system_prompts"]["gsm8k_reference"]
    return manifest["system_prompts"][family]


def completion_cmd(manifest: dict, model: dict, prompt: str, family: str) -> list[str]:
    runtime = manifest["runtime"]
    model_path = CACHE / "models" / model["file"]
    cmd = [
        str(resolve_binary(manifest)),
        "-m",
        str(model_path),
        "--jinja",
        "-sys",
        system_prompt_for(manifest, family),
        "-p",
        prompt,
        "--temp",
        str(runtime["temp"]),
        "--top-k",
        str(runtime["top_k"]),
        "--top-p",
        str(runtime["top_p"]),
        "--min-p",
        str(runtime["min_p"]),
        "--repeat-penalty",
        str(runtime["repeat_penalty"]),
        "--presence-penalty",
        str(runtime["presence_penalty"]),
        "--frequency-penalty",
        str(runtime["frequency_penalty"]),
        "--seed",
        str(runtime["seed"]),
        "-c",
        str(runtime["ctx"]),
        "-n",
        str(n_predict_for(manifest, family)),
        "--reasoning",
        str(runtime["reasoning"]),
        "-t",
        str(runtime["threads"]),
        "-tb",
        str(runtime["threads_batch"]),
        "-b",
        str(runtime["batch"]),
        "-ub",
        str(runtime["ubatch"]),
    ]
    cmd.extend(runtime["extra_args"])
    return cmd


def parse_timings(stderr: str) -> dict:
    prompt = None
    gen = None
    for line in stderr.splitlines():
        if "prompt eval time" in line:
            match = PROMPT_TPS_RE.search(line)
            if match:
                prompt = {"ms": float(match.group(1)), "tokens": int(match.group(2)), "tps": float(match.group(3))}
        elif "eval time" in line:
            match = GEN_TPS_RE.search(line)
            if match:
                gen = {"ms": float(match.group(1)), "tokens": int(match.group(2)), "tps": float(match.group(3))}
    return {"prompt": prompt, "gen": gen}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_once(cmd: list[str], env: dict, timeout_s: int = 900):
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_s,
            env=env,
            check=False,
        )
        return proc.returncode, proc.stdout, proc.stderr, time.time() - started, None
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        return 124, stdout, stderr, time.time() - started, "timeout"


def run_item(manifest: dict, model: dict, item_id: str, family: str, prompt: str, directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    stdout_path = directory / f"{item_id}.txt"
    meta_path = directory / f"{item_id}.json"
    if meta_path.exists() and stdout_path.exists():
        try:
            old = json.loads(meta_path.read_text())
        except json.JSONDecodeError:
            old = {}
        intact = old.get("stdout_sha256") == _sha256(stdout_path.read_bytes())
        if intact and (old.get("returncode") == 0 or
                       (manifest.get("protocol_version") == "sealedbench/v2" and old.get("attempt") == 2)):
            return old
    runtime = manifest["runtime"]
    env = os.environ.copy()
    env.update({key: str(value) for key, value in runtime["env"].items()})
    cmd = completion_cmd(manifest, model, prompt, family)
    n_predict = n_predict_for(manifest, family)
    code, stdout, stderr, seconds, err = _run_once(cmd, env)
    attempt = 1
    if code != 0:
        (directory / f"{item_id}.attempt1.txt").write_bytes(stdout)
        (directory / f"{item_id}.attempt1.stderr").write_bytes(stderr)
        (directory / f"{item_id}.attempt1.json").write_text(
            json.dumps({"returncode": code, "error": err, "seconds": round(seconds, 3)}, indent=2) + "\n"
        )
        code, stdout, stderr, seconds, err = _run_once(cmd, env)
        attempt = 2
    (directory / f"{item_id}.txt").write_bytes(stdout)
    (directory / f"{item_id}.stderr").write_bytes(stderr)
    stderr_text = stderr.decode("utf-8", errors="replace")
    timings = parse_timings(stderr_text)
    gen_tokens = timings["gen"]["tokens"] if timings["gen"] else None
    meta = {
        "item_id": item_id,
        "model": model["id"],
        "family": family,
        "attempt": attempt,
        "returncode": code,
        "error": err,
        "seconds": round(seconds, 3),
        "n_predict": n_predict,
        "prompt_tokens": timings["prompt"]["tokens"] if timings["prompt"] else None,
        "prompt_tps": timings["prompt"]["tps"] if timings["prompt"] else None,
        "gen_tokens": gen_tokens,
        "gen_tps": timings["gen"]["tps"] if timings["gen"] else None,
        "hit_cap": bool(gen_tokens is not None and gen_tokens >= n_predict - (1 if manifest.get("protocol_version") == "sealedbench/v2" else 0)),
        "stdout_sha256": _sha256(stdout),
        "stdout_bytes": len(stdout),
    }
    temporary = meta_path.with_suffix(".json.partial")
    temporary.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n")
    temporary.replace(meta_path)
    return meta


def _lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = LOCK_PATH.open("a")
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def infer_batch(batch: str, models: list[str] | None = None, limit: int | None = None) -> int:
    manifest = load_manifest(batch)
    try:
        resolve_binary(manifest)
    except FileNotFoundError as exc:
        print(f"BINARY_SHA_MISMATCH {exc}")
        return 2
    items = []
    for line in (batch_dir(batch) / "items.jsonl").read_text().splitlines():
        if line.strip():
            items.append(json.loads(line))
    if limit is not None:
        items = items[:limit]
    if manifest.get("protocol_version") == "sealedbench/v2":
        reference = _v2_reference(manifest, batch)
    else:
        reference = reference_questions()
    wanted = set(models) if models else None
    lock = _lock()
    failures = 0
    try:
        for model in manifest["models"]:
            if wanted is not None and model["id"] not in wanted:
                continue
            exam_dir = batch_dir(batch) / "runs" / model["id"]
            ref_dir = batch_dir(batch) / "reference_runs" / model["id"]
            work = [("exam", exam_dir, item["item_id"], item["family"], item["prompt"]) for item in items]
            work += [
                ("ref", ref_dir, row["item_id"], "gsm8k", row["question"])
                for row in reference
            ]
            print(f"INFER_START {model['id']} n={len(work)}", flush=True)
            for kind, directory, item_id, family, prompt in work:
                meta = run_item(manifest, model, item_id, family, prompt, directory)
                if meta.get("returncode") != 0:
                    failures += 1
                print(
                    f"INFER {model['id']} {item_id} rc={meta.get('returncode')} "
                    f"s={meta.get('seconds')} gen={meta.get('gen_tokens')} attempt={meta.get('attempt')}",
                    flush=True,
                )
            print(f"INFER_DONE {model['id']}", flush=True)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()
    print(f"INFER_BATCH_DONE failures={failures}")
    return 0 if failures == 0 else 2
