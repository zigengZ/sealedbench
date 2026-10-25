"""Atomic, artifact-hashed checkpoints for the unattended v2 shell pipeline."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
import subprocess
from sealedbench.infer import batch_dir, load_manifest, _v2_reference


def atomic(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_suffix('.json.partial')
    tmp.write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n')
    tmp.replace(path)


def inference_files(batch,model):
    dest=batch_dir(batch);doc=load_manifest(batch)
    items=[json.loads(line) for line in (dest/'items.jsonl').read_text().splitlines() if line.strip()]
    work=[(dest/'runs'/model,i['item_id']) for i in items]
    work += [(dest/'reference_runs'/model,i['item_id']) for i in _v2_reference(doc,batch)]
    files=[]
    for directory,item_id in work:
        meta_path=directory/f'{item_id}.json';stdout=directory/f'{item_id}.txt'
        meta=json.loads(meta_path.read_text())
        if meta.get('returncode') is None or (meta['returncode']!=0 and meta.get('attempt')!=2):
            raise ValueError('incomplete inference attempt')
        if meta.get('stdout_sha256')!=hashlib.sha256(stdout.read_bytes()).hexdigest():
            raise ValueError('inference stdout hash mismatch')
        files += [meta_path,stdout,directory/f'{item_id}.stderr']
        files += sorted(directory.glob(f'{item_id}.attempt*'))
    return files


def artifacts(batch,step):
    dest=batch_dir(batch)
    if step=='release':return [dest/f for f in ('items.jsonl','beacon.json','release.json')]
    if step.startswith('infer_'):return inference_files(batch,step.removeprefix('infer_'))
    if step=='score':return [dest/'scores.json',dest/'scores.md']
    if step=='replay':
        report=dest/'replay_qwen3-4b-instruct-2507.json'
        doc=json.loads(report.read_text())
        if not doc.get('compared') or doc.get('matches')!=doc['compared']:raise ValueError('replay mismatches')
        base=Path(doc['output_dir'])
        return [report]+[base/f"{item['item_id']}.{suffix}" for item in doc['items'] for suffix in ('txt','json','stderr')]
    if step=='upload':
        doc=json.loads((dest/'txids.json').read_text());index=json.loads((dest/'index.json').read_text())
        if not doc['items'].get('index',{}).get('txid') or not index.get('results',{}).get('txid'):raise ValueError('missing upload txids')
        files=[dest/'txids.json',dest/'index.json']
        files+=sorted((dest/'uploads').glob('*'))
        files+=sorted((dest/'receipts').glob('*'))
        return files
    if step=='verify':
        path=dest/'verify_seal.txt'
        if not path.read_text().endswith(('RESULT PASS\n','RESULT UNKNOWN\n','RESULT WEAK\n')):raise ValueError('verifier failed or did not complete')
        return [path]
    raise ValueError(f'unknown step {step}')


def fingerprint(files):
    return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in files}


def inputs(batch,step):
    dest=batch_dir(batch)
    files=[dest/'manifest.json']
    if step=='release':return files
    files+=[dest/'items.jsonl',dest/'reference.json']
    if step.startswith('infer_'):return files
    if step=='replay':return files+inference_files(batch,'qwen3-4b-instruct-2507')
    if step in ('score','upload','verify'):
        for model in load_manifest(batch)['models']:
            files+=inference_files(batch,model['id'])
    if step in ('upload','verify'):files+=[dest/'scores.json']
    if step=='verify':files+=[dest/'txids.json',dest/'index.json']
    return files


def checkpoint(state_path,batch,step):
    doc=json.loads(state_path.read_text()) if state_path.exists() else {'steps':{}}
    hashes=fingerprint(artifacts(batch,step))
    doc['steps'][step]={'artifacts':hashes,'inputs':fingerprint(inputs(batch,step))}
    atomic(state_path,doc)


def have(state_path,step):
    try:
        doc=json.loads(state_path.read_text())['steps'][step]
        hashes={**doc['artifacts'],**doc.get('inputs',{})}
        return bool(hashes) and all(Path(path).is_file() and hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in hashes.items())
    except (OSError,ValueError,KeyError,TypeError):return False


def llama_active(table=None):
    if table is None:
        table=subprocess.check_output(['ps','-eo','pid=,args='],text=True)
    for line in table.splitlines():
        fields=line.split(None,2)
        if len(fields)>=2 and Path(fields[1]).name=='llama-completion':return True
    return False


def main():
    if sys.argv[1]=='llama-active':return 0 if llama_active() else 1
    mode,batch,step=sys.argv[1:4]
    path=Path(os.environ['SEALEDBENCH_PIPELINE_STATE'])
    if mode=='have':return 0 if have(path,step) else 1
    if mode=='done':checkpoint(path,batch,step);return 0
    if mode=='validate-infer':inference_files(batch,step);return 0
    raise ValueError(mode)

if __name__=='__main__':raise SystemExit(main())
