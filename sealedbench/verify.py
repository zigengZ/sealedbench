"""Verify a published batch from gateways.

Exit 0 is PASS, 1 is a hard FAIL, 2 is UNKNOWN or INVALID.
HTTP 404, 429, timeouts, and connection errors are UNKNOWN, never FAIL.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import time
from pathlib import Path

from sealedbench.grade import grade_answer
from sealedbench.items import canon, loads_jsonl, question_set_sha256
from sealedbench.net import Fetcher
from sealedbench.observe import before_unlock, observe_item
from sealedbench.reference import reference_questions
from sealedbench.release import FetchError, fetch_beacon, fetch_matching, js_decrypt, regenerate, tle_decrypt
from sealedbench.wilson import wald_diff, wilson

from sealedbench.paths import cache_root, repo_root

ROOT = repo_root()
CACHE = cache_root()
DEFAULT_GATEWAYS = (
    "https://ar-io.dev",
    "https://turbo-gateway.com",
    "https://arweave.net",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def classify_inclusion(flag: str, claimed_valid: bool) -> str:
    """A missing block timestamp is UNKNOWN even when the index claims valid."""
    del claimed_valid
    if flag == "PASS":
        return "PASS"
    if flag == "FAIL":
        return "FAIL"
    return "UNKNOWN"


def classify_fetch_error(exc: BaseException) -> str:
    if getattr(exc, "kind", None) == "mismatch":
        return "FAIL"
    return "UNKNOWN"


def classify_gateway_hits(hits: list) -> str:
    matches = [hit for hit in hits if hit.get("match")]
    contradictions = [
        hit for hit in hits if hit.get("http") == 200 and hit.get("sha256") and not hit.get("match")
    ]
    if matches:
        return "PASS"
    if contradictions:
        return "FAIL"
    return "UNKNOWN"


def classify_payload(payload: dict | None) -> str:
    payload = payload or {}
    if payload.get("ok"):
        return "PASS"
    http = payload.get("http")
    if http in (200, 206) and payload.get("sha256") and not payload.get("ok"):
        return "FAIL"
    return "UNKNOWN"


def result_exit(rows: list) -> tuple[str, int]:
    fails = sum(1 for _name, status, _detail in rows if status == "FAIL")
    unknowns = sum(1 for _name, status, _detail in rows if status in ("UNKNOWN", "REPO-ONLY"))
    weaks = sum(1 for _name, status, _detail in rows if status == "WEAK")
    invalids = sum(1 for _name, status, _detail in rows if status == "INVALID")
    if fails:
        return "FAIL", 1
    if unknowns:
        return "UNKNOWN", 2
    if invalids:
        return "INVALID", 2
    if weaks:
        return "WEAK", 2
    return "PASS", 0


def _family_counts(grades: list) -> tuple[int, int, int]:
    return (
        len(grades),
        sum(1 for grade in grades if grade.correct),
        sum(1 for grade in grades if grade.invalid),
    )


def verify_index(txid: str, gateways: list[str] | None = None, batch: str = "b1") -> int:
    started = time.time()
    fetcher = Fetcher()
    hosts = tuple(gateways) if gateways else DEFAULT_GATEWAYS
    rows = []

    def add(name: str, status: str, detail: str) -> None:
        rows.append((name, status, detail))

    bodies = {}
    for host in hosts:
        status, _headers, body = fetcher.get(f"{host}/{txid}")
        digest = _sha(body) if body else None
        bodies[host] = {"http": status, "sha256": digest, "body": body if status == 200 else None, "bytes": len(body)}
    good = [(host, rec) for host, rec in bodies.items() if rec["body"] is not None]
    same = len({rec["sha256"] for _host, rec in good}) == 1 and len(good) >= 2
    if same:
        index_body = good[0][1]["body"]
        add("index", "PASS", f"{len(good)} gateways agree sha256={good[0][1]['sha256']}")
    else:
        summary = " ".join(f"{host}={rec['http']}:{rec['sha256']}" for host, rec in bodies.items())
        hashes = {rec["sha256"] for _host, rec in good}
        if len(hashes) > 1:
            add("index", "FAIL", summary)
        else:
            add("index", "UNKNOWN", summary)
        index_body = good[0][1]["body"] if good else None
    if index_body is None:
        return _emit(rows, started, fetcher, batch, txid)
    index = json.loads(index_body)
    manifest_id = index["manifest_txid"]
    cipher_id = index["ciphertext_txid"]
    try:
        manifest_got = fetch_matching(manifest_id, index["manifest_sha256"], fetcher)
        manifest_body = manifest_got["body"]
        add("manifest sha256", "PASS", index["manifest_sha256"])
    except Exception as exc:
        add("manifest sha256", classify_fetch_error(exc), str(exc)[:300])
        return _emit(rows, started, fetcher, batch, txid)
    manifest = json.loads(manifest_body)
    if not (manifest.get("ciphertext") or {}).get("txid"):
        add(
            "ciphertext txid binding",
            "WEAK",
            "v1 manifest binds ciphertext sha256 but not the txid. The index that names the txid is written after the run.",
        )
    try:
        cipher_got = fetch_matching(cipher_id, index["ciphertext_sha256"], fetcher)
        armor = cipher_got["body"]
        add("ciphertext sha256", "PASS", index["ciphertext_sha256"])
    except Exception as exc:
        add("ciphertext sha256", classify_fetch_error(exc), str(exc)[:300])
        return _emit(rows, started, fetcher, batch, txid)
    if manifest.get("ciphertext", {}).get("sha256") not in (None, index["ciphertext_sha256"]):
        add("manifest ciphertext field", "FAIL", str(manifest.get("ciphertext", {}).get("sha256")))
    else:
        add("manifest ciphertext field", "PASS", "matches index")

    for label, got in (("manifest served", manifest_got), ("ciphertext served", cipher_got)):
        parts = []
        for hit in got["gateways"]:
            if hit["match"]:
                parts.append(f"{hit['host']} PASS")
            elif hit["http"] == 200 and hit.get("sha256"):
                parts.append(f"{hit['host']} FAIL")
            else:
                parts.append(f"{hit['host']} UNKNOWN({hit['http']})")
        add(label, classify_gateway_hits(got["gateways"]), " ".join(parts))

    manifest_obs = observe_item(manifest_id, _sha(manifest_body), fetcher)
    cipher_obs = observe_item(cipher_id, _sha(armor), fetcher)
    for label, obs in (("manifest L1", manifest_obs), ("ciphertext L1", cipher_obs)):
        flag = before_unlock(obs, manifest["unlock_unix"])
        block = obs.get("block") or {}
        source = (obs.get("l1") or {}).get("source")
        detail = f"{flag} source={source} ts={block.get('timestamp_utc')} height={(obs.get('l1') or {}).get('height')}"
        claimed_valid = bool(index.get("batch_valid", True))
        add(label, classify_inclusion(flag, claimed_valid), detail)
        payload = obs.get("payload") or {}
        payload_status = classify_payload(payload)
        if payload_status == "PASS":
            add(label + " payload", "PASS", f"offset={payload.get('absolute_offset')} len={payload.get('length')}")
        else:
            add(
                label + " payload",
                payload_status,
                json.dumps({k: payload.get(k) for k in ("http", "got_bytes", "sha256")}),
            )

    indexed = _indexed(fetcher, [manifest_id, cipher_id])
    add("indexed", "INFO", indexed)

    try:
        beacon = fetch_beacon(manifest["release_round"], fetcher)
    except Exception as exc:
        add("beacon", "UNKNOWN", str(exc)[:300])
        return _emit(rows, started, fetcher, batch, txid)
    code, plain, err = tle_decrypt(armor)
    if code == 0 and _sha(plain) == manifest["generator"]["generator_sha256"]:
        add("beacon+tle", "PASS", "tle -d decrypted; that verifies the quicknet BLS signature")
    else:
        add("beacon+tle", "FAIL", f"exit={code} {err[-240:]}")
        plain = b""
    js_code, js_plain, js_text = js_decrypt(armor, CACHE / "work" / "verify-js")
    if code == 0 and js_code == 0 and js_plain == plain:
        add("tlock-js", "PASS", "matches tle plaintext")
    elif code == 0 and js_code != 0:
        add("tlock-js", "INFO", "tle already verified the signature; js said " + js_text.strip()[-180:])
    else:
        add("tlock-js", "FAIL", js_text.strip()[-180:])

    if plain:
        counts = {row["name"]: int(row["n"]) for row in manifest["generator"]["families"]}
        jsonl = regenerate(plain, manifest["drand"]["chain_hash"], manifest["release_round"], beacon["randomness"], counts)
        items = loads_jsonl(jsonl)
        qhash = question_set_sha256(items)
        if qhash == index.get("question_set_sha256"):
            add("question set", "PASS", qhash)
        else:
            add("question set", "FAIL", f"rebuilt {qhash} index {index.get('question_set_sha256')}")
            items = []
    else:
        items = []

    scores_body, scores_status, scores_detail = _fetch_scores(fetcher, index)
    if scores_body is None:
        add("scores fetch", scores_status, scores_detail)
        scores = None
    else:
        if _sha(scores_body) != index.get("results_sha256"):
            add("scores sha256", "FAIL", _sha(scores_body))
            scores = None
        else:
            add("scores sha256", "PASS", index["results_sha256"])
            scores = json.loads(scores_body)
    archive, archive_status, archive_detail = _load_archive(fetcher, index)
    add("completions", archive_status, archive_detail)
    if archive is not None and items and scores is not None:
        rebuilt = _regrade(manifest, items, archive, scores)
        if rebuilt is None:
            add("regrade", "FAIL", "could not regrade every published completion")
        else:
            add("regrade", "PASS" if rebuilt["ok"] else "FAIL", rebuilt["detail"])
    claimed = index.get("batch_valid", True)
    m_flag = before_unlock(manifest_obs, manifest["unlock_unix"])
    c_flag = before_unlock(cipher_obs, manifest["unlock_unix"])
    if m_flag == "UNKNOWN" or c_flag == "UNKNOWN":
        add("batch validity", "UNKNOWN", f"claimed_valid={claimed} manifest={m_flag} ciphertext={c_flag}")
    elif m_flag == "PASS" and c_flag == "PASS":
        note = "both bundles are in L1 before unlock"
        if claimed is False:
            note += "; the release-time flag was false and is not decisive"
        add("batch validity", "PASS", note)
    elif claimed is False and (m_flag == "FAIL" or c_flag == "FAIL"):
        add("batch validity", "INVALID", "publication marks the batch INVALID and inclusion is not before unlock")
    else:
        add("batch validity", "FAIL", f"claimed_valid={claimed} manifest={m_flag} ciphertext={c_flag}")

    return _emit(rows, started, fetcher, batch, txid)


def _indexed(fetcher: Fetcher, ids: list[str]) -> str:
    query = {
        "query": "query($ids:[ID!]!){ transactions(ids:$ids){ edges { node { id block { height timestamp } } } } }",
        "variables": {"ids": ids},
    }
    payload = json.dumps(query).encode("utf-8")
    parts = []
    for host in ("https://ar-io.dev/graphql",):
        status, _headers, body = fetcher.get(host, data=payload, headers={"Content-Type": "application/json"})
        found = []
        try:
            parsed = json.loads(body)
            edges = parsed.get("data", {}).get("transactions", {}).get("edges", []) or []
            for edge in edges:
                node = edge.get("node") or {}
                block = node.get("block")
                if node.get("id"):
                    found.append(f"{node['id'][:6]}:{'block' if block else 'unconfirmed'}")
        except json.JSONDecodeError:
            found = ["bad-json"]
        parts.append(f"{host} HTTP {status} {','.join(found) if found else 'not-indexed'}")
    return " | ".join(parts)


def _local_bytes(path: str | None, expected: str | None) -> bytes | None:
    if not path or not expected:
        return None
    file = ROOT / path
    if not file.exists():
        return None
    data = file.read_bytes()
    if _sha(data) != expected:
        return None
    return data


def _fetch_scores(fetcher: Fetcher, index: dict):
    txid = index.get("results_txid")
    expected = index.get("results_sha256")
    if txid and expected:
        try:
            got = fetch_matching(txid, expected, fetcher)
            return got["body"], "PASS", expected
        except FetchError as exc:
            return None, classify_fetch_error(exc), str(exc)[:300]
        except Exception as exc:
            return None, "UNKNOWN", str(exc)[:300]
    local = _local_bytes(index.get("results_repo_path"), expected)
    if local is not None:
        return local, "REPO-ONLY", "results were not fetched from a gateway"
    return None, "UNKNOWN", "results txid not served and no local file matched"


def _load_archive(fetcher: Fetcher, index: dict):
    comp = index.get("completions") or {}
    expected = comp.get("sha256")
    if comp.get("uploaded") and comp.get("txid") and expected:
        try:
            got = fetch_matching(comp["txid"], expected, fetcher)
            return got["body"], "PASS", f"sha256={expected} bytes={len(got['body'])}"
        except FetchError as exc:
            local = _local_bytes(comp.get("repo_path"), expected)
            if local is not None and exc.kind != "mismatch":
                return local, "REPO-ONLY", "gateway unavailable; local file matches the index hash"
            return None, classify_fetch_error(exc), str(exc)[:300]
        except Exception as exc:
            return None, "UNKNOWN", str(exc)[:300]
    local = _local_bytes(comp.get("repo_path"), expected)
    if local is not None:
        return local, "REPO-ONLY", "completions are not on Arweave; local file matches the index hash"
    return None, "UNKNOWN", "completions were not uploaded and no local file matched"


def _regrade(manifest: dict, items: list, archive: bytes, scores: dict) -> dict | None:
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            extracted = tar.extractfile(member)
            if extracted is None:
                continue
            files[member.name] = extracted.read().decode("utf-8", errors="replace")
    reference = reference_questions()
    detail = []
    ok = True
    notes = []
    for model in manifest["models"]:
        by_family = {name: [] for name in ("arith_word", "code_output", "graph_path")}
        for item in items:
            rel = f"runs/{model['id']}/{item['item_id']}.txt"
            if rel not in files:
                return {"ok": False, "detail": f"missing {rel}"}
            grade = grade_answer(item["family"], item["oracle_answer"], files[rel])
            by_family[item["family"]].append(grade)
            detail.append(
                canon(
                    {
                        "correct": grade.correct,
                        "family": item["family"],
                        "invalid": grade.invalid,
                        "item_id": item["item_id"],
                        "model": model["id"],
                        "oracle": grade.oracle,
                        "parsed": grade.parsed,
                    }
                )
            )
        gsm = []
        for row in reference:
            rel = f"reference_runs/{model['id']}/{row['item_id']}.txt"
            if rel not in files:
                return {"ok": False, "detail": f"missing {rel}"}
            grade = grade_answer("gsm8k", row["oracle_answer"], files[rel])
            gsm.append(grade)
            detail.append(
                canon(
                    {
                        "correct": grade.correct,
                        "family": "gsm8k",
                        "invalid": grade.invalid,
                        "item_id": row["item_id"],
                        "model": model["id"],
                        "oracle": grade.oracle,
                        "parsed": grade.parsed,
                    }
                )
            )
        published = scores["models"][model["id"]]
        for family, grades in by_family.items():
            n, correct, invalid = _family_counts(grades)
            block = published["families"][family]
            if (n, correct, invalid) != (block["n"], block["correct"], block["invalid"]):
                ok = False
                notes.append(f"{model['id']} {family} got {(n, correct, invalid)} published {(block['n'], block['correct'], block['invalid'])}")
            lo, hi = wilson(correct, n)
            pub_lo, pub_hi = block["wilson95"]
            if pub_lo is not None and (abs(lo - pub_lo) > 1e-9 or abs(hi - pub_hi) > 1e-9):
                ok = False
                notes.append(f"{model['id']} {family} wilson drift")
        n, correct, invalid = _family_counts(gsm)
        block = published["gsm8k120"]
        if (n, correct, invalid) != (block["n"], block["correct"], block["invalid"]):
            ok = False
            notes.append(f"{model['id']} gsm8k got {(n, correct, invalid)}")
        arith_n, arith_correct, _arith_invalid = _family_counts(by_family["arith_word"])
        gap, lo, hi = wald_diff(arith_correct, arith_n, correct, n)
        pub_gap = published["gap_arith_minus_gsm8k"]
        if pub_gap["gap"] is not None and abs(pub_gap["gap"] - gap) > 1e-9:
            ok = False
            notes.append(f"{model['id']} gap drift")
        del lo, hi
    detail_bytes = ("\n".join(detail) + "\n").encode("utf-8")
    detail_sha = hashlib.sha256(detail_bytes).hexdigest()
    if detail_sha != scores.get("grade_detail_sha256"):
        ok = False
        notes.append(f"detail sha {detail_sha} != {scores.get('grade_detail_sha256')}")
    if scores.get("batch_valid") != bool(scores.get("batch_valid")):
        pass
    return {"ok": ok, "detail": "counts and detail hash match" if ok else "; ".join(notes)}


def _emit(rows, started, fetcher: Fetcher, batch: str, txid: str) -> int:
    wall = time.time() - started
    lines = [f"SealedBench verify {txid}", ""]
    for name, status, detail in rows:
        lines.append(f"{status:<8} {name}: {detail}")
    result, exit_code = result_exit(rows)
    fails = sum(1 for _name, status, _detail in rows if status == "FAIL")
    lines.append("")
    lines.append(
        f"RESULT {result} fails={fails} exit={exit_code} wall={wall:.1f}s "
        f"downloaded={fetcher.downloaded} bytes requests={fetcher.calls}"
    )
    lines.append("HTTP 404, 429, and timeouts are UNKNOWN, not FAIL. Exit 2 is not a hard failure.")
    text = "\n".join(lines) + "\n"
    print(text, end="")
    out = ROOT / "results" / "batches" / batch / "verify_output.txt"
    if out.parent.exists():
        out.write_text(text)
    return exit_code
