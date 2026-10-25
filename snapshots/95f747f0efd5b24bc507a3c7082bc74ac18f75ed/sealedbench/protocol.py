"""Frozen Phase 2 constants. The manifest builder reads this module.

Numbers that can be remeasured (binary sha256, cgroup files, GGUF sha256)
are checked again at seal time. The literals here are the Phase 1 record.
"""

from __future__ import annotations

from sealedbench.extract import (
    FENCE_RE_SRC,
    GOLD_RE_SRC,
    INTEGER_BARE_RE_SRC,
    INTEGER_HASH_RE_SRC,
)
from sealedbench.generate import ITEM_ORDERING
from sealedbench.seed import SEED_RULE

PROTOCOL_VERSION = "sealedbench/v1"
APP_VERSION = "0.1.0"

CHAIN_HASH = "52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971"
CHAIN_PUBKEY = (
    "83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c"
    "8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5"
    "ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a"
)
SCHEME = "bls-unchained-g1-rfc9380"
GENESIS = 1692803367
PERIOD_S = 3
DRAND_URL = f"https://api.drand.sh/{CHAIN_HASH}"

# round = floor((unix - genesis) / period) + 1, and both targets fall on a boundary.
BATCHES = {
    "b1": {
        "release_round": 33170212,
        "unlock_unix": 1792314000,
        "unlock_utc": "2026-10-18T09:00:00Z",
        "families": [
            {"name": "arith_word", "n": 120},
            {"name": "code_output", "n": 60},
            {"name": "graph_path", "n": 60},
        ],
    },
    "cap": {
        "release_round": 33980212,
        "unlock_unix": 1794744000,
        "unlock_utc": "2026-11-15T12:00:00Z",
        "families": [
            {"name": "arith_word", "n": 120},
            {"name": "code_output", "n": 60},
            {"name": "graph_path", "n": 60},
        ],
    },
}

DECLARED_BATCHES = ["b1", "cap"]

SYSTEM_PROMPTS = {
    "arith_word": (
        "Solve the grade-school math problem. Show brief reasoning, then end "
        "with a line exactly of the form #### <integer> and nothing after it."
    ),
    "graph_path": (
        "Solve the shortest-path problem on the undirected weighted graph. "
        "Show brief reasoning, then end with a line exactly of the form "
        "#### <integer> and nothing after it."
    ),
    "code_output": (
        "Determine the exact standard output of the Python 3 program. After any "
        "reasoning, put that output and only that output in one fenced code block. "
        "The last fenced block is graded. Do not add commentary inside the fence."
    ),
    "gsm8k_reference": (
        "Solve the grade-school math problem. Show brief reasoning, then end "
        "with a line exactly of the form #### <integer> and nothing after it."
    ),
}

BUILD_FLAGS = [
    "-DCMAKE_BUILD_TYPE=Release",
    "-DGGML_NATIVE=ON",
    "-DGGML_AVX512=ON",
    "-DGGML_AVX512_VBMI=ON",
    "-DGGML_AVX512_VNNI=ON",
    "-DGGML_AVX512_BF16=ON",
    "-DGGML_CUDA=OFF",
    "-DGGML_BLAS=OFF",
    "-DGGML_METAL=OFF",
    "-DGGML_VULKAN=OFF",
    "-DGGML_HIP=OFF",
    "-DGGML_MUSA=OFF",
    "-DGGML_RPC=OFF",
    "-DGGML_SYCL=OFF",
    "-DGGML_OPENCL=OFF",
    "-DGGML_OPENVINO=OFF",
    "-DGGML_ZENDNN=OFF",
    "-DGGML_WEBGPU=OFF",
    "-DLLAMA_CURL=OFF",
    "-DLLAMA_OPENSSL=OFF",
    "-DLLAMA_BUILD_SERVER=OFF",
    "-DLLAMA_BUILD_TESTS=OFF",
    "-DLLAMA_BUILD_EXAMPLES=OFF",
    "-DLLAMA_BUILD_UI=OFF",
]

MODELS = [
    {
        "id": "qwen3-4b-instruct-2507",
        "file": "qwen3-4b-instruct-2507-q8_0.gguf",
        "sha256": "ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1",
        "url": "https://huggingface.co/ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF/resolve/main/qwen3-4b-instruct-2507-q8_0.gguf",
        "rendered_prompt_path": "results/cpu/rendered/qwen3-4b-instruct-2507.txt",
        "rendered_prompt_sha256": "d013fd0cbe6c4319a336769fd8acc21f8755181f69ec9025ed6fca704bd58070",
        "rendered_prompt_bytes": 498,
    },
    {
        "id": "gemma-3-4b-it",
        "file": "gemma-3-4b-it-Q8_0.gguf",
        "sha256": "97b06383df48336e7d2f9b56b6ce545e0fa476407a62c0bd081b53447a58e644",
        "url": "https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF/resolve/main/gemma-3-4b-it-Q8_0.gguf",
        "rendered_prompt_path": "results/cpu/rendered/gemma-3-4b-it.txt",
        "rendered_prompt_sha256": "b617e4f52945baccc027e9232c10ffb2f57b866b7f1d463ad8b852cea5dc306a",
        "rendered_prompt_bytes": 475,
    },
    {
        "id": "ministral-3-3b-instruct-2512",
        "file": "Ministral-3-3B-Instruct-2512-Q8_0.gguf",
        "sha256": "70c6e5b77435062a46bfa3f0b9fa21744a10161ed23eabe9fdc47b3fb6711ad3",
        "url": "https://huggingface.co/ggml-org/Ministral-3-3B-Instruct-2512-GGUF/resolve/main/Ministral-3-3B-Instruct-2512-Q8_0.gguf",
        "rendered_prompt_path": "results/cpu/rendered/ministral-3-3b-instruct-2512.txt",
        "rendered_prompt_sha256": "93b2d2a1cc8c05535b20d31bb22a440115eb055e77eb366d7d1aed861a270977",
        "rendered_prompt_bytes": 462,
    },
    {
        "id": "falcon3-1b-instruct",
        "file": "Falcon3-1B-Instruct-q8_0.gguf",
        "sha256": "dda44709157103fc272ea3c44ae0deb7fbec5b2d82b313362680dec08e66f57a",
        "url": "https://huggingface.co/tiiuae/Falcon3-1B-Instruct-GGUF/resolve/main/Falcon3-1B-Instruct-q8_0.gguf",
        "rendered_prompt_path": "results/cpu/rendered/falcon3-1b-instruct.txt",
        "rendered_prompt_sha256": "227fa354934a1cda4f3181000d6354842ffac5e31db80bba866e391148074a64",
        "rendered_prompt_bytes": 454,
    },
]

LLAMA_COMMIT = "620d2225cc436ab0b001e3200e590e3b286ef9ab"
LLAMA_TAG = "v0.7.0"
LLAMA_BINARY = "/root/.cache/sealedbench/llama.cpp/build/bin/llama-completion"
LLAMA_BINARY_SHA256 = "d95bb69be967034fa5414b708a75e8119946ecbdb34404363111d2ee20cd5eb7"

RUNTIME = {
    "llama_cpp_tag": LLAMA_TAG,
    "llama_cpp_commit": LLAMA_COMMIT,
    "build_flags": BUILD_FLAGS,
    "compile_flags": "-O3 -DNDEBUG -std=gnu++17 -fPIC -march=native -fopenmp",
    "binary_path": LLAMA_BINARY,
    "binary_sha256": LLAMA_BINARY_SHA256,
    "threads": 6,
    "threads_batch": 6,
    "batch": 2048,
    "ubatch": 512,
    "seed": 42,
    "ctx": 2048,
    "n_predict": {"default": 320, "code_output": 512},
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
    "prompt_cache_note": (
        "llama-completion v0.7.0 enables a prompt cache only when --prompt-cache "
        "names a file. The frozen command does not pass that flag."
    ),
    "extra_args": [
        "--no-warmup",
        "--single-turn",
        "--no-display-prompt",
        "--color",
        "off",
        "--log-colors",
        "off",
        "--no-log-prefix",
    ],
    "env": {"OMP_NUM_THREADS": "6", "GOMP_SPINCOUNT": "0"},
}

REPORTING = {
    "all_declared_batches_reported": True,
    "invalid_output_counts_as_wrong": True,
    "inclusion_rule": (
        "A batch whose manifest or ciphertext is not in an L1 block before the "
        "release round is invalid and is reported as such."
    ),
    "retries": (
        "none. A crashed run is re-executed once with identical settings and both logs are kept."
    ),
}

GRADER_FILES = ["sealedbench/extract.py", "sealedbench/grade.py"]
REGEXES = {
    "integer_hash": INTEGER_HASH_RE_SRC,
    "integer_bare_fallback": INTEGER_BARE_RE_SRC,
    "gsm8k_gold": GOLD_RE_SRC,
    "code_fence": FENCE_RE_SRC,
}
ITEM_ORDERING_TEXT = ITEM_ORDERING
SEED_RULE_TEXT = SEED_RULE

GSM8K_PATH = "results/cpu/gsm8k_test.jsonl"
GSM8K_URL = (
    "https://raw.githubusercontent.com/openai/grade-school-math/"
    "master/grade_school_math/data/test.jsonl"
)
REFERENCE_INDEXES = list(range(120))
