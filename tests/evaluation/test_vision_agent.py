"""Focused tests for the vision-agent replay engine (no network, no GT files)."""
import json

from amidst.evaluation import vision_agent as va

T = va.TICK
BOX = (100, 100, 160, 260)


def _view(kinds, cams=None):
    ticks = [i * T for i in range(len(kinds))]
    kind = dict(zip(ticks, kinds))
    camera = {t: ('CAM_A' if k == 'ON_CAMERA' else None) for t, k in kind.items()}
    boxes = {t: [BOX] if k == 'ON_CAMERA' else [] for t, k in kind.items()}
    lock = next((t for t in ticks if kind[t] == 'ON_CAMERA'), None)
    return va.RuleView(ticks, kind, camera, boxes, lock)


def _index(n, cam='CAM_B', shift=2):
    return {(cam, i * T): [va.Det('D1', f'o{i}', (200 + shift * i, 100, 260 + shift * i, 260), 0.6, ('red',))] for i in range(n)}


def _answer(cam='CAM_B', did='D1', lat=0.0):
    return {'present': True, 'camera_id': cam, 'detection_id': did, 'box_xyxy': None, 'latency_s': lat}


def test_trigger_only_after_first_lock():
    v = _view(['GAP', 'ON_CAMERA', 'GAP', 'GAP', 'ON_CAMERA'])
    assert va.trigger_ticks(v) == [2 * T, 3 * T]
    assert va.last_known(v, 3 * T)[:2] == ('CAM_A', 1 * T)
    assert va.last_known(v, 0) is None


def test_offline_answer_follows_chain_until_rule_reconnects():
    v = _view(['ON_CAMERA', 'GAP', 'GAP', 'GAP', 'ON_CAMERA'])
    d, calls = va.replay(v, _index(5), lambda t: _answer(), 'offline')
    assert sorted(d) == [1 * T, 2 * T, 3 * T]
    assert all(x['kind'] == 'SNAP' and x['cam'] == 'CAM_B' for x in d.values())
    assert len(calls) == 1


def test_chain_break_triggers_new_call():
    idx = _index(6)
    del idx[('CAM_B', 3 * T)]
    v = _view(['ON_CAMERA', 'GAP', 'GAP', 'GAP', 'GAP', 'ON_CAMERA'])
    d, calls = va.replay(v, idx, lambda t: _answer() if t != 3 * T else None, 'offline')
    assert 3 * T not in d and 4 * T in d              # chain broke at tick 3 (no detection); the next call re-acquires at tick 4
    assert [c['call_t'] for c in calls] == [1 * T, 3 * T, 4 * T]


def test_realtime_delays_and_blocks_calls():
    v = _view(['ON_CAMERA'] + ['GAP'] * 6 + ['ON_CAMERA'])
    d, calls = va.replay(v, _index(8), lambda t: _answer(lat=0.5), 'realtime')
    assert [c['call_t'] for c in calls] == [1 * T]    # arrives at tick 4 (0.5 s -> 3 ticks); chain alive; no second call
    assert min(d) == 4 * T and calls[0]['effective_t'] == 4 * T


def test_realtime_expired_when_chain_breaks_in_flight():
    idx = _index(8)
    del idx[('CAM_B', 3 * T)]
    v = _view(['ON_CAMERA'] + ['GAP'] * 6 + ['ON_CAMERA'])
    d, calls = va.replay(v, idx, lambda t: _answer(lat=0.6), 'realtime')
    assert calls[0].get('expired') is True and 4 * T not in d


def test_own_box_is_separate_and_single_tick():
    v = _view(['ON_CAMERA', 'GAP', 'GAP', 'ON_CAMERA'])
    ans = {'present': True, 'camera_id': 'CAM_B', 'detection_id': None, 'box_xyxy': [10, 10, 50, 120], 'latency_s': 0}
    d, _ = va.replay(v, _index(4), lambda t: ans, 'offline')
    assert {x['kind'] for x in d.values()} == {'OWN'}


def test_snap_by_box_iou():
    idx = _index(2)
    res = va.resolve({'present': True, 'camera_id': 'CAM_B', 'detection_id': None, 'box_xyxy': [202, 104, 262, 256]}, 0, idx)
    assert res[0] == 'SNAP' and res[2].id == 'D1'


def test_overlay_scores_snap_and_own_separately():
    v = _view(['ON_CAMERA', 'GAP', 'GAP', 'ON_CAMERA'])
    rows = [{'t_us': t, 'kind': v.kind[t], 'camera': v.camera[t], 't_visible': ['CAM_B'] if 0 < t < 3 * T else [],
             'cls': 'CORRECT' if v.kind[t] == 'ON_CAMERA' else 'MISSED'} for t in v.ticks]
    disp = {1 * T: {'src': 'AGENT', 'kind': 'SNAP', 'cam': 'CAM_B', 'box': (200, 100, 260, 260)},
            2 * T: {'src': 'AGENT', 'kind': 'OWN', 'cam': 'CAM_B', 'box': (10, 10, 20, 20)}}
    body = lambda cam, t: (190, 90, 270, 270)
    out = va.overlay(rows, disp, body)
    assert out[1]['cls'] == 'CORRECT' and out[1]['src'] == 'AGENT'
    assert out[2]['cls'] == 'MISSED' and out[2]['own'] == 'OWN_WRONG'
    st = va.episode_stats(v, rows, out)
    assert st['right_connections'] == 1 and st['own_box_wrong_ticks'] == 1
    assert st['episodes'][0]['missed_s_rule'] == 0.4 and st['episodes'][0]['missed_s_agent'] == 0.2
    assert st['own_box_wrong_s'] == 0.2 and st['combined_lost_s_while_visible'] == 0.2


def test_wrong_connection_counted_once_per_run():
    v = _view(['ON_CAMERA', 'GAP', 'GAP', 'ON_CAMERA'])
    rows = [{'t_us': t, 'kind': v.kind[t], 'camera': v.camera[t], 't_visible': ['CAM_B'], 'cls': 'MISSED'} for t in v.ticks]
    disp = {t: {'src': 'AGENT', 'kind': 'SNAP', 'cam': 'CAM_B', 'box': (0, 0, 10, 10)} for t in (1 * T, 2 * T)}
    out = va.overlay(rows, disp, lambda c, t: (190, 90, 270, 270))
    assert va.episode_stats(v, rows, out)['wrong_connections'] == 1


def test_parse_answer_validation():
    dets = {'CAM_B': [va.Det('D1', 'o', BOX, 0.5, ())]}
    ok, err = va.parse_answer(json.dumps({'present': True, 'camera_id': 'CAM_B', 'detection_id': 'D1'}), ['CAM_B'], dets)
    assert ok['detection_id'] == 'D1' and err is None
    assert va.parse_answer('nope', ['CAM_B'], dets)[1] == 'NOT_JSON'
    assert va.parse_answer(json.dumps({'present': True, 'camera_id': 'CAM_X', 'detection_id': 'D1'}), ['CAM_B'], dets)[1] == 'BAD_CAMERA'
    assert va.parse_answer(json.dumps({'present': True, 'camera_id': 'CAM_B', 'detection_id': 'D9'}), ['CAM_B'], dets)[1] == 'BAD_DETECTION_ID'
    assert va.parse_answer(json.dumps({'present': False}), ['CAM_B'], dets)[0]['present'] is False


def test_allowed_cameras_uses_graph_neighbours_only():
    tr = {('CAM_A', 'CAM_B'): 't1', ('CAM_C', 'CAM_A'): 't2', ('CAM_D', 'CAM_E'): 't3'}
    assert va.allowed_cameras('CAM_A', tr, {'CAM_A', 'CAM_B', 'CAM_C', 'CAM_D'}) == ['CAM_A', 'CAM_B', 'CAM_C']


def test_request_text_has_no_gt_fields_and_marks_draft():
    ctx = {'t_s': 3.4, 'last_camera': 'CAM_A', 'last_t_s': 3.0, 'seed': {'camera_id': 'CAM_A', 't_s': 2.0, 'colors': ['red']},
           'neighbours': ['CAM_B'], 'allowed': ['CAM_A', 'CAM_B'], 'dets': {'CAM_B': [va.Det('D1', 'o', BOX, 0.5, ('red',))]}}
    txt = va.request_text(ctx, with_images=False)
    assert 'DRAFT' in txt and 'D1' in txt and 'No images' in txt
    assert 'ground' not in txt.lower() and 'visib' not in txt.lower()


def test_own_box_correct_counts_in_combined_metrics_only():
    v = _view(['ON_CAMERA', 'GAP', 'GAP', 'ON_CAMERA'])
    rows = [{'t_us': t, 'kind': v.kind[t], 'camera': v.camera[t], 't_visible': ['CAM_B'] if v.kind[t] != 'ON_CAMERA' else [],
             'cls': 'CORRECT' if v.kind[t] == 'ON_CAMERA' else 'MISSED'} for t in v.ticks]
    disp = {1 * T: {'src': 'AGENT', 'kind': 'OWN', 'cam': 'CAM_B', 'box': (190, 90, 270, 270)}}
    out = va.overlay(rows, disp, lambda c, t: (190, 90, 270, 270))
    st = va.episode_stats(v, rows, out)
    assert out[1]['own'] == 'OWN_CORRECT' and out[1]['cls'] == 'MISSED'          # primary class untouched
    assert st['combined_lost_s_while_visible'] == 0.2 and st['own_box_correct_s'] == 0.2
    assert st['episodes'][0]['first_agent_correct_s'] == 0.2
