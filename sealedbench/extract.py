"""Answer extraction. One module, used by the grader and the manifest.

Integer families (arith_word, graph_path) and the GSM8K reference use the
Phase 1 C3 convention:

  hash form:  ####\\s*(-?\\d[\\d,]*(?:\\.\\d+)?)     last match wins
  fallback:   -?\\d[\\d,]*(?:\\.\\d+)?               last match, only if no hash form
  gold form:  ####\\s*(-?\\d[\\d,]*)                 last match, GSM8K answer field

Normalization: remove commas, and if the text is an integer followed by
`.0`, `.00`, … drop the decimal. Comparison is exact string equality with
the oracle's decimal integer.

code_output:

  fence: ```[optional token]\\n <body> ```
  regex: ```[ \\t]*([A-Za-z0-9_+-]*)[ \\t]*\\n(.*?)```    DOTALL, last match

The body is normalized by converting CRLF to LF, stripping trailing
whitespace on each line, and dropping one trailing empty line that came
from a final newline. Empty or missing fences are invalid. A parsed body
that does not match the oracle is wrong, not invalid.
"""

from __future__ import annotations

import re

INTEGER_HASH_RE_SRC = r"####\s*(-?\d[\d,]*(?:\.\d+)?)"
INTEGER_BARE_RE_SRC = r"-?\d[\d,]*(?:\.\d+)?"
GOLD_RE_SRC = r"####\s*(-?\d[\d,]*)"
FENCE_RE_SRC = r"```[ \t]*([A-Za-z0-9_+-]*)[ \t]*\n(.*?)```"

INTEGER_HASH_RE = re.compile(INTEGER_HASH_RE_SRC)
INTEGER_BARE_RE = re.compile(INTEGER_BARE_RE_SRC)
GOLD_RE = re.compile(GOLD_RE_SRC)
FENCE_RE = re.compile(FENCE_RE_SRC, re.DOTALL)
_TRAILING_DOT_ZERO = re.compile(r"-?\d+\.0+")


def canon_number(raw: str) -> str:
    text = raw.replace(",", "").strip()
    if _TRAILING_DOT_ZERO.fullmatch(text):
        text = text.split(".", 1)[0]
    return text


def extract_integer(text: str | None) -> str | None:
    """Last #### number, else the last bare number, else None."""
    if text is None:
        return None
    hashed = INTEGER_HASH_RE.findall(text)
    if hashed:
        return canon_number(hashed[-1])
    nums = INTEGER_BARE_RE.findall(text)
    if not nums:
        return None
    return canon_number(nums[-1])


def extract_gold(answer_field: str | None) -> str | None:
    if not answer_field:
        return None
    found = GOLD_RE.findall(answer_field)
    if not found:
        return None
    return canon_number(found[-1])


def normalize_output(text: str) -> str:
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = body.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return "\n".join(line.rstrip() for line in lines)


def extract_fenced(text: str | None) -> str | None:
    """Last fenced block body, or None when the completion has no fence."""
    if text is None:
        return None
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    matches = list(FENCE_RE.finditer(normalized))
    if not matches:
        return None
    return matches[-1].group(2)
