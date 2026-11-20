import json

import pytest

from amidst.q1q5 import agent_service as ag
from amidst.q1q5 import scene_context as sx

from amidst.evaluation.live_coverage_gap import make_camera


def catalog():
    def cam(cid, x):
        c = make_camera(cid, (x, 0.0, 3.0), 90.0, 30.0, 600.0, 600.0)
        c2w = [[c.rot[r][k] for k in range(3)] + [c.pos[r]] for r in range(3)] + [[0, 0, 0, 1]]
        return {'camera_id': cid, 'camera_to_world': c2w, 'fx': 600.0, 'fy': 600.0, 'width': 960, 'height': 540, 'calibration_sha256': 'c' * 64}
    return {'cameras': [cam('CAM_A', 0.0), cam('CAM_B', 2.0)]}


REGION = {'regions': [{'region_id': 'R1', 'kind': 'OUTDOOR', 'floor_id': 'F'}], 'approval_status': 'DRAFT',
          'edges': [{'edge_id': 'E1', 'regions': ['R1', 'R1'], 'state': 'UNKNOWN', 'traversability': 'TOPOLOGICAL_ONLY', 'via': None}]}
CAMG = {'approval_status': 'DRAFT', 'cameras': [{'camera_id': 'CAM_A', 'covered_regions': [], 'entry_zones': [], 'exit_zones': []}],
        'transitions': [{'transition_id': 'T1', 'from_camera_id': 'CAM_A', 'to_camera_id': 'CAM_B'}]}
SCOPE = {'directed_pairs': [{'from_camera_id': 'CAM_B', 'to_camera_id': 'CAM_A', 'disposition': 'EXCLUDED', 'reason': 'X'}]}


def scene():
    return sx.build(REGION, CAMG, catalog(), None, {'a.json': '0' * 64}, SCOPE)


def inp(**kw):
    cands = [ag.Candidate('D1', 'CAM_A', (10, 10, 50, 120), 0.9, 'person', ('red',)),
             ag.Candidate('D2', 'CAM_A', (60, 10, 90, 120), 0.35, 'sports ball', ())]
    base = dict(scene_context=scene(), t_s=3.0, candidates=cands, seed_colors=('red',), reference_jpeg=b'ref',
                frames=[('CAM_A', b'frame')], rule_display={'kind': 'LOST', 'camera_id': 'CAM_A', 'last_t_s': 1.0}, last_camera='CAM_A')
    base.update(kw)
    return ag.DecisionInput(**base)


def test_scene_context_stable_and_clean():
    a, b = scene(), scene()
    assert sx.serialize(a) == sx.serialize(b) and sx.sha256_of(a) == sx.sha256_of(b)
    assert {c['camera_id'] for c in a['cameras']} == {'CAM_A', 'CAM_B'}
    assert a['cameras'][0]['ground_footprint_area_m2'] > 0 and a['overlaps']
    assert any('CAMERAS_NOT_IN_GRAPH:CAM_B' in x for x in a['incomplete'])
    assert a['excluded_camera_pairs'] == [{'from': 'CAM_B', 'to': 'CAM_A', 'reason': 'X'}]
    sx.assert_no_forbidden(a)


def test_forbidden_keys_rejected():
    for key in ('visibility', 'gt_private', 'depth_map', 'foot_position_world_m'):
        with pytest.raises(ValueError):
            sx.assert_no_forbidden({'cameras': [{key: 1}]})


def test_three_layers_prefix_identical_variable_last():
    b1 = ag.build_body('m', inp(t_s=3.0))
    b2 = ag.build_body('m', inp(t_s=9.0, candidates=[]))
    assert b1['input'][0] == b2['input'][0] and b1['input'][1] == b2['input'][1]
    assert b1['input'][2] != b2['input'][2]
    assert b1['prompt_cache_key'] == sx.sha256_of(scene())[:32]
    assert 'CAM_A' in b1['input'][0]['content'][0]['text'] and 'position_xyz_m' not in json.dumps(b1['input'][2])
    assert 'as_of' not in b1['input'][0]['content'][0]['text']


def test_cache_none_and_state_and_no_scene():
    assert ag.build_body('m', inp(), cache='none')['prompt_cache_options'] == {'mode': 'explicit'}
    s = ag.build_body('m', inp(), cache='state', previous_response_id='resp_1')
    assert len(s['input']) == 1 and s['previous_response_id'] == 'resp_1' and s['store'] is True
    no = ag.build_body('m', inp(include_scene=False))
    assert 'SCENE_CONTEXT=' not in no['input'][0]['content'][0]['text']


def test_gate_is_information_and_all_detections_listed():
    text = ag.variable_text(inp())
    assert 'sports ball' in text and 'rule_eligible=false' in text and 'CLASS_NOT_PERSON:sports ball' in text


def test_select_ineligible_is_override_not_error():
    ans, err = ag.parse_answer(json.dumps({'answer': 'SELECT', 'camera_id': 'CAM_A', 'detection_id': 'D2', 'reason_codes': ['a'] * 9}), inp())
    assert err is None and ans['rule_override'] and ans['reason_codes'][0].startswith('RULE_OVERRIDE:') and len(ans['reason_codes']) == 4


def test_c6_reason_codes_truncated_not_rejected():
    ans, err = ag.parse_answer(json.dumps({'answer': 'NOT_VISIBLE', 'reason_codes': list('abcdefgh')}), inp())
    assert err is None and ans['reason_codes'] == list('abcd')


def test_answer_types():
    i = inp()
    nv, _ = ag.parse_answer(json.dumps({'answer': 'NOT_VISIBLE', 'next_camera_hint': 'CAM_B'}), i)
    assert nv['next_camera_hint'] == 'CAM_B'
    nv2, _ = ag.parse_answer(json.dumps({'answer': 'NOT_VISIBLE', 'next_camera_hint': 'CAM_ZZ'}), i)
    assert nv2['next_camera_hint'] is None
    assert ag.parse_answer(json.dumps({'answer': 'STILL_HERE_OCCLUDED', 'camera_id': 'CAM_A'}), i)[1] is None
    assert ag.parse_answer(json.dumps({'answer': 'OWN_BOX', 'camera_id': 'CAM_A', 'box_xyxy': [1, 1, 50, 100]}), i)[0]['box_xyxy']
    assert ag.parse_answer(json.dumps({'answer': 'OWN_BOX', 'camera_id': 'CAM_A', 'box_xyxy': [50, 1, 1, 100]}), i)[1] == 'BAD_OWN_BOX'
    assert ag.parse_answer(json.dumps({'answer': 'SELECT', 'camera_id': 'CAM_A', 'detection_id': 'D9'}), i)[1] == 'UNKNOWN_DETECTION'
    assert ag.parse_answer('nope', i)[1] == 'NOT_JSON'


def test_rule_mode_never_calls_transport():
    calls = []
    rule = {'camera_id': 'CAM_A', 'detection_id': 'D1'}
    rec = ag.decide(inp(rule_answer=rule), mode='RULE', transport=lambda b: calls.append(b))
    assert not calls and rec.decision_source == 'RULE' and rec.answer == rule and not rec.agent_attempted


def test_agent_mode_uses_model_and_falls_back():
    good = lambda b: {'text': json.dumps({'answer': 'NOT_VISIBLE'}), 'usage': {'input_tokens': 5, 'cached_tokens': 0}, 'latency_s': 1.0}  # noqa: E731
    rec = ag.decide(inp(rule_answer={'x': 1}), mode='AGENT', transport=good)
    assert rec.decision_source == 'AGENT' and rec.agent_used and rec.answer['answer'] == 'NOT_VISIBLE'
    bad = ag.decide(inp(rule_answer={'x': 1}), mode='AGENT', transport=lambda b: {'text': 'x'})
    assert bad.fallback_used and bad.answer == {'x': 1} and bad.fallback_reason.startswith('INVALID_RESPONSE')

    def boom(b):
        raise RuntimeError('guard denied')
    assert ag.decide(inp(), mode='AGENT', transport=boom).fallback_reason == 'TRANSPORT:RuntimeError'
    with pytest.raises(ValueError):
        ag.decide(inp(), mode='X')


def test_parse_response_usage():
    r = ag.parse_response({'id': 'r', 'status': 'completed', 'output': [{'content': [{'type': 'output_text', 'text': '{}'}]}],
                           'usage': {'input_tokens': 3000, 'output_tokens': 50, 'input_tokens_details': {'cached_tokens': 2048, 'cache_write_tokens': 0}}})
    assert r['usage'] == {'input_tokens': 3000, 'cached_tokens': 2048, 'cache_write_tokens': 0, 'output_tokens': 50} and r['text'] == '{}'
