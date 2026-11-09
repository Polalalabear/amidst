"""Create LOCAL playback-only JPEG/WebP copies from exact pinned RGB files.

No original bytes, run clocks or inference/index inputs are written. The manifest
maps every derivative to the original PNG byte hash; it is not model evidence.
"""
from pathlib import Path
import argparse
import hashlib
from io import BytesIO
import json
import os
import platform
import shutil
import stat
import time
import zlib

MIN_FREE = 8 * 1024**3
P1_PIN = '6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7'
D124_PIN = 'ad3c66f21ef6713a76b0bb6505a7e5eb3514fa346f9279c42d7b486479281f01'


def require(ok, code):
    if not ok:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def read_pin(path, pin):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path
            and all(not p.is_symlink() for p in (path, *path.parents)), 'CANONICAL_REGULAR_FILE')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        require(stat.S_ISREG(info.st_mode) and info.st_size <= 16_777_216, 'BOUNDED_REGULAR_FILE')
        raw = stream.read(16_777_217)
    require(len(raw) == info.st_size and sha(raw) == pin, 'BYTE_PIN_MISMATCH')
    return raw


def safe_join(root, rel):
    require(isinstance(rel, str) and rel and '\\' not in rel and not Path(rel).is_absolute()
            and '..' not in Path(rel).parts and Path(rel).as_posix() == rel, 'RELATIVE_PATH_REQUIRED')
    return root/rel


def make_plan(p1_root, d124_root):
    p1, d124 = Path(p1_root), Path(d124_root)
    p1m = json.loads(read_pin(p1/'MANIFEST.json', P1_PIN))
    bundle = json.loads(read_pin(p1/'BUNDLE.json', p1m['files']['BUNDLE.json']['sha256']))
    rgb = json.loads(read_pin(safe_join(p1, bundle['rgb_ref']), bundle['rgb_file_sha256']))
    require(rgb['sampling']['fps'] == 20 and rgb['sampling']['duration_s'] == 8, 'P1_SOURCE_GRID')
    rows, cases = [], []
    cameras = sorted({r['camera_id'] for r in rgb['records']})
    cases.append({'key': 'B-05b', 'source_kind': 'SYNTHETIC', 'run_id': rgb['run_id'],
                  'fps': 20, 'frames': 160, 'cameras': cameras})
    for r in rgb['records']:
        rel = (Path('data/rgb')/r['rgb_ref']).as_posix()
        require(rel.startswith('data/rgb/media/') and p1m['files'][rel]['sha256'] == r['file_sha256'], 'P1_FRAME_PIN')
        rows.append(dict(case='B-05b',camera_id=r['camera_id'],frame_index=r['frame_index'],
                         source_time_us=r['frame_index']*50_000,path=str(safe_join(p1,rel)),sha256=r['file_sha256']))
    dm = json.loads(read_pin(d124/'MANIFEST.json', D124_PIN))
    for label in ['A4-1', 'B4-1']:
        rel = 'runs/'+label+'.json'
        descriptor = json.loads(read_pin(d124/rel,dm['files'][rel]))
        clock = json.loads(read_pin(safe_join(d124,descriptor['clock_ref']),dm['files'][descriptor['clock_ref']]))
        require(clock['run_id']==descriptor['run_id'] and descriptor['sampling']['fps']==5, 'D124_GRID')
        count=clock['source_duration_us']//200_000
        cases.append(dict(key=label,source_kind='ACTUAL_BLENDER',run_id=descriptor['run_id'],
                          fps=5,frames=count,cameras=descriptor['camera_ids']))
        for frame in descriptor['frames']:
            rel=frame['filename'];require(dm['files'][rel]==frame['file_sha256'] and rel==f"rgb/{descriptor['run_id']}/{frame['camera_id']}/frame_{frame['frame_index']:06d}.png",'D124_FRAME_PIN')
            rows.append(dict(case=label,camera_id=frame['camera_id'],frame_index=frame['frame_index'],
                             source_time_us=frame['frame_index']*200_000,path=str(safe_join(d124,rel)),sha256=frame['file_sha256']))
    for case in cases:
        actual={(r['camera_id'],r['frame_index']) for r in rows if r['case']==case['key']}
        require(actual=={(c,i) for c in case['cameras'] for i in range(case['frames'])},'COMPLETE_GRID')
    return {'purpose':'LOCAL_PLAYBACK_ONLY_NOT_INFERENCE','original_png_written':False,
            'source_manifests':{'P1':P1_PIN,'D124':D124_PIN},'cases':cases,'rows':rows}


def png_chunks(raw):
    require(raw[:8]==b'\x89PNG\r\n\x1a\n','PNG_SIGNATURE')
    offset=8;names=[]
    while offset<len(raw):
        require(offset+12<=len(raw),'PNG_TRUNCATED')
        n=int.from_bytes(raw[offset:offset+4],'big');kind=raw[offset+4:offset+8];end=offset+n+12
        require(end<=len(raw),'PNG_TRUNCATED')
        require(zlib.crc32(raw[offset+4:end-4])==int.from_bytes(raw[end-4:end],'big'),'PNG_CRC')
        names.append(kind.decode('ascii'));offset=end
        if kind==b'IEND':
            require(n==0 and offset==len(raw),'PNG_TRAILING_DATA');break
    require(names and names[0]=='IHDR' and names[-1]=='IEND','PNG_STRUCTURE')
    # Baseline may serve exact original bytes only if metadata cannot expose private text.
    require(set(names)<={'IHDR','IDAT','IEND','sRGB','gAMA','pHYs','cHRM','bKGD','sBIT'},'PNG_METADATA_NOT_PUBLIC')
    return names


def public_png(raw):
    """Drop ancillary metadata without interpreting it; preserve pixel chunks."""
    require(raw[:8]==b'\x89PNG\r\n\x1a\n','PNG_SIGNATURE')
    allowed={b'IHDR',b'IDAT',b'IEND',b'sRGB',b'gAMA',b'pHYs',b'cHRM',b'bKGD',b'sBIT'}
    out=bytearray(raw[:8]);offset=8
    while offset<len(raw):
        require(offset+12<=len(raw),'PNG_TRUNCATED')
        size=int.from_bytes(raw[offset:offset+4],'big');kind=raw[offset+4:offset+8];end=offset+size+12
        require(end<=len(raw),'PNG_TRUNCATED')
        require(zlib.crc32(raw[offset+4:end-4])==int.from_bytes(raw[end-4:end],'big'),'PNG_CRC')
        require(kind in allowed or kind[0]&32,'UNKNOWN_CRITICAL_CHUNK')
        if kind in allowed:out.extend(raw[offset:end])
        offset=end
        if kind==b'IEND':
            require(size==0 and offset==len(raw),'PNG_TRAILING_DATA');break
    result=bytes(out);png_chunks(result);return result


def encode(raw, fmt):
    from PIL import Image
    require(fmt in {'jpeg','webp'}, 'EXPLICIT_PROXY_FORMAT')
    raw=public_png(raw)
    image=Image.open(BytesIO(raw));require(image.format=='PNG' and not getattr(image,'is_animated',False),'ONE_PNG_FRAME')
    require(image.width*image.height<=4_194_304,'PIXEL_SIZE')
    if 'A' in image.getbands():require(image.getchannel('A').getextrema()==(255,255),'OPAQUE_SOURCE_REQUIRED')
    image=image.convert('RGB');out=BytesIO()
    if fmt=='jpeg':image.save(out,format='JPEG',quality=90,subsampling=0,optimize=True)
    else:image.save(out,format='WEBP',quality=90,method=4)
    return out.getvalue(),list(image.size)


def build(plan_path, plan_sha, out_root):
    from PIL import Image,features
    require(features.check('webp'),'EXISTING_WEBP_ENCODER_REQUIRED')
    plan=json.loads(read_pin(plan_path,plan_sha));out=Path(out_root)
    require(plan['purpose']=='LOCAL_PLAYBACK_ONLY_NOT_INFERENCE' and not plan['original_png_written'],'PLAYBACK_ONLY')
    require(out.is_absolute() and out.resolve()==out and not out.exists(),'NEW_CANONICAL_OUTPUT')
    require(shutil.disk_usage(out.parent).free>=MIN_FREE,'LOW_DISK');out.mkdir()
    code_sha=sha(Path(__file__).read_bytes())
    began=time.monotonic();rows=[];minimum=shutil.disk_usage(out).free
    for i,source in enumerate(plan['rows']):
        minimum=min(minimum,shutil.disk_usage(out).free);require(minimum>=MIN_FREE,'LOW_DISK')
        require(Path(source['path']).suffix=='.png','PNG_SOURCE_ONLY')
        raw=read_pin(source['path'],source['sha256']);safe=public_png(raw)
        row=dict(source,source_bytes=len(raw),png_public_sha256=sha(safe),png_public_bytes=len(safe),proxies={})
        for fmt,ext in [('jpeg','jpg'),('webp','webp')]:
            payload,size=encode(raw,fmt);rel=f"{fmt}/{source['case']}/{source['camera_id']}/{source['frame_index']:06d}.{ext}"
            target=out/rel;target.parent.mkdir(parents=True,exist_ok=True)
            require(shutil.disk_usage(out).free>=MIN_FREE,'LOW_DISK')
            with target.open('xb') as stream:stream.write(payload)
            row['image_size_px']=size;row['proxies'][fmt]={'relative_path':rel,'sha256':sha(payload),'bytes':len(payload)}
        require(sha(Path(source['path']).read_bytes())==source['sha256'],'ORIGINAL_CHANGED')
        rows.append(row)
        if (i+1)%100==0:print(json.dumps({'converted':i+1,'total':len(plan['rows'])}),flush=True)
    require(code_sha==sha(Path(__file__).read_bytes()),'ENCODER_SOURCE_CHANGED')
    result={**plan,'rows':rows,'executed_script_sha256':code_sha,'encoder':{'pillow':Image.__version__,'jpeg':{'quality':90,'subsampling':0,'optimize':True},
            'webp':{'quality':90,'method':4}},'plan_sha256':plan_sha,'minimum_free_bytes':minimum,
            'conversion_seconds':time.monotonic()-began,'platform':platform.platform()}
    with (out/'manifest.json').open('xb') as stream:stream.write(canonical(result)+b'\n')
    print(json.dumps({'status':'COMPLETE','frames':len(rows),'manifest_sha256':sha((out/'manifest.json').read_bytes()),
                      'source_png_bytes':sum(r['source_bytes'] for r in rows),'proxy_bytes':{f:sum(r['proxies'][f]['bytes'] for r in rows) for f in ['jpeg','webp']}}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    plan=sub.add_parser('plan');plan.add_argument('--p1',type=Path,required=True);plan.add_argument('--d124',type=Path,required=True);plan.add_argument('--out',type=Path,required=True)
    run=sub.add_parser('build');run.add_argument('--plan',type=Path,required=True);run.add_argument('--plan-sha256',required=True);run.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.command=='plan':
        value=make_plan(args.p1,args.d124)
        with args.out.open('xb') as stream:stream.write(canonical(value)+b'\n')
        print(json.dumps({'cases':value['cases'],'frames':len(value['rows']),'plan_sha256':sha(args.out.read_bytes())}))
    else:build(args.plan,args.plan_sha256,args.out)
