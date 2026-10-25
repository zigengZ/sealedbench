"""Shortest-path length on a random connected weighted undirected graph.

Nodes are names. Edges have integer weights from 1 to 9. The queried pair's
shortest path has at least two edges, so a single-edge answer is rejected.
The oracle is Dijkstra. The answer is the total weight, written as an integer.
"""

from __future__ import annotations

import heapq

from sealedbench.items import Item
from sealedbench.rng import RNG

NODES = [
    "Ash", "Bay", "Cleo", "Drew", "Eden", "Fern", "Glen", "Hart",
    "Indigo", "Jules", "Kai", "Lark", "Moss", "Nell", "Oak", "Poe",
    "Quill", "Reed", "Sage", "Tess", "Uri", "Vale", "West", "Xen",
    "York", "Zed", "Amber", "Blair", "Cedar", "Dove",
]

INF = 10**18


def shortest(nodes: list[str], edges: list[list], src: str) -> tuple[dict, dict]:
    """Return (distance, hop count). Ties prefer fewer hops."""
    adj = {name: [] for name in nodes}
    for edge in edges:
        a, b, weight = edge[0], edge[1], int(edge[2])
        adj[a].append((b, weight))
        adj[b].append((a, weight))
    dist = {name: INF for name in nodes}
    hops = {name: 10**9 for name in nodes}
    dist[src] = 0
    hops[src] = 0
    heap = [(0, 0, src)]
    while heap:
        cur_d, cur_h, node = heapq.heappop(heap)
        if cur_d != dist[node] or cur_h != hops[node]:
            continue
        for nxt, weight in adj[node]:
            nd, nh = cur_d + weight, cur_h + 1
            if nd < dist[nxt] or (nd == dist[nxt] and nh < hops[nxt]):
                dist[nxt] = nd
                hops[nxt] = nh
                heapq.heappush(heap, (nd, nh, nxt))
    return dist, hops


def _direct(edges: list[list], a: str, b: str) -> int | None:
    for edge in edges:
        if {edge[0], edge[1]} == {a, b}:
            return int(edge[2])
    return None


def answer_of(params: dict) -> int | None:
    dist, hops = shortest(params["nodes"], params["edges"], params["src"])
    dst = params["dst"]
    if dist[dst] >= INF or hops[dst] < 2 or dist[dst] <= 0:
        return None
    direct = _direct(params["edges"], params["src"], dst)
    if direct is not None and direct <= dist[dst]:
        return None
    return int(dist[dst])


def render(params: dict) -> str:
    lines = [
        "Undirected weighted graph.",
        "Nodes: " + ", ".join(params["nodes"]),
        "Edges:",
    ]
    for edge in params["edges"]:
        lines.append(f"{edge[0]} {edge[1]} {edge[2]}")
    lines.append(
        f"What is the total weight of the shortest path between {params['src']} and {params['dst']}?"
    )
    return "\n".join(lines)


def _sample(rng: RNG) -> dict | None:
    count = rng.randint(6, 10)
    nodes = sorted(rng.sample(NODES, count))
    order = rng.shuffle(nodes)
    edge_map: dict[tuple[str, str], int] = {}
    for index in range(1, len(order)):
        parent = order[rng.randint(0, index - 1)]
        a, b = sorted((order[index], parent))
        edge_map[(a, b)] = rng.randint(1, 9)
    extra_target = rng.randint(2, 5)
    added = 0
    guard = 0
    while added < extra_target and guard < 40:
        guard += 1
        a, b = rng.sample(nodes, 2)
        a, b = sorted((a, b))
        if a == b or (a, b) in edge_map:
            continue
        edge_map[(a, b)] = rng.randint(1, 9)
        added += 1
    edges = [[a, b, weight] for (a, b), weight in sorted(edge_map.items())]
    pairs = []
    for src in nodes:
        dist, hops = shortest(nodes, edges, src)
        for dst in nodes:
            if dst <= src:
                continue
            if hops[dst] < 2 or dist[dst] >= INF or dist[dst] <= 0:
                continue
            direct = _direct(edges, src, dst)
            if direct is not None and direct <= dist[dst]:
                continue
            pairs.append((src, dst, int(dist[dst]), int(hops[dst])))
    if not pairs:
        return None
    src, dst, dist, hops = rng.choice(pairs)
    return {
        "nodes": nodes,
        "edges": edges,
        "src": src,
        "dst": dst,
        "distance": dist,
        "hops": hops,
        "n_nodes": len(nodes),
        "n_edges": len(edges),
    }


def generate(seed_bytes: bytes, n: int) -> list[Item]:
    rng = RNG(seed_bytes)
    items: list[Item] = []
    seen: set[str] = set()
    attempts = 0
    limit = max(20, n * 40)
    while len(items) < n:
        attempts += 1
        if attempts > limit:
            raise RuntimeError(f"graph_path produced {len(items)} of {n} after {attempts} draws")
        params = _sample(rng)
        if params is None:
            continue
        answer = answer_of(params)
        if answer is None or answer == 0 or answer != params["distance"]:
            continue
        prompt = render(params)
        if prompt in seen or "####" in prompt:
            continue
        seen.add(prompt)
        items.append(
            Item(
                item_id=f"graph_path-{len(items):04d}",
                prompt=prompt,
                oracle_answer=str(answer),
                family="graph_path",
                params=params,
            )
        )
    return items
