"""D144/D145: causal local candidates and explicitly unconfirmed reacquisition."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from amidst.q1q5.cross_camera_demo import Observation, Parameters, Track, response
from amidst.q1q5.demo_local_tracks import local_candidates
from test_bootstrap_class_counts import recorded_demo  # noqa: F401
from test_d124_demo_default import synthetic_tracking_input


def candidate(camera, times, ref, color='red', score=.7):
    return Track(camera, ref, tuple(Observation(camera, t, f'{ref}:{t}', score,
                 frozenset([color]) if color else frozenset()) for t in times))


def replay(tracks, edges=None, now=2_000_000, params=None):
    return response(tracks, edges or {}, as_of_us=now, parameters=params or Parameters(),
                    clock_mapping_sha256='a'*64)


def test_same_camera_reappearance_requires_new_ref_and_is_marked_in_response():
    result, events, audit = replay([candidate('A', [0], 'first'), candidate('A', [800_000], 'new')])
    assert [s['kind'] for s in result['single_view']] == ['ON_CAMERA', 'GAP', 'ON_CAMERA', 'LOST']
    assert [s['track_ref'] for s in result['sightings']] == ['first', 'new']
    assert result['sightings'][1]['link_kind'] == 'SAME_CAMERA_REACQUISITION'
    assert events[0]['transition_id'] is None
    assert events[0]['from_track_ref'] == 'first' and events[0]['to_track_ref'] == 'new'
    assert 'SAME_CAMERA_REACQUISITION' in result['reasons']
    assert result['identity_verdict'] == audit[0]['identity_verdict'] == 'UNCONFIRMED'
    assert result['physical_navigation'] == 'UNKNOWN'
    assert result['association_audit'] == audit


@pytest.mark.parametrize('color,gap,reason', [
    ('blue', 600_000, 'COLOR_NOT_COMPATIBLE'),
    (None, 600_000, 'COLOR_NOT_COMPATIBLE'),
    ('red', 6_000_001, 'HANDOFF_WINDOW_EXCEEDED'),
])
def test_same_camera_reappearance_preserves_existing_color_and_time_gates(color, gap, reason):
    result, events, audit = replay([candidate('A', [0], 'first'),
                                   candidate('A', [200_000 + gap], 'new', color)], now=8_000_000)
    assert not events and len(result['sightings']) == 1
    assert audit[0]['reason'] == reason


def test_same_camera_gap_boundary_inclusive_and_adjacent_new_refs_not_merged():
    for seed in [200_000, 6_200_000]:
        result, events, _ = replay([candidate('A', [0], 'first'), candidate('A', [seed], 'new')], now=7_000_000)
        assert len(events) == 1 and len(result['sightings']) == 2
        assert result['sightings'][1]['track_ref'] == 'new'


def test_same_camera_low_score_or_reused_segment_is_not_a_new_identity():
    with pytest.raises(ValueError, match='LOCAL_TRACK_INVALID'):
        replay([candidate('A', [0], 'first'), candidate('A', [800_000], 'new', score=.39)])
    _, events, audit = replay([candidate('A', [0], 'same'), candidate('A', [800_000], 'same')])
    assert not events and audit[0]['reason'] == 'SAME_LOCAL_SEGMENT'


def test_cross_camera_still_requires_direct_edge_and_ambiguous_handoffs_stay_unknown():
    _, events, audit = replay([candidate('A', [0], 'first'), candidate('B', [800_000], 'other')])
    assert not events and audit[0]['reason'] == 'NO_DIRECT_TRANSITION'
    result, events, audit = replay([candidate('A', [0], 'first'), candidate('A', [800_000], 'new'),
                                   candidate('B', [800_000], 'other')], {('A', 'B'): 'AB'})
    assert not events and len(result['sightings']) == 1
    assert all(a['reason'] == 'AMBIGUOUS_HANDOFF' for a in audit)


def test_reappearance_never_uses_future_observations():
    tracks = [candidate('A', [0], 'first'), candidate('A', [800_000, 1_000_000], 'new')]
    assert replay(tracks, now=800_000) == replay(tracks[:1], now=800_000)
    assert len(replay(tracks, now=800_001)[1]) == 1


def synthetic_rows():
    cfg, manifest, original = synthetic_tracking_input()
    meta = manifest['sampling']['per_camera'][0]
    meta.update(index_interval_us=200_000, stride_samples=1, index_grid_origin_frame=0)
    rows = []
    for frame in range(8):
        row = deepcopy(original[0])
        row.update(frame_index=frame, timestamp_us=frame * 200_000,
                   frame_ref=f'SYNTHETIC_FRAME_{frame}', detections=[])
        if frame in {0, 1, 5, 6}:
            det = deepcopy(original[0]['detections'][0])
            det['observation_id'] = f'obs:0123456789abcdef:SYN_CAM:{frame}:0'
            row['detections'] = [det]
        rows.append(row)
    return cfg, manifest, rows


def test_all_local_segments_replayed_after_searching_with_frozen_parameters():
    cfg, manifest, rows = synthetic_rows()
    before = deepcopy((cfg, manifest, rows))
    tracks, audit = local_candidates(manifest, rows, cfg, 'a'*64)
    assert [tuple(o.timestamp_us for o in t.observations) for t in tracks] == [(0, 200_000), (1_000_000, 1_200_000)]
    assert tracks[0].track_ref != tracks[1].track_ref
    assert any(a.get('state') == 'SEARCHING' for a in audit)
    assert (cfg, manifest, rows) == before


def test_local_unmatched_iou_observation_starts_new_candidate_not_discarded():
    cfg, manifest, rows = synthetic_rows()
    rows[1]['detections'][0]['bbox_xyxy_px'] = [500, 0, 520, 40]
    tracks, _ = local_candidates(manifest, rows[:2], cfg, 'a'*64)
    assert len(tracks) == 2 and all(len(t.observations) == 1 for t in tracks)


def test_local_score_and_ambiguous_seed_gates_do_not_fabricate_tracks():
    cfg, manifest, rows = synthetic_rows()
    rows[0]['detections'][0]['score'] = .39
    second = deepcopy(rows[1]['detections'][0])
    second['observation_id'] = 'obs:0123456789abcdef:SYN_CAM:1:1'
    rows[1]['detections'].append(second)
    tracks, audit = local_candidates(manifest, rows[:2], cfg, 'a'*64)
    assert not tracks and audit[0]['reason'] == 'AMBIGUOUS_SEED'


@pytest.mark.parametrize('label,expected_count', [('A4-1', 13), ('B4-1', 12)])
def test_recorded_loader_replays_all_candidates_and_keeps_original_pins(recorded_demo, label, expected_count):
    demo = recorded_demo
    run = next(r for r in demo.api.runs.values() if r.title.startswith(label + ' '))
    key = run.catalog['scene_id'], run.catalog['run_id']
    tracks = demo.cross[key]
    assert len(tracks) == expected_count
    token = demo.call('session', {'role': 'demo'})['session_ref']
    result = demo.call('q_core_track', {
        'schema_version': 'q-core.track-request.v1', 'session_ref': token,
        'scene_id': key[0], 'run_id': key[1], 'feature': {'class_label': 'person', 'color_label': None},
        'region_ids': [], 'time': None, 'playback_now_us': run.bindings.clock.duration_us})
    assert result['resolved_scope']['detection_index_sha256'] == run.bindings.index_sha256
    assert result['identity_verdict'] == 'UNCONFIRMED'
    assert result['provenance']['gt_read'] is False and result['provenance']['formal_eligible'] is False
    if label == 'A4-1':
        assert 'SAME_CAMERA_REACQUISITION' in result['reasons']
        assert any(s['link_kind'] == 'SAME_CAMERA_REACQUISITION' and s['range_us'][0] == 14_800_000
                   for s in result['sightings'])
        assert result['single_view'][-1]['range_us'] == [22_800_000, 50_000_000]
    else:
        assert result['single_view'][-1]['range_us'] == [5_200_000, 42_000_000]
    evidence = json.loads((Path(__file__).parent/'fixtures/d139-index-diagnostics.engineering.json').read_text())
    expected = next(r for r in evidence['runs'] if r['label'] == label)
    assert expected['index_content_sha256'] == run.bindings.index_sha256
    assert result['single_view'] == expected['after_single_view']
    for camera in expected['cameras']:
        local = [t for t in tracks if t.camera_id == camera['camera_id']]
        assert len(local) == camera['new_candidate_segments']
        assert sum(len(t.observations) for t in local) == camera['new_candidate_observations']
        for window in camera['time_bins']:
            people = [d for row in run.bindings.index.records
                      if row['camera_id'] == camera['camera_id']
                      and window['range_us'][0] <= row['timestamp_us'] < window['range_us'][1]
                      for d in row['detections'] or [] if d['class_label'] == 'person']
            assert len(people) == window['raw_person_detections']
            assert sum(d['score'] >= .4 for d in people) == window['score_at_least_0_4']
    assert result['single_view'][-1]['kind'] == 'LOST'
    if label == 'A4-1':
        assert sum(a['reason'] == 'AMBIGUOUS_HANDOFF' for a in result['association_audit']) == 2
    else:
        assert any(a['to_camera_id'] == 'CAM_WIDE' and a['gap_us'] == 8_800_000
                   and a['reason'] == 'HANDOFF_WINDOW_EXCEEDED' for a in result['association_audit'])
