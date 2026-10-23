"""Explicit, file-pinned Qwen wiring. No model discovery, pulls or startup calls."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import re
import stat
import time

from amidst.q1q5.llm_provider import OllamaProvider, LocalHTTPTransport, CallResult, ProviderError, generation_request, QWEN3_MODEL, NATIVE_PROTOCOL
from amidst.q1q5.q5_agent import AgentController, AgentSettings
from amidst.q1q5.store import canonical_hash, _json, _safe_content


class RuntimeConfigError(ValueError):
    code = 'DataIntegrityError'


def require(ok, message):
    if not ok:
        raise RuntimeConfigError(message)


def load_config(path, expected_file_sha256):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path, 'Canonical runtime path required')
    require(isinstance(expected_file_sha256, str) and re.fullmatch('[0-9a-f]{64}', expected_file_sha256), 'Independent runtime file pin required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_size <= 2_097_152, 'Invalid runtime file')
        raw = b''
        while len(raw) <= 2_097_152:
            chunk = os.read(fd, min(65536, 2_097_153 - len(raw)))
            if not chunk:
                break
            raw += chunk
        require(len(raw) == info.st_size and hashlib.sha256(raw).hexdigest() == expected_file_sha256, 'Runtime file pin mismatch')
    finally:
        os.close(fd)
    return validate_config(_json(raw))


def validate_config(config):
    fields = {'schema_version', 'applies_to', 'base_url', 'model', 'model_digest', 'options',
              'q3_template', 'q5_template', 'agent_authorization_ref', 'enable_q3', 'enable_q5', 'content_sha256'}
    require(isinstance(config, dict) and set(config) == fields and config['schema_version'] == 'q-demo.ollama-runtime.v1', 'Runtime schema mismatch')
    require(config['content_sha256'] == canonical_hash(config, exclude=('content_sha256',)), 'Runtime content hash mismatch')
    require(config['model'] == QWEN3_MODEL, 'Only explicitly selected Qwen3-1.7B is enabled')
    require(isinstance(config['model_digest'], str) and re.fullmatch('[0-9a-f]{64}', config['model_digest']), 'Model digest required')
    require(type(config['enable_q3']) is bool and type(config['enable_q5']) is bool, 'Explicit capability flags required')
    scope = config['applies_to']
    require(isinstance(scope, dict) and set(scope) == {'scene_id', 'scene_revision', 'run_id', 'detection_index_sha256', 'parameter_set_sha256', 'clock_mapping_sha256'}, 'Runtime source scope required')
    require(all(isinstance(x, str) and x for x in scope.values()), 'Runtime scope must be complete')
    LocalHTTPTransport(config['base_url'])  # validates loopback, performs no HTTP
    for name in ('q3_template', 'q5_template'):
        template = config[name]
        require(isinstance(template, dict) and set(template) == {'text', 'sha256', 'version'} and isinstance(template['text'], str)
                and template['text'] and template['sha256'] == hashlib.sha256(template['text'].encode()).hexdigest()
                and isinstance(template['version'], str) and template['version'], 'Prompt template pin mismatch')
    require(config['q3_template']['version'] == 'q3-parse.v1', 'Unsupported Q3 template version')
    AgentSettings(config['model'], config['model_digest'], config['options'], config['q5_template']['text'],
                  config['q5_template']['sha256'], config['q5_template']['version'], config['agent_authorization_ref'])
    _safe_content(config)
    return deepcopy(config)


class SourceIntervalScheduler:
    """Pace calls within a SEARCHING episode; uses existing interval, no defaults."""
    def __init__(self, *, clock=time.monotonic, sleep=time.sleep):
        self.clock, self.sleep = clock, sleep
        self.last = None
        self.episode = None

    def __call__(self, episode, rounds_used, interval_us):
        require(type(interval_us) is int and interval_us > 0, 'Explicit source interval required')
        if self.episode == episode and self.last is not None:
            wait = self.last + interval_us / 1_000_000 - self.clock()
            if wait > 0:
                self.sleep(wait)
        self.episode = episode
        self.last = self.clock()


def bind_runs(runs, config, *, provider_factory=None, scheduler_factory=SourceIntervalScheduler):
    config = validate_config(config)
    scope = config['applies_to']
    matches = []
    for i, run in enumerate(runs):
        b = run.bindings
        manifest = b.index.manifest
        if (manifest['scene_id'], manifest['run_id']) == (scope['scene_id'], scope['run_id']):
            actual = {'scene_id': manifest['scene_id'], 'scene_revision': manifest['scene_revision'], 'run_id': manifest['run_id'],
                      'detection_index_sha256': b.index_sha256, 'parameter_set_sha256': b.parameter_sha256, 'clock_mapping_sha256': b.clock_sha256}
            require(actual == scope, 'Runtime source binding mismatch')
            matches.append(i)
    require(len(matches) == 1, 'Runtime must bind exactly one registered run')
    provider = (provider_factory or (lambda url: OllamaProvider(LocalHTTPTransport(url))))(config['base_url'])
    result = list(runs)
    index = matches[0]
    run = result[index]
    q3 = {}
    if config['enable_q3']:
        require(run.parse_settings.q3_max_llm_attempts is not None and run.parse_settings.q3_llm_timeout_ms is not None, 'Explicit Q3 bounds required')
        q3 = {'provider': provider, 'prompt_template': config['q3_template']['text'], 'model': config['model'],
              'options': deepcopy(config['options']), 'expected_digest': config['model_digest']}
    agent_factory = None
    if config['enable_q5']:
        settings = AgentSettings(config['model'], config['model_digest'], deepcopy(config['options']), config['q5_template']['text'],
                                 config['q5_template']['sha256'], config['q5_template']['version'], config['agent_authorization_ref'])
        def agent_factory(request, **kwargs):
            return AgentController(request, provider=provider, agent_settings=settings,
                                   round_scheduler=scheduler_factory(), **kwargs)
    result[index] = replace(run, q3_options=q3, agent_factory=agent_factory)
    return tuple(result)


def configure_environment(runs):
    path = os.environ.get('AMIDST_Q1Q5_OLLAMA_RUNTIME')
    pin = os.environ.get('AMIDST_Q1Q5_OLLAMA_RUNTIME_SHA256')
    if not path and not pin:
        return runs
    require(path and pin, 'Both runtime path and independent file SHA-256 are required')
    return bind_runs(runs, load_config(path, pin))


class RecordedParseProvider:
    """Exact Q3 provider audit replay; task validation remains in parse_query."""
    def __init__(self, audit, *, expected_sha256):
        require(isinstance(audit, (tuple, list)) and canonical_hash(audit) == expected_sha256, 'Q3 audit pin mismatch')
        self.audit = deepcopy(audit)
        self.cursor = 0

    def generate(self, **request):
        require(self.cursor < len(self.audit), 'Q3 replay exhausted')
        row = self.audit[self.cursor]['provider_record']
        path, payload = generation_request(request['model'], request['prompt'], request['template'], request['options'])
        if path == '/api/chat':
            require(row.get('protocol') == NATIVE_PROTOCOL and row.get('wire_request') == payload, 'Q3 native replay protocol mismatch')
        else:
            require('protocol' not in row and 'wire_request' not in row, 'Q3 legacy replay protocol mismatch')
        require(row['content_sha256'] == canonical_hash(row, exclude=('content_sha256', 'stats'))
                and row['input_sha256'] == canonical_hash(payload) and row['timeout_ms'] == request['timeout_ms']
                and row['prompt_template_sha256'] == hashlib.sha256(request['template'].encode()).hexdigest()
                and row['prompt_template_version'] == request['template_version']
                and (request.get('expected_digest') is None or row['model_digest'] in {None, request['expected_digest']}), 'Q3 replay input/audit mismatch')
        self.cursor += 1
        if row['validation'] != 'PROVIDER_VALIDATED':
            raise ProviderError(row['validation'], deepcopy(row))
        require(request.get('expected_digest') is None or row['model_digest'] == request['expected_digest'], 'Q3 replay success digest mismatch')
        require(isinstance(row['raw_output'], str) and hashlib.sha256(row['raw_output'].encode()).hexdigest() == row['raw_output_sha256'], 'Q3 replay output mismatch')
        return CallResult(row['raw_output'], deepcopy(row))

    def assert_consumed(self):
        require(self.cursor == len(self.audit), 'Q3 replay left unused calls')
