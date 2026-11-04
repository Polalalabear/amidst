"""#416 source/served pin translation and lossless ancillary stripping."""
from __future__ import annotations
import importlib
import json
from pathlib import Path
import struct
import sys
import zlib
import pytest
from amidst.q1q5.p1_workbench import bundle_media_reader, public_png

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
s=importlib.import_module('strip_p1_bundle')
v=importlib.import_module('verify_safe_pack')


def chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))


def test_strip_keeps_idat_bytes_and_decoded_pixels():
    header=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',960,540,8,2,0,0,0))
    data=chunk(b'IDAT',zlib.compress((b'\0'+b'\x12\x34\x56'*960)*540))
    raw=header+chunk(b'tEXt',b'SyntheticKey\0not printed')+data+chunk(b'IEND',b'')
    clean,keys,idat=s.strip_png(raw)
    assert clean==header+data+chunk(b'IEND',b'')
    assert keys==['tEXt:SyntheticKey'] and idat==v.sha(data)
    assert s.pixels(raw)==s.pixels(clean)
    assert v.sha(raw)!=v.sha(clean)


def test_public_bridge_also_removes_exif():
    header=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))
    end=chunk(b'IEND',b'')
    assert public_png(header+chunk(b'eXIf',b'synthetic')+end)==header+end


def translation_fixture(root):
    served=b'bounded new RGB bytes'
    name='data/rgb/media/A-0000.png'
    p=root/name;p.parent.mkdir(parents=True);p.write_bytes(served)
    source={'files':{name:{'sha256':'a'*64,'bytes':999}}}
    source_raw=json.dumps(source).encode();(root/'SOURCE_MANIFEST.json').write_bytes(source_raw)
    entry={'original_file_sha256':'a'*64,'file_sha256':v.sha(served),
           'original_pixel_sha256':'b'*64,'pixel_sha256':'b'*64,'idat_sha256':'c'*64,'metadata_key_names':[]}
    mapping={'format':'p1-media-transform.v1','source_manifest_ref':'SOURCE_MANIFEST.json',
             'source_manifest_sha256':v.sha(source_raw),'entries':{name:entry}}
    raw=json.dumps(mapping).encode();(root/'MEDIA_TRANSFORM.json').write_bytes(raw)
    manifest={'media_transform_ref':'MEDIA_TRANSFORM.json','files':{
        'MEDIA_TRANSFORM.json':{'sha256':v.sha(raw)},'SOURCE_MANIFEST.json':{'sha256':v.sha(source_raw)},
        name:{'sha256':v.sha(served)}}}
    return p,mapping,manifest


def test_source_hash_remains_original_while_bytes_use_served_pin(tmp_path):
    p,mapping,manifest=translation_fixture(tmp_path)
    reader=bundle_media_reader(tmp_path,manifest)
    assert reader(p,'a'*64)==p.read_bytes()
    with pytest.raises(ValueError,match='MEDIA_TRANSFORM_SOURCE_MISMATCH'):reader(p,'d'*64)
    p.write_bytes(b'changed')
    with pytest.raises(ValueError,match='RGB_PIN_MISMATCH'):reader(p,'a'*64)


@pytest.mark.parametrize('field,value',[
    ('original_file_sha256','d'*64),('file_sha256','d'*64),('pixel_sha256','d'*64)])
def test_rehashed_map_still_checks_original_and_served_and_pixel_pins(tmp_path,field,value):
    p,mapping,manifest=translation_fixture(tmp_path)
    mapping['entries'][p.relative_to(tmp_path).as_posix()][field]=value
    raw=json.dumps(mapping).encode();(tmp_path/'MEDIA_TRANSFORM.json').write_bytes(raw)
    manifest['files']['MEDIA_TRANSFORM.json']['sha256']=v.sha(raw)
    with pytest.raises(ValueError,match='MEDIA_TRANSFORM_PIN_MISMATCH'):bundle_media_reader(tmp_path,manifest)


def test_missing_entry_and_manifest_tamper_fail_closed(tmp_path):
    p,mapping,manifest=translation_fixture(tmp_path)
    mapping['entries']['other.png']=mapping['entries'].pop(p.relative_to(tmp_path).as_posix())
    raw=json.dumps(mapping).encode();(tmp_path/'MEDIA_TRANSFORM.json').write_bytes(raw)
    manifest['files']['MEDIA_TRANSFORM.json']['sha256']=v.sha(raw)
    with pytest.raises(ValueError,match='MEDIA_TRANSFORM_FILE_SET'):bundle_media_reader(tmp_path,manifest)
    manifest['files']['SOURCE_MANIFEST.json']['sha256']='f'*64
    with pytest.raises(ValueError,match='MEDIA_TRANSFORM_SOURCE_PIN'):bundle_media_reader(tmp_path,manifest)


def test_ordinary_original_bundle_keeps_original_reader():
    from amidst.q1q5.p1_workbench import binary
    assert bundle_media_reader(Path('/unused'),{'files':{}}) is binary
