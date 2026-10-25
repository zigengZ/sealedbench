# b3 design

b3 is the sealedbench/v2 batch with b2's generator, counts, models, decoding flags, and seed rule. It changes the grader input, the batch id, the secret, and the unlock. cap3 is the same correction for cap2.

## Round

`round = (unix − 1692803367) / 3 + 1`. Checked 2026-10-18 against `https://api.drand.sh/<chain>/info` (genesis 1692803367, period 3, scheme `bls-unchained-g1-rfc9380`) and `.../public/1000` (body `round` is 1000). Both targets are on a 3-second boundary.

| batch | unlock | unix | round |
| --- | --- | --- | --- |
| b3 | 2026-10-19T12:00:00Z | 1792411200 | 33202612 |
| cap3 | 2026-11-15T12:00:00Z | 1794744000 | 33980212 |

## Grader input

`sealedbench/v2/grade.py` is byte-identical to the b2 seal. Its hash over the registered file list remains `98b796af643192968126a5895561ec1d4701c71ccf9af76ae874fe1f0b3b0648`. b3 pins `sealedbench/v2/grade.py` and `sealedbench/v2/grade_b3.py`.

The text that is graded is the raw stdout after this procedure, which is copied byte-for-byte into `grader.input_normalization`:

1. Let B be the raw stdout bytes.
2. S = B.rstrip(), using Python `bytes.rstrip()` with no argument (ASCII whitespace 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x20).
3. If S ends with the 13 bytes `5b 65 6e 64 20 6f 66 20 74 65 78 74 5d` (`[end of text]`), set S = S[:-13] once.
4. S = S.rstrip() again.
5. Decode S as UTF-8, replacing invalid sequences.
6. Apply b2's integer rule and b2's code rule to that text.

Truncation is unchanged. It is decided on the raw stdout before this procedure: the marker is absent, or the llama.cpp run count is at least `n_predict - 1`.

The manifest declares b2 ciphertext `a7911be4af063978284e703f6f64cf21378531e27d7cdff6c8665ea8ad9b8bc9` and cap2 ciphertext `39d0d1145a0521285d7125dbb394f13a8f4ec917e60c3129445b0a3ee04776ef`, and states that b3 corrects the grader-input bug found on rehearsal b2r before b1 unlocked at 2026-10-18T09:00:00Z. b2 and cap2 stay sealed.

## n_predict

Kept at the b2 caps: 768 for arith_word, graph_path, gsm8k, and the default; 512 for code_output.

b2r, same flags, `-t 6`, 8 completions per family:

| family | mean generated tokens | max | at 767 runs |
| --- | --- | --- | --- |
| arith_word | 169.75 | 546 | 0 |
| code_output | 193.5 | 333 | 0 |
| graph_path | 542.25 | 767 | 3 |
| gsm8k | 89.875 | 205 | 0 |

Measured generation speeds on those completions, tokens divided by llama.cpp eval seconds: Qwen 5.4294/s, Gemma 5.1399/s, Ministral 5.9481/s, Falcon 15.4910/s. Per-item startup (wall minus eval) was 4.43 s, 4.52 s, 3.88 s, and 2.00 s.

Full b3 is 80 + 30 + 30 + 80 = 220 completions per model. Expected tokens per model at the rehearsal means:

`80*169.75 + 30*193.5 + 30*542.25 + 80*89.875 = 42842.5`.

Generation time across four models: `42842.5/5.4294 + 42842.5/5.1399 + 42842.5/5.9481 + 42842.5/15.4910 = 26194 s = 7.276 h`. Startup: `220 * (4.43 + 4.52 + 3.88 + 2.00) = 3262 s = 0.906 h`. Total `8.183 h`.

That extrapolation is eight samples per family from one public test seed. It sits about 11 minutes over the 8 hour line because the completions are that long, not because the cap is above them. The completed maxima are 546, 333, 748, and 205. Lowering a cap enough to save those 11 minutes would cut a completion the rehearsal already finished.

Giving the censored graph tail another 256 tokens, on the observed 3/8 of 30 graph items per model, adds `30*(3/8)*256` tokens per model and `0.489 h` across the four speeds. `8.183 + 0.489 = 8.672 h`, past the budget, and the residual length is unknown because those runs stopped at 767. The longest b2r prompt was 162 tokens, so 162 + 768 is inside ctx 2048.

The caps therefore stay 768/512.

## Everything else

Counts, reference indexes `0..79`, models, llama.cpp flags, seed rule, and the inclusion rule match b2. The batch secret is a new 32 bytes from `os.urandom`, mode 0600, path `/root/sbw/p2r/secrets/b3.bin`, and it is not committed. cap3 has its own secret. The generator sources match the b2 seal commit `e6b8795`, so the published 1000-seed diversity gate is not rerun. Upload order for b3 is ciphertext, reference, manifest. The pipeline waits for round 33202612 and for the b2 pipeline to finish before any llama.cpp.
