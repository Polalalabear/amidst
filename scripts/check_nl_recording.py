#!/usr/bin/env python3
"""Check that an Epic D path (b) recording can be replayed against a backend's catalog (offline, no model, no network).

For every fixed sentence: does the recording hold a call whose prompt (template + this run's closed catalog + sentence)
hashes the same? If not, the UI shows 「退回規則：錄製檔沒有這句話」. Also tells whether the catalog inside the recording equals
the run's current catalog. Exit 0 only when every sentence matches. Usage:
  python scripts/check_nl_recording.py --recording R.json --bootstrap /tmp/epicd_bootstrap.json --run-id RUN_ID
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from amidst.q1q5 import nl_options as nl  # noqa: E402
from amidst.q1q5.store import canonical_hash  # noqa: E402


def _recorded_catalog(entry):
    prompt = entry['request']['prompt']
    return json.loads(prompt.split('\nCLOSED_CATALOG=', 1)[1].split('\nUSER_TEXT=', 1)[0])


def check_recording(recording, catalog, sentences):
    """Returns (ok, report). `catalog` is the run's closed catalog (nl_options.catalog_from_run_summary)."""
    provider = nl.RecordedNlProvider(recording)  # also verifies content/request hashes
    hashes = {e['request_sha256'] for e in recording['entries']}
    template = nl._template()
    model, options = provider.info['model'], provider.info['options']
    rows = []
    for item in sentences:
        prompt = nl.build_prompt(item['text'], catalog)
        want = canonical_hash(nl._request_for_hash(model, prompt, template, nl.TEMPLATE_VERSION, options))
        rows.append({'id': item['id'], 'match': want in hashes})
    wanted = {c for c in (canonical_hash(_recorded_catalog(e)) for e in recording['entries'])}
    current = canonical_hash({k: catalog[k] for k in nl._LLM_CATALOG_FIELDS})
    report = {'recording_id': recording['recording_id'], 'data_origin': recording['data_origin'], 'model': model,
              'catalog_equal': wanted == {current}, 'recorded_catalog_variants': len(wanted), 'sentences': rows,
              'missing': [r['id'] for r in rows if not r['match']], 'entries': len(recording['entries'])}
    return not report['missing'] and report['catalog_equal'], report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--recording', required=True)
    ap.add_argument('--bootstrap', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--sentences', default=str(ROOT / 'configs/epicd/nl_sentences_v1.json'))
    args = ap.parse_args(argv)
    runs = [r for r in json.loads(Path(args.bootstrap).read_text(encoding='utf-8'))['runs'] if r['run_id'] == args.run_id]
    if len(runs) != 1:
        raise SystemExit('run-id not found in bootstrap')
    ok, report = check_recording(json.loads(Path(args.recording).read_text(encoding='utf-8')), nl.catalog_from_run_summary(runs[0]),
                                 json.loads(Path(args.sentences).read_text(encoding='utf-8'))['sentences'])
    print(json.dumps(report, ensure_ascii=False, indent=1))
    print('RESULT', 'MATCH' if ok else 'MISMATCH (UI would fall back with REPLAY_MISS)')
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
