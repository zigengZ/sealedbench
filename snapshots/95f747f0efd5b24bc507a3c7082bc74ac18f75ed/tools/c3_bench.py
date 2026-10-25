#!/usr/bin/env python3
"""C3 CPU determinism, speed, and GSM8K-test accuracy.

One llama-completion process at a time. A finished item (returncode 0 and a
stdout file) is skipped, so the script can be re-run after an interruption.

Answer extraction, documented here and copied into results/cpu/summary.md:
  gold: last match of ####\\s*(-?\\d[\\d,]*) in the GSM8K answer field
  pred: last ####\\s*(-?\\d[\\d,]*(?:\\.\\d+)?) in the completion, else the
        last -?\\d[\\d,]*(?:\\.\\d+)?
  match: exact string equality after removing commas and a trailing .0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path("/root/codes/sealedbench")
CACHE = Path("/root/.cache/sealedbench")
CPU = ROOT / "results" / "cpu"
GSM8K_URL = (
    "https://raw.githubusercontent.com/openai/grade-school-math/"
    "master/grade_school_math/data/test.jsonl"
)
GSM8K_PATH = CPU / "gsm8k_test.jsonl"
BIN = CACHE / "llama.cpp" / "build" / "bin" / "llama-completion"

SYSTEM_PROMPT = (
    "Solve the grade-school math problem. Show brief reasoning, then end "
    "with a line exactly of the form #### <integer> and nothing after it."
)

GOLD_RE = re.compile(r"####\s*(-?\d[\d,]*)")
PRED_HASH_RE = re.compile(r"####\s*(-?\d[\d,]*(?:\.\d+)?)")
PRED_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
PROMPT_TPS_RE = re.compile(
    r"prompt eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens\s*"
    r"\(\s*[\d.]+\s*ms per token,\s*([\d.]+) tokens per second\)"
)
GEN_TPS_RE = re.compile(
    r"eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*runs\s*"
    r"\(\s*[\d.]+\s*ms per token,\s*([\d.]+) tokens per second\)"
)
N_CTX_TRAIN_RE = re.compile(r"n_ctx_train\s*=\s*(\d+)")

N_PREDICT = 320
CTX = 2048
SEED = 42

MODELS = [
    {
        "id": "qwen3-4b-instruct-2507",
        "family": "Qwen3",
        "params": "4B",
        "quant": "Q8_0",
        "license": "apache-2.0",
        "context_note": "Qwen3 4B Instruct 2507, non-thinking",
        "release_note": "base repo Qwen/Qwen3-4B-Instruct-2507 created 2025-08-05; GGUF from ggml-org",
        "file": "qwen3-4b-instruct-2507-q8_0.gguf",
        "sha256": "ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1",
        "url": "https://huggingface.co/ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF/resolve/main/qwen3-4b-instruct-2507-q8_0.gguf",
    },
    {
        "id": "gemma-3-4b-it",
        "family": "Gemma 3",
        "params": "4B",
        "quant": "Q8_0",
        "license": "gemma",
        "context_note": "text GGUF only; mmproj not downloaded",
        "release_note": "google/gemma-3-4b-it created 2025-02-20; Q8_0 from ggml-org",
        "file": "gemma-3-4b-it-Q8_0.gguf",
        "sha256": "97b06383df48336e7d2f9b56b6ce545e0fa476407a62c0bd081b53447a58e644",
        "url": "https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q8_0.gguf",
    },
    {
        "id": "ministral-3-3b-instruct-2512",
        "family": "Ministral 3",
        "params": "3B",
        "quant": "Q8_0",
        "license": "apache-2.0",
        "context_note": "text GGUF only; mmproj not downloaded",
        "release_note": "mistralai/Ministral-3-3B-Instruct-2512 created 2025-10-31; Q8_0 from ggml-org",
        "file": "Ministral-3-3B-Instruct-2512-Q8_0.gguf",
        "sha256": "70c6e5b77435062a46bfa3f0b9fa21744a10161ed23eabe9fdc47b3fb6711ad3",
        "url": "https://huggingface.co/ggml-org/Ministral-3-3B-Instruct-2512-GGUF/resolve/main/Ministral-3-3B-Instruct-2512-Q8_0.gguf",
    },
    {
        "id": "falcon3-1b-instruct",
        "family": "Falcon3",
        "params": "1B",
        "quant": "Q8_0",
        "license": "other (Falcon / TII)",
        "context_note": "official GGUF from the model org",
        "release_note": "tiiuae/Falcon3-1B-Instruct created 2024-12-14",
        "file": "Falcon3-1B-Instruct-q8_0.gguf",
        "sha256": "dda44709157103fc272ea3c44ae0deb7fbec5b2d82b313362680dec08e66f57a",
        "url": "https://huggingface.co/tiiuae/Falcon3-1B-Instruct-GGUF/resolve/main/Falcon3-1B-Instruct-q8_0.gguf",
    },
]

RUNS = [
    {"name": "t6_a", "n": 50, "threads": 6, "batch": 2048, "ubatch": 512},
    {"name": "t6_b", "n": 10, "threads": 6, "batch": 2048, "ubatch": 512},
    {"name": "t4", "n": 10, "threads": 4, "batch": 2048, "ubatch": 512},
    {"name": "batch", "n": 10, "threads": 6, "batch": 512, "ubatch": 128},
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon_number(raw: str) -> str:
    text = raw.replace(",", "").strip()
    if re.fullmatch(r"-?\d+\.0+", text):
        text = text.split(".", 1)[0]
    return text


def gold_of(answer: str) -> str | None:
    found = GOLD_RE.findall(answer)
    if not found:
        return None
    return canon_number(found[-1])


def pred_of(completion: str) -> str | None:
    hashed = PRED_HASH_RE.findall(completion)
    if hashed:
        return canon_number(hashed[-1])
    nums = PRED_NUM_RE.findall(completion)
    if not nums:
        return None
    return canon_number(nums[-1])


def ensure_gsm8k() -> list[dict]:
    CPU.mkdir(parents=True, exist_ok=True)
    if not GSM8K_PATH.exists():
        req = urllib.request.Request(GSM8K_URL, headers={"User-Agent": "sealedbench/0.0.1"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            GSM8K_PATH.write_bytes(resp.read())
    rows = []
    for line in GSM8K_PATH.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if len(rows) < 50:
        raise SystemExit(f"GSM8K test set has {len(rows)} rows, need at least 50")
    return rows[:50]


def parse_timings(stderr: str) -> dict:
    prompt = None
    gen = None
    for line in stderr.splitlines():
        if "prompt eval time" in line:
            m = PROMPT_TPS_RE.search(line)
            if m:
                prompt = {
                    "ms": float(m.group(1)),
                    "tokens": int(m.group(2)),
                    "tps": float(m.group(3)),
                }
        elif "eval time" in line and "prompt eval time" not in line:
            m = GEN_TPS_RE.search(line)
            if m:
                gen = {
                    "ms": float(m.group(1)),
                    "tokens": int(m.group(2)),
                    "tps": float(m.group(3)),
                }
    nctx = N_CTX_TRAIN_RE.search(stderr)
    return {
        "prompt": prompt,
        "gen": gen,
        "n_ctx_train": int(nctx.group(1)) if nctx else None,
    }


def extract_rendered_prompt(stderr: str) -> str | None:
    key = 'prompt: "'
    start = stderr.find(key)
    if start < 0:
        return None
    start += len(key)
    match = re.search(r'\ntokens: ', stderr[start:])
    if not match:
        return None
    chunk = stderr[start : start + match.start()]
    if chunk.endswith('"'):
        chunk = chunk[:-1]
    return chunk


def base_cmd(model_path: Path, question: str, threads: int, batch: int, ubatch: int) -> list[str]:
    return [
        str(BIN),
        "-m",
        str(model_path),
        "--jinja",
        "-sys",
        SYSTEM_PROMPT,
        "-p",
        question,
        "--temp",
        "0",
        "--top-k",
        "1",
        "--top-p",
        "1",
        "--min-p",
        "0",
        "--repeat-penalty",
        "1",
        "--presence-penalty",
        "0",
        "--frequency-penalty",
        "0",
        "--seed",
        str(SEED),
        "-c",
        str(CTX),
        "-n",
        str(N_PREDICT),
        "--no-warmup",
        "--single-turn",
        "--no-display-prompt",
        "--color",
        "off",
        "--log-colors",
        "off",
        "--no-log-prefix",
        "--reasoning",
        "off",
        "-t",
        str(threads),
        "-tb",
        str(threads),
        "-b",
        str(batch),
        "-ub",
        str(ubatch),
    ]


def run_completion(cmd: list[str], threads: int, timeout_s: int = 900) -> subprocess.CompletedProcess[bytes]:
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(threads)
    env["GOMP_SPINCOUNT"] = "0"
    return subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout_s,
        env=env,
        check=False,
    )


def item_dir(model_id: str, run_name: str) -> Path:
    path = CPU / "runs" / model_id / run_name
    path.mkdir(parents=True, exist_ok=True)
    return path


def already_done(directory: Path, index: int) -> bool:
    meta = directory / f"{index:02d}.json"
    stdout = directory / f"{index:02d}.stdout"
    if not meta.exists() or not stdout.exists():
        return False
    try:
        row = json.loads(meta.read_text())
    except json.JSONDecodeError:
        return False
    return row.get("returncode") == 0


def run_item(model: dict, index: int, row: dict, run: dict, verbose: bool = False) -> dict:
    directory = item_dir(model["id"], run["name"])
    model_path = CACHE / "models" / model["file"]
    cmd = base_cmd(model_path, row["question"], run["threads"], run["batch"], run["ubatch"])
    if verbose:
        cmd += ["--verbose-prompt", "--verbosity", "5"]
    started = time.time()
    try:
        proc = run_completion(cmd, run["threads"])
        stdout = proc.stdout
        stderr = proc.stderr
        code = proc.returncode
        err = None
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        code = 124
        err = "timeout"
    elapsed = time.time() - started
    (directory / f"{index:02d}.stdout").write_bytes(stdout)
    (directory / f"{index:02d}.stderr").write_bytes(stderr)
    stderr_text = stderr.decode("utf-8", errors="replace")
    stdout_text = stdout.decode("utf-8", errors="replace")
    timings = parse_timings(stderr_text)
    gold = gold_of(row["answer"])
    pred = pred_of(stdout_text)
    gen_tokens = timings["gen"]["tokens"] if timings["gen"] else None
    meta = {
        "i": index,
        "run": run["name"],
        "model": model["id"],
        "threads": run["threads"],
        "batch": run["batch"],
        "ubatch": run["ubatch"],
        "returncode": code,
        "error": err,
        "seconds": round(elapsed, 3),
        "gold": gold,
        "pred": pred,
        "match": gold is not None and pred == gold,
        "hit_cap": gen_tokens is not None and gen_tokens >= N_PREDICT,
        "prompt_tps": None if not timings["prompt"] else timings["prompt"]["tps"],
        "gen_tps": None if not timings["gen"] else timings["gen"]["tps"],
        "prompt_tokens": None if not timings["prompt"] else timings["prompt"]["tokens"],
        "gen_tokens": gen_tokens,
        "n_ctx_train": timings["n_ctx_train"],
        "stdout_sha256": sha256_bytes(stdout),
        "stdout_bytes": len(stdout),
    }
    (directory / f"{index:02d}.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(
        f"{model['id']} {run['name']} {index:02d} rc={code} "
        f"match={meta['match']} gen_tps={meta['gen_tps']} hit_cap={meta['hit_cap']}",
        flush=True,
    )
    return meta


def capture_rendered(model: dict, question: str) -> str | None:
    out = CPU / "rendered" / f"{model['id']}.stderr"
    out.parent.mkdir(parents=True, exist_ok=True)
    text_path = CPU / "rendered" / f"{model['id']}.txt"
    if text_path.exists() and text_path.stat().st_size > 0:
        return text_path.read_text()
    model_path = CACHE / "models" / model["file"]
    cmd = base_cmd(model_path, question, 6, 2048, 512)
    cmd += ["--verbose-prompt", "--verbosity", "5", "-n", "1"]
    # The last -n wins because common_params_parse uses the last occurrence.
    proc = run_completion(cmd, 6, timeout_s=600)
    err = proc.stderr.decode("utf-8", errors="replace")
    out.write_text(err)
    rendered = extract_rendered_prompt(err)
    if rendered is None:
        text_path.write_text("")
        return None
    text_path.write_text(rendered)
    return rendered


def median(values: list[float]) -> float | None:
    if not values:
        return None
    return float(statistics.median(values))


def compare(model_id: str, left: str, right: str, n: int) -> dict:
    mismatches = []
    for i in range(n):
        a = item_dir(model_id, left) / f"{i:02d}.stdout"
        b = item_dir(model_id, right) / f"{i:02d}.stdout"
        if not a.exists() or not b.exists():
            mismatches.append({"i": i, "reason": "missing"})
            continue
        ab, bb = a.read_bytes(), b.read_bytes()
        if ab != bb:
            mismatches.append(
                {
                    "i": i,
                    "left_sha256": sha256_bytes(ab),
                    "right_sha256": sha256_bytes(bb),
                    "left_bytes": len(ab),
                    "right_bytes": len(bb),
                }
            )
    return {"identical": not mismatches, "n": n, "mismatches": mismatches}


def summarize_model(model: dict, rows: list[dict]) -> dict:
    t6 = []
    for i in range(50):
        path = item_dir(model["id"], "t6_a") / f"{i:02d}.json"
        if path.exists():
            t6.append(json.loads(path.read_text()))
    prompt = [r["prompt_tps"] for r in t6 if r.get("prompt_tps") is not None]
    gen = [r["gen_tps"] for r in t6 if r.get("gen_tps") is not None]
    nctx = next((r.get("n_ctx_train") for r in t6 if r.get("n_ctx_train")), None)
    rendered_path = CPU / "rendered" / f"{model['id']}.txt"
    rendered = rendered_path.read_text() if rendered_path.exists() else ""
    correct = sum(1 for r in t6 if r.get("match"))
    return {
        "id": model["id"],
        "family": model["family"],
        "params": model["params"],
        "quant": model["quant"],
        "license": model["license"],
        "release_note": model["release_note"],
        "context_note": model["context_note"],
        "sha256": model["sha256"],
        "file": model["file"],
        "url": model["url"],
        "n_ctx_train": nctx,
        "gsm8k_correct": correct,
        "gsm8k_n": len(t6),
        "hit_cap": sum(1 for r in t6 if r.get("hit_cap")),
        "load_failures": sum(1 for r in t6 if r.get("returncode") not in (0, None)),
        "prompt_tps_median": median(prompt),
        "prompt_tps_min": min(prompt) if prompt else None,
        "prompt_tps_max": max(prompt) if prompt else None,
        "gen_tps_median": median(gen),
        "gen_tps_min": min(gen) if gen else None,
        "gen_tps_max": max(gen) if gen else None,
        "rendered_prompt_sha256": sha256_bytes(rendered.encode()) if rendered else None,
        "rendered_prompt_bytes": len(rendered.encode()),
        "determinism": {
            "t6_repeat": compare(model["id"], "t6_a", "t6_b", 10),
            "threads_4": compare(model["id"], "t6_a", "t4", 10),
            "batch": compare(model["id"], "t6_a", "batch", 10),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot", action="store_true", help="one verbose item on the first model")
    parser.add_argument("--model", action="append", default=[], help="limit to these model ids")
    args = parser.parse_args()
    if not BIN.exists():
        raise SystemExit(f"missing binary {BIN}")
    items = ensure_gsm8k()
    selected = [m for m in MODELS if not args.model or m["id"] in args.model]
    if args.pilot:
        model = selected[0]
        rendered = capture_rendered(model, items[0]["question"])
        meta = run_item(model, 0, items[0], RUNS[0], verbose=False)
        print(json.dumps({"rendered_bytes": None if rendered is None else len(rendered), "item": meta}, indent=2))
        return
    for model in selected:
        path = CACHE / "models" / model["file"]
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
        if digest != model["sha256"]:
            print(f"SKIP {model['id']} sha256 {digest}", flush=True)
            continue
        capture_rendered(model, items[0]["question"])
        for run in RUNS:
            for i in range(run["n"]):
                if already_done(item_dir(model["id"], run["name"]), i):
                    print(f"skip {model['id']} {run['name']} {i:02d}", flush=True)
                    continue
                run_item(model, i, items[i], run)
    report = {
        "binary": str(BIN),
        "system_prompt": SYSTEM_PROMPT,
        "seed": SEED,
        "ctx": CTX,
        "n_predict": N_PREDICT,
        "temp": 0,
        "top_k": 1,
        "top_p": 1,
        "min_p": 0,
        "repeat_penalty": 1,
        "presence_penalty": 0,
        "frequency_penalty": 0,
        "reasoning": "off",
        "jinja": True,
        "prompt_cache": False,
        "byte_compare": "stdout completion bytes, not stderr timings",
        "answer_extraction": {
            "gold": r"####\s*(-?\d[\d,]*)",
            "pred_hash": r"####\s*(-?\d[\d,]*(?:\.\d+)?)",
            "pred_fallback": r"-?\d[\d,]*(?:\.\d+)?",
            "normalize": "strip commas; strip a trailing .0; exact string match",
        },
        "gsm8k": str(GSM8K_PATH.relative_to(ROOT)),
        "models": [summarize_model(m, items) for m in selected],
    }
    (CPU / "measurements.json").write_text(json.dumps(report, indent=2) + "\n")
    print("C3_DONE", flush=True)


if __name__ == "__main__":
    main()
