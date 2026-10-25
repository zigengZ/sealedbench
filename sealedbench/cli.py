"""Command line. `python3 -m sealedbench <command>`."""

from __future__ import annotations

import argparse
import sys



def _verify_v2(batch: str, txid: str) -> int:
    """Check a v2 batch. The txid must be the published index, then the v2 verifier runs.

    v2 does not accept a gateway list. Its two independent gateways are fixed.
    """
    import json

    from sealedbench.paths import repo_root

    path = repo_root() / "results" / "batches" / batch / "txids.json"
    if not path.is_file():
        print(f"no published index record for {batch}")
        return 2
    try:
        published = json.loads(path.read_text())["items"]["index"]["txid"]
    except (KeyError, TypeError, json.JSONDecodeError):
        print(f"no published index transaction for {batch}")
        return 2
    if txid != published:
        print(f"txid {txid} does not match the published index {published}")
        return 1
    from sealedbench.v2.verification import verify as verify_v2

    return verify_v2(batch)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sealedbench")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ent = sub.add_parser("entropy", help="measure generator diversity")
    ent.add_argument("--family", required=True)
    ent.add_argument("--seeds", type=int, default=1000)
    ent.add_argument("--n", type=int, default=40)
    ent.add_argument("--workers", type=int, default=4)

    sub.add_parser("freeze-reference", help="write the GSM8K-120 reference record")

    sub.add_parser("prepare-seal", help="tarball, tlock, and write batch manifests")

    pub = sub.add_parser("publish", help="upload scores and the final index")
    pub.add_argument("--batch", default="b1")

    rel = sub.add_parser("release", help="decrypt a released batch and write items")
    rel.add_argument("--batch", default="b1")

    inf = sub.add_parser("infer", help="run frozen llama.cpp completions")
    inf.add_argument("--batch", default="b1")
    inf.add_argument("--models", nargs="*", default=None)
    inf.add_argument("--limit", type=int, default=None, help="run only the first N exam items")

    scr = sub.add_parser("score", help="grade a batch and write scores")
    scr.add_argument("--batch", default="b1")

    ver = sub.add_parser("verify", help="check a published batch from gateways")
    ver.add_argument("--txid", required=True)
    ver.add_argument("--gateways", nargs="*", default=None)
    ver.add_argument("--batch", default="b1")

    rep = sub.add_parser("replay", help="re-run the first k items and diff raw completions")
    rep.add_argument("--txid", default=None)
    rep.add_argument("--batch", default=None)
    rep.add_argument("--model", required=True)
    rep.add_argument("--items", type=int, required=True)

    args = parser.parse_args(argv)
    if args.cmd == "entropy":
        from sealedbench.entropy import run_entropy, write_report
        from sealedbench.paths import repo_root

        report = run_entropy(args.family, args.seeds, args.n, args.workers)
        out = repo_root() / "results" / "entropy"
        write_report(report, out)
        print(
            f"ENTROPY {report['family']} sets={report['distinct_question_sets']}/{report['seeds']} "
            f"prompts={report['distinct_prompts']} jaccard={report['mean_pairwise_jaccard']:.4f} "
            f"gate={'PASS' if report['gate_pass'] else 'FAIL'}"
        )
        return 0 if report["gate_pass"] else 2
    if args.cmd == "freeze-reference":
        from sealedbench.reference import freeze_reference
        import json
        from pathlib import Path

        from sealedbench.paths import repo_root

        record = freeze_reference()
        path = repo_root() / "results" / "reference" / "gsm8k120.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        print(f"REFERENCE n={record['n']} list_sha256={record['list_sha256']} source_sha256={record['source_sha256']}")
        return 0
    if args.cmd == "release":
        from sealedbench.infer import load_manifest

        if load_manifest(args.batch).get("protocol_version") == "sealedbench/v2":
            from sealedbench.v2.run_release import release_batch as release_v2

            return release_v2(args.batch)
        from sealedbench.release import release_batch

        return release_batch(args.batch)
    if args.cmd == "infer":
        from sealedbench.infer import infer_batch

        return infer_batch(args.batch, models=args.models, limit=args.limit)
    if args.cmd == "score":
        from sealedbench.infer import load_manifest

        if load_manifest(args.batch).get("protocol_version") == "sealedbench/v2":
            from sealedbench.v2.scoring import score_batch as score_v2

            return score_v2(args.batch)
        from sealedbench.score import score_batch

        return score_batch(args.batch)
    if args.cmd == "verify":
        from sealedbench.infer import load_manifest

        if load_manifest(args.batch).get("protocol_version") == "sealedbench/v2":
            return _verify_v2(args.batch, args.txid)
        from sealedbench.verify import verify_index

        return verify_index(args.txid, gateways=args.gateways, batch=args.batch)
    if args.cmd == "replay":
        from sealedbench.replay import replay

        return replay(model=args.model, k=args.items, txid=args.txid, batch=args.batch)
    if args.cmd == "prepare-seal":
        from sealedbench.seal import prepare_seal

        return prepare_seal()
    if args.cmd == "publish":
        from sealedbench.publish import publish_batch

        return publish_batch(args.batch)
    parser.error(f"unknown command {args.cmd}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
