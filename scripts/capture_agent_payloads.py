#!/usr/bin/env python3
"""Capture the Agent/LLM request payloads the product would send, without any network call or API key.

Read-only audit tool for docs/engineering/AGENT_API_WIRING_AUDIT_20261120.md (issue #643).

* Every capture replaces the transport with a recorder: the real request builders run, nothing leaves the process.
* ``OPENAI_API_KEY`` is removed from the environment at start-up and a placeholder is used where code insists on one.
* Sockets are blocked while capturing, so a regression that tries to connect fails loudly.
* Images are never stored: they become ``{bytes, sha256, width, height, format}`` summaries.

Pure helpers (``redact_images``, ``scan_forbidden``, ``cache_report`` ...) need no data and are unit-tested.
The ``--root`` captures (A4-1, B4-1) need the owned demo package (AMIDST_DEMO_HOME) and the venv that runs 8785.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import io
import json
import os
import re
import socket
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA_URL = re.compile(r'^data:image/([a-z0-9.+-]+);base64,(.*)$', re.S)
LOCAL_PATH = re.compile(r'(/Users/|/home/|/private/|[A-Za-z]:\\\\)')
CACHE_MIN_TOKENS = 1024          # OpenAI automatic prompt caching applies from 1024 prompt tokens (documented provider behaviour)
LIVE_IMAGE_PAIR_TOKENS = 807     # measured by the LIVE adjudication probe (advisor.py EST_PROMPT_TOKENS comment)
PLACEHOLDER_KEY = 'capture-only-placeholder'


# ----------------------------------------------------------------------------- pure helpers
def sha256(data: bytes | str) -> str:
    return hashlib.sha256(data.encode() if isinstance(data, str) else data).hexdigest()


def image_summary(fmt: str, raw: bytes) -> dict:
    out = {'format': fmt, 'bytes': len(raw), 'sha256': sha256(raw), 'width': None, 'height': None}
    try:
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as im:
            out['width'], out['height'] = im.size
    except Exception:  # noqa: BLE001 - PIL missing or not an image: keep the bytes/hash summary
        pass
    return out


def redact_images(value):
    """Deep copy with every ``data:image/...;base64,`` string replaced by a size/hash/dimension summary."""
    if isinstance(value, str):
        m = DATA_URL.match(value)
        if m:
            return {'_image': image_summary(m.group(1), base64.b64decode(m.group(2)))}
        return value
    if isinstance(value, list):
        return [redact_images(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_images(v) for k, v in value.items()}
    return value


def find_images(value, path='$') -> list[dict]:
    out = []
    if isinstance(value, dict):
        if '_image' in value:
            out.append({'path': path, **value['_image']})
        for k, v in value.items():
            out += find_images(v, f'{path}.{k}')
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out += find_images(v, f'{path}[{i}]')
    return out


def _forbidden_keys() -> frozenset:
    from amidst.q1q5 import agent_decision as ad
    return ad.FORBIDDEN_KEYS


def scan_forbidden(value, path='$') -> list[str]:
    """Key paths that are GT / renderer / visibility / depth / identity fields, plus local file paths inside strings.

    Text payloads (a JSON string inside a message) are parsed so a field hidden in the prompt is still found."""
    bad, fk, prefix = [], _forbidden_keys(), ''.join(('gt', '_'))
    if isinstance(value, dict):
        for k, v in value.items():
            low = str(k).lower()
            if low in fk or low.startswith(prefix):
                bad.append(f'{path}.{k}')
            bad += scan_forbidden(v, f'{path}.{k}')
    elif isinstance(value, list):
        for i, v in enumerate(value):
            bad += scan_forbidden(v, f'{path}[{i}]')
    elif isinstance(value, str):
        if LOCAL_PATH.search(value):
            bad.append(f'{path}:LOCAL_PATH')
        if value[:1] in '{[':
            try:
                bad += scan_forbidden(json.loads(value), path + '<json>')
            except ValueError:
                pass
    return bad


def estimate_tokens(text: str) -> int:
    """Heuristic: ASCII ~4 chars/token, non-ASCII ~1 token/char. A planning number, not a tokenizer."""
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return ascii_chars // 4 + (len(text) - ascii_chars)


def message_texts(messages: list[dict]) -> list[str]:
    out = []
    for m in messages:
        c = m.get('content')
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, list):
            out.append(''.join(p.get('text', '') if p.get('type') == 'text' else f'[{p.get("type")}]' for p in c))
    return out


def common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b))
    i = 0
    while i < n and a[i] == b[i]:
        i += 1
    return i


def cache_report(body_a: dict, body_b: dict) -> dict:
    """How much of two consecutive requests' text is a shared prefix (what provider prompt caching can reuse)."""
    ta, tb = '\n'.join(message_texts(body_a['messages'])), '\n'.join(message_texts(body_b['messages']))
    n = common_prefix_len(ta, tb)
    return {'shared_prefix_chars': n, 'shared_prefix_est_tokens': estimate_tokens(ta[:n]),
            'request_a_est_tokens': estimate_tokens(ta), 'request_b_est_tokens': estimate_tokens(tb),
            'shared_fraction_of_a': round(n / max(1, len(ta)), 3),
            'cache_threshold_tokens': CACHE_MIN_TOKENS,
            'cacheable': estimate_tokens(ta[:n]) >= CACHE_MIN_TOKENS,
            'first_divergence_context': ta[max(0, n - 40):n + 60]}


def summarize_body(name: str, body: dict, *, endpoint: str, image_tokens: int = 0, extra: dict | None = None) -> dict:
    """One capture record: the redacted body plus the facts the audit tabulates."""
    red = redact_images(body)
    images = find_images(red)
    texts = message_texts(red['messages'])
    fmt = red.get('response_format') or {}
    schema = (fmt.get('json_schema') or {})
    text_tokens = sum(estimate_tokens(t) for t in texts)
    return {
        'name': name, 'endpoint': endpoint, 'model': red.get('model'),
        'roles': [m['role'] for m in red['messages']], 'message_chars': [len(t) for t in texts],
        'images': images, 'n_images': len(images),
        'response_format': {'type': fmt.get('type'), 'name': schema.get('name'), 'strict': schema.get('strict')},
        'max_completion_tokens': red.get('max_completion_tokens'), 'temperature': red.get('temperature'), 'seed': red.get('seed'),
        'est_text_tokens': text_tokens, 'est_image_tokens': image_tokens, 'est_prompt_tokens': text_tokens + image_tokens,
        'forbidden_field_hits': scan_forbidden(red), 'body_sha256': sha256(json.dumps(red, sort_keys=True, ensure_ascii=True)),
        **(extra or {}), 'body_redacted': red,
    }


@contextlib.contextmanager
def no_network():
    """Fail loudly if anything opens a socket; hide the real API key from the code under capture."""
    saved_key = os.environ.pop('OPENAI_API_KEY', None)
    real = socket.socket.connect

    def blocked(self, *a, **k):
        raise RuntimeError('NETWORK_FORBIDDEN: capture_agent_payloads makes no network calls')
    socket.socket.connect = blocked
    try:
        yield
    finally:
        socket.socket.connect = real
        if saved_key is not None:
            os.environ['OPENAI_API_KEY'] = saved_key


def write_evidence(out_dir: Path, captures: list[dict]) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for c in captures:
        p = out_dir / f'{c["name"]}.json'
        p.write_text(json.dumps(c, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
        written.append(p)
    sums = out_dir / 'SHA256SUMS'
    sums.write_text(''.join(f'{sha256(p.read_bytes())}  {p.name}\n' for p in sorted(written)), encoding='utf-8')
    return written + [sums]


# ----------------------------------------------------------------------------- recorders (no network)
class Recorder:
    """Transport stand-in: stores the request body and answers with a 503 so the caller takes its fallback path."""

    def __init__(self):
        self.bodies: list[dict] = []

    def __call__(self, *, url, headers, body, timeout_s, **_):
        self.bodies.append(json.loads(body))
        self.last_headers = sorted(headers)          # names only, never values
        self.last_timeout_s = timeout_s
        import urllib.error
        raise urllib.error.HTTPError(url, 503, 'capture-only', {}, io.BytesIO(b'{}'))


# ----------------------------------------------------------------------------- live adjudication (real builders, real image encoders)
def capture_live(pack_dir: Path, k: int = 2) -> list[dict]:
    """LIVE: OpenAIAdjudicator body from a real LIVE-pack image (reference crop + 960x540 frame with numbered boxes)."""
    import urllib.request
    from PIL import Image
    from amidst.live_mode import advisor as adv
    img = sorted((pack_dir / 'data' / 'img').glob('*_combined.jpg'))[0]
    frame_img = Image.open(img).convert('RGB')
    frame_img = frame_img.crop((frame_img.width - 960, 0, frame_img.width, frame_img.height))     # 960x540 camera frame
    ref = adv.crop_jpeg(frame_img, (400, 120, 520, 400))
    frame = adv.frame_jpeg(frame_img, [(100, 100, 220, 380), (600, 110, 720, 390)][:k])
    sent = {}

    def fake_urlopen(req, timeout=None):
        sent['body'] = json.loads(req.data)
        sent['timeout'] = timeout
        sent['header_names'] = sorted(req.headers)
        raise urllib.error.URLError('capture-only')
    import urllib.error
    saved = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    os.environ['OPENAI_API_KEY'] = PLACEHOLDER_KEY
    try:
        with contextlib.suppress(urllib.error.URLError):
            adv.OpenAIAdjudicator('sol6.1')(ref, frame, k, 5.0)
    finally:
        urllib.request.urlopen = saved
        os.environ.pop('OPENAI_API_KEY', None)
    rec = summarize_body('live_adjudication', sent['body'], endpoint=adv.URL, image_tokens=LIVE_IMAGE_PAIR_TOKENS, extra={
        'source_image': {'name': img.name, 'sha256': sha256(img.read_bytes())},
        'timeout_s': sent['timeout'], 'request_header_names': sent['header_names'],
        'guard_caller': 'live_adjudication', 'guard_est_prompt_tokens': adv.EST_PROMPT_TOKENS, 'guard_max_out': adv.MAX_OUT,
        'note': 'candidates are chosen by LiveDecider: people within gate_m (3.0 m) of the previous estimate, '
                'one camera, max_candidates=4, sorted left to right; the model sees pixels only.'})
    return [rec]


# ----------------------------------------------------------------------------- Q3 natural-language parse
def capture_q3(vocab, text: str = '找出有人的鏡頭') -> list[dict]:
    from amidst.q1q5 import nl_query_parse as nlp
    rec = Recorder()
    client = nlp.OpenAINlClient(model='astra6', transport=rec, env={'OPENAI_API_KEY': PLACEHOLDER_KEY}, max_output_tokens=400)
    with contextlib.suppress(Exception):
        client.parse(text, vocab, 5000)
    return [summarize_body('q3_nl_parse', rec.bodies[0], endpoint=nlp.ap.OPENAI_CHAT_URL, extra={
        'timeout_s': rec.last_timeout_s, 'request_header_names': rec.last_headers, 'model_field_note': 'config id sent when api_model_id is None'})]


# ----------------------------------------------------------------------------- DP1 / DP3 (associate() decider, offline eval path)
def capture_dp(app, key, params: dict, label: str) -> list[dict]:
    """DP1/DP3 requests extracted from one real run, wrapped by the real OpenAIProvider payload builder (no call)."""
    from amidst.agent_eval.question_bank import extract_requests_from_run
    from amidst.q1q5 import agent_providers as ap
    run = app.api.runs[key]
    b = run.bindings
    reqs, _ = extract_requests_from_run(app.cross[key], app.transitions, as_of_us=b.clock.duration_us, parameters=app.cross_params,
                                        clock_mapping_sha256=b.clock_sha256, params=params)
    provider = ap.OpenAIProvider(model=params['models'][0]['config_id'], params=params, env={'OPENAI_API_KEY': PLACEHOLDER_KEY})
    out, seen = [], set()
    for r in reqs:
        dp = r['decision_point']
        if dp in seen:
            continue
        seen.add(dp)
        body = provider._build_payload(r, max_output_tokens=params['per_call']['max_output_tokens'])
        out.append(summarize_body(f'dp_{label}_{dp.split("_")[0].lower()}', body, endpoint=ap.OPENAI_CHAT_URL, extra={
            'request_structured': r, 'n_requests_in_run': len(reqs), 'timeout_ms': params['per_call']['timeout_ms'],
            'retries_on_429_5xx': params['per_call']['max_retries_on_429_5xx'],
            'step_budget_ms': params['per_step']['budget_ms'],
            'candidates_in_request': len(r.get('candidates', [])),
            'graph_status': r['topology']['graph_status'], 'n_graph_edges': len(r['topology']['edges'])}))
    return out


# ----------------------------------------------------------------------------- Q5 controller via the 8785 recorded-agent gateway wire
class CapturingProvider:
    """``AgentController.provider``: records every ``generate(**args)`` and fails as 'unavailable' so the rule runs."""

    def __init__(self):
        self.calls: list[dict] = []

    def generate(self, **args):
        self.calls.append(args)
        raise RuntimeError('capture-only')


def capture_q5(app, key, label: str) -> list[dict]:
    """Q5 AgentController, first Agent round of a real A4-1 / B4-1 run, then the exact gateway wire and OpenAI body."""
    from dataclasses import replace
    from amidst.q1q5 import openai_gateway as gw
    from amidst.q1q5 import agent_providers as ap
    from amidst.q1q5.llm_guidance import Q5_MARKER, q5_schema
    from amidst.q1q5.q5_agent import AgentController
    run = gw.ensure_agent_parameters(app.api.runs[key])
    provider = CapturingProvider()
    settings = gw.load_settings()
    run = replace(run, agent_factory=lambda request, **kw: AgentController(
        request, provider=provider, agent_settings=settings, round_scheduler=lambda *a: None, **kw))
    app.api.runs[key] = run
    b = run.bindings
    request = {'schema_version': 'q-demo.q2-request.v1', 'session_ref': 'CAPTURE', 'scene_id': key[0], 'run_ids': [key[1]],
               'time': {'kind': 'SOURCE', 'run_id': key[1], 'range_us': [0, b.clock.duration_us]},
               'seed': {'kind': 'APPEARANCE', 'class_label': 'person', 'color': None},
               'switch_mode': 'AGENT_SEQUENTIAL', 'parameter_set_id': b.parameter_set['parameter_set_id']}
    err, resp = None, {}
    try:
        resp = app.api.call('q2_session', request, lambda *a, **k: None)
    except Exception as exc:  # noqa: BLE001
        err = f'{type(exc).__name__}: {exc}'
    out = []
    if not provider.calls:
        return [{'name': f'q5_{label}', 'error': err or 'NO_AGENT_CALL', 'q2_status': resp.get('status'), 'q2_reason': resp.get('reason'),
                 'q2_reasons': resp.get('reasons'), 'agent_attempted': resp.get('agent_attempted'),
                 'note': 'controller never reached the provider: the Agent was not asked on this run'}]
    args = provider.calls[0]
    template, prompt = args['template'], args['prompt']
    user = prompt[len(template) + 1:]
    wire = {'model': gw.API_MODEL, 'system': template, 'user': user, 'max_output_tokens': gw.MAX_OUTPUT_TOKENS}
    wire['schema'] = gw.wrap_schema(q5_schema(json.loads(user)))
    rec = Recorder()
    saved = ap.default_http_transport
    ap.default_http_transport = rec
    try:
        with contextlib.suppress(Exception):
            gw.openai_chat(wire['system'], wire['user'], wire['model'], wire['max_output_tokens'], 8.0,
                           {'OPENAI_API_KEY': PLACEHOLDER_KEY}, wire['schema'])
    finally:
        ap.default_http_transport = saved
    ctx = json.loads(user)
    second = provider.calls[1]['prompt'][len(template) + 1:] if len(provider.calls) > 1 else None
    out.append(summarize_body(f'q5_{label}', rec.bodies[0], endpoint=ap.OPENAI_CHAT_URL, extra={
        'n_provider_calls_before_fallback': len(provider.calls), 'timeout_ms': args['timeout_ms'], 'options_from_settings': args['options'],
        'options_sent_on_wire': ['max_output_tokens'], 'template_version': args['template_version'],
        'template_sha256': settings.template_sha256, 'payload_top_keys': sorted(ctx), 'context_keys': sorted(ctx['context']),
        'n_candidates': len(ctx['context'].get('candidates', [])) if isinstance(ctx['context'], dict) else None,
        'user_payload_prefix_marker': user[:80], 'controller_error': err,
        'agent_values': {k: v for k, v in run.bindings.parameter_set.items() if k.startswith('agent') or k == 'session_max_agent_rounds'},
        'second_round_available': second is not None}))
    if second is not None:
        out[0]['cache_vs_second_round'] = cache_report(
            {'messages': [{'role': 'system', 'content': template}, {'role': 'user', 'content': user}]},
            {'messages': [{'role': 'system', 'content': template}, {'role': 'user', 'content': second}]})
    return out


def capture_q5_fixture() -> list[dict]:
    """Q5 AgentController on the repo's SYNTHETIC two-camera test fixture, two rounds, then the exact gateway body.

    Used because A4-1/B4-1 on the 8785 pin cannot reach the Agent (TRACKING_SCOPE_MISSING); the payload SHAPE is the real one."""
    from dataclasses import replace  # noqa: F401
    sys.path.insert(0, str(REPO / 'tests' / 'q1q5'))
    import hashlib as _h
    import test_q5_agent as t
    from amidst.q1q5 import openai_gateway as gw
    from amidst.q1q5 import agent_providers as ap
    from amidst.q1q5.llm_guidance import q5_schema
    v2 = (REPO / gw.TEMPLATE_REL).read_text(encoding='utf-8')
    st = t.settings(template=v2, template_sha256=_h.sha256(v2.encode()).hexdigest(), template_version='q5-agent-v2')
    _, _, provider, _ = t.run_agent(agent_settings=st)
    reqs = provider.requests
    template = reqs[0]['template']
    users = [r['prompt'][len(template) + 1:] for r in reqs]
    out = []
    for i, user in enumerate(users[:2]):
        wire_schema = gw.wrap_schema(q5_schema(json.loads(user)))
        rec = Recorder()
        saved = ap.default_http_transport
        ap.default_http_transport = rec
        try:
            with contextlib.suppress(Exception):
                gw.openai_chat(template, user, gw.API_MODEL, gw.MAX_OUTPUT_TOKENS, 8.0, {'OPENAI_API_KEY': PLACEHOLDER_KEY}, wire_schema)
        finally:
            ap.default_http_transport = saved
        ctx = json.loads(user)
        out.append(summarize_body(f'q5_fixture_round{i + 1}', rec.bodies[0], endpoint=ap.OPENAI_CHAT_URL, extra={
            'source': 'SYNTHETIC test fixture (tests/q1q5/test_q5_agent.py), template q5-agent-v2',
            'options_sent_on_wire': ['max_output_tokens'], 'options_in_settings': reqs[i]['options'],
            'payload_top_keys': sorted(ctx), 'context_keys': sorted(ctx['context']),
            'n_candidates': len(ctx['context'].get('candidates', [])), 'n_rounds_in_run': len(reqs)}))
    if len(out) == 2:
        out[0]['cache_vs_round2'] = cache_report(out[0]['body_redacted'], out[1]['body_redacted'])
    return out


# ----------------------------------------------------------------------------- driver
def load_demo(state_parent: Path):
    """Build the 8785 Demo object in-process (no socket). Needs AMIDST_DEMO_HOME and a resolved, writable state parent."""
    sys.path.insert(0, str(REPO / 'scripts'))
    import tempfile
    import serve_demo_integration as s
    from demo_dependency_config import configuration, owned_path
    for name in ('AMIDST_Q1Q5_REGISTRY', 'AMIDST_Q1Q5_REGISTRY_SHA256'):
        os.environ.pop(name, None)
    config, root = configuration()
    state = Path(tempfile.mkdtemp(dir=state_parent)).resolve() / 'state'
    return s.Demo(owned_path(root, config['artifacts_root']), owned_path(root, config['p1_bundle']), state,
                  job_path=owned_path(root, config['cross_camera_job']), job_pin=config['cross_camera_job_sha256'], owned_root=root,
                  eightcam=None, eightcam_required=False, agent_queue=None)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True, help='evidence directory (created)')
    p.add_argument('--state-parent', type=Path, required=True, help='existing resolved dir for the throw-away Demo state')
    p.add_argument('--live-pack', type=Path, help='LIVE adjudication pack dir (contains data/img)')
    a = p.parse_args(argv)
    sys.path.insert(0, str(REPO / 'src'))
    captures: list[dict] = []
    with no_network():
        app = load_demo(a.state_parent.resolve())
        params = json.loads((REPO / 'configs/q1q5/agent_decision_params_v1.json').read_text(encoding='utf-8'))
        from amidst.q1q5 import nl_query_parse as nlp
        for key, run in list(app.api.runs.items()):
            label = 'a4_1' if 'a4' in key[1] else 'b4_1' if 'b4' in key[1] else 'b05_synthetic' if key[0] == 'ENGINEERING_DYNAMIC_SCENE' else None
            if label is None:
                continue
            if label != 'b05_synthetic':      # associate()/DP1-DP3 needs the cross-camera tracks of the real runs
                captures += capture_dp(app, key, params, label)
            captures += capture_q5(app, key, label)
        captures += capture_q5_fixture()
        captures += capture_q3(nlp.vocabulary_from_catalog(next(iter(app.api.runs.values())).catalog))
        if a.live_pack:
            captures += capture_live(a.live_pack)
    files = write_evidence(a.out, captures)
    print(json.dumps({'written': [f.name for f in files], 'captures': [(c['name'], c.get('est_prompt_tokens'), c.get('n_images'),
                                                                        c.get('forbidden_field_hits'), c.get('error')) for c in captures]},
                     ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
