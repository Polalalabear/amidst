"""WP5 live OpenAI arm (D237): the API id sent is the mapped one (never a config id like 'astra6'); terra is the default.
No network, no key (fake transports, fake env)."""
import importlib
import json

import pytest

wp5 = importlib.import_module('amidst.agent_eval.wp5')
runner = importlib.import_module('amidst.agent_eval.wp5_runner')
fake = importlib.import_module('amidst.agent_eval.wp5_fake')
ap = importlib.import_module('amidst.q1q5.agent_providers')
nlp = importlib.import_module('amidst.q1q5.nl_query_parse')

IDS = {'astra6': 'gpt-6-astra', 'sol6.1': 'gpt-6.1-sol', 'terra6.1': 'gpt-6.1-terra'}


def _cfg():
    return wp5.load_config()


@pytest.mark.parametrize('cid,api', IDS.items())
def test_runner_maps_config_id_to_api_id(cid, api):
    assert runner.api_model_id(_cfg(), cid) == api


def test_unmapped_model_is_refused():
    with pytest.raises(wp5.Wp5Error, match='API_MODEL_ID_UNMAPPED'):
        runner.api_model_id(_cfg(), 'nope')


@pytest.mark.parametrize('cid,api', IDS.items())
def test_decision_provider_sends_api_id(cid, api):
    sent = []

    def transport(*, url, headers, body=None, timeout_s=2.0, **kw):
        sent.append(json.loads(body))
        raise OSError('stop')  # the request payload is all we need

    prov = ap.OpenAIProvider(model=cid, api_model_id=runner.api_model_id(_cfg(), cid), transport=transport, env={'OPENAI_API_KEY': 'sk-test-FAKE'})
    try:
        prov.call(fake.dp1_request(0), timeout_ms=2000, max_output_tokens=300)
    except Exception:
        pass
    assert sent and sent[0]['model'] == api


@pytest.mark.parametrize('cid,api', IDS.items())
def test_nl_client_sends_api_id(cid, api):
    sent = []

    def transport(*, url, headers, body, timeout_s, method='POST'):
        sent.append(json.loads(body))
        raise OSError('stop')

    c = nlp.OpenAINlClient(model=cid, api_model_id=api, transport=transport, env={'OPENAI_API_KEY': 'sk-test-FAKE'})
    try:
        c.parse('找穿紅衣的人', nlp.vocabulary_from_catalog(fake.CATALOG), 3000)
    except Exception:
        pass
    assert sent and sent[0]['model'] == api


def test_default_openai_model_is_terra_on_arm_without_models():
    cfg = _cfg()
    assert cfg['default_openai_model'] == 'terra6.1'
    args = runner.build_parser().parse_args(['--set', 'pilot', '--out', 'x', '--arm', 'mac'])
    models, _ = runner._select(cfg, args)
    assert models == ['rule', 'terra6.1']
    args = runner.build_parser().parse_args(['--set', 'pilot', '--out', 'x', '--arm', 'mac', '--all-openai'])
    assert runner._select(cfg, args)[0] == ['rule', 'astra6', 'sol6.1', 'terra6.1']
    args = runner.build_parser().parse_args(['--set', 'pilot', '--out', 'x', '--arm', 'mac', '--models', 'sol6.1'])
    assert runner._select(cfg, args)[0] == ['sol6.1']


def test_price_table_is_pinned_and_matches_params_mapping():
    t = wp5.load_json(_cfg()['price_table_path'])
    assert t['status'] == 'PINNED' and t['date'] == '2026-11-15' and t['source'].startswith('https://developers.openai.com/')
    assert {k: v['api_model_id'] for k, v in t['models'].items()} == IDS
    assert {k: (v['input_usd_per_mtok'], v['output_usd_per_mtok']) for k, v in t['models'].items()} == {
        'astra6': (10.0, 50.0), 'sol6.1': (2.0, 10.0), 'terra6.1': (1.0, 5.0)}
