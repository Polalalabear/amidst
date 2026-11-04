"""Create a new compatible P1 package; strip ancillary metadata without pixel encoding.

Reads only the pinned original manifest and its allowlisted immutable payload.
Original source/index/recording bytes remain unchanged; an explicit pinned media
map binds source-file hashes to served-file hashes. Never walk STATE/RETURN or
private source directories. Uses existing Pillow only for decoded RGB hash checks.
"""
from __future__ import annotations
import argparse
from collections import Counter
import ctypes
import io
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import zlib
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_safe_pack import (MANIFEST, checked_path, inspect_payload, inspect_png, json_document,
                             read, relative, require, sha, verify)
from build_argon_safe_packs import P1_PIN, clone_one, disk

STRIP={b'tEXt',b'zTXt',b'iTXt',b'eXIf'}


def strip_png(raw):
    require(raw[:8]==b'\x89PNG\r\n\x1a\n','PNG_INVALID')
    offset=8;clean=bytearray(raw[:8]);idat=[];keys=[]
    while offset<len(raw):
        require(offset+12<=len(raw),'PNG_INVALID')
        size=struct.unpack('>I',raw[offset:offset+4])[0]
        kind=raw[offset+4:offset+8];end=offset+size+12
        require(end<=len(raw),'PNG_INVALID')
        payload=raw[offset+8:end-4]
        require(zlib.crc32(kind+payload)==struct.unpack('>I',raw[end-4:end])[0],'PNG_CRC_INVALID')
        if kind in STRIP:
            if kind==b'eXIf':
                from PIL import Image, ExifTags
                # Read key identifiers only, never display or retain field values.
                metadata=Image.Exif();metadata.load(b'Exif\0\0'+payload)
                keys += ['eXIf:'+str(ExifTags.TAGS.get(tag,tag)) for tag in metadata.keys()]
            else:
                keyword=payload.split(b'\0',1)[0].decode('latin-1')
                keys.append(kind.decode()+':'+keyword)
        else:
            clean.extend(raw[offset:end])
        if kind==b'IDAT':idat.append(raw[offset:end])
        offset=end
    inspect_png(bytes(clean))
    return bytes(clean), sorted(set(keys)), sha(b''.join(idat))


def pixels(raw):
    from PIL import Image
    with Image.open(io.BytesIO(raw)) as image:
        require(image.mode=='RGB' and image.size==(960,540),'PIXEL_LAYOUT_INVALID')
        return sha(image.tobytes())


def serialize(doc):
    return (json.dumps(doc,sort_keys=True,indent=2)+'\n').encode()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--runtime-adapter',type=Path,default=Path(__file__).resolve().parents[1]/'src/amidst/q1q5/p1_workbench.py')
    args=p.parse_args(argv)
    source=checked_path(args.source);out=checked_path(args.output)
    require(not out.exists() and out.parent.is_dir(),'NEW_OUTPUT_REQUIRED')
    original_manifest=read(source/'MANIFEST.json')
    require(sha(original_manifest)==P1_PIN,'SOURCE_MANIFEST_PIN_MISMATCH')
    old=json_document(original_manifest)
    before=disk(out.parent)
    libc=ctypes.CDLL(None,use_errno=True);clonefile=libc.clonefile
    clonefile.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int];clonefile.restype=ctypes.c_int
    out.mkdir();files={};entries={};key_counts=Counter()
    def write(name,raw):
        target=relative(out,name);disk(target.parent)
        target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(raw)
        files[name]={'bytes':len(raw),'sha256':sha(raw)}
    for index,(name,pin) in enumerate(sorted(old['files'].items()),1):
        original=relative(source,name);raw=read(original)
        require(len(raw)==pin['bytes'] and sha(raw)==pin['sha256'],'SOURCE_FILE_PIN_MISMATCH')
        if name.endswith('.png'):
            clean,keys,idat_hash=strip_png(raw)
            before_pixels,after_pixels=pixels(raw),pixels(clean)
            require(before_pixels==after_pixels,'PIXELS_CHANGED')
            # IDAT is retained verbatim; no encoder is called.
            write(name,clean)
            entries[name]={'original_file_sha256':pin['sha256'],'file_sha256':sha(clean),
                           'original_pixel_sha256':before_pixels,'pixel_sha256':after_pixels,
                           'idat_sha256':idat_hash,'metadata_key_names':keys}
            key_counts.update(keys)
        elif name=='app/src/amidst/q1q5/p1_workbench.py':
            write(name,read(args.runtime_adapter))
        else:
            inspect_payload(name,raw)
            target=relative(out,name)
            clone_one(original,target,pin['sha256'],pin['bytes'],clonefile)
            files[name]=pin
        require(sha(read(original))==pin['sha256'],'SOURCE_CHANGED')
        if index%80==0:print(json.dumps({'stage':'p1-strip','files':index,'pngs':len(entries)}),flush=True)
    require(len(entries)==320,'P1_PNG_GRID_CHANGED')
    write('provenance/SOURCE_MANIFEST.json',original_manifest)
    transform={'format':'p1-media-transform.v1','source_manifest_ref':'provenance/SOURCE_MANIFEST.json',
               'source_manifest_sha256':P1_PIN,'entries':entries}
    write('MEDIA_TRANSFORM.json',serialize(transform))
    new_manifest={**old,'files':dict(files),'total_bytes':sum(p['bytes'] for p in files.values()),
                  'media_transform_ref':'MEDIA_TRANSFORM.json',
                  'derivation':{'source_manifest_sha256':P1_PIN,'method':'strip PNG text/EXIF; preserve IDAT and decoded RGB',
                                'runtime_adapter_file':'app/src/amidst/q1q5/p1_workbench.py',
                                'runtime_adapter_sha256':files['app/src/amidst/q1q5/p1_workbench.py']['sha256']}}
    runtime_raw=serialize(new_manifest)
    # The runtime manifest excludes itself/sidecar, as in the original P1 contract.
    write('MANIFEST.json',runtime_raw)
    write('MANIFEST.sha256',(sha(runtime_raw)+'\n').encode())
    transport={'format':'amidst.argon-safe-pack.v1','pack_id':'p1-v4-stripped','classification':'SYNTHETIC_ENGINEERING_DEMO',
        'formal_eligible':False,'gt_read':False,'files':files,'sources':{'manifest_sha256':P1_PIN,
        'runtime_manifest_sha256':sha(runtime_raw),'copy_method':'independent cloned non-PNGs and new stripped PNG bytes'}}
    transport_raw=serialize(transport)
    with (out/MANIFEST).open('xb') as stream:stream.write(transport_raw)
    result=verify(out,sha(transport_raw))
    result.update(local_path=str(out),runtime_manifest_sha256=sha(runtime_raw),
        source_manifest_sha256=P1_PIN,pngs_pixel_equal=len(entries),metadata_key_counts=dict(key_counts),
        metadata_values_recorded=False,before_available_bytes=before,after_available_bytes=disk(out))
    # Keep this report outside the exact-set transfer pack.
    report=out.with_name(out.name+'-receipt.json')
    with report.open('x') as stream:json.dump(result,stream,sort_keys=True,indent=2);stream.write('\n')
    print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':
    main()
