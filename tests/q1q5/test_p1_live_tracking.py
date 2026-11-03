"""DEMO-UI-F P1 checks; immutable LOCAL bundle is explicitly opted in."""
import hashlib
import os
from pathlib import Path

import pytest
from test_demo_live_tracking_t import live_case, node_cases, run_job

from amidst.q1q5.p1_workbench import P1, live_tracking_run

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / 'configs/q1q5/p1_live_tracking_scope.json'
MANIFEST = '6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7'


@pytest.fixture(scope='module')
def p1(tmp_path_factory):
    path = os.environ.get('AMIDST_P1_BUNDLE')
    if not path:
        pytest.skip('LOCAL P1 bundle not explicitly selected: AMIDST_P1_BUNDLE')
    state = tmp_path_factory.mktemp('p1-live') / 'state'
    return P1(Path(path).resolve(), MANIFEST, state,
              tracking_scope=SCOPE, tracking_scope_pin=hashlib.sha256(SCOPE.read_bytes()).hexdigest(),
              ui_root=ROOT / 'frontend/workbench-v2')


def query(app, seed):
    row = app.bootstrap()['runs'][0]
    token = app.call('session', {'role': 'demo'})['session_ref']
    return {'schema_version': 'q-demo.q2-request.v1', 'session_ref': token,
            'scene_id': row['scene_id'], 'run_ids': [row['run_id']],
            'time': {'kind': 'SOURCE', 'run_id': row['run_id'],
                     'range_us': [0, row['clock_mapping']['source_duration_us']]},
            'seed': seed, 'switch_mode': 'RULE_ONLY', 'parameter_set_id': row['parameter_set_id']}


@pytest.mark.parametrize('kind', ['APPEARANCE', 'OBSERVATION'])
def test_p1_seed_opens_live_session_in_backend_and_real_frontend(p1, tmp_path, kind):
    request = query(p1, {'kind': 'APPEARANCE', 'class_label': 'person', 'color': {'label': 'red', 'min_verdict': 'STRONG'}})
    choices = p1.call('q2_seed_candidates', request)
    assert choices['candidates'] and choices['reason'] is None
    chosen = choices['candidates'][0]['observation_id']
    selected = chosen
    if kind == 'OBSERVATION':
        request['seed'] = {'kind': 'OBSERVATION', 'observation_id': chosen}
        selected = None

    # The shared -T harness expects an API-shaped call including authorization.
    class API:
        def call(self, action, payload, authorize=None):
            return p1.call(action, payload)
        def bootstrap(self):
            return p1.bootstrap()

    api = API()
    response = run_job(api, request, selected)['response']
    assert response['reason'] != 'TRACKING_SCOPE_MISSING'
    assert response['status'] in {'COMPLETE', 'PARTIAL', 'ENDED_BY_LIMIT'}
    assert any(s['kind'] == 'ON_CAMERA' for s in response['timeline'])
    assert response['resolved_scope']['tracking_scope_sha256'] == hashlib.sha256(SCOPE.read_bytes()).hexdigest()
    result = node_cases(tmp_path, [live_case(api, kind, request, selected)])[kind]
    assert result['ok'], result
    assert not p1.api.recordings  # historic graph-bound recordings are not re-bound to the overlay


def test_p1_scope_is_opt_in_pinned_and_never_approved(p1, tmp_path):
    run = next(iter(p1.api.runs.values()))
    assert run.bindings.graphs.approval_status == 'DRAFT'
    assert run.bindings.graphs.tracking_scope['G4_approved'] is False
    raw = SCOPE.read_bytes()
    with pytest.raises(ValueError):
        live_tracking_run(run, SCOPE, '0' * 64)
    with pytest.raises(ValueError, match='P1_SCOPE_ALREADY_DECLARED'):
        live_tracking_run(run, SCOPE, hashlib.sha256(raw).hexdigest())


def test_d112_unapproved_scope_excludes_b_even_when_b_has_observations(p1):
    request = query(p1, {'kind': 'APPEARANCE', 'class_label': 'person',
                         'color': {'label': 'red', 'min_verdict': 'STRONG'}})
    choices = p1.call('q2_seed_candidates', request)['candidates']
    assert any(c['camera_id'] == 'B' for c in choices)
    chosen = next(c for c in choices if c['camera_id'] == 'A')
    response = p1.call('q2_select_seed', {'request': request,
                                        'selected_observation_id': chosen['observation_id']})
    bundle = p1.api.responses[(request['session_ref'], response['session_id'])]
    assert bundle['snapshots']
    assert all(s['candidates'] == [] and
               {'transition_id': 'T_A_B', 'reason': 'GRAPH_NOT_APPROVED'} in s['excluded_transitions']
               for s in bundle['snapshots'])
    assert {s['camera_id'] for s in response['timeline'] if s['kind'] == 'ON_CAMERA'} == {'A'}
    assert p1.api.runs[next(iter(p1.api.runs))].bindings.graphs.tracking_scope['G4_approved'] is False
