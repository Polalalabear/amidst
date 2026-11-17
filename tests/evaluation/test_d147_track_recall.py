"""D147 evaluation module: strategies see only index records; scoring uses the human reference."""
import json
from pathlib import Path

import pytest

from amidst.evaluation.track_recall import (
    box_continuation_frames, load_reference, person_frames, score_frames, score_single_view)

ROOT = Path(__file__).resolve().parents[2]
REFERENCE = ROOT / 'configs/evaluation/d147_human_reference_v1.json'


def det(label, score, box, red=False):
    d = {'class_label': label, 'score': score, 'bbox_xyxy_px': box, 'observation_id': f'{label}:{box}'}
    if red:
        d['color'] = {'verdicts': {'red': 'STRONG'}}
    return d


def row(t, *detections, camera='C'):
    return {'camera_id': camera, 'timestamp_us': t, 'detections': list(detections)}


def test_reference_file_is_evaluation_only_and_well_formed():
    ref = load_reference(REFERENCE)
    assert ref['use'] == 'EVALUATION_ONLY'
    ids = [i['id'] for r in ref['runs'] for i in r['intervals']]
    assert ids == ['A4-W1-early', 'A4-W1-late', 'B4-WIDE', 'B4-BRANCH', 'B4-R101']
    assert all(r['unknown'] for r in ref['runs'])   # open items stay written down


def test_reference_is_not_read_by_inference_roots():
    for root in ['src/amidst/q1q5', 'frontend/workbench-v2']:
        for path in (ROOT / root).rglob('*'):
            if path.suffix in {'.py', '.mjs'}:
                text = path.read_text(encoding='utf-8')
                assert 'd147_human_reference' not in text and 'track_recall' not in text, path


def test_reference_rejects_bad_schema(tmp_path):
    bad = json.loads(REFERENCE.read_text())
    bad['use'] = 'INFERENCE'
    (tmp_path / 'r.json').write_text(json.dumps(bad))
    with pytest.raises(ValueError, match='REFERENCE_SCHEMA_INVALID'):
        load_reference(tmp_path / 'r.json')
    bad['use'] = 'EVALUATION_ONLY'
    bad['runs'][0]['intervals'][0]['range_us'] = [5, 5]
    (tmp_path / 'r.json').write_text(json.dumps(bad))
    with pytest.raises(ValueError, match='REFERENCE_INTERVAL_INVALID'):
        load_reference(tmp_path / 'r.json')


def test_person_threshold_strategy():
    records = [row(0, det('person', .45, [0, 0, 10, 30])), row(1, det('person', .35, [0, 0, 10, 30])),
               row(2, det('traffic light', .9, [0, 0, 10, 30]))]
    assert person_frames(records, 'C', .4) == {0}
    assert person_frames(records, 'C', .3) == {0, 1}


def test_continuation_follows_a_misclassified_moving_box_and_drops_full_frame_boxes():
    records = [row(0, det('person', .5, [0, 100, 40, 220], red=True)),
               row(1, det('traffic light', .5, [6, 100, 46, 220]), det('umbrella', .9, [0, 0, 960, 540])),
               row(2, det('parking meter', .4, [12, 102, 52, 222])),
               row(3),                                                   # one empty frame: kept
               row(4, det('toothbrush', .35, [20, 104, 60, 224])),
               row(5, det('person', .2, [26, 104, 66, 224]))]           # below continue score
    covered, continued = box_continuation_frames(records, 'C')
    assert covered == {0, 1, 2, 4} and continued == {1, 2, 4}


def test_continuation_needs_a_coloured_person_seed_and_ends_after_misses():
    no_colour = [row(0, det('person', .9, [0, 0, 10, 30])), row(1, det('clock', .9, [0, 0, 10, 30]))]
    assert box_continuation_frames(no_colour, 'C')[0] == set()
    assert box_continuation_frames(no_colour, 'C', require_seed_color=False)[0] == {0, 1}
    gap = [row(0, det('person', .9, [0, 0, 10, 30], red=True)), row(1), row(2), row(3),
           row(4, det('clock', .9, [0, 0, 10, 30]))]
    assert box_continuation_frames(gap, 'C')[0] == {0}


def test_part_box_does_not_collapse_the_track():
    # a head-sized box between two body boxes must not shrink the reference box
    records = [row(0, det('person', .6, [100, 100, 140, 260], red=True)),
               row(1, det('sports ball', .5, [108, 100, 132, 124]), det('traffic light', .45, [102, 102, 142, 262])),
               row(2, det('toothbrush', .4, [106, 104, 146, 264]))]
    covered, _ = box_continuation_frames(records, 'C')
    assert covered == {0, 1, 2}


def test_scoring_against_reference_and_single_view():
    run = {'intervals': [{'id': 'X', 'camera_id': 'C', 'range_us': [0, 1_000_000]}]}
    records = [row(t) for t in range(0, 1_200_000, 200_000)]
    assert score_frames(records, run, {'C': {0, 200_000, 1_000_000}})[0] | {} == {
        'id': 'X', 'camera_id': 'C', 'range_us': [0, 1_000_000], 'reference_frames': 5, 'covered_frames': 2, 'recall': 0.4}
    single = [{'kind': 'ON_CAMERA', 'camera_id': 'C', 'range_us': [200_000, 600_000]},
              {'kind': 'GAP', 'camera_id': None, 'range_us': [600_000, 800_000]},
              {'kind': 'ON_CAMERA', 'camera_id': 'D', 'range_us': [800_000, 1_000_000]}]
    assert score_single_view(records, run, single)[0]['covered_frames'] == 2


def test_d150_overlapping_cameras_score_independently_and_time_union_counts_once():
    from amidst.evaluation.track_recall import score_sightings, score_single_view_switching
    reference = {'intervals': [{'id': 'A', 'camera_id': 'A', 'range_us': [0, 4_000_000]},
                               {'id': 'B', 'camera_id': 'B', 'range_us': [2_000_000, 6_000_000]}]}
    records = [row(t*1_000_000, camera=c) for c in ['A', 'B'] for t in range(6)]
    sightings = [{'camera_id': 'A', 'range_us': [0, 2_000_000]},
                 {'camera_id': 'B', 'range_us': [2_000_000, 6_000_000]}]
    assert [s['recall'] for s in score_sightings(records, reference, sightings)] == [.5, 1.]
    single = [{'kind': 'ON_CAMERA', 'camera_id': 'A', 'range_us': [0, 1_000_000]},
              {'kind': 'ON_CAMERA', 'camera_id': 'WRONG', 'range_us': [1_000_000, 3_000_000]},
              {'kind': 'ON_CAMERA', 'camera_id': 'B', 'range_us': [3_000_000, 5_000_000]}]
    assert score_single_view_switching(reference, single) == {
        'reference_union_us': 6_000_000, 'covered_us': 3_000_000, 'ratio': .5}
    assert score_single_view_switching({'intervals': []}, [])['ratio'] is None


def test_actual_track_evaluation_rejects_wrong_run_index_and_tampered_output(tmp_path):
    import hashlib
    import runpy
    loader = runpy.run_path(str(ROOT/'scripts/eval_d147_recall.py'))['load_track_response']
    response = {'schema_version': 'q-core.track-response.v1',
                'resolved_scope': {'run_id': 'SYNTHETIC_RUN', 'detection_index_sha256': 'a'*64},
                'sightings': [], 'single_view': []}
    raw = json.dumps(response, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    response['output_sha256'] = hashlib.sha256(raw).hexdigest()
    path = tmp_path/'track.json';path.write_text(json.dumps(response))
    assert loader(path, run_id='SYNTHETIC_RUN', index_sha256='a'*64) == response
    with pytest.raises(ValueError, match='TRACK_SCOPE_MISMATCH'):
        loader(path, run_id='ANOTHER_RUN', index_sha256='a'*64)
    with pytest.raises(ValueError, match='TRACK_SCOPE_MISMATCH'):
        loader(path, run_id='SYNTHETIC_RUN', index_sha256='b'*64)
    response['sightings'] = [{'camera_id': 'SYNTHETIC_TAMPER'}];path.write_text(json.dumps(response))
    with pytest.raises(ValueError, match='TRACK_OUTPUT_SHA256_MISMATCH'):
        loader(path, run_id='SYNTHETIC_RUN', index_sha256='a'*64)
