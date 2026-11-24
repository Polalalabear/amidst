"""CX-H6: core tracks retain all local candidates and F3/M1 semantics."""
from copy import deepcopy
from dataclasses import replace

import pytest

from amidst.q1q5.core_query import execute_core_track, CoreRequestError
from amidst.q1q5.service_core_track import core_track
from amidst.q1q5.service_agent_track import ServiceTrackDecider
from test_core_query_regressions import bound_run, track_request
from test_q5_controller import seal_parameters
from test_service_agent_track import Fake


def engineering(run, status='DEMO_DEFAULT'):
    p = deepcopy(run.bindings.parameter_set)
    p['approval'] = {'status': status, 'approval_ref': None, 'approved_by': None}
    for item in p['parameters']:
        if item['name'].startswith('link_'):
            item['status'] = status
    seal_parameters(p)
    return replace(run, bindings=replace(run.bindings, parameter_set=p, parameter_sha256=p['content_sha256']))


def test_demo_default_is_server_opt_in_and_keeps_original_status_and_hash():
    run = engineering(bound_run())
    original = deepcopy(run.bindings.parameter_set)
    assert execute_core_track(track_request(run), run)['status'] == 'UNKNOWN'
    out = core_track(track_request(run), run, demo_default=True)
    assert out['status'] == 'TRACKING' and out['sightings']
    assert run.bindings.parameter_set == original
    assert out['provenance']['parameter_mode'] == 'DEMO_DEFAULT'
    assert out['provenance']['parameter_set_sha256'] == original['content_sha256']
    assert out['provenance']['formal_eligible'] is False


@pytest.mark.parametrize('status', ['UNKNOWN', 'REJECTED', 'PROPOSED'])
def test_engineering_opt_in_does_not_accept_other_statuses(status):
    run = engineering(bound_run(), status)
    assert core_track(track_request(run), run, demo_default=True)['status'] == 'UNKNOWN'


def test_manual_target_is_applied_and_unknown_target_is_rejected():
    run = bound_run()
    base = core_track(track_request(run), run)
    ref = base['sightings'][0]['track_ref']
    chosen = core_track(track_request(run, manual_seed={'track_ref': ref, 'at_us': 0}), run)
    assert chosen['manual_seed']['applied'] is True
    assert chosen['association_audit'][0]['reason'] == 'OPERATOR_SELECTION'
    with pytest.raises(CoreRequestError, match='MANUAL_SEED_UNKNOWN'):
        core_track(track_request(run, manual_seed={'track_ref': 'absent', 'at_us': 0}), run)


def test_same_camera_reacquisition_is_adopted_by_shared_agent_service():
    run = bound_run({'A': {0: 'STRONG', 1: None, 2: None, 3: 'STRONG'}}, frames=4)
    # The gap exceeds the linker's window, so the second box is a new local track.
    p = deepcopy(run.bindings.parameter_set)
    for item in p['parameters']:
        if item['name'] == 'link_max_gap_us':
            item['value'] = 200_000
        if item['name'] == 'link_max_gap_samples':
            item['value'] = 0
    seal_parameters(p)
    run = replace(run, bindings=replace(run.bindings, parameter_set=p, parameter_sha256=p['content_sha256']))
    fake = Fake({'answer': 'SELECT', 'camera_id': 'A', 'detection_id': 'D1', 'confidence': 'medium', 'reason_codes': ['SAME'], 'reason': 'x'})
    d = ServiceTrackDecider(fake, run.bindings.index.records)
    out = core_track(track_request(run, switch_mode='AGENT_SEQUENTIAL'), run, decider=d)
    assert out['agent']['adopted'] == 1 and out['agent']['agent_used'] is True
    assert any(a.get('adopted_track_ref') for a in out['association_audit'])
    core_track(track_request(run, switch_mode='AGENT_SEQUENTIAL'), run, decider=d)
    assert len(fake.bodies) == 1


@pytest.mark.parametrize('status', ['UNKNOWN', 'REJECTED', 'PROPOSED'])
def test_engineering_opt_in_still_refuses_unapproved_individual_rows(status):
    run = engineering(bound_run())
    p = deepcopy(run.bindings.parameter_set)
    next(v for v in p['parameters'] if v['name'] == 'link_min_score')['status'] = status
    seal_parameters(p)
    run = replace(run, bindings=replace(run.bindings, parameter_set=p, parameter_sha256=p['content_sha256']))
    assert core_track(track_request(run), run, demo_default=True)['status'] == 'UNKNOWN'


def test_demo_server_limits_core_adapter_to_registered_runs(monkeypatch):
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
    from serve_demo_integration import Demo, EIGHTCAM_RUN
    from amidst.q1q5 import service_core_track
    app = Demo.__new__(Demo)
    keys = [('scene', EIGHTCAM_RUN), ('synthetic', 'b05')]
    app.core_track_keys = set(keys)
    app.cross, app.positions = {}, {}
    app.api = SimpleNamespace(runs={k: object() for k in keys}, call=lambda *args: {'generic': True})
    app.authorize = lambda *args: None
    app.track_decider = lambda *args: (None, 'OFF')
    app.with_estimate = lambda key, doc: dict(doc, display_estimate={'schema_version': 'q-core.display-estimate.v1', 'est_xy': 'UNKNOWN'})
    monkeypatch.setattr(service_core_track, 'core_track', lambda *args, **kw: kw)
    for key in keys:
        out = app.call('q_core_track', {'session_ref': 'S', 'scene_id': key[0], 'run_id': key[1]})
        assert out['demo_default'] == (key[1] == EIGHTCAM_RUN)
    assert app.call('q_core_track', {'session_ref': 'S', 'scene_id': 'other', 'run_id': 'unregistered'}) == {'generic': True}


def test_manual_candidates_preserve_a_different_coloured_person_on_the_same_camera():
    from test_core_query_regressions import changed_records
    run = bound_run(frames=2)
    def extra(rows):
        for row in rows:
            other = deepcopy(row['detections'][0])
            other['bbox_xyxy_px'] = [500, 10, 540, 90]
            other['color']['verdicts'].update(red='NONE', blue='STRONG')
            row['detections'].append(other)
    run = changed_records(run, extra)
    base = core_track(track_request(run), run)
    refs = {s['track_ref'] for s in base['sightings']}
    assert len(refs) == 2
    # Both locals survive even if an ambiguous first seed prevents association.
    selected = {s['track_ref'] for s in base['sightings'] if s.get('selected_for_single_view')}
    ref = next(iter(refs - selected))
    out = core_track(track_request(run, manual_seed={'track_ref': ref, 'at_us': 0}), run)
    assert out['manual_seed']['applied'] is True
    assert len({s['track_ref'] for s in out['sightings']}) == 2


def test_blind_display_prediction_uses_selected_target_only(monkeypatch):
    from amidst.q1q5 import service_core_track as module
    run = bound_run({'A': {0: 'STRONG', 1: None, 2: None, 3: None}}, frames=4)
    calls = []
    def predict(run, sightings, stamp, positions):
        calls.append((sightings, positions))
        return {'status': 'UNAVAILABLE', 'reason': 'PREDICTION_UNAVAILABLE', 'estimate': None}
    monkeypatch.setattr(module, '_blind_for_track', predict)
    out = core_track(track_request(run), run, display_positions={'A': {'xy_m': [0, 1]}})
    assert out['single_view'][-1]['kind'] == 'LOST'
    assert calls and all(s.get('selected_for_single_view') for s in calls[-1][0])
    assert calls[-1][1] == {'A': {'xy_m': [0, 1]}}


def test_demo_fallback_rejects_manual_seed_without_silently_delegating():
    import sys
    from pathlib import Path
    from types import SimpleNamespace
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
    from serve_demo_integration import Demo
    app = Demo.__new__(Demo)
    app.core_track_keys, app.cross = set(), {}
    calls = []
    app.api = SimpleNamespace(call=lambda *args: calls.append(args) or {'generic': True})
    app.authorize = lambda *args: None
    payload = {'session_ref': 'S', 'scene_id': 'new-scene', 'run_id': 'new-run'}
    with pytest.raises(ValueError, match='MANUAL_SEED_UNSUPPORTED'):
        app.call('q_core_track', dict(payload, manual_seed={'track_ref': 'local:A', 'at_us': 0}))
    assert calls == []
    assert app.call('q_core_track', payload) == {'generic': True}
    assert calls == [('q_core_track', payload, app.authorize)]
