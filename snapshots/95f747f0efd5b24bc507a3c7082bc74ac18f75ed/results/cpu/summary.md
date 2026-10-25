# CPU inference

Byte-identical means the completion stdout bytes match. Stderr timings are not part of the comparison.

Binary `/root/.cache/sealedbench/llama.cpp/build/bin/llama-completion`. Seed 42, ctx 2048, n_predict 320, temp 0, top_k 1, top_p 1, min_p 0, repeat/presence/frequency penalties 1/0/0, reasoning off, jinja True, prompt cache False.

System prompt:

```
Solve the grade-school math problem. Show brief reasoning, then end with a line exactly of the form #### <integer> and nothing after it.
```

Answer extraction:

- gold regex: `####\s*(-?\d[\d,]*)`
- pred prefers last match of `####\s*(-?\d[\d,]*(?:\.\d+)?)`
- otherwise the last match of `-?\d[\d,]*(?:\.\d+)?`
- strip commas; strip a trailing .0; exact string match

Determinism columns: `t6 repeat` is a second `-t 6` run of the first 10 prompts against the first; `t4` is `-t 4`; `batch` is `-b 512 -ub 128` against the default `-b 2048 -ub 512`. tok/s is the median of the 50-item `-t 6` default-batch run.

| model | params | quant | sha256 | prompt tok/s | gen tok/s | det t6 repeat | det t4 | det batch | gsm8k@50 | hit cap | n_ctx_train |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qwen3-4b-instruct-2507 | 4B | Q8_0 | `ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1` | 41.72 | 6.12 | Y | N | N | 46/50 | 0 | 262144 |
| gemma-3-4b-it | 4B | Q8_0 | `97b06383df48336e7d2f9b56b6ce545e0fa476407a62c0bd081b53447a58e644` | 48.75 | 6.42 | Y | Y | N | 41/50 | 0 | 131072 |
| ministral-3-3b-instruct-2512 | 3B | Q8_0 | `70c6e5b77435062a46bfa3f0b9fa21744a10161ed23eabe9fdc47b3fb6711ad3` | 49.44 | 7.00 | Y | Y | Y | 39/50 | 0 | 262144 |
| falcon3-1b-instruct | 1B | Q8_0 | `dda44709157103fc272ea3c44ae0deb7fbec5b2d82b313362680dec08e66f57a` | 120.38 | 15.95 | Y | Y | N | 19/50 | 0 | 8192 |

## Rendered prompts

One capture per model used the same chat template path (`--jinja`, `-sys`, `-p`) with `--verbosity 5`. The string is the debug `prompt:` value, which is the template output that was tokenized. Files: `results/cpu/rendered/<model>.txt`.

- `qwen3-4b-instruct-2507` sha256 `d013fd0cbe6c4319a336769fd8acc21f8755181f69ec9025ed6fca704bd58070` bytes 498
- `gemma-3-4b-it` sha256 `b617e4f52945baccc027e9232c10ffb2f57b866b7f1d463ad8b852cea5dc306a` bytes 475
- `ministral-3-3b-instruct-2512` sha256 `93b2d2a1cc8c05535b20d31bb22a440115eb055e77eb366d7d1aed861a270977` bytes 462
- `falcon3-1b-instruct` sha256 `227fa354934a1cda4f3181000d6354842ffac5e31db80bba866e391148074a64` bytes 454

## Notes

A determinism cell is N when any of the 10 completion stdouts differ, including a missing run. Mismatched indexes are in `results/cpu/measurements.json`.

The sampler chain ends in greedy when `--temp 0`. llama.cpp then prints `sampler seed: 4294967295` (`LLAMA_DEFAULT_SEED`) because the greedy sampler has no RNG. The process is still started with `--seed 42`. Greedy selection does not consult that seed.

Rates are the median of the 50-item `-t 6` run inside cgroup `sealedbench-p1.scope` (`cpu.max` 600000/100000, about 6 CPUs). No item hit the 320-token cap.

Byte mismatches, from `measurements.json`:

- Qwen3, `-t 4` items 4 and 7, and batch items 4 and 8. The extracted final number still matched the `-t 6` run and the gold answer on those four.
- Gemma 3, batch item 4. The extracted number was the same wrong value (760) in both runs; the stdout bytes differed.
- Falcon3, batch items 4 and 8. The extracted numbers differed (100 vs 800, and 4 vs 340).
- Ministral 3 was byte-identical on all three comparisons. Every model was byte-identical on the repeated `-t 6` run.

