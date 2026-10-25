"""Grade one model completion against an item.

An unparseable completion is invalid and counts as wrong. A parsed answer
that differs from the oracle is wrong and not invalid.
"""

from __future__ import annotations

from dataclasses import dataclass

from sealedbench.extract import extract_fenced, extract_integer, normalize_output

INTEGER_FAMILIES = ("arith_word", "graph_path", "gsm8k")


@dataclass
class GradeResult:
    correct: bool
    invalid: bool
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
        }


def grade_answer(family: str, oracle_answer: str, raw: str | None) -> GradeResult:
    oracle = oracle_answer if family == "code_output" else str(oracle_answer)
    if family in INTEGER_FAMILIES:
        parsed = extract_integer(raw)
        if parsed is None:
            return GradeResult(False, True, None, oracle, "no integer found")
        ok = parsed == oracle
        return GradeResult(ok, False, parsed, oracle, "match" if ok else "mismatch")
    if family == "code_output":
        body = extract_fenced(raw)
        if body is None:
            return GradeResult(False, True, None, normalize_output(oracle), "no fenced block")
        parsed = normalize_output(body)
        expected = normalize_output(oracle)
        ok = parsed == expected
        return GradeResult(ok, False, parsed, expected, "match" if ok else "mismatch")
    raise ValueError(f"unknown family {family}")
