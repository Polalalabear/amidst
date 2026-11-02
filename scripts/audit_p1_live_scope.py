"""D112-3: inspect pinned P1 live scope decisions without changing authority."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from amidst.q1q5.p1_workbench import P1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--state-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('New audit output required')
    scope = Path(__file__).resolve().parents[1] / 'configs/q1q5/p1_live_tracking_scope.json'
    pin = hashlib.sha256(scope.read_bytes()).hexdigest()
    app = P1(args.bundle.resolve(), args.manifest_sha256, args.state_root.resolve(),
             tracking_scope=scope, tracking_scope_pin=pin)
    run = next(iter(app.api.runs.values()))
    boot = app.bootstrap()['runs'][0]
    token = app.call('session', {'role': 'demo'})['session_ref']
    request = {'schema_version': 'q-demo.q2-request.v1', 'session_ref': token,
               'scene_id': boot['scene_id'], 'run_ids': [boot['run_id']],
               'time': {'kind': 'SOURCE', 'run_id': boot['run_id'],
                        'range_us': [0, boot['clock_mapping']['source_duration_us']]},
               'seed': {'kind': 'APPEARANCE', 'class_label': 'person',
                        'color': {'label': 'red', 'min_verdict': 'STRONG'}},
               'switch_mode': 'RULE_ONLY', 'parameter_set_id': boot['parameter_set_id']}
    seeds = app.call('q2_seed_candidates', request)['candidates']
    selected = seeds[0]
    response = app.call('q2_select_seed', {'request': request,
                                        'selected_observation_id': selected['observation_id']})
    bundle = app.api.responses[(token, response['session_id'])]
    decisions = [json.loads(line) for line in bundle['decisions'].splitlines()]
    actions = [d for d in decisions if d['executed_action'] is not None]
    exclusions = Counter((row['transition_id'], row['reason'])
                         for snap in bundle['snapshots'] for row in snap['excluded_transitions'])
    counts = {}
    for camera in boot['camera_ids']:
        rows = [o for row in run.bindings.index.records if row['camera_id'] == camera
                for o in row['detections'] or [] if o['class_label'] == 'person']
        counts[camera] = {'person_detections': len(rows),
                         'red_strong_at_query_floor': sum(
                             o['score'] >= boot['query_defaults']['query_min_score']
                             and (o.get('color') or {}).get('verdicts', {}).get('red') == 'STRONG'
                             for o in rows)}
    report = {'purpose': 'D112-3 UI-05 source-bound diagnosis; not approval or acceptance',
              'bundle_manifest_sha256': args.manifest_sha256,
              'bundle_source_commit': app.manifest['source_commit'],
              'scene_id': boot['scene_id'], 'run_id': boot['run_id'],
              'index_sha256': run.bindings.index_sha256,
              'parameter_set_sha256': run.bindings.parameter_sha256,
              'clock_mapping_sha256': run.bindings.clock_sha256,
              'tracking_scope_sha256': pin,
              'tracking_scope_status': run.bindings.graphs.tracking_scope['status'],
              'G4_approved': run.bindings.graphs.tracking_scope['G4_approved'],
              'effective_graph_approval': run.bindings.graphs.approval_status,
              'selected_seed': {k: selected[k] for k in ('observation_id', 'camera_id', 'timestamp_us')},
              'detection_counts': counts, 'response_status': response['status'],
              'response_reason': response['reason'], 'output_sha256': response['output_sha256'],
              'observed_camera_ids': sorted({s['camera_id'] for s in response['timeline'] if s['kind'] == 'ON_CAMERA'}),
              'candidate_snapshot_count': len(bundle['snapshots']),
              'candidate_counts': [len(s['candidates']) for s in bundle['snapshots']],
              'excluded_transitions': [{'transition_id': t, 'reason': r, 'snapshot_count': n}
                                       for (t, r), n in sorted(exclusions.items())],
              'executed_actions': dict(sorted(Counter(d['executed_action'] for d in actions).items())),
              'action_times_us': [d['source_time_us'] for d in actions],
              'model_calls': 0, 'gt_read': False, 'ui05_acceptance': 'FAIL_REMAINS'}
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
