"""b3 grader-input normalization.

sealedbench/v2/grade.py stays the registered b2 grader and is not modified.
This module applies one byte procedure to raw llama.cpp stdout, then calls
that module's integer rule and code rule.

Procedure, once, on the raw stdout bytes B:
  W is the ASCII whitespace removed by bytes.rstrip() with no argument
  (0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x20).
  S = B.rstrip()
  If S ends with the 13 bytes of ASCII "[end of text]", S = S[:-13] once.
  S = S.rstrip()
The graded text is S decoded as UTF-8, with invalid sequences replaced.
Truncation is not decided here. Callers still use grade.is_truncated on the
raw stdout and the llama.cpp run count.
"""

from __future__ import annotations

from sealedbench.v2.grade import GradeResult, grade_answer as grade_registered

SENTINEL = b"[end of text]"
NORMALIZATION_SPEC = (
    "Let B be the raw stdout bytes. "
    "Let W be the ASCII whitespace stripped by Python bytes.rstrip() with no argument: "
    "0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x20. "
    "Set S = B.rstrip(). "
    "If S ends with the 13 bytes 5b 65 6e 64 20 6f 66 20 74 65 78 74 5d "
    "(ASCII [end of text]), set S = S[:-13] exactly once. "
    "Set S = S.rstrip() again. "
    "The integer rule and the code rule then apply to S decoded as UTF-8, "
    "with invalid byte sequences replaced. "
    "Truncation is unchanged and uses the raw stdout before this procedure: "
    "the completion is truncated when it does not contain the ASCII marker "
    "[end of text], or when the llama.cpp run count is at least n_predict-1."
)


def normalize_stdout_bytes(raw: bytes) -> bytes:
    if not isinstance(raw, (bytes, bytearray)):
        raise TypeError("normalize_stdout_bytes expects the raw stdout bytes")
    if len(SENTINEL) != 13:
        raise RuntimeError("llama.cpp sentinel is not 13 bytes")
    data = bytes(raw).rstrip()
    if data.endswith(SENTINEL):
        data = data[:-13]
    return data.rstrip()


def graded_text(raw: str | bytes | None) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        blob = raw.encode("utf-8")
    else:
        blob = bytes(raw)
    return normalize_stdout_bytes(blob).decode("utf-8", errors="replace")


def grade_answer(
    family: str,
    oracle_answer: str,
    raw: str | bytes | None,
    truncated: bool = False,
) -> GradeResult:
    return grade_registered(family, oracle_answer, graded_text(raw), truncated=truncated)
