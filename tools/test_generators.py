#!/usr/bin/env python3
"""Checks for the Phase 2 generators, grader, and deterministic tarball."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path("/root/codes/sealedbench")
sys.path.insert(0, str(ROOT))

from sealedbench.extract import extract_fenced, extract_gold, extract_integer, normalize_output
from sealedbench.families.arith_word import answer_of, render, steps_of
from sealedbench.families.code_output import generate as gen_code
from sealedbench.families.code_output import run_program
from sealedbench.families.graph_path import answer_of as graph_answer
from sealedbench.families.graph_path import shortest
from sealedbench.generate import generate_batch
from sealedbench.grade import grade_answer
from sealedbench.items import dumps_jsonl, loads_jsonl, question_set_sha256
from sealedbench.rng import RNG
from sealedbench.seed import seed_bytes
from sealedbench.tarball import build_generator_tarball


def expect(cond, msg):
    if not cond:
        raise SystemExit(f"FAIL {msg}")


def test_rng_stable():
    a = RNG(b"\x00" * 32)
    b = RNG(b"\x00" * 32)
    draws = [a.randint(0, 10**6) for _ in range(5)]
    expect(draws == [b.randint(0, 10**6) for _ in range(5)], "rng diverged")
    expect(len(set(draws)) > 1, "rng constant")
    print("rng", draws[0])


def test_seed_rule():
    digest = seed_bytes("aa", 3, "bb")
    material = b"sealedbench/v1" + b"aa" + b"3" + b"bb"
    expect(digest == hashlib.sha256(material).digest(), "seed rule")
    expect(seed_bytes("AA", 3, "BB") == digest, "lowercase")


def test_arith_manual():
    params = {
        "frame": "packs",
        "template": "buy_give",
        "name": "Ava",
        "friend": "Ben",
        "plural": "stickers",
        "singular": "sticker",
        "packs": 4,
        "per": 9,
        "give": 6,
    }
    expect(answer_of(params) == 30, "buy_give answer")
    expect(steps_of(params) == 2, "buy_give steps")
    text = render(params)
    expect("4 packs" in text and "9 stickers" in text and "6 stickers" in text, text)
    expect("30" not in text, "answer leaked")
    share = dict(params, template="buy_give_share", share=3)
    # 36-6=30, 30/3=10
    expect(answer_of(share) == 10, "share")
    wage = {
        "frame": "wage",
        "template": "two_days_spend",
        "name": "Nico",
        "rate": 10,
        "hours": [3, 4],
        "spend": 5,
    }
    expect(answer_of(wage) == 65, "wage")
    expect(steps_of(wage) == 4, "wage steps")


def test_graph_dijkstra():
    nodes = ["A", "B", "C"]
    edges = [["A", "B", 1], ["B", "C", 1], ["A", "C", 5]]
    dist, hops = shortest(nodes, edges, "A")
    expect(dist["C"] == 2 and hops["C"] == 2, (dist["C"], hops["C"]))
    direct = [["A", "B", 4]]
    dist2, hops2 = shortest(["A", "B"], direct, "A")
    expect(dist2["B"] == 4 and hops2["B"] == 1, "direct hop")


def test_batch():
    seed = hashlib.sha256(b"batch-test").digest()
    counts = {"arith_word": 12, "code_output": 6, "graph_path": 6}
    first = generate_batch(seed, counts)
    second = generate_batch(seed, counts)
    expect(dumps_jsonl(first) == dumps_jsonl(second), "batch not deterministic")
    other = generate_batch(hashlib.sha256(b"other").digest(), counts)
    expect(question_set_sha256(first) != question_set_sha256(other), "seeds collided")
    prompts = [item.prompt for item in first]
    expect(len(prompts) == len(set(prompts)), "duplicate prompt")
    for item in first:
        if item.family == "arith_word":
            expect(item.params["n_steps"] in range(2, 6), item.item_id)
            expect(int(item.oracle_answer) > 0, item.item_id)
            expect(render(item.params) == item.prompt, "arith render drift")
            expect(str(answer_of(item.params)) == item.oracle_answer, "arith oracle drift")
            expect("####" not in item.prompt, "marker in prompt")
        elif item.family == "graph_path":
            expect(item.params["hops"] >= 2, item.params)
            expect(str(graph_answer(item.params)) == item.oracle_answer, "graph oracle")
            expect(6 <= item.params["n_nodes"] <= 10, item.params["n_nodes"])
        else:
            expect(item.params["n_lines"] <= 15, item.params["n_lines"])
            stdout, err = run_program(item.params["source"])
            expect(err == "" and stdout == item.oracle_answer, (err, stdout, item.oracle_answer))
            for token in ("import ", "open(", "input(", "random"):
                expect(token not in item.params["source"], token)
    reloaded = loads_jsonl(dumps_jsonl(first))
    expect(question_set_sha256(reloaded) == question_set_sha256(first), "reload")
    print("batch", len(first), "qsha", question_set_sha256(first)[:12])


def test_grade():
    expect(extract_integer("see #### 1,204.0\n") == "1204", "canon")
    expect(extract_integer("no hash, the last is 7 then 8") == "8", "fallback")
    expect(extract_integer("none") is None, "invalid")
    expect(extract_gold("work\n#### 18") == "18", "gold")
    expect(grade_answer("arith_word", "18", "because #### 18").correct, "grade ok")
    bad = grade_answer("arith_word", "18", "I think 17")
    expect(bad.correct is False and bad.invalid is False and bad.parsed == "17", bad)
    inv = grade_answer("graph_path", "4", "no numbers here")
    expect(inv.invalid and not inv.correct, inv)
    fenced = "reasoning\n```text\nhello \nworld\n```\n"
    expect(normalize_output(extract_fenced(fenced)) == "hello\nworld", extract_fenced(fenced))
    graded = grade_answer("code_output", "hello\nworld", fenced)
    expect(graded.correct and not graded.invalid, graded)
    missing = grade_answer("code_output", "hello", "hello")
    expect(missing.invalid, "fence required")


def test_tarball():
    if not hasattr(test_tarball, "ok"):
        pass
    one = build_generator_tarball(ROOT)
    two = build_generator_tarball(ROOT)
    expect(one == two and len(one) < 100 * 1024, f"tar bytes {len(one)}")
    print("tarball", len(one), hashlib.sha256(one).hexdigest()[:12])


def main():
    test_rng_stable()
    test_seed_rule()
    test_arith_manual()
    test_graph_dijkstra()
    test_grade()
    test_batch()
    test_tarball()
    print("TEST_GENERATORS_OK")


if __name__ == "__main__":
    main()
