"""CX-H6 bounded QA server; scratchpad state only, original assets read-only.

Uses the production Demo/agent_service/file gateway and ApiGuard. Its six-call
per-run QA cap limits the screenshot smoke; it is not a research experiment.
"""
import argparse
import dataclasses
import json
import os
import re
from pathlib import Path
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from demo_dependency_config import configuration, owned_path  # noqa: E402
from demo_eightcam import prepare_eightcam  # noqa: E402
from serve_demo_integration import Demo  # noqa: E402
from amidst.q1q5.p1_workbench import server  # noqa: E402
from amidst.q1q5.api_budget import ApiGuard, GuardConfig, estimate_run  # noqa: E402
from amidst.q1q5.openai_gateway import GatewayWorker, PRICES  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--root-8cam', type=Path, required=True)
    p.add_argument('--port', type=int, default=8807)
    p.add_argument('--duration-s', type=int, default=600, help='QA server exits normally after a bounded interval')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--paid', action='store_true')
    mode.add_argument('--mock', action='store_true', help='clearly labelled, no network or paid calls')
    mode.add_argument('--replay-source', type=Path, help='exact request-SHA replay of existing paid decision records; no network')
    args = p.parse_args()
    out = args.output.resolve()
    repo = Path(__file__).resolve().parents[2]
    if not out.is_relative_to(repo / 'local/evidence'):
        raise ValueError('SCRATCHPAD_EVIDENCE_REQUIRED')
    out.mkdir(parents=True, exist_ok=True)
    prices = {m: {'input_usd_per_mtok': a, 'output_usd_per_mtok': b} for m, (a, b) in PRICES.items()}
    cfg = dataclasses.replace(GuardConfig.from_env(), enabled=args.paid, max_usd_total=.85, max_usd_per_day=.85,
                              max_usd_per_call=.08, max_tokens_per_call=80_000, max_calls_per_min=60, prices=prices)
    estimate = estimate_run(questions=12, model='gpt-6.1-terra', avg_prompt_tokens=40_000, avg_output_tokens=2_000,
                            prices=prices, config=cfg)
    (out / 'dry-run.json').write_text(json.dumps(estimate, indent=2) + '\n')
    print(json.dumps({'dry_run': estimate, 'paid': args.paid}), flush=True)
    if not args.paid and not args.mock and not args.replay_source:
        return
    if args.paid:
        guard = ApiGuard(cfg, usage_dir=out / 'usage')
        worker = GatewayWorker(out / 'queue', guard, models=('gpt-6.1-terra',))
        worker.write_status()
        threading.Thread(target=worker.serve_forever, daemon=True).start()
        os.environ['AMIDST_RECORDED_AGENT'] = 'openai'
    else:
        os.environ.pop('AMIDST_RECORDED_AGENT', None)
    config, root = configuration()
    eight, _ = prepare_eightcam(args.root_8cam)
    app = Demo(owned_path(root, config['artifacts_root']), owned_path(root, config['p1_bundle']), out / 'state',
               job_path=owned_path(root, config['cross_camera_job']), job_pin=config['cross_camera_job_sha256'],
               owned_root=root, eightcam=eight, agent_queue=out / 'queue' if args.paid else None)
    if args.mock or args.replay_source:
        from amidst.q1q5.service_agent_q5 import ServiceAgentFactory
        from amidst.q1q5.scene_graphs import load_scene_graphs
        _, _, settings, catalog, _, _ = eight.load()
        service = app.agent_service(load_scene_graphs('r004'), {(settings['scene_id'], settings['run_id']): (catalog, settings['catalog_sha256'])})
        def fake(body):
            text = '\n'.join(c.get('text', '') for x in body['input'] for c in x['content'])
            candidates = re.findall(r'^- (\S+) (D\d+): person score', text, re.MULTILINE)
            answer = {'answer': 'SELECT', 'camera_id': candidates[0][0], 'detection_id': candidates[0][1], 'reason_codes': ['MOCK_QA'], 'reason': 'MOCK: first person; no model called', 'confidence': 'low'} if candidates else {'answer': 'NOT_VISIBLE', 'reason_codes': ['MOCK_QA'], 'reason': 'MOCK: no person; no model called'}
            return {'text': json.dumps(answer)}
        if args.replay_source:
            from amidst.q1q5.service_agent_q5 import body_sha256
            records = {}
            for name in ('A4-1-8CAM-agent.json', 'B-05-agent.json'):
                document = json.loads((args.replay_source / name).read_bytes())
                for row in document['association_audit']:
                    if row.get('request_sha256') and row.get('answer'):
                        records[row['request_sha256']] = row
            replay_log = []
            def fake(body):
                sha = body_sha256(body)
                if sha not in records:
                    replay_log.append({'request_sha256': sha, 'matched': False})
                    (out / 'REPLAY.json').write_text(json.dumps(replay_log, indent=2) + '\n')
                    raise ValueError('REPLAY_MISS: rule fallback; never calls network')
                row = records[sha]
                replay_log.append({'request_sha256': sha, 'matched': True})
                (out / 'REPLAY.json').write_text(json.dumps(replay_log, indent=2) + '\n')
                return {'text': json.dumps(row['answer']), 'usage': row.get('usage'), 'latency_s': 0}
        app.api.runs = {k: dataclasses.replace(r, agent_factory=ServiceAgentFactory(fake, **service(r))) if k in app.core_track_keys else r for k, r in app.api.runs.items()}
    audit = {'destination': 'https://api.openai.com/v1/responses', 'model': 'gpt-6.1-terra',
             'source_kinds': {k[1]: app.api.runs[k].source_kind for k in sorted(app.core_track_keys)},
             'payload': ['Blender synthetic rendered JPEG frames/reference crop', 'RGB-only detector boxes/HSV labels', 'hash-bound scene configuration; unknown calibration explicitly marked'],
             'ground_truth_sent': False, 'real_person_footage_sent': False, 'private_locators_sent': False,
             'text_path_validation': 'GatewayResponsesTransport and GatewayWorker reject /Users/, /private/, /tmp/ and Windows local paths'}
    assert set(audit['source_kinds'].values()) <= {'SYNTHETIC', 'ACTUAL_BLENDER'}
    (out / 'PAYLOAD_AUDIT.json').write_text(json.dumps(audit, indent=2) + '\n')
    for key in app.core_track_keys:
        decider, why = app.track_decider(key, app.api.runs[key])
        if decider is None:
            raise ValueError(why)
        decider.max_calls = 6
    with server(app, args.port) as http:
        print(json.dumps({'mock': args.mock, 'replay': bool(args.replay_source), 'url': f'http://127.0.0.1:{http.server_port}/workbench-v2/'}), flush=True)
        deadline = time.monotonic() + args.duration_s
        http.timeout = 1
        while time.monotonic() < deadline:
            http.handle_request()


if __name__ == '__main__':
    main()
