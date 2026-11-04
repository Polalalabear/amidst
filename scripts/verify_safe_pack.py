"""Verify #416 transfer packs with Python 3.12 stdlib on macOS or Windows.

A required out-of-band manifest hash anchors the complete regular-file set.
Unknown files, links, private names/data, changed hashes and unsafe PNGs fail closed.
No package code is executed and no network/model/Blender is used.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import struct
import zlib

MANIFEST = 'SAFE_PACK_MANIFEST.json'
SHA = re.compile(r'[0-9a-f]{64}\Z')
FORBIDDEN = re.compile(r'(?i)(?:^|[^a-z0-9])(?:gt|gt_private|ground_truth|groundtruth|private|trajector(?:y|ies)|renderer_track|depth|visibility|waypoints?|keyframes?)(?:$|[^a-z0-9])')
ALLOWED_SUFFIXES = {'.json','.jsonl','.png','.py','.mjs','.css','.html','.txt','.command','.sha256'}
MAX_FILE_BYTES = 64 * 1024**2


def require(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_document(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))


def unsafe_token(value):
    separated=re.sub(r'(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])','_',value)
    return FORBIDDEN.search(separated) is not None


def checked_path(path):
    path = Path(path).absolute()
    for i, part in enumerate(path.parts):
        if i == 1 and part == 'private' and len(path.parts)>2 and path.parts[2] in {'tmp','var'}:
            continue
        require(not unsafe_token(part), 'PRIVATE_PATH_FORBIDDEN')
    for parent in reversed((path,*path.parents)):
        require(not parent.is_symlink(), 'SYMLINK_FORBIDDEN')
        require(not getattr(parent,'is_junction',lambda:False)(), 'JUNCTION_FORBIDDEN')
    require(path.resolve() == path, 'NONCANONICAL_PATH')
    return path


def relative(root, name):
    require(isinstance(name,str) and name and '\\' not in name and ':' not in name and '\0' not in name,
            'UNSAFE_RELATIVE_PATH')
    path = PurePosixPath(name)
    require(not path.is_absolute() and '..' not in path.parts and path.as_posix()==name,
            'UNSAFE_RELATIVE_PATH')
    require(not unsafe_token(name), 'PRIVATE_PATH_FORBIDDEN')
    require(path.suffix.lower() in ALLOWED_SUFFIXES, 'FILE_TYPE_FORBIDDEN')
    return checked_path(Path(root).joinpath(*path.parts))


def read(path):
    path = checked_path(path)
    require(path.is_file() and path.stat().st_size <= MAX_FILE_BYTES, 'INPUT_NOT_BOUNDED_FILE')
    return path.read_bytes()


def safe_json(value):
    if isinstance(value,dict):
        for key,item in value.items():
            if key == 'gt_read':
                require(item is False, 'GT_READ_MUST_BE_FALSE')
            elif key == 'visibility_ref':
                # Manual static graph refs are not renderer visibility data.
                require(isinstance(item,str) and (item.startswith('vis:') or item.startswith('static-review:')),
                        'STATIC_REFERENCE_INVALID')
            else:
                require(not unsafe_token(key), 'PRIVATE_DATA_FORBIDDEN')
            safe_json(item)
    elif isinstance(value,list):
        for item in value:
            safe_json(item)
    elif isinstance(value,str):
        require(not re.search(r'(?i)(gt_private|ground_truth|(?:^|[/\\])(?:private|trajectory|trajectories|depth)(?:[/\\]|$))', value),
                'PRIVATE_LOCATOR_FORBIDDEN')
        require(not re.search(r'sk-[A-Za-z0-9_-]{20,}',value), 'CREDENTIAL_CONTENT_FORBIDDEN')


def inspect_png(raw):
    require(raw[:8]==b'\x89PNG\r\n\x1a\n','PNG_INVALID')
    offset, kinds, compressed = 8, [], []
    allowed = {b'IHDR',b'IDAT',b'IEND',b'cHRM',b'gAMA',b'oFFs',b'pHYs',b'sRGB'}
    while offset < len(raw):
        require(offset+12<=len(raw),'PNG_INVALID')
        size=struct.unpack('>I',raw[offset:offset+4])[0]
        kind=raw[offset+4:offset+8]
        end=offset+size+12
        require(end<=len(raw) and kind in allowed,'PNG_CHUNK_FORBIDDEN')
        data=raw[offset+8:end-4]
        require(zlib.crc32(kind+data)==struct.unpack('>I',raw[end-4:end])[0],'PNG_CRC_INVALID')
        if kind==b'IHDR':
            require(not kinds and size==13,'PNG_INVALID')
            width,height,bits,color,compression,filtering,interlace=struct.unpack('>IIBBBBB',data)
            require((width,height,bits,color,compression,filtering,interlace)==(960,540,8,2,0,0,0),'PNG_FORMAT_INVALID')
        elif kind==b'IDAT':
            require(kinds and kinds[-1] in allowed-{b'IEND'} and
                    (b'IDAT' not in kinds or kinds[-1]==b'IDAT'),'PNG_INVALID')
            compressed.append(data)
        elif kind==b'IEND':
            require(size==0 and compressed and end==len(raw),'PNG_INVALID')
        kinds.append(kind);offset=end
    require(kinds and kinds[0]==b'IHDR' and kinds[-1]==b'IEND','PNG_INVALID')
    expected=(960*3+1)*540
    decoder=zlib.decompressobj()
    pixels=decoder.decompress(b''.join(compressed),expected+1)
    require(len(pixels)==expected and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
            and all(pixels[i]<=4 for i in range(0,expected,960*3+1)),'PNG_PIXEL_STREAM_INVALID')


def inspect_payload(name, raw):
    suffix=PurePosixPath(name).suffix.lower()
    if suffix=='.png':
        inspect_png(raw)
    elif suffix=='.json':
        safe_json(json_document(raw))
    elif suffix=='.jsonl':
        for row in raw.splitlines():
            if row.strip():safe_json(json_document(row))
    else:
        # Bundled source is never executed. Denial constants are code, not GT data.
        require(not re.search(rb'sk-[A-Za-z0-9_-]{20,}',raw),'CREDENTIAL_CONTENT_FORBIDDEN')


def file_set(root):
    found=set()
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            path=checked_path(Path(parent)/name)
            relative_name=path.relative_to(root).as_posix()
            require(not unsafe_token(relative_name),'PRIVATE_PATH_FORBIDDEN')
            if path.is_file():found.add(relative_name)
    return found


def verify(root, manifest_sha256):
    root=checked_path(root)
    require(SHA.fullmatch(manifest_sha256 or ''),'MANIFEST_SHA256_REQUIRED')
    raw=read(root/MANIFEST)
    require(sha(raw)==manifest_sha256,'MANIFEST_SHA256_MISMATCH')
    manifest=json_document(raw)
    require(set(manifest)=={'format','pack_id','classification','formal_eligible','gt_read','files','sources'},'MANIFEST_KEYS_INVALID')
    require(manifest['format']=='amidst.argon-safe-pack.v1' and manifest['gt_read'] is False
            and manifest['formal_eligible'] is False,'SAFE_MANIFEST_INVALID')
    files=manifest['files']
    require(isinstance(files,dict) and files,'FILES_REQUIRED')
    # NTFS uses case-insensitive names; reject colliding paths before opening payloads.
    require(len({n.casefold() for n in files})==len(files),'CASE_COLLISION')
    for name,row in files.items():
        relative(root,name)
        require(isinstance(row,dict) and set(row)=={'bytes','sha256'} and type(row['bytes']) is int
                and row['bytes']>=0 and isinstance(row['sha256'],str) and SHA.fullmatch(row['sha256']),
                'FILE_ENTRY_INVALID')
    require(file_set(root)==set(files)|{MANIFEST},'FILE_SET_MISMATCH')
    total=0
    for name,row in files.items():
        payload=read(relative(root,name))
        require(len(payload)==row['bytes'] and sha(payload)==row['sha256'],'FILE_PIN_MISMATCH')
        inspect_payload(name,payload)
        total+=len(payload)
    return {'status':'VERIFIED','pack_id':manifest['pack_id'],'payload_files':len(files),
            'files_including_manifest':len(files)+1,'payload_bytes':total,
            'total_bytes_including_manifest':total+len(raw),'manifest_sha256':manifest_sha256,
            'png_files':sum(n.endswith('.png') for n in files),'gt_read':False,'formal_eligible':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pack',type=Path,required=True)
    p.add_argument('--manifest-sha256',required=True)
    args=p.parse_args(argv)
    try:
        result=verify(args.pack,args.manifest_sha256)
    except (OSError,ValueError,TypeError,KeyError,AttributeError,zlib.error) as exc:
        # Never echo data values or traceback locals.
        print(json.dumps({'status':'INVALID','error':str(exc) if isinstance(exc,ValueError) else type(exc).__name__}))
        return 1
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
