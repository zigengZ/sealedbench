#!/usr/bin/env python3
"""Write results/cpu/summary.md from results/cpu/measurements.json."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path("/root/codes/sealedbench")
CPU = ROOT / "results" / "cpu"


def yn(flag: bool | None) -> str:
    if flag is True:
        return "Y"
    if flag is False:
        return "N"
    return ""


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


PROMPT_TPS_RE = re.compile(
    r"prompt eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*tokens\s*"
    r"\(\s*[\d.]+\s*ms per token,\s*([\d.]+) tokens per second\)"
)
GEN_TPS_RE = re.compile(
    r"eval time\s*=\s*([\d.]+)\s*ms\s*/\s*(\d+)\s*runs\s*"
    r"\(\s*[\d.]+\s*ms per token,\s*([\d.]+) tokens per second\)"
)


def timings_from_stderr(path: Path) -> tuple[float | None, float | None]:
    if not path.exists():
        return None, None
    prompt = gen = None
    for line in path.read_text(errors="replace").splitlines():
        if "prompt eval time" in line:
            match = PROMPT_TPS_RE.search(line)
            if match:
                prompt = float(match.group(3))
        elif "eval time" in line:
            match = GEN_TPS_RE.search(line)
            if match:
                gen = float(match.group(3))
    return prompt, gen


def overlay_speed(data: dict) -> None:
    """Fill tok/s from stderr. The in-run parser missed the spaced llama.cpp format."""
    for model in data.get("models", []):
        prompts = []
        gens = []
        run_dir = CPU / "runs" / model["id"] / "t6_a"
        if not run_dir.exists():
            continue
        for stderr in sorted(run_dir.glob("*.stderr")):
            prompt, gen = timings_from_stderr(stderr)
            if prompt is not None:
                prompts.append(prompt)
            if gen is not None:
                gens.append(gen)
        def median(xs: list[float]) -> float:
            xs = sorted(xs)
            n = len(xs)
            if n % 2:
                return xs[n // 2]
            return (xs[n // 2 - 1] + xs[n // 2]) / 2

        if prompts:
            model["prompt_tps_median"] = median(prompts)
            model["prompt_tps_min"] = min(prompts)
            model["prompt_tps_max"] = max(prompts)
        if gens:
            model["gen_tps_median"] = median(gens)
            model["gen_tps_min"] = min(gens)
            model["gen_tps_max"] = max(gens)


def overlay_context(data: dict) -> None:
    meta_path = CPU / "gguf_meta.json"
    if not meta_path.exists():
        return
    meta = json.loads(meta_path.read_text())
    by_file = {}
    for filename, info in meta.items():
        fields = info.get("meta", {})
        ctx = next((v for k, v in fields.items() if k.endswith("context_length") and "original" not in k), None)
        by_file[filename] = ctx
    for model in data.get("models", []):
        if model.get("n_ctx_train") is None and model.get("file") in by_file:
            model["n_ctx_train"] = by_file[model["file"]]


def main() -> None:
    path = CPU / "measurements.json"
    if not path.exists():
        raise SystemExit(f"missing {path}")
    data = json.loads(path.read_text())
    overlay_speed(data)
    overlay_context(data)
    lines = ["# CPU inference", ""]
    lines.append(
        "Byte-identical means the completion stdout bytes match. Stderr timings are not part of the comparison."
    )
    lines.append("")
    lines.append(
        f"Binary `{data.get('binary')}`. Seed {data.get('seed')}, ctx {data.get('ctx')}, "
        f"n_predict {data.get('n_predict')}, temp {data.get('temp')}, top_k {data.get('top_k')}, "
        f"top_p {data.get('top_p')}, min_p {data.get('min_p')}, repeat/presence/frequency penalties "
        f"{data.get('repeat_penalty')}/{data.get('presence_penalty')}/{data.get('frequency_penalty')}, "
        f"reasoning {data.get('reasoning')}, jinja {data.get('jinja')}, prompt cache {data.get('prompt_cache')}."
    )
    lines.append("")
    lines.append("System prompt:")
    lines.append("")
    lines.append("```")
    lines.append(data.get("system_prompt", ""))
    lines.append("```")
    lines.append("")
    extract = data.get("answer_extraction", {})
    lines.append("Answer extraction:")
    lines.append("")
    lines.append(f"- gold regex: `{extract.get('gold')}`")
    lines.append(f"- pred prefers last match of `{extract.get('pred_hash')}`")
    lines.append(f"- otherwise the last match of `{extract.get('pred_fallback')}`")
    lines.append(f"- {extract.get('normalize')}")
    lines.append("")
    lines.append(
        "Determinism columns: `t6 repeat` is a second `-t 6` run of the first 10 prompts against the first; "
        "`t4` is `-t 4`; `batch` is `-b 512 -ub 128` against the default `-b 2048 -ub 512`. "
        "tok/s is the median of the 50-item `-t 6` default-batch run."
    )
    lines.append("")
    lines.append(
        "| model | params | quant | sha256 | prompt tok/s | gen tok/s | det t6 repeat | det t4 | det batch | gsm8k@50 | hit cap | n_ctx_train |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for model in data.get("models", []):
        det = model.get("determinism", {})
        gsm = ""
        if model.get("gsm8k_n"):
            gsm = f"{model.get('gsm8k_correct')}/{model.get('gsm8k_n')}"
        lines.append(
            "| {id} | {params} | {quant} | `{sha}` | {pt} | {gt} | {a} | {b} | {c} | {gsm} | {hit} | {ctx} |".format(
                id=model.get("id"),
                params=model.get("params"),
                quant=model.get("quant"),
                sha=model.get("sha256"),
                pt=fmt(model.get("prompt_tps_median")),
                gt=fmt(model.get("gen_tps_median")),
                a=yn(det.get("t6_repeat", {}).get("identical")),
                b=yn(det.get("threads_4", {}).get("identical")),
                c=yn(det.get("batch", {}).get("identical")),
                gsm=gsm,
                hit=fmt(model.get("hit_cap")),
                ctx=fmt(model.get("n_ctx_train")),
            )
        )
    lines += ["", "## Rendered prompts", ""]
    lines.append(
        "One capture per model used the same chat template path (`--jinja`, `-sys`, `-p`) with `--verbosity 5`. "
        "The string is the debug `prompt:` value, which is the template output that was tokenized. "
        "Files: `results/cpu/rendered/<model>.txt`."
    )
    lines.append("")
    for model in data.get("models", []):
        lines.append(
            f"- `{model.get('id')}` sha256 `{model.get('rendered_prompt_sha256')}` bytes {model.get('rendered_prompt_bytes')}"
        )
    lines += ["", "## Notes", ""]
    lines.append(
        "A determinism cell is N when any of the 10 completion stdouts differ, including a missing run. "
        "Mismatched indexes are in `results/cpu/measurements.json`."
    )
    lines.append("")
    lines.append(
        "The sampler chain ends in greedy when `--temp 0`. llama.cpp then prints "
        "`sampler seed: 4294967295` (`LLAMA_DEFAULT_SEED`) because the greedy sampler has no RNG. "
        "The process is still started with `--seed 42`. Greedy selection does not consult that seed."
    )
    lines.append("")
    lines.append(
        "Rates are the median of the 50-item `-t 6` run inside cgroup `sealedbench-p1.scope` "
        "(`cpu.max` 600000/100000, about 6 CPUs). No item hit the 320-token cap."
    )
    lines.append("")
    lines.append("Byte mismatches, from `measurements.json`:")
    lines.append("")
    lines.append(
        "- Qwen3, `-t 4` items 4 and 7, and batch items 4 and 8. The extracted final number still matched the `-t 6` run and the gold answer on those four."
    )
    lines.append(
        "- Gemma 3, batch item 4. The extracted number was the same wrong value (760) in both runs; the stdout bytes differed."
    )
    lines.append(
        "- Falcon3, batch items 4 and 8. The extracted numbers differed (100 vs 800, and 4 vs 340)."
    )
    lines.append(
        "- Ministral 3 was byte-identical on all three comparisons. Every model was byte-identical on the repeated `-t 6` run."
    )
    lines.append("")
    (CPU / "summary.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {CPU / 'summary.md'}")


if __name__ == "__main__":
    main()
