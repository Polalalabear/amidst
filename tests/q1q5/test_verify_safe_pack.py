"""#416 synthetic transport checks; no existing data, renderer or network."""
from __future__ import annotations
import importlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import zlib
import pytest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
v=importlib.import_module('verify_safe_pack')
b=importlib.import_module('build_argon_safe_packs')


def make_pack(root, payload=None):
    root.mkdir()
    payload=payload or {'data/observation.json':b'{"evidence_state":"UNKNOWN","gt_read":false}'}
    files={}
    for name,raw in payload.items():
        p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        files[name]={'sha256':v.sha(raw),'bytes':len(raw)}
    doc={'format':'amidst.argon-safe-pack.v1','pack_id':'synthetic','classification':'SYNTHETIC_ONLY',
         'formal_eligible':False,'gt_read':False,'files':files,'sources':{'manifest_sha256':'a'*64}}
    raw=json.dumps(doc).encode();(root/v.MANIFEST).write_bytes(raw)
    return v.sha(raw)


def test_verified_exact_files_and_bytes(tmp_path):
    pin=make_pack(tmp_path/'pack')
    report=v.verify(tmp_path/'pack',pin)
    assert report['status']=='VERIFIED' and report['payload_files']==1 and report['files_including_manifest']==2
    assert report['gt_read'] is False


def test_modified_payload_manifest_pin_and_extra_files(tmp_path):
    root=tmp_path/'pack';pin=make_pack(root)
    (root/'data/observation.json').write_bytes(b'changed')
    with pytest.raises(ValueError,match='FILE_PIN_MISMATCH'):v.verify(root,pin)
    with pytest.raises(ValueError,match='MANIFEST_SHA256_MISMATCH'):v.verify(root,'0'*64)
    (root/'extra.txt').write_text('extra')
    with pytest.raises(ValueError,match='FILE_SET_MISMATCH'):v.verify(root,pin)


@pytest.mark.parametrize('name',['../outside.json','/absolute.json','C:/drive.json',
    'nested\\windows.json','gt_private/x.json','GroundTruth/x.json','trajectory.json','depth.png','keyframes.json'])
def test_bad_names_rejected_before_read(name,tmp_path):
    with pytest.raises(ValueError):v.relative(tmp_path,name)


@pytest.mark.parametrize('data',[{'gt_read':True},{'groundTruth':[]},{'rendererTrack':{}},
    {'visibility':[]},{'depth':[]},{'route':{'waypoints':[1,2]}},{'source':'gt_private/file'},
    {'source':'/x/trajectories/file'}])
def test_private_data_and_nested_locators_rejected(data):
    with pytest.raises(ValueError):v.safe_json(data)


def test_only_static_reference_and_denial_metadata_allowed():
    v.safe_json({'gt_read':False,'visibility_ref':'static-review:CAM_SYN:ROOM_SYN'})
    with pytest.raises(ValueError,match='STATIC_REFERENCE_INVALID'):v.safe_json({'visibility_ref':[1,2]})


def test_symlinks_and_case_collisions_rejected(tmp_path):
    root=tmp_path/'pack';pin=make_pack(root)
    (root/'alias.json').symlink_to(root/'data/observation.json')
    with pytest.raises(ValueError,match='SYMLINK'):v.verify(root,pin)
    other=tmp_path/'case';pin2=make_pack(other,{'a.json':b'{}','A.json':b'{}'})
    with pytest.raises(ValueError,match='CASE_COLLISION'):v.verify(other,pin2)


def test_duplicate_json_keys_fail_closed():
    with pytest.raises(ValueError,match='DUPLICATE_JSON_KEY'):v.json_document(b'{"files":{},"files":{}}')


def png_chunk(kind,raw):
    return struct.pack('>I',len(raw))+kind+raw+struct.pack('>I',zlib.crc32(kind+raw))


def test_rgb_png_structure_and_metadata_rejection():
    header=b'\x89PNG\r\n\x1a\n'+png_chunk(b'IHDR',struct.pack('>IIBBBBB',960,540,8,2,0,0,0))
    body=png_chunk(b'IDAT',zlib.compress((b'\0'+b'\0'*2880)*540))+png_chunk(b'IEND',b'')
    v.inspect_png(header+body)
    with pytest.raises(ValueError,match='PNG_CHUNK_FORBIDDEN'):v.inspect_png(header+png_chunk(b'tEXt',b'x\0synthetic')+body)
    with pytest.raises(ValueError,match='PNG_CRC_INVALID'):v.inspect_png(header+body[:-1]+bytes([body[-1]^1]))


def test_copy_has_independent_inode_and_never_falls_back(tmp_path,monkeypatch):
    src=tmp_path/'source.json';src.write_bytes(b'{}')
    target=tmp_path/'copied.json'
    monkeypatch.setattr(b,'disk',lambda p: 10*1024**3)
    with pytest.raises(ValueError,match='CLONEFILE_FAILED_NO_COPY_FALLBACK'):
        b.clone_one(src,target,v.sha(b'{}'),2,lambda *a:1)
    assert src.read_bytes()==b'{}' and not target.exists()
    def local_test_copy(source,dest,flags):
        shutil.copyfile(os.fsdecode(source),os.fsdecode(dest));return 0
    b.clone_one(src,target,v.sha(b'{}'),2,local_test_copy)
    assert src.stat().st_ino!=target.stat().st_ino and target.read_bytes()==b'{}'


def test_manifest_allowlist_avoids_mutable_source_tree(tmp_path):
    root=tmp_path/'source';root.mkdir();(root/'safe.json').write_bytes(b'{}')
    raw=json.dumps({'files':{'safe.json':{'bytes':2,'sha256':v.sha(b'{}')}}}).encode()
    (root/'MANIFEST.json').write_bytes(raw);(root/'MANIFEST.sha256').write_text(v.sha(raw))
    spec=b.specification(root,'MANIFEST.json',v.sha(raw))
    assert set(spec)=={'MANIFEST.json','MANIFEST.sha256','safe.json'}
    assert b.destination_name('VIEWER/A4-1/safe/media/CAM_X/000000.png','safe_bundle/')=='A4-1/safe/media/CAM_X/000000.png'


@pytest.mark.parametrize('script',['verify_safe_pack','build_argon_safe_packs'])
def test_standalone_help(script,tmp_path):
    result=subprocess.run([sys.executable,'-S',str(ROOT/'scripts'/f'{script}.py'),'--help'],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    assert not list(tmp_path.iterdir())
