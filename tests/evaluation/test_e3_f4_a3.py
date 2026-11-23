"""F4 (#658) A3 = preregistration §7: an answer applies at t_arrive only through an IoU >= 0.3 chain from t_call, else EXPIRED.
SYNTHETIC boxes and a fake transport; no network, no GT."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

Image = pytest.importorskip('PIL.Image')
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('e3_f4_run', ROOT / 'scripts/evaluation/e3_f4_run.py')
run = importlib.util.module_from_spec(spec)
spec.loader.exec_module(run)


def test_chain_box_follows_overlapping_detections_in_the_same_camera():
    hist = [{'C': [[12, 10, 52, 90], [200, 10, 240, 90]]}, {'C': [[14, 10, 54, 90]]}]
    assert run.chain_box([10, 10, 50, 90], 'C', hist) == [14, 10, 54, 90]


@pytest.mark.parametrize('hist', [[{'C': [[12, 10, 52, 90]]}, {'C': []}],             # the detection disappears
                                  [{'C': [[12, 10, 52, 90]]}, {'C': [[45, 10, 85, 90]]}],   # IoU below 0.3
                                  [{'C': [[12, 10, 52, 90]]}, {'D': [[14, 10, 54, 90]]}]])  # only in another camera
def test_chain_box_breaks_to_expired(hist):
    assert run.chain_box([10, 10, 50, 90], 'C', hist) is None


class Tracker:
    est, state, lost, active, t_seen = None, 'LOST', 5, 'B', 0.0
    last_seen = {}


def drive(boxes_by_tick, latency_s=0.5, answer=None):
    """Ticks every 0.2 s; tick 0 asks (the rule is LOST), the answer arrives at the first tick >= latency_s."""
    answer = answer or {'answer': 'SELECT', 'camera_id': 'C', 'detection_id': 'D1', 'confidence': 'high', 'reason_codes': ['SAME'],
                        'reason': 'x', 'next_camera_hint': None}

    def transport(body):
        return {'text': json.dumps(answer), 'usage': {'input_tokens': 1, 'output_tokens': 1}, 'latency_s': latency_s}
    clock = [0.0]
    d = run.make_decider('A3', transport, None, lambda: clock[0])
    d.reference = b'ref'
    frame = Image.new('RGB', (320, 180))
    outs = []
    for i, boxes in enumerate(boxes_by_tick):
        t = round(i * 0.2, 3)
        clock[0] = t
        dets = {'C': [{'bbox': b, 'est_xy': [1.0 + 0.01 * i, 2.0], 'score': 0.9, 'color': 'red'} for b in boxes]}
        tracking = {'state': 'LOST', 'active_cam': 'B', 'lost_ticks': 5, 'events': [], 'target': {'color': 'red'}}
        outs.append(d.step(i, t, Tracker(), tracking, dets, {'C': frame}))
    return d, outs


def test_a3_answer_applies_through_an_unbroken_chain():
    d, outs = drive([[[10, 10, 50, 90]], [[12, 10, 52, 90]], [[14, 10, 54, 90]], [[16, 10, 56, 90]]])
    assert d.chain_log == [{'answer': 'SELECT', 'camera_id': 'C', 'ticks_chained': 3, 'result': 'CHAINED'}]
    rec = d.records[-1]
    assert rec['tick'] == 3 and rec['applied'] is True and rec['source'] == 'AGENT'                  # 0.6 s >= t_call + 0.5 s
    assert outs[3]['active_cam'] == 'C' and outs[3]['state'] == 'TRACKING'
    assert all(o['active_cam'] == 'B' for o in outs[:3])                                               # rule display while in flight


def test_a3_broken_chain_is_expired_and_not_shown():
    d, outs = drive([[[10, 10, 50, 90]], [[12, 10, 52, 90]], [], [[14, 10, 54, 90]]])
    assert d.chain_log[-1]['result'] == 'EXPIRED'
    rec = d.records[-1]
    assert rec['applied'] is False and rec['source'] == 'RULE_FALLBACK' and rec['fallback_reason'] == 'EXPIRED'
    assert outs[3]['active_cam'] == 'B' and outs[3]['fallback_reason'] == 'EXPIRED'


def test_a3_not_visible_only_changes_the_search_hint():
    d, outs = drive([[[10, 10, 50, 90]]] * 4, answer={'answer': 'NOT_VISIBLE', 'reason_codes': ['GONE'], 'reason': 'x',
                                                       'next_camera_hint': 'C', 'camera_id': None})
    assert d.chain_log == [] and outs[3]['advisor']['next_camera_hint'] == 'C' and outs[3]['active_cam'] == 'B'
