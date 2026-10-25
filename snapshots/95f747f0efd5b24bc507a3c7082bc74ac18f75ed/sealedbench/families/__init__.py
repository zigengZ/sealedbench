"""Question families. Each exposes generate(seed_bytes, n) -> list[Item]."""

from sealedbench.families.arith_word import generate as generate_arith
from sealedbench.families.code_output import generate as generate_code
from sealedbench.families.graph_path import generate as generate_graph

GENERATORS = {
    "arith_word": generate_arith,
    "code_output": generate_code,
    "graph_path": generate_graph,
}

__all__ = ["GENERATORS"]
