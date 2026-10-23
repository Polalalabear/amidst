"""Explicit SYNTHETIC engineering comparison; no models, GT or formal answers."""
import argparse
from pathlib import Path
import json
import subprocess
import sys
import os
from copy import deepcopy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--synthetic', action='store_true', required=True)
    parser.add_argument('--lost-after-us', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.lost_after_us <= 0:
        parser.error('lost-after-us must be positive; no formal default')
    need_parent = args.output.parent.resolve()
    if not need_parent.is_dir() or args.output.exists():
        parser.error('existing parent and new output directory required')
    args.output.mkdir()

    def disk(tag):
        raw = subprocess.check_output(['df', '-k', str(args.output)], text=True)
        (args.output / ('df-' + tag + '.txt')).write_text(raw)
        if int(raw.splitlines()[-1].split()[3]) < 8 * 1024 * 1024:
            raise RuntimeError('DISK_SPACE_BELOW_8_GIB')

    disk('before')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'tests/q1q5'))
    from test_q5_agent import bindings, settings, PolicyProvider, auto, request, seed_id
    from amidst.q1q5.q5_agent import AgentController, RecordedProvider
    from amidst.q1q5.q5_controller import RuleController
    from amidst.q1q5.q4_evidence import candidate_evidence
    from amidst.q1q5.event_modes import record_mode, compare_modes
    from amidst.q1q5.store import canonical_hash
    from amidst.q1q5.q5_controller import jsonl

    def domain_record(name, mode, query, result, b):
        directory = args.output / 'recorded' / name / mode
        directory.mkdir(parents=True)
        docs = {'request.json': query, 'response.json': result.response, 'detection_index.json': b.index.manifest,
                'parameter_set.json': b.parameter_set, 'clock_mapping.json': dict(b.clock.document),
                'region_graph.json': b.graphs.region, 'camera_graph.json': b.graphs.camera}
        docs.update({f'{i}.snapshot.json': x for i, x in enumerate(result.snapshots)})
        docs.update({f'{i}.evidence.json': x for i, x in enumerate(result.evidence)})
        for filename, doc in docs.items():
            (directory / filename).write_text(json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=True))
        (directory / b.index.manifest['records_ref']).write_bytes(jsonl(b.index.records))
        (directory / result.response['decisions_ref']).write_bytes(result.decisions_bytes)
        (directory / result.response['links_ref']).write_bytes(result.links_bytes)

    def policy(payload, n):
        last = payload['last_tool_result']
        if last.get('schema_version') == 'q-demo.candidate-evidence.v1' and not last['best_observations'] and last['entry_observation_id'] is None:
            # Current contract cannot cite empty evidence for NEXT (#183).
            return auto(payload, n, 'RETURN_TO_ORIGIN')
        return auto(payload, n)

    cases = [
        ('supported_candidate', None, policy),
        ('empty_first_candidate', {'A': {0: 'STRONG', 1: 'STRONG'}, 'E': {i: 'STRONG' for i in range(5, 10)}}, policy),
        ('no_candidate_observations', {'A': {0: 'STRONG', 1: 'STRONG'}}, policy),
        ('temporary_loss_recovery', {'A': {0: 'STRONG', 1: 'STRONG', **{i: 'STRONG' for i in range(4, 10)}}}, policy),
        ('provider_failure', None, lambda payload, n: ConnectionError()),
    ]
    reports = []
    for name, pattern, agent_policy in cases:
        b = bindings(pattern, cameras=('A', 'B', 'E'))
        q = request(b); selected = seed_id(b)
        evidence = lambda index, snapshot, ref, context: candidate_evidence(index, snapshot, ref, **context)
        rule = RuleController(q, bindings=b, evidence_provider=evidence, selected_observation_id=selected)
        rule_result = rule.run()
        backend = record_mode('BACKEND_FLAGS', q, rule_result, selected_seed=selected, lost_after_us=args.lost_after_us)
        domain_record(name, 'BACKEND_FLAGS', q, rule_result, b)
        aq = deepcopy(q); aq['switch_mode'] = 'AGENT_SEQUENTIAL'
        provider = PolicyProvider(agent_policy)
        agent = AgentController(aq, bindings=b, evidence_provider=evidence, selected_observation_id=selected,
                                provider=provider, agent_settings=settings(), round_scheduler=lambda *x: None, clock=lambda: 0)
        result = agent.run(); trace = agent.trace()
        domain_record(name, 'AGENT_DECISIONS', aq, result, b)
        recorded = record_mode('AGENT_DECISIONS', aq, result, selected_seed=selected, lost_after_us=args.lost_after_us, trace=trace)
        replay = RecordedProvider(trace, expected_sha256=trace['content_sha256'])
        rerun = AgentController(aq, bindings=b, evidence_provider=evidence, selected_observation_id=selected,
                               provider=replay, agent_settings=settings(), round_scheduler=lambda *x: None, clock=replay.clock).run()
        replay.assert_consumed()
        assert result.response['output_sha256'] == rerun.response['output_sha256'] and result.decisions_bytes == rerun.decisions_bytes and result.links_bytes == rerun.links_bytes
        report = compare_modes(backend, recorded, lost_after_us=args.lost_after_us, source_kind='SYNTHETIC')
        item = {'case_id': name, 'provider_kind': 'MECHANICAL_FAKE_PROVIDER', 'offline_trace_replay_equal': True, 'comparison': report}
        reports.append(item)
        fd = os.open(args.output / (name + '.trace.json'), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as handle:
            json.dump(trace, handle, ensure_ascii=True, indent=2)
    bundle = {'schema_version': 'q-demo.event-mode-suite.v1', 'source_kind': 'SYNTHETIC', 'counts_for_acceptance': False,
              'provider_kind': 'MECHANICAL_FAKE_PROVIDER', 'cases': reports}
    bundle['content_sha256'] = canonical_hash(bundle)
    (args.output / 'comparison.json').write_text(json.dumps(bundle, ensure_ascii=True, separators=(',', ':'), sort_keys=True))
    disk('after')
    print(json.dumps({'cases': len(reports), 'output': str(args.output), 'content_sha256': bundle['content_sha256']}))


if __name__ == '__main__':
    main()
