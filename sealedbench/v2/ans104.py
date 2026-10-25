"""Independent ANS-104 bundle table and data-item payload offsets.

Layout follows the installed @dha-team/arbundles Bundle.getItems/DataItem
implementations: uint256le count; count * (uint256le size + 32-byte id),
then concatenated data items. Offsets never come from Turbo metadata.
"""
from __future__ import annotations
import base64
import hashlib
import re

MAX_HEADER = 2 * 1024 * 1024
SIG_LENGTHS = {1:(512,512),2:(64,32),3:(65,65),4:(64,32),5:(64,32),6:(2052,1025),7:(65,42),101:(65,65)}


class BundleUnavailable(RuntimeError):
    pass


class BundleFormatError(ValueError):
    pass


def encode_id(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip('=')


def count_from_prefix(raw):
    if len(raw)!=32:raise BundleFormatError('short bundle count')
    count=int.from_bytes(raw,'little')
    if count<1 or 32+64*count>MAX_HEADER:
        raise BundleUnavailable('bundle table is empty or exceeds bounded range parser')
    return count


def parse_header(raw):
    count=count_from_prefix(raw[:32])
    header_end=32+64*count
    if len(raw)!=header_end:raise BundleFormatError('bundle table length mismatch')
    offset=header_end
    entries={}
    for index in range(count):
        pos=32+64*index
        size=int.from_bytes(raw[pos:pos+32],'little')
        item_id=encode_id(raw[pos+32:pos+64])
        if size<2 or item_id in entries:raise BundleFormatError('zero/short item or duplicate id')
        entries[item_id]={'start':offset,'size':size,'index':index}
        offset+=size
    return entries


def parse_data_item_prefix(raw,item_id,item_size):
    if len(raw)<2:raise BundleFormatError('short data-item prefix')
    kind=int.from_bytes(raw[:2],'little')
    if kind not in SIG_LENGTHS:raise BundleUnavailable(f'unsupported signature type {kind}')
    sig_length,owner_length=SIG_LENGTHS[kind]
    position=2+sig_length+owner_length
    if len(raw)<position+2:raise BundleFormatError('short signature/owner/flags')
    if encode_id(hashlib.sha256(raw[2:2+sig_length]).digest())!=item_id:
        raise BundleFormatError('data-item signature hash disagrees with table id')
    for _ in range(2):
        if len(raw)<=position or raw[position] not in (0,1):raise BundleFormatError('invalid target/anchor flag')
        position+=1+(32 if raw[position] else 0)
    if len(raw)<position+16:raise BundleFormatError('short tag metadata')
    tag_count=int.from_bytes(raw[position:position+8],'little')
    tag_bytes=int.from_bytes(raw[position+8:position+16],'little')
    payload_start=position+16+tag_bytes
    if tag_count>128 or tag_bytes>4096 or payload_start>item_size:
        raise BundleFormatError('tag metadata exceeds item bounds')
    return {'signature_type':kind,'payload_start':payload_start,'payload_len':item_size-payload_start,'tag_count':tag_count}


def fetch_range(network,url,start,length):
    end=start+length-1
    code,raw,headers=network.get(url,{'Range':f'bytes={start}-{end}'})
    content_range=next((value for key,value in headers.items() if key.lower()=='content-range'),'')
    match=re.fullmatch(r'bytes (\d+)-(\d+)/(\d+|\*)',content_range)
    if code!=206 or len(raw)!=length or not match or int(match[1])!=start or int(match[2])!=end:
        raise BundleUnavailable(f'range unavailable HTTP {code} bytes={len(raw)} at {start}')
    if match[3]!='*' and end>=int(match[3]):raise BundleFormatError('range exceeds bundle size')
    return raw


def locate_payload(network,host,bundle,item_id):
    last=None
    for url in (f'{host}/raw/{bundle}',f'{host}/{bundle}'):
        try:
            prefix=fetch_range(network,url,0,32)
            count=count_from_prefix(prefix)
            header=prefix+fetch_range(network,url,32,64*count)
            entries=parse_header(header)
            if item_id not in entries:
                raise BundleUnavailable('item not in root table; nested bundles require a further proof')
            entry=entries[item_id]
            raw=fetch_range(network,url,entry['start'],min(entry['size'],8192))
            payload=parse_data_item_prefix(raw,item_id,entry['size'])
            return {**entry,**payload,'url':url,'bundle_items':count,'header_sha256':hashlib.sha256(header).hexdigest()}
        except BundleUnavailable as exc:
            last=exc
    raise last or BundleUnavailable('bundle not served')
