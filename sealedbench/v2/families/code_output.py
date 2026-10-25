"""Code-output items with a step-budget interpreter.

The oracle never starts a subprocess and never reads the clock. A candidate
that exceeds the step budget, prints nothing, or uses an unsupported syntax
node is rejected. Later items do not depend on machine load.
"""

from __future__ import annotations

import ast

from sealedbench.items import Item
from sealedbench.v2.prng import PRNG

STEP_BUDGET = 10_000
WORDS = (
    "amber", "brook", "cloud", "delta", "ember", "flint", "grove", "harbor",
    "ivory", "juniper", "kelp", "lilac", "maple", "north", "opal", "pine",
    "quartz", "river", "stone", "timber",
)


class InterpError(Exception):
    pass


class StepLimit(Exception):
    pass


def _show(value) -> str:
    if isinstance(value, bool) or value is None:
        raise InterpError("bad print value")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "[" + ", ".join(_list_token(item) for item in value) + "]"
    raise InterpError("bad print value")


def _list_token(value) -> str:
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        return repr(value)
    raise InterpError("bad list token")


class Interpreter:
    def __init__(self, budget: int = STEP_BUDGET):
        self.budget = budget
        self.steps = 0
        self.env: dict = {}
        self.output: list[str] = []

    def tick(self) -> None:
        self.steps += 1
        if self.steps > self.budget:
            raise StepLimit(str(self.steps))

    def run(self, source: str) -> str:
        tree = ast.parse(source)
        for stmt in tree.body:
            self.exec(stmt)
        return "\n".join(self.output)

    def exec(self, node) -> None:
        self.tick()
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise InterpError("assignment")
            self.env[node.targets[0].id] = self.eval(node.value)
            return
        if isinstance(node, ast.For):
            if not isinstance(node.target, ast.Name) or node.orelse:
                raise InterpError("for")
            seq = self.eval(node.iter)
            if not isinstance(seq, list):
                raise InterpError("for iterator")
            for value in list(seq):
                self.tick()
                self.env[node.target.id] = value
                for stmt in node.body:
                    self.exec(stmt)
            return
        if isinstance(node, ast.If):
            branch = node.body if self.truth(self.eval(node.test)) else node.orelse
            for stmt in branch:
                self.exec(stmt)
            return
        if isinstance(node, ast.Expr):
            self.eval(node.value)
            return
        raise InterpError(type(node).__name__)

    def truth(self, value) -> bool:
        if isinstance(value, bool):
            return value
        raise InterpError("condition")

    def eval(self, node):
        self.tick()
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, str)) and not isinstance(node.value, bool):
                return node.value
            raise InterpError("constant")
        if isinstance(node, ast.Name):
            if node.id not in self.env:
                raise InterpError(f"name {node.id}")
            return self.env[node.id]
        if isinstance(node, ast.List):
            return [self.eval(elt) for elt in node.elts]
        if isinstance(node, ast.BinOp):
            left = self.eval(node.left)
            right = self.eval(node.right)
            if isinstance(node.op, ast.Add) and isinstance(left, str) and isinstance(right, str):
                return left + right
            if isinstance(left, int) and isinstance(right, int) and not isinstance(left, bool):
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Mod):
                    if right == 0:
                        raise InterpError("mod 0")
                    return left % right
            raise InterpError("binop")
        if isinstance(node, ast.Compare):
            if len(node.ops) != 1 or len(node.comparators) != 1:
                raise InterpError("compare")
            left = self.eval(node.left)
            right = self.eval(node.comparators[0])
            op = node.ops[0]
            pairs = {
                ast.Eq: lambda a, b: a == b,
                ast.NotEq: lambda a, b: a != b,
                ast.Lt: lambda a, b: a < b,
                ast.LtE: lambda a, b: a <= b,
                ast.Gt: lambda a, b: a > b,
                ast.GtE: lambda a, b: a >= b,
            }
            kind = type(op)
            if kind not in pairs:
                raise InterpError("compare op")
            return bool(pairs[kind](left, right))
        if isinstance(node, ast.Subscript):
            host = self.eval(node.value)
            index = self.eval(node.slice)
            if not isinstance(index, int):
                raise InterpError("index")
            if isinstance(host, list):
                return host[index]
            if isinstance(host, str):
                return host[index]
            raise InterpError("subscript")
        if isinstance(node, ast.Call):
            return self.call(node)
        raise InterpError(type(node).__name__)

    def call(self, node: ast.Call):
        if node.keywords:
            raise InterpError("keywords")
        args = [self.eval(arg) for arg in node.args]
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name == "range":
                if len(args) == 1 and isinstance(args[0], int) and 0 <= args[0] <= 32:
                    return list(range(args[0]))
                if (
                    len(args) == 2
                    and isinstance(args[0], int)
                    and isinstance(args[1], int)
                    and 0 <= args[1] - args[0] <= 32
                ):
                    return list(range(args[0], args[1]))
                raise InterpError("range")
            if name == "len" and len(args) == 1 and isinstance(args[0], (list, str)):
                return len(args[0])
            if name == "print":
                self.output.append(" ".join(_show(arg) for arg in args))
                return None
            raise InterpError(name)
        if isinstance(node.func, ast.Attribute):
            obj = self.eval(node.func.value)
            attr = node.func.attr
            if attr == "append" and isinstance(obj, list) and len(args) == 1:
                if not isinstance(args[0], (int, str)) or isinstance(args[0], bool):
                    raise InterpError("append")
                obj.append(args[0])
                return None
            if attr == "upper" and isinstance(obj, str) and not args:
                return obj.upper()
            raise InterpError(attr)
        raise InterpError("call")


def execute(source: str, budget: int = STEP_BUDGET) -> tuple[str | None, str]:
    try:
        text = Interpreter(budget).run(source)
    except (InterpError, StepLimit, SyntaxError, IndexError, TypeError, ValueError) as exc:
        return None, type(exc).__name__
    if text == "":
        return None, "empty"
    if len(text) > 2000:
        return None, "long"
    return text, ""


def _acc(rng: PRNG) -> str:
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
    literal = ", ".join(str(value) for value in values)
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


def _string(rng: PRNG) -> str:
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


def _nested(rng: PRNG) -> str:
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


def _filter(rng: PRNG) -> str:
    length = rng.randint(5, 8)
    values = [rng.randint(0, 15) for _ in range(length)]
    thresh = rng.randint(1, 12)
    cmp_op = rng.choice([">=", ">", "<="])
    literal = ", ".join(str(value) for value in values)
    return (
        f"nums = [{literal}]\n"
        "kept = []\n"
        "for num in nums:\n"
        f"    if num {cmp_op} {thresh}:\n"
        "        kept.append(num)\n"
        "print(len(kept))\n"
        "print(kept)\n"
    )


def _range_sum(rng: PRNG) -> str:
    limit = rng.randint(4, 12)
    skip = rng.randint(0, limit - 1)
    return (
        "total = 0\n"
        f"for value in range({limit}):\n"
        f"    if value == {skip}:\n"
        "        total = total + 0\n"
        "    else:\n"
        "        total = total + value\n"
        "print(total)\n"
    )


def _digit_sum(rng: PRNG) -> str:
    length = rng.randint(4, 8)
    digits = [rng.randint(0, 9) for _ in range(length)]
    literal = ", ".join(str(value) for value in digits)
    return (
        f"digits = [{literal}]\n"
        "total = 0\n"
        "for digit in digits:\n"
        "    total = total + digit\n"
        "print(total)\n"
        "print(len(digits))\n"
    )


def _pairs(rng: PRNG) -> str:
    limit = rng.randint(3, 7)
    residue = rng.randint(0, 2)
    return (
        "count = 0\n"
        f"for i in range({limit}):\n"
        f"    for j in range({limit}):\n"
        "        if i < j:\n"
        f"            if (i + j) % 3 == {residue}:\n"
        "                count = count + 1\n"
        "print(count)\n"
    )


def _window(rng: PRNG) -> str:
    length = rng.randint(4, 7)
    values = [rng.randint(1, 9) for _ in range(length)]
    width = rng.randint(2, 3)
    literal = ", ".join(str(value) for value in values)
    return (
        f"values = [{literal}]\n"
        "best = 0\n"
        f"for start in range({length - width + 1}):\n"
        "    total = 0\n"
        f"    for offset in range({width}):\n"
        "        total = total + values[start + offset]\n"
        "    if total > best:\n"
        "        best = total\n"
        "print(best)\n"
    )


BUILDERS = {
    "acc": _acc,
    "string": _string,
    "nested": _nested,
    "filter": _filter,
    "range_sum": _range_sum,
    "digit_sum": _digit_sum,
    "pairs": _pairs,
    "window": _window,
}
TEMPLATE_IDS = tuple(BUILDERS)


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
    rng = PRNG(seed_bytes)
    items: list[Item] = []
    seen: set[str] = set()
    attempts = 0
    limit = max(20, n * 40)
    names = list(TEMPLATE_IDS)
    while len(items) < n:
        attempts += 1
        if attempts > limit:
            raise RuntimeError(f"code_output produced {len(items)} of {n} after {attempts} draws")
        variant = rng.choice(names)
        source = BUILDERS[variant](rng)
        if source in seen or "import " in source or "def " in source:
            continue
        stdout, err = execute(source)
        if err or stdout is None:
            continue
        seen.add(source)
        items.append(
            Item(
                item_id=f"code_output-{len(items):04d}",
                prompt=render(source),
                oracle_answer=stdout,
                family="code_output",
                params={
                    "template_id": variant,
                    "variant": variant,
                    "source": source,
                    "step_budget": STEP_BUDGET,
                },
            )
        )
    return items
