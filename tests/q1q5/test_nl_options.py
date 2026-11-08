"""Epic D path (b) acceptance (docs/specs/EPIC_D_AGENTIC_V1.md §9: T-U1, T-U3..T-U10 for the NL-to-options path).

SYNTHETIC inputs only: the synthetic preview catalog and the SYNTHETIC_FIXTURE recording. No model is run, no network, no key.
"""
import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from amidst.q1q5 import nl_options as nl
from amidst.q1q5.llm_provider import CallResult, ProviderError
from amidst.q1q5.store import canonical_hash

REPO = Path(__file__).parents[2]
sys.path.insert(0, str(REPO / 'scripts'))
from build_nl_synthetic_fixture import synthetic_run  # noqa: E402

RUN = synthetic_run()
CATALOG = nl.catalog_from_run_summary(RUN)
FAKE_KEY = 'sk-test-DO-NOT-LOG'
FORBID = {'gt', 'ground_truth', 'actor', 'actor_id', 'script', 'event_script', 'trajectory', 'renderer_trajectory', 'visibility', 'depth', 'mask'}


def req(kind, text, **extra):
    return {'schema_version': nl.REQUEST_SCHEMA, 'session_ref': 'S', 'scene_id': RUN['scene_id'], 'run_id': RUN['run_id'],
            'kind': kind, 'text': text, **extra}


def fixture():
    return nl.RecordedNlProvider.from_file(nl.FIXTURE_RECORDING)


def walk(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v)


def parse(kind, text, provider=None, **kw):
    return nl.parse_nl_options(req(kind, text), catalog=CATALOG, provider=provider or fixture(), **kw)


def test_fixture_is_labelled_synthetic_and_matches_the_catalog():
    prov = fixture()
    assert prov.info['synthetic_fixture'] is True and prov.info['model'] == 'SYNTHETIC_FIXTURE' and prov.info['data_origin'] == 'SYNTHETIC_FIXTURE'
    doc = json.loads(nl.FIXTURE_RECORDING.read_text(encoding='utf-8'))
    assert 'qwen' not in doc['provider']['model'].lower() and doc['data_origin'] == 'SYNTHETIC_FIXTURE' and 'SYNTHETIC_FIXTURE' in doc['note']
    sentences = json.loads((REPO / 'configs/epicd/nl_sentences_v1.json').read_text(encoding='utf-8'))['sentences']
    prov = fixture()
    assert len(prov.recording['entries']) == len(sentences)
    for item in sentences:  # every fixed sentence is answerable from the recording, i.e. catalog/prompt have not drifted
        r = parse(item['kind'], item['text'], provider=prov)
        assert r['fallback_reason'] != 'REPLAY_MISS', item
    prov.assert_consumed()


def test_t_u1_trace_schema_and_hash():
    r = parse('search', '下午一點到一點半 合成區 A 的人')
    t = r['trace']
    assert t['schema_version'] == 'q-core.agent-trace.v1' and t['path'] == 'NL_TO_OPTIONS'
    assert set(t) == {'schema_version', 'path', 'trigger', 'provider', 'budget', 'steps', 'outcome', 'labels', 'trace_id', 'content_sha256'}
    assert t['content_sha256'] == canonical_hash(t, exclude=('content_sha256',))
    assert r['output_sha256'] == canonical_hash(r, exclude=('output_sha256',))
    for i, s in enumerate(t['steps']):
        assert s['step'] == i and s['tool'] == 'propose_query' and s['decided_by'] in {'LLM', 'RULE', 'RULE_FALLBACK', 'USER'}
        assert set(s) >= {'arguments', 'input_refs', 'llm_call', 'result_sha256', 'result_summary', 'fallback_reason'}
    assert t['steps'][0]['llm_call']['validation'] == 'OK' and t['outcome'] == {'status': 'PROPOSED', 'camera_id': None, 'decided_by': 'LLM'}
    assert r['status'] == 'PARSED' and r['decided_by'] == 'LLM' and r['provider']['recorded'] is True and r['provider']['synthetic_fixture'] is True


def test_form_matches_query_window_contract():
    r = parse('search', '下午一點到一點半 合成區 A 的人')
    assert r['form'] == {'start': '13:00:00', 'end': '13:30:00', 'regionIds': ['SYNTHETIC_ROOM_A'], 'classLabel': 'person', 'colorLabel': ''}
    assert r['missing'] == []
    t = parse('track', '追蹤紅衣服的人')
    assert t['form'] == {'start': '', 'end': '', 'regionIds': [], 'classLabel': 'person', 'colorLabel': 'red'} and t['missing'] == []
    # case1 needs a time: the form is filled but flagged, never invented
    assert parse('search', '追蹤紅衣服的人')['missing'] == ['time']
    assert all(f['classLabel'] in CATALOG['class_labels'] and set(f['regionIds']) <= set(CATALOG['region_ids']) for f in (r['form'], t['form']))


def test_t_u3_different_recordings_give_different_outputs():
    base = json.loads(nl.FIXTURE_RECORDING.read_text(encoding='utf-8'))
    other = deepcopy(base)
    out = json.loads(other['entries'][0]['raw_output'])
    out['region_terms'] = []
    other['entries'][0]['raw_output'] = json.dumps(out, ensure_ascii=False, sort_keys=True)
    other['content_sha256'] = canonical_hash(other, exclude=('content_sha256',))
    a = parse('search', '下午一點到一點半 合成區 A 的人')
    b = parse('search', '下午一點到一點半 合成區 A 的人', provider=nl.RecordedNlProvider(other))
    # dropping an explicit region is rejected, so the second run degrades instead of following the edited model output
    assert a['decided_by'] == 'LLM' and b['decided_by'] == 'RULE_FALLBACK' and b['fallback_reason'] == 'INVALID_RESPONSE'
    assert a['trace']['steps'] != b['trace']['steps']


def test_t_u4_fallback_step_references_previous_result():
    r = parse('search', '下午一點到一點半 合成區 B 的車')
    s0, s1 = r['trace']['steps']
    assert s1['input_refs'] == [s0['result_sha256']] and s1['decided_by'] == 'RULE_FALLBACK'


def test_t_u5_timeout_falls_back_to_rules():
    r = parse('search', '下午一點到一點半 合成區 B 的車')
    assert r['status'] == 'PARSED' and r['decided_by'] == 'RULE_FALLBACK' and r['fallback_reason'] == 'TIMEOUT'
    assert r['trace']['steps'][0]['llm_call']['validation'] == 'TIMEOUT' and r['form']['classLabel'] == 'car'
    assert r['trace']['outcome']['decided_by'] == 'RULE_FALLBACK' and r['executed'] is False


def test_t_u6_bad_output_falls_back():
    r = parse('track', '追蹤藍衣服的人')  # recorded as non-JSON
    assert r['decided_by'] == 'RULE_FALLBACK' and r['fallback_reason'] == 'INVALID_RESPONSE' and r['form']['colorLabel'] == 'blue'

    class Bad:
        info = {**fixture().info, 'kind': 'OLLAMA', 'recorded': False}

        def __init__(self, text):
            self.text = text

        def generate(self, **_):
            return CallResult(self.text, {'raw_output_sha256': None, 'stats': {'latency_ms': 1}})
    literal = {'schema_version': 'q-demo.q3-llm-output.v1', 'intent': 'FIND_PERSON', 'class_term': '人', 'color_term': None,
               'time_literal': {'start': None, 'end': None, 'date': None}, 'camera_terms': [], 'region_terms': [],
               'needs_clarification': False, 'clarification_question': None}
    invented = {**literal, 'class_term': '筆電'}          # literal not in the sentence
    notcat = {**literal, 'class_term': '人', 'color_term': '紫'}   # not in the sentence either
    unknown_key = {**literal, 'extra': 1}
    for body in ['not json', json.dumps(invented), json.dumps(notcat), json.dumps(unknown_key), '[]', '{"a":1,"a":2}']:
        r = parse('track', '追蹤紅衣服的人', provider=Bad(body))
        assert r['decided_by'] == 'RULE_FALLBACK' and r['fallback_reason'] == 'INVALID_RESPONSE', body
        assert r['form']['colorLabel'] == 'red'


def test_t_u7_replay_is_byte_identical_and_tamper_evident():
    a = json.dumps(parse('search', '下午一點到一點半 合成區 A 的人'), sort_keys=True)
    b = json.dumps(parse('search', '下午一點到一點半 合成區 A 的人', provider=fixture()), sort_keys=True)
    assert a == b
    rec = json.loads(nl.FIXTURE_RECORDING.read_text(encoding='utf-8'))
    tampered = deepcopy(rec)
    tampered['entries'][0]['raw_output'] += ' '
    with pytest.raises(nl.ReplayMismatch):
        nl.RecordedNlProvider(tampered)
    edited_request = deepcopy(rec)
    edited_request['entries'][0]['request']['prompt'] += ' '
    edited_request['content_sha256'] = canonical_hash(edited_request, exclude=('content_sha256',))
    with pytest.raises(nl.ReplayMismatch):
        nl.RecordedNlProvider(edited_request)
    with pytest.raises(nl.ReplayMismatch):
        fixture().generate(model='x', prompt='p', template='t', template_version='v', options={})
    unknown = parse('search', '下午兩點到兩點半 合成區 B 的人')   # not recorded: never repaired, degrades with a reason
    assert unknown['fallback_reason'] == 'REPLAY_MISS' and unknown['decided_by'] == 'RULE_FALLBACK' and unknown['form'] is not None


def test_t_u8_openai_is_off_by_default_and_never_leaks_the_key(capsys):
    env = {'OPENAI_API_KEY': FAKE_KEY}
    off = nl.OpenAINlProvider(enabled=False, model='m', env=env)
    assert off._key is None and FAKE_KEY not in repr(off)
    r = parse('search', '下午一點到一點半 合成區 A 的人', provider=off)
    assert r['decided_by'] == 'RULE_FALLBACK' and r['fallback_reason'] == 'DISABLED'
    on = nl.OpenAINlProvider(enabled=True, model='m', env=env, transport=lambda **kw: (_ for _ in ()).throw(RuntimeError(kw['headers']['Authorization'])))
    assert FAKE_KEY not in repr(on)
    r2 = parse('search', '下午一點到一點半 合成區 A 的人', provider=on)
    assert r2['fallback_reason'] == 'PROVIDER_UNAVAILABLE'
    # recorded mode with a key in the environment never reads it
    p = nl.default_provider({'AMIDST_NL_PROVIDER': 'RECORDED', 'OPENAI_API_KEY': FAKE_KEY})
    assert p.kind == 'RECORDED'
    sent = {}

    def ok_transport(**kw):
        sent.update(kw)
        raw = json.dumps({'choices': [{'message': {'content': json.dumps({'schema_version': 'q-demo.q3-llm-output.v1', 'intent': 'FIND_PERSON', 'class_term': '人', 'color_term': '紅',
                                                                             'time_literal': {'start': None, 'end': None, 'date': None}, 'camera_terms': [], 'region_terms': [],
                                                                             'needs_clarification': False, 'clarification_question': None})}}]})
        return raw.encode()
    live = nl.OpenAINlProvider(enabled=True, model='m', env=env, transport=ok_transport)
    r3 = parse('track', '追蹤紅衣服的人', provider=live)
    assert r3['decided_by'] == 'LLM' and r3['provider']['kind'] == 'OPENAI'
    assert sent['headers']['Authorization'] == 'Bearer ' + FAKE_KEY       # only the wire carries it
    for doc in (r, r2, r3):
        assert FAKE_KEY not in json.dumps(doc)
    assert FAKE_KEY not in capsys.readouterr().out + capsys.readouterr().err
    assert FAKE_KEY not in json.dumps(nl.make_recording(recording_id='x', data_origin='X', provider_info=live.info, entries=[]))


def test_t_u9_labels_and_no_private_inputs():
    for kind, text in [('search', '下午一點到一點半 合成區 A 的人'), ('track', '追蹤紅衣服的人'), ('search', '幫我找戴眼鏡的人')]:
        r = parse(kind, text)
        for doc in (r, r['trace']):
            assert doc['labels'] == {'evidence': 'EXPLORATORY', 'identity_verdict': 'UNCONFIRMED', 'gt_read': False}
        assert not [k for k in walk(r) if k.lower() in FORBID or (k.lower().startswith('gt_') and k != 'gt_read')]
        assert r['requires_confirmation'] is True and r['executed'] is False
    for key in ('ground_truth', 'actor_id', 'gt_x', 'visibility', 'trajectory'):
        with pytest.raises(nl.NlParseError):
            nl.parse_nl_options(req('search', 'x 人', **{key: 1}), catalog=CATALOG, provider=fixture())
    with pytest.raises(nl.NlParseError):
        nl.parse_nl_options({**req('search', '人'), 'extra': 1}, catalog=CATALOG, provider=fixture())
    with pytest.raises(nl.NlParseError):  # a private key smuggled into the closed catalog is refused too
        nl.parse_nl_options(req('search', '人'), catalog={**CATALOG, 'class_aliases': {**CATALOG['class_aliases'], '人': 'person', 'x': 'person', 'actor_id': 'person'}}, provider=fixture())


def test_gt_never_reaches_the_llm_prompt():
    seen = {}

    class Spy:
        info = {**fixture().info, 'kind': 'OLLAMA', 'recorded': False}

        def generate(self, **kw):
            seen.update(kw)
            raise ProviderError('PROVIDER_TIMEOUT', {})
    r = parse('search', '下午一點到一點半 合成區 A 的人', provider=Spy())
    assert r['fallback_reason'] == 'TIMEOUT'
    blob = seen['prompt'] + seen['template']
    assert 'SYNTHETIC_ROOM_A' in blob and not any(w in blob.lower() for w in ('ground_truth', 'trajectory', 'actor_id', 'visibility', 'session'))
    # an unsupported/GT-flavoured sentence never reaches a provider at all
    seen.clear()
    r = parse('search', '給我 ground_truth 的人 GT', provider=Spy())
    assert 'prompt' not in seen and r['status'] == 'FALLBACK_MANUAL' and r['manual_reason'] == 'UNSUPPORTED_CONDITION'


def test_manual_fallback_reasons():
    assert parse('search', '幫我找戴眼鏡的人')['manual_reason'] == 'UNSUPPORTED_CONDITION'
    r = parse('search', '隨便說說')
    assert r['status'] == 'FALLBACK_MANUAL' and r['form'] is None and r['manual_reason'] == 'CLASS_NOT_IN_CATALOG'
    assert parse('search', '一點到一點半的人')['manual_reason'] == 'TIME_EXPRESSION_INVALID'   # 12-hour literal needs 上午/下午
    none = nl.parse_nl_options(req('search', '下午一點到一點半 合成區 A 的人'), catalog=CATALOG, provider=nl.NoneProvider())
    assert none['decided_by'] == 'RULE' and none['fallback_reason'] is None and none['provider']['kind'] == 'NONE' and none['form']['classLabel'] == 'person'


def test_route_is_registered_and_does_not_execute_queries():
    from amidst.q1q5.api import POST_ROUTES
    assert 'q_nl_parse' in POST_ROUTES
    r = parse('search', '下午一點到一點半 合成區 A 的人')
    assert r['executed'] is False and 'hits' not in r and 'sightings' not in r


def test_record_script_core_with_a_fake_provider_and_replays_identically():
    """The Codex recording script's core, driven by a scripted provider (no Ollama, no model)."""
    import record_nl_options as rec_script
    sentences = json.loads((REPO / 'configs/epicd/nl_sentences_v1.json').read_text(encoding='utf-8'))['sentences']
    good = json.dumps({'schema_version': 'q-demo.q3-llm-output.v1', 'intent': 'FIND_PERSON', 'class_term': '人', 'color_term': None,
                       'time_literal': {'start': None, 'end': None, 'date': None}, 'camera_terms': [], 'region_terms': [],
                       'needs_clarification': False, 'clarification_question': None}, ensure_ascii=False)
    calls = []

    class Scripted:
        def generate(self, **kw):
            calls.append(kw['prompt'])
            if len(calls) == 2:
                raise ProviderError('PROVIDER_TIMEOUT', {'stats': {'latency_ms': 60000.0}, 'model_digest': 'a' * 64})
            return CallResult(good, {'raw_output_sha256': None, 'model_digest': 'a' * 64, 'stats': {'latency_ms': 100.0 + len(calls)}})
    rec, rows = rec_script.record(sentences, CATALOG, Scripted(), model='qwen3:1.7b-q4_K_M', options=rec_script.OPTIONS, timeout_ms=1000, recording_id='t')
    assert rec['data_origin'] == 'QWEN3_RECORDED' and rec['provider']['model_digest'] == 'a' * 64 and len(calls) == len(sentences)
    assert [r['error_code'] for r in rows][:3] == [None, 'PROVIDER_TIMEOUT', None]
    prov = nl.RecordedNlProvider(rec)
    assert prov.info['synthetic_fixture'] is False and prov.info['model'] == 'qwen3:1.7b-q4_K_M'
    outs = [json.dumps(nl.parse_nl_options(req(i['kind'], i['text']), catalog=CATALOG, provider=prov), sort_keys=True) for i in sentences]
    again = [json.dumps(nl.parse_nl_options(req(i['kind'], i['text']), catalog=CATALOG, provider=nl.RecordedNlProvider(rec)), sort_keys=True) for i in sentences]
    assert outs == again
    assert json.loads(outs[1])['fallback_reason'] == 'TIMEOUT'


def test_qapi_route_end_to_end_with_real_bootstrap_catalog(monkeypatch):
    """Through QAPI.call: authorised, whitelisted, pre-fills only (no core query runs), defaults to RECORDED."""
    sys.path.insert(0, str(REPO / 'tests/q1q5'))
    from test_api import TOKEN, api_fixture, authorize
    from amidst.q1q5.api import APIError
    monkeypatch.delenv('AMIDST_NL_PROVIDER', raising=False)
    monkeypatch.delenv('AMIDST_NL_RECORDING', raising=False)
    api, _ = api_fixture()
    row = api.bootstrap()['runs'][0]
    base = {'schema_version': nl.REQUEST_SCHEMA, 'session_ref': TOKEN, 'scene_id': row['scene_id'], 'run_id': row['run_id'], 'kind': 'track', 'text': '追蹤人'}
    r = api.call('q_nl_parse', base, authorize)
    assert r['schema_version'] == nl.RESPONSE_SCHEMA and r['executed'] is False and r['provider']['kind'] == 'RECORDED' and r['provider']['synthetic_fixture'] is True
    assert r['form']['classLabel'] == 'person' and r['fallback_reason'] == 'REPLAY_MISS'   # real catalog differs from the fixture's: honest fallback
    assert not api.responses, 'no response bundle stored: nothing was executed'
    for bad in ({**base, 'actor_id': 'x'}, {**base, 'extra': 1}, {**base, 'kind': 'other'}, {**base, 'run_id': 'NOPE'}):
        with pytest.raises(APIError):
            api.call('q_nl_parse', bad, authorize)
    with pytest.raises(APIError):
        api.call('q_nl_parse', {**base, 'session_ref': 'not-a-session'}, authorize)


def test_check_recording_script_detects_catalog_drift():
    import check_nl_recording as chk
    sentences = json.loads((REPO / 'configs/epicd/nl_sentences_v1.json').read_text(encoding='utf-8'))['sentences']
    rec = json.loads(nl.FIXTURE_RECORDING.read_text(encoding='utf-8'))
    ok, report = chk.check_recording(rec, CATALOG, sentences)
    assert ok and report['catalog_equal'] and report['missing'] == [] and report['entries'] == len(sentences)
    drifted = {**CATALOG, 'region_ids': CATALOG['region_ids'] + ['R9'], 'region_aliases': {**CATALOG['region_aliases'], 'R9': 'R9'}}
    ok, report = chk.check_recording(rec, drifted, sentences)
    assert not ok and report['catalog_equal'] is False and len(report['missing']) == len(sentences)
    assert chk.check_recording(rec, CATALOG, sentences + [{'id': 'SX', 'kind': 'search', 'text': '沒錄過的句子 人'}])[1]['missing'] == ['SX']


def _llm_literal(**o):
    base = {'schema_version': 'q-demo.q3-llm-output.v1', 'intent': 'FIND_PERSON', 'class_term': None, 'color_term': None,
            'time_literal': {'start': None, 'end': None, 'date': None}, 'camera_terms': [], 'region_terms': [],
            'needs_clarification': False, 'clarification_question': None}
    return json.dumps({**base, **o}, ensure_ascii=False)


class _Scripted:
    def __init__(self, text=None, exc=None, latency=1.0):
        self.text, self.exc, self.latency = text, exc, latency
        self.info = {**fixture().info, 'kind': 'OLLAMA', 'recorded': False, 'synthetic_fixture': False}

    def generate(self, **_):
        if self.exc:
            raise self.exc
        return CallResult(self.text, {'raw_output_sha256': None, 'stats': {'latency_ms': self.latency}})


def test_a_provider_failing_in_an_unexpected_way_degrades_to_rules_without_echoing_the_message():
    for exc in (OSError('/secret/path'), RuntimeError('Bearer ' + FAKE_KEY), ConnectionResetError('x')):
        r = parse('track', '追蹤紅衣服的人', provider=_Scripted(exc=exc))
        assert r['decided_by'] == 'RULE_FALLBACK' and r['fallback_reason'] == 'PROVIDER_UNAVAILABLE' and r['form']['colorLabel'] == 'red'
        assert '/secret/path' not in json.dumps(r) and FAKE_KEY not in json.dumps(r)


def test_an_answer_slower_than_the_total_budget_is_not_used():
    good = _llm_literal(class_term='人', color_term='紅')
    ok = parse('track', '追蹤紅衣服的人', provider=_Scripted(good, latency=14999.0))
    assert ok['decided_by'] == 'LLM' and ok['fallback_reason'] is None
    slow = parse('track', '追蹤紅衣服的人', provider=_Scripted(good, latency=15001.0))
    assert slow['decided_by'] == 'RULE_FALLBACK' and slow['fallback_reason'] == 'TIME_BUDGET'
    assert slow['trace']['steps'][0]['arguments'] is None and slow['form']['colorLabel'] == 'red'
    tight = parse('track', '追蹤紅衣服的人', provider=_Scripted(good, latency=500.0), budget={'total_budget_ms': 400})
    assert tight['fallback_reason'] == 'TIME_BUDGET'


def test_terms_not_in_the_sentence_never_reach_the_form():
    """The model copies words; the server builds menu values. A catalog label or a word the user never wrote is refused."""
    sentence = '追蹤的人'   # no colour word in the sentence
    for term in ({'class_term': '人', 'color_term': '紅'}, {'class_term': 'person'}, {'class_term': '人', 'color_term': 'red'},
                 {'class_term': '人', 'region_terms': ['SYNTHETIC_ROOM_A']}, {'class_term': '人', 'region_terms': ['合成區 A']}):
        r = parse('track', sentence, provider=_Scripted(_llm_literal(**term)))
        assert r['decided_by'] == 'RULE_FALLBACK' and r['fallback_reason'] == 'INVALID_RESPONSE', term
        assert r['form']['colorLabel'] == '' and r['form']['regionIds'] == [], term
    # a catalog label that the sentence really contains is a literal copy and is fine
    ok = parse('track', '追蹤 person', provider=_Scripted(_llm_literal(class_term='person')))
    assert ok['form']['classLabel'] == 'person'


def test_malformed_recording_is_a_replay_miss_not_a_crash():
    rec = json.loads(nl.FIXTURE_RECORDING.read_text(encoding='utf-8'))
    for broken in ({k: v for k, v in rec.items() if k != 'provider'}, {**rec, 'entries': [{'request': {}}]}, {**rec, 'entries': [1]}):
        broken['content_sha256'] = canonical_hash(broken, exclude=('content_sha256',))
        with pytest.raises(nl.ReplayMismatch):
            nl.RecordedNlProvider(broken)


def test_safe_default_provider_degrades_with_a_reason_instead_of_failing(tmp_path):
    for env, code in (({'AMIDST_NL_RECORDING': str(tmp_path / 'missing.json')}, 'PROVIDER_UNAVAILABLE'),
                      ({'AMIDST_NL_PROVIDER': 'NOPE'}, 'PROVIDER_UNAVAILABLE')):
        prov = nl.safe_default_provider(env)
        r = parse('track', '追蹤紅衣服的人', provider=prov)
        assert r['status'] == 'PARSED' and r['decided_by'] == 'RULE_FALLBACK' and r['fallback_reason'] == code
        assert r['form']['colorLabel'] == 'red' and r['executed'] is False
    bad = tmp_path / 'bad.json'
    bad.write_text('{"schema_version": "x"}', encoding='utf-8')
    assert parse('track', '追蹤紅衣服的人', provider=nl.safe_default_provider({'AMIDST_NL_RECORDING': str(bad)}))['fallback_reason'] == 'REPLAY_MISS'
    assert nl.safe_default_provider({}).kind == 'RECORDED' and nl.safe_default_provider({}).info['synthetic_fixture'] is True


def test_qapi_route_survives_a_broken_recording_path(monkeypatch, tmp_path):
    sys.path.insert(0, str(REPO / 'tests/q1q5'))
    from test_api import TOKEN, api_fixture, authorize
    monkeypatch.setenv('AMIDST_NL_RECORDING', str(tmp_path / 'missing.json'))
    api, _ = api_fixture()
    row = api.bootstrap()['runs'][0]
    r = api.call('q_nl_parse', {'schema_version': nl.REQUEST_SCHEMA, 'session_ref': TOKEN, 'scene_id': row['scene_id'], 'run_id': row['run_id'],
                                'kind': 'track', 'text': '追蹤人'}, authorize)
    assert r['decided_by'] == 'RULE_FALLBACK' and r['fallback_reason'] == 'PROVIDER_UNAVAILABLE' and r['form']['classLabel'] == 'person'
    monkeypatch.delenv('AMIDST_NL_RECORDING')   # a failed build is not cached: the next call recovers
    r2 = api.call('q_nl_parse', {'schema_version': nl.REQUEST_SCHEMA, 'session_ref': TOKEN, 'scene_id': row['scene_id'], 'run_id': row['run_id'],
                                 'kind': 'track', 'text': '追蹤人'}, authorize)
    assert r2['provider']['synthetic_fixture'] is True
