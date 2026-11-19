"""CL-B16 (#620): the 8785 recorded Q2 session on A4-1/B4-1/B-05. SYNTHETIC inputs + repo configs only; fake model, no network."""
import json
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest
from test_api import authorize, q2, run_binding
from test_openai_gateway import select, wire
from test_q5_controller import seed_id

from amidst.q1q5 import openai_gateway as og
from amidst.q1q5.api import APIError, QAPI
from amidst.q1q5.graphs import load_graphs
from amidst.q1q5.scene_graphs import load_scene_graphs

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import serve_demo_integration as demo  # noqa: E402

BINDING = {'demo': 'cl-b16'}


def projected():
    return demo.scene_projection(load_scene_graphs('r004'), 'SYNTH_SCENE', BINDING)


def test_scene_projection_keeps_the_verified_tracking_scope():
    """Root cause: the projection returned GraphBundle(r, c) without the scope, but the graphs still pin it -> every Q2 session on
    A4-1/B4-1 (rule and Agent) was UNKNOWN / TRACKING_SCOPE_MISSING."""
    g = projected()
    assert g.tracking_scope is not None and g.tracking_scope_sha256 == og_scope_sha()
    assert any(x['ref'].startswith('tracking-scope:') for x in g.camera['inputs'])
    # the controller re-loads graphs from the bundle's own pieces: that must now succeed
    again = load_graphs(g.region, g.camera, region_sha256=g.region['content_sha256'], camera_sha256=g.camera['content_sha256'],
                        tracking_scope=g.tracking_scope, tracking_scope_sha256=g.tracking_scope_sha256,
                        tracking_scope_bytes=g.tracking_scope_bytes)
    assert again.tracking_scope == g.tracking_scope


def og_scope_sha():
    from amidst.q1q5.scene_graphs import R004_PINS
    return R004_PINS['tracking_scope_v3_1.json']


def demo_set(run):
    """The shape of the job parameters: DEMO_DEFAULT rows and a string exit_rule."""
    b = run.bindings
    ps = deepcopy(b.parameter_set)
    for row in ps['parameters']:
        if row['name'] in {'switch_min_presence', 'exit_rule', 'query_min_score'}:
            row['status'] = 'DEMO_DEFAULT'
    for row in ps['parameters']:
        if row['name'] == 'exit_rule':
            row['value'] = 'BBOX_BOTTOM_MIDPOINT_IN_ROI'
    ps['parameters'].append({'name': 'exit_boundary_inclusive', 'value': True, 'unit': None, 'status': 'DEMO_DEFAULT', 'proposed_by': 'x', 'proposal_ref': 'x'})
    ps['approval'] = {'status': 'DEMO_DEFAULT', 'approval_ref': None, 'approved_by': None}
    return demo.seal(ps, 'pset:q-demo')


def test_demo_approved_is_scoped_and_leaves_inputs_alone():
    run = run_binding(agent=True)
    src = demo_set(run)
    before = deepcopy(src)
    out = demo.demo_approved(src)
    assert src == before                                  # input untouched
    assert out['approval']['status'] == 'APPROVED' and '2026-11-19' in out['approval']['approval_ref']
    assert all(r['status'] == 'APPROVED' for r in out['parameters'] if r['name'] in {'switch_min_presence', 'query_min_score', 'exit_rule'})
    assert next(r for r in out['parameters'] if r['name'] == 'exit_rule')['value'] == {'method': 'BBOX_BOTTOM_MIDPOINT', 'boundary_inclusive': True}
    assert out['parameter_set_id'] == 'pset:q-demo:' + out['content_sha256'][:16] != src['parameter_set_id']
    formal = json.loads((ROOT / 'configs/q1q5/parameter_set_v1.json').read_text())
    assert formal['approval']['status'] == 'PROPOSED'     # the pinned file is not promoted
    llm_seed = [r for r in out['parameters'] if r['name'] == 'llm_seed']
    assert all(r['status'] == next(s['status'] for s in src['parameters'] if s['name'] == 'llm_seed') for r in llm_seed)
    assert all(r['status'] == 'APPROVED' for r in out['parameters'] if r['name'] in demo.DEMO_APPROVED_ROWS and r['value'] is not None)
    assert not any(r['status'] == 'APPROVED' for r in out['parameters'] if r['name'] not in demo.DEMO_APPROVED_ROWS and r['name'] in {p['name'] for p in src['parameters'] if p['status'] == 'DEMO_DEFAULT'})


def test_demo_approved_missing_boundary_row_gives_explicit_error():
    run = run_binding(agent=True)
    src = demo_set(run)
    src['parameters'] = [r for r in src['parameters'] if r['name'] != 'exit_boundary_inclusive']
    with pytest.raises(Exception) as e:
        demo.demo_approved(src)
    assert 'DEMO_EXIT_BOUNDARY_MISSING' in str(e.value)


def test_unapproved_set_through_scene_projection_path_stays_not_approved(tmp_path):
    # the eightcam path: same scope-bearing projection, but no demo_approved -> Q2 must still refuse
    _, _, provider = wire(tmp_path)
    run = run_binding(agent=True)
    ps = demo_set(run)
    b = replace(run.bindings, parameter_set=ps, parameter_sha256=ps['content_sha256'])
    settings = replace(run.parse_settings, parameter_set_id=ps['parameter_set_id'], parameter_set_sha256=ps['content_sha256'])
    run = og.bind_openai_agent([replace(run, bindings=b, parse_settings=settings)], provider.queue_dir, provider=provider)[0]
    api = QAPI([run], max_responses=128, max_media_refs=4096)
    q = q2(run)
    q['switch_mode'] = 'RULE_ONLY'
    r = api.call('q2_select_seed', {'request': q, 'selected_observation_id': seed_id(run.bindings)}, authorize)
    assert r['reason'] == 'PARAMETERS_NOT_APPROVED'


def approved_agent_run(provider):
    run = run_binding(agent=True)
    ps = demo.demo_approved(demo_set(run))
    b = replace(run.bindings, parameter_set=ps, parameter_sha256=ps['content_sha256'])
    settings = replace(run.parse_settings, parameter_set_id=ps['parameter_set_id'], parameter_set_sha256=ps['content_sha256'])
    return og.bind_openai_agent([replace(run, bindings=b, parse_settings=settings)], provider.queue_dir, provider=provider)[0]


@pytest.mark.parametrize('mode', ['RULE_ONLY', 'AGENT_SEQUENTIAL'])
def test_a4_b4_style_run_completes_in_both_modes_with_mock_gateway(tmp_path, mode):
    _, _, provider = wire(tmp_path)
    run = approved_agent_run(provider)
    api = QAPI([run], max_responses=128, max_media_refs=4096)
    q = q2(run)
    q['switch_mode'] = mode
    r = api.call('q2_select_seed', {'request': q, 'selected_observation_id': seed_id(run.bindings)}, authorize)
    assert r['status'] not in {'UNKNOWN'} and r['reason'] not in {'TRACKING_SCOPE_MISSING', 'PARAMETERS_NOT_APPROVED'}
    if mode == 'RULE_ONLY':
        assert r['agent_attempted'] is False
    else:
        assert r['agent_attempted'] is True


def test_b05_shows_not_applicable_instead_of_an_error_code(tmp_path):
    _, _, provider = wire(tmp_path)
    run = replace(run_binding(agent=True), agent_factory=og.NotApplicableAgent())
    api = QAPI([run], max_responses=8, max_media_refs=8)
    row = api.bootstrap()['runs'][0]
    assert row['agent_available'] is False and row['agent_unavailable_reason'] == 'NOT_APPLICABLE_NO_DECIDER'
    q = q2(run)
    q['switch_mode'] = 'AGENT_SEQUENTIAL'
    with pytest.raises(APIError) as caught:
        api.call('q2_select_seed', {'request': q, 'selected_observation_id': seed_id(run.bindings)}, authorize)
    assert caught.value.code == 'AGENT_ADAPTER_NOT_CONFIGURED'
