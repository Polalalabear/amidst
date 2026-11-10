"""WP3 gate: JSONL recording and offline REPLAY provider (#511).

Verifies R_hash == 100% across 3 replay runs, zero network calls during replay,
REPLAY_MISS fallback, §3.3 canonical JSONL format, forbidden-key/secret/path rejection,
and zero live cap deduction on replay.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import socket
import urllib.request

import pytest

from amidst.q1q5 import agent_decision as ad
from amidst.q1q5.agent_decision import AgentDecisionError, CallBudget, RuleDecider
from amidst.q1q5.agent_providers import FakeClock, OpenAIProvider
from amidst.q1q5.agent_recording import (
    RECORDING_KEYS,
    JSONLRecorder,
    ReplayProvider,
    load_recordings,
    recording_sha256,
    validate_recording_entry,
)

ROOT = Path(__file__).resolve().parents[2]
FORMAL = json.loads((ROOT / 'configs/q1q5/agent_decision_params_v1.json').read_text(encoding='utf-8'))
STAGE = 'PILOT_AND_CONSISTENCY'
FAKE_KEY = 'sk-test-FAKE-REC-SECRET-123456789'


def _scores(lo=0.5, mid=0.7, hi=0.9, n=5) -> dict:
    return {'n': n, 'min': lo, 'median': mid, 'max': hi}


def _view(id_: str, camera: str = 'CAM_A', first: int = 0, last: int = 1_000_000, colors=('red',)) -> dict:
    return {
        'id': id_,
        'camera_id': camera,
        'first_seen_us': first,
        'last_seen_us': last,
        'colors': list(colors),
        'scores': _scores(),
        'continuation_fraction': 0.1,
    }


def _cand(id_: str, camera: str = 'CAM_B', eligible: bool = True, gap: int = 400_000) -> dict:
    return dict(
        _view(id_, camera, 1_600_000, 1_800_000),
        gap_us=gap,
        graph_edge=True,
        link_kind='CROSS_CAMERA_HANDOFF',
        rule_eligible=eligible,
    )


def _dp1_question(index: int) -> dict:
    gap_b = 300_000 + index * 20_000
    gap_c = 350_000 + index * 20_000
    req = {
        'schema_version': ad.REQUEST_SCHEMA_VERSION,
        'decision_point': ad.DP1,
        'as_of_us': 2_000_000 + index * 100_000,
        'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': [['CAM_A', 'CAM_B'], ['CAM_A', 'CAM_C']]},
        'current': _view('A1'),
        'candidates': [_cand('B1', 'CAM_B', gap=gap_b), _cand('C2', 'CAM_C', gap=gap_c)],
        'rule_answer': 'ABSTAIN',
        'identity_verdict': 'UNCONFIRMED',
    }
    req['rule_answer'] = RuleDecider().answer(req)
    return req


def _dp3_question(index: int) -> dict:
    return {
        'schema_version': ad.REQUEST_SCHEMA_VERSION,
        'decision_point': ad.DP3,
        'as_of_us': 2_000_000 + index * 100_000,
        'topology': {'graph_status': 'GRAPH_NOT_APPROVED', 'edges': []},
        'current': _view('A1'),
        'rule_answer': 'ACCEPT_SEGMENT',
        'identity_verdict': 'UNCONFIRMED',
        'segment': {'start_us': 400_000, 'end_us': 800_000, 'n_frames': 3, 'box_scores': _scores(0.3, 0.35, 0.4)},
    }


def _select(id_: str = 'C2') -> dict:
    return {
        'action': 'SELECT',
        'candidate_id': id_,
        'reason_codes': ['GRAPH_EDGE', 'SHORT_GAP'],
        'rationale': f'chose {id_}',
    }


def _reject_segment() -> dict:
    return {
        'action': 'REJECT_SEGMENT',
        'reason_codes': ['LOW_SCORE'],
        'rationale': 'low score segment',
    }


def _openai_bytes(resp_obj: dict, *, model: str = 'astra6-2026-11-10', p: int = 1100, c: int = 40) -> bytes:
    return json.dumps({
        'id': 'chatcmpl-rec',
        'model': model,
        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': json.dumps(resp_obj)}}],
        'usage': {'prompt_tokens': p, 'completion_tokens': c},
    }).encode('utf-8')


def _block_network(monkeypatch):
    def _deny(*_a, **_k):
        raise AssertionError('network access is forbidden during replay')

    for attr in ('connect', 'connect_ex', 'create_connection', 'getaddrinfo'):
        if hasattr(socket, attr):
            monkeypatch.setattr(socket, attr, _deny)
        if hasattr(socket.socket, attr):
            monkeypatch.setattr(socket.socket, attr, _deny)
    monkeypatch.setattr(urllib.request, 'urlopen', _deny)


# ------------------------------------------------------------------ 1. Live record N -> Replay 3x -> R_hash = 100%

def test_live_record_and_replay_three_times_has_100_percent_r_hash(tmp_path, monkeypatch):
    questions = [_dp1_question(i) for i in range(6)] + [_dp3_question(i) for i in range(2)]
    recording_file = tmp_path / 'session_recording.jsonl'
    clock = FakeClock()
    live_calls = 0

    def fake_transport(*, url, headers, body, timeout_s):
        nonlocal live_calls
        live_calls += 1
        req_payload = json.loads(body.decode('utf-8'))
        user_req = json.loads(req_payload['messages'][1]['content'])
        clock.advance_ms(125.0 + live_calls * 5.0)
        if user_req['decision_point'] == ad.DP3:
            return 200, _openai_bytes(_reject_segment(), p=950, c=28)
        chosen = 'C2' if live_calls % 2 == 0 else 'B1'
        return 200, _openai_bytes(_select(chosen), p=1200 + live_calls, c=45)

    recorder = JSONLRecorder(recording_file, env={'OPENAI_API_KEY': FAKE_KEY})
    live_budget = CallBudget(FORMAL, STAGE)
    live_provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=fake_transport,
        env={'OPENAI_API_KEY': FAKE_KEY},
        budget=live_budget,
        recorder=recorder,
        seed=42,
        temperature=0.0,
        candidate_order_seed=99,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )

    live_records = []
    for q in questions:
        live_budget.begin_session()
        rec = ad.decide(
            q,
            mode='AGENT_LIVE',
            params=FORMAL,
            budget=live_budget,
            model='astra6',
            call=live_provider,
            provider_kind='OPENAI',
            provider_meta=live_provider.provider_meta(),
        )
        ad.validate_record(rec)
        assert rec['decision_source'] == 'AGENT'
        live_records.append(rec)

    assert live_calls == len(questions) == 8
    assert recorder.count == 8
    file_sha = recorder.sha256()
    assert file_sha == recording_sha256(recording_file) and len(file_sha) == 64

    # Disable all network functions and verify transport is called 0 times during 3 replay runs
    _block_network(monkeypatch)
    calls_before_replay = live_calls

    replay_runs_hashes: list[list[str]] = []
    for _ in range(3):
        replay_provider = ReplayProvider(recording_file)
        replay_budget = CallBudget(FORMAL, STAGE)
        run_hashes: list[str] = []
        for q, live_rec in zip(questions, live_records):
            replay_budget.begin_session()
            rep_rec = ad.decide(
                q,
                mode='AGENT_REPLAY',
                params=FORMAL,
                budget=replay_budget,
                model='astra6',
                call=replay_provider,
                provider_kind='OPENAI',
                provider_meta=live_provider.provider_meta(),
            )
            ad.validate_record(rep_rec)
            assert rep_rec['decision_source'] == 'AGENT'
            assert rep_rec['final_answer'] == live_rec['final_answer']
            run_hashes.append(hashlib.sha256(ad.canonical(rep_rec)).hexdigest())
        replay_runs_hashes.append(run_hashes)

    # R_hash == 100% across all 3 replay runs
    assert replay_runs_hashes[0] == replay_runs_hashes[1] == replay_runs_hashes[2]
    assert live_calls == calls_before_replay  # 0 transport calls during replay


# ------------------------------------------------------------------ 2. Candidate order independence & REPLAY_MISS

def test_replay_matches_reordered_candidates_and_misses_unknown_request(tmp_path):
    q = _dp1_question(0)
    recording_file = tmp_path / 'one.jsonl'
    clock = FakeClock()
    recorder = JSONLRecorder(recording_file, env={'OPENAI_API_KEY': FAKE_KEY})
    provider = OpenAIProvider(
        model='astra6',
        params=FORMAL,
        transport=lambda **_: (200, _openai_bytes(_select('C2')), 110.0),
        env={'OPENAI_API_KEY': FAKE_KEY},
        recorder=recorder,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    ad.decide(
        q, mode='AGENT_LIVE', params=FORMAL, budget=CallBudget(FORMAL, STAGE),
        model='astra6', call=provider, provider_kind='OPENAI',
    )

    replay = ReplayProvider(recording_file)
    # Reordering candidates keeps request_sha256 identical (design §3.3) -> replay hit!
    reordered = copy.deepcopy(q)
    reordered['candidates'] = list(reversed(reordered['candidates']))
    hit_rec = ad.decide(
        reordered, mode='AGENT_REPLAY', params=FORMAL, budget=CallBudget(FORMAL, STAGE),
        model='astra6', call=replay, provider_kind='OPENAI',
    )
    assert hit_rec['decision_source'] == 'AGENT' and hit_rec['final_answer'] == 'C2'

    # Unknown request_sha256 -> REPLAY_MISS -> falls back to rule answer
    unknown_q = _dp1_question(99)
    miss_rec = ad.decide(
        unknown_q, mode='AGENT_REPLAY', params=FORMAL, budget=CallBudget(FORMAL, STAGE),
        model='astra6', call=replay, provider_kind='OPENAI',
    )
    ad.validate_record(miss_rec)
    assert miss_rec['decision_source'] == 'RULE_FALLBACK'
    assert miss_rec['fallback_reason'] == 'REPLAY_MISS'
    assert miss_rec['final_answer'] == miss_rec['rule_answer'] == 'ABSTAIN'
    assert [a['outcome'] for a in miss_rec['attempts']] == ['REPLAY_MISS']


# ------------------------------------------------------------------ 3. §3.3 fields, canonical JSON, forbidden scan

def test_recording_lines_match_section_3_3_fields_and_canonical_json(tmp_path):
    q = _dp1_question(1)
    recording_file = tmp_path / 'canonical.jsonl'
    clock = FakeClock()
    recorder = JSONLRecorder(recording_file, env={'OPENAI_API_KEY': FAKE_KEY})
    provider = OpenAIProvider(
        model='terra6.1',
        params=FORMAL,
        transport=lambda **_: (200, _openai_bytes(_select('B1'), model='terra6.1-2026-11', p=1300, c=50), 140.0),
        env={'OPENAI_API_KEY': FAKE_KEY},
        recorder=recorder,
        seed=11,
        temperature=0.2,
        candidate_order_seed=7,
        clock_ms=clock.now_ms,
        sleep_ms=clock.sleep_ms,
    )
    ad.decide(
        q, mode='AGENT_LIVE', params=FORMAL, budget=CallBudget(FORMAL, STAGE),
        model='terra6.1', call=provider, provider_kind='OPENAI',
    )

    raw_lines = [line for line in recording_file.read_bytes().splitlines() if line]
    assert len(raw_lines) == 1
    parsed = json.loads(raw_lines[0].decode('utf-8'))
    assert set(parsed.keys()) == RECORDING_KEYS
    assert raw_lines[0] == ad.canonical(parsed)
    assert parsed['request_sha256'] == ad.request_sha256(q)
    assert parsed['provider'] == 'OPENAI'
    assert parsed['model'] == 'terra6.1'
    assert parsed['api_model_id'] == 'terra6.1-2026-11'
    assert parsed['model_digest'] is None
    assert parsed['seed'] == 11
    assert parsed['temperature'] == 0.2
    assert parsed['candidate_order_seed'] == 7
    assert parsed['wall_ms'] == 140.0
    assert parsed['usage'] == {'prompt_tokens': 1300, 'completion_tokens': 50}


@pytest.mark.parametrize('mutate', [
    lambda e: e['request'].update({'gt_private': 1}),
    lambda e: e['response'].update({'actor_id': 'person_1'}),
    lambda e: e['response'].update({'file_path': 'x'}),
    lambda e: e['response'].update({'rationale': f'leaked {FAKE_KEY}'}),
    lambda e: e['response'].update({'rationale': 'read from /Users/alice/secret.jsonl'}),
    lambda e: e['response'].update({'rationale': r'C:\Users\a\secret.json'}),
])
def test_recording_rejects_forbidden_keys_file_paths_and_api_keys(tmp_path, mutate):
    q = _dp1_question(0)
    base_entry = {
        'request_sha256': ad.request_sha256(q),
        'request': copy.deepcopy(q),
        'response': _select('B1'),
        'provider': 'OPENAI',
        'model': 'astra6',
        'api_model_id': 'astra6-2026-11',
        'model_digest': None,
        'seed': 0,
        'temperature': 0.0,
        'candidate_order_seed': 0,
        'wall_ms': 100.0,
        'usage': {'prompt_tokens': 1000, 'completion_tokens': 40},
    }
    validate_recording_entry(base_entry, env={'OPENAI_API_KEY': FAKE_KEY})

    bad_entry = copy.deepcopy(base_entry)
    mutate(bad_entry)
    rec_path = tmp_path / 'rejected.jsonl'
    recorder = JSONLRecorder(rec_path, env={'OPENAI_API_KEY': FAKE_KEY})
    with pytest.raises(AgentDecisionError, match='FORBIDDEN_INFERENCE_INPUT'):
        recorder.record(bad_entry)
    assert not rec_path.exists()


# ------------------------------------------------------------------ 4. Replay does not deduct LIVE caps

def test_replay_does_not_deduct_live_budget_caps(tmp_path):
    q = _dp1_question(0)
    rec_file = tmp_path / 'replay_cap.jsonl'
    recorder = JSONLRecorder(rec_file, env={'OPENAI_API_KEY': FAKE_KEY})
    recorder.record({
        'request_sha256': ad.request_sha256(q),
        'request': q,
        'response': _select('C2'),
        'provider': 'OPENAI',
        'model': 'astra6',
        'api_model_id': 'astra6-2026-11',
        'model_digest': None,
        'seed': 0,
        'temperature': 0.0,
        'candidate_order_seed': 0,
        'wall_ms': 95.0,
        'usage': {'prompt_tokens': 1400, 'completion_tokens': 55},
    })
    assert len(load_recordings(rec_file)) == 1

    params = copy.deepcopy(FORMAL)
    params['stages'][STAGE].update(max_calls=1, per_model_max_calls=1)
    budget = CallBudget(params, STAGE)
    replay = ReplayProvider(rec_file)

    for _ in range(5):
        rec = ad.decide(
            q, mode='AGENT_REPLAY', params=params, budget=budget,
            model='astra6', call=replay, provider_kind='OPENAI',
        )
        assert rec['decision_source'] == 'AGENT' and rec['final_answer'] == 'C2'

    assert budget.stage_calls == 0
    assert budget.stage_tokens == 0
    assert budget.model_calls == {'astra6': 0, 'sol6.1': 0, 'terra6.1': 0}
    assert budget.model_tokens == {'astra6': 0, 'sol6.1': 0, 'terra6.1': 0}
    assert budget.spent_usd == 0.0
    assert budget.session_rounds == 5
