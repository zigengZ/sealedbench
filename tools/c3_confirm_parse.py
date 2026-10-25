#!/usr/bin/env python3
"""Confirm b3r numeric completions parse after sentinel normalization."""

import json
import os
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sealedbench.v2.grade import canon_number, extract_strict_integer, is_truncated
from sealedbench.v2.grade_b3 import grade_answer, normalize_stdout_bytes
from sealedbench.v2.scoring import RUNS_RE

INTEGER_LINE = re.compile(r"^####[ \t]+(-?\d[\d,]*)[ \t]*(?:\[end of text\])?[ \t]*$")


def main() -> None:
    batch = os.environ.get("SEALEDBENCH_BATCH", "b3r")
    dest = ROOT / "results/batches" / batch
    manifest = json.loads((dest / "manifest.json").read_text())
    if "sealedbench/v2/grade_b3.py" not in manifest["grader"]["files"]:
        raise SystemExit("manifest is not using the b3 grader")
    items = [json.loads(line) for line in (dest / "items.jsonl").read_text().splitlines() if line.strip()]
    families = {item["item_id"]: item["family"] for item in items}
    rows = []
    failures = []
    for kind, base in (("exam", dest / "runs"), ("reference", dest / "reference_runs")):
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*/*.txt")):
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            normalized = normalize_stdout_bytes(raw).decode("utf-8", errors="replace")
            matches = [canon_number(match.group(1)) for line in text.splitlines() if (match := INTEGER_LINE.match(line))]
            parsed = extract_strict_integer(normalized)
            stderr_path = path.with_suffix(".stderr")
            stderr = stderr_path.read_text(encoding="utf-8", errors="replace") if stderr_path.exists() else ""
            found = RUNS_RE.search(stderr)
            runs = int(found.group(1)) if found else None
            family = families.get(path.stem, "gsm8k")
            n_predict = int(manifest["runtime"]["n_predict"].get(family, manifest["runtime"]["n_predict"]["default"]))
            truncated = is_truncated(text, runs, n_predict)
            if matches and parsed != matches[-1]:
                failures.append(str(path))
            graded = None
            if family in ("arith_word", "graph_path", "gsm8k"):
                oracle = "0"
                graded = grade_answer(family, oracle, raw, truncated=truncated)
                if matches and graded.parsed != matches[-1]:
                    failures.append(str(path) + " grade")
            rows.append({
                "path": str(path.relative_to(dest)),
                "family": family,
                "runs": runs,
                "truncated": truncated,
                "integer_lines": len(matches),
                "parsed": parsed,
                "grade_invalid": None if graded is None else graded.invalid,
            })
    integer_rows = [row for row in rows if row["integer_lines"]]
    parsed_rows = [row for row in integer_rows if row["parsed"]]
    report = {
        "batch": batch,
        "outputs": len(rows),
        "integer_line_outputs": len(integer_rows),
        "parsed_integer_line_outputs": len(parsed_rows),
        "failures": failures,
        "rows": rows,
    }
    out = Path("/root/sbw/c3/b3r_parse.json")
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(
        f"PARSE_CONFIRM outputs={len(rows)} integer_lines={len(integer_rows)} "
        f"parsed={len(parsed_rows)} failures={len(failures)}"
    )
    if failures or not integer_rows or len(parsed_rows) != len(integer_rows):
        raise SystemExit("numeric rehearsal outputs did not all parse")


if __name__ == "__main__":
    main()
