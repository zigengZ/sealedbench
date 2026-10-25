#!/usr/bin/env python3
"""Write results/day1/summary.md from the day-1 artifacts."""

from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/codes/sealedbench")
DAY1 = ROOT / "results" / "day1"


def load(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def percentile(sorted_values: list[float], p: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return sorted_values[f]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def stats(values: list[float]) -> dict:
    xs = sorted(values)
    return {
        "n": len(xs),
        "p50": percentile(xs, 0.5),
        "p90": percentile(xs, 0.9),
        "p95": percentile(xs, 0.95),
        "max": xs[-1] if xs else None,
    }


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def parse_iso(text: str | None) -> datetime | None:
    if not text:
        return None
    for fmt_s in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(text, fmt_s).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def iso_to_unix(text: str | None) -> float | None:
    parsed = parse_iso(text)
    return parsed.timestamp() if parsed else None


HTTP_LINE = re.compile(r"^(\S+) HTTP (\d+) bytes ")
POLLER_START = re.compile(r"poller_start (\S+)")


def gql_responses(path: Path) -> list[tuple[str, str]]:
    """One entry per poller response line. ERROR echoes of the same response are skipped."""
    if not path.exists():
        return []
    out = []
    for line in path.read_text(errors="replace").splitlines():
        match = HTTP_LINE.match(line)
        if match:
            out.append((match.group(1), match.group(2)))
    return out


def poller_start_from_log(path: Path) -> str | None:
    if not path.exists():
        return None
    match = POLLER_START.search(path.read_text(errors="replace"))
    return match.group(1) if match else None


def main() -> None:
    manifest = load(DAY1 / "manifest.json", {})
    probes = manifest.get("probes", [])
    verify_rows = {r["probe_id"]: r for r in load(DAY1 / "receipt_verify.json", [])}
    poll = load(DAY1 / "poll" / "final.json") or load(DAY1 / "poll" / "latest.json") or {}
    poll_rows = {r["probe_id"]: r for r in poll.get("probes", [])}
    tsa = load(DAY1 / "tsa" / "summary.json") or {"rows": load(DAY1 / "tsa" / "partial.json", [])}
    tsa_rows = {}
    for row in tsa.get("rows", []):
        tsa_rows.setdefault(row["probe_id"], {})[row["tsa"]] = row

    lines = ["# Day-1 falsifiable checks", ""]
    lines.append(f"Generated from artifacts under `results/day1/`.")
    lines.append("")
    lines.append("## Per probe")
    lines.append("")
    lines.append(
        "| probe | round | tx id | receipt verify | slack s | block−receipt s | first-seen−receipt s | deadline−inclusion | conf | arweave | ario | go | js | freetsa Δs | digicert Δs | sectigo Δs |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")

    block_deltas = []
    seen_deltas = []
    for probe in probes:
        pid = probe["probe_id"]
        v = verify_rows.get(pid, {})
        receipt = load(DAY1 / "receipts" / f"{pid}.json", {})
        p = poll_rows.get(pid, {})
        dec = load(DAY1 / "decrypt" / f"{pid}.json", {})
        gateways = {}
        served = dec.get("attempts", [])
        if served:
            gateways = served[-1].get("gateways", {})
        ar_status = gateways.get("https://arweave.net", {}).get("http_status")
        ao_status = gateways.get("https://ario.zigza.xyz", {}).get("http_status")
        receipt_ms = receipt.get("timestamp")
        block_delta = None
        seen_delta = None
        if receipt_ms is not None and p.get("inclusion_timestamp_s") is not None:
            block_delta = p["inclusion_timestamp_s"] - receipt_ms / 1000
            block_deltas.append(block_delta)
        if receipt_ms is not None and p.get("first_seen_ms") is not None:
            seen_delta = (p["first_seen_ms"] - receipt_ms) / 1000
            seen_deltas.append(seen_delta)
        tsa_delta = {}
        for name in ("freetsa", "digicert", "sectigo"):
            row = tsa_rows.get(pid, {}).get(name)
            gen = iso_to_unix(row.get("gen_time_utc")) if row else None
            if gen is not None and receipt_ms is not None:
                tsa_delta[name] = gen - receipt_ms / 1000
            elif row and not row.get("ok"):
                tsa_delta[name] = "FAIL"
        lines.append(
            "| {pid} | {round} | `{tx}` | {ver} | {slack} | {bd} | {sd} | {dd} | {conf} | {ar} | {ao} | {go} | {js} | {ft} | {dg} | {sc} |".format(
                pid=pid,
                round=probe.get("round", ""),
                tx=receipt.get("id", ""),
                ver="PASS" if v.get("pass") else ("FAIL" if v else ""),
                slack=fmt(v.get("unlock_minus_upload_s")),
                bd=fmt(block_delta),
                sd=fmt(seen_delta),
                dd=fmt(p.get("deadline_minus_inclusion")),
                conf=fmt(p.get("confirmations")),
                ar=fmt(ar_status),
                ao=fmt(ao_status),
                go=fmt(dec.get("go_match")),
                js=fmt(dec.get("js_match")),
                ft=fmt(tsa_delta.get("freetsa")),
                dg=fmt(tsa_delta.get("digicert")),
                sc=fmt(tsa_delta.get("sectigo")),
            )
        )

    lines += ["", "## Latency percentiles", ""]
    lines.append("Method: linear interpolation, index `(n-1)*p` on the sorted sample. Times are seconds.")
    lines.append("")
    lines.append("| series | n | p50 | p90 | p95 | max |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for name, xs in (
        ("block timestamp − receipt timestamp", block_deltas),
        ("first GQL sighting − receipt timestamp", seen_deltas),
    ):
        st = stats(xs)
        lines.append(
            f"| {name} | {st['n']} | {fmt(st['p50'])} | {fmt(st['p90'])} | {fmt(st['p95'])} | {fmt(st['max'])} |"
        )
    not_included = poll.get("not_included")
    if not_included is None and poll_rows:
        not_included = sum(1 for r in poll_rows.values() if not r.get("included"))
    shown = not_included if not_included is not None else "unknown"
    lines.append("")
    if poll.get("finished_utc"):
        lines.append(f"Not included by the end of the poller: {shown}.")
        lines.append(f"Poller finished: {poll['finished_utc']}.")
    else:
        lines.append(f"Not included in the latest snapshot: {shown}.")
        if poll.get("updated_utc"):
            lines.append(
                f"Poller snapshot updated {poll['updated_utc']}. "
                "`final.json` is not written, so this is not the end of the poll."
            )
    start = poll.get("started_utc") or poller_start_from_log(DAY1 / "poll" / "poller.log")
    if start:
        lines.append(f"Poller process start recorded as {start}.")
    lines.append(
        f"Seen in GraphQL: {poll.get('seen_in_gql', 'unknown')}. "
        f"Included: {poll.get('included', 'unknown')}."
    )
    if not block_deltas:
        lines.append(
            "The block-timestamp sample is empty, so p50, p90, p95, and max are not defined for that series."
        )
    if not seen_deltas:
        lines.append(
            "The first-seen sample is empty, so p50, p90, p95, and max are not defined for that series."
        )
    responses = gql_responses(DAY1 / "poll" / "gql.log")
    if responses:
        counts = Counter(code for _, code in responses)
        count_text = ", ".join(f"HTTP {code} x {n}" for code, n in sorted(counts.items()))
        lines.append(
            "GraphQL `ids:` responses in `results/day1/poll/gql.log` "
            f"(response lines only): {count_text}. First {responses[0][0]}, last {responses[-1][0]}."
        )
        start_dt = parse_iso(start) if start else None
        if start_dt is not None:
            window = [(ts, code) for ts, code in responses if (parse_iso(ts) or start_dt) >= start_dt]
            wcounts = Counter(code for _, code in window)
            wtext = ", ".join(f"HTTP {code} x {n}" for code, n in sorted(wcounts.items()))
            lines.append(
                f"Responses at or after {start}: {wtext} ({len(window)} requests)."
            )

    lines += ["", "## Early decrypt", ""]
    early_ok = 0
    for probe in probes:
        go_ok = probe.get("early_decrypt", {}).get("go", {}).get("ok")
        js_ok = probe.get("early_decrypt", {}).get("js", {}).get("ok")
        if go_ok is False and js_ok is False:
            early_ok += 1
    lines.append(
        f"{early_ok}/{len(probes)} probes failed early decrypt in both Go tle and tlock-js. "
        "Exact errors are in `results/day1/manifest.json`."
    )

    served = Counter()
    go_yes = js_yes = 0
    for probe in probes:
        dec = load(DAY1 / "decrypt" / f"{probe['probe_id']}.json", {})
        if dec.get("go_match") is True:
            go_yes += 1
        if dec.get("js_match") is True:
            js_yes += 1
        if dec.get("served_by"):
            served[dec["served_by"]] += 1
    lines += ["", "## Decrypt after unlock", ""]
    lines.append(
        f"Go plaintext sha256 match: {go_yes}/{len(probes)}. "
        f"JS plaintext sha256 match: {js_yes}/{len(probes)}."
    )
    if served:
        served_text = ", ".join(f"{host} x {n}" for host, n in sorted(served.items()))
        lines.append(f"Gateway whose body matched the local ciphertext sha256: {served_text}.")
    lines.append(
        "Per-probe HTTP status in the table is the last fetch attempt. "
        "Earlier attempts, including the first 404s, are in `results/day1/decrypt/`."
    )

    tsa_series = {"freetsa": [], "digicert": [], "sectigo": []}
    for pid, by_name in tsa_rows.items():
        receipt = load(DAY1 / "receipts" / f"{pid}.json", {})
        receipt_ms = receipt.get("timestamp")
        if receipt_ms is None:
            continue
        for name, row in by_name.items():
            gen = iso_to_unix(row.get("gen_time_utc")) if row else None
            if gen is not None and name in tsa_series:
                tsa_series[name].append(gen - receipt_ms / 1000)
    lines += ["", "## RFC 3161 genTime minus receipt timestamp", ""]
    lines.append(
        "Seconds. p50 is linear interpolation at index `(n-1)*p`. "
        "Sectigo was requested last, with at least 16 seconds between its requests."
    )
    lines.append("")
    lines.append("| tsa | n | min | p50 | upper central | max |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for name, xs in tsa_series.items():
        st = stats(xs)
        ordered = sorted(xs)
        upper = ordered[len(ordered) // 2] if ordered else None
        minimum = min(xs) if xs else None
        lines.append(
            f"| {name} | {st['n']} | {fmt(minimum)} | {fmt(st['p50'])} | {fmt(upper)} | {fmt(st['max'])} |"
        )
    lines.append(
        "Upper central is the sorted value at index `n/2`. "
        "For these 20-point samples that is the figure recorded as the median in the D5 status line."
    )

    lines += ["", "## What was NOT measured", ""]
    lines += [
        "- Gateways other than `https://arweave.net/<id>` and `https://ario.zigza.xyz/<id>`.",
        "- Cross-machine or cross-CPU determinism of llama.cpp.",
        "- GPU inference and vLLM.",
        "- The exam generator G, a freeze manifest for a real exam, or grading of model answers to sealed questions.",
        "- Paid Turbo uploads, top-ups, or any wallet other than the throwaway address in `results/day1/WALLET.md`.",
        "- Data durability past the poller's 3 hour window, and confirmation depth past the poller's stop (10 confirmations, or the window ending).",
        "- Quants other than Q8_0, llama.cpp commits other than the pinned tag, and GSM8K items beyond the first 50 of the test split.",
        "- Tag-only Arweave GraphQL enumeration. Lookups used `transactions(ids:...)` only.",
        "- Whether a receipt signature would verify under a key other than the Turbo `/info` address pinned in `results/day1/turbo_info.json`.",
    ]
    lines.append("")
    (DAY1 / "summary.md").write_text("\n".join(lines))
    print(f"wrote {DAY1 / 'summary.md'}")


if __name__ == "__main__":
    main()
