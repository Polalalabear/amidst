"""#601: recorded-mode OpenAI Agent through the file-queue gateway. SYNTHETIC inputs, fake model, no network, no socket."""
import json
import socket
from dataclasses import replace

import pytest
from test_api import TOKEN, authorize, q2, run_binding
from test_q5_agent import auto
from test_q5_controller import seed_id

from amidst.q1q5 import openai_gateway as og
from amidst.q1q5.api import QAPI
from amidst.q1q5.api_budget import LEDGER_NAME as og_ledger_name, ApiGuard, GuardConfig
from amidst.q1q5.llm_provider import ProviderError

SECRET = 'sk-TEST-NOT-A-REAL-KEY'
PRICES = {og.API_MODEL: {'input_usd_per_mtok': 1.0, 'output_usd_per_mtok': 5.0}}


class Clock:
    """Fake wall + monotonic clock; ``sleep`` can also drive the gateway so the polling loop runs without threads."""
    def __init__(self, on_sleep=None):
        self.t, self.on_sleep = 1000.0, on_sleep

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s
        if self.on_sleep:
            self.on_sleep()


def guard(tmp_path, **kw):
    cfg = dict(enabled=True, max_usd_total=1.0, max_usd_per_day=1.0, max_usd_per_call=0.05, prices=PRICES)
    cfg.update(kw)
    return ApiGuard(GuardConfig(**cfg), usage_dir=tmp_path / 'ledger')


def fake_call(log=None, text=None):
    n = [0]

    def call(system, user, api_model, max_out, timeout_s, env, schema=None):
        n[0] += 1
        if not env.get('OPENAI_API_KEY'):
            raise PermissionError('NO_API_KEY')   # what openai_chat does without a key
        if log is not None:
            log.append((system, user, api_model, max_out, timeout_s, schema))
        out = text if text is not None else json.dumps(auto(json.loads(user), n[0]))
        return out, 300, 60, api_model
    return call


def wire(tmp_path, *, call=None, env=None, clock=None, **guard_kw):
    queue = tmp_path / 'queue'
    worker = og.GatewayWorker(queue, guard(tmp_path, **guard_kw), call=call or fake_call(), env={'OPENAI_API_KEY': SECRET} if env is None else env,
                              wall=clock or Clock())
    clock = clock or worker.wall
    worker.write_status()
    provider = og.GatewayProvider(queue, clock=clock, wall=clock, sleep=lambda s: (setattr(clock, 't', clock.t + s), worker.process_once()), poll_s=0.01)
    return queue, worker, provider


def agent_run(provider):
    run = run_binding(agent=True)
    return og.bind_openai_agent([run], provider.queue_dir, provider=provider)[0]


def select(run):
    api = QAPI([run], max_responses=128, max_media_refs=4096)
    q = q2(run)
    q['switch_mode'] = 'AGENT_SEQUENTIAL'
    return api, api.call('q2_select_seed', {'request': q, 'selected_observation_id': seed_id(run.bindings)}, authorize)


# ---- default off ------------------------------------------------------------------------------------------------------
def test_default_off_leaves_runs_untouched(tmp_path):
    run = run_binding()
    assert og.configure_environment([run], tmp_path, env={}) == (run,)
    assert og.configure_environment([run], tmp_path, env={og.ENV_SWITCH: 'off'}) == (run,)
    b = QAPI([run], max_responses=8, max_media_refs=8).bootstrap()['runs'][0]
    assert b['agent_available'] is False and 'agent_unavailable_reason' not in b


def test_unknown_switch_value_is_an_error_not_a_silent_noop(tmp_path):
    with pytest.raises(ValueError):
        og.configure_environment([run_binding()], tmp_path, env={og.ENV_SWITCH: 'yes'})


def test_switch_binds_every_run_with_the_gateway_factory(tmp_path):
    runs = [run_binding(), run_binding(agent=True)]
    bound = og.configure_environment(runs, tmp_path, env={og.ENV_SWITCH: 'openai'})
    assert len(bound) == 2 and all(isinstance(r.agent_factory, og.GatewayAgentFactory) for r in bound)
    assert bound[0].agent_factory.settings.model == og.API_MODEL == 'gpt-6.1-terra'
    assert bound[0].agent_factory.settings.template_version == 'q5-agent-v2'


# ---- availability and visible reasons ---------------------------------------------------------------------------------
@pytest.mark.parametrize('setup,reason', [
    (lambda q, w, c: (q / 'status.json').unlink(), 'GATEWAY_OFFLINE'),
    (lambda q, w, c: setattr(c, 't', c.t + 60), 'GATEWAY_OFFLINE'),
    (None, 'GUARD_NOT_APPROVED'), (None, 'NO_API_KEY'), (None, None)])
def test_bootstrap_availability_and_reason(tmp_path, setup, reason):
    kw = {'max_usd_total': 0.0} if reason == 'GUARD_NOT_APPROVED' else {}
    env = {} if reason == 'NO_API_KEY' else None
    clock = Clock()
    queue, worker, provider = wire(tmp_path, env=env, clock=clock, **kw)
    if setup:
        setup(queue, worker, clock)
    b = QAPI([agent_run(provider)], max_responses=8, max_media_refs=8).bootstrap()['runs'][0]
    assert b['agent_available'] is (reason is None)
    assert b.get('agent_unavailable_reason') == reason


def test_status_file_carries_booleans_never_the_key(tmp_path):
    queue, worker, _ = wire(tmp_path)
    text = (queue / 'status.json').read_text()
    assert SECRET not in text and json.loads(text)['key_present'] is True


# ---- the real flow (fake model) ---------------------------------------------------------------------------------------
def test_agent_decides_through_the_gateway_with_audit_record_and_no_socket(tmp_path, monkeypatch):
    log = []
    _, worker, provider = wire(tmp_path, call=fake_call(log))
    monkeypatch.setattr(socket.socket, 'connect', lambda *a, **k: (_ for _ in ()).throw(AssertionError('socket.connect in the demo process')))
    api, result = select(agent_run(provider))
    assert result['agent_used'] and not result['fallback_used'] and result['fallback_reason'] is None
    assert log and all(x[2] == og.API_MODEL and x[3] <= og.MAX_OUTPUT_TOKENS for x in log)
    assert len(log) <= 3   # agent_max_rounds
    rows = [json.loads(line) for line in (tmp_path / 'ledger' / og_ledger_name).read_text().splitlines()] if (tmp_path / 'ledger' / og_ledger_name).exists() else []
    assert rows and all(r['caller'] == 'recorded_agent' and r['outcome'] == 'OK' for r in rows)
    blob = json.dumps(result) + ''.join((tmp_path / 'queue' / d).as_posix() for d in ('requests', 'responses'))
    assert SECRET not in blob
    assert not list((tmp_path / 'queue' / 'requests').glob('*.json')) and not list((tmp_path / 'queue' / 'responses').glob('*.json'))


def test_no_key_at_call_time_falls_back_to_rules_with_reason(tmp_path):
    _, worker, provider = wire(tmp_path)
    run = agent_run(provider)
    worker.env.pop('OPENAI_API_KEY')   # key disappears after the heartbeat: the call itself is refused
    _, result = select(run)
    assert result['fallback_used'] and result['fallback_reason'] == 'MODE_NOT_AUTHORIZED' and not result['agent_used']
    assert not (tmp_path / 'ledger' / og_ledger_name).exists()   # a keyless attempt is not charged


def test_apiguard_denial_falls_back_to_rules_with_reason(tmp_path):
    _, worker, provider = wire(tmp_path, max_usd_per_call=0.0000001)   # PER_CALL_COST_CAP: the call is denied before any request
    _, result = select(agent_run(provider))
    assert result['fallback_used'] and result['fallback_reason'] == 'MODE_NOT_AUTHORIZED' and not result['agent_used']


def test_gateway_offline_during_run_falls_back(tmp_path):
    queue, worker, provider = wire(tmp_path)
    run = agent_run(provider)
    (queue / 'status.json').unlink()
    _, result = select(run)
    assert result['fallback_used'] and result['fallback_reason'] == 'PROVIDER_UNAVAILABLE'


def test_timeout_falls_back_and_removes_the_request(tmp_path):
    clock = Clock()
    queue = tmp_path / 'queue'
    worker = og.GatewayWorker(queue, guard(tmp_path), call=fake_call(), env={'OPENAI_API_KEY': SECRET}, wall=clock)
    worker.write_status()
    provider = og.GatewayProvider(queue, clock=clock, wall=clock, sleep=clock.sleep, poll_s=0.5)   # gateway never serves
    _, result = select(agent_run(provider))
    assert result['fallback_used'] and result['fallback_reason'] == 'PROVIDER_TIMEOUT'
    assert not list((queue / 'requests').glob('*.json'))


def test_reply_after_the_deadline_is_a_timeout_and_leaves_no_orphan(tmp_path):
    clock = Clock()

    def slow(system, user, api_model, max_out, timeout_s, env, schema=None):
        clock.t += 5   # the model answers 5 s later; the per-call budget is 2 s
        return json.dumps(auto(json.loads(user), 1)), 10, 10, api_model
    queue, worker, provider = wire(tmp_path, call=slow, clock=clock)
    _, result = select(agent_run(provider))
    assert result['fallback_used'] and result['fallback_reason'] == 'PROVIDER_TIMEOUT'
    assert not list((queue / 'responses').glob('*.json'))


def test_bad_model_text_falls_back_invalid_response(tmp_path):
    _, _, provider = wire(tmp_path, call=fake_call(text='not json'))
    _, result = select(agent_run(provider))
    assert result['fallback_used'] and result['fallback_reason'] == 'INVALID_RESPONSE'


# ---- worker/provider input boundary -----------------------------------------------------------------------------------
def test_provider_refuses_local_paths_in_the_prompt(tmp_path):
    _, _, provider = wire(tmp_path)
    with pytest.raises(ValueError):
        provider.generate(model=og.API_MODEL, prompt='T\n{"x":"/Users/someone/secret"}', template='T', template_version='q5-agent-v2',
                          options={}, timeout_ms=1000)


def test_worker_rejects_bad_requests_without_calling_the_model(tmp_path):
    log = []
    queue, worker, _ = wire(tmp_path, call=fake_call(log))
    base = {'schema_version': 'q-demo.agent-gateway-request.v1', 'id': 'a' * 16, 'model': og.API_MODEL, 'system': 's', 'user': 'u',
            'max_output_tokens': 64, 'deadline_unix': worker.wall() + 5}
    for i, change in enumerate([{'model': 'gpt-6-astra'}, {'user': 'see /Users/x/gt.json'}, {'max_output_tokens': 4096}, {'system': ''}, {'deadline_unix': 'soon'}]):
        rid = f'{i:02d}' + 'b' * 14
        og._write_json(queue / 'requests' / f'{rid}.json', {**base, **change, 'id': rid})
    (queue / 'requests' / 'garbage.json').write_text('{')
    assert worker.process_once() == 6 and log == []
    assert not list((queue / 'requests').glob('*.json'))


def test_stale_request_spends_nothing(tmp_path):
    log = []
    queue, worker, _ = wire(tmp_path, call=fake_call(log))
    og._write_json(queue / 'requests' / ('c' * 16 + '.json'), {'schema_version': 'q-demo.agent-gateway-request.v1', 'id': 'c' * 16,
        'model': og.API_MODEL, 'system': 's', 'user': 'u', 'max_output_tokens': 64, 'deadline_unix': worker.wall() - 1})
    worker.process_once()
    assert log == [] and not (tmp_path / 'ledger' / og_ledger_name).exists()


def test_agent_input_is_only_the_controller_payload_no_gt_fields(tmp_path):
    log = []
    _, _, provider = wire(tmp_path, call=fake_call(log))
    select(agent_run(provider))
    sent = ' '.join(x[0] + x[1] for x in log).lower()
    for forbidden in ('ground_truth', 'gt_private', 'renderer', 'visibility', 'trajectory', '/users/', '/private/'):
        assert forbidden not in sent


# ---- parameters -------------------------------------------------------------------------------------------------------
def test_missing_agent_parameters_are_added_with_the_approved_values_and_resealed():
    run = run_binding()
    names = {p['name'] for p in run.bindings.parameter_set['parameters']}
    stripped_ps = {**run.bindings.parameter_set, 'parameters': [p for p in run.bindings.parameter_set['parameters'] if not p['name'].startswith(('agent_', 'session_max_agent'))]}
    from amidst.q1q5.store import canonical_hash
    stripped_ps['content_sha256'] = canonical_hash(stripped_ps, exclude=('content_sha256', 'stats', 'graph_id', 'parameter_set_id', 'index_id'))
    stripped_ps['parameter_set_id'] = 'pset:q-demo:' + stripped_ps['content_sha256'][:16]
    stripped = replace(run, bindings=replace(run.bindings, parameter_set=stripped_ps, parameter_sha256=stripped_ps['content_sha256']))
    fixed = og.ensure_agent_parameters(stripped)
    rows = {p['name']: p for p in fixed.bindings.parameter_set['parameters']}
    assert all(rows[n]['status'] == 'APPROVED' for n, *_ in og.AGENT_PARAMETERS) and rows['agent_call_timeout_ms']['value'] == 2000
    assert fixed.bindings.parameter_sha256 == fixed.bindings.parameter_set['content_sha256'] == fixed.parse_settings.parameter_set_sha256
    assert fixed.parse_settings.parameter_set_id == fixed.bindings.parameter_set['parameter_set_id'] != stripped.parse_settings.parameter_set_id
    assert og.ensure_agent_parameters(fixed) == fixed   # idempotent
    assert names  # sanity: the source run had parameters


def test_provider_error_type_is_what_agent_controller_catches(tmp_path):
    queue, _, provider = wire(tmp_path)
    (queue / 'status.json').unlink()
    with pytest.raises(ProviderError) as exc:
        provider.generate(model=og.API_MODEL, prompt='T\n{}', template='T', template_version='q5-agent-v2', options={}, timeout_ms=1000)
    assert exc.value.code == 'PROVIDER_UNAVAILABLE' and exc.value.record['validation_errors'] == ['GATEWAY_OFFLINE']


# ---- guided schema, unwrap, operator budgets --------------------------------------------------------------------------
def test_q5_requests_carry_the_wrapped_guided_schema_and_the_worker_passes_it_on(tmp_path):
    log = []
    _, _, provider = wire(tmp_path, call=fake_call(log))
    select(agent_run(provider))
    schema = log[0][5]
    assert schema['type'] == 'object' and schema['required'] == ['output'] and schema['additionalProperties'] is False and 'output' in schema['properties']


def test_openai_chat_sends_json_schema_with_bearer_key_and_unwraps_output(monkeypatch):
    seen = {}

    def transport(*, url, headers, body, timeout_s, method='POST'):
        seen.update(url=url, headers=headers, body=json.loads(body), timeout_s=timeout_s)
        reply = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'output': {'b': 1, 'a': [2]}})}}],
                 'usage': {'prompt_tokens': 11, 'completion_tokens': 7}, 'model': 'gpt-6.1-terra-2026'}
        return 200, json.dumps(reply).encode()
    monkeypatch.setattr('amidst.q1q5.agent_providers.default_http_transport', transport)
    schema = og.wrap_schema({'type': 'object'})
    text, pt, ct, served = og.openai_chat('SYS JSON', 'USER', og.API_MODEL, 64, 5.0, {'OPENAI_API_KEY': SECRET}, schema)
    assert json.loads(text) == {'a': [2], 'b': 1} and (pt, ct, served) == (11, 7, 'gpt-6.1-terra-2026')
    assert seen['body']['response_format'] == {'type': 'json_schema', 'json_schema': {'name': 'q5_decision', 'strict': True, 'schema': schema}}
    assert seen['body']['max_completion_tokens'] == 64 and seen['headers']['Authorization'] == 'Bearer ' + SECRET
    with pytest.raises(PermissionError):
        og.openai_chat('s', 'u', og.API_MODEL, 64, 5.0, {}, None)


def test_operator_budget_override_is_explicit_visible_and_validated(tmp_path):
    runs = [run_binding(agent=True)]
    assert og.configure_environment(runs, tmp_path, env={og.ENV_SWITCH: 'openai'})[0].bindings.parameter_sha256 == runs[0].bindings.parameter_sha256   # unset = approved values
    env = {og.ENV_SWITCH: 'openai', 'AMIDST_RECORDED_AGENT_CALL_TIMEOUT_MS': '8000', 'AMIDST_RECORDED_AGENT_TOTAL_BUDGET_MS': '20000'}
    bound = og.configure_environment(runs, tmp_path, env=env)[0]
    rows = {p['name']: p for p in bound.bindings.parameter_set['parameters']}
    assert rows['agent_call_timeout_ms']['value'] == 8000 and rows['agent_total_budget_ms']['value'] == 20000
    assert rows['agent_call_timeout_ms']['proposal_ref'] == og.OVERRIDE_REF and bound.bindings.parameter_sha256 != runs[0].bindings.parameter_sha256
    assert bound.parse_settings.parameter_set_sha256 == bound.bindings.parameter_sha256
    for bad in ('0', '-5', 'abc', '999999'):
        with pytest.raises(ValueError):
            og.configure_environment(runs, tmp_path, env={og.ENV_SWITCH: 'openai', 'AMIDST_RECORDED_AGENT_CALL_TIMEOUT_MS': bad})


def test_strictify_gives_const_and_enum_an_explicit_type():
    out = og.strictify({'anyOf': [{'properties': {'a': {'const': 'X'}, 'b': {'const': None}, 'c': {'enum': ['p', 'q']}, 'd': {'enum': [None, 'p']},
                                                  'e': {'type': 'array', 'items': {'enum': ['r']}, 'maxItems': 1}, 'f': {'type': 'array', 'maxItems': 0}}}]})
    p = out['anyOf'][0]['properties']
    assert p['a'] == {'type': 'string', 'enum': ['X']} and p['b'] == {'type': 'null', 'enum': [None]} and p['c'] == {'type': 'string', 'enum': ['p', 'q']}
    assert p['d']['type'] == ['null', 'string'] and p['e']['items'] == {'type': 'string', 'enum': ['r']} and p['f']['items'] == {'type': 'string'}
