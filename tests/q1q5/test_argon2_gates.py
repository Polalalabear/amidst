"""Acceptance gates for the Agent evaluation toolchain (Argon task #515), D200.

Contract: docs/contracts/AGENT_EVAL_TOOLCHAIN_GATES_V1.md (read it first; it is normative).

Every gate is ``xfail(strict=True)``: it must fail today (modules do not exist) and Argon turns
it into PASS by implementing the contract. When a gate passes, strict xfail reports XPASS as a
failure, which forces the owner to delete the marker (the completion condition of #515).

Module interface summary (full detail in the contract document):

  amidst.agent_eval.question_bank
      build_questions(requests, *, source_run, commit, params_sha256, scene_sha256,
                      candidate_order_seed=0) -> list[dict]
      write_question_bank(questions, out_dir) -> dict      # requests_v1.jsonl + MANIFEST.json
  amidst.agent_eval.synthetic_perturbation
      generate_synthetic(questions, *, safe_index_path, seed, per_point, out_dir) -> dict
  amidst.agent_eval.rule_r1
      load_params(path=None) -> dict ; R1Decider(params=None).answer(request) -> str
      R1Decider.params_report() -> {name: {"value": ..., "status": "PROPOSED"}}
  amidst.agent_eval.latency
      GROUPS, group_params() -> {group: {timeout_ms, budget_ms, max_rounds}}, summarize(samples)
  amidst.agent_eval.runner
      main(argv, *, provider=None) -> int                  # default DRY_RUN
  amidst.agent_eval.windows_pack
      build_pack(out_dir, *, files) -> dict                # MANIFEST.json with upload_list
  amidst.agent_eval_scoring.mapping / .cli                 # separate package, subprocess only

These tests use synthetic data only. ``FAKE_GT_FIXTURE`` below is invented in this file; no
real ground truth, scoring_private/ or media is read. No network, no OPENAI_API_KEY.
"""
import ast
import hashlib
import importlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from amidst.q1q5 import agent_decision as ad

ROOT = Path(__file__).resolve().parents[2]
ISSUE = '#515'
GATE = pytest.mark.xfail(strict=True, reason=f'awaiting Argon ② {ISSUE}')
FORMAL_PARAMS = ROOT / 'configs/q1q5/agent_decision_params_v1.json'
EXPLORATORY_PARAMS = ROOT / 'configs/q1q5/agent_decision_params_v1_exploratory.json'
QUESTION_VERSION = 'amidst.agent-eval-question.v1'
LABEL_KEY = 'inserted_candidate_ids'  # lives only in scoring_private/ (contract §3)
EXTRA_FORBIDDEN = ('visib' + 'ility', 'dep' + 'th', 'traject' + 'ory', 'gt_' + 'private', 'scoring_' + 'private',
                   'ground' + '_truth')


# ------------------------------------------------------------------ fixtures (synthetic only)

def _scores(median=.7):
    return {'n': 5, 'min': .5, 'median': median, 'max': .9}


def _view(id_, camera='CAM_A', first=0, last=1_000_000, colors=('red',), cont=.1):
    return {'id': id_, 'camera_id': camera, 'first_seen_us': first, 'last_seen_us': last,
            'colors': list(colors), 'scores': _scores(), 'continuation_fraction': cont}


def _cand(id_, *, eligible=True, gap=400_000, edge=True, median=.7, camera='CAM_B'):
    c = dict(_view(id_, camera, 1_600_000, 1_800_000), gap_us=gap, graph_edge=edge,
             link_kind='CROSS_CAMERA_HANDOFF', rule_eligible=eligible)
    c['scores'] = _scores(median)
    return c


def _dp1(*candidates, rule_answer=None):
    req = {'schema_version': ad.REQUEST_SCHEMA_VERSION, 'decision_point': ad.DP1, 'as_of_us': 2_000_000,
           'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': [['CAM_A', 'CAM_B']]},
           'current': _view('A1'), 'candidates': list(candidates) or [_cand('B1')],
           'rule_answer': ad.ABSTAIN, 'identity_verdict': 'UNCONFIRMED'}
    req['rule_answer'] = rule_answer or ad.RuleDecider().answer(req)
    return req


def _dp3(cont=.3):
    req = {'schema_version': ad.REQUEST_SCHEMA_VERSION, 'decision_point': ad.DP3, 'as_of_us': 2_000_000,
           'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': [['CAM_A', 'CAM_B']]},
           'current': _view('A1', cont=cont),
           'segment': {'start_us': 1_000_000, 'end_us': 1_800_000, 'n_frames': 4, 'box_scores': _scores()},
           'rule_answer': ad.ACCEPT_SEGMENT, 'identity_verdict': 'UNCONFIRMED'}
    return req


def _requests(n_dp1=12, n_dp3=3):
    """Deterministic synthetic requests; DP1 ones carry 2-3 candidates with distinct gaps."""
    out = []
    for i in range(n_dp1):
        cands = [_cand(f'B{j + 1}', gap=300_000 + 50_000 * (i + j), eligible=bool(j % 2 == 0)) for j in range(2 + i % 2)]
        out.append(_dp1(*cands))
    out += [_dp3(cont=.1 + .05 * i) for i in range(n_dp3)]
    return out


COMMIT = 'a' * 40
PARAMS_SHA = 'b' * 64
SCENE_SHA = 'c' * 64


def _build(requests=None, **kw):
    qb = importlib.import_module('amidst.agent_eval.question_bank')
    args = dict(source_run='fake-run-1', commit=COMMIT, params_sha256=PARAMS_SHA, scene_sha256=SCENE_SHA)
    args.update(kw)
    return qb, qb.build_questions(requests if requests is not None else _requests(), **args)


def _all_keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _all_keys(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _all_keys(v)


def _is_forbidden_key(key):
    low = str(key).lower()
    return low in ad.FORBIDDEN_KEYS or low.startswith('gt_') or any(low == e for e in EXTRA_FORBIDDEN)


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# FAKE_GT_FIXTURE: four invented actors on one camera with disjoint boxes.
FAKE_ACTORS = {'zeta-target': [0, 0, 10, 10], 'eta-samecolor': [20, 0, 30, 10],
               'theta-nearcolor': [40, 0, 50, 10], 'iota-control': [60, 0, 70, 10]}
FAKE_TARGET = 'zeta-target'
FAKE_TIMES = [1_000_000 + 100_000 * i for i in range(5)]


def fake_gt_fixture():
    return {'fixture': 'FAKE_GT_FIXTURE', 'target': FAKE_TARGET,
            'frames': [{'camera_id': 'CAM_B', 'timestamp_us': t, 'boxes': dict(FAKE_ACTORS)} for t in FAKE_TIMES]}


def fake_iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def fake_gt_source(camera_id, timestamp_us):
    return {k: list(v) for k, v in FAKE_ACTORS.items()} if camera_id == 'CAM_B' and timestamp_us in FAKE_TIMES else {}


def _obs(box, times=FAKE_TIMES):
    return [{'camera_id': 'CAM_B', 'timestamp_us': t, 'box': list(box)} for t in times]


# ------------------------------------------------------------------ self-tests (NOT xfail)

def test_selftest_fixture_requests_are_valid():
    for request in _requests():
        ad.validate_request(request)


def test_selftest_fake_gt_iou_and_actor_separation():
    assert fake_iou([0, 0, 10, 10], [0, 0, 10, 10]) == 1.0
    assert fake_iou([0, 0, 10, 10], [0, 0, 10, 5]) == 0.5
    assert fake_iou([0, 0, 10, 10], [0, 0, 10, 4]) == pytest.approx(0.4)
    assert fake_iou([0, 0, 10, 10], [20, 0, 30, 10]) == 0.0
    boxes = list(FAKE_ACTORS.values())
    assert len(boxes) == 4
    for i, a in enumerate(boxes):
        shifted = [a[0] + 1, a[1], a[2] + 1, a[3]]
        best = max(range(4), key=lambda j: fake_iou(shifted, boxes[j]))
        assert best == i and fake_iou(shifted, a) > 0.8
    assert fake_gt_fixture()['target'] in FAKE_ACTORS and len(fake_gt_fixture()['frames']) == len(FAKE_TIMES)


def test_selftest_forbidden_key_detector_catches_planted_keys():
    assert not any(_is_forbidden_key(k) for k in _all_keys(_requests()))
    for planted in ('gt_private', 'scoring_private', 'visib' + 'ility', 'dep' + 'th', 'traject' + 'ory', 'gt_anything'):
        assert any(_is_forbidden_key(k) for k in _all_keys({'x': [{planted: 1}]}))


def test_selftest_percentile_convention_example():
    values = list(range(1, 11))
    nearest = lambda p: sorted(values)[-(-p * len(values) // 100) - 1]  # noqa: E731  ceil(p/100*n)-1
    assert (nearest(50), nearest(90), nearest(99)) == (5, 9, 10)


# ------------------------------------------------------------------ gate 1: question bank

def test_g1_every_question_binds_commit_params_scene_and_request_sha(tmp_path):
    qb, questions = _build()
    assert len(questions) == len(_requests())
    for q in questions:
        assert q['schema_version'] == QUESTION_VERSION
        assert (q['commit'], q['params_sha256'], q['scene_sha256'], q['source_run']) == (
            COMMIT, PARAMS_SHA, SCENE_SHA, 'fake-run-1')
        assert q['request_sha256'] == ad.request_sha256(q['request'])
        assert q['decision_point'] == q['request']['decision_point']
        assert q['question_class'] == 'REAL'
        ad.validate_request(q['request'])
    manifest = qb.write_question_bank(questions, tmp_path)
    on_disk = json.loads((tmp_path / 'MANIFEST.json').read_text())
    assert on_disk == manifest
    assert manifest['commit'] == COMMIT and manifest['params_sha256'] == PARAMS_SHA
    assert manifest['scene_sha256'] == SCENE_SHA and manifest['n_questions'] == len(questions)
    assert manifest['requests_sha256'] == _sha(tmp_path / 'requests_v1.jsonl')


def test_g1_same_input_gives_byte_identical_bank(tmp_path):
    qb, questions = _build()
    qb2, questions2 = _build()
    a, b = tmp_path / 'a', tmp_path / 'b'
    qb.write_question_bank(questions, a)
    qb2.write_question_bank(questions2, b)
    for name in ('requests_v1.jsonl', 'MANIFEST.json'):
        assert (a / name).read_bytes() == (b / name).read_bytes()
    reordered = [dict(r, candidates=list(reversed(r['candidates']))) if 'candidates' in r else r for r in _requests()]
    _, questions3 = _build(reordered)
    assert [q['request_sha256'] for q in questions3] == [q['request_sha256'] for q in questions]


def test_g1_allowed_answers_are_candidate_ids_plus_abstain_or_accept_reject():
    _, questions = _build()
    seen = set()
    for q in questions:
        seen.add(q['decision_point'])
        if q['decision_point'] == ad.DP1:
            ids = [c['id'] for c in q['request']['candidates']]
            assert sorted(q['allowed_answers']) == sorted(ids + [ad.ABSTAIN])
        else:
            assert sorted(q['allowed_answers']) == [ad.ACCEPT_SEGMENT, ad.REJECT_SEGMENT]
    assert seen == {ad.DP1, ad.DP3}


# ------------------------------------------------------------------ gate 2: FORBIDDEN keys

def test_g2_no_forbidden_key_in_questions_requests_or_files(tmp_path):
    qb, questions = _build()
    qb.write_question_bank(questions, tmp_path)
    rows = _jsonl(tmp_path / 'requests_v1.jsonl')
    assert rows
    for row in rows:
        bad = [k for k in _all_keys(row) if _is_forbidden_key(k)]
        assert not bad, bad
    assert not [k for k in _all_keys(json.loads((tmp_path / 'MANIFEST.json').read_text())) if _is_forbidden_key(k)]
    assert not [k for k in _all_keys(questions) if _is_forbidden_key(k)]


@pytest.mark.parametrize('planted', ['gt_private', 'scoring_private', 'visib' + 'ility', 'dep' + 'th',
                                      'traject' + 'ory', 'gt_x'])
def test_g2_planted_forbidden_key_fails_the_whole_batch(planted):
    requests = _requests()
    requests[3]['current'][planted] = 1
    with pytest.raises(ad.AgentDecisionError):
        _build(requests)


# ------------------------------------------------------------------ gate 3: S2 synthetic perturbation

def _safe_index(tmp_path, extra=None):
    tracks = []
    for i in range(8):
        tracks.append({'camera_id': 'CAM_C' if i % 2 else 'CAM_B', 'first_seen_us': 100_000 * i,
                       'last_seen_us': 100_000 * i + 400_000, 'colors': ['red'] if i % 3 else ['orange'],
                       'scores': _scores(.5 + .04 * i), 'continuation_fraction': .1})
    doc = {'schema_version': 'safe-track-index-v1', 'tracks': tracks}
    doc.update(extra or {})
    path = tmp_path / 'safe' / 'safe_index.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(doc))
    return path


def _s2(tmp_path, name='out', seed=7, per_point=2, safe=None):
    sp = importlib.import_module('amidst.agent_eval.synthetic_perturbation')
    _, questions = _build()
    out = tmp_path / name
    safe = safe or _safe_index(tmp_path)
    result = sp.generate_synthetic([q for q in questions if q['decision_point'] == ad.DP1],
                                   safe_index_path=safe, seed=seed, per_point=per_point, out_dir=out)
    return sp, result, out, safe


def test_g3_label_only_in_scoring_private_and_questions_flagged_synthetic(tmp_path):
    _, result, out, _ = _s2(tmp_path)
    q_path, l_path = Path(result['questions_path']), Path(result['labels_path'])
    assert l_path.resolve().parent == (out / 'scoring_private').resolve()
    assert (out / 'scoring_private') not in q_path.resolve().parents
    labels = json.loads(l_path.read_text())
    rows = _jsonl(q_path)
    assert rows and len(rows) == len(labels) == result['n_synthetic']
    for row in rows:
        assert row['question_class'] == 'SYNTHETIC_PERTURBATION'
        ad.validate_request(row['request'])
        assert row['request']['rule_answer'] == ad.RuleDecider().answer(row['request'])
        assert row['request_sha256'] == ad.request_sha256(row['request'])
        inserted = labels[row['request_sha256']][LABEL_KEY]
        ids = [c['id'] for c in row['request']['candidates']]
        assert len(inserted) == 2 and set(inserted) <= set(ids)
        assert sorted(row['allowed_answers']) == sorted(ids + [ad.ABSTAIN])


def test_g3_decision_side_cannot_see_or_infer_the_label(tmp_path):
    _, result, _, _ = _s2(tmp_path, per_point=1)
    text = Path(result['questions_path']).read_text()
    labels = json.loads(Path(result['labels_path']).read_text())
    assert LABEL_KEY not in text and 'scoring_private' not in text
    positions = set()
    for row in _jsonl(result['questions_path']):
        prompt = ad.canonical(row['request']).decode()  # prompt is derived from the request only
        assert LABEL_KEY not in prompt and 'synthetic' not in prompt.lower()
        assert 'perturb' not in prompt.lower() and 'inserted' not in prompt.lower()
        ids = [c['id'] for c in row['request']['candidates']]
        inserted = labels[row['request_sha256']][LABEL_KEY][0]
        positions.add(ids.index(inserted))
        assert all(ad.OPAQUE_ID.fullmatch(i) for i in ids)
    assert len(positions) > 1, 'inserted candidate must not sit at a fixed position'


def test_g3_generator_reads_only_the_safe_index(tmp_path, monkeypatch):
    sp = importlib.import_module('amidst.agent_eval.synthetic_perturbation')
    _, questions = _build()
    dp1 = [q for q in questions if q['decision_point'] == ad.DP1]
    safe = _safe_index(tmp_path)
    reads = []
    real_open = io.open

    def spy(file, mode='r', *a, **k):
        if isinstance(file, (str, bytes, os.PathLike)) and not set(mode) & set('wax+'):
            reads.append(Path(os.fsdecode(file)).resolve())
        return real_open(file, mode, *a, **k)

    with monkeypatch.context() as m:
        m.setattr('builtins.open', spy)
        m.setattr(io, 'open', spy)
        sp.generate_synthetic(dp1, safe_index_path=safe, seed=1, per_point=1, out_dir=tmp_path / 'out')
    assert reads and set(reads) == {safe.resolve()}


def test_g3_same_seed_same_bytes_and_protected_index_is_rejected(tmp_path):
    _, r1, _, safe = _s2(tmp_path, 'a', seed=3)
    _, r2, _, _ = _s2(tmp_path, 'b', seed=3, safe=safe)
    _, r3, _, _ = _s2(tmp_path, 'c', seed=4, safe=safe)
    assert _sha(r1['questions_path']) == _sha(r2['questions_path'])
    assert _sha(r1['labels_path']) == _sha(r2['labels_path'])
    assert _sha(r1['questions_path']) != _sha(r3['questions_path'])
    bad = tmp_path / 'bad'
    bad.mkdir()
    with pytest.raises(ad.AgentDecisionError):
        _s2(bad, safe=_safe_index(bad, {'gt_private': {'x': 1}}))


# ------------------------------------------------------------------ gate 4: scoring isolation

DECISION_SIDE = [*sorted((ROOT / 'src/amidst/q1q5').glob('*.py')), *sorted((ROOT / 'src/amidst/agent_eval').glob('*.py')),
                 *sorted((ROOT / 'scripts/agent_decision').glob('*.py'))]


def _imports_scoring(path):
    tree = ast.parse(path.read_text())
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            hits += [a.name for a in node.names if 'agent_eval_scoring' in a.name]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ''] + [a.name for a in node.names]
            hits += [n for n in names if 'agent_eval_scoring' in n]
        elif (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
              and isinstance(node.args[0].value, str) and 'agent_eval_scoring' in node.args[0].value):
            hits.append(node.args[0].value)
    return hits


def test_g4_decision_and_bank_modules_never_import_scoring():
    required = ['src/amidst/agent_eval/question_bank.py', 'src/amidst/agent_eval/synthetic_perturbation.py',
                'src/amidst/agent_eval/rule_r1.py', 'src/amidst/agent_eval/runner.py']
    assert all((ROOT / r).is_file() for r in required), 'decision-side modules must exist to be scanned'
    assert (ROOT / 'src/amidst/agent_eval_scoring/__init__.py').is_file()
    offenders = {str(p.relative_to(ROOT)): _imports_scoring(p) for p in DECISION_SIDE if _imports_scoring(p)}
    assert not offenders, offenders
    code = ('import sys, amidst.agent_eval.question_bank, amidst.agent_eval.synthetic_perturbation, '
            'amidst.agent_eval.rule_r1, amidst.agent_eval.runner; '
            "assert not [m for m in sys.modules if 'agent_eval_scoring' in m], 'scoring imported'")
    proc = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, cwd=ROOT,
                          env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')})
    assert proc.returncode == 0, proc.stderr


def test_g4_iou_maps_each_track_to_the_right_actor_among_four():
    mapping = importlib.import_module('amidst.agent_eval_scoring.mapping')
    assert mapping.iou([0, 0, 10, 10], [0, 0, 10, 5]) == 0.5
    kw = dict(iou_match=.5, iou_manual_low=.3, majority_fraction=.6)
    for actor, box in FAKE_ACTORS.items():
        shifted = [box[0] + 1, box[1], box[2] + 1, box[3]]
        result = mapping.map_track_to_actor(_obs(shifted), fake_gt_source, **kw)
        assert result == {'actor': actor, 'needs_manual': False, 'majority_fraction': 1.0}
    half = _obs([1, 0, 11, 10], FAKE_TIMES[:3]) + _obs([20, 0, 30, 10], FAKE_TIMES[3:])
    assert mapping.map_track_to_actor(half, fake_gt_source, **kw)['actor'] == FAKE_TARGET  # 3/5 == 0.6 inclusive
    split = _obs([0, 0, 10, 10], FAKE_TIMES[:2]) + _obs([20, 0, 30, 10], FAKE_TIMES[2:4]) + _obs([0, 0, 1, 1], FAKE_TIMES[4:])
    out = mapping.map_track_to_actor(split, fake_gt_source, **kw)
    assert out['needs_manual'] is True and out['actor'] is None and out['majority_fraction'] < .6
    middling = mapping.map_track_to_actor(_obs([0, 0, 10, 4]), fake_gt_source, **kw)  # IoU 0.4 for every frame
    assert middling['needs_manual'] is True and middling['actor'] is None
    assert mapping.map_track_to_actor(_obs([0, 0, 10, 5]), fake_gt_source, **kw)['actor'] == FAKE_TARGET  # IoU 0.5 inclusive


def test_g4_scoring_runs_in_a_subprocess_and_leaks_no_actor_info(tmp_path):
    q1 = _dp1(_cand('B1', gap=300_000), _cand('B2', gap=500_000))
    q2 = _dp1(_cand('B1', gap=350_000), _cand('B2', gap=550_000))
    sha1, sha2 = ad.request_sha256(q1), ad.request_sha256(q2)
    questions = [{'request_sha256': s, 'decision_point': ad.DP1, 'question_class': 'REAL', 'request': q}
                 for s, q in ((sha1, q1), (sha2, q2))]
    t_box, d_box = [1, 0, 11, 10], [21, 0, 31, 10]
    observations = {s: {'candidates': {'B1': _obs(t_box), 'B2': _obs(d_box)}} for s in (sha1, sha2)}
    decisions = [{'request_sha256': sha1, 'answer': 'B1'}, {'request_sha256': sha2, 'answer': 'B2'}]
    files = {'questions.jsonl': '\n'.join(json.dumps(r) for r in questions) + '\n',
             'decisions.jsonl': '\n'.join(json.dumps(r) for r in decisions) + '\n',
             'observations.json': json.dumps(observations),
             'gt_fixture.json': json.dumps(fake_gt_fixture()),
             'params.json': json.dumps({'iou_match': .5, 'iou_manual_low': .3, 'majority_fraction': .6,
                                        'status': 'PROPOSED'})}
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    out = tmp_path / 'scored'
    cmd = [sys.executable, '-m', 'amidst.agent_eval_scoring.cli', '--questions', str(tmp_path / 'questions.jsonl'),
           '--decisions', str(tmp_path / 'decisions.jsonl'), '--candidate-observations', str(tmp_path / 'observations.json'),
           '--gt-fixture', str(tmp_path / 'gt_fixture.json'), '--params', str(tmp_path / 'params.json'),
           '--out', str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=tmp_path,
                          env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')})
    assert proc.returncode == 0, proc.stderr
    rows = {r['request_sha256']: r for r in _jsonl(out / 'per_question.jsonl')}
    assert all(set(r) == {'request_sha256', 'correct'} for r in rows.values())
    assert rows[sha1]['correct'] is True and rows[sha2]['correct'] is False
    metrics = json.loads((out / 'metrics.json').read_text())
    assert metrics['Acc_dp']['DP1'] == pytest.approx(.5) and metrics['n_scored'] == 2
    blob = ''.join(p.read_text() for p in out.rglob('*') if p.is_file())
    assert not [a for a in FAKE_ACTORS if a in blob]


# ------------------------------------------------------------------ gate 5: R1 rule baseline

def _r1():
    return importlib.import_module('amidst.agent_eval.rule_r1')


def test_g5_params_are_proposed_and_follow_design_tie_order():
    r1 = _r1()
    params = r1.load_params()
    assert params['dp1_tie_order']['value'] == ['gap_us', 'graph_edge', 'score_median', 'id']
    assert 0 < params['dp3_reject_continuation_fraction']['value'] < 1
    assert all(v['status'] == 'PROPOSED' for v in params.values())
    report = r1.R1Decider().params_report()
    assert set(report) == set(params) and all(v['status'] == 'PROPOSED' for v in report.values())
    assert (ROOT / 'configs/q1q5/agent_r1_params_v1.json').is_file()


def test_g5_dp1_tie_rules_in_design_order_and_reproducible():
    decider = _r1().R1Decider()
    a = _dp1(_cand('B1', gap=500_000, edge=True, median=.9), _cand('B2', gap=300_000, edge=False, median=.5))
    assert decider.answer(a) == 'B2'  # 1) smallest gap beats edge and score
    b = _dp1(_cand('B1', gap=300_000, edge=False, median=.9), _cand('B2', gap=300_000, edge=True, median=.5))
    assert decider.answer(b) == 'B2'  # 2) equal gap: topology edge wins
    c = _dp1(_cand('B1', median=.6), _cand('B2', median=.8))
    assert decider.answer(c) == 'B2'  # 3) equal gap and edge: higher score median
    d = _dp1(_cand('B2'), _cand('B1'))
    assert decider.answer(d) == 'B1'  # 4) everything equal: id order
    e = _dp1(_cand('B1', eligible=False), _cand('B2', gap=900_000, eligible=True))
    assert decider.answer(e) == 'B2'  # only rule-eligible candidates compete
    assert decider.answer(_dp1(_cand('B1', eligible=False), _cand('B2', eligible=False))) == ad.ABSTAIN
    for request in (a, b, c, d, e):
        first = decider.answer(request)
        assert first == _r1().R1Decider().answer(request) == decider.answer(dict(request, candidates=request['candidates'][::-1]))
        assert first in {x['id'] for x in request['candidates']}


def test_g5_dp3_rejects_only_above_the_threshold():
    r1 = _r1()
    decider = r1.R1Decider()
    threshold = r1.load_params()['dp3_reject_continuation_fraction']['value']
    assert decider.answer(_dp3(cont=min(1.0, threshold + .01))) == ad.REJECT_SEGMENT
    assert decider.answer(_dp3(cont=threshold)) == ad.ACCEPT_SEGMENT  # "exceeds" is strict
    assert decider.answer(_dp3(cont=max(0.0, threshold - .01))) == ad.ACCEPT_SEGMENT


# ------------------------------------------------------------------ gate 6: runner and latency

class _EnvTrap(dict):
    def _boom(self, *a, **k):
        raise AssertionError('OPENAI_API_KEY must not be read')

    def __getitem__(self, key):
        if key == 'OPENAI_API_KEY':
            self._boom()
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == 'OPENAI_API_KEY':
            self._boom()
        return super().get(key, default)

    def __contains__(self, key):
        if key == 'OPENAI_API_KEY':
            self._boom()
        return super().__contains__(key)

    items = values = _boom


class _CountingProvider:
    def __init__(self):
        self.calls = 0

    def __call__(self, request, *, timeout_ms, max_output_tokens):
        self.calls += 1
        raise AssertionError('provider must not be called')


def _block_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError('network access attempted')

    for name in ('connect', 'connect_ex', 'bind', 'sendto'):
        monkeypatch.setattr(socket.socket, name, boom)
    for name in ('create_connection', 'getaddrinfo', 'gethostbyname'):
        monkeypatch.setattr(socket, name, boom)


def _questions_file(tmp_path, n=6):
    path = tmp_path / 'requests_v1.jsonl'
    path.write_text(''.join(json.dumps({'request_sha256': ad.request_sha256(r), 'decision_point': r['decision_point'],
                                        'request': r}) + '\n' for r in _requests(n, 0)))
    return path


def test_g6_default_is_dry_run_with_zero_calls_no_network_no_api_key(tmp_path, monkeypatch):
    runner = importlib.import_module('amidst.agent_eval.runner')
    _block_network(monkeypatch)
    trap = _EnvTrap({**os.environ, 'OPENAI_API_KEY': 'sk-test-FAKE'})
    monkeypatch.setattr(os, 'environ', trap)
    qpath, provider, out = _questions_file(tmp_path), _CountingProvider(), tmp_path / 'run'
    rc = runner.main(['--questions', str(qpath), '--params', str(FORMAL_PARAMS), '--stage', 'PILOT_AND_CONSISTENCY',
                      '--k', '3', '--out', str(out)], provider=provider)
    assert rc == 0 and provider.calls == 0
    report = json.loads((out / 'dry_run.json').read_text())
    params = json.loads(FORMAL_PARAMS.read_text())
    assert report['mode'] == 'DRY_RUN' and report['provider_calls'] == 0
    assert report['estimate'] == ad.dry_run_estimate(params, questions=6, k=3, stage='PILOT_AND_CONSISTENCY')


def test_g6_live_flag_with_unapproved_stage_is_refused(tmp_path, monkeypatch):
    runner = importlib.import_module('amidst.agent_eval.runner')
    _block_network(monkeypatch)
    monkeypatch.setattr(os, 'environ', _EnvTrap({**os.environ, 'OPENAI_API_KEY': 'sk-test-FAKE'}))
    assert json.loads(FORMAL_PARAMS.read_text())['stages']['FORMAL']['approved'] is False
    provider = _CountingProvider()
    rc = runner.main(['--questions', str(_questions_file(tmp_path)), '--params', str(FORMAL_PARAMS), '--stage', 'FORMAL',
                      '--live', '--out', str(tmp_path / 'run')], provider=provider)
    assert rc != 0 and provider.calls == 0


def test_g6_latency_groups_are_separate_and_use_their_own_parameters():
    latency = importlib.import_module('amidst.agent_eval.latency')
    assert tuple(latency.GROUPS) == ('tracking_formal', 'search_relaxed')
    params = latency.group_params()
    assert params['tracking_formal'] == {'timeout_ms': 2000, 'budget_ms': 5000, 'max_rounds': 3}
    ex = json.loads(EXPLORATORY_PARAMS.read_text())
    assert params['search_relaxed'] == {'timeout_ms': ex['per_call']['timeout_ms'],
                                        'budget_ms': ex['per_step']['budget_ms'],
                                        'max_rounds': ex['per_step']['max_rounds']}
    samples = [{'group': 'tracking_formal', 'kind': 'call', 'wall_ms': v} for v in range(1, 11)]
    samples += [{'group': 'search_relaxed', 'kind': 'call', 'wall_ms': 1000 * v} for v in range(1, 11)]
    samples += [{'group': 'tracking_formal', 'kind': 'step', 'wall_ms': 7}]
    out = latency.summarize(samples)
    assert out['tracking_formal']['call'] == {'n': 10, 'p50': 5, 'p90': 9, 'p99': 10}
    assert out['search_relaxed']['call'] == {'n': 10, 'p50': 5000, 'p90': 9000, 'p99': 10000}
    assert out['tracking_formal']['step']['n'] == 1 and 'step' not in out['search_relaxed']
    with pytest.raises(ValueError):
        latency.summarize([{'group': 'mixed', 'kind': 'call', 'wall_ms': 1}])


# ------------------------------------------------------------------ gate 7: Windows pack

def test_g7_upload_list_has_sha256_and_relative_paths(tmp_path):
    pack = importlib.import_module('amidst.agent_eval.windows_pack')
    src = tmp_path / 'src'
    (src / 'sub').mkdir(parents=True)
    (src / 'a.jsonl').write_text('{"x":1}\n')
    (src / 'sub' / 'b.json').write_text('{"y":2}')
    out = tmp_path / 'pack'
    manifest = pack.build_pack(out, files={'data/a.jsonl': src / 'a.jsonl', 'data/sub/b.json': src / 'sub' / 'b.json'})
    on_disk = json.loads((out / 'MANIFEST.json').read_text())
    assert on_disk == manifest and manifest['upload_list']
    assert {r['relative_path'] for r in manifest['upload_list']} >= {'data/a.jsonl', 'data/sub/b.json'}
    for row in manifest['upload_list']:
        assert set(row) == {'relative_path', 'sha256'}
        rel = row['relative_path']
        assert not rel.startswith(('/', '\\')) and ':' not in rel and '\\' not in rel and '..' not in rel.split('/')
        assert row['sha256'] == _sha(out / rel)
    for needed in ('README.md', 'RETURN/README.txt', 'tools/verify_pack.py'):
        assert (out / needed).is_file()
    readme = (out / 'README.md').read_text()
    for heading in ('工作內容', '要上傳的檔案', '操作步驟', '不要改'):
        assert heading in readme
    assert all(r['relative_path'] in readme for r in manifest['upload_list'])
    for js in out.rglob('*.json'):
        assert not [k for k in _all_keys(json.loads(js.read_text())) if _is_forbidden_key(k)]
