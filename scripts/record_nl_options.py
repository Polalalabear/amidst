#!/usr/bin/env python3
"""Record Epic D path (b) NL-to-options calls with local Ollama (Qwen3 1.7B) into a q-core.agent-recording.v1 file.

Run by Codex on a Mac with Ollama; Claude sessions never run it. Loopback only, no API key, no network beyond 127.0.0.1.
The catalog is the exact run row the server uses (a saved q_bootstrap response), so replay prompts match byte for byte.
Usage: see docs/operations/EPICD_NL_RECORDING.md
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from amidst.q1q5 import nl_options as nl  # noqa: E402
from amidst.q1q5.llm_provider import QWEN3_MODEL, LocalHTTPTransport, OllamaProvider, ProviderError  # noqa: E402

OPTIONS = {'temperature': 0, 'seed': 7, 'num_predict': 256}


def record(sentences, catalog, provider, *, model, options, timeout_ms, recording_id, note=None):
    """Call the provider once per sentence; returns (recording, rows). Failures are recorded (error_code), not hidden."""
    entries, rows, digest = [], [], None
    for item in sentences:
        prompt = nl.build_prompt(item['text'], catalog)
        raw, latency, code = None, None, None
        try:
            result = provider.generate(model=model, prompt=prompt, template=nl._template(), template_version=nl.TEMPLATE_VERSION,
                                       options=options, timeout_ms=timeout_ms, expected_digest=digest)
            raw, record_ = result.text, result.record
        except ProviderError as exc:
            code, record_ = exc.code, exc.record or {}
            raw = record_.get('raw_output')
        latency = (record_.get('stats') or {}).get('latency_ms')
        digest = digest or record_.get('model_digest')
        entries.append(nl.recorded_entry(model, prompt, options, raw, latency, code))
        rows.append({'id': item['id'], 'latency_ms': latency, 'error_code': code})
    info = {'kind': 'OLLAMA', 'model': model, 'model_digest': digest, 'options': options}
    return nl.make_recording(recording_id=recording_id, data_origin=nl.QWEN_RECORDED, provider_info=info, entries=entries, note=note), rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bootstrap', required=True, help='saved q_bootstrap JSON (GET /api/q_bootstrap)')
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--sentences', default=str(ROOT / 'configs/epicd/nl_sentences_v1.json'))
    ap.add_argument('--model', default=QWEN3_MODEL)
    ap.add_argument('--ollama-url', default='http://127.0.0.1:11434')
    ap.add_argument('--timeout-ms', type=int, default=60000, help='generous on purpose: Qwen3 1.7B median was 5.8 s untruncated')
    ap.add_argument('--recording-id', default='nl-qwen3-1p7b-v1')
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    bootstrap = json.loads(Path(args.bootstrap).read_text(encoding='utf-8'))
    runs = [r for r in bootstrap['runs'] if r['run_id'] == args.run_id]
    if len(runs) != 1:
        raise SystemExit('run-id not found in bootstrap')
    catalog = nl.catalog_from_run_summary(runs[0])
    sentences = json.loads(Path(args.sentences).read_text(encoding='utf-8'))['sentences']
    provider = OllamaProvider(LocalHTTPTransport(args.ollama_url))
    rec, rows = record(sentences, catalog, provider, model=args.model, options=OPTIONS, timeout_ms=args.timeout_ms,
                       recording_id=args.recording_id, note='Recorded locally with Ollama; replay via AMIDST_NL_RECORDING.')
    Path(args.out).write_text(json.dumps(rec, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    # offline self-check: replay every sentence through the real parser
    prov = nl.RecordedNlProvider(rec)
    print('id  latency_ms  record  replay')
    for item, row in zip(sentences, rows):
        r = nl.parse_nl_options({'schema_version': nl.REQUEST_SCHEMA, 'session_ref': 'S', 'scene_id': runs[0]['scene_id'], 'run_id': args.run_id,
                                 'kind': item['kind'], 'text': item['text']}, catalog=catalog, provider=prov)
        print(f"{item['id']}  {row['latency_ms']}  {row['error_code'] or 'OK'}  {r['decided_by']}/{r['fallback_reason']}/{r['status']}")
    print('recording_sha256', rec['content_sha256'], 'model_digest', rec['provider']['model_digest'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
