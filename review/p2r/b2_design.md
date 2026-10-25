# b2 design — protocol `sealedbench/v2`

Committed before implementation. v1 modules stay on the b1 path. b2 and cap2 are new batches. They are not inside b1's sealed `declared_batches`.

## Rounds

`round = (unix - 1692803367) / 3 + 1`. Both targets are multiples of the 3 s period.

Checked 2026-10-17 against `https://api.drand.sh/<chain>/info` (genesis 1692803367, period 3) and `.../public/1000` (body `round` is 1000).

| batch | unlock | unix | round |
| --- | --- | --- | --- |
| b2 | 2026-10-19T00:00:00Z | 1792368000 | 33188212 |
| cap2 | 2026-11-15T12:00:00Z | 1794744000 | 33980212 |

cap (v1) and cap2 share a round and differ by ciphertext sha256.

## What v1 does not bind, and what v2 adds

Upload order is ciphertext, then the reference subset, then the manifest.

The manifest contains:

- `ciphertext.txid`, `ciphertext.sha256`, `ciphertext.bytes`
- `plaintext_tarball_sha256` and `plaintext_tarball_bytes`
- `grader.sha256` over the v2 grader sources
- `reference.sha256` and `reference.txid` of the uploaded subset (GSM8K-test indexes `0 .. n_ref-1`, question and gold only)
- `template_bank_sha256` of the canonical template-bank JSON, which is also a file inside the tarball
- `peer.batch_id` and `peer.ciphertext_sha256` (b2 names cap2 and the reverse)

Tags on every upload: `Protocol=sealedbench/v2`, `Batch`, `Drand-Chain`, `Drand-Round`, `Unlock-Unix`, `Unlock-UTC`, `Content-SHA256`, plus `Type`, `App-Name=SealedBench`, `App-Version=0.2.0`, `Content-Type`.

The in-tarball recipe hash from F01 is not used. The ciphertext hash exists only after encryption, and putting it inside the plaintext would require a second encryption. The manifest, uploaded after the ciphertext, is the binding.

## Seed

```text
enc(b) = uint32be(len(b)) || b

material = enc(utf8("sealedbench/v2"))
        || enc(utf8(lowercase chain-hash hex))
        || enc(utf8(decimal round, no sign, no leading zeros))
        || enc(signature bytes)
        || enc(batch secret, exactly 32 bytes)

seed = SHA-256(material)
```

`signature bytes` are the hex-decoded quicknet signature after `randomness == hex(SHA-256(signature))` and a BLS verify under the pinned key (`bls-unchained-g1-rfc9380`, DST `BLS_SIG_BLS12381G1_XMD:SHA-256_SSWU_RO_NUL_`, message `SHA-256(uint64be(round))`).

Family subseed:

```text
family_seed = SHA-256(
    enc(utf8("sealedbench/v2/family"))
 || enc(seed)
 || enc(utf8(family name))
 || enc(utf8(decimal n))
)
```

PRNG: SHA-256(key || uint64be(counter)), counter from 0, one block per draw, rejection sampling on the first 8 bytes. No `random` module. Canonical items: `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"`.

The batch secret is 32 bytes from `os.urandom`, stored only as `sealedbench/v2/batch_secret.bin` inside that batch's tarball and in `/root/sbw/p2r/secrets/` mode 0600. It is not committed. b2 and cap2 have different secrets.

The author knows the secret and the generator and does not know the beacon, so the author cannot list the items before the round. Publishing the repository after b1's unlock does not reveal b2 or cap2 items.

Test vectors use the published secret `bytes.fromhex("0123456789abcdef" * 4)` and three past quicknet rounds. Each vector records round, signature hex, seed hex, and the first three item ids at the b2 counts. They do not predict the sealed batches.

## Generator

Arith and graph reuse the v1 samplers (25 arith templates, parametric graphs) under the v2 subseed. Each item's `params.template_id` is the arith template name or `nodes-<count>`.

Code does not shell out. Eight templates render a small Python subset. An AST walker with a 10_000-step budget is the oracle. Exceeding the budget, an empty stdout, or an unsupported node rejects that candidate. Rejection does not depend on the clock or the load.

Diversity gate, 1000 seeds, test secret, run from the extracted sealed tarball:

- at least 999/1000 distinct question-set hashes
- arith pool ≥ 20; each 80-item draw uses ≥ 12 templates; max share ≤ 0.30
- code pool ≥ 8; each 30-item draw uses ≥ 6 templates; max share ≤ 0.40
- graph: each 30-item draw uses ≥ 3 distinct node counts

## Grading and the cap

Strict grader, separate from v1:

- arith, graph, gsm8k: last line matching `^####\s*(-?\d[\d,]*)\s*$` wins; no bare-number fallback; otherwise `invalid`
- code: last fenced block, trailing whitespace stripped per line; no fence is `invalid`
- primary accuracy counts invalid as wrong
- also report invalid rate and accuracy among parsed
- a completion with no `[end of text]`, or with generated runs ≥ n_predict − 1, is `truncated` and counts as invalid for the primary accuracy

Phase 1 at n_predict 320, 50 GSM8K items, `-t 6`: truncation (no EOS) was Qwen 5/50, Gemma 5/50, Ministral 2/50, Falcon 8/50, 20/200 in total. EOS maxima were 317, 314, 292, 318. That is not a ≤1% cap. b2 sets `n_predict` to 768 for arith, graph, and the reference, and 512 for code. The ≤1% rate at 768 was not measured, because the 20 long completions were censored at 320. ctx stays 2048: the longest Phase 1 prompt was 174 tokens, and 174 + 768 < 2048.

## Pre-registration

Primary endpoint: per model, per family, accuracy with invalid and truncated counted wrong.

Interval: Wilson 95% on each accuracy. For arith minus gsm8k, the Newcombe 1998 hybrid score interval.

Reported comparisons, and no others as headline results:

- the four families arith_word, code_output, graph_path, gsm8k (indexes 0..79)
- per-model Newcombe interval for arith minus gsm8k
- template id counts and a trivial baseline (uniform draw from the observed answer set; for graph, also the direct-edge weight when one exists)
- not a claim of contamination, and not a "matched" set

Minimum detectable effect, two-sided 95%, p≈0.5, independent items: Wilson half-width about 11 pp at n=80 and 18 pp at n=30. The arith-minus-gsm8k difference has a half-width of about 16 pp at n=80. Gaps inside that band are reported and not interpreted.

Invalid and no-show: one retry with the same flags, both logs kept. A partial model is published as partial and is not dropped. A batch is INVALID only when the verifier proves a committed bundle's L1 timestamp is greater than unlock − 600 s. A 404, a 429, or a missing observation is UNKNOWN. The author's node is never the sole inclusion witness.

## Budget

Measured t6_a wall means, which include process start, at the old cap: 34.202 + 30.078 + 19.307 + 14.508 = 98.095 s per item across four models.

Items per model: arith 80 + code 30 + graph 30 + reference 80 = 220.

At the measured mean: 220 × 98.095 = 21581 s = 6.00 h.

Allowance if the 10% that hit 320 tokens instead run to 768 (extra ≈ 448 tokens): 448/6.12 + 448/6.42 + 448/7.00 + 448/15.95 ≈ 235 s per long item, times 22 items = 5170 s = 1.44 h. Total ≈ 7.4 h. The 9 h line holds under that assumption. It was not checked by regenerating the censored tail.

## Runtime

Same GGUFs, same llama.cpp commit, `-t 6 -b 2048 -ub 512`, seed 42, temp 0, top-k 1, top-p 1, min-p 0, penalties 1/0/0, reasoning off, jinja on, prompt cache off. b2 also records sha256 of the `libllama` and `libggml` shared objects, because the 15968-byte executable is only the launcher.

## Pipeline

`tools/p2r_b2_pipeline.sh` waits for round 33188212 and for b1 (`/root/sbw/p2/DONE` or pid 3557323 gone), then release, generate, infer, replay 10 items in a fresh directory, score, upload within the 25-upload / 2 MiB phase cap, verify, commit, push, write `/root/sbw/p2r/B2_DONE`. Steps are skipped when their output hash is already recorded.
