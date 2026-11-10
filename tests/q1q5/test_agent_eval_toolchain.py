"""Additional unit and integration tests for Agent evaluation toolchain (#515)."""

from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ad = importlib.import_module('amidst.q1q5.agent_decision')
ccd = importlib.import_module('amidst.q1q5.cross_camera_demo')
qb = importlib.import_module('amidst.agent_eval.question_bank')
sp = importlib.import_module('amidst.agent_eval.synthetic_perturbation')
r1 = importlib.import_module('amidst.agent_eval.rule_r1')
latency = importlib.import_module('amidst.agent_eval.latency')
runner = importlib.import_module('amidst.agent_eval.runner')
windows_pack = importlib.import_module('amidst.agent_eval.windows_pack')
metrics_mod = importlib.import_module('amidst.agent_eval_scoring.metrics')
scoring_cli = importlib.import_module('amidst.agent_eval_scoring.cli')

PARAMS = json.loads((ROOT / 'configs/q1q5/agent_decision_params_v1.json').read_text(encoding='utf-8'))
EDGES = {('CAM_A', 'CAM_B'): 'A_TO_B', ('CAM_B', 'CAM_C'): 'B_TO_C'}


def _scores(med: float = 0.72) -> dict:
    return {'n': 5, 'min': 0.5, 'median': med, 'max': 0.9}


def _view(
    id_: str,
    camera: str = 'CAM_A',
    first: int = 0,
    last: int = 1_000_000,
    colors: tuple = ('red',),
    cont: float = 0.1,
) -> dict:
    return {
        'id': id_,
        'camera_id': camera,
        'first_seen_us': first,
        'last_seen_us': last,
        'colors': list(colors),
        'scores': _scores(),
        'continuation_fraction': cont,
    }


def _cand(cid: str, cam: str = 'CAM_B', gap: int = 400_000, edge: bool = True, med: float = 0.75) -> dict:
    c = dict(
        _view(cid, cam, 1_600_000, 1_800_000),
        gap_us=gap,
        graph_edge=edge,
        link_kind='CROSS_CAMERA_HANDOFF',
        rule_eligible=True,
    )
    c['scores'] = _scores(med)
    return c


def _sample_dp1(idx: int = 0) -> dict:
    cands = [
        _cand('B1', gap=300_000 + idx * 50_000, med=0.72),
        _cand('B2', gap=450_000 + idx * 50_000, med=0.81),
    ]
    req = {
        'schema_version': ad.REQUEST_SCHEMA_VERSION,
        'decision_point': ad.DP1,
        'as_of_us': 2_000_000 + idx * 100_000,
        'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': [['CAM_A', 'CAM_B']]},
        'current': _view('A1'),
        'candidates': cands,
        'rule_answer': ad.ABSTAIN,
        'identity_verdict': 'UNCONFIRMED',
    }
    req['rule_answer'] = ad.RuleDecider().answer(req)
    return req


def _trk(camera: str, ref: str, times: list[int], color: str = 'red', score: float = 0.7):
    obs = [
        ccd.Observation(camera, t, f'{ref}:{t}', score, frozenset([color]), evidence_kind='PERSON_DETECTION')
        for t in times
    ]
    return ccd.Track(camera, ref, tuple(obs))


def test_extract_requests_from_run_preserves_response_sha256():
    grid = lambda a, b: list(range(a, b, 200_000))  # noqa: E731
    tracks = [
        _trk('CAM_A', 'a', grid(0, 600_000)),
        _trk('CAM_B', 'b', grid(1_000_000, 2_000_000)),
        _trk('CAM_C', 'c', grid(1_000_000, 2_200_000)),
    ]
    baseline_res = ccd.response(
        tracks,
        EDGES,
        as_of_us=2_600_000,
        parameters=ccd.Parameters(),
        clock_mapping_sha256='a' * 64,
    )
    captured, extracted_res = qb.extract_requests_from_run(
        tracks,
        EDGES,
        as_of_us=2_600_000,
        parameters=ccd.Parameters(),
        clock_mapping_sha256='a' * 64,
        params=PARAMS,
    )
    assert hashlib.sha256(ad.canonical(baseline_res)).hexdigest() == hashlib.sha256(
        ad.canonical(extracted_res)
    ).hexdigest()
    assert len(captured) >= 1
    for req in captured:
        ad.validate_request(req)


def test_s2_generates_at_least_8_clusters_and_counts_episodes_d203(tmp_path):
    # Create 4 DP1 requests: first 3 at consecutive timestamps (100ms apart -> 1 episode), 4th far apart (-> 2nd episode)
    r0 = _sample_dp1(0)
    r1_req = _sample_dp1(1)
    r2_req = _sample_dp1(2)
    r3_req = _sample_dp1(20)
    questions = qb.build_questions(
        [r0, r1_req, r2_req, r3_req],
        commit='84a97b64',
        params_sha256='a' * 64,
        scene_sha256='b' * 64,
        source_run='r004-a4',
    )
    ep = qb.count_ambiguous_episodes(questions, max_step_us=200_000)
    assert ep['n_ambiguous_timestamps'] == 4
    assert ep['n_ambiguous_episodes'] == 2
    assert ep['episodes_by_run']['r004-a4'][0]['n_timestamps'] == 3
    assert ep['episodes_by_run']['r004-a4'][1]['n_timestamps'] == 1

    safe_tracks = [
        {
            'camera_id': 'CAM_B' if i % 2 == 0 else 'CAM_C',
            'first_seen_us': 100_000 * i,
            'last_seen_us': 100_000 * i + 400_000,
            'colors': ['red'] if i % 2 == 0 else ['orange'],
            'scores': _scores(0.6 + 0.02 * i),
            'continuation_fraction': 0.1,
        }
        for i in range(10)
    ]
    safe_path = tmp_path / 'safe_index.json'
    safe_path.write_text(
        json.dumps({'schema_version': 'safe-track-index-v1', 'tracks': safe_tracks}),
        encoding='utf-8',
    )

    result = sp.generate_synthetic_clusters(
        questions,
        safe_index_path=safe_path,
        seeds=(1, 2, 3, 4, 5, 6, 7, 8),
        per_point=2,
        out_dir=tmp_path / 's2_clusters',
    )
    assert result['n_clusters'] >= 8
    assert result['n_synthetic'] == 4 * 8
    assert result['ambiguous_episodes']['n_ambiguous_episodes'] >= 8


def test_scoring_metrics_hand_calculated_and_insufficient_gate():
    # 1. Camera recall R_cam
    rec = metrics_mod.compute_camera_recall(
        covered_frames=[('CAM_A', 100), ('CAM_B', 200)],
        target_gt_frames=[('CAM_A', 100), ('CAM_A', 150), ('CAM_B', 200)],
    )
    assert rec['per_camera']['CAM_A'] == pytest.approx(0.5)
    assert rec['per_camera']['CAM_B'] == pytest.approx(1.0)
    assert rec['macro'] == pytest.approx(0.75)
    assert rec['micro'] == pytest.approx(2.0 / 3.0)

    # 2. Switch metrics
    sw = metrics_mod.compute_switch_metrics(
        switch_count=4,
        false_switch_count=1,
        total_frames=100,
        duration_us=30_000_000,
    )
    assert sw['switch_ratio'] == pytest.approx(0.04)
    assert sw['FS_per_min'] == pytest.approx(2.0)

    # 3. Fallback, timeout, schema invalid rates
    fb = metrics_mod.compute_fallback_and_call_rates([
        {'decision_source': 'AGENT', 'fallback_reason': None, 'attempts': [{'outcome': 'OK'}]},
        {
            'decision_source': 'RULE_FALLBACK',
            'fallback_reason': 'ROUND_LIMIT',
            'attempts': [{'outcome': 'PROVIDER_TIMEOUT'}, {'outcome': 'INVALID_RESPONSE'}],
        },
    ])
    assert fb['FB'] == pytest.approx(0.5)
    assert fb['FB_by_reason'] == {'ROUND_LIMIT': pytest.approx(0.5)}
    assert fb['TO'] == pytest.approx(1.0 / 3.0)
    assert fb['SI'] == pytest.approx(1.0 / 3.0)

    # 4. Consistency K and Fleiss' kappa
    cons = metrics_mod.compute_consistency_k({'q1': ['B1', 'B1', 'B1'], 'q2': ['B1', 'B2', 'B1']})
    assert cons['Cons_K'] == pytest.approx(0.5)

    # 5. Replay hash consistency R_hash (gate fails if < 100%)
    r_ok = metrics_mod.compute_replay_hash_consistency([[{'a': 1}, {'b': 2}], [{'a': 1}, {'b': 2}]])
    assert r_ok['R_hash'] == 1.0 and r_ok['gate_passed'] is True and r_ok['status'] == 'PASS'
    r_fail = metrics_mod.compute_replay_hash_consistency([[{'a': 1}, {'b': 2}], [{'a': 1}, {'b': 3}]])
    assert r_fail['R_hash'] == pytest.approx(0.5) and r_fail['gate_passed'] is False and r_fail['status'] == 'FAIL'

    # 6. Sign test power gates: n_scored < 20 -> INSUFFICIENT
    st_small = metrics_mod.paired_sign_test(12, 2, n_scored=15)
    assert st_small['verdict'] == 'INSUFFICIENT'
    st_under = metrics_mod.paired_sign_test(12, 2, n_scored=25)
    assert st_under['verdict'] == 'INCONCLUSIVE_UNDERPOWERED'
    st_pow = metrics_mod.paired_sign_test(25, 5, n_scored=40)
    assert st_pow['verdict'] == 'POWERED'
    assert st_pow['p_value_one_sided'] < 0.001

    # 7. Cluster bootstrap and Holm-Bonferroni
    boot = metrics_mod.cluster_bootstrap_ci([(f'c{i}', 0.8) for i in range(10)], n_boot=100, seed=42)
    assert boot['status'] == 'OK' and boot['ci95'] == [0.8, 0.8]
    holm = metrics_mod.holm_bonferroni({'m1': 0.01, 'm2': 0.03, 'm3': 0.20})
    assert holm['m1']['p_holm'] == pytest.approx(0.03) and holm['m1']['reject'] is True
    assert holm['m3']['reject'] is False


def test_runner_live_approved_stage_and_colab_helpers(tmp_path):
    q_list = [_sample_dp1(0), _sample_dp1(1)]
    q_path = tmp_path / 'requests_v1.jsonl'
    q_path.write_text(
        ''.join(
            json.dumps({
                'request_sha256': ad.request_sha256(r),
                'decision_point': r['decision_point'],
                'request': r,
            }) + '\n'
            for r in q_list
        ),
        encoding='utf-8',
    )
    params_path = ROOT / 'configs/q1q5/agent_decision_params_v1.json'
    out_dir = tmp_path / 'live_pilot'

    def _fake_provider(req, *, timeout_ms, max_output_tokens):
        resp = {
            'action': 'SELECT',
            'candidate_id': req['candidates'][0]['id'],
            'reason_codes': ['GRAPH_EDGE'],
            'rationale': 'synthetic test',
        }
        return ad.Attempt('OK', 12.0, resp, 100, 20)

    rc = runner.main(
        [
            '--questions', str(q_path),
            '--params', str(params_path),
            '--stage', 'PILOT_AND_CONSISTENCY',
            '--k', '1',
            '--model', 'astra6',
            '--live',
            '--out', str(out_dir),
        ],
        provider=_fake_provider,
    )
    assert rc == 0
    for fname in ('recordings.jsonl', 'decisions.jsonl', 'latency.json', 'MANIFEST.json'):
        assert (out_dir / fname).is_file()

    l4 = runner.detect_colab_gpu('NVIDIA L4\n')
    assert l4['is_l4'] is True and l4['measure_latency'] is True
    t4 = runner.detect_colab_gpu('Tesla T4\n')
    assert t4['is_l4'] is False and t4['measure_latency'] is False and t4['status'] == 'NON_L4_DECISIONS_ONLY'

    models_txt = 'qwen2.5:7b-instruct-q4_K_M@sha256:111\nllama3.1:8b-instruct-q4_K_M@sha256:222\n'
    tags_ok = {
        'models': [
            {
                'name': 'qwen2.5:7b-instruct-q4_K_M',
                'digest': 'sha256:111',
                'details': {'quantization_level': 'Q4_K_M'},
            },
            {
                'name': 'llama3.1:8b-instruct-q4_K_M',
                'digest': 'sha256:222',
                'details': {'quantization_level': 'Q4_K_M'},
            },
        ]
    }
    assert runner.verify_ollama_models(models_txt, tags_ok)['valid'] is True
    tags_bad = {'models': [{'name': 'qwen2.5:7b-instruct-q4_K_M', 'digest': 'sha256:999'}]}
    assert runner.verify_ollama_models(models_txt, tags_bad)['valid'] is False

    nb = json.loads((ROOT / 'notebooks/agent_decision/colab_l4.ipynb').read_text(encoding='utf-8'))
    assert nb['cells']
    for cell in nb['cells']:
        first_line = ''.join(cell['source']).lstrip().splitlines()[0]
        assert first_line.startswith('#') or first_line.startswith('<!--')


def test_windows_pack_verify_pack_catches_planted_forbidden_keys_and_tampering(tmp_path):
    src = tmp_path / 'src'
    src.mkdir()
    req = _sample_dp1(0)
    (src / 'requests_v1.jsonl').write_text(json.dumps({'request': req}) + '\n', encoding='utf-8')
    (src / 'params.json').write_text(json.dumps({'mode': 'DRY_RUN'}), encoding='utf-8')

    pack_dir = tmp_path / 'pack'
    windows_pack.build_pack(
        pack_dir,
        files={
            'data/requests_v1.jsonl': src / 'requests_v1.jsonl',
            'configs/params.json': src / 'params.json',
        },
    )
    proc = subprocess.run(
        [sys.executable, str(pack_dir / 'tools' / 'verify_pack.py'), str(pack_dir)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0 and 'VALID' in proc.stdout

    # Plant forbidden key in pack -> verify_pack.py must return 1 and print INVALID
    leaked = pack_dir / 'data' / 'leaked.json'
    leaked.write_text(json.dumps({'gt_private': 1}), encoding='utf-8')
    proc_bad = subprocess.run(
        [sys.executable, str(pack_dir / 'tools' / 'verify_pack.py'), str(pack_dir)],
        capture_output=True,
        text=True,
    )
    assert proc_bad.returncode == 1 and 'INVALID' in proc_bad.stdout
    leaked.unlink()

    # Tamper with uploaded file -> SHA-256 mismatch -> INVALID
    (pack_dir / 'configs' / 'params.json').write_text(json.dumps({'mode': 'TAMPERED'}), encoding='utf-8')
    proc_tamper = subprocess.run(
        [sys.executable, str(pack_dir / 'tools' / 'verify_pack.py'), str(pack_dir)],
        capture_output=True,
        text=True,
    )
    assert proc_tamper.returncode == 1 and 'INVALID' in proc_tamper.stdout

    with pytest.raises(ValueError):
        windows_pack.build_pack(tmp_path / 'bad_pack', files={'../escape.json': src / 'params.json'})
