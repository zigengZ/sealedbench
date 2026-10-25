"""Frozen sizes and rounds for b2 and cap2. See review/p2r/b2_design.md."""

from __future__ import annotations

COUNTS = {"arith_word": 80, "code_output": 30, "graph_path": 30}
N_REFERENCE = 80
N_PREDICT = {
    "default": 768,
    "arith_word": 768,
    "graph_path": 768,
    "code_output": 512,
    "gsm8k": 768,
}

BATCHES = {
    "b2": {
        "release_round": 33188212,
        "unlock_unix": 1792368000,
        "unlock_utc": "2026-10-19T00:00:00Z",
        "peer": "cap2",
    },
    "cap2": {
        "release_round": 33980212,
        "unlock_unix": 1794744000,
        "unlock_utc": "2026-11-15T12:00:00Z",
        "peer": "b2",
    },
}

INCLUSION_RULE = (
    "A committed item is in time iff the L1 block timestamp of its Turbo bundle "
    "is less than or equal to unlock_unix - 600, the bundle id is in that block, "
    "and the data-item bytes hash to the committed sha256 at the payload offset. "
    "The timestamp, height, and hash must agree on at least two independent "
    "gateways. ario.zigza.xyz is operated by the author and never counts as one "
    "of those two. HTTP 404, 429, and timeouts are UNKNOWN, not FAIL. "
    "The author's observation at release time is recorded and is not decisive. "
    "A batch is INVALID only when this check proves a timestamp after the deadline."
)

REPORTING = {
    "primary_endpoint": (
        "Per model and per family, accuracy with invalid and truncated answers "
        "counted as wrong."
    ),
    "interval": "Wilson 95% on each accuracy. Newcombe hybrid score 95% on arith_word minus gsm8k.",
    "comparisons": [
        "accuracy, invalid rate, truncated rate, and accuracy among parsed, for arith_word, code_output, graph_path, and gsm8k indexes 0..79",
        "per model, Newcombe 95% interval for arith_word accuracy minus gsm8k accuracy",
        "template_id counts per family",
        "trivial baseline: uniform draw from that family's observed oracle answers; for graph_path also the direct-edge weight when an edge exists",
    ],
    "not_claimed": [
        "The GSM8K prefix is not difficulty-matched to arith_word.",
        "A gap inside the minimum detectable effect is reported and is not called contamination.",
        "No model-versus-model comparison is a headline result.",
    ],
    "minimum_detectable_effect": (
        "At p=0.5, the Wilson 95% half-width is about 11 percentage points at n=80 "
        "and about 18 points at n=30. The Newcombe half-width of an arith-minus-gsm8k "
        "difference at n=80 is about 16 points. Items that share a template are not "
        "independent, so these are lower bounds on the uncertainty."
    ),
    "invalid_and_no_show": (
        "An unparsable answer is invalid. A completion with no end-of-text marker, "
        "or with a llama.cpp run count at least n_predict-1, is truncated and counts "
        "as invalid in the primary accuracy. Both are reported separately, and "
        "accuracy among parsed excludes them. A crashed item is retried once with "
        "the same flags and both logs are kept. A partial model is published as "
        "partial and is not dropped or trimmed. A batch is INVALID only under the "
        "inclusion rule. Unknown observation is not INVALID."
    ),
    "inclusion_rule": INCLUSION_RULE,
}

# b3 / cap3. n_predict stays at the b2 caps; see review/c3/b3_design.md.
B3_N_PREDICT = {
    "default": 768,
    "arith_word": 768,
    "graph_path": 768,
    "code_output": 512,
    "gsm8k": 768,
}

B3_GRADER_FILES = [
    "sealedbench/v2/grade.py",
    "sealedbench/v2/grade_b3.py",
]

# Ciphertext hashes of the already sealed batches. prepare asserts these
# against the on-disk manifests and does not rewrite those files.
B2_CIPHERTEXT_SHA256 = "a7911be4af063978284e703f6f64cf21378531e27d7cdff6c8665ea8ad9b8bc9"
CAP2_CIPHERTEXT_SHA256 = "39d0d1145a0521285d7125dbb394f13a8f4ec917e60c3129445b0a3ee04776ef"

B3_BATCHES = {
    "b3": {
        "release_round": 33202612,
        "unlock_unix": 1792411200,
        "unlock_utc": "2026-10-19T12:00:00Z",
    },
    "cap3": {
        "release_round": 33980212,
        "unlock_unix": 1794744000,
        "unlock_utc": "2026-11-15T12:00:00Z",
    },
}

B3_N_PREDICT_NOTE = (
    "Chosen from the b2r rehearsal run counts and kept at the b2 caps: "
    "768 for arith_word, graph_path, gsm8k, and the default; 512 for code_output. "
    "In that rehearsal the completed maxima were arith 546, code 333, gsm8k 205, "
    "and graph 748. Three of eight graph outputs had 767 runs and were censored, "
    "so a higher graph cap is not identified. Lengthening those runs does not fit "
    "the 8 hour budget. The arithmetic is in review/c3/b3_design.md. "
    "ctx stays 2048; the longest b2r prompt was 162 tokens."
)

B3_CORRECTION = (
    "b3 corrects b2's grader-input bug found in rehearsal before b1 unlocked. "
    "The sealed b2 grader applied the strict integer rule to raw llama.cpp stdout. "
    "llama.cpp appends the end sentinel on the same line as the final answer, so a line "
    "such as '#### 261 [end of text]' was graded invalid. "
    "The bug was observed on rehearsal batch b2r before b1's unlock at 2026-10-18T09:00:00Z. "
    "b2 and cap2 remain sealed and run as registered. "
    "b3 grades stdout only after the byte procedure in grader.input_normalization. "
    "Truncation detection is unchanged and still uses the raw stdout marker and the run count."
)

CAP3_CORRECTION = (
    "cap3 corrects cap2's grader-input bug. cap2 sealed the same raw-stdout integer rule as b2, "
    "so the same llama.cpp end sentinel makes integer answers invalid. "
    "The bug was found in the b2r rehearsal before b1 unlocked at 2026-10-18T09:00:00Z. "
    "cap2 stays sealed and is not edited. cap3 uses the b3 normalization and the same generation caps."
)
