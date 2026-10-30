"""Read-only P1 linker/controller replay; proposed variants remain fail closed.

No predictor, RGB, GT, live provider, product patch, or approval fabrication.
Full native-domain output (excluding timing stats) is written only to a new LOCAL
output directory. Proposed options do not inherit the baseline approval.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
from pathlib import Path

from amidst.q1q5.clock_mapping import ClockMapping
from amidst.q1q5.graphs import load_graphs
from amidst.q1q5.q4_evidence import candidate_evidence
from amidst.q1q5.q5_controller import RuleController, RuntimeBindings
from amidst.q1q5.store import DocumentPin, JsonRunStore, canonical_hash

MANIFEST_SHA256 = '6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7'
RECORDING = 'data/recordings/2777741d96ac9aff5bffb2f61a4d2938.json'
PROPOSAL_REF = 'https://github.com/Polalalabear/amidst/pull/273'
METRICS = ('linked_pairs', 'linked_contiguous_runs', 'on_camera_segments',
           'searching_entries', 'return_actions', 'switch_actions')


def need(ok, code):
    if not ok:
        raise ValueError(code)


def raw_json(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       ensure_ascii=True, allow_nan=False) + '\n').encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def regular(path):
    need(path.is_absolute() and path.resolve() == path and not path.is_symlink()
         and path.is_file(), 'CANONICAL_REGULAR_INPUT_REQUIRED')
    return path.read_bytes()


def load_source(root):
    need(root.is_absolute() and root.resolve() == root and root.is_dir(), 'SOURCE_ROOT')
    raw = regular(root / 'MANIFEST.json')
    need(sha(raw) == MANIFEST_SHA256, 'SOURCE_MANIFEST_PIN')
    manifest = json.loads(raw)
    need(manifest['formal_eligible'] is False and manifest['gt_read'] is False, 'ENGINEERING_ONLY')
    pins = {'MANIFEST.json': sha(raw)}

    def member(name):
        data = regular(root / name)
        pin = manifest['files'][name]
        need(sha(data) == pin['sha256'] and len(data) == pin['bytes'], 'FILE_PIN')
        pins[name] = sha(data)
        return json.loads(data)

    registry = member('data/registry/registry.json')
    need(canonical_hash(registry, exclude=('content_sha256',)) == registry['content_sha256'], 'REGISTRY_HASH')
    run, = registry['runs']
    names = ('index', 'records', 'parameter', 'clock', 'region', 'camera')
    documents = {k: DocumentPin(**registry['documents'][k]) for k in names}
    for pin in documents.values():
        relative = 'data/registry/' + pin.path
        need(manifest['files'][relative]['sha256'] == pin.file_sha256, 'REGISTRY_MANIFEST_BINDING')
        pins[relative] = pin.file_sha256
    store = JsonRunStore(root / 'data/registry', documents)
    index = store.load_detection_index('index')
    parameter, clock_doc = store.load_document('parameter'), store.load_document('clock')
    region, camera = store.load_document('region'), store.load_document('camera')
    graphs = load_graphs(region, camera, region_sha256=region['content_sha256'], camera_sha256=camera['content_sha256'])
    clock = ClockMapping.from_document(clock_doc, expected_sha256=clock_doc['content_sha256'])
    bindings = RuntimeBindings(index, index.manifest['content_sha256'], graphs,
                               region['content_sha256'], camera['content_sha256'], clock,
                               clock.content_sha256, parameter, parameter['content_sha256'],
                               run['media_ranges_by_camera'], run['media_scope_sha256'])
    bundle = member(RECORDING)
    need(bundle['schema_version'] == 'q-demo.api-recording.v1' and bundle['data_origin'] == 'RECORDED'
         and bundle['source_kind'] == 'SYNTHETIC', 'RECORDING_SCOPE')
    need(canonical_hash(bundle, exclude=('content_sha256',)) == bundle['content_sha256'], 'RECORDING_HASH')
    response = bundle['response']
    need(canonical_hash(response, exclude=('output_sha256', 'stats')) == response['output_sha256'], 'RESPONSE_HASH')
    for key in ('decisions', 'links'):
        need(sha(bundle[key].encode()) == response[key + '_sha256'], 'JOURNAL_HASH')
    scope = response['resolved_scope']
    for key, expected in [('detection_index_sha256', bindings.index_sha256),
                          ('parameter_set_sha256', bindings.parameter_sha256),
                          ('clock_mapping_sha256', bindings.clock_sha256),
                          ('region_graph_sha256', bindings.region_graph_sha256),
                          ('camera_graph_sha256', bindings.camera_graph_sha256)]:
        need(scope[key] == expected, 'RECORDING_BINDING')
    request = deepcopy(bundle['request'])
    need(request['switch_mode'] == 'RULE_ONLY', 'RULE_ONLY_REQUIRED')
    # Saved requests strip the ephemeral browser session token. This explicit
    # LOCAL session has new IDs; historical byte equality is never claimed.
    request['session_ref'] = 'LOCAL_CQ38_ENGINEERING_REPLAY'
    seed = next(s['observation_ids'][0] for s in response['timeline'] if s['kind'] == 'ON_CAMERA')
    return bindings, request, seed, bundle, pins


def proposed_parameters(baseline, changes):
    allowed = {'link_min_score': (.30, .4), 'link_iou_min': (0, .3)}
    need(bool(changes) and changes.keys() <= allowed.keys(), 'OPTION_NOT_ALLOWLISTED')
    doc = deepcopy(baseline)
    for name, value in changes.items():
        low, high = allowed[name]
        need(type(value) in (int, float) and low <= value <= high, 'OPTION_OUT_OF_RANGE')
        rows = [p for p in doc['parameters'] if p['name'] == name]
        need(len(rows) == 1, 'PARAMETER_MISSING')
        rows[0].update(value=value, status='PROPOSED', proposal_ref=PROPOSAL_REF)
    doc['approval'] = {'status': 'PROPOSED', 'approval_ref': None, 'approved_by': None}
    digest = canonical_hash(doc, exclude=('parameter_set_id', 'content_sha256', 'stats'))
    doc.update(content_sha256=digest, parameter_set_id='pset:q-demo:' + digest[:16])
    return doc


def native_replay(bindings, request, seed):
    def evidence(index, snapshot, reference, context):
        return candidate_evidence(index, snapshot, reference, **context)
    return RuleController(request, bindings=bindings, evidence_provider=evidence,
                          selected_observation_id=seed).run()


def metrics(response, decisions, links):
    # Pair = actual LINKED prev->next observation; runs = consecutive LINKED
    # journal rows on the same camera/local segment, not identity/GT recovery.
    pairs = {(r['camera_id'], r['prev_observation_id'], r['next_observation_id'])
             for r in links if r['decision'] == 'LINKED'}
    runs, prior = 0, None
    for r in links:
        key = (r['camera_id'], r['local_segment_id']) if r['decision'] == 'LINKED' else None
        if key is not None and key != prior:
            runs += 1
        prior = key
    accepted = [d for d in decisions if d['accepted']]
    counts = Counter(d['executed_action'] for d in accepted)
    return {'linked_pairs': len(pairs), 'linked_contiguous_runs': runs,
            'on_camera_segments': sum(s['kind'] == 'ON_CAMERA' for s in response['timeline']),
            'searching_entries': sum(d['state_after'] == 'SEARCHING' and d['state_before'] != 'SEARCHING' for d in accepted),
            'return_actions': counts['RETURN_TO_ORIGIN'], 'switch_actions': counts['SWITCH']}, pairs


def domain(result):
    response = deepcopy(result.response)
    response.pop('stats', None)  # Timing is explicitly excluded by the response hash contract.
    diagnostics = deepcopy(list(result.diagnostics))
    for row in diagnostics:
        row.pop('stats', None)  # Per-search wall timing; not domain evidence.
    return {'response': response, 'decisions': result.decisions_bytes.decode(),
            'links': result.links_bytes.decode(), 'snapshots': result.snapshots,
            'evidence': result.evidence, 'seed_candidates': result.seed_candidates,
            'diagnostics': diagnostics}


def run_comparison(bindings, request, seed, original, *, sweep=False):
    variants = {'baseline': {}}
    if sweep:
        variants.update({f'score_{v:.2f}': {'link_min_score': v} for v in (.39, .38, .35, .30)})
        variants.update({f'iou_{v}': {'link_iou_min': v} for v in (.299, .25, .24, .225)})
        variants['combined_0.30_0.225'] = {'link_min_score': .30, 'link_iou_min': .225}
    reports, outputs = {}, {}
    baseline_metrics, baseline_pairs = None, None
    for name, changes in variants.items():
        b, q = bindings, deepcopy(request)
        if changes:
            p = proposed_parameters(bindings.parameter_set, changes)
            b = replace(bindings, parameter_set=p, parameter_sha256=p['content_sha256'])
            q['parameter_set_id'] = p['parameter_set_id']
        result = native_replay(b, q, seed)
        value = domain(result)
        decisions = [json.loads(s) for s in value['decisions'].splitlines()]
        links = [json.loads(s) for s in value['links'].splitlines()]
        blocked = result.response.get('reason') == 'PARAMETERS_NOT_APPROVED'
        if blocked:
            need(not links and not decisions and not result.response['timeline'], 'FAIL_CLOSED_OUTPUT_LEAK')
            measured, pairs = None, None
        else:
            need(not changes, 'PROPOSED_EXECUTION_FORBIDDEN')
            need(result.response['status'] == 'COMPLETE', 'BASELINE_INCOMPLETE')
            measured, pairs = metrics(result.response, decisions, links)
            baseline_metrics, baseline_pairs = measured, pairs
        reports[name] = {'requested_options': changes, 'status': result.response['status'],
                         'reason': result.response.get('reason'), 'parameter_sha256': b.parameter_sha256,
                         'metrics': measured, 'delta_from_current': None if blocked else {k: measured[k] - baseline_metrics[k] for k in METRICS},
                         'new_linked_pairs': None if blocked else len(pairs - baseline_pairs),
                         'native_domain_sha256': sha(raw_json(value)), 'approval_promoted': False}
        outputs[name] = value
    historical_metrics, historical_pairs = metrics(original['response'],
        [json.loads(s) for s in original['decisions'].splitlines()],
        [json.loads(s) for s in original['links'].splitlines()])
    return {'classification': 'ENGINEERING_ONLY', 'formal_eligible': False,
            'identity_verdict': 'UNCONFIRMED', 'runtime_defaults_changed': False,
            'historical_recording_metrics': historical_metrics,
            'current_minus_historical': {k: baseline_metrics[k] - historical_metrics[k] for k in METRICS},
            'current_new_pairs_vs_historical': len(baseline_pairs - historical_pairs),
            'current_removed_pairs_vs_historical': len(historical_pairs - baseline_pairs),
            'historical_byte_replay': 'NOT_CLAIMED: new LOCAL session ID and current pinned product revision',
            'low_floor_0.10': 'NOT_RUN: RAW_BELOW_FLOOR_MISSING',
            'variants': reports}, outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sweep', action='store_true', help='Submit proposed variants to the unchanged fail-closed controller')
    args = parser.parse_args()
    need(args.output.is_absolute() and args.output.resolve() == args.output and not args.output.exists(), 'NEW_CANONICAL_OUTPUT_REQUIRED')
    need(not args.output.is_relative_to(args.source_root), 'OUTPUT_INSIDE_SOURCE')
    b, q, seed, original, pins = load_source(args.source_root)
    report, outputs = run_comparison(b, q, seed, original, sweep=args.sweep)
    report['source_file_sha256'] = pins
    report['product_module_sha256'] = {p.name: sha(p.read_bytes()) for p in sorted(Path(__import__('amidst.q1q5.q5_controller', fromlist=['x']).__file__).parent.glob('*.py'))}
    for path, pin in pins.items():
        need(sha(regular(args.source_root / path)) == pin, 'INPUT_CHANGED')
    args.output.mkdir()
    for name, output in outputs.items():
        (args.output / (name + '.LOCAL.json')).write_bytes(raw_json(output))
    (args.output / 'report.json').write_bytes(raw_json(report))
    print(json.dumps({'report_sha256': sha(raw_json(report)), 'variants': len(outputs), 'baseline': report['variants']['baseline']['metrics']}, sort_keys=True))


if __name__ == '__main__':
    main()
