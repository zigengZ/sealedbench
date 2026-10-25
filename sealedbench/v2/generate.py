"""Build a v2 batch from a 32-byte seed.

family_seed is defined in sealedbench.v2.spec. Arith and graph use the v1
samplers, which do not read the clock. Code uses the step-budget interpreter.
"""

from __future__ import annotations

from sealedbench.families.arith_word import generate as generate_arith
from sealedbench.families.graph_path import generate as generate_graph
from sealedbench.items import Item
from sealedbench.v2.families.code_output import TEMPLATE_IDS as CODE_TEMPLATES
from sealedbench.v2.families.code_output import generate as generate_code
from sealedbench.v2.spec import family_seed

FAMILY_ORDER = ("arith_word", "code_output", "graph_path")

ARITH_TEMPLATES = (
    "buy_give",
    "buy_receive",
    "buy_give_receive",
    "two_buys",
    "buy_give_price",
    "buy_give_receive_price",
    "two_buys_give",
    "two_buys_give_price",
    "buy_give_share",
    "two_buys_share",
    "two_buys_give_share",
    "one_day_spend",
    "two_days",
    "two_days_spend",
    "three_days",
    "days_plus",
    "days_plus_skip",
    "two_books",
    "two_books_skip",
    "two_books_weeks",
    "rows_left",
    "rows_price",
    "two_sections",
    "two_sections_sold",
    "two_sections_price",
)


def template_bank() -> dict:
    return {
        "arith_word": list(ARITH_TEMPLATES),
        "code_output": list(CODE_TEMPLATES),
        "graph_path": {
            "template_id": "nodes-<count>",
            "node_counts": [6, 7, 8, 9, 10],
            "note": "Connected weighted graphs. template_id is the node count, not a prose template.",
        },
    }


def _retag(item: Item, template_id: str) -> Item:
    params = dict(item.params)
    params["template_id"] = template_id
    return Item(
        item_id=item.item_id,
        prompt=item.prompt,
        oracle_answer=item.oracle_answer,
        family=item.family,
        params=params,
    )


def generate_batch(seed: bytes, counts: dict) -> list[Item]:
    if set(counts) != set(FAMILY_ORDER):
        raise ValueError(f"counts must name {FAMILY_ORDER}")
    items: list[Item] = []
    seen: set[str] = set()
    for family in FAMILY_ORDER:
        n = int(counts[family])
        if n < 0:
            raise ValueError("n must be >= 0")
        sub = family_seed(seed, family, n)
        if family == "arith_word":
            produced = [_retag(item, str(item.params["template"])) for item in generate_arith(sub, n)]
        elif family == "graph_path":
            produced = [_retag(item, f"nodes-{int(item.params['n_nodes'])}") for item in generate_graph(sub, n)]
        else:
            produced = list(generate_code(sub, n))
        if len(produced) != n:
            raise RuntimeError(f"{family} returned {len(produced)} items, wanted {n}")
        for item in produced:
            if item.family != family or item.prompt in seen or "template_id" not in item.params:
                raise RuntimeError(f"bad item {item.item_id}")
            seen.add(item.prompt)
            items.append(item)
    return items
