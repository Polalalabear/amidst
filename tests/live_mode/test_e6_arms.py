"""E6 arms (#721) offline tests: local fake transports only. No model, network, key or evaluation annotations."""
import ast
import hashlib
import inspect
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from amidst.live_mode.aopen import arms as A
from amidst.live_mode.aopen.arms import (ARMS, SELF, SYS, ArmConfig, ArmDecider, HistoryLedger, reject_forbidden,
                                         validate_summary, variable_text)
from amidst.live_mode.aopen.decider import AOpenDecider

REPO = Path(__file__).resolve().parents[2]
BOX = [10, 10, 30, 90]
SCENE = {'cameras': [{'camera_id': c} for c in ('A', 'B', 'C', 'D')]}
RULE_MARK = 'RULE_CAM_ZZ'


class Projection:
    def ground(self, *args):
        return [1, 2]


def answer(kind='SELECT', **kw):
    return {'answer': kind, 'camera_id': 'A', 'detection_id': 'D1', 'box_xyxy': BOX,
            'next_camera_ranking': ['B', 'A'], 'confidence': 'medium', **kw}


def transport(*docs, bodies=None):
    todo = iter(docs)

    def run(body):
        if bodies is not None:
            bodies.append(body)
        x = next(todo)
        return {'text': x if isinstance(x, str) else json.dumps(x), 'latency_s': 0, 'usage': {}}
    return run


def dets():
    return {'A': [{'bbox': list(BOX), 'score': 0.5, 'color': 'red', 'est_xy': [1, 2]}],
            'B': [{'bbox': [50, 10, 70, 90], 'score': 0.4, 'color': 'red', 'est_xy': [8, 8]}]}


def rule(acquire=False):
    return {'state': 'TRACKING', 'active_cam': RULE_MARK, 'est_xy': [1, 2], 'lost_ticks': 7,
            'events': [{'type': 'ACQUIRE'}] if acquire else []}


@pytest.fixture
def frames():
    images = {c: Image.new('RGB', (320, 180), 'black') for c in ('A', 'B', 'C', 'D')}
    yield images
    for im in images.values():
        im.close()


def run_ticks(d, frames, ticks):
    for t in ticks:
        d.step(t, dets(), frames, rule(t == 0))


def user_text(body):
    return body['input'][-1]['content'][0]['text']


def make(arm, *docs, bodies=None, **kw):
    return ArmDecider(arm, transport(*docs, bodies=bodies), SCENE, Projection(), call_cap=kw.pop('call_cap', len(docs)),
                      poll_s=1.0, min_interval_s=1.0, **kw)


# ---- configuration -----------------------------------------------------------------------------------
def test_arm_flags_and_bad_arm():
    assert [(a, ArmConfig.of(a).history, ArmConfig.of(a).summary) for a in ARMS] == [
        ('DEANCHOR', False, False), ('DEANCHOR_HIST', True, False), ('DEANCHOR_HIST_SUM', True, True)]
    with pytest.raises(ValueError):
        ArmConfig.of('AO')
    cfg = json.loads((REPO / 'configs/evaluation/e6_arms_v1.json').read_text())
    assert set(cfg['arms']) == set(ARMS)
    for a in ARMS:
        assert (cfg['arms'][a]['history'], cfg['arms'][a]['summary']) == (ArmConfig.of(a).history, ArmConfig.of(a).summary)


# ---- request structure and de-anchoring --------------------------------------------------------------
@pytest.mark.parametrize('arm', ARMS)
def test_request_has_reference_frames_candidates_and_no_rule_or_tracking(arm, frames):
    bodies = []
    d = make(arm, answer('UNCERTAIN'), answer('UNCERTAIN'), bodies=bodies)
    # An existing displayed target must not leak into the request.
    d.neutral.adopt(-1, 'A', [11, 11, 31, 91], 'AGENT_SELECT')
    run_ticks(d, frames, range(0, 8))
    assert len(bodies) >= 1
    for body in bodies:
        text = json.dumps(body)
        var = user_text(body)
        for banned in ('Rule display', 'Rule answer', 'rule_eligible', 'gate=', 'AO_STATE', 'neutral_status', 'overlap_with_last_camera',
                       RULE_MARK, '"tracking"', 'lost_ticks'):
            assert banned not in var and banned not in text, banned
        assert 'TARGET REFERENCE' in json.dumps(body['input'][1])
        assert [p['image_url'][:5] for it in body['input'][1:2] for p in it['content'] if p['type'] == 'input_image']
        assert 'E6 DE-ANCHOR OVERRIDES' in body['input'][0]['content'][0]['text']
        assert 'A-OPEN OVERRIDES' in body['input'][0]['content'][0]['text']
    rec = d.calls[0]['request']
    assert rec['arm'] == arm and rec['reference'] and rec['candidates'] == 2
    assert all(set(c) == {'detection_id', 'camera_id', 'box', 'score', 'class_label', 'colors'} for c in rec['candidate_list'])
    assert 'rule_state' not in rec


def test_e5_base_derivation_drops_only_the_state_line():
    assert 'AO_STATE' in A.E5_EXTRA and 'AO_STATE' not in A.E5_BASE and 'rule_state' not in A.E5_BASE
    assert len(A.E5_EXTRA.splitlines()) - len(A.E5_BASE.splitlines()) == 1


def test_ranking_never_reorders_frames(frames):
    bodies = []
    d = make('DEANCHOR', answer(next_camera_ranking=['D', 'C']), answer('UNCERTAIN', next_camera_ranking=['D', 'C']), bodies=bodies)
    run_ticks(d, frames, range(0, 12))
    assert d.ranking == ['D', 'C']
    cams = [[p['text'] for p in b['input'][-1]['content'] if p['type'] == 'input_text' and p['text'].startswith('[frame')] for b in bodies]
    assert len(cams) >= 2 and all(c == cams[0] for c in cams) and cams[0][0] == '[frame A]'


def test_marker_blocks_only_where_the_arm_adds_them(frames):
    texts = {}
    for arm in ARMS:
        bodies = []
        d = make(arm, answer(summary=[{'text': 'Picked D1 earlier.', 'sources': ['H1']}]), answer('UNCERTAIN'),
                 answer('UNCERTAIN'), bodies=bodies)
        run_ticks(d, frames, range(0, 20))
        texts[arm] = [user_text(b) for b in bodies]
    assert all('HISTORY=' not in t and 'PRIOR_NOTES' not in t for t in texts['DEANCHOR'])
    assert all('PRIOR_NOTES' not in t for t in texts['DEANCHOR_HIST'])
    assert 'HISTORY=[]' in texts['DEANCHOR_HIST'][0]
    assert any('HISTORY=[{' in t for t in texts['DEANCHOR_HIST'][1:])


# ---- history ---------------------------------------------------------------------------------------
def test_history_labels_and_system_follow_time(frames):
    bodies = []
    d = make('DEANCHOR_HIST', answer(), answer('UNCERTAIN'), bodies=bodies)
    run_ticks(d, frames, range(0, 14))
    last = user_text(bodies[-1])
    entries = json.loads(last.split('HISTORY=')[1].splitlines()[0])
    e = entries[0]
    assert set(e) == {'id', SYS, SELF} and e['id'] == 'H1'
    assert set(e[SELF]) == {'answer', 'camera_id', 'detection_id', 'box_xyxy', 'confidence', 'next_camera_ranking'}
    assert e[SELF]['answer'] == 'SELECT' and e[SELF]['detection_id'] == 'D1'
    assert e[SYS]['applied'] is True and e[SYS]['followed_ticks'] > 0
    assert e[SYS]['followed_s'] == e[SYS]['followed_ticks'] / 5
    # Own picks never appear under SYSTEM_OBSERVED, observations never under SELF_ANSWER_UNVERIFIED.
    assert not {'answer', 'detection_id', 'box_xyxy', 'confidence'} & set(e[SYS])
    assert not {'applied', 'followed_s', 'followed_ticks', 'fallback_reason'} & set(e[SELF])


def test_history_follow_ends_when_a_new_entry_arrives():
    h = HistoryLedger()
    h.add({'answer': 'SELECT', 'camera_id': 'A', 'detection_id': 'D1', 'applied': True, 'ask_tick': 0}, 1)
    h.observe('FOLLOWING')
    h.observe('FOLLOWING')
    h.observe('LOST')
    h.observe('FOLLOWING')
    assert h.entries[0][SYS]['followed_ticks'] == 2 and h.entries[0][SYS]['follow_ended']
    h.add({'answer': 'UNCERTAIN', 'applied': False, 'ask_tick': 9}, 10)
    assert len(h.view()) == 2 and h.ids() == {'H1', 'H2'}


def test_history_is_capped():
    h = HistoryLedger()
    for i in range(12):
        h.add({'answer': 'UNCERTAIN', 'applied': False}, i)
    assert [e['id'] for e in h.view()] == [f'H{i}' for i in range(5, 13)]


# ---- summary ---------------------------------------------------------------------------------------
GOOD = [{'text': 'Earlier I picked D1 in A.', 'sources': ['H1']}]


def test_validate_summary_all_or_nothing():
    assert validate_summary(GOOD, {'H1', 'H2'}) == GOOD
    for bad in (None, [], 'x', GOOD * 4,
                [{'text': 'no source', 'sources': []}],
                [{'text': 'unknown', 'sources': ['H9']}],
                GOOD + [{'text': 'bad second', 'sources': ['H3']}],
                [{'text': 'x' * 201, 'sources': ['H1']}],
                [{'text': '', 'sources': ['H1']}],
                [{'text': 'uses gt_visible=1', 'sources': ['H1']}],
                [{'text': 'trajectory says so', 'sources': ['H1']}],
                [{'sources': ['H1']}]):
        assert validate_summary(bad, {'H1', 'H2'}) is None
    assert validate_summary(GOOD, set()) is None      # nothing shown, nothing to cite


def test_summary_valid_is_passed_and_invalid_is_not(frames):
    for summary, passed in ((GOOD, True), ([{'text': 'made up', 'sources': ['H42']}], False)):
        bodies = []
        # First call has no history yet, so a citation of H1 is rejected there; the second call may cite H1.
        d = make('DEANCHOR_HIST_SUM', answer(), answer('UNCERTAIN', summary=summary), answer('UNCERTAIN'), bodies=bodies)
        run_ticks(d, frames, range(0, 25))
        assert len(bodies) == 3
        assert 'PRIOR_NOTES' not in user_text(bodies[1])          # first answer cites nothing valid yet
        assert ('PRIOR_NOTES' in user_text(bodies[2])) is passed
        if passed:
            assert SELF in user_text(bodies[2]).split('PRIOR_NOTES')[1]
        assert d.calls[1]['summary_valid'] is passed and d.calls[1]['summary_present'] is True


def test_summary_only_in_sum_arm(frames):
    bodies = []
    d = make('DEANCHOR_HIST', answer(), answer('UNCERTAIN', summary=GOOD), answer('UNCERTAIN'), bodies=bodies)
    run_ticks(d, frames, range(0, 25))
    assert all('PRIOR_NOTES' not in user_text(b) for b in bodies) and 'summary_valid' not in d.calls[1]


# ---- inference-side isolation -----------------------------------------------------------------------
def test_reject_forbidden_keys_and_text():
    for bad in ({'gt_visible': 1}, {'a': {'depth': 3}}, [{'actors': []}], {'x': {'visibility': 1}}, {'trajectory': 1}, 'ground_truth says'):
        with pytest.raises(ValueError):
            reject_forbidden(bad)
    reject_forbidden({'answer': 'SELECT', 'camera_id': 'A', 'reason': 'target is visible in A'})


def test_variable_text_renders_history_block():
    c = A.ag.Candidate('D1', 'A', (1, 2, 3, 4), 0.5, 'person', ())
    assert 'HISTORY=[]' in variable_text(ArmConfig.of('DEANCHOR_HIST'), 1.0, [c], ['A'], [])
    assert 'HISTORY' not in variable_text(ArmConfig.of('DEANCHOR'), 1.0, [c], ['A'], [])


def test_ledger_refuses_forbidden_fields():
    with pytest.raises(ValueError):
        HistoryLedger().add({'answer': 'SELECT', 'camera_id': 'A', 'detection_id': 'D1', 'box_xyxy': {'gt_boxes': 1}}, 1)


SOURCES = ['src/amidst/live_mode/aopen/arms.py', 'scripts/evaluation/e6_arms_run.py']
BANNED_NAME = re.compile(r'(?i)(?:ground_?truth|(?:^|_)gt(?:_|$)|visib|depth|trajector|renderer_track|expected|scoring)')


@pytest.mark.parametrize('path', SOURCES)
def test_ast_no_evaluation_imports_and_no_gt_identifiers(path):
    tree = ast.parse((REPO / path).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ''] + [a.name for a in node.names]
        else:
            mods = []
        for m in mods:
            assert not m.startswith('amidst.evaluation') and 'scoring' not in m and 'e3_f4_score' not in m, (path, m)
        # identifiers (not string constants: the blacklist regex itself is data)
        names = []
        if isinstance(node, ast.Name):
            names = [node.id]
        elif isinstance(node, ast.Attribute):
            names = [node.attr]
        elif isinstance(node, ast.arg):
            names = [node.arg]
        elif isinstance(node, ast.keyword) and node.arg:
            names = [node.arg]
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names = [node.name]
        for n in names:
            assert not BANNED_NAME.search(n), (path, n)


def test_signature_takes_only_observations():
    allowed = {'self', 'tick', 'dets', 'frames', 'rule_state', 'kind', 'arm', 'transport', 'scene', 'projector', 'kw', 'neutral_status',
               'arm_cfg'}
    for fn in (ArmDecider.__init__, ArmDecider.build_input, ArmDecider.step, ArmDecider._ask, ArmDecider._poll):
        names = set(inspect.signature(fn).parameters)
        assert names <= allowed, (fn, names - allowed)
        assert not any(BANNED_NAME.search(n) for n in names)


# ---- original AO path unchanged ---------------------------------------------------------------------
def test_original_ao_request_is_unchanged(frames):
    """Golden captured on origin/main before this change (decider.py and neutral.py untouched)."""
    for rel, digest in (('src/amidst/live_mode/aopen/decider.py', AO_DECIDER_SHA), ('src/amidst/live_mode/aopen/neutral.py', AO_NEUTRAL_SHA)):
        assert hashlib.sha256((REPO / rel).read_bytes()).hexdigest() == digest, rel
    d = AOpenDecider(transport(answer('UNCERTAIN')), SCENE, Projection(), call_cap=1, poll_s=1.0, min_interval_s=1.0)
    d.step(0, dets(), frames, rule(True))
    d.step(5, dets(), frames, rule())
    req = d.calls[0]['request']
    assert req['variable_text'].startswith('NOW t=0.0s. Rule display: TRACKING camera=RULE_CAM_ZZ')
    assert 'AO_STATE=' in req['variable_text'] and 'rule_eligible=' in req['variable_text']
    assert hashlib.sha256(req['variable_text'].encode()).hexdigest() == AO_VARTEXT_SHA
    assert req['prefix_sha256'] == AO_PREFIX_SHA


AO_DECIDER_SHA = '63fb81c7a7426de726ffdc00644cfd14a849bbda1894e61356b1fa7307ba60c7'
AO_NEUTRAL_SHA = '9754d50bdc9518868d3e21f7ea6ae5257fa51430fcb548f6961e1b4758874df3'
AO_VARTEXT_SHA = '16c8666484839f60afc3a7946031ceab7d502df7d672f273d818d308b33bcb9c'
AO_PREFIX_SHA = '3816b4ae347b787bf2ad5df2db72a1bf80d346d79bd26707f33a26416de3127f'
