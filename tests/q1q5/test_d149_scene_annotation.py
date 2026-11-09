"""D149 acceptance gate: the static car in A4-1 CAM_EXT_CAR is a scene annotation (written by Claude, implemented by Codex).

User decision D149 (#93, 2026-11-09): COCO RT-DETR never finds the box-model car, so 查找 returns it from the
hand-drawn annotation ``configs/q1q5/scene_annotations_v1.json``. The hit carries a ``SCENE_ANNOTATION`` basis
(evidence_state ``ANNOTATED``), is shown as 場景標註（非偵測）, and is never counted as a detection, never used by
tracking, ranking or identity. Real-data tests need ``AMIDST_DEMO_HOME`` (and >= 8 GiB free disk).
"""
import hashlib
import json
from collections import Counter
from pathlib import Path

import pytest

from test_bootstrap_class_counts import recorded_demo  # noqa: F401

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / 'configs/q1q5/scene_annotations_v1.json'
SCHEMA = ROOT / 'docs/contracts/schemas/q-core.search-track.v1.schema.json'
A4_RUN = 'ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1'
FORBIDDEN = ('ground_truth', 'gt_', 'visibility', 'depth', 'trajectory', 'renderer_track')


def annotations():
    return json.loads(CONFIG.read_text())


# ---- runs everywhere --------------------------------------------------------------------------------------

def test_annotation_set_is_valid_bounded_and_gt_free():
    doc = annotations()
    assert doc['schema_version'] == 'q-demo.scene-annotations.v1'
    [a] = doc['annotations']
    assert a['annotation_id'] == 'A4-1:CAM_EXT_CAR:car:static' and a['run_id'] == A4_RUN
    assert a['camera_id'] == 'CAM_EXT_CAR' and a['class_label'] == 'car' and a['motion'] == 'STATIC'
    x0, y0, x1, y1 = a['bbox_xyxy_px']; w, h = a['frame_size_px']
    assert 0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h
    assert a['range_us'][0] < a['range_us'][1]
    assert all(len(f['rgb_file_sha256']) == 64 for f in a['checked_frames'])
    text = CONFIG.read_text().lower()
    assert not any(word in text for word in FORBIDDEN), 'annotation set must not reference GT or renderer data'


def test_schema_declares_the_scene_annotation_basis():
    text = SCHEMA.read_text()
    assert 'SCENE_ANNOTATION' in text and 'ANNOTATED' in text and 'annotation_set_sha256' in text


# ---- real recorded demo -----------------------------------------------------------------------------------

def a4(recorded_demo):
    api = recorded_demo.api
    return api, next(r for r in api.runs.values() if r.title.startswith('A4-1 '))


def search_car(api, run):
    from test_core_query_regressions import search_request  # synthetic request shape, real run
    from amidst.q1q5.core_query import execute_core_search
    from test_core_search_track_t import full_wall
    request = search_request(run, feature={'class_label': 'car', 'color_label': None}, time=full_wall(run))
    return execute_core_search(request, run, media_token_for_frame=lambda _: "SYNTHETIC_ANNOTATION_MEDIA")


def test_a4_search_for_car_returns_the_annotated_hit(recorded_demo):
    api, run = a4(recorded_demo)
    result = search_car(api, run)
    hits = [h for h in result['hits'] if h['camera_id'] == 'CAM_EXT_CAR']
    assert hits, 'CAM_EXT_CAR must be returned for car'
    basis = [b for h in hits for b in h['basis'] if b['kind'] == 'SCENE_ANNOTATION']
    assert basis and all(b['class_label'] == 'car' and b['evidence_state'] == 'ANNOTATED'
                         and b['annotation_id'] == 'A4-1:CAM_EXT_CAR:car:static' for b in basis)
    sha = hashlib.sha256(CONFIG.read_bytes()).hexdigest()
    assert all(b['annotation_set_sha256'] == sha for b in basis)
    assert not any(b['kind'] == 'OBJECT' and b.get('class_label') == 'car' for h in hits for b in h['basis']), \
        'the annotation must not be dressed up as a detection'


def test_bootstrap_exposes_scene_annotations_but_counts_stay_detection_only(recorded_demo):
    api, run = a4(recorded_demo)
    row = next(r for r in api.bootstrap()['runs'] if r['run_id'] == A4_RUN)
    assert row['scene_annotations'] == [{'annotation_id': 'A4-1:CAM_EXT_CAR:car:static', 'class_label': 'car',
                                         'camera_ids': ['CAM_EXT_CAR']}]
    expected = Counter(d['class_label'] for r in run.bindings.index.records for d in r['detections'] or [])
    assert {x['class_label']: x['detection_count'] for x in row['detected_class_counts']} == expected
    others = [r for r in api.bootstrap()['runs'] if r['run_id'] != A4_RUN]
    assert all(r.get('scene_annotations', []) == [] for r in others)


def test_tracking_never_reads_the_annotation(recorded_demo):
    # passes today and must keep passing after D149: tracking and identity ignore scene annotations
    api, run = a4(recorded_demo)
    from test_core_query_regressions import track_request
    from amidst.q1q5.core_query import execute_core_track
    result = execute_core_track(track_request(run, feature={'class_label': 'car', 'color_label': None}), run)
    assert 'SCENE_ANNOTATION' not in json.dumps(result)


def test_annotation_search_respects_time_location_and_colour(recorded_demo):
    from amidst.q1q5.core_query import execute_core_search
    from test_core_query_regressions import search_request
    api, run = a4(recorded_demo)
    def query(**changes):
        payload = search_request(run, feature={'class_label': 'car', 'color_label': None}, **changes)
        return execute_core_search(payload, run, media_token_for_frame=lambda _: 'SYNTHETIC_ANNOTATION_MEDIA')
    time = {'kind': 'WALL', 'timezone': 'Asia/Taipei',
            'wall_range': [run.bindings.clock.source_to_wall(1_000_001), run.bindings.clock.source_to_wall(2_000_000)]}
    [hit] = query(time=time)['hits']
    assert hit['source_range_us'] == [1_000_001, 2_000_000]
    assert hit['segments'][0]['representative']['frame_ref'].endswith(':6')
    assert hit['segments'][0]['representative']['observation_ids'] == []
    coloured = search_request(run, feature={'class_label': 'car', 'color_label': 'red'}, time=time)
    from amidst.q1q5.core_query import CoreRequestError
    with pytest.raises(CoreRequestError, match='UNSUPPORTED_CONDITION'):
        execute_core_search(coloured, run)
    for region in run.catalog['region_ids']:
        result = query(time=time, region_ids=[region])
        for h in result['hits']:
            assert {b['kind'] for b in h['basis']} == {'LOCATION', 'SCENE_ANNOTATION'}


def test_annotation_rgb_pin_tampering_fails_closed(recorded_demo, tmp_path):
    from amidst.q1q5.scene_annotations import bind_annotations
    _, run = a4(recorded_demo)
    doc = annotations()
    doc['annotations'][0]['checked_frames'][0]['rgb_file_sha256'] = '0' * 64
    path = tmp_path / 'annotations.json'
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='SCENE_ANNOTATION_RGB_PIN_MISMATCH'):
        bind_annotations(run, path)
