"""Independent #418 entry: approved static authoring, no legacy r004 edits."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import zlib

import pytest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('office_static_builder',ROOT/'scripts/build_office_expanded_static.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


def chunk(tag,raw):
    return struct.pack('>I',len(raw))+tag+raw+struct.pack('>I',zlib.crc32(tag+raw)&0xffffffff)


def tiny_png():
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0\x11\x22\x33'))+chunk(b'IEND',b'')


def test_help_needs_no_bpy_or_output(tmp_path):
    r=subprocess.run([sys.executable,'-S',str(Path(b.__file__)),'--help'],cwd=tmp_path,capture_output=True,text=True)
    assert r.returncode==0 and '--authorization-ref' in r.stdout
    assert not list(tmp_path.iterdir())


def test_missing_authorization_does_not_open_parameters(tmp_path):
    with pytest.raises(ValueError,match='EXPLICIT_AUTHORIZATION_REQUIRED'):
        b.main(['--execute','--parameters',str(tmp_path/'not-read.json')])
    assert not list(tmp_path.iterdir())


def test_approved_bytes_and_static_scope():
    p=b.parameters()
    assert [x['region_id'] for x in p['rooms']]==['R101','R102','R103','R104']
    assert len(p['corridor_cameras'])==2 and p['render']['animation_frames']==0
    assert p['render']['camera_static_images']+p['render']['human_only_overhead_images']==7


def test_parameter_tamper_fails(tmp_path):
    p=tmp_path/'params.json';p.write_bytes(b.PARAMETERS.read_bytes()+b' ')
    with pytest.raises(ValueError,match='PARAMETER_PIN_MISMATCH'):b.parameters(p)


def test_output_refuses_existing_and_unapproved_paths(tmp_path):
    p=tmp_path/'output';p.mkdir()
    with pytest.raises(ValueError,match='OUTPUT_EXISTS'):b.new_output(p,approved=p)
    with pytest.raises(ValueError,match='OUTPUT_NOT_APPROVED'):b.new_output(tmp_path/'other',approved=p)


def test_symlink_parent_is_not_followed(tmp_path):
    actual=tmp_path/'actual';actual.mkdir();link=tmp_path/'link';link.symlink_to(actual,target_is_directory=True)
    with pytest.raises(ValueError,match='SYMLINK_FORBIDDEN'):b.new_output(link/'new',approved=link/'new')
    assert not list(actual.iterdir())


@pytest.mark.parametrize('free,starting,ok',[(8.5,True,True),(8.49,True,False),(8,False,True),(7.99,False,False)])
def test_disk_thresholds(monkeypatch,tmp_path,free,starting,ok):
    monkeypatch.setattr(b.shutil,'disk_usage',lambda _:type('Usage',(),{'free':int(free*b.GIB)})())
    if ok:assert b.disk_record(tmp_path/'out','test',start=starting)['free_bytes']==int(free*b.GIB)
    else:
        with pytest.raises(ValueError,match='DISK_GATE'):b.disk_record(tmp_path/'out','test',start=starting)


def test_metadata_strip_preserves_idat_and_no_trailing_payload():
    raw=tiny_png();annotated=raw[:-12]+chunk(b'tEXt',b'SyntheticComment\0opaque')+raw[-12:]
    clean,removed=b.strip_png(annotated)
    assert clean==raw and removed==['tEXt']
    with pytest.raises(ValueError,match='TRAILING'):b.strip_png(raw+b'junk')
    altered=bytearray(raw);altered[30]^=1
    with pytest.raises(ValueError,match='PNG_CRC'):b.strip_png(bytes(altered))
