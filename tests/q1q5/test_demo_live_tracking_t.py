"""DEMO-UI-F-T: live Q2 tracking from the search dialog (Issue #372, D110). Test-first; Codex implements.

Symptom (P1 engineering bundle, source c26d7cd): live Q2 with an APPEARANCE seed returns
UNKNOWN/TRACKING_SCOPE_MISSING and with an OBSERVATION seed the front end rejects the session with
SESSION_BINDING; replaying a recorded response (?recording=) works.

Root cause found while writing these tests (to be confirmed by Codex):
  * SESSION_BINDING: `RuleController.session_id` (q5_controller.py) hashes a `tracking_scope` entry
    (the scope's tracking_scope_sha256, or null), but `bindResponse` in frontend/workbench-v2/q-api.mjs
    (the `kind==='q2'` branch) recomputes `sess-<hash16>` from request/index/region/camera/clock/
    parameters/media/selected_seed only, and `bootstrap().runs[]` carries no tracking_scope_sha256.
    Contract 5.1 (D81) requires a scope change to produce a new binding, so the backend entry stays;
    the front end needs the pin (see PR "Deviation proposal").
  * TRACKING_SCOPE_MISSING: the live registry has no tracking_scope_ref for the run. Either supply the
    scope (pinned, never derived from GT/script/render) or provide a fixed OBSERVATION seed.

Everything is SYNTHETIC and generated here. No P1 pack, GT, video or large media is read.
Default mode: missing implementation -> skip. AMIDST_REQUIRE_IMPL=1: missing implementation -> fail
with LIVE_TRACKING_IMPLEMENTATION_MISSING.
"""
import hashlib
import json
import os
import shutil
import subprocess
import time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from test_api import TOKEN, authorize, q2, run_binding
from test_graphs import fixture as graph_fixture
from test_graphs import scope_fixture
from test_graphs import seal as seal_graphs
from test_q5_controller import fixture as controller_fixture
from test_q5_controller import seed_id

from amidst.q1q5.api import QAPI, RecordingStore
from amidst.q1q5.graphs import GraphBundle, GraphError, load_graphs

ROOT = Path(__file__).resolve().parents[2]
QAPI_MJS = ROOT / 'frontend/workbench-v2/q-api.mjs'
CODE = 'LIVE_TRACKING_IMPLEMENTATION_MISSING'
APPEARANCE = {'kind': 'APPEARANCE', 'class_label': 'person', 'color': {'label': 'red', 'min_verdict': 'STRONG'}}
FORBIDDEN_RESPONSE_KEYS = {'ground_truth', 'actor_id', 'renderer_trajectory', 'visibility', 'depth', 'event_script', 'mask'}


def strict():
    return os.environ.get('AMIDST_REQUIRE_IMPL') == '1'


def missing(code=CODE):
    # Same convention as tests/q1q5/demo_ui_support_helpers.py (PR #380), inlined so this file has no
    # dependency on a branch that is not in codex/q1q5-staging yet.
    if strict():
        pytest.fail(code)
    pytest.skip(code)


# ---------------------------------------------------------------- SYNTHETIC fixture (two tracking cameras + one query-only)

def scoped_bindings(*, declare_scope=True, scope_bytes_indent=2):
    """Scoped bindings: tracking cameras A,B (graph) + query-only CAM_ENTRY. Scope bytes are NOT canonical
    JSON (indent) so the SHA-256 must be taken over the file bytes (contract 5.1)."""
    b = controller_fixture({'A': {0: 'STRONG', 1: 'STRONG'}, 'B': {5: 'STRONG'}, 'CAM_ENTRY': {0: 'STRONG'}},
                           cameras=('A', 'B', 'CAM_ENTRY'))
    r, c = graph_fixture()
    r['scene_id'] = c['scene_id'] = b.index.manifest['scene_id']
    for doc in (r, c):
        doc.update(approval_status='APPROVED', approval_ref='SYNTHETIC_TEST_ONLY')
    seal_graphs(r, c)
    scope, _ = scope_fixture(r, c)
    raw = json.dumps(scope, indent=scope_bytes_indent).encode() + b'\n'
    pin = hashlib.sha256(raw).hexdigest()
    for graph in (r, c):
        for item in graph['inputs']:
            if item['ref'].startswith('tracking-scope:'):
                item['sha256'] = pin
    seal_graphs(r, c)
    graphs = load_graphs(r, c, region_sha256=r['content_sha256'], camera_sha256=c['content_sha256'],
                         tracking_scope=scope, tracking_scope_sha256=pin, tracking_scope_bytes=raw)
    b = replace(b, graphs=graphs, region_graph_sha256=r['content_sha256'], camera_graph_sha256=c['content_sha256'],
                tracking_scope_required=True)
    if not declare_scope:
        b = replace(b, graphs=GraphBundle(r, c))  # pins declared in both graphs, scope document absent
    return b, pin, raw


def scoped_run(**kwargs):
    b, pin, raw = scoped_bindings(**kwargs)
    run = run_binding(b)
    catalog = deepcopy(run.catalog)
    catalog['camera_ids'] = ['A', 'B', 'CAM_ENTRY']
    return replace(run, catalog=catalog), pin, raw


def make_api(run, **kwargs):
    return QAPI([run], max_responses=128, max_media_refs=4096, **kwargs)


def request_for(run, seed):
    q = q2(run)
    q['seed'] = seed
    return q


def observation_seed(run, camera='A'):
    return {'kind': 'OBSERVATION', 'observation_id': seed_id(run.bindings, camera)}


def run_job(api, request, selected=None, timeout=20):
    """The route the front end uses: q2_start_session, then q2_poll_session until it leaves RUNNING."""
    job = api.call('q2_start_session', {'request': request, 'selected_observation_id': selected}, authorize)
    deadline = time.monotonic() + timeout
    while job['status'] == 'RUNNING' and time.monotonic() < deadline:
        time.sleep(0.02)
        job = api.call('q2_poll_session', {'session_ref': request['session_ref'], 'response_ref': job['session_id']}, authorize)
    assert job['status'] == 'COMPLETE', job
    return job


def keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from keys(v)


# ---------------------------------------------------------------- node harness (the real q-api.mjs, fed API output)

HARNESS = r'''
import {readFileSync} from 'node:fs';
const [,, qApiPath, inputPath] = process.argv;
const {createQApi, buildQ2} = await import(qApiPath);
const data = JSON.parse(readFileSync(inputPath, 'utf8'));
const out = [];
for (const c of data.cases) {
  const routes = c.routes;
  const fetchImpl = async (path, options) => {
    const text = routes[path];
    if (text === undefined) return {ok: false, status: 404, text: async () => '{"error_code":"HTTP_404"}'};
    return {ok: true, status: 200, text: async () => text};
  };
  const api = createQApi({fetchImpl});
  const result = {name: c.name};
  try {
    const boot = await api.bootstrap();
    if (!boot.ok) { result.stage = 'bootstrap'; result.ok = false; result.code = boot.error?.code; out.push(result); continue; }
    await api.createSession();
    const run = api.getBootstrap().runs[0];
    if (c.kind === 'live') {
      const request = buildQ2(run, api.getSession(), c.seed);
      const r = await api.query('q2', request, {selected_observation_id: c.selected});
      result.stage = 'query'; result.ok = r.ok; result.code = r.ok ? null : r.error?.code;
      if (r.ok) { result.status = r.data.status; result.kinds = r.data.timeline.map(s => s.kind); }
    } else {
      const r = await api.replay(c.recording_id);
      result.stage = 'replay'; result.ok = r.ok; result.code = r.ok ? null : r.error?.code;
      if (r.ok) { result.status = r.data.status; result.kinds = r.data.timeline.map(s => s.kind); }
    }
  } catch (e) { result.ok = false; result.code = 'EXC:' + e.message; }
  out.push(result);
}
process.stdout.write(JSON.stringify(out));
'''


def node_cases(tmp_path, cases):
    node = shutil.which('node')
    if node is None:
        missing('LIVE_TRACKING_NODE_MISSING')
    harness = tmp_path / 'harness.mjs'
    harness.write_text(HARNESS)
    payload = tmp_path / 'cases.json'
    payload.write_text(json.dumps({'cases': cases}))
    done = subprocess.run([node, str(harness), QAPI_MJS.as_uri(), str(payload)], capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr[-2000:]
    return {row['name']: row for row in json.loads(done.stdout)}


def assert_playable(result, label):
    """SESSION_BINDING is the known DEMO-UI-F gap (skip / strict fail); any other front-end error is a real failure."""
    if not result['ok'] and result['code'] == 'SESSION_BINDING':
        missing()
    assert result['ok'], f"{label}: front end rejected the response with {result['code']} at {result['stage']}"


def live_case(api, name, request, selected=None):
    """Routes exactly as q-api.mjs calls them for Q2: /api/q_bootstrap, /api/session, /api/q2_start_session."""
    job = run_job(api, request, selected)
    return {'name': name, 'kind': 'live', 'seed': request['seed'], 'selected': selected,
            'routes': {'/api/q_bootstrap': json.dumps(api.bootstrap()),
                       '/api/session': json.dumps({'session_ref': request['session_ref']}),
                       '/api/q2_start_session': json.dumps(job)}}


# ================================================================ 1. APPEARANCE seed opens a session with a valid scope

def test_appearance_seed_with_valid_scope_returns_candidates_and_opens_session():
    run, pin, raw = scoped_run()
    assert hashlib.sha256(raw).hexdigest() == pin and raw != json.dumps(json.loads(raw), sort_keys=True,
                                                                         separators=(',', ':')).encode() + b'\n'
    api = make_api(run)
    q = request_for(run, APPEARANCE)
    candidates = api.call('q2_seed_candidates', q, authorize)
    assert candidates['reason'] != 'TRACKING_SCOPE_MISSING' and candidates['reason'] is None
    assert candidates['status'] in {'CHOICE_REQUIRED', 'AVAILABLE'} and candidates['candidates']
    assert {c['camera_id'] for c in candidates['candidates']} <= {'A', 'B'}  # CAM_ENTRY is query-only
    chosen = candidates['candidates'][0]['observation_id']
    job = run_job(api, q, chosen)
    response = job['response']
    assert response['status'] != 'UNKNOWN' and response['reason'] != 'TRACKING_SCOPE_MISSING'
    assert response['status'] == 'COMPLETE' and response['timeline']
    assert response['resolved_scope']['tracking_scope_sha256'] == pin
    assert response['resolved_scope']['camera_ids'] == ['A', 'B']
    assert job['session_id'] == response['session_id'] and response['identity_verdict'] == 'UNCONFIRMED'


def test_changing_the_scope_changes_the_session_binding():
    """Contract 5.1: replacing the scope must yield a new binding (guards the fix: do not drop the scope from session_id)."""
    run_a, pin_a, _ = scoped_run(scope_bytes_indent=2)
    run_b, pin_b, _ = scoped_run(scope_bytes_indent=4)
    assert pin_a != pin_b
    ids = []
    for run in (run_a, run_b):
        api = make_api(run)
        ids.append(run_job(api, request_for(run, observation_seed(run)))['session_id'])
    assert ids[0] != ids[1]


def test_live_bootstrap_lets_the_front_end_see_the_scope_pin():
    """Needed so q-api.mjs can recompute session_id. If Codex instead removes the scope from the front-end
    preimage by a contract-approved deviation, update this test with that deviation (see PR text)."""
    run, pin, _ = scoped_run()
    row = make_api(run).bootstrap()['runs'][0]
    if 'tracking_scope_sha256' not in row:
        missing()
    assert row['tracking_scope_sha256'] == pin
    legacy = make_api(run_binding(controller_fixture())).bootstrap()['runs'][0]
    assert legacy['tracking_scope_sha256'] is None  # unused scope is an explicit null, not an absent key


# ================================================================ 2. OBSERVATION seed: request as q-api.mjs builds it

def test_observation_seed_as_built_by_q_api_is_accepted_by_backend_and_front_end(tmp_path):
    """Request shape = buildQ2() in q-api.mjs (lines 36-39): schema_version, session_ref, scene_id, run_ids,
    time {kind SOURCE, run_id, range_us [0, source_duration_us]}, seed, switch_mode RULE_ONLY, parameter_set_id.
    The seed has no selected_observation_id (app.mjs line 39 default; q1-wall-model.mjs line 19 builds it)."""
    run, pin, _ = scoped_run()
    api = make_api(run)
    q = request_for(run, observation_seed(run))
    assert set(q) == {'schema_version', 'session_ref', 'scene_id', 'run_ids', 'time', 'seed', 'switch_mode', 'parameter_set_id'}
    assert q['time'] == {'kind': 'SOURCE', 'run_id': run.bindings.clock.run_id, 'range_us': [0, run.bindings.clock.duration_us]}
    response = run_job(api, q)['response']
    assert response['status'] == 'COMPLETE' and response['resolved_scope']['tracking_scope_sha256'] == pin
    result = node_cases(tmp_path, [live_case(api, 'observation_selected_null', q, None)])['observation_selected_null']
    assert_playable(result, 'live OBSERVATION session')
    assert result['status'] == 'COMPLETE'


def test_appearance_seed_session_passes_front_end_binding(tmp_path):
    run, _, _ = scoped_run()
    api = make_api(run)
    q = request_for(run, APPEARANCE)
    chosen = api.call('q2_seed_candidates', q, authorize)['candidates'][0]['observation_id']
    result = node_cases(tmp_path, [live_case(api, 'appearance_selected', q, chosen)])['appearance_selected']
    assert_playable(result, 'live APPEARANCE session')
    assert result['status'] == 'COMPLETE'


def test_front_end_binding_also_holds_for_an_unscoped_run(tmp_path):
    """A run with no tracking scope at all (legacy fixture, tracking_scope_required False) still binds."""
    run = run_binding(controller_fixture())
    api = make_api(run)
    q = request_for(run, observation_seed(run))
    result = node_cases(tmp_path, [live_case(api, 'unscoped', q, None)])['unscoped']
    assert_playable(result, 'unscoped live session')


# ================================================================ 3. fail closed (should already PASS; protects the guards)

def test_declared_scope_missing_stays_unknown_tracking_scope_missing():
    run, _, _ = scoped_run(declare_scope=False)
    api = make_api(run)
    q = request_for(run, APPEARANCE)
    response = api.call('q2_session', q, authorize)
    assert response['status'] == 'UNKNOWN' and response['reason'] == 'TRACKING_SCOPE_MISSING'
    assert response['timeline'] == [] and response['resolved_scope']['tracking_scope_sha256'] is None
    job = run_job(api, request_for(run, observation_seed(run)))
    assert job['response']['status'] == 'UNKNOWN' and job['response']['reason'] == 'TRACKING_SCOPE_MISSING'
    assert job['response']['timeline'] == []


def test_required_scope_absent_from_both_graphs_is_not_treated_as_all_cameras_trackable():
    b = controller_fixture()
    run = run_binding(replace(b, tracking_scope_required=True))
    response = make_api(run).call('q2_session', request_for(run, APPEARANCE), authorize)
    assert response['status'] == 'UNKNOWN' and response['reason'] == 'TRACKING_SCOPE_MISSING' and response['timeline'] == []


def finish_job(api, request, selected=None, timeout=20):
    """Submit through q2_start_session and wait for the worker; returns the public job (never asserts COMPLETE)."""
    job = api.call('q2_start_session', {'request': request, 'selected_observation_id': selected}, authorize)
    deadline = time.monotonic() + timeout
    while job['status'] == 'RUNNING' and time.monotonic() < deadline:
        time.sleep(0.02)
        job = api.call('q2_poll_session', {'session_ref': request['session_ref'], 'response_ref': job['session_id']}, authorize)
    return job


def test_scope_hash_mismatch_is_a_data_integrity_failure_not_unknown():
    run, pin, raw = scoped_run()
    graphs = run.bindings.graphs
    for tampered in (GraphBundle(graphs.region, graphs.camera, graphs.tracking_scope, '0' * 64, raw),
                     GraphBundle(graphs.region, graphs.camera, graphs.tracking_scope, pin, raw + b' ')):
        api = make_api(replace(run, bindings=replace(run.bindings, graphs=tampered)))
        q = request_for(run, observation_seed(run))
        with pytest.raises(Exception) as caught:
            api.call('q2_session', deepcopy(q), authorize)
        assert getattr(caught.value, 'code', None) != 'TRACKING_SCOPE_MISSING' and not api.responses
        job = finish_job(make_api(replace(run, bindings=replace(run.bindings, graphs=tampered))), q)
        assert job['status'] == 'FAILED' and job['response'] is None  # never COMPLETE, never an UNKNOWN answer


def test_scope_cross_reference_contradiction_is_a_data_integrity_failure():
    run, pin, raw = scoped_run()
    scope = deepcopy(run.bindings.graphs.tracking_scope)
    scope['tracking_camera_ids'] = scope['tracking_camera_ids'] + ['NOT_A_REGISTERED_CAMERA']
    scope['query_camera_ids'] = sorted(scope['query_camera_ids'] + ['NOT_A_REGISTERED_CAMERA'])
    contradictory = json.dumps(scope, indent=2).encode() + b'\n'
    new_pin = hashlib.sha256(contradictory).hexdigest()  # hashes agree; the cross reference does not
    r, c = deepcopy(run.bindings.graphs.region), deepcopy(run.bindings.graphs.camera)
    for graph in (r, c):
        for item in graph['inputs']:
            if item['ref'].startswith('tracking-scope:'):
                item['sha256'] = new_pin
    seal_graphs(r, c)
    with pytest.raises(GraphError) as caught:
        load_graphs(r, c, region_sha256=r['content_sha256'], camera_sha256=c['content_sha256'], tracking_scope=scope,
                    tracking_scope_sha256=new_pin, tracking_scope_bytes=contradictory)
    assert caught.value.code != 'TRACKING_SCOPE_MISSING'


def test_query_only_seed_camera_is_seed_camera_not_tracked():
    run, _, _ = scoped_run()
    api = make_api(run)
    seed = observation_seed(run, 'CAM_ENTRY')
    job = run_job(api, request_for(run, seed))
    response = job['response']
    assert response['status'] == 'UNKNOWN' and response['reason'] == 'SEED_CAMERA_NOT_TRACKED' and response['timeline'] == []


# ================================================================ 4. live and recorded responses share one front-end path

def segment_shape(response):
    return [(s['kind'], tuple(sorted(s))) for s in response['timeline']]


def test_live_and_recorded_responses_are_structurally_identical_and_playable(tmp_path):
    run, pin, _ = scoped_run()
    store = RecordingStore(tmp_path, repo_root=ROOT, max_bytes=4000000)
    api = make_api(run, recording_store=store)
    q = request_for(run, observation_seed(run))
    live = run_job(api, q)['response']
    pinned = api.call('q_record_response', {'session_ref': TOKEN, 'response_ref': live['session_id']}, authorize)
    descriptor = {k: pinned[k] for k in ('recording_id', 'file', 'file_sha256')}
    replay_api = make_api(run, recording_store=store, recordings=[descriptor])
    recorded = replay_api.call('q_recorded_response', {'session_ref': TOKEN, 'recording_id': pinned['recording_id']}, authorize)
    # Same keys, status, segment kinds and per-segment field sets (GAP / TEMP_LOST markers included); timing ignored.
    assert set(recorded) == set(live) and recorded['status'] == live['status'] == 'COMPLETE'
    assert recorded['schema_version'] == live['schema_version']
    assert segment_shape(recorded) == segment_shape(live) and 'GAP' in {s['kind'] for s in live['timeline']}
    assert [(s['kind'], s.get('reasons'), s.get('camera_shown')) for s in recorded['timeline']] == \
           [(s['kind'], s.get('reasons'), s.get('camera_shown')) for s in live['timeline']]
    assert set(recorded['resolved_scope']) == set(live['resolved_scope'])
    assert recorded['resolved_scope']['tracking_scope_sha256'] == live['resolved_scope']['tracking_scope_sha256'] == pin
    # Both flow through the same q-api.mjs validation (validateQResponse + source bindings).
    cases = [live_case(api, 'live', q, None)]
    cases.append({'name': 'recorded', 'kind': 'replay', 'recording_id': pinned['recording_id'],
                  'routes': {'/api/q_bootstrap': json.dumps(replay_api.bootstrap() | {'runs': api.bootstrap()['runs']}),
                             '/api/session': json.dumps({'session_ref': TOKEN}),
                             '/api/q_recorded_response': json.dumps(recorded)}})
    results = node_cases(tmp_path, cases)
    assert_playable(results['recorded'], 'recorded replay')
    assert_playable(results['live'], 'live session')
    assert results['live']['status'] == results['recorded']['status']
    assert results['live']['kinds'] == results['recorded']['kinds']


# ================================================================ 5. GT isolation

GT_KEYS = [('top', 'ground_truth'), ('top', 'visibility'), ('top', 'depth'), ('seed', 'renderer_trajectory'),
           ('seed', 'visibility'), ('time', 'depth'), ('top', 'gt_actor_position')]


def poisoned(run, where, key):
    q = request_for(run, observation_seed(run))
    (q if where == 'top' else q[where])[key] = {'x': 1}
    return q


@pytest.mark.parametrize('where,key', GT_KEYS)
def test_synchronous_q2_routes_reject_gt_visibility_or_depth_input(where, key):
    run, _, _ = scoped_run()
    for action in ('q2_seed_candidates', 'q2_session'):
        api = make_api(run)
        with pytest.raises(Exception) as caught:
            api.call(action, poisoned(run, where, key), authorize)
        assert getattr(caught.value, 'code', None) == 'FORBIDDEN_INFERENCE_INPUT', (action, repr(caught.value))
        assert not api.responses


@pytest.mark.parametrize('where,key', GT_KEYS)
def test_live_start_session_never_completes_on_gt_visibility_or_depth_input(where, key):
    """Weak guard (passes today): the worker fails and nothing is stored."""
    run, _, _ = scoped_run()
    api = make_api(run)
    try:
        job = finish_job(api, poisoned(run, where, key))
    except Exception as exc:  # rejected at submission is also fine
        assert getattr(exc, 'code', None) == 'FORBIDDEN_INFERENCE_INPUT'
        return
    assert job['status'] == 'FAILED' and job['response'] is None and not api.responses


@pytest.mark.parametrize('where,key', GT_KEYS)
def test_live_start_session_rejects_gt_visibility_or_depth_input_at_submission(where, key):
    """Required: q2_start_session (the route q-api.mjs uses) answers FORBIDDEN_INFERENCE_INPUT synchronously, like
    q2_session does, instead of starting a worker that fails later (today 'visibility' / 'gt_*' keys are accepted
    into a RUNNING job)."""
    run, _, _ = scoped_run()
    api = make_api(run)
    try:
        job = api.call('q2_start_session', {'request': poisoned(run, where, key), 'selected_observation_id': None}, authorize)
    except Exception as exc:
        assert getattr(exc, 'code', None) == 'FORBIDDEN_INFERENCE_INPUT', repr(exc)
        return
    deadline = time.monotonic() + 20
    while job['status'] == 'RUNNING' and time.monotonic() < deadline:  # let the worker end before the test returns
        time.sleep(0.02)
        job = api.call('q2_poll_session', {'session_ref': TOKEN, 'response_ref': job['session_id']}, authorize)
    missing()


def test_gt_keys_are_absent_from_the_synthetic_fixture_and_responses():
    run, _, raw = scoped_run()
    api = make_api(run)
    q = request_for(run, observation_seed(run))
    response = run_job(api, q)['response']
    surfaces = {'request': q, 'bootstrap': api.bootstrap(), 'scope': json.loads(raw),
                'region_graph': run.bindings.graphs.region, 'camera_graph': run.bindings.graphs.camera, 'response': response}
    for name, document in surfaces.items():
        bad = FORBIDDEN_RESPONSE_KEYS & set(keys(document))
        assert not bad, (name, bad)
    assert response['provenance']['gt_read'] is False and api.bootstrap()['gt_read'] is False
