"""P1 stdlib adapter boundaries; no model, renderer, GT, or full datasets."""
import hashlib
import json
import zlib

import pytest

from amidst.q1q5.p1_workbench import local, public_png, verify_bundle


def manifest(root):
    payload=b'bounded test';(root/'payload.json').write_bytes(payload)
    m={'schema_version':'q-demo.p1-bundle-manifest.v1','source_commit':'a'*40,'total_bytes':len(payload),
       'files':{'payload.json':{'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload)}}}
    raw=json.dumps(m).encode();(root/'MANIFEST.json').write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_pins_relocate_and_mutable_return_is_not_a_runtime_input(tmp_path):
    pin=manifest(tmp_path);(tmp_path/'RETURN').mkdir();(tmp_path/'RETURN/review.csv').write_text('human result')
    assert verify_bundle(tmp_path,pin)['total_bytes']==12
    (tmp_path/'RETURN/review.csv').write_text('changed human result')
    assert verify_bundle(tmp_path,pin)['source_commit']=='a'*40


@pytest.mark.parametrize('kind',['bytes','size','manifest'])
def test_bundle_refuses_tampering(tmp_path,kind):
    pin=manifest(tmp_path)
    if kind=='bytes':(tmp_path/'payload.json').write_bytes(b'changed test')
    elif kind=='size':(tmp_path/'payload.json').write_bytes(b'x')
    else:pin='0'*64
    with pytest.raises(ValueError):verify_bundle(tmp_path,pin)


@pytest.mark.parametrize('ref',['../secret','/etc/passwd','a/../../secret','a\\b'])
def test_relative_scope_rejects_escape(tmp_path,ref):
    with pytest.raises(ValueError):local(tmp_path,ref)


def test_symlink_is_not_a_portable_asset(tmp_path):
    (tmp_path/'actual').write_text('asset');(tmp_path/'alias').symlink_to(tmp_path/'actual')
    with pytest.raises(ValueError):local(tmp_path,'alias')


def chunk(kind,payload):return len(payload).to_bytes(4,'big')+kind+payload+zlib.crc32(kind+payload).to_bytes(4,'big')


def test_png_text_removed_and_crc_errors_fail_closed():
    header=chunk(b'IHDR',(1).to_bytes(4,'big')*2+bytes([8,2,0,0,0]));end=chunk(b'IEND',b'')
    raw=b'\x89PNG\r\n\x1a\n'+header+chunk(b'tEXt',b'source\0private')+end
    assert public_png(raw)==b'\x89PNG\r\n\x1a\n'+header+end
    with pytest.raises(ValueError):public_png(raw[:-1]+b'x')
