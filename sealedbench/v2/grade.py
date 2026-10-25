"""Strict v2 grader.

Integer families accept only a `#### <integer>` line. There is no
last-number fallback. Code is the last fenced block. Truncation is invalid.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

HASH_LINE_RE = re.compile(r"^####[ \t]+(-?\d[\d,]*)[ \t]*$", re.MULTILINE)
FENCE_RE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```", re.DOTALL)
_DOT_ZERO = re.compile(r"-?\d+\.0+")

INTEGER_FAMILIES = ("arith_word", "graph_path", "gsm8k")


def canon_number(raw: str) -> str:
    text = raw.replace(",", "").strip()
    if _DOT_ZERO.fullmatch(text):
        text = text.split(".", 1)[0]
    return text


def extract_strict_integer(text: str | None) -> str | None:
    if text is None:
        return None
    found = HASH_LINE_RE.findall(text)
    if not found:
        return None
    return canon_number(found[-1])


def normalize_output(text: str) -> str:
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = body.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return "\n".join(line.rstrip() for line in lines)


def extract_last_fence(text: str | None) -> str | None:
    if text is None:
        return None
    matches = list(FENCE_RE.finditer(text.replace("\r\n", "\n").replace("\r", "\n")))
    if not matches:
        return None
    return matches[-1].group(2)


@dataclass
class GradeResult:
    correct: bool
    invalid: bool
    truncated: bool
    parsed: str | None
    oracle: str
    detail: str

    def to_obj(self) -> dict:
        return {
            "correct": self.correct,
            "detail": self.detail,
            "invalid": self.invalid,
            "oracle": self.oracle,
            "parsed": self.parsed,
            "truncated": self.truncated,
        }


def grade_answer(family: str, oracle_answer: str, raw: str | None, truncated: bool = False) -> GradeResult:
    if family in INTEGER_FAMILIES:
        oracle = str(oracle_answer)
        parsed = extract_strict_integer(raw)
        if truncated:
            return GradeResult(False, True, True, parsed, oracle, "truncated")
        if parsed is None:
            return GradeResult(False, True, False, None, oracle, "no #### line")
        ok = parsed == oracle
        return GradeResult(ok, False, False, parsed, oracle, "match" if ok else "mismatch")
    if family == "code_output":
        oracle = normalize_output(str(oracle_answer))
        body = extract_last_fence(raw)
        if truncated:
            parsed = normalize_output(body) if body is not None else None
            return GradeResult(False, True, True, parsed, oracle, "truncated")
        if body is None:
            return GradeResult(False, True, False, None, oracle, "no fenced block")
        parsed = normalize_output(body)
        ok = parsed == oracle
        return GradeResult(ok, False, False, parsed, oracle, "match" if ok else "mismatch")
    raise ValueError(f"unknown family {family}")


def is_truncated(stdout: str | None, runs: int | None, n_predict: int) -> bool:
    """EOS marker missing, or the llama.cpp run count reached n_predict-1."""
    text = stdout or ""
    if "[end of text]" not in text:
        return True
    if runs is not None and runs >= int(n_predict) - 1:
        return True
    return False
