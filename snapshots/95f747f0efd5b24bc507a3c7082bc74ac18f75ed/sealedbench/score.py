"""Score a released batch and write scores.json, scores.md, and the completion archive."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

from sealedbench.grade import grade_answer
from sealedbench.infer import batch_dir, load_manifest
from sealedbench.items import canon
from sealedbench.reference import reference_questions
from sealedbench.wilson import wald_diff, wilson

ROOT = Path("/root/codes/sealedbench")


def _read(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _family_block(correct: int, invalid: int, n: int) -> dict:
    lo, hi = wilson(correct, n)
    return {
        "n": n,
        "correct": correct,
        "invalid": invalid,
        "accuracy": (correct / n) if n else None,
        "wilson95": [lo, hi],
    }


def _archive(batch: str, models: list[dict]) -> tuple[bytes, str]:
    files = []
    base = batch_dir(batch)
    for model in models:
        for folder in ("runs", "reference_runs"):
            directory = base / folder / model["id"]
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.txt")):
                if ".attempt" in path.name:
                    continue
                rel = f"{folder}/{model['id']}/{path.name}"
                files.append((rel, path.read_bytes()))
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name, data in files:
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            tar.addfile(info, io.BytesIO(data))
    packed = gzip.compress(raw.getvalue(), compresslevel=9, mtime=0)
    return packed, hashlib.sha256(packed).hexdigest()


def score_batch(batch: str) -> int:
    manifest = load_manifest(batch)
    items = []
    for line in (batch_dir(batch) / "items.jsonl").read_text().splitlines():
        if line.strip():
            items.append(json.loads(line))
    reference = reference_questions()
    release_path = batch_dir(batch) / "release.json"
    release = json.loads(release_path.read_text()) if release_path.exists() else {}
    valid = bool(release.get("batch_valid"))
    detail_lines = []
    per_model = {}
    examples = []
    first_arith = next(item for item in items if item["family"] == "arith_word")
    for model in manifest["models"]:
        families = {name: [] for name in ("arith_word", "code_output", "graph_path")}
        gsm_grades = []
        example_raw = None
        for item in items:
            raw = _read(batch_dir(batch) / "runs" / model["id"] / f"{item['item_id']}.txt")
            if raw is None:
                grade = grade_answer(item["family"], item["oracle_answer"], "")
                grade.invalid = True
                grade.correct = False
                grade.detail = "missing completion"
                grade.parsed = None
            else:
                grade = grade_answer(item["family"], item["oracle_answer"], raw)
            families[item["family"]].append(grade)
            detail_lines.append(
                canon(
                    {
                        "correct": grade.correct,
                        "family": item["family"],
                        "invalid": grade.invalid,
                        "item_id": item["item_id"],
                        "model": model["id"],
                        "oracle": grade.oracle,
                        "parsed": grade.parsed,
                    }
                )
            )
            if item["item_id"] == first_arith["item_id"]:
                example_raw = raw
        for row in reference:
            raw = _read(batch_dir(batch) / "reference_runs" / model["id"] / f"{row['item_id']}.txt")
            grade = grade_answer("gsm8k", row["oracle_answer"], raw if raw is not None else "")
            if raw is None:
                grade.invalid = True
                grade.correct = False
                grade.detail = "missing completion"
                grade.parsed = None
            gsm_grades.append(grade)
            detail_lines.append(
                canon(
                    {
                        "correct": grade.correct,
                        "family": "gsm8k",
                        "invalid": grade.invalid,
                        "item_id": row["item_id"],
                        "model": model["id"],
                        "oracle": grade.oracle,
                        "parsed": grade.parsed,
                    }
                )
            )
        family_stats = {}
        for name, grades in families.items():
            family_stats[name] = _family_block(
                sum(g.correct for g in grades),
                sum(g.invalid for g in grades),
                len(grades),
            )
        gsm_stats = _family_block(
            sum(g.correct for g in gsm_grades),
            sum(g.invalid for g in gsm_grades),
            len(gsm_grades),
        )
        gap, lo, hi = wald_diff(
            family_stats["arith_word"]["correct"],
            family_stats["arith_word"]["n"],
            gsm_stats["correct"],
            gsm_stats["n"],
        )
        per_model[model["id"]] = {
            "families": family_stats,
            "gsm8k120": gsm_stats,
            "gap_arith_minus_gsm8k": {
                "gap": gap,
                "wald95": [lo, hi],
                "method": "Wald 95% interval for the difference of independent proportions",
            },
        }
        raw = example_raw
        grade = grade_answer("arith_word", first_arith["oracle_answer"], raw if raw is not None else "")
        if raw is None:
            grade.invalid = True
            grade.correct = False
            grade.parsed = None
            grade.detail = "missing completion"
        examples.append(
            {
                "model": model["id"],
                "raw_answer": raw,
                "parsed": grade.parsed,
                "oracle": grade.oracle,
                "correct": grade.correct,
                "invalid": grade.invalid,
                "detail": grade.detail,
            }
        )
    detail_bytes = ("\n".join(detail_lines) + "\n").encode("utf-8")
    archive, archive_sha = _archive(batch, manifest["models"])
    archive_path = batch_dir(batch) / "completions.tar.gz"
    archive_path.write_bytes(archive)
    scores = {
        "protocol_version": manifest["protocol_version"],
        "batch_id": batch,
        "batch_valid": valid,
        "validity_note": release.get("validity_note", ""),
        "question_set_sha256": release.get("question_set_sha256"),
        "release_round": manifest["release_round"],
        "unlock_utc": manifest["unlock_utc"],
        "models": per_model,
        "grade_detail_sha256": hashlib.sha256(detail_bytes).hexdigest(),
        "grade_detail_bytes": len(detail_bytes),
        "completions_sha256": archive_sha,
        "completions_bytes": len(archive),
        "completions_repo_path": str(archive_path.relative_to(ROOT)),
        "worked_example": {
            "item_id": first_arith["item_id"],
            "family": "arith_word",
            "prompt": first_arith["prompt"],
            "oracle_answer": first_arith["oracle_answer"],
            "models": examples,
        },
    }
    (batch_dir(batch) / "grades.jsonl").write_bytes(detail_bytes)
    (batch_dir(batch) / "scores.json").write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n")
    _write_md(batch_dir(batch) / "scores.md", scores)
    print(
        f"SCORE valid={valid} detail={scores['grade_detail_sha256'][:12]} "
        f"completions_bytes={len(archive)}"
    )
    return 0


def _fmt_pct(block: dict) -> str:
    if not block["n"]:
        return "n/a"
    acc = block["accuracy"]
    lo, hi = block["wilson95"]
    return f"{block['correct']}/{block['n']} = {acc:.3f} [{lo:.3f}, {hi:.3f}]"


def _write_md(path: Path, scores: dict) -> None:
    lines = [
        f"# Batch {scores['batch_id']} scores",
        "",
        f"Batch validity: {'VALID' if scores['batch_valid'] else 'INVALID'}. {scores.get('validity_note', '')}",
        "",
        f"Question set `{scores.get('question_set_sha256')}`.",
        f"Release round {scores['release_round']} unlocks at {scores['unlock_utc']}.",
        "",
        "Wilson intervals are 95% score intervals. The gap interval is a Wald interval for the difference.",
        "Invalid completions are included in `n` and are not correct.",
        "",
        "| model | family | n | correct | invalid | accuracy | Wilson 95% |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for model, row in scores["models"].items():
        for family, block in row["families"].items():
            lo, hi = block["wilson95"]
            acc = "n/a" if block["accuracy"] is None else f"{block['accuracy']:.4f}"
            span = "n/a" if lo is None else f"[{lo:.4f}, {hi:.4f}]"
            lines.append(
                f"| {model} | {family} | {block['n']} | {block['correct']} | {block['invalid']} | {acc} | {span} |"
            )
        gsm = row["gsm8k120"]
        lo, hi = gsm["wilson95"]
        lines.append(
            f"| {model} | gsm8k-120 | {gsm['n']} | {gsm['correct']} | {gsm['invalid']} | "
            f"{gsm['accuracy']:.4f} | [{lo:.4f}, {hi:.4f}] |"
        )
    lines.extend(["", "## Reference gap (arith_word minus GSM8K-120)", "", "| model | arith_word | GSM8K-120 | gap | Wald 95% |", "| --- | --- | --- | --- | --- |"])
    for model, row in scores["models"].items():
        gap = row["gap_arith_minus_gsm8k"]
        lo, hi = gap["wald95"]
        lines.append(
            f"| {model} | {_fmt_pct(row['families']['arith_word'])} | {_fmt_pct(row['gsm8k120'])} | "
            f"{gap['gap']:.4f} | [{lo:.4f}, {hi:.4f}] |"
        )
    example = scores["worked_example"]
    lines.extend(
        [
            "",
            f"## Worked example `{example['item_id']}`",
            "",
            "Prompt:",
            "",
            "```",
            example["prompt"],
            "```",
            "",
            f"Oracle answer: `{example['oracle_answer']}`",
            "",
        ]
    )
    for row in example["models"]:
        lines.append(f"### {row['model']}")
        lines.append("")
        lines.append(f"Parsed `{row['parsed']}`, oracle `{row['oracle']}`, correct={row['correct']}, invalid={row['invalid']}.")
        lines.append("")
        lines.append("Raw completion:")
        lines.append("")
        lines.append("```")
        lines.append(row["raw_answer"] if row["raw_answer"] is not None else "(missing)")
        lines.append("```")
        lines.append("")
    path.write_text("\n".join(lines))
