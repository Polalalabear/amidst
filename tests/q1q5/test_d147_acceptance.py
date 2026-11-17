"""D147 acceptance gate for the tracking backend (written by Claude, implemented by Codex).

* D147-1 (user decision, #93 comment 6730595312): after LOST or an ambiguity, rescan every camera
  for the rest of the queried window and adopt the first candidate that passes the existing score
  and colour gates (marked as a reacquisition, identity UNCONFIRMED). An ambiguity is still reported
  but does not end tracking. Same-camera gaps of at most 0.6 s are merged into one ON_CAMERA span.
* Full function (user: acceptance is still full function): every interval of the human reference
  ``configs/evaluation/d147_human_reference_v1.json`` reaches recall >= 0.75 in the real track
  response. The offline prototype (``scripts/eval_d147_recall.py``) reaches 0.78-0.97 on the current
  index without new inference, using a person seed >= 0.3 plus class-agnostic box continuation.

The human reference is read here only to score; it must never be read by ``src/amidst/q1q5``.
"""
from pathlib import Path

import pytest

from amidst.evaluation.track_recall import load_reference, score_sightings, score_single_view_switching
from amidst.q1q5.cross_camera_demo import Observation, Parameters, Track, response
from test_bootstrap_class_counts import recorded_demo  # noqa: F401

REFERENCE = Path(__file__).resolve().parents[2] / 'configs/evaluation/d147_human_reference_v1.json'
MERGE_GAP_US = 600_000


def candidate(camera, times, ref, color='red', score=.7):
    return Track(camera, ref, tuple(Observation(camera, t, f'{ref}:{t}', score,
                 frozenset([color]) if color else frozenset()) for t in times))


def replay(tracks, now):
    return response(tracks, {}, as_of_us=now, parameters=Parameters(), clock_mapping_sha256='a' * 64)


def on_camera(result, camera):
    return [s for s in result['single_view'] if s['kind'] == 'ON_CAMERA' and s['camera_id'] == camera]


# ---- D147-1, synthetic (runs everywhere) ------------------------------------------------------------------

def test_same_camera_candidate_after_the_window_is_reacquired_not_dropped():
    result, events, audit = replay([candidate('A', [0], 'first'), candidate('A', [7_000_000], 'later')], now=8_000_000)
    assert [s['track_ref'] for s in result['sightings']] == ['first', 'later']
    assert result['sightings'][1]['link_kind'].endswith('REACQUISITION')
    assert on_camera(result, 'A')[-1]['range_us'][0] == 7_000_000
    assert result['identity_verdict'] == 'UNCONFIRMED' and all(a['identity_verdict'] == 'UNCONFIRMED' for a in audit)


def test_other_camera_candidate_after_lost_is_reacquired_without_a_graph_edge():
    result, _, _ = replay([candidate('A', [0], 'first'), candidate('B', [9_000_000, 9_200_000], 'b')], now=10_000_000)
    assert on_camera(result, 'B') and on_camera(result, 'B')[0]['range_us'][0] == 9_000_000
    assert result['sightings'][-1]['link_kind'].endswith('REACQUISITION')
    assert result['identity_verdict'] == 'UNCONFIRMED' and result['physical_navigation'] == 'UNKNOWN'


def test_rescan_keeps_the_existing_colour_and_score_gates():
    # passes today and must keep passing: a non-red candidate is never adopted, whatever the gap
    result, events, audit = replay([candidate('A', [0], 'first'), candidate('A', [7_000_000], 'blue', 'blue')], now=8_000_000)
    assert not events and len(result['sightings']) == 1
    with pytest.raises(ValueError, match='LOCAL_TRACK_INVALID'):
        replay([candidate('A', [0], 'first'), candidate('B', [7_000_000], 'low', score=.29)], now=8_000_000)


def test_ambiguity_is_reported_but_tracking_continues():
    tracks = [candidate('A', [0], 'first'), candidate('B', [1_000_000], 'b'), candidate('C', [1_000_000], 'c'),
              candidate('D', [3_000_000, 3_200_000], 'd')]
    result, _, audit = replay(tracks, now=4_000_000)
    assert any('AMBIGUOUS' in str(a.get('reason', '')) for a in audit) or any('AMBIGUOUS' in r for r in result['reasons'])
    assert on_camera(result, 'D'), 'tracking must continue after the ambiguity'


def test_short_same_camera_gaps_are_merged_and_longer_ones_kept():
    merged, _, _ = replay([candidate('A', [0, 200_000, 400_000], 'a1'), candidate('A', [800_000, 1_000_000], 'a2')], now=2_000_000)
    spans = on_camera(merged, 'A')
    assert len(spans) == 1 and spans[0]['range_us'] == [0, 1_200_000]          # 0.2 s gap merged
    kept, _, _ = replay([candidate('A', [0, 200_000, 400_000], 'a1'), candidate('A', [1_400_000], 'a2')], now=2_000_000)
    assert len(on_camera(kept, 'A')) == 2                                       # 0.8 s gap stays a GAP


# ---- real recorded runs (need AMIDST_DEMO_HOME) -----------------------------------------------------------

def track(demo, label):
    run = next(r for r in demo.api.runs.values() if r.title.startswith(label + ' '))
    token = demo.call('session', {'role': 'demo'})['session_ref']
    result = demo.call('q_core_track', {
        'schema_version': 'q-core.track-request.v1', 'session_ref': token,
        'scene_id': run.catalog['scene_id'], 'run_id': run.catalog['run_id'],
        'feature': {'class_label': 'person', 'color_label': None}, 'region_ids': [], 'time': None,
        'playback_now_us': run.bindings.clock.duration_us})
    assert result['identity_verdict'] == 'UNCONFIRMED' and result['provenance']['gt_read'] is False
    return run, result


def overlap(spans, lo, hi):
    return sum(max(0, min(b, hi) - max(a, lo)) for a, b in (s['range_us'] for s in spans))


def test_real_b4_wide_and_w2_are_adopted(recorded_demo):
    _, result = track(recorded_demo, 'B4-1')
    assert overlap(on_camera(result, 'CAM_WIDE'), 14_000_000, 20_000_000) >= 0.8 * 6_000_000
    assert overlap(on_camera(result, 'CAM_W2'), 26_800_000, 30_000_000) >= 0.8 * 3_200_000


def test_real_a4_continues_after_the_ambiguity_and_does_not_flicker(recorded_demo):
    _, result = track(recorded_demo, 'A4-1')
    assert overlap(on_camera(result, 'CAM_EXT_CLEAR'), 28_800_000, 36_800_000) >= 0.8 * 8_000_000
    gaps = [s for s in result['single_view'] if s['kind'] == 'GAP']
    for i, s in enumerate(result['single_view']):
        if (s['kind'] == 'GAP' and i > 0 and i + 1 < len(result['single_view'])
                and result['single_view'][i-1]['camera_id'] == result['single_view'][i+1]['camera_id']):
            assert s['range_us'][1] - s['range_us'][0] > MERGE_GAP_US


@pytest.mark.parametrize('label', ['A4-1', 'B4-1'])
def test_real_full_function_recall_against_the_human_reference(recorded_demo, label):
    reference = next(r for r in load_reference(REFERENCE)['runs'] if r['label'] == label)
    run, result = track(recorded_demo, label)
    scores = score_sightings(run.bindings.index.records, reference, result['sightings'])
    low = [(s['id'], s['recall']) for s in scores if s['recall'] is None or s['recall'] < 0.75]
    assert not low, f'reference intervals below recall 0.75: {low}'


@pytest.mark.parametrize('label', ['A4-1', 'B4-1'])
def test_real_single_view_switching_covers_reference_time_union(recorded_demo, label):
    reference = next(r for r in load_reference(REFERENCE)['runs'] if r['label'] == label)
    _, result = track(recorded_demo, label)
    score = score_single_view_switching(reference, result['single_view'])
    assert score['ratio'] is not None and score['ratio'] >= .75, score
