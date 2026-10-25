"""Short Python programs whose stdout is the oracle.

Programs are at most 15 lines, use no imports, no randomness, and no input.
The oracle runs the source in a fresh interpreter with a 2 second timeout.
The prompt asks for that stdout inside a fenced block.
"""

from __future__ import annotations

import subprocess
import sys

from sealedbench.extract import normalize_output
from sealedbench.items import Item
from sealedbench.rng import RNG

WORDS = [
    "amber", "brook", "cloud", "delta", "ember", "flint", "grove", "harbor",
    "ivory", "juniper", "kelp", "lilac", "maple", "north", "opal", "pine",
    "quartz", "river", "stone", "timber",
]

_FORBIDDEN = ("import ", "open(", "input(", "eval(", "exec(", "random", "__", "os.", "sys.")


def run_program(source: str, timeout: float = 2.0) -> tuple[str | None, str]:
    """Return (normalized stdout, error). error is empty on success."""
    try:
        proc = subprocess.run(
            [sys.executable, "-I", "-c", source],
            capture_output=True,
            timeout=timeout,
            check=False,
            env={"PATH": "/usr/bin:/bin", "PYTHONIOENCODING": "utf-8", "LC_ALL": "C"},
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip().splitlines()
        return None, err[-1] if err else f"exit {proc.returncode}"
    text = proc.stdout.decode("utf-8", errors="replace")
    normalized = normalize_output(text)
    if normalized == "":
        return None, "empty stdout"
    if len(normalized) > 2000:
        return None, "stdout too long"
    return normalized, ""


def _line_count(source: str) -> int:
    return source.count("\n") + (0 if source.endswith("\n") else 1)


def _ok_source(source: str) -> bool:
    if _line_count(source) > 15 or _line_count(source) < 3:
        return False
    lowered = source.lower()
    if any(token in lowered for token in _FORBIDDEN):
        return False
    if "print(" not in source or "for " not in source or "if " not in source:
        return False
    return True


def _acc(rng: RNG) -> str:
    length = rng.randint(4, 8)
    values = [rng.randint(0, 18) for _ in range(length)]
    lo, hi = min(values), max(values)
    thresh = lo if lo == hi else rng.randint(lo, hi)
    cmp_op = rng.choice([">", ">=", "<", "<="])
    init = rng.randint(0, 6)
    then_const = rng.randint(1, 5)
    else_const = rng.randint(0, 4)
    then_op = rng.choice(["value", str(then_const)])
    else_op = rng.choice(["value", str(else_const)])
    literal = ", ".join(str(v) for v in values)
    return (
        f"values = [{literal}]\n"
        f"total = {init}\n"
        "for value in values:\n"
        f"    if value {cmp_op} {thresh}:\n"
        f"        total = total + {then_op}\n"
        "    else:\n"
        f"        total = total + {else_op}\n"
        "print(total)\n"
    )


def _string(rng: RNG) -> str:
    words = rng.sample(WORDS, rng.randint(3, 6))
    modulus = rng.randint(2, 3)
    remainder = rng.randint(0, modulus - 1)
    sep = rng.choice(["-", ",", "/", " "])
    quoted = ", ".join(repr(word) for word in words)
    return (
        f"words = [{quoted}]\n"
        'out = ""\n'
        "for index in range(len(words)):\n"
        "    piece = words[index]\n"
        f"    if index % {modulus} == {remainder}:\n"
        "        piece = piece.upper()\n"
        '    if out == "":\n'
        "        out = piece\n"
        "    else:\n"
        f"        out = out + {sep!r} + piece\n"
        "print(out)\n"
    )


def _nested(rng: RNG) -> str:
    outer = rng.randint(2, 6)
    inner = rng.randint(2, 5)
    modulus = rng.randint(2, 4)
    return (
        "count = 0\n"
        f"for i in range({outer}):\n"
        f"    for j in range({inner}):\n"
        f"        if (i + j) % {modulus} == 0:\n"
        "            count = count + i + 1\n"
        "        else:\n"
        "            count = count + j + 1\n"
        "print(count)\n"
    )


def _filter(rng: RNG) -> str:
    length = rng.randint(5, 8)
    values = [rng.randint(0, 15) for _ in range(length)]
    thresh = rng.randint(1, 12)
    cmp_op = rng.choice([">=", ">", "<="])
    literal = ", ".join(str(v) for v in values)
    return (
        f"nums = [{literal}]\n"
        "kept = []\n"
        "for num in nums:\n"
        f"    if num {cmp_op} {thresh}:\n"
        "        kept.append(num)\n"
        "print(len(kept))\n"
        "print(kept)\n"
    )


_BUILDERS = {
    "acc": _acc,
    "string": _string,
    "nested": _nested,
    "filter": _filter,
}


def render(source: str) -> str:
    body = source if source.endswith("\n") else source + "\n"
    return (
        "What is the exact standard output of this Python 3 program?\n"
        "\n"
        "```python\n"
        f"{body}"
        "```"
    )


def generate(seed_bytes: bytes, n: int) -> list[Item]:
    rng = RNG(seed_bytes)
    items: list[Item] = []
    seen: set[str] = set()
    attempts = 0
    limit = max(20, n * 30)
    names = list(_BUILDERS)
    while len(items) < n:
        attempts += 1
        if attempts > limit:
            raise RuntimeError(f"code_output produced {len(items)} of {n} after {attempts} draws")
        variant = rng.choice(names)
        source = _BUILDERS[variant](rng)
        if not _ok_source(source) or source in seen:
            continue
        stdout, err = run_program(source)
        if err or stdout is None:
            continue
        seen.add(source)
        params = {
            "variant": variant,
            "source": source,
            "n_lines": _line_count(source),
        }
        items.append(
            Item(
                item_id=f"code_output-{len(items):04d}",
                prompt=render(source),
                oracle_answer=stdout,
                family="code_output",
                params=params,
            )
        )
    return items
