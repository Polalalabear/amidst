#!/usr/bin/env python3
"""Build configs/epicd/nl_recording_synthetic_fixture_v1.json: a SYNTHETIC_FIXTURE recording for Epic D path (b).

NOT a model output. Raw outputs are computed from the deterministic rule parser so that the UI and tests can run offline;
S03 is recorded as a timeout and S04 as invalid JSON to exercise the fallback paths. Catalog = the synthetic preview run
(frontend/workbench-v2/fixtures/q-bootstrap.json + the two preview regions). Run: python scripts/build_nl_synthetic_fixture.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from amidst.q1q5 import nl_options as nl  # noqa: E402
from amidst.q1q5.q3_rules import parse_rule  # noqa: E402

REGIONS = [{'region_id': 'SYNTHETIC_ROOM_A', 'display_name': '合成區 A'}, {'region_id': 'SYNTHETIC_ROOM_B', 'display_name': '合成區 B'}]
FAILURES = {'S03': ('PROVIDER_TIMEOUT', None), 'S04': (None, 'not json')}


def synthetic_run():
    wrapper = json.loads((ROOT / 'frontend/workbench-v2/fixtures/q-bootstrap.json').read_text(encoding='utf-8'))
    run = json.loads(wrapper['bootstrap_json'])['runs'][0]
    run['region_graph'] = {'regions': REGIONS}
    return run


def main():
    catalog = nl.catalog_from_run_summary(synthetic_run())
    sentences = json.loads((ROOT / 'configs/epicd/nl_sentences_v1.json').read_text(encoding='utf-8'))['sentences']
    options = {'temperature': 0, 'seed': 7, 'num_predict': 256}
    entries = []
    for item in sentences:
        prompt = nl.build_prompt(item['text'], catalog)
        code, raw = FAILURES.get(item['id'], (None, None))
        if code is None and raw is None:
            rules = parse_rule(item['text'], allow_missing_time=True, class_aliases=catalog['class_aliases'], color_aliases=catalog['color_aliases'],
                               camera_aliases=catalog['camera_aliases'], region_aliases=catalog['region_aliases'])
            raw = json.dumps(rules.output, ensure_ascii=False, sort_keys=True)
        entries.append(nl.recorded_entry(nl.SYNTHETIC_FIXTURE, prompt, options, raw, None, code))
    rec = nl.make_recording(recording_id='nl-synthetic-fixture-v1', data_origin=nl.SYNTHETIC_FIXTURE,
                            provider_info={'kind': 'RECORDED', 'model': nl.SYNTHETIC_FIXTURE, 'options': options}, entries=entries,
                            note='SYNTHETIC_FIXTURE: computed from the rule parser, not produced by Qwen or any model. Latency unknown.')
    out = ROOT / 'configs/epicd/nl_recording_synthetic_fixture_v1.json'
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(out, rec['content_sha256'])


if __name__ == '__main__':
    main()
