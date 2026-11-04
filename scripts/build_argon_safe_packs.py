"""LOCAL #416 allowlist packager. Uses macOS clonefile; no raw-copy fallback.

Only the named manifest files and their enumerated safe payloads are read.
No source tree walk, event-root scan, private data, original asset or model is read.
Copies have independent inodes; original bytes remain unchanged. Windows uses the
separate stdlib verifier; it does not need this macOS materialization method.
"""
from __future__ import annotations
import argparse
import ctypes
import json
import os
from pathlib import Path
import shutil
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_safe_pack import (MANIFEST, checked_path, inspect_payload, json_document, read,
                             relative, require, sha, verify)

P1_PIN='6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7'
D119_PIN='60f2b5f8cdddf5096ffa9a25053260568570c40d8ea2737d6663f0ae3e3c2c82'
D124_PIN='ad3c66f21ef6713a76b0bb6505a7e5eb3514fa346f9279c42d7b486479281f01'
MIN_FREE=8*1024**3


def disk(root):
    root=checked_path(root)
    while not root.exists():root=root.parent
    free=shutil.disk_usage(root).free
    require(free>=MIN_FREE+32*1024**2,'STOP_BELOW_8_GIB_PLUS_RESERVE')
    return free


def specification(source, manifest_name, expected, *, viewer_aliases=False):
    source=checked_path(source)
    raw=read(source/manifest_name)
    require(sha(raw)==expected,'SOURCE_MANIFEST_PIN_MISMATCH')
    doc=json_document(raw)
    records={manifest_name:(source/manifest_name,expected,len(raw))}
    for name,item in doc['files'].items():
        path=relative(source,name)
        pin=item if isinstance(item,str) else item['sha256']
        size=path.stat().st_size if isinstance(item,str) else item['bytes']
        records[name]=(path,pin,size)
    if manifest_name=='MANIFEST.json':
        sidecar=read(source/'MANIFEST.sha256')
        require(sidecar.decode().strip()==expected,'SOURCE_MANIFEST_SIDECAR_MISMATCH')
        records['MANIFEST.sha256']=(source/'MANIFEST.sha256',sha(sidecar),len(sidecar))
    if viewer_aliases:
        for run_ref in doc['runs']:
            run_path,pin,_=records[run_ref]
            run_raw=read(run_path)
            require(sha(run_raw)==pin,'RUN_PIN_MISMATCH')
            run=json_document(run_raw)
            label=run['label']
            for frame in run['frames']:
                name=f"{label}/safe/media/{frame['camera_id']}/{frame['frame_index']:06d}.png"
                relative(source,name)  # validate names only, never open this alias in the source
                original=records[frame['filename']]
                require(original[1]==frame['file_sha256'],'FRAME_PIN_MISMATCH')
                records['VIEWER/'+name]=original
    return records


def destination_name(name, prefix):
    return name.removeprefix('VIEWER/') if name.startswith('VIEWER/') else prefix+name


def clone_one(source,target,expected,size,clonefile):
    raw=read(source)
    require(len(raw)==size and sha(raw)==expected,'SOURCE_FILE_PIN_MISMATCH')
    inspect_payload(source.name,raw)
    disk(target.parent)
    target.parent.mkdir(parents=True,exist_ok=True)
    require(not target.exists() and not target.is_symlink(),'OUTPUT_FILE_ALREADY_EXISTS')
    require(clonefile(os.fsencode(source),os.fsencode(target),0)==0,'CLONEFILE_FAILED_NO_COPY_FALLBACK')
    a,b=source.stat(),target.stat()
    require((a.st_dev,a.st_ino)!=(b.st_dev,b.st_ino),'HARDLINK_FORBIDDEN')
    require(sha(read(target))==expected and sha(read(source))==expected,'COPY_OR_SOURCE_CHANGED')


def materialize(output,pack_id,records,prefix,classification,source_manifest_pin,clonefile):
    out=checked_path(output/pack_id)
    require(not out.exists(),'OUTPUT_PACK_ALREADY_EXISTS')
    out.mkdir()
    files={}
    for index,(name,(source,pin,size)) in enumerate(sorted(records.items()),1):
        target_name=destination_name(name,prefix)
        require(target_name not in files,'DUPLICATE_OUTPUT')
        target=relative(out,target_name)
        clone_one(source,target,pin,size,clonefile)
        files[target_name]={'bytes':size,'sha256':pin}
        if index%250==0:print(json.dumps({'stage':'copy','pack':pack_id,'files':index}),flush=True)
    manifest={'format':'amidst.argon-safe-pack.v1','pack_id':pack_id,'classification':classification,
              'formal_eligible':False,'gt_read':False,'files':files,
              'sources':{'manifest_sha256':source_manifest_pin,'copy_method':'APFS clonefile; independent inodes'}}
    raw=(json.dumps(manifest,sort_keys=True,indent=2)+'\n').encode()
    with (out/MANIFEST).open('xb') as stream:stream.write(raw)
    result=verify(out,sha(raw))
    result.update(local_path=str(out),source_manifest_sha256=source_manifest_pin)
    print(json.dumps({'stage':'verified',**result}),flush=True)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--p1',type=Path,required=True)
    p.add_argument('--d119-safe-bundle',type=Path,required=True)
    p.add_argument('--d124-safe-bundle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--skip-p1',action='store_true',help='Produce CX-7 only, with P1 explicitly UNKNOWN; never relax PNG metadata rejection.')
    args=p.parse_args(argv)
    output=checked_path(args.output)
    require(not output.exists() and output.parent.is_dir(),'NEW_OUTPUT_REQUIRED')
    before=disk(output.parent)
    # Enumerated safe manifests only. No private or mutable source subdirectories are walked.
    p1=None if args.skip_p1 else specification(args.p1,'MANIFEST.json',P1_PIN)
    old=specification(args.d119_safe_bundle,'manifest.json',D119_PIN,viewer_aliases=True)
    new=specification(args.d124_safe_bundle,'manifest.json',D124_PIN)
    libc=ctypes.CDLL(None,use_errno=True)
    clonefile=libc.clonefile
    clonefile.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
    clonefile.restype=ctypes.c_int
    output.mkdir()
    results=[]
    if p1 is not None:
        results.append(materialize(output,'p1-v4',p1,'','SYNTHETIC_ENGINEERING_DEMO',P1_PIN,clonefile))
    results += [materialize(output,'cx7-d119',old,'safe_bundle/','ACTUAL_BLENDER_D119_ENGINEERING',D119_PIN,clonefile),
             materialize(output,'cx7-d124',new,'safe_bundle/','ACTUAL_BLENDER_D124_ENGINEERING',D124_PIN,clonefile)]
    after=disk(output)
    report={'p1_status':'UNKNOWN_PNG_METADATA_COMPATIBLE_SAFE_BUNDLE_REQUIRED' if args.skip_p1 else 'VERIFIED','packs':results,'before_available_bytes':before,'after_available_bytes':after,
            'method':'APFS clonefile only; no hardlinks; no raw-copy fallback',
            'not_run':['Windows verifier invocation','Blender','inference','research experiments'],
            'gt_private_accessed':False,'original_assets_modified':False}
    (output/'DELIVERY.json').write_text(json.dumps(report,indent=2)+'\n')
    shutil.copyfile(Path(__file__).with_name('verify_safe_pack.py'),output/'verify_safe_pack.py')
    print(json.dumps({'status':'PARTIAL_DELIVERY_READY' if args.skip_p1 else 'DELIVERY_READY','output':str(output),'packs':len(results)}),flush=True)


if __name__=='__main__':
    main()
