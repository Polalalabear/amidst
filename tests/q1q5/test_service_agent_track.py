"""F3 (#657): Agent mode on the 8785 main tracking screen (q_core_track -> associate). SYNTHETIC tracks and index, fake transport."""
import json

import pytest

from amidst.q1q5.core_query import CoreRequestError, validate_track_request
from amidst.q1q5.cross_camera_demo import Observation, Parameters, Track, response
from amidst.q1q5.service_agent_track import AUDIT_REASON, ServiceTrackDecider

EDGES = {('A', 'B'): 'AB'}
VERDICT = {'red': 'STRONG', 'blue': 'NONE'}


def track(camera, times, color='red'):
    return Track(camera, 'synthetic:' + camera, tuple(Observation(camera, t, f'{camera}:{t}', .7, frozenset([color])) for t in times))


def index(tracks):
    rows = {}
    for tr in tracks:
        color = next(iter(tr.observations[0].colors))
        for i, o in enumerate(tr.observations):
            row = rows.setdefault((tr.camera_id, o.timestamp_us), {'frame_state': 'INFERRED', 'camera_id': tr.camera_id,
                                                                  'timestamp_us': o.timestamp_us, 'frame_index': i, 'detections': []})
            row['detections'].append({'observation_id': o.observation_id, 'score': .7, 'bbox_xyxy_px': [10, 10, 40, 90],
                                      'class_label': 'person', 'color': {'verdicts': {'red': VERDICT[color]}}})
    return list(rows.values())


class Fake:
    def __init__(self, answer):
        self.answer, self.bodies = answer, []

    def __call__(self, body):
        self.bodies.append(body)
        a = self.answer(body) if callable(self.answer) else self.answer
        if isinstance(a, Exception):
            raise a
        return {'text': json.dumps(a), 'usage': {'input_tokens': 10, 'output_tokens': 5}, 'latency_s': 0.0}


SELECT_B = {'answer': 'SELECT', 'camera_id': 'B', 'detection_id': 'D1', 'confidence': 'medium', 'reason_codes': ['SAME'], 'reason': 'x'}
NOT_VISIBLE = {'answer': 'NOT_VISIBLE', 'reason_codes': ['GONE'], 'reason': 'x'}


def run(tracks, decider=None, now=1_600_000):
    return response(tracks, EDGES, as_of_us=now, parameters=Parameters(), clock_mapping_sha256='a' * 64, decider=decider)


def blue_case():
    return [track('A', [0, 200_000]), track('B', [800_000, 1_000_000], color='blue')]


def test_rule_mode_without_decider_is_unchanged_and_the_rule_rejects_the_blue_track():
    result, events, audit = run(blue_case())
    assert not events and audit[0]['reason'] == 'COLOR_NOT_COMPATIBLE'


def test_agent_select_of_a_colour_incompatible_track_is_adopted_with_audit():
    tracks = blue_case()
    fake = Fake(SELECT_B)
    result, events, audit = run(tracks, ServiceTrackDecider(fake, index(tracks)))
    assert len(fake.bodies) == 1
    assert len(events) == 1 and events[0]['reason'] == 'AGENT_ASSOCIATION_HYPOTHESIS' and events[0]['rule_override'] == 'COLOR_NOT_COMPATIBLE'
    row = next(a for a in audit if a['reason'] == AUDIT_REASON)
    assert row['decision_source'] == 'AGENT' and row['adopted_track_ref'] == 'synthetic:B' and row['identity_verdict'] == 'UNCONFIRMED'
    assert row['request_sha256'] and row['fallback_reason'] is None
    assert result['identity_verdict'] == 'UNCONFIRMED' and [s['camera_id'] for s in result['sightings'] if s['selected_for_single_view']][-1] == 'B'


def test_agent_wait_keeps_the_target_lost_even_where_the_rule_would_cut():
    tracks = [track('A', [0, 200_000]), track('B', [800_000, 1_000_000])]
    assert len(run(tracks)[1]) == 1                                         # the rule cuts to B (red, graph edge)
    fake = Fake(NOT_VISIBLE)
    result, events, audit = run(tracks, ServiceTrackDecider(fake, index(tracks)))
    assert not events and any(a.get('reason') == 'AGENT_WAITING' for a in audit)
    assert next(a for a in audit if a['reason'] == AUDIT_REASON)['answer']['answer'] == 'NOT_VISIBLE'


def test_failed_call_falls_back_to_the_rule_with_reason():
    tracks = [track('A', [0, 200_000]), track('B', [800_000, 1_000_000])]
    fake = Fake(RuntimeError('boom'))
    result, events, audit = run(tracks, ServiceTrackDecider(fake, index(tracks)))
    assert len(events) == 1 and events[0]['reason'] == 'DEMO_ASSOCIATION_HYPOTHESIS'      # rule decided
    row = next(a for a in audit if a['reason'] == AUDIT_REASON)
    assert row['decision_source'] != 'AGENT' and row['fallback_reason'] == 'PROVIDER_UNAVAILABLE'


def test_replaying_the_same_run_pays_no_extra_calls_and_gives_the_same_answer():
    tracks = blue_case()
    fake = Fake(SELECT_B)
    d = ServiceTrackDecider(fake, index(tracks))
    one = run(tracks, d)
    two = run(tracks, d)
    assert len(fake.bodies) == 1 and one[1] == two[1] and one[0]['single_view'] == two[0]['single_view']
    assert one[0]['sightings'] == two[0]['sightings']
    assert next(a for a in two[2] if a['reason'] == AUDIT_REASON)['cached'] is True


def test_round_limit_hands_back_to_the_rule():
    tracks = [track('A', [0, 200_000]), track('B', [800_000, 1_000_000])]
    fake = Fake(SELECT_B)
    result, events, audit = run(tracks, ServiceTrackDecider(fake, index(tracks), max_calls=0))
    assert fake.bodies == [] and len(events) == 1 and events[0]['reason'] == 'DEMO_ASSOCIATION_HYPOTHESIS'
    assert next(a for a in audit if a['reason'] == AUDIT_REASON)['fallback_reason'] == 'ROUND_LIMIT'


def test_request_lists_every_detection_with_the_colour_gate_and_no_gt():
    tracks = blue_case()
    fake = Fake(SELECT_B)
    run(tracks, ServiceTrackDecider(fake, index(tracks)))
    text = json.dumps(fake.bodies[0])
    assert 'B D1' in text and 'COLOUR_NO_MATCH' in text
    assert not any(w in text.lower() for w in ('ground_truth', 'gt_', 'depth', 'trajectory'))


def track_request(**change):
    q = {'schema_version': 'q-core.track-request.v1', 'session_ref': 'S', 'scene_id': 'X', 'run_id': 'R',
         'feature': {'class_label': 'person', 'color_label': 'red'}, 'region_ids': [], 'time': None, 'playback_now_us': 1}
    q.update(change)
    return q


CATALOG = dict(region_ids=[], class_labels=['person'], class_aliases={}, color_labels=['red'], clock_mapping=None)


@pytest.mark.parametrize('mode', ['RULE_ONLY', 'AGENT_SEQUENTIAL'])
def test_track_request_accepts_switch_mode(mode):
    try:
        validate_track_request(track_request(switch_mode=mode), **CATALOG)
    except CoreRequestError as e:
        assert e.code != 'FORBIDDEN_INFERENCE_INPUT'


def test_track_request_rejects_an_unknown_switch_mode():
    with pytest.raises(CoreRequestError) as exc:
        validate_track_request(track_request(switch_mode='AGENT_LIVE'), **CATALOG)
    assert exc.value.code == 'FORBIDDEN_INFERENCE_INPUT'


def run_manual(tracks, manual, decider=None, now=1_600_000):
    return response(tracks, EDGES, as_of_us=now, parameters=Parameters(), clock_mapping_sha256='a' * 64, decider=decider, manual=manual)


def test_manual_selection_switches_to_the_chosen_track_and_records_the_operator():
    tracks = [track('A', [0, 200_000, 400_000, 600_000]), track('C', [400_000, 600_000, 800_000], color='blue')]
    result, events, audit = run_manual(tracks, ('synthetic:C', 400_000))
    assert len(events) == 1 and events[0]['link_kind'] == 'MANUAL_TARGET_SELECTION' and events[0]['decided_by'] == 'USER'
    assert events[0]['identity_verdict'] == 'UNCONFIRMED' and events[0]['timestamp_us'] == 400_000
    assert [s['camera_id'] for s in result['single_view'] if s['kind'] == 'ON_CAMERA'] == ['A', 'C']


def test_manual_selection_as_the_first_seed_and_none_is_unchanged():
    tracks = [track('A', [0, 200_000]), track('C', [0, 200_000], color='blue')]
    assert run_manual(tracks, None) == run(tracks)
    result, events, audit = run_manual(tracks, ('synthetic:C', 0))
    assert not events and [s['camera_id'] for s in result['single_view'] if s['kind'] == 'ON_CAMERA'] == ['C']


@pytest.mark.parametrize('bad', [{'track_ref': 'x'}, {'track_ref': '', 'at_us': 0}, {'track_ref': 'x', 'at_us': -1},
                                 {'track_ref': 'x', 'at_us': 1.5}, {'track_ref': 'x', 'at_us': 0, 'gt': 1}, 'x'])
def test_track_request_rejects_malformed_manual_seed(bad):
    with pytest.raises(CoreRequestError):
        validate_track_request(track_request(manual_seed=bad), **CATALOG)
