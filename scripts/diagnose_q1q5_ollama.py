"""Explicit local load/timing diagnosis; never used by product startup or inference.

Inputs are independently pinned SYNTHETIC API probe bundles. Longer timing calls
are labelled diagnostic-only; their outputs cannot replace a domain response.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.request import Request

from amidst.q1q5.api import QAPI, regular
from amidst.q1q5.llm_provider import LocalHTTPTransport, OllamaProvider, ProviderError, _object, generation_request, NATIVE_PROTOCOL, GUIDED_PROTOCOL
from amidst.q1q5.q3_parse import validate_literal_output
from amidst.q1q5.store import canonical_hash


MODELS = {'qwen3:1.7b-q4_K_M', 'qwen2.5:7b-instruct', 'qwen2.5:7b'}  # legacy pins remain readable


def require(ok, message):
    if not ok:
        raise ValueError(message)


def model_pin(model, digest):
    require(model in MODELS and isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'Explicit local Qwen pin required')


class DiagnosticTransport(LocalHTTPTransport):
    """Adds read-only running-model metadata; keeps inherited loopback/no-proxy policy."""
    def __init__(self, base_url):
        super().__init__(base_url)
        self.envelopes = []

    def request(self, method, path, payload, timeout_s):
        if (method, path) == ('GET', '/api/ps'):
            require(payload is None, 'No metadata payload')
            with self.opener.open(Request(self.base_url + path, method='GET'), timeout=timeout_s) as response:
                raw = response.read(self.max_response_bytes + 1)
            require(len(raw) <= self.max_response_bytes, 'Metadata response too large')
        else:
            raw = super().request(method, path, payload, timeout_s)
        if method == 'POST' and path in {'/api/generate', '/api/chat'}:
            self.envelopes.append(_object(raw))
        return raw


def inventory(transport, path, timeout_s):
    doc = _object(transport.request('GET', path, None, timeout_s))
    require(isinstance(doc.get('models'), list) and all(isinstance(x, dict) for x in doc['models']), 'Invalid model metadata')
    return doc['models']


def verify_local(transport, model, digest, timeout_s):
    model_pin(model, digest)
    matches = [x for x in inventory(transport, '/api/tags', timeout_s) if x.get('name') == model or x.get('model') == model]
    require(len(matches) == 1 and matches[0].get('digest') == digest, 'Local model digest mismatch')


def preload_model(transport, *, model, digest, timeout_ms, keep_alive_seconds, clock=time.monotonic):
    """Explicit management-only request, bounded separately from task budgets."""
    model_pin(model, digest)
    require(type(timeout_ms) is int and 0 < timeout_ms <= 30000, 'Management timeout must be 1..30000 ms')
    require(type(keep_alive_seconds) is int and 0 < keep_alive_seconds <= 300, 'Explicit keep-alive must be 1..300 seconds')
    start = clock()

    def remaining():
        value = timeout_ms / 1000 - (clock() - start)
        if value <= 0:
            raise TimeoutError('Management deadline exceeded')
        return value

    verify_local(transport, model, digest, remaining())
    active = inventory(transport, '/api/ps', remaining())
    require(all((x.get('name') == model or x.get('model') == model) and x.get('digest') == digest for x in active), 'Shared service has another active model; yield')
    sent = False
    if not active:
        payload = {'model': model, 'prompt': '', 'stream': False, 'keep_alive': str(keep_alive_seconds) + 's'}
        response = _object(transport.request('POST', '/api/generate', payload, remaining()))
        remaining()
        require(response.get('model') == model and response.get('done') is True and response.get('response') == ''
                and response.get('done_reason') == 'load' and 'error' not in response, 'Invalid preload response')
        sent = True
        verify_local(transport, model, digest, remaining())
        active = inventory(transport, '/api/ps', remaining())
        require(len(active) == 1 and active[0].get('digest') == digest
                and (active[0].get('name') == model or active[0].get('model') == model), 'Preload not observed in running inventory')
    remaining()
    return {'status': 'LOADED_OBSERVED', 'management_only': True, 'preload_request_sent': sent,
            'timeout_ms': timeout_ms, 'keep_alive_seconds': keep_alive_seconds,
            'latency_ms': (clock() - start) * 1000, 'inference_budgets_changed': False, 'model_digest': digest}


def pinned_record(path, file_pin, kind, *, model, digest, template):
    model_pin(model, digest)
    require(isinstance(file_pin, str) and re.fullmatch('[0-9a-f]{64}', file_pin), 'Independent probe file pin required')
    raw = regular(Path(path), 2_097_152)
    require(hashlib.sha256(raw).hexdigest() == file_pin, 'Probe file pin mismatch')
    bundle = _object(raw)
    require(bundle.get('source_kind') == 'SYNTHETIC', 'Only SYNTHETIC probes may be diagnosed')
    QAPI(max_responses=1, max_media_refs=1)._verify_bundle(bundle)
    require(kind in {'q3', 'q5'}, 'Unsupported task')
    if kind == 'q3':
        require(bundle['response']['schema_version'] == 'q-demo.q3-parse-response.v1', 'Wrong probe kind')
        record = bundle['q3_provider_audit'][0]['provider_record']
    else:
        require(bundle['response']['schema_version'] == 'q-demo.q2-response.v1', 'Wrong probe kind')
        record = bundle['agent_trace']['events'][0]['record']
    path, payload = generation_request(model, record['prompt'], template, record['sampling'])
    if path == '/api/chat':
        require(record.get('protocol') == (GUIDED_PROTOCOL if isinstance(payload['format'],dict) else NATIVE_PROTOCOL) and record.get('wire_request') == payload, 'Probe native framing mismatch')
    require(record['content_sha256'] == canonical_hash(record, exclude=('content_sha256', 'stats'))
            and record['input_sha256'] == canonical_hash(payload) and record['model'] == model and record['model_digest'] == digest
            and record['prompt_template_sha256'] == hashlib.sha256(template.encode()).hexdigest(), 'Probe model/input/template mismatch')
    return bundle, record


def measure_record(transport, record, *, template, timeout_ms, text=None):
    require(type(timeout_ms) is int and 0 < timeout_ms <= 30000, 'Diagnostic timeout must be 1..30000 ms')
    before = len(transport.envelopes)
    try:
        result = OllamaProvider(transport).generate(model=record['model'], prompt=record['prompt'], template=template,
            template_version=record['prompt_template_version'], options=record['sampling'], timeout_ms=timeout_ms, expected_digest=record['model_digest'])
        actual = result.record
    except ProviderError as error:
        actual = error.record
    require(actual['input_sha256'] == record['input_sha256'], 'Diagnostic input drift')
    envelopes = transport.envelopes[before:]
    envelope = envelopes[-1] if envelopes else {}
    literal = None
    if text is not None and actual['validation'] == 'PROVIDER_VALIDATED':
        try:
            validate_literal_output(_object(actual['raw_output'].encode()), text)
            literal = 'VALID_LITERAL_SCHEMA_ONLY'
        except (ValueError, TypeError):
            literal = 'INVALID_LITERAL_SCHEMA_OR_SUBSTRING'
    report = {'diagnostic_only': True, 'production_or_evaluation_accepted': False, 'inference_budgets_changed': False,
              'diagnostic_timeout_ms': timeout_ms, 'source_probe_timeout_ms': record['timeout_ms'],
              'input_sha256_unchanged': True, 'validation': actual['validation'], 'latency_ms': actual['stats']['latency_ms'],
              'q3_literal_check': literal, 'q5_task_guard_executed': False,
              'metrics': {k: envelope.get(k) for k in ['done_reason', 'total_duration', 'load_duration', 'prompt_eval_count', 'prompt_eval_duration', 'eval_count', 'eval_duration']}}
    return report, actual, envelopes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--model', required=True, choices=sorted(MODELS))
    parser.add_argument('--model-digest', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preload', action='store_true')
    parser.add_argument('--preload-timeout-ms', type=int)
    parser.add_argument('--keep-alive-seconds', type=int)
    parser.add_argument('--measure-timeout-ms', type=int)
    for kind in ('q3', 'q5'):
        parser.add_argument('--' + kind + '-bundle', type=Path)
        parser.add_argument('--' + kind + '-bundle-sha256')
    args = parser.parse_args()
    if args.preload != (args.preload_timeout_ms is not None and args.keep_alive_seconds is not None):
        parser.error('Preload requires both explicit management bounds; no implicit preload')
    if not args.preload and (args.preload_timeout_ms is not None or args.keep_alive_seconds is not None):
        parser.error('Management bounds require --preload')
    if args.preload and (not 0 < args.preload_timeout_ms <= 30000 or not 0 < args.keep_alive_seconds <= 300):
        parser.error('Management bounds exceed the explicit diagnostic limits')
    if args.measure_timeout_ms is not None and not 0 < args.measure_timeout_ms <= 30000:
        parser.error('Measurement timeout must be 1..30000 ms')
    root = args.output
    if not root.is_absolute() or root.resolve() != root or root.exists() or not root.parent.is_dir():
        parser.error('New canonical output directory with existing parent required')
    transport = DiagnosticTransport(args.base_url)
    model_pin(args.model, args.model_digest)
    sources = {}
    for kind in ('q3', 'q5'):
        path, pin = getattr(args, kind + '_bundle'), getattr(args, kind + '_bundle_sha256')
        if (path is None) != (pin is None):
            parser.error('Each probe path requires an independent file pin')
        if path is not None:
            original_raw=regular(path,2_097_152)
            require(hashlib.sha256(original_raw).hexdigest()==pin,'Probe file pin mismatch')
            original = _object(original_raw)
            record = original['q3_provider_audit'][0]['provider_record'] if kind=='q3' else original['agent_trace']['events'][0]['record']
            version = record['prompt_template_version']
            names = {'q3-parse.v1':'q3_parse_v1.txt','q3-parse.v2':'q3_parse_v2.txt'} if kind=='q3' else {'q5-agent-v1':'q5_agent_v1.txt','q5-agent-v2':'q5_agent_v2.txt'}
            require(version in names,'Unsupported pinned template version')
            template = (Path(__file__).resolve().parents[1]/'configs/q1q5/prompts'/names[version]).read_text()
            bundle, record = pinned_record(path, pin, kind, model=args.model, digest=args.model_digest, template=template)
            sources[kind] = (bundle, record, template, pin)
    if args.measure_timeout_ms is not None and not sources:
        parser.error('Measurement requires a pinned SYNTHETIC probe')
    root.mkdir(mode=0o700)

    def save(name, value):
        fd = os.open(root / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n')

    def disk(tag):
        raw = subprocess.check_output(['df', '-k', str(root)], text=True)
        (root / ('df-' + tag + '.txt')).write_text(raw)
        require(int(raw.splitlines()[-1].split()[3]) >= 8 * 1024 * 1024, 'STOP_BELOW_8_GIB')

    disk('before')
    try:
        verify_local(transport, args.model, args.model_digest, 3)
        report = {'diagnostic_only': True, 'production_or_evaluation_accepted': False, 'inference_budgets_changed': False,
                  'running_before': inventory(transport, '/api/ps', 3), 'source_bundle_file_sha256': {k: v[3] for k, v in sources.items()}}
        if args.preload:
            report['preload'] = preload_model(transport, model=args.model, digest=args.model_digest,
                timeout_ms=args.preload_timeout_ms, keep_alive_seconds=args.keep_alive_seconds)
        if args.measure_timeout_ms is not None:
            report['measurements'] = {}
            for kind, (bundle, record, template, _) in sources.items():
                active = inventory(transport, '/api/ps', 3)
                require(all((x.get('name') == args.model or x.get('model') == args.model) and x.get('digest') == args.model_digest
                            for x in active), 'Shared service has another active model; yield before measurement')
                summary, actual, envelopes = measure_record(transport, record, template=template, timeout_ms=args.measure_timeout_ms,
                    text=bundle['request']['text'] if kind == 'q3' else None)
                save(kind + '-provider-audit.json', actual)
                save(kind + '-envelopes.json', envelopes)
                report['measurements'][kind] = summary
        report['running_after'] = inventory(transport, '/api/ps', 3)
        save('REPORT.json', report)
        print(json.dumps(report))
    except Exception as error:
        save('ERROR.json', {'exception_type': type(error).__name__, 'diagnostic_only': True, 'production_or_evaluation_accepted': False})
        raise
    finally:
        disk('after')


if __name__ == '__main__':
    main()
