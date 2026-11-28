"""N1 gate: NL_QUERY_PARSE_V1 (docs/contracts/NL_QUERY_PARSE_V1.md). Fake clients only; no network, no key."""
from __future__ import annotations

import itertools
import json

import pytest

nlp = pytest.importorskip('amidst.q1q5.nl_query_parse')

CATALOG = {
    'scene_id': 'S', 'scene_revision': 'r1', 'run_id': 'R', 'class_labels': ['person', 'car'], 'color_labels': ['red', 'blue'],
    'camera_ids': ['A', 'B'], 'region_ids': ['R1', 'R2'], 'class_aliases': {'人': 'person', '車': 'car', 'person': 'person'},
    'color_aliases': {'紅': 'red', '藍': 'blue'}, 'camera_aliases': {}, 'region_aliases': {'西入口': 'R1', '東入口': 'R2'}, 'class_map_sha256': '0' * 64,
}
VOCAB = nlp.vocabulary_from_catalog(CATALOG)


def parse(text):
    return nlp.parse_rules(text, VOCAB)


def test_find_with_location_target_time():
    assert parse('查找紅衣的人 西入口 0:10 到 0:30') == {'action': '查找', 'location': ['R1'], 'target': ['person', 'red'], 'time': {'start': 10, 'end': 30}, 'unrecognized': []}


def test_track_sentence_from_the_brief():
    r = parse('追蹤紅衣的人 從西入口 0:10 到 0:30')
    assert r['action'] == '追蹤' and r['location'] == ['R1'] and r['target'] == ['person', 'red'] and r['time'] == {'start': 10, 'end': 30}


def test_no_action_cue_is_null_not_guessed():
    assert parse('藍色的車')['action'] is None


def test_time_forms():
    assert parse('找人 1:02:03 到 1:02:30')['time'] == {'start': 3723, 'end': 3750}
    assert parse('找人 10秒到30秒')['time'] == {'start': 10, 'end': 30}


def test_single_time_is_not_a_range():
    r = parse('找人 0:10')
    assert r['time'] is None and '0:10' in r['unrecognized']


def test_reversed_range_is_unrecognized_not_swapped():
    r = parse('找人 0:30 到 0:10')
    assert r['time'] is None


def test_mixed_known_and_unknown():
    r = parse('追蹤戴眼鏡的人 西入口')
    assert r['action'] == '追蹤' and r['location'] == ['R1'] and r['target'] == ['person'] and r['unrecognized'] == ['戴眼鏡']


def test_unrecognized_only():
    r = parse('今天天氣如何')
    assert r['target'] == [] and r['location'] == [] and r['time'] is None and r['unrecognized']


def test_pure_function_is_deterministic_and_has_exact_keys():
    assert parse('找人') == parse('找人') and set(parse('找人')) == {'action', 'location', 'target', 'time', 'unrecognized'}


@pytest.mark.parametrize('bad', [
    {'action': '查找', 'location': ['R9'], 'target': [], 'time': None, 'unrecognized': []},
    {'action': '查找', 'location': [], 'target': ['dog'], 'time': None, 'unrecognized': []},
    {'action': 'search', 'location': [], 'target': [], 'time': None, 'unrecognized': []},
    {'action': '查找', 'location': [], 'target': [], 'time': {'start': 5, 'end': 2}, 'unrecognized': []},
    {'action': '查找', 'location': [], 'target': [], 'time': {'start': True, 'end': 9}, 'unrecognized': []},
    {'action': '查找', 'location': [], 'target': [], 'time': None},
    {'action': '查找', 'location': [], 'target': [], 'time': None, 'unrecognized': [], 'extra': 1},
    {'action': '查找', 'location': ['R1', 'R1'], 'target': [], 'time': None, 'unrecognized': []},
])
def test_schema_rejects_values_outside_vocabulary_or_shape(bad):
    with pytest.raises(nlp.NlSchemaError):
        nlp.validate_parse(bad, VOCAB)


def test_schema_accepts_good():
    good = {'action': None, 'location': ['R2'], 'target': ['car', 'blue'], 'time': {'start': 0, 'end': 1.5}, 'unrecognized': ['x']}
    assert nlp.validate_parse(good, VOCAB) == good


class Fake:
    def __init__(self, name, result=None, error=None, tokens=(10, 5), cost=None):
        self.name, self.result, self.error, self.tokens, self.cost, self.calls = name, result, error, tokens, cost, 0

    def parse(self, text, vocab, timeout_ms):
        self.calls += 1
        if self.error:
            raise self.error
        return nlp.ClientResult(self.result, *self.tokens, self.cost)


GOOD = {'action': '追蹤', 'location': ['R2'], 'target': ['person'], 'time': None, 'unrecognized': []}


def run(mode, **clients):
    return nlp.parse_nl_query('追蹤人 東入口', VOCAB, mode=mode, **clients)


def test_rules_mode_never_calls_clients():
    api = Fake('API', GOOD)
    r = run('RULES', api=api)
    assert r['parser'] == 'RULES' and api.calls == 0 and r['cost_usd'] == 0.0 and r['latency_ms'] >= 0 and r['schema_version'] == 'q-demo.nl-query-parse.v1'


def test_api_success_records_parser_and_cost():
    r = run('API', api=Fake('API', GOOD, cost=0.0004), local=Fake('LOCAL', GOOD))
    assert r['parser'] == 'API' and r['cost_usd'] == 0.0004 and r['location'] == ['R2'] and [t['parser'] for t in r['fallback_trail']] == ['API']


def test_absolute_clock_requires_mapping_only_when_rules_produce_the_answer():
    text = '找人 14:00:00 到 14:00:20'
    for mode in ('RULES', 'LOCAL'):
        with pytest.raises(nlp.ClockMappingError) as exc:
            nlp.parse_nl_query(text, VOCAB, mode=mode)
        assert exc.value.code == 'CLOCK_MAPPING_MISSING'
    answer = dict(GOOD, time={'start': 3, 'end': 8})
    for mode, client_key in [('API', 'api'), ('LOCAL', 'local')]:
        client = Fake(mode, answer)
        result = nlp.parse_nl_query(text, VOCAB, mode=mode, **{client_key: client})
        assert result['parser'] == mode and result['time'] == answer['time'] and client.calls == 1


def test_api_timeout_falls_to_local_then_rules():
    local = Fake('LOCAL', GOOD)
    r = run('API', api=Fake('API', error=nlp.NlClientError('TIMEOUT')), local=local)
    assert r['parser'] == 'LOCAL' and [(t['parser'], t['outcome']) for t in r['fallback_trail']] == [('API', 'TIMEOUT'), ('LOCAL', 'OK')]
    r = run('API', api=Fake('API', error=nlp.NlClientError('TIMEOUT')), local=Fake('LOCAL', error=nlp.NlClientError('UNAVAILABLE')))
    assert r['parser'] == 'RULES' and r['fallback_trail'][-1]['outcome'] == 'OK' and r['location'] == ['R2']


def test_schema_violation_drops_to_next_layer():
    bad = dict(GOOD, location=['R9'])
    r = run('API', api=Fake('API', bad), local=Fake('LOCAL', GOOD))
    assert r['parser'] == 'LOCAL' and r['fallback_trail'][0]['outcome'] == 'SCHEMA_REJECTED'


def test_not_configured_layers_are_skipped():
    r = run('API')
    assert r['parser'] == 'RULES' and [t['outcome'] for t in r['fallback_trail']] == ['NOT_CONFIGURED', 'NOT_CONFIGURED', 'OK']


def test_local_mode_skips_api():
    api = Fake('API', GOOD)
    r = run('LOCAL', api=api, local=Fake('LOCAL', GOOD))
    assert r['parser'] == 'LOCAL' and api.calls == 0


def test_unknown_cost_is_null_and_local_is_zero():
    assert run('API', api=Fake('API', GOOD, cost=None))['cost_usd'] is None
    assert run('LOCAL', local=Fake('LOCAL', GOOD, cost=0.0))['cost_usd'] == 0.0


def test_slow_layer_counts_as_timeout():
    ticks = itertools.chain([0.0, 0.0, 5.0], itertools.repeat(5.0))
    r = nlp.parse_nl_query('找人', VOCAB, mode='API', api=Fake('API', GOOD), timeout_ms=2500, clock=lambda: next(ticks))
    assert r['fallback_trail'][0]['outcome'] == 'TIMEOUT' and r['parser'] == 'RULES'


def test_bad_text_rejected():
    for t in ['', '   ', 'x' * 201, None, 3]:
        with pytest.raises(ValueError):
            nlp.parse_nl_query(t, VOCAB)


def test_openai_client_uses_server_key_and_fake_transport():
    seen = {}

    def transport(*, url, headers, body, timeout_s, method='POST'):
        seen.update(url=url, auth=headers.get('Authorization'), body=json.loads(body), timeout=timeout_s)
        content = json.dumps(GOOD, ensure_ascii=False)
        return 200, json.dumps({'choices': [{'message': {'content': content}}], 'usage': {'prompt_tokens': 100, 'completion_tokens': 20}}).encode()

    c = nlp.OpenAINlClient(model='astra6', transport=transport, env={'OPENAI_API_KEY': 'sk-test-FAKE'},
                           prices={'astra6': {'input_usd_per_mtok': 1.0, 'output_usd_per_mtok': 2.0}})
    res = c.parse('追蹤人 東入口', VOCAB, 2500)
    assert res.parsed == GOOD and seen['auth'] == 'Bearer sk-test-FAKE' and seen['timeout'] == 2.5
    assert res.cost_usd == pytest.approx((100 * 1.0 + 20 * 2.0) / 1e6)
    schema = seen['body']['response_format']['json_schema']['schema']
    assert schema['properties']['location']['items']['enum'] == ['R1', 'R2'] and 'sk-test' not in json.dumps(seen['body'])


def test_openai_without_key_is_not_configured_and_never_calls():
    called = []
    c = nlp.OpenAINlClient(model='astra6', transport=lambda **k: called.append(1), env={})
    with pytest.raises(nlp.NlClientError) as e:
        c.parse('找人', VOCAB, 2500)
    assert e.value.code == 'NOT_CONFIGURED' and not called


def test_openai_model_must_be_known():
    with pytest.raises(ValueError):
        nlp.OpenAINlClient(model='gpt-unknown', env={})


def test_ollama_client_fake_transport_and_loopback_only():
    def transport(*, url, headers, body, timeout_s, method='POST'):
        assert url == 'http://127.0.0.1:11434/api/chat'
        return 200, json.dumps({'message': {'content': json.dumps(GOOD, ensure_ascii=False)}, 'prompt_eval_count': 7, 'eval_count': 3}).encode()
    r = nlp.OllamaNlClient(model='qwen3:8b', transport=transport).parse('找人', VOCAB, 3000)
    assert r.parsed == GOOD and r.cost_usd == 0.0
    with pytest.raises(Exception):
        nlp.OllamaNlClient(model='qwen3:8b', endpoint='http://example.com:11434')


def test_client_timeout_exception_maps_to_timeout():
    def transport(**k):
        raise TimeoutError()
    with pytest.raises(nlp.NlClientError) as e:
        nlp.OllamaNlClient(model='qwen3:8b', transport=transport).parse('找人', VOCAB, 3000)
    assert e.value.code == 'TIMEOUT'


def test_recorder_failure_never_breaks_parse():
    def transport(**k):
        return 200, json.dumps({'choices': [{'message': {'content': json.dumps(GOOD)}}]}).encode()

    def recorder(row):
        raise RuntimeError('disk')
    c = nlp.OpenAINlClient(model='astra6', transport=transport, env={'OPENAI_API_KEY': 'k'}, recorder=recorder)
    assert c.parse('找人', VOCAB, 2500).parsed == GOOD


def test_replay_client_answers_from_recording():
    rows = []
    def transport(**k):
        return 200, json.dumps({'choices': [{'message': {'content': json.dumps(GOOD)}}]}).encode()
    nlp.OpenAINlClient(model='astra6', transport=transport, env={'OPENAI_API_KEY': 'k'}, recorder=rows.append).parse('找人', VOCAB, 2500)
    assert 'OPENAI_API_KEY' not in json.dumps(rows) and rows[0]['request_sha256']
    replay = nlp.ReplayNlClient('API', rows)
    assert replay.parse('找人', VOCAB, 2500).parsed == GOOD
    with pytest.raises(nlp.NlClientError):
        replay.parse('別的句子', VOCAB, 2500)


def test_huge_time_is_unrecognized_not_a_window_and_never_raises():
    for text in ('追蹤 0:10 到 ' + '9' * 150 + '秒', '找 0秒 到 ' + '9' * 190 + '秒'):
        out = nlp.parse_nl_query(text[:200], VOCAB)
        assert out['time'] is None and out['parser'] == 'RULES'
    with pytest.raises(nlp.NlSchemaError):
        nlp.validate_parse({'action': None, 'location': [], 'target': [], 'time': {'start': 0, 'end': 1e150}, 'unrecognized': []}, VOCAB)
