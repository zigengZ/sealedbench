"""v2 verification: local bindings/regrading and independent network observations.

Exit 0 PASS, 1 proven failure, 2 UNKNOWN/WEAK. Missing observations never
prove a late batch. No author gateway or arweave.net requests are made.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tarfile
import io
import time
import urllib.error
import urllib.request

from sealedbench.paths import repo_root
from sealedbench.release import safe_extract, beacon_binding_error
from sealedbench.v2.tarball import grader_sha256
from sealedbench.v2.transport import INDEPENDENT
from sealedbench.v2.ans104 import locate_payload, fetch_range, BundleUnavailable, BundleFormatError


def sha(data):
    return hashlib.sha256(data).hexdigest()


def result(rows):
    statuses = {r[0] for r in rows}
    if 'FAIL' in statuses: return 'FAIL', 1
    if 'UNKNOWN' in statuses: return 'UNKNOWN', 2
    if 'WEAK' in statuses: return 'WEAK', 2
    return 'PASS', 0


class Network:
    def __init__(self):
        self.cache = {}
        self.last_turbo = 0

    def get(self, url, headers=None):
        key=(url,tuple(sorted((headers or {}).items())))
        if key in self.cache:return self.cache[key]
        if url.startswith('https://upload.ardrive.io/'):
            wait=1.1-(time.monotonic()-self.last_turbo)
            if wait>0:time.sleep(wait)
            self.last_turbo=time.monotonic()
        req=urllib.request.Request(url,headers={'User-Agent':'sealedbench-v2-verify',**(headers or {})})
        try:
            with urllib.request.urlopen(req,timeout=30) as response:
                # A gateway that ignores Range must not stream a whole huge bundle.
                body=response.read(2*1024*1024+1)
                got=(response.status,body,dict(response.headers))
                if len(body)>2*1024*1024:got=(0,b'',{})
        except urllib.error.HTTPError as exc:
            got=(exc.code,b'',{})
        except (OSError,ValueError,TimeoutError):
            got=(0,b'',{})
        self.cache[key]=got
        return got

    def json(self,url):
        status,body,_=self.get(url)
        try:return status,json.loads(body)
        except (ValueError,TypeError):return status,None


def served(network, txid, expected, name, rows, dry=False):
    if dry:
        rows.append(('UNKNOWN',name,'rehearsal txid; no public upload'))
        return
    for host in INDEPENDENT:
        code,body,_=network.get(f'{host}/{txid}')
        state='PASS' if code==200 and sha(body)==expected else 'FAIL' if code==200 else 'UNKNOWN'
        rows.append((state,f'{name} {host}',f'HTTP {code}'))


def inclusion(network, txid, expected, unlock, name, rows, dry=False):
    if dry:
        rows.append(('UNKNOWN',name+' inclusion','rehearsal txid; no L1 evidence'))
        return None
    code,status=network.json(f'https://upload.ardrive.io/v1/tx/{txid}/status')
    if code!=200 or not isinstance(status,dict) or not status.get('bundleId'):
        rows.append(('UNKNOWN',name+' inclusion',f'Turbo HTTP {code}; bundle unavailable'))
        return None
    bundle=status['bundleId']
    observed=[]
    for host in INDEPENDENT:
        code,l1=network.json(f'{host}/tx/{bundle}/status')
        if code!=200 or not isinstance(l1,dict) or not isinstance(l1.get('block_height'),int):
            rows.append(('UNKNOWN',name+' L1 '+host,f'HTTP {code}'));continue
        height=l1['block_height']
        code,block=network.json(f'{host}/block/height/{height}')
        if code!=200 or not isinstance(block,dict):
            rows.append(('UNKNOWN',name+' block '+host,f'HTTP {code}'));continue
        if not isinstance(block.get('txs'),list) or bundle not in block['txs']:
            rows.append(('UNKNOWN',name+' block '+host,'bundle membership unproven'));continue
        if block.get('height')!=height or block.get('indep_hash')!=l1.get('block_indep_hash'):
            rows.append(('FAIL',name+' block '+host,'height/hash disagreement'));continue
        try:
            proof=locate_payload(network,host,bundle,txid)
            begin=proof['start']+proof['payload_start']
            length=proof['payload_len']
            raw=fetch_range(network,proof['url'],begin,length)
        except BundleUnavailable as exc:
            rows.append(('UNKNOWN',name+' bundle proof '+host,str(exc)));continue
        except BundleFormatError as exc:
            rows.append(('FAIL',name+' bundle proof '+host,str(exc)));continue
        if sha(raw)!=expected:
            rows.append(('FAIL',name+' payload '+host,'sha256 mismatch'));continue
        stamp=block.get('timestamp')
        if not isinstance(stamp,int):
            rows.append(('UNKNOWN',name+' timestamp '+host,'missing timestamp'));continue
        observed.append((height,block['indep_hash'],stamp))
    if len(observed)!=2 or observed[0]!=observed[1]:
        rows.append(('UNKNOWN',name+' inclusion','need agreeing height, block hash, timestamp and payload on two independent gateways'))
        return None
    timely=observed[0][2]<=unlock-600
    rows.append(('PASS' if timely else 'FAIL',name+' inclusion',f'bundle={bundle} height={observed[0][0]} timestamp={observed[0][2]} deadline={unlock-600}'))
    rows.append(('PASS',name+' bundle header','table offsets, signature-hash item id, payload offset and payload hash independently parsed on two gateways'))
    return timely


def beacon_check(root, beacon, round_num):
    if int(beacon.get('round',-1))!=int(round_num) or beacon_binding_error(beacon):return False
    try:
        proc=subprocess.run(['node',str(root/'tools/verify_beacon.mjs')],input=json.dumps({'round':round_num,'beacon':beacon}).encode(),capture_output=True,cwd=root,timeout=120,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return None
    if proc.returncode==2: return None
    return proc.returncode==0


def verify(batch='b2', network=None):
    root=repo_root();network=network or Network();rows=[]
    batches=(batch,'cap2') if batch=='b2' else (batch,)
    manifests={}
    for name in batches:
        dest=root/'results/batches'/name
        try:
            raw=(dest/'manifest.json').read_bytes();doc=json.loads(raw)
            tx=json.loads((dest/'txids.json').read_text())
            manifests[name]=doc
            dry=bool(tx.get('dry_run'))
            if doc.get('protocol_version')!='sealedbench/v2':
                rows.append(('WEAK',name+' protocol','not sealedbench/v2'));continue
            binding=doc.get('ciphertext',{})
            if not binding.get('txid'):
                rows.append(('WEAK',name+' ciphertext binding','missing txid'))
            else:
                rows.append(('PASS' if binding['txid']==tx['items']['generator-ciphertext']['txid'] else 'FAIL',name+' ciphertext binding',binding['txid']))
            rows.append(('PASS' if grader_sha256(root, doc.get('grader',{}).get('files'))==doc['grader']['sha256'] else 'FAIL',name+' grader','source hash'))
            reference=dest/'reference.json'
            if not reference.exists():reference=root/'results/batches/b2/reference.json'
            rows.append(('PASS' if sha(reference.read_bytes())==doc['reference']['sha256'] else 'FAIL',name+' reference','file hash'))
            manifest_tx=tx['items']['manifest']['txid']
            served(network,manifest_tx,sha(raw),name+' manifest',rows,dry)
            for kind,item_id,digest in [('manifest',manifest_tx,sha(raw)),('ciphertext',binding.get('txid'),binding.get('sha256')),('reference',doc['reference'].get('txid'),doc['reference'].get('sha256'))]:
                if item_id:inclusion(network,item_id,digest,doc['unlock_unix'],name+' '+kind,rows,dry)
            # Verify the actual release beacon once released; otherwise a pinned past vector.
            if (dest/'beacon.json').exists():
                beacon=json.loads((dest/'beacon.json').read_text());target=doc['release_round']
            else:
                target=1000
                code,beacon=network.json(doc['drand']['beacon_url_template'].format(round=target))
                if code!=200 or not isinstance(beacon,dict):beacon=None
            if beacon is None:
                rows.append(('UNKNOWN',name+' beacon','beacon network unavailable'))
            else:
                ok=beacon_check(root,beacon,target)
                rows.append(('PASS' if ok else 'UNKNOWN' if ok is None else 'FAIL',name+' BLS',str(target)))
            if (dest/'scores.json').exists():
                from sealedbench.v2.scoring import calculate_scores
                published=json.loads((dest/'scores.json').read_text())
                rows.append(('PASS' if calculate_scores(name)==published else 'FAIL',name+' regrade','strict grader, truncation, all models and references'))
                index=json.loads((dest/'index.json').read_text())
                if index.get('manifest_txid')!=manifest_tx or index.get('ciphertext_txid')!=binding.get('txid'):
                    rows.append(('FAIL',name+' index','binding mismatch'))
                scores_link=index.get('results',{})
                if scores_link.get('sha256')!=sha((dest/'scores.json').read_bytes()):
                    rows.append(('FAIL',name+' results link','scores hash mismatch'))
                elif scores_link.get('txid'):
                    served(network,scores_link['txid'],scores_link['sha256'],name+' published scores',rows,dry)
                else:rows.append(('UNKNOWN',name+' results link','results txid missing'))
                for archive in index.get('completions',[]):
                    label=name+' completions '+archive['model']
                    path=dest/'uploads'/f"{archive['model']}.tar.gz"
                    if sha(path.read_bytes())!=archive.get('sha256'):
                        rows.append(('FAIL',label,'archive hash mismatch'));continue
                    with tarfile.open(fileobj=io.BytesIO(path.read_bytes()),mode='r:gz') as tar:
                        same=True
                        for member in tar.getmembers():
                            relative=Path(member.name)
                            if relative.is_absolute() or '..' in relative.parts or not member.isfile():
                                same=False;break
                            local=dest/relative
                            body=tar.extractfile(member).read()
                            if not local.is_file() or body!=local.read_bytes():
                                same=False;break
                        rows.append(('PASS' if same else 'FAIL',label+' local answers','archive members equal regraded run files'))
                    if archive.get('txid'):
                        served(network,archive['txid'],archive['sha256'],label+' served',rows,dry)
                    else:
                        rows.append(('WEAK',label,'REPO-ONLY; not independently served'))
                # Rebuild from the local ciphertext only after its committed hash check.
                cipher=(dest/'generator.tlock').read_bytes()
                if sha(cipher)!=binding['sha256']:
                    rows.append(('FAIL',name+' ciphertext','local hash mismatch'))
                elif beacon is not None:
                    from sealedbench.release import tle_decrypt
                    from sealedbench.v2.run_release import _generate
                    code,plain,err=tle_decrypt(cipher)
                    if code:rows.append(('UNKNOWN',name+' regeneration',f'decrypt unavailable rc={code}'))
                    elif sha(plain)!=doc['plaintext_tarball_sha256']:
                        rows.append(('FAIL',name+' plaintext','hash mismatch'))
                    else:
                        with tempfile.TemporaryDirectory() as tmp:
                            src=Path(tmp)/'src';safe_extract(plain,src)
                            bank=(src/'sealedbench/v2/template_bank.json').read_bytes()
                            rows.append(('PASS' if sha(bank)==doc['template_bank_sha256'] else 'FAIL',name+' template bank','sealed bytes'))
                            counts={r['name']:r['n'] for r in doc['generator']['families']}
                            jsonl=_generate(src,doc['drand']['chain_hash'],target,bytes.fromhex(beacon['signature']),counts)
                            rows.append(('PASS' if jsonl==(dest/'items.jsonl').read_bytes() else 'FAIL',name+' regeneration','items from sealed bytes'))
            elif name==batch and time.time()>=doc['unlock_unix']:
                rows.append(('UNKNOWN',name+' scores','run not published'))
        except (OSError,ValueError,KeyError,TypeError,RuntimeError,subprocess.SubprocessError,tarfile.TarError) as exc:
            rows.append(('FAIL',name+' local verification',f'{type(exc).__name__}: {exc}'))
    def _manifest_for(batch_id):
        other=manifests.get(batch_id)
        if other is not None:
            return other
        path=root/'results/batches'/str(batch_id)/'manifest.json'
        try:
            return json.loads(path.read_text())
        except (OSError, ValueError):
            return None

    for name,doc in manifests.items():
        declared=(doc.get('corrects') or {}).get('declared') or []
        for row in declared:
            other=_manifest_for(row.get('batch_id'))
            if not other:
                rows.append(('UNKNOWN',name+' declares '+str(row.get('batch_id')),'manifest unavailable'))
            else:
                ok=row.get('ciphertext_sha256')==other.get('ciphertext',{}).get('sha256')
                rows.append(('PASS' if ok else 'FAIL',name+' declares '+str(row.get('batch_id')),'ciphertext sha256'))
        peer=doc.get('peer') or {}
        if peer.get('batch_id'):
            other=_manifest_for(peer.get('batch_id'))
            if other:
                ok=peer.get('ciphertext_sha256')==other['ciphertext']['sha256']
                rows.append(('PASS' if ok else 'FAIL',name+' peer','cross-ciphertext hash'))
            else:
                rows.append(('UNKNOWN',name+' peer','peer manifest unavailable'))
        elif not declared:
            rows.append(('UNKNOWN',name+' peer','peer manifest unavailable'))
    outcome,code=result(rows)
    text=''.join(f'{state:<8} {name}: {detail}\n' for state,name,detail in rows)+f'RESULT {outcome}\n'
    dest=root/'results/batches'/batch;dest.mkdir(parents=True,exist_ok=True)
    seal=dest/'verify_seal.txt'
    # A file already there is the registered seal log. Print the new result.
    if not seal.exists():
        seal.write_text(text)
    print(text,end='')
    return code
