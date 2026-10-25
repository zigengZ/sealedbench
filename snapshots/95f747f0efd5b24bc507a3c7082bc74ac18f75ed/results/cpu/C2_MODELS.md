# C2 — candidate models

Rule: 1–4B instruct models with an official GGUF Q8_0 from the model's own org or from ggml-org. At most four families. Files live in `/root/.cache/sealedbench/models/` and are not committed. Total size 13,841,020,256 bytes (12.89 GiB), under 15 GB.

sha256 below matches both the Hugging Face LFS oid and a local `sha256sum` on 2026-10-17. GGUF `general.file_type` is 7 (Q8_0). Context length is the GGUF `{arch}.context_length`.

| model | params | quant | license | context | release | sha256 | source |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Qwen3-4B-Instruct-2507 | 4B | Q8_0 | apache-2.0 | 262144 | base repo created 2025-08-05; GGUF from ggml-org | `ae916ede1c010a26955ee8ae2e908bf8815a3f135ec860439ab924701c69d5f1` | `https://huggingface.co/ggml-org/Qwen3-4B-Instruct-2507-Q8_0-GGUF` file `qwen3-4b-instruct-2507-q8_0.gguf` (4,280,403,520 bytes) |
| Gemma 3 4B IT | 4B | Q8_0 | gemma | 131072 | `google/gemma-3-4b-it` created 2025-02-20; Q8_0 from ggml-org | `97b06383df48336e7d2f9b56b6ce545e0fa476407a62c0bd081b53447a58e644` | `https://huggingface.co/ggml-org/gemma-3-4b-it-GGUF` file `gemma-3-4b-it-Q8_0.gguf` (4,130,226,336 bytes). Text file only. |
| Ministral 3 3B Instruct 2512 | 3.4B label | Q8_0 | apache-2.0 | 262144 (rope original 16384) | `mistralai/Ministral-3-3B-Instruct-2512` created 2025-10-31 | `70c6e5b77435062a46bfa3f0b9fa21744a10161ed23eabe9fdc47b3fb6711ad3` | `https://huggingface.co/ggml-org/Ministral-3-3B-Instruct-2512-GGUF` file `Ministral-3-3B-Instruct-2512-Q8_0.gguf` (3,651,679,744 bytes). Text file only. |
| Falcon3 1B Instruct | 1B | Q8_0 | other (falcon-llm-license) | 8192 | `tiiuae/Falcon3-1B-Instruct` created 2024-12-14 | `dda44709157103fc272ea3c44ae0deb7fbec5b2d82b313362680dec08e66f57a` | `https://huggingface.co/tiiuae/Falcon3-1B-Instruct-GGUF` file `Falcon3-1B-Instruct-q8_0.gguf` (1,778,710,656 bytes). The model's own org. |

Header fields read from the GGUF metadata are in `results/cpu/gguf_meta.json`.

## Not downloaded

- Llama-3.2-3B-Instruct Q8_0 is published by third parties, not by Meta or ggml-org.
- `microsoft/Phi-3-mini-4k-instruct-gguf` has fp16 and Q4, not Q8_0.
- `microsoft/phi-4-gguf` Q8_0 is about 15.6 GB and about 14B parameters.
- SmolLM2's official GGUF is Q4_K_M. `HuggingFaceTB/smollm-1.7B-instruct-v0.2-Q8_0-GGUF` is an older add-basics variant, not SmolLM2.
- Qwen2.5-3B has an official Q8_0 and was skipped so the set would not contain two Qwen generations.
- Falcon-H1-0.5B is under 1B parameters.
