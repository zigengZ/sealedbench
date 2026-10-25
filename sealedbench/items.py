"""Canonical items and the question-set hash.

JSON objects use sorted keys, no extra whitespace, and ASCII escapes.
The question-set hash is SHA-256 of the UTF-8 JSONL bytes in item order.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


@dataclass
class Item:
    item_id: str
    prompt: str
    oracle_answer: str
    family: str
    params: dict

    def to_obj(self) -> dict:
        return {
            "family": self.family,
            "item_id": self.item_id,
            "oracle_answer": self.oracle_answer,
            "params": self.params,
            "prompt": self.prompt,
        }

    def to_json_line(self) -> str:
        return canon(self.to_obj()) + "\n"


def question_set_sha256(items: list[Item]) -> str:
    digest = hashlib.sha256()
    for item in items:
        digest.update(item.to_json_line().encode("utf-8"))
    return digest.hexdigest()


def dumps_jsonl(items: list[Item]) -> bytes:
    return "".join(item.to_json_line() for item in items).encode("utf-8")


def loads_jsonl(data: bytes) -> list[Item]:
    items = []
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        items.append(
            Item(
                item_id=obj["item_id"],
                prompt=obj["prompt"],
                oracle_answer=obj["oracle_answer"],
                family=obj["family"],
                params=obj["params"],
            )
        )
    return items
