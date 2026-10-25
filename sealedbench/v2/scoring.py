"""Score a v2 batch. Primary accuracy counts invalid and truncated as wrong."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from sealedbench.infer import batch_dir, load_manifest, _v2_reference
from sealedbench.paths import repo_root
from sealedbench.v2.grade import grade_answer, is_truncated
from sealedbench.v2.grade_b3 import grade_answer as grade_normalized
from sealedbench.v2.spec import canon
from sealedbench.v2.stats import newcombe, wilson

RUNS_RE = re.compile(r"eval time\s*=\s*[0-9.]+ ms\s*/\s*(\d+) runs")


def _read(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _runs(stderr: str | None) -> int | None:
    if not stderr:
        return None
    match = RUNS_RE.search(stderr)
    return int(match.group(1)) if match else None


def _block(grades: list) -> dict:
    n = len(grades)
    correct = sum(1 for grade in grades if grade.correct)
    invalid = sum(1 for grade in grades if grade.invalid)
    truncated = sum(1 for grade in grades if grade.truncated)
    parsed = sum(1 for grade in grades if grade.parsed is not None and not grade.truncated and not grade.invalid)
    lo, hi = wilson(correct, n)
    among = correct / parsed if parsed else None
    return {
        "n": n,
        "correct": correct,
        "invalid": invalid,
        "truncated": truncated,
        "parsed": parsed,
        "accuracy": correct / n if n else None,
        "invalid_rate": invalid / n if n else None,
        "truncated_rate": truncated / n if n else None,
        "accuracy_among_parsed": among,
        "wilson95": [lo, hi],
    }


def _baseline(items: list[dict]) -> dict:
    answers = {str(item["oracle_answer"]) for item in items}
    return {
        "distinct_observed_answers": len(answers),
        "uniform_over_observed_answers": 1 / len(answers) if answers else None,
    }


def _completion(base: Path, item_id: str, n_predict: int):
    stdout_path = base / f"{item_id}.txt"
    raw = _read(stdout_path)
    raw_bytes = stdout_path.read_bytes() if stdout_path.exists() else None
    stderr = _read(base / f"{item_id}.stderr")
    meta_text = _read(base / f"{item_id}.json")
    try:
        meta = json.loads(meta_text) if meta_text else {}
    except ValueError:
        meta = {}
    missing = raw is None or meta.get("returncode") != 0
    # Truncation stays on the raw decoded stdout. Normalization must not run first:
    # stripping the sentinel would make every finished completion look truncated.
    truncated = raw is None or is_truncated(raw, _runs(stderr), n_predict)
    return raw or "", raw_bytes, truncated, missing


def _registered_normalized(manifest: dict) -> bool:
    files = (manifest.get("grader") or {}).get("files") or []
    return "sealedbench/v2/grade_b3.py" in files


def _apply_grade(normalized: bool, family: str, oracle: str, raw_text: str, raw_bytes: bytes | None, truncated: bool, missing: bool):
    if missing:
        payload: str | bytes = ""
    elif normalized:
        payload = raw_bytes if raw_bytes is not None else raw_text
    else:
        payload = raw_text
    grader = grade_normalized if normalized else grade_answer
    return grader(family, oracle, payload, truncated=truncated)


def _graph_direct(items: list[dict]) -> dict | None:
    if not items or items[0]["family"] != "graph_path":
        return None
    have = 0
    equal = 0
    for item in items:
        params = item["params"]
        direct = None
        for edge in params.get("edges", []):
            if {edge[0], edge[1]} == {params.get("src"), params.get("dst")}:
                direct = edge[2]
        if direct is None:
            continue
        have += 1
        if str(direct) == str(item["oracle_answer"]):
            equal += 1
    return {"items_with_direct_edge": have, "direct_edge_equals_answer": equal}


def calculate_scores(batch: str) -> dict:
    root = repo_root()
    manifest = load_manifest(batch)
    if manifest.get("protocol_version") != "sealedbench/v2":
        raise SystemExit("score_batch_v2 requires sealedbench/v2")
    directory = batch_dir(batch)
    items = [json.loads(line) for line in (directory / "items.jsonl").read_text().splitlines() if line.strip()]
    expected = {row["name"]: int(row["n"]) for row in manifest["generator"]["families"]}
    actual = Counter(item["family"] for item in items)
    if any(actual.get(name, 0) != n for name, n in expected.items()) or set(actual) - set(expected):
        raise ValueError("item counts disagree with the manifest; refusing to trim the endpoint")
    if len({item["item_id"] for item in items}) != len(items):
        raise ValueError("duplicate item ids")
    reference = _v2_reference(manifest, batch)
    if len(reference) != int(manifest["reference"]["n"]):
        raise ValueError("reference count disagrees with the manifest")
    release = {}
    if (directory / "release.json").exists():
        release = json.loads((directory / "release.json").read_text())
        from sealedbench.items import loads_jsonl, question_set_sha256
        if release.get("question_set_sha256") != question_set_sha256(loads_jsonl((directory / "items.jsonl").read_bytes())):
            raise ValueError("question-set hash disagrees with release")
    normalized = _registered_normalized(manifest)
    per_model = {}
    posthoc_models = {}
    for model in manifest["models"]:
        families = {}
        post_families = {}
        missing_total = 0
        for family in ("arith_word", "code_output", "graph_path"):
            grades = []
            post_grades = []
            missing_count = 0
            family_items = [item for item in items if item["family"] == family]
            n_predict = int(manifest["runtime"]["n_predict"].get(family, manifest["runtime"]["n_predict"]["default"]))
            for item in family_items:
                raw, raw_bytes, truncated, missing = _completion(directory / "runs" / model["id"], item["item_id"], n_predict)
                missing_count += int(missing)
                grades.append(_apply_grade(normalized, family, item["oracle_answer"], raw, raw_bytes, truncated, missing))
                if not normalized:
                    post_grades.append(_apply_grade(True, family, item["oracle_answer"], raw, raw_bytes, truncated, missing))
            families[family] = _block(grades)
            families[family]["no_show_or_failed"] = missing_count
            missing_total += missing_count
            families[family]["baseline"] = _baseline(family_items)
            families[family]["templates"] = dict(Counter(item["params"].get("template_id", "?") for item in family_items))
            direct = _graph_direct(family_items)
            if direct:
                families[family]["direct_edge_baseline"] = direct
            if not normalized:
                post_families[family] = _block(post_grades)
        gsm = []
        post_gsm = []
        n_predict = int(manifest["runtime"]["n_predict"]["gsm8k"])
        missing_count = 0
        for row in reference:
            raw, raw_bytes, truncated, missing = _completion(directory / "reference_runs" / model["id"], row["item_id"], n_predict)
            missing_count += int(missing)
            gsm.append(_apply_grade(normalized, "gsm8k", row["oracle_answer"], raw, raw_bytes, truncated, missing))
            if not normalized:
                post_gsm.append(_apply_grade(True, "gsm8k", row["oracle_answer"], raw, raw_bytes, truncated, missing))
        gsm_block = _block(gsm)
        gsm_block["no_show_or_failed"] = missing_count
        missing_total += missing_count
        diff, lo, hi = newcombe(
            families["arith_word"]["correct"],
            families["arith_word"]["n"],
            gsm_block["correct"],
            gsm_block["n"],
        )
        per_model[model["id"]] = {
            "status": "PARTIAL" if missing_total else "COMPLETE",
            "no_show_or_failed": missing_total,
            "families": families,
            "gsm8k": gsm_block,
            "arith_minus_gsm8k": {"diff": diff, "newcombe95": [lo, hi]},
        }
        if not normalized:
            post_gsm_block = _block(post_gsm)
            post_diff, post_lo, post_hi = newcombe(
                post_families["arith_word"]["correct"],
                post_families["arith_word"]["n"],
                post_gsm_block["correct"],
                post_gsm_block["n"],
            )
            posthoc_models[model["id"]] = {
                "families": post_families,
                "gsm8k": post_gsm_block,
                "arith_minus_gsm8k": {"diff": post_diff, "newcombe95": [post_lo, post_hi]},
            }
    scores = {
        "protocol_version": "sealedbench/v2",
        "batch_id": batch,
        "batch_valid": release.get("batch_valid"),
        "question_set_sha256": release.get("question_set_sha256"),
        "primary_endpoint": manifest["reporting"]["primary_endpoint"],
        "models": per_model,
    }
    if not normalized:
        scores["posthoc_sentinel_normalization"] = {
            "label": "POST-HOC",
            "registered_primary": False,
            "method": (
                "Same items, same truncation rule on the raw stdout, with the b3 grader-input "
                "normalization from sealedbench/v2/grade_b3.py applied before the registered "
                "integer and code rules. Not the registered primary endpoint."
            ),
            "models": posthoc_models,
        }
    return scores


def score_batch(batch: str) -> int:
    directory = batch_dir(batch)
    scores = calculate_scores(batch)
    per_model = scores["models"]
    (directory / "scores.json").write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n")
    lines = [f"# {batch}", "", canon({"batch_valid": scores["batch_valid"]}), ""]
    for model, row in per_model.items():
        lines.append(f"## {model} ({row['status']})")
        for name, block in {**row["families"], "gsm8k": row["gsm8k"]}.items():
            acc = block["accuracy"]
            lines.append(
                f"- {name}: n={block['n']} correct={block['correct']} invalid={block['invalid']} "
                f"truncated={block['truncated']} accuracy={None if acc is None else round(acc, 4)} "
                f"among_parsed={block['accuracy_among_parsed']}"
            )
        gap = row["arith_minus_gsm8k"]
        lines.append(f"- arith minus gsm8k: {gap['diff']} newcombe95={gap['newcombe95']}")
        lines.append("")
    posthoc = scores.get("posthoc_sentinel_normalization")
    if posthoc:
        lines.append("# POST-HOC sentinel normalization")
        lines.append("")
        lines.append("Not the registered primary endpoint. The registered scores above are unchanged.")
        lines.append(posthoc["method"])
        lines.append("")
        for model, row in posthoc["models"].items():
            lines.append(f"## POST-HOC {model}")
            for name, block in {**row["families"], "gsm8k": row["gsm8k"]}.items():
                acc = block["accuracy"]
                lines.append(
                    f"- {name}: n={block['n']} correct={block['correct']} invalid={block['invalid']} "
                    f"truncated={block['truncated']} accuracy={None if acc is None else round(acc, 4)} "
                    f"among_parsed={block['accuracy_among_parsed']}"
                )
            gap = row["arith_minus_gsm8k"]
            lines.append(f"- arith minus gsm8k: {gap['diff']} newcombe95={gap['newcombe95']}")
            lines.append("")
    (directory / "scores.md").write_text("\n".join(lines))
    print(f"SCORED {batch}")
    return 0
