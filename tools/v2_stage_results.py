#!/usr/bin/env python3
"""Stage only named v2 output artifacts; never sources or extracted secrets."""
import json
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from sealedbench.v2.pipeline_state import artifacts


def paths(batch):
    dest=ROOT/'results/batches'/batch
    files=[dest/name for name in ('manifest.json','reference.json','generator.tlock')]
    for step in ['release']+['infer_'+m['id'] for m in json.loads((dest/'manifest.json').read_text())['models']]+['replay','score','upload','verify']:
        files+=artifacts(batch,step)
    files.append(dest/'pipeline_state.json')
    # The budget ledger is part of result publication; the spec is reproducible.
    ledger=ROOT/'results/batches'/('v2_dry_upload_ledger.json' if batch in ('b2r','b3r') else 'p2r_upload_ledger.json')
    if ledger.exists():files.append(ledger)
    return sorted({str(path.relative_to(ROOT)) for path in files})

if __name__=='__main__':
    batch=sys.argv[1]
    if batch not in ('b2','b2r','b3','b3r'):raise SystemExit('unsupported batch')
    selected=paths(batch)
    staged=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0')
    unexpected=set(staged)-set(selected)-{''}
    if unexpected:raise SystemExit('refusing unrelated staged paths: '+', '.join(sorted(unexpected)))
    # Stage with explicit arguments so symlinks, untracked scratch files, and
    # other indexed changes are not swept into the commit.
    subprocess.run(['git','add','--',*selected],cwd=ROOT,check=True)
    print(f'STAGED_RESULTS files={len(selected)}')
