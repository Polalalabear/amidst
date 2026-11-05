"""Pinned safe static metadata only; no media or runtime acceptance."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

import pytest

from amidst.q1q5.graphs import GraphError, GraphBundle
from amidst.q1q5.scene_graphs import (
    ROOT, R004, R004_PINS, R005, R005_MANIFEST_SHA256,
    _pending_graphs, load_scene_graphs, location_coverage, room_coverage_pending,
)
from amidst.q1q5.store import canonical_hash


def test_r004_original_bytes_and_loader_are_preserved():
    graphs = load_scene_graphs('r004', run_scene_id=R004)
    for name, expected in R004_PINS.items():
        assert hashlib.sha256((ROOT / 'r004' / name).read_bytes()).hexdigest() == expected
    assert graphs.region['scene_id'] == R004
    assert graphs.camera == load_scene_graphs(R004).camera


def test_r005_selects_separate_pinned_pending_skeleton():
    graphs = load_scene_graphs(R005, run_scene_id=R005)
    assert not isinstance(graphs, GraphBundle)
    assert graphs.region == load_scene_graphs('r005').region
    assert len([r for r in graphs.region['regions'] if r['kind'] == 'ROOM']) == 4
    assert len(graphs.camera['cameras']) == 6 and len(graphs.camera['transitions']) == 10
    for camera in graphs.camera['cameras']:
        for row in camera['covered_regions']:
            assert row['basis'] == 'NOT_EVALUATED'
            assert row['visibility_ref'] is row['visible_area_m2'] is None
    copy = graphs.camera; copy['cameras'].clear()
    assert len(graphs.camera['cameras']) == 6


def test_pending_location_has_no_hits_and_run_catalog_is_required():
    graphs = load_scene_graphs(R005)
    regions = [r['region_id'] for r in graphs.region['regions']]
    cameras = [r['camera_id'] for r in graphs.camera['cameras']]
    result = location_coverage(graphs, regions, run_camera_ids=cameras)
    assert result['hits'] == {} and len(result['not_evaluated']) == len(cameras)
    assert {r['reason'] for r in result['not_evaluated']} == {'COVERAGE_BASIS_UNSUPPORTED'}
    missing = location_coverage(graphs, regions, run_camera_ids=[])
    assert missing['hits'] == {} and {r['reason'] for r in missing['not_evaluated']} == {'CAMERA_NOT_IN_RUN'}
    with pytest.raises(GraphError, match='Unknown region'):
        location_coverage(graphs, ['NOT_IN_GRAPH'], run_camera_ids=cameras)


def test_source_bound_room_coverage_acceptance():
    graphs = load_scene_graphs(R005)
    reason = room_coverage_pending(graphs)
    if reason:
        pytest.skip(reason + ': r005 manual static-frame coverage awaits #464; AI review is not human approval')
    assert room_coverage_pending(graphs) is None


@pytest.mark.parametrize('scene,run,code', [('UNKNOWN', None, 'SCENE_UNKNOWN'), ('r005', R004, 'SCENE_RUN_MISMATCH')])
def test_unsupported_scene_and_cross_run_fail_closed(scene, run, code):
    with pytest.raises(GraphError) as exc:
        load_scene_graphs(scene, run_scene_id=run)
    assert exc.value.code == code


@pytest.mark.parametrize('change', ['missing_manifest', 'missing_graph', 'missing_pin', 'tamper', 'symlink'])
def test_missing_or_changed_evidence_cannot_be_skipped(tmp_path, change):
    target = tmp_path / R005 / 'search_skeleton'
    shutil.copytree(ROOT / R005 / 'search_skeleton', target)
    if change == 'missing_manifest': (target / 'source_pins.json').unlink()
    elif change == 'missing_graph': (target / 'camera_graph.json').unlink()
    elif change == 'missing_pin':
        doc = json.loads((target / 'source_pins.json').read_bytes()); doc['files'].pop('camera_graph.json')
        (target / 'source_pins.json').write_text(json.dumps(doc))
    elif change == 'tamper':
        with (target / 'camera_graph.json').open('ab') as output: output.write(b' ')
    else:
        (target / 'camera_graph.json').unlink()
        (target / 'camera_graph.json').symlink_to(ROOT / R005 / 'search_skeleton/camera_graph.json')
    with pytest.raises(GraphError) as exc:
        load_scene_graphs('r005', graph_root=tmp_path)
    assert exc.value.code in {'GRAPH_EVIDENCE_MISSING', 'GRAPH_PIN_MISMATCH', 'GRAPH_SOURCE_UNSAFE'}


def reseal(r, c, pins):
    for doc, prefix, pin in [(r, 'rgraph', 'region_content_sha256'), (c, 'cgraph', 'camera_content_sha256')]:
        if prefix == 'cgraph': doc['region_graph_sha256'] = r['content_sha256']
        doc['content_sha256'] = canonical_hash(doc, exclude=('graph_id', 'content_sha256', 'stats'))
        doc['graph_id'] = f"{prefix}:r005:static:{doc['content_sha256'][:16]}"
        pins[pin] = doc['content_sha256']


@pytest.mark.parametrize('change', ['manual', 'basis', 'claim', 'wrong_region', 'wrong_camera', 'wrong_edge', 'authority', 'cross_scene', 'unknown_field'])
def test_semantic_counterexamples_fail_even_with_recomputed_content_pins(change):
    graphs = load_scene_graphs('r005'); r, c = graphs.region, graphs.camera
    pins = json.loads((ROOT / R005 / 'search_skeleton/source_pins.json').read_bytes())
    if change == 'manual': c['cameras'][0]['covered_regions'][0]['basis'] = 'MANUAL_ON_STATIC_FRAME'
    elif change == 'basis': c['cameras'][0]['covered_regions'][0]['basis'] = 'UNKNOWN_BASIS'
    elif change == 'claim': c['cameras'][0]['covered_regions'][0]['visibility_ref'] = 'review:UNAPPROVED'
    elif change == 'wrong_region': r['edges'][0]['regions'][0] = 'MISSING'
    elif change == 'wrong_camera': c['transitions'][0]['to_camera_id'] = 'MISSING'
    elif change == 'wrong_edge': c['transitions'][0]['edge_path'][0] = 'MISSING'
    elif change == 'authority': c['transitions'][0]['path_traversability'] = 'APPROVED_WALKABLE'
    elif change == 'cross_scene': c['scene_id'] = R004
    else: c['unregistered_authority'] = True
    reseal(r, c, pins)
    with pytest.raises(GraphError): _pending_graphs(r, c, pins)


def test_exact_source_reference_is_retained_without_its_ai_coverage_grant():
    raw = (ROOT / R005 / 'search_skeleton/source_pins.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == R005_MANIFEST_SHA256
    pins = json.loads(raw)
    assert pins['source_commit'] == '39b9c4323288cae8c52532277cdd6dc75b63a965'
    assert pins['source_files'] == {
        'region_graph.json': 'c61b1ce126d1fcae34f517f0d500d614990aa66ca4770c09e73d797d991ddf50',
        'camera_graph.json': '0ed4b6ca74917459d25935915fdfe2c20e274924d89845b08e89db858286d0f9',
    }
    assert room_coverage_pending(load_scene_graphs(R005)) == 'SCENE_ROOM_COVERAGE_PENDING'
