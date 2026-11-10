"""SYNTHETIC native-chat comparison; never activated by product runtime.

Explicit diagnostic bounds and sampling apply only to cloned mechanical bindings.
No downloads, images, formal questions/answers, or changes to production settings.
"""
import argparse
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request

from amidst.q1q5.llm_provider import LocalHTTPTransport, CallResult, ProviderError, _object
from amidst.q1q5.store import canonical_hash, _safe_content

MODELS = {'qwen2.5:7b-instruct', 'qwen3:1.7b-q4_K_M', 'qwen3:4b-instruct-2507-q4_K_M'}
TOOL_TYPES = '\nExact tool argument keys: get_search_context(session_id,decision_id); get_candidate_evidence(session_id,decision_id,candidate_ref); get_observation_summary(session_id,observation_id). Copy references from returned context; no additional keys.\n'


def require(ok, message):
    if not ok:
        raise ValueError(message)


class ChatTransport(LocalHTTPTransport):
    def request(self, method, path, payload, timeout_s):
        require((method, path) in {('GET', '/api/tags'), ('GET', '/api/ps'), ('POST', '/api/chat'), ('POST', '/api/generate')}, 'Unsupported benchmark operation')
        raw_payload = None if payload is None else json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
        req = Request(self.base_url + path, data=raw_payload, method=method, headers={'Content-Type': 'application/json'})
        with self.opener.open(req, timeout=timeout_s) as response:
            raw = response.read(self.max_response_bytes + 1)
        require(len(raw) <= self.max_response_bytes, 'Oversized response')
        return raw


def messages(prompt, template):
    require(prompt.startswith(template + '\n'), 'Template framing mismatch')
    suffix = prompt[len(template) + 1:]
    if suffix.startswith('CLOSED_CATALOG='):
        catalog, text = suffix.split('\nUSER_TEXT=', 1)
        _safe_content(_object(catalog[len('CLOSED_CATALOG='):].encode()))
        value = json.loads(text)
        require(isinstance(value, str), 'Q3 user text must be literal text')
        result = [{'role': 'system', 'content': template + '\n' + catalog}, {'role': 'user', 'content': value}]
    else:
        _safe_content(_object(suffix.encode()))
        result = [{'role': 'system', 'content': template}, {'role': 'user', 'content': suffix}]
    _safe_content(result)
    return result


def metadata(transport, path, timeout_s):
    result = _object(transport.request('GET', path, None, timeout_s))
    require(isinstance(result.get('models'), list) and all(isinstance(x, dict) for x in result['models']), 'Malformed inventory')
    return result['models']


def verify_owner(transport, model, digest, timeout_s, *, allow_empty=True):
    tags = metadata(transport, '/api/tags', timeout_s)
    found = [x for x in tags if x.get('name') == model or x.get('model') == model]
    require(len(found) == 1 and found[0].get('digest') == digest, 'Model digest mismatch')
    active = metadata(transport, '/api/ps', timeout_s)
    require((allow_empty or bool(active)) and all((x.get('name') == model or x.get('model') == model) and x.get('digest') == digest for x in active), 'Shared model ownership mismatch')


class NativeChatProvider:
    def __init__(self, transport, *, context_tokens, token_cap, clock=time.monotonic):
        require(type(context_tokens) is int and context_tokens == 4096 and type(token_cap) is int and 1 <= token_cap <= 256, 'Explicit bounded benchmark context/token cap required')
        self.transport, self.context_tokens, self.token_cap, self.clock = transport, context_tokens, token_cap, clock
        self.events = []

    def generate(self, **args):
        require(args['model'] in MODELS, 'Model is outside comparison allowlist')
        require(isinstance(args['expected_digest'], str) and len(args['expected_digest']) == 64 and all(c in '0123456789abcdef' for c in args['expected_digest']), 'Independent model pin required')
        require(type(args['timeout_ms']) is int and 0 < args['timeout_ms'] <= 30000, 'Invalid diagnostic call bound')
        _safe_content({'prompt': args['prompt'], 'template': args['template']})
        payload = {'model': args['model'], 'messages': messages(args['prompt'], args['template']), 'stream': False, 'format': 'json',
                   'options': {**args['options'], 'num_ctx': self.context_tokens, 'num_predict': self.token_cap}, 'keep_alive': '60s'}
        if args['model'] == 'qwen3:1.7b-q4_K_M':
            payload['think'] = False
        start = self.clock()
        record = {'model': args['model'], 'model_digest': None, 'prompt': args['prompt'], 'prompt_sha256': hashlib.sha256(args['prompt'].encode()).hexdigest(),
            'prompt_template_version': args['template_version'], 'prompt_template_sha256': hashlib.sha256(args['template'].encode()).hexdigest(),
            'sampling': args['options'], 'input_sha256': canonical_hash(payload), 'caller_request_sha256': canonical_hash(args),
            'protocol': 'q-demo.native-chat-benchmark.v1', 'wire_request': payload, 'raw_output': None, 'raw_output_sha256': None,
            'response_body_sha256': None, 'validation': 'NOT_RUN', 'validation_errors': [], 'timeout_ms': args['timeout_ms'], 'timed_out': False}
        envelope = None

        def remaining():
            value = args['timeout_ms'] / 1000 - (self.clock() - start)
            if value <= 0:
                raise TimeoutError()
            return value

        def finish(code):
            row = deepcopy(record)
            row['validation'] = code
            row['stats'] = {'latency_ms': max(0, (self.clock() - start) * 1000)}
            row['content_sha256'] = canonical_hash(row, exclude=('stats',))
            self.events.append({'request': deepcopy(args), 'record': row, 'envelope': envelope})
            return row

        try:
            verify_owner(self.transport, args['model'], args['expected_digest'], remaining())
            record['model_digest'] = args['expected_digest']
            raw = self.transport.request('POST', '/api/chat', payload, remaining())
            remaining()
            record['response_body_sha256'] = hashlib.sha256(raw).hexdigest()
            envelope = _object(raw)
            value = envelope.get('message')
            require(envelope.get('model') == args['model'] and envelope.get('done') is True and envelope.get('done_reason') == 'stop'
                    and 'error' not in envelope and isinstance(value, dict) and value.get('role') == 'assistant'
                    and isinstance(value.get('content'), str) and value['content'].strip() and not value.get('thinking') and not value.get('tool_calls'), 'Invalid or truncated native-chat envelope')
            record['raw_output'] = value['content']
            record['raw_output_sha256'] = hashlib.sha256(value['content'].encode()).hexdigest()
            verify_owner(self.transport, args['model'], args['expected_digest'], remaining(), allow_empty=False)
            remaining()
        except Exception as error:
            if isinstance(error, TimeoutError) or isinstance(error, URLError) and isinstance(error.reason, TimeoutError):
                code = 'PROVIDER_TIMEOUT';record['timed_out'] = True
            elif isinstance(error, (HTTPError, URLError, OSError, ConnectionError)):
                code = 'PROVIDER_UNAVAILABLE'
            elif isinstance(error, (ValueError, TypeError, UnicodeError)):
                code = 'INVALID_RESPONSE'
            else:
                raise
            record['validation_errors'] = [code]
            raise ProviderError(code, finish(code)) from None
        return CallResult(record['raw_output'], finish('PROVIDER_VALIDATED'))


class ReplayChatProvider:
    def __init__(self, events, *, expected_sha256):
        require(canonical_hash(events) == expected_sha256, 'Replay audit pin mismatch')
        self.events, self.cursor = deepcopy(events), 0

    def generate(self, **args):
        require(self.cursor < len(self.events), 'Replay exhausted')
        event = self.events[self.cursor];record = event['record']
        require(args == event['request'] and canonical_hash(args) == record['caller_request_sha256']
                and record['content_sha256'] == canonical_hash(record, exclude=('stats', 'content_sha256')), 'Replay request/audit mismatch')
        self.cursor += 1
        if record['validation'] != 'PROVIDER_VALIDATED':
            raise ProviderError(record['validation'], deepcopy(record))
        require(hashlib.sha256(record['raw_output'].encode()).hexdigest() == record['raw_output_sha256'], 'Replay output mismatch')
        return CallResult(record['raw_output'], deepcopy(record))

    def assert_consumed(self):
        require(self.cursor == len(self.events), 'Unused replay events')


def diagnostic_run(run, *, call_ms, total_ms):
    require(run.source_kind == 'SYNTHETIC' and run.catalog['scene_id'] == 'SYNTHETIC_SCENE', 'Only built-in mechanical run is allowed')
    require(type(call_ms) is int and 0 < call_ms <= 30000 and type(total_ms) is int and call_ms <= total_ms <= 90000, 'Explicit diagnostic bounds required')
    b = run.bindings;p = deepcopy(b.parameter_set)
    overrides = {'agent_call_timeout_ms': call_ms, 'agent_total_budget_ms': total_ms, 'research_interval_us': 1000000, 'q3_llm_timeout_ms': call_ms, 'q3_max_llm_attempts': 1}
    for item in p['parameters']:
        if item['name'] in overrides:
            item['value'] = overrides[item['name']]
    p['content_sha256'] = canonical_hash(p, exclude=('content_sha256', 'parameter_set_id'))
    p['parameter_set_id'] = 'pset:q-demo:' + p['content_sha256'][:16]
    b = replace(b, parameter_set=p, parameter_sha256=p['content_sha256'])
    settings = replace(run.parse_settings, parameter_set_id=p['parameter_set_id'], parameter_set_sha256=p['content_sha256'], q3_llm_timeout_ms=call_ms, q3_max_llm_attempts=1)
    return replace(run, bindings=b, parse_settings=settings), overrides


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--synthetic', action='store_true', required=True)
    p.add_argument('--model', required=True, choices=sorted(MODELS))
    p.add_argument('--model-digest', required=True)
    p.add_argument('--base-url', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--repeats', type=int, required=True, choices=range(1, 4))
    p.add_argument('--call-timeout-ms', type=int, required=True)
    p.add_argument('--total-timeout-ms', type=int, required=True)
    args = p.parse_args()
    require(len(args.model_digest) == 64 and all(c in '0123456789abcdef' for c in args.model_digest), 'Pinned model digest required')
    require(args.output.is_absolute() and args.output.resolve() == args.output and not args.output.exists() and args.output.parent.is_dir(), 'New canonical artifact directory required')
    root = Path(__file__).resolve().parents[1];sys.path.insert(0, str(root / 'tests/q1q5'))
    from test_api import run_binding, q2, TOKEN, seed_id
    from amidst.q1q5.q3_parse import parse_query
    from amidst.q1q5.q5_agent import AgentController, AgentSettings, RecordedProvider
    from amidst.q1q5.q4_evidence import candidate_evidence
    from amidst.q1q5.ollama_runtime import SourceIntervalScheduler
    run, overrides = diagnostic_run(run_binding(agent=True), call_ms=args.call_timeout_ms, total_ms=args.total_timeout_ms)
    args.output.mkdir(mode=0o700)

    def save(name, value):
        fd = os.open(args.output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2);handle.write('\n')

    def disk(tag):
        raw = subprocess.check_output(['df', '-k', str(args.output)], text=True)
        (args.output / ('df-' + tag + '.txt')).write_text(raw)
        require(int(raw.splitlines()[-1].split()[3]) >= 8 * 1024 * 1024, 'STOP_BELOW_8_GIB')

    transport = ChatTransport(args.base_url);summaries=[]
    disk('before')
    loaded_by_this_run = False
    try:
        require(metadata(transport, '/api/ps', 3) == [], 'Shared runner must be idle before benchmark load')
        verify_owner(transport, args.model, args.model_digest, 3)
        load_start = time.monotonic()
        loaded_by_this_run = True
        load = _object(transport.request('POST', '/api/generate', {'model': args.model, 'prompt': '', 'stream': False, 'keep_alive': '60s'}, 30))
        require(load.get('done_reason') == 'load' and load.get('response') == '' and load.get('done') is True, 'Model preload failed')
        verify_owner(transport, args.model, args.model_digest, 3, allow_empty=False)
        save('load.json', {'latency_ms': (time.monotonic() - load_start) * 1000, 'envelope': load, 'management_only': True})
        save('protocol.json', {'diagnostic_only': True, 'counts_for_acceptance': False, 'model': args.model, 'model_digest': args.model_digest,
            'protocol': 'native-chat-json.v1', 'context_tokens': 4096, 'token_cap': 256, 'repeat_seeds': list(range(7, 7 + args.repeats)),
            'diagnostic_overrides_on_cloned_synthetic_bindings': overrides, 'product_settings_changed': False, 'rt_detr_concurrent': False,
            'rule_only_baseline': 'retained in prior source; no model calls', 'not_comparable_as_model_only_change_to_historical_raw': True})
        for i in range(args.repeats):
            for task in ('q3', 'q5'):
                name = task + '-' + str(i);disk(name + '-before')
                provider = NativeChatProvider(transport, context_tokens=4096, token_cap=256)
                options = {'temperature': 0.7, 'top_p': 0.8, 'top_k': 20, 'seed': 7 + i}
                template = (root / 'configs/q1q5/prompts' / (task + ('_parse_v1.txt' if task == 'q3' else '_agent_v1.txt'))).read_text()
                started = time.monotonic()
                if task == 'q3':
                    request = {'schema_version': 'q-demo.q3-parse-request.v1', 'session_ref': TOKEN, 'text': '車13:00:00到13:00:01', 'locale': 'zh-TW',
                        'context': {'scene_id': run.catalog['scene_id'], 'run_ids': [run.catalog['run_id']], 'clock_mapping_sha256': run.bindings.clock_sha256}, 'parser_mode': 'LLM_WITH_RULE_FALLBACK'}
                    kwargs = dict(catalog=run.catalog, settings=run.parse_settings, clock_mapping=run.bindings.clock, prompt_template=template, model=args.model, options=options, expected_digest=args.model_digest)
                    response, audit = parse_query(request, provider=provider, **kwargs)
                    live_ms = (time.monotonic() - started) * 1000
                    replay = ReplayChatProvider(provider.events, expected_sha256=canonical_hash(provider.events))
                    repeated, _ = parse_query(request, provider=replay, **kwargs);replay.assert_consumed();require(response == repeated, 'Q3 replay mismatch')
                    extra = {'literal_parser_accepted': response['status'] == 'PARSED' and response['llm_parse_used'], 'task_audit': audit}
                else:
                    template += TOOL_TYPES
                    settings = AgentSettings(args.model, args.model_digest, options, template, hashlib.sha256(template.encode()).hexdigest(), 'q5-native-bench-v1', 'SYNTHETIC_DIAGNOSTIC_ONLY')
                    request = q2(run);request['switch_mode'] = 'AGENT_SEQUENTIAL';b = run.bindings
                    common = dict(bindings=b, evidence_provider=lambda idx, snapshot, ref, context:candidate_evidence(idx, snapshot, ref, **context), selected_observation_id=seed_id(b), agent_settings=settings)
                    controller = AgentController(request, provider=provider, round_scheduler=SourceIntervalScheduler(), **common)
                    result = controller.run();response = result.response;trace = controller.trace()
                    live_ms = (time.monotonic() - started) * 1000
                    replay = RecordedProvider(trace, expected_sha256=trace['content_sha256'])
                    repeated = AgentController(request, provider=replay, clock=replay.clock, round_scheduler=lambda *x:None, **common).run();replay.assert_consumed()
                    require(result.decisions_bytes == repeated.decisions_bytes and result.links_bytes == repeated.links_bytes and response['output_sha256'] == repeated.response['output_sha256'], 'Q5 replay mismatch')
                    decisions = [json.loads(x) for x in result.decisions_bytes.splitlines()]
                    extra = {'legal_agent_decision_used': response['agent_used'], 'switches': sum(x['executed_action'] == 'SWITCH' for x in decisions),
                        'rejected_decisions': sum(not x['accepted'] for x in decisions), 'trace': trace, 'decisions': decisions, 'links': result.links_bytes.decode()}
                elapsed = (time.monotonic() - started) * 1000
                # Replay time is small but kept separate from provider calls; no claim of live latency from replay.
                call_ms = [x['record']['stats']['latency_ms'] for x in provider.events]
                summary = {'task': task, 'repeat': i, 'seed': 7 + i, 'diagnostic_only': True, 'counts_for_acceptance': False,
                    'live_elapsed_ms': live_ms, 'replay_elapsed_ms': elapsed - live_ms, 'provider_latency_ms': call_ms, 'provider_calls': len(call_ms), 'status': response['status'],
                    'fallback_used': response['fallback_used'], 'fallback_reason': response['fallback_reason'], 'replay_equal': True,
                    'q3_llm_parse_used': response.get('llm_parse_used'), 'q5_agent_used': response.get('agent_used'),
                    'all_calls_within_2000ms_observed': bool(call_ms) and all(ms <= 2000 for ms in call_ms),
                    'live_under_5000ms_observed': live_ms <= 5000}
                save(name + '.json', {'summary': summary, 'request': request, 'response': response, 'provider_events': provider.events, **extra})
                summaries.append(summary);print(json.dumps(summary), flush=True);disk(name + '-after')
        save('REPORT.json', {'diagnostic_only': True, 'counts_for_acceptance': False, 'model': args.model, 'model_digest': args.model_digest, 'trials': summaries})
    finally:
        # Release only the model loaded by this run, after a fresh ownership check.
        try:
            if loaded_by_this_run:
                active = metadata(transport, '/api/ps', 3)
                if active:
                    verify_owner(transport, args.model, args.model_digest, 3, allow_empty=False)
                    released = _object(transport.request('POST', '/api/generate', {'model': args.model, 'prompt': '', 'stream': False, 'keep_alive': 0}, 10))
                    save('release.json', {'owned_memory_only': True, 'envelope': released, 'running_after': metadata(transport, '/api/ps', 3)})
        finally:
            disk('after')


if __name__ == '__main__':
    main()
