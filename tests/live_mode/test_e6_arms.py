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


def make(arm, *docs, bodies=None, scene=None, ablation='none', **kw):
    return ArmDecider(arm, transport(*docs, bodies=bodies), scene or SCENE, Projection(), call_cap=kw.pop('call_cap', len(docs)),
                      poll_s=1.0, min_interval_s=1.0, ablation=ablation, **kw)


# ---- configuration -----------------------------------------------------------------------------------
def test_arm_flags_and_bad_arm():
    assert [(a, ArmConfig.of(a).history, ArmConfig.of(a).summary) for a in ARMS] == [
        ('DEANCHOR', 'previous', False), ('DEANCHOR_HIST', 'full', False), ('DEANCHOR_HIST_SUM', 'full', True)]
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
        prefix = body['input'][0]['content'][0]['text']
        assert 'E6 DE-ANCHOR RULES' in prefix and 'E6 ANSWER FORMAT' in prefix
        for hint in ('Rule gates', 'rule gate', 'previous display', 'current target', 'Tracker colour', 'displayed', 'AO_STATE',
                     'A-OPEN', 'rule_state', 'neutral tracker', 'unchanged', 'clear the target'):
            assert hint.lower() not in (prefix + json.dumps(body['input'][1])).lower(), hint
        assert 'a person wearing red' in json.dumps(body['input'][1])
    rec = d.calls[0]['request']
    assert rec['arm'] == arm and rec['reference'] and rec['candidates'] == 2
    assert all(set(c) == {'detection_id', 'camera_id', 'box', 'score', 'class_label', 'colors'} for c in rec['candidate_list'])
    assert 'rule_state' not in rec


def test_prefix_mentions_only_fields_the_arm_has():
    d = A.ArmConfig.of('DEANCHOR').extra()
    assert 'PREVIOUS_ANSWER' in d and 'SELF_ANSWER_UNVERIFIED' in d
    for word in ('SYSTEM_OBSERVED', 'HISTORY', 'summary', 'tracker kept'):
        assert word not in d, word
    h = A.ArmConfig.of('DEANCHOR_HIST').extra()
    assert 'SYSTEM_OBSERVED' in h and 'HISTORY' in h and 'summary' not in h and 'PREVIOUS_ANSWER' not in h
    assert '"summary"' in A.ArmConfig.of('DEANCHOR_HIST_SUM').extra()


def test_static_prefix_is_e6_only_and_original_prompt_untouched():
    from amidst.q1q5 import agent_service as ag
    from amidst.live_mode.aopen.decider import E5_EXTRA
    pre = A.static_prefix(SCENE, A.ArmConfig.of('DEANCHOR').extra())
    assert ag.SYSTEM_TEXT not in pre and E5_EXTRA not in pre and 'Rule gates' in ag.SYSTEM_TEXT
    assert A.sx.sha256_of(SCENE) in pre


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
    assert 'PREVIOUS_ANSWER=null' in texts['DEANCHOR'][0] and 'PREVIOUS_ANSWER=' not in texts['DEANCHOR_HIST'][0]
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


def pick(h, tick, applied=True, answer='SELECT'):
    return h.add({'answer': answer, 'camera_id': 'A', 'detection_id': 'D1', 'applied': applied, 'ask_tick': tick - 1}, tick)


def test_follow_counts_until_lost_and_uncertain_does_not_cut():
    h = HistoryLedger()
    pick(h, 1)
    h.observe('FOLLOWING')
    h.observe('COASTING')                       # neither counts nor ends
    h.observe('FOLLOWING')
    h.add({'answer': 'UNCERTAIN', 'applied': False, 'ask_tick': 5}, 6)
    h.add({'answer': 'SELECT', 'applied': False, 'fallback_reason': 'EXPIRED', 'ask_tick': 7}, 8)
    h.observe('FOLLOWING')
    assert h.entries[0][SYS]['followed_ticks'] == 3 and not h.entries[0][SYS]['follow_ended']
    assert h.entries[1][SYS]['followed_ticks'] == 0 and h.entries[1][SYS]['follow_ended']
    h.observe('LOST')
    h.observe('FOLLOWING')
    assert h.entries[0][SYS]['followed_ticks'] == 3 and h.entries[0][SYS]['follow_ended']
    assert h.entries[0][SYS]['followed_s'] == 0.6


def test_follow_replaced_by_next_applied_pick():
    h = HistoryLedger()
    pick(h, 1)
    h.observe('FOLLOWING')
    pick(h, 4)
    h.observe('FOLLOWING')
    h.observe('FOLLOWING')
    assert h.entries[0][SYS]['followed_ticks'] == 1 and h.entries[0][SYS]['follow_ended']
    assert h.entries[1][SYS]['followed_ticks'] == 2 and not h.entries[1][SYS]['follow_ended']
    h.add({'answer': 'NOT_VISIBLE', 'applied': True}, 9)      # applied clear also ends the follow
    assert h.entries[1][SYS]['follow_ended']
    assert h.ids() == {'H1', 'H2', 'H3'}


def test_deanchor_shows_only_previous_answer(frames):
    bodies = []
    d = make('DEANCHOR', answer(), answer('UNCERTAIN'), answer('UNCERTAIN'), bodies=bodies)
    run_ticks(d, frames, range(0, 16))
    line = [ln for ln in user_text(bodies[-1]).splitlines() if ln.startswith('PREVIOUS_ANSWER=')][0]
    prev = json.loads(line.split('=', 1)[1])
    assert set(prev) == {SELF}
    assert SYS not in json.dumps(prev) and 'SYSTEM_OBSERVED' not in user_text(bodies[-1]) and 'HISTORY' not in user_text(bodies[-1])
    assert prev[SELF]['answer'] == 'UNCERTAIN'          # latest answer only, not the earlier SELECT
    assert 'applied' not in line and 'followed' not in line and 'H1' not in line


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
               'arm_cfg', 'ablation'}
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


# ---- D403 ablations (applied to the selected agent only) ------------------------------------------------------------------------
RICH_SCENE = {'schema': 'amidst.scene.v1', 'identity': 'UNCONFIRMED', 'physical_walkability': 'UNKNOWN',
              'regions': [{'id': 'R1', 'kind': 'corridor', 'floor': 'F1'}],
              'region_edges': [{'id': 'E1', 'regions': ['R1', 'R2'], 'state': 'OPEN', 'traversability': 'UNKNOWN', 'via': None}],
              'camera_transitions': [{'id': 'T1', 'from': 'A', 'to': 'B', 'disposition': 'TRANSITION', 'approval': 'DRAFT'}],
              'excluded_camera_pairs': [{'from': 'A', 'to': 'C', 'reason': 'x'}],
              'cameras': [{'camera_id': c, 'position_m': [1.5, 2.5, 3.5], 'yaw_deg': 12.5, 'fov_deg': 90.0, 'footprint': [[0, 0], [4, 4]]}
                          for c in 'ABCD'],
              'overlaps': [{'cameras': ['A', 'B'], 'overlap_area_m2': 3.0, 'overlap_iou': 0.2}], 'sources': {'a': 'b'}}
SPATIAL_WORDS = ('position', 'yaw', 'fov', 'footprint', 'region', 'overlaps', 'overlap_', 'transition', 'topolog', 'traversal', 'adjacen', 'last_known',
                 'est_xy', 'ground')


def request_body(arm, ablation, frames, ticks=range(0, 3)):
    bodies = []
    d = make(arm, answer('UNCERTAIN'), bodies=bodies, scene=RICH_SCENE, ablation=ablation)
    run_ticks(d, frames, ticks)
    return bodies[0], d.calls[0]['request']


def parts(body):
    return [p for it in body['input'] for p in it['content']]


def test_ablation_none_is_byte_identical_to_the_pre_ablation_request(frames):
    gold = {'DEANCHOR': ('49b5bed08d9610c9ebaf12b4876e6ac87e7cffb2c9526b149b031383d4ecf89d', 'a4a012b3bba03b63df305518e36a24d1f6b2a6169793b1256f3d9b7b61f52a36'),
            'DEANCHOR_HIST': ('abe31838c6af2438b04f5a54df70847cf9265b8e5ac5de8836407c17371f0141', 'e2381b848d68a3695592e9da34edeb60eed342ae400b93fbb2f2f0fe79b82fa3'),
            'DEANCHOR_HIST_SUM': ('f5c6e58976113b574f793abb294644cb54d2623b29aafb9600938763c7dc9d40', 'e2381b848d68a3695592e9da34edeb60eed342ae400b93fbb2f2f0fe79b82fa3')}
    for arm in ARMS:
        bodies = []
        d = make(arm, answer('UNCERTAIN'), bodies=bodies)               # default ablation, SCENE
        run_ticks(d, frames, range(0, 3))
        r = d.calls[0]['request']
        assert (r['prefix_sha256'], hashlib.sha256(r['variable_text'].encode()).hexdigest()) == gold[arm]
        assert r['ablation'] == 'none' and d.calls[0]['ablation'] == 'none'


@pytest.mark.parametrize('arm', ARMS)
def test_no_image_has_no_image_and_everything_else_is_the_selected_request(arm, frames):
    base, rb = request_body(arm, 'none', frames)
    abl, ra = request_body(arm, 'NO_IMAGE', frames)
    assert any(p['type'] == 'input_image' for p in parts(base))
    text = json.dumps(abl)
    assert not [p for p in parts(abl) if p['type'] == 'input_image'] and 'data:image' not in text and 'image_url' not in text
    assert ra['images'] == {} and ra['reference'] is None and ra['ablation'] == 'NO_IMAGE'
    # same structured input: variable text, candidates, scene context, model parameters identical to the selected request
    assert ra['variable_text'] == rb['variable_text'] and ra['candidate_list'] == rb['candidate_list']
    assert user_text(abl) == user_text(base)
    scene_line = lambda b: [ln for ln in b['input'][0]['content'][0]['text'].splitlines() if ln.startswith('SCENE_CONTEXT')]
    assert scene_line(abl) == scene_line(base)
    for k in ('model', 'max_output_tokens', 'text', 'prompt_cache_key'):
        assert abl[k] == base[k]
    # prompt sentences that mention the removed images are gone
    prefix = abl['input'][0]['content'][0]['text'] + json.dumps(abl['input'][1])
    for word in ('reference crop', 'TARGET REFERENCE', 'shown frames', 'these frames', 'request frames', 'frames alone', 'crop'):
        assert word not in prefix, word
    assert 'a person wearing red' in json.dumps(abl['input'][1])
    assert '[frame' not in text


@pytest.mark.parametrize('arm', ARMS)
def test_no_spatial_keeps_images_and_drops_every_spatial_field(arm, frames):
    base, rb = request_body(arm, 'none', frames)
    abl, ra = request_body(arm, 'NO_SPATIAL', frames)
    assert [p for p in parts(abl) if p['type'] == 'input_image'] == [p for p in parts(base) if p['type'] == 'input_image']
    assert ra['images'] == rb['images'] and ra['reference'] == rb['reference'] and ra['candidate_list'] == rb['candidate_list']
    prefix = abl['input'][0]['content'][0]['text']
    ctx = json.loads(prefix.split('SCENE_CONTEXT=')[1].splitlines()[0])
    assert set(ctx) == {'schema', 'identity', 'cameras'} and ctx['cameras'] == [{'camera_id': c} for c in 'ABCD']
    low = (prefix + ra['variable_text']).lower()
    for w in SPATIAL_WORDS:
        assert w not in low, w
    # the camera ids and the in-frame box coordinates stay
    assert 'A D1' in ra['variable_text'] or '- A D1' in ra['variable_text'] or 'box [' in ra['variable_text']
    assert ra['variable_text'] == rb['variable_text'].replace(' Camera properties are in the scene context.', '')
    assert user_text(abl) == ra['variable_text']
    assert 'physical traversal' not in prefix and 'Camera properties' not in user_text(abl)
    # the selected request does mention them (so the test above is meaningful)
    assert 'position_m' in base['input'][0]['content'][0]['text'] and 'region' in base['input'][0]['content'][0]['text']


def test_ablation_variants_differ_only_where_expected(frames):
    base, _ = request_body('DEANCHOR_HIST', 'none', frames)
    ni, _ = request_body('DEANCHOR_HIST', 'NO_IMAGE', frames)
    ns, _ = request_body('DEANCHOR_HIST', 'NO_SPATIAL', frames)
    assert user_text(ni) == user_text(base) and ni['input'][-1]['content'][0] == base['input'][-1]['content'][0]
    assert ns['input'][1] == base['input'][1]                                    # reference layer (text and image) untouched
    assert len(parts(ns)) == len(parts(base))


def test_bad_ablation_is_refused():
    with pytest.raises(ValueError, match='BAD_ABLATION'):
        make('DEANCHOR', ablation='NO_AUDIO')
    with pytest.raises(ValueError, match='BAD_ABLATION'):
        A.static_prefix(SCENE, 'x', 'bogus')


def test_ablation_runs_still_ask_and_apply_like_the_selected_agent(frames):
    for abl in ('NO_IMAGE', 'NO_SPATIAL'):
        d = make('DEANCHOR_HIST', answer(), answer('UNCERTAIN'), scene=RICH_SCENE, ablation=abl)
        run_ticks(d, frames, range(0, 14))
        assert d.calls[0]['applied'] and d.calls[0]['ablation'] == abl and len(d.calls) == 2
