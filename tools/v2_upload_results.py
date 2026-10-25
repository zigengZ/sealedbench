#!/usr/bin/env python3
"""Publish v2 results. SEALEDBENCH_DRY_UPLOAD=1 never invokes the wallet/uploader."""
from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sealedbench.paths import repo_root

HOLD = Path('/root/sbw/p2r/HOLD')
MAX_ITEM = 100 * 1024
MAX_MORE_COUNT = 20
MAX_MORE_BYTES = int(1.8 * 1024 * 1024)


def write_json(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.partial')
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + '\n')
    tmp.replace(path)


def pack(root, batch, model):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for kind in ('runs', 'reference_runs'):
            base = root / 'results/batches' / batch / kind / model
            for path in sorted(base.glob('*')):
                if path.suffix not in ('.txt', '.json', '.stderr'):
                    continue
                data = path.read_bytes()
                info = tarfile.TarInfo(name=f'{kind}/{model}/{path.name}')
                info.size, info.mtime, info.mode = len(data), 0, 0o644
                tar.addfile(info, io.BytesIO(data))
    return gzip.compress(raw.getvalue(), compresslevel=9, mtime=0)


def plan_budget(root, items, dry):
    ledger_name = 'v2_dry_upload_ledger.json' if dry else 'p2r_upload_ledger.json'
    path = root / 'results/batches' / ledger_name
    if path.exists():
        ledger = json.loads(path.read_text())
    elif dry:
        # Count the already sealed uploads against the same limits in rehearsal.
        ledger = json.loads((root / 'results/batches/p2r_upload_ledger.json').read_text())
    else:
        raise RuntimeError('upload ledger missing')
    pending = []
    for item in items:
        data = (root / item['path']).read_bytes()
        if len(data) > MAX_ITEM:
            raise RuntimeError(f'item exceeds 100 KiB: {item["path"]}')
        txpath = root / 'results/batches' / item['batch'] / 'txids.json'
        tx = json.loads(txpath.read_text())['items'].get(item['type'], {})
        if tx.get('txid') and tx.get('sha256') == hashlib.sha256(data).hexdigest():
            continue
        pending.append((item, data))
    count, size = len(pending), sum(len(data) for _,data in pending)
    # The phase began with exactly five seal uploads, 135875 bytes.
    used = [r for r in ledger.get('uploads', []) if r.get('type') not in ('manifest','generator-ciphertext','reference')]
    if len(used) + count > MAX_MORE_COUNT or sum(r['bytes'] for r in used) + size > MAX_MORE_BYTES:
        raise RuntimeError('remaining result-upload budget exceeded')
    if ledger['count'] + count > 25 or ledger['total_bytes'] + size > 2 * 1024 * 1024:
        raise RuntimeError('phase upload budget exceeded')
    return path, ledger, pending


def upload(root, items, dry):
    ledger_path, ledger, pending = plan_budget(root, items, dry)
    spec = root / 'results/batches/v2_results_spec.json'
    write_json(spec, {'dry_run':dry, 'items':items})
    if not dry:
        subprocess.run(['node', str(root/'tools/v2_upload.mjs'), str(spec)], cwd=root, check=True)
        return
    for item, data in pending:
        digest = hashlib.sha256(data).hexdigest()
        fake = base64.urlsafe_b64encode(hashlib.sha256(b'REHEARSAL ONLY\0'+data).digest()).decode().rstrip('=')
        txpath = root/'results/batches'/item['batch']/'txids.json'
        tx = json.loads(txpath.read_text())
        tx['items'][item['type']] = {'txid':fake,'sha256':digest,'bytes':len(data),'dry_run':True}
        write_json(txpath,tx)
        ledger['uploads'].append({'batch':item['batch'],'type':item['type'],'txid':fake,'sha256':digest,'bytes':len(data),'dry_run':True})
        ledger['count'] += 1
        ledger['total_bytes'] += len(data)
        write_json(ledger_path,ledger)
        print(f'DRY_UPLOAD {item["type"]} bytes={len(data)}',flush=True)


def main():
    root = repo_root()
    batch = os.environ.get('SEALEDBENCH_BATCH','b2')
    dry = os.environ.get('SEALEDBENCH_DRY_UPLOAD') == '1'
    if batch not in ('b2', 'b3') and not dry:
        raise RuntimeError('non-b2 result upload requires dry-upload mode')
    if HOLD.exists():
        raise RuntimeError('HOLD exists')
    dest = root/'results/batches'/batch
    manifest = json.loads((dest/'manifest.json').read_text())
    if not dry and json.loads((dest/'txids.json').read_text()).get('dry_run'):
        raise RuntimeError('refusing to publish rehearsal txids')
    out = dest/'uploads';out.mkdir(exist_ok=True)
    def item(path, kind, content_type):
        return {'path':str(path.relative_to(root)),'type':kind,'batch':batch,'round':manifest['release_round'],
                'unlock_unix':manifest['unlock_unix'],'unlock_utc':manifest['unlock_utc'],
                'content_type':content_type,'chain':manifest['drand']['chain_hash']}
    scores = dest/'scores.json'
    if not scores.exists() or scores.stat().st_size > MAX_ITEM:
        raise RuntimeError('scores missing or over 100 KiB')
    items=[item(scores,'results','application/json')]
    archives=[]
    for model in manifest['models']:
        blob=pack(root,batch,model['id'])
        path=out/f'{model["id"]}.tar.gz';path.write_bytes(blob)
        if len(blob)>MAX_ITEM:
            archives.append({'model':model['id'],'sha256':hashlib.sha256(blob).hexdigest(),'bytes':len(blob),'repo_path':str(path.relative_to(root)),'status':'REPO-ONLY'})
            print(f'REPO_ONLY {model["id"]} bytes={len(blob)}')
        else:
            items.append(item(path,f'completions-{model["id"]}','application/gzip'))
            archives.append({'model':model['id'],'kind':f'completions-{model["id"]}'})
    # Preflight all planned bytes, including a conservative index allowance, before uploading.
    index_path=dest/'index.json'
    old_index = index_path.read_bytes() if index_path.exists() else None
    index_path.write_bytes(b' ' * 16384)
    try:
        plan_budget(root,items+[item(index_path,'index','application/json')],dry)
    finally:
        if old_index is None: index_path.unlink()
        else: index_path.write_bytes(old_index)
    upload(root,items,dry)
    tx=json.loads((dest/'txids.json').read_text())['items']
    for archive in archives:
        if 'kind' in archive:
            archive.update(tx[archive.pop('kind')]);archive['status']='UPLOADED' if not dry else 'DRY'
    index={'protocol_version':'sealedbench/v2','batch_id':batch,'manifest_txid':tx['manifest']['txid'],
           'manifest_sha256':hashlib.sha256((dest/'manifest.json').read_bytes()).hexdigest(),
           'ciphertext_txid':manifest['ciphertext']['txid'],'results':tx['results'],'completions':archives,
           'dry_run':dry,'note':'Index is written after the run and is not a pre-commitment.'}
    write_json(index_path,index)
    upload(root,[item(index_path,'index','application/json')],dry)
    print('UPLOAD_RESULTS_DONE dry='+str(dry))

if __name__=='__main__':
    main()
