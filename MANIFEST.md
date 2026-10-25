# SealedBench manifest

Each batch has `results/batches/<id>/manifest.json` and `results/batches/<id>/MANIFEST.md`. This file is the field guide. The JSON file is the one that is uploaded and hashed.

## Seed rule

The manifest stores this string verbatim:

```
seed_hex = SHA-256( "sealedbench/v1" || chain_hash_hex || ascii(round) || randomness_hex )
```

`chain_hash_hex` and `randomness_hex` are stripped and lowercased. `ascii(round)` is the decimal round with no sign and no leading zeros. The four pieces are concatenated as ASCII. `seed_bytes` is the raw 32-byte digest. `randomness_hex` is the `randomness` field of the same quicknet round that decrypts the generator.

The per-family seed is SHA-256 of `ASCII("sealedbench/v1/family\n") || seed_bytes || ASCII("\n") || ASCII(family) || ASCII("\n") || ASCII(n)`.

## What a manifest fixes

- Protocol version `sealedbench/v1`, batch id, the seed rule, drand chain hash, public key, scheme `bls-unchained-g1-rfc9380`, genesis `1692803367`, period 3 seconds, release round, and the computed unlock time.
- Generator git commit, sha256 of the deterministic source tarball, sealed paths, Python 3.12.3, families and `n`, and the item ordering rule.
- Grader sha256, the extraction regexes, and the normalization rules. Integer answers use the Phase 1 convention: last `####` number, otherwise the last bare number. Code answers use the last fenced block. Unparseable output is invalid and counts as wrong.
- GSM8K-test indexes `0..119` from `results/cpu/gsm8k_test.jsonl`, each row's sha256, and the sha256 of that list. Only `arith_word` is compared with it. `code_output` and `graph_path` are fresh-only.
- The four Q8_0 GGUFs by file name, sha256, source URL, and the Phase 1 chat-template capture sha256 under `results/cpu/rendered/`.
- System prompt per family. The GSM8K reference uses the `arith_word` prompt.
- Runtime: llama.cpp `v0.7.0` commit `620d2225cc436ab0b001e3200e590e3b286ef9ab`, the C1 build flags, binary sha256, `-t 6 -tb 6 -b 2048 -ub 512`, seed 42, ctx 2048, `n_predict` 512 for `code_output` and 320 otherwise, temp 0, top-k 1, top-p 1, min-p 0, penalties 1/0/0, reasoning off, jinja on, prompt cache off (no `--prompt-cache` file).
- CPU model string and the cgroup limits of `sealedbench-p2.scope`.
- Reporting: every declared batch is reported; a batch whose manifest or ciphertext is not in an L1 block before the release round is invalid; a crashed run is re-executed once with the same settings and both logs are kept.
- Declared batches: `b1`, `cap`.

`b1` unlocks at 2026-10-18 09:00:00 UTC, round 33170212. `cap` unlocks at 2026-11-15 12:00:00 UTC, round 33980212. Both are exact quicknet boundaries. `cap` is not run in Phase 2. Both batches use 120 `arith_word`, 60 `code_output`, and 60 `graph_path` items.

Item ids are `{family}-{index:04d}` in family order `arith_word`, `code_output`, `graph_path`.
