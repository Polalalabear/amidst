"""Independent #418 entry: approved static authoring, no legacy r004 edits."""
from __future__ import annotations

import importlib.util
from copy import deepcopy
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
sys.path.insert(0,str(ROOT/'scripts'))
import office_expanded_static_graphs as g
GRAPH=ROOT/'configs/q1q5/graphs/office_expanded_r005'


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


def source_documents():
    values={name:g.parse((GRAPH/name).read_bytes()) for name in
            ['build_receipt.json','cameras.json','regions.json','coverage_review.json','source_pins.json']}
    return values


def compile_values(values):
    pins=values['source_pins.json']['files']
    return g.compile_graphs(values['build_receipt.json'],values['cameras.json'],values['regions.json'],
        values['coverage_review.json'],catalog_sha=pins['cameras.json'],geometry_sha=pins['regions.json'],
        review_sha=pins['coverage_review.json'],receipt_sha=pins['build_receipt.json'])


def test_source_bound_curated_static_inputs_and_four_room_coverage():
    d=source_documents();pins=d['source_pins.json']
    assert d['build_receipt.json']['builder_sha256']==b.sha(Path(b.__file__).read_bytes())
    for name,pin in pins['files'].items():assert b.sha((GRAPH/name).read_bytes())==pin
    region,camera=compile_values(d)
    assert region==g.parse((GRAPH/'region_graph.json').read_bytes())
    assert camera==g.parse((GRAPH/'camera_graph.json').read_bytes())
    rooms={r['region_id'] for r in region['regions'] if r['kind']=='ROOM'}
    covered={c['region_id'] for row in camera['cameras'] for c in row['covered_regions']
             if c['basis']=='MANUAL_ON_STATIC_FRAME'}
    assert rooms=={'R101','R102','R103','R104'} and rooms<=covered
    assert len(camera['cameras'])==6 and len(camera['transitions'])==10
    assert region['approval_status']==camera['approval_status']=='DRAFT'
    assert all(e['traversability']=='TOPOLOGICAL_ONLY' and e['state']=='UNKNOWN' for e in region['edges'])
    assert all(t['path_traversability']=='TOPOLOGICAL_ONLY' and t['relation']=='UNKNOWN'
               and t['ranking_area_m2'] is None for t in camera['transitions'])


@pytest.mark.parametrize('failure',['frame','calibration','source','review_method','missing_review','not_visible','run_binding'])
def test_no_manual_coverage_without_its_actual_source_pin(failure):
    d=deepcopy(source_documents());review=d['coverage_review.json'];camera=d['cameras.json']['cameras'][0]
    if failure=='frame':review['camera_reviews'][0]['static_frame_sha256']='a'*64
    if failure=='calibration':camera['fx']+=1
    if failure=='source':camera['source_sha256']='a'*64
    if failure=='review_method':review['review_method']='AUTOMATIC_FRUSTUM_ONLY'
    if failure=='missing_review':review['camera_reviews'].pop()
    if failure=='not_visible':review['camera_reviews'][0]['region_visible']=False
    if failure=='run_binding':d['cameras.json']['run_bindings']=['synthetic-non-static-run']
    with pytest.raises(ValueError):compile_values(d)


def test_receipt_symlink_rejected_before_reading(tmp_path):
    outside=tmp_path/'outside';outside.write_text('not-a-receipt')
    root=tmp_path/'bundle';root.mkdir();(root/'build_receipt.json').symlink_to(outside)
    with pytest.raises(ValueError,match='SYMLINK_FORBIDDEN'):g.verify_local(root)


def test_duplicate_json_keys_are_not_accepted():
    with pytest.raises(ValueError,match='DUPLICATE_KEY'):g.parse(b'{"scene_id":"a","scene_id":"b"}')


def test_r004_v3_1_bytes_are_unchanged():
    hashes={'region_graph_v3_1.json':'a2f737805cf5446c6ba01fa4bebfddd2186d040cbd94314cf573c082191b24e1',
            'camera_graph_v3_1.json':'e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409',
            'build_plan_v3_1.json':'277d0e9376f8d0bcb055d11aac7e856a4ae50b541bf7519c719a998c2f1b3d51'}
    for name,pin in hashes.items():assert b.sha((ROOT/'configs/q1q5/graphs/r004'/name).read_bytes())==pin
