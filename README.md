# SealedBench

SealedBench seals an exam generator to a future [drand quicknet](https://drand.love) round and stores the ciphertext on Arweave. After the round, anyone can rebuild the questions and re-check the published scores. The models and the scoring rules are frozen before that round.

This repository holds three released batches, b1, b2, and b3, and three capsules that stay sealed until 2026-11-15. b1 uses protocol `sealedbench/v1`. b2, b3, and the later capsules use `sealedbench/v2`. v1's ciphertext transaction binding is weak: a missing ciphertext id is not a pass. b2's registered grader rejects llama.cpp's trailing end marker, so its registered integer and GSM8K scores are about zero. A post-hoc normalization exists and is labeled post-hoc. The seal does not allow that grader to be replaced in place. b3 uses the corrected grader `sealedbench/v2/grade_b3.py` as the registered grade.

**Disclosure:** AI coding agents (Claude, Grok, OpenAI Codex, Cursor) wrote the code and tests under the author's direction. The author set the batches, unlock rounds, and the rule that registered scores stay distinct from post-hoc scores.

## Quick start

Python 3.12, Node.js 22, and the `tle` binary at version 1.2.0. The Python scripts use the standard library only. `npm ci` installs `tlock-js` 0.9.0, which the verifier uses for a second decrypt. A replay also needs the frozen `llama-completion` binary and the model file named in the manifest.

```bash
git clone https://github.com/zigengZ/sealedbench.git
cd sealedbench
python3 -m venv .venv
. .venv/bin/activate
npm ci
```

If `node` is older than 22, or `tle` is not on `PATH`, and you already built the tools into the default cache:

```bash
export PATH="$HOME/.cache/sealedbench/node/current/bin:$HOME/.cache/sealedbench/gopath/bin:$PATH"
```

`tle` is read from `$TLE` or `$HOME/.cache/sealedbench/gopath/bin/tle`. Leave `SEALEDBENCH_ROOT` unset. The code then uses this checkout.

Check b3. The txid is the published index. Exit 0 is PASS, 1 is FAIL, 2 is UNKNOWN. HTTP 404, 429, and timeouts are UNKNOWN. This command reads gateways. It does not upload.

```bash
python3 -m sealedbench verify --batch b3 --txid vlVlUfyBn4IUmbXjkSX8079QuySP-Qqr8rN8TbivzTg
```

The command prints the result. An existing `results/batches/<batch>/verify_seal.txt` is left unchanged.

v2 checks `https://ar-io.dev` and `https://turbo-gateway.com`. Those two have to agree. `https://arweave.net` is not used for a v2 check. Re-run the first five b3 items for one model, with the manifest's llama.cpp settings:

```bash
python3 -m sealedbench replay --batch b3 --model qwen3-4b-instruct-2507 --items 5
```

b1 is v1. Pass its index txid from the table below. A v1 result of WEAK means the ciphertext transaction id is not bound.

## Batches

| Batch | Protocol | Unlock (UTC) | drand round | Index or ciphertext |
| --- | --- | --- | --- | --- |
| b1 | v1 | 2026-10-18 09:00 | 33170212 | index `AtNAZQtp_JqReahCoCpYcjP-b3P98jWtC_AJgVoBWdM` |
| b2 | v2 | 2026-10-19 00:00 | 33188212 | index `OhlaaBEIuQrtAu_FvJz1zAvHknpHFMXktWO0iFleidU` |
| b3 | v2 | 2026-10-19 12:00 | 33202612 | index `vlVlUfyBn4IUmbXjkSX8079QuySP-Qqr8rN8TbivzTg` |
| cap | v1 | 2026-11-15 12:00 | 33980212 | ciphertext `q5O5v8XwkxCJkAyuZHd9V1pBV6XCWEtmCU5_2bactb0` |
| cap2 | v2 | 2026-11-15 12:00 | 33980212 | ciphertext `dLSRuUQDZV8aXut9v0faXVwQjvIdw-juKlCWbOyK-qo` |
| cap3 | v2 | 2026-11-15 12:00 | 33980212 | ciphertext `QUTZFXr03mYfwJ51wlrrxztLgL6VSbhQDZwMvI8YS9U` |

cap, cap2, and cap3 are still sealed. Do not decrypt them before the round. Their plaintext is not in this repository.

Question-set ids, score files, and completion archives are under `results/batches/<batch>/`. b2's `scores.json` has a block named `posthoc_sentinel_normalization`. That block is not the registered score.

## Development commit 95f747f

b1 and cap were sealed against development-repository commit `95f747f0efd5b24bc507a3c7082bc74ac18f75ed`. This public repository starts a new history, so that commit object is not present here. The code content at seal time is under `snapshots/95f747f0efd5b24bc507a3c7082bc74ac18f75ed/`, with git tree and blob hashes that anyone can recompute from the files. See that directory's README.

## Figures

Article figures and the drawing script live under `article/fig/` (`make_figs.py`). Run with no network:

```bash
python3 article/fig/make_figs.py
```

## Method notes

`MANIFEST.md` explains the seed rule and what a manifest fixes. Per-batch files are under `results/batches/<id>/`.

## License

[ISC](LICENSE). Copyright (c) 2026 Zigza. `package.json` declares `ISC`.
