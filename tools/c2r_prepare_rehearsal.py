#!/usr/bin/env python3
"""Build b2r with the v2 seal primitives and the PUBLIC test secret. No uploads."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sealedbench.v2.tarball import build_v2_tarball
from sealedbench.v2.reference_set import build_reference
from sealedbench.v2.spec import TEST_SECRET, CHAIN_HASH
from sealedbench.v2.manifest_doc import build_manifest, dumps_manifest
from sealedbench.protocol import GENESIS


def fake(data):
    return base64.urlsafe_b64encode(hashlib.sha256(b'REHEARSAL ONLY\0' + data).digest()).decode().rstrip('=')


def main():
    if ROOT.name != 'sealedbench-b2r' or os.environ.get('SEALEDBENCH_DRY_UPLOAD') != '1':
        raise SystemExit('requires the b2r worktree and dry-upload mode')
    dest = ROOT / 'results/batches/b2r'
    dest.mkdir(parents=True, exist_ok=True)
    gateway = dest / 'gateway'
    gateway.mkdir(exist_ok=True)
    plain = build_v2_tarball(ROOT, TEST_SECRET)
    round_num = 33000000  # a published past vector, not a target round
    cmd = [os.environ['TLE'], '-e', '-n', 'https://api.drand.sh/', '-c', CHAIN_HASH, '-r', str(round_num), '-a', '-f']
    proc = subprocess.run(cmd, input=plain, capture_output=True, check=True, timeout=180)
    armor = proc.stdout
    reference = build_reference(ROOT, n=2)
    ref = reference['file_bytes']
    tx = {'batch_id': 'b2r', 'dry_run': True, 'items': {}}
    for kind, blob in [('generator-ciphertext', armor), ('reference', ref)]:
        tx['items'][kind] = {'txid': fake(blob), 'sha256': hashlib.sha256(blob).hexdigest(), 'bytes': len(blob), 'dry_run': True}
        (gateway / fake(blob)).write_bytes(blob)
    unlock = GENESIS + (round_num - 1) * 3
    manifest = build_manifest(ROOT, batch_id='b2r', release_round=round_num, unlock_unix=unlock,
        unlock_utc=datetime.fromtimestamp(unlock, timezone.utc).isoformat(), peer_id='b2r',
        peer_ciphertext_sha256=hashlib.sha256(armor).hexdigest(), ciphertext_txid=fake(armor),
        ciphertext_sha256=hashlib.sha256(armor).hexdigest(), ciphertext_bytes=len(armor),
        plaintext_sha256=hashlib.sha256(plain).hexdigest(), plaintext_bytes=len(plain),
        reference_txid=fake(ref), reference_sha256=hashlib.sha256(ref).hexdigest(), reference_bytes=len(ref), vectors=[])
    for family in manifest['generator']['families']:
        family['n'] = 2
    manifest['reference'].update(n=2, indexes='0..1')
    manifest['counts_note'] = 'REHEARSAL ONLY: 2 per family plus 2 reference, 4 models'
    data = dumps_manifest(manifest)
    (dest / 'manifest.json').write_bytes(data)
    tx['items']['manifest'] = {'txid': fake(data), 'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'dry_run': True}
    (gateway / fake(data)).write_bytes(data)
    (dest / 'txids.json').write_text(json.dumps(tx, indent=2) + '\n')
    (dest / 'reference.json').write_bytes(ref)
    (dest / 'generator.tlock').write_bytes(armor)
    print(f'REHEARSAL_SEALED round={round_num} bytes={len(armor)} models={len(manifest["models"])}')

if __name__ == '__main__':
    main()
