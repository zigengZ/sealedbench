# cap manifest

Protocol `sealedbench/v1`. Unlock 2026-11-15T12:00:00Z at round 33980212.

Seed rule, verbatim:

```
seed_hex = SHA-256( "sealedbench/v1" || chain_hash_hex || ascii(round) || randomness_hex )
```

chain_hash_hex and randomness_hex are stripped and lowercased. ascii(round) is the decimal round with no sign and no leading zeros. The four pieces are concatenated as ASCII. seed_bytes is the raw 32-byte SHA-256 digest.

Chain `52db9ba70e0cc0f6eaf7803dd07447a1f5477735fd3f661792ba94600c84e971` scheme `bls-unchained-g1-rfc9380`.
Public key `83cf0f2896adee7eb8b5f01fcad3912212c437e0073e911fb90022d3e760183c8c4b450b6a0a6c3ac6a5776a2d1064510d1fec758c921cc22b0e17e63aaf4bcb5ed66304de9cf809bd274ca73bab4af5a6e9c76a4bc09e76eae8991ef5ece45a`.

Generator commit `95f747f0efd5b24bc507a3c7082bc74ac18f75ed`.
Generator sha256 `e054f1ab7824fde33e6ac399252098cf25c29815ff4ffacabbd311da05eac9c2` (11171 bytes).
Ciphertext sha256 `ae58d4306691970ce34394e85a413a39bf3fd46374eed53b9f1b0ca369b7068c` (15685 bytes).
Families: arith_word=120, code_output=60, graph_path=60.

Families run in the order arith_word, code_output, graph_path. item_id is '{family}-{index:04d}' starting at 0 inside the family. family_seed = SHA-256(ASCII('sealedbench/v1/family\n') || seed_bytes || ASCII('\n') || ASCII(family) || ASCII('\n') || ASCII(n)), where seed_bytes is the raw 32-byte digest from the seed rule. Candidates are drawn in RNG order and rejected when they are degenerate (integer answer 0, empty program output, a one-edge shortest path), when the prompt was already kept, or when a program errors or times out. The first n accepted candidates form the family.

Grader sha256 `2075763a8194cd90bb98560f88ac7f84089c17fb6133919a610523d793ed46fe`.

Extraction regexes:

- `integer_hash`: `####\s*(-?\d[\d,]*(?:\.\d+)?)`
- `integer_bare_fallback`: `-?\d[\d,]*(?:\.\d+)?`
- `gsm8k_gold`: `####\s*(-?\d[\d,]*)`
- `code_fence`: ````[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)````

Reference list sha256 `e25d897c56f446b2a097f4ee7b51fc0935d03a881bb6b0cc0ab603c083c02a15` over GSM8K-test indexes 0..119.
Source file sha256 `3730d312f6e3440559ace48831e51066acaca737f6eabec99bccb9e4b3c39d14`.

Models:

| id | sha256 | chat-template capture |
| --- | --- | --- |
| qwen3-4b-instruct-2507 | `ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1` | `d013fd0cbe6c4319a336769fd8acc21f8755181f69ec9025ed6fca704bd58070` |
| gemma-3-4b-it | `97b06383df48336e7d2f9b56b6ce545e0fa476407a62c0bd081b53447a58e644` | `b617e4f52945baccc027e9232c10ffb2f57b866b7f1d463ad8b852cea5dc306a` |
| ministral-3-3b-instruct-2512 | `70c6e5b77435062a46bfa3f0b9fa21744a10161ed23eabe9fdc47b3fb6711ad3` | `93b2d2a1cc8c05535b20d31bb22a440115eb055e77eb366d7d1aed861a270977` |
| falcon3-1b-instruct | `dda44709157103fc272ea3c44ae0deb7fbec5b2d82b313362680dec08e66f57a` | `227fa354934a1cda4f3181000d6354842ffac5e31db80bba866e391148074a64` |

llama.cpp `v0.7.0` `620d2225cc436ab0b001e3200e590e3b286ef9ab`.
Binary sha256 `d95bb69be967034fa5414b708a75e8119946ecbdb34404363111d2ee20cd5eb7`.
Flags: -t 6 -tb 6 -b 2048 -ub 512, seed 42, ctx 2048, n_predict default 320 and code_output 512, temp 0, top-k 1, top-p 1, min-p 0, penalties 1/0/0, reasoning off, jinja True, prompt cache False.

Host `AMD Ryzen 7 7700 8-Core Processor` cgroup `sealedbench-p2.scope` cpu.max `600000 100000` memory.max `19327352832`.

A batch whose manifest or ciphertext is not in an L1 block before the release round is invalid and is reported as such.
none. A crashed run is re-executed once with identical settings and both logs are kept.

Declared batches: b1, cap.
