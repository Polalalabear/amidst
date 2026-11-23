"""E4 (#681, D355) arm A2E4 on the frozen E3 corpus: the E3 A2 replay with service_decider_e4.ServiceLiveDeciderE4 (+ scene context).

Preregistration: docs/evaluation/E4_PREREGISTRATION_20261123.md. Inference side only: the same frozen PNGs, detection index, tick
sequence and camera catalog as E3, loaded through ``e3_f4_run`` (unchanged). No case file, GT or scoring catalog is read here.
B1 / B2 / A2 are not rerun; scoring reuses the E3 run files (``e4_score.py``).

Per tick the row has the same fields as E3 (``tracking``, ``ranking``, ``decision_source``, ``events``). ``ranking`` is the Agent's
``next_camera_ranking`` from the latest answer (up to 3 cameras; empty before the first answer). Every call keeps the E4 record:
candidate list with ``detection_id``, chosen ``detection_id``, variable request text, prefix and image SHA-256s, trust state and
``validation``.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
_spec = importlib.util.spec_from_file_location('e3_f4_run', ROOT / 'scripts/evaluation/e3_f4_run.py')
E3 = importlib.util.module_from_spec(_spec)
sys.modules['e3_f4_run'] = E3
_spec.loader.exec_module(E3)

ARM = 'A2E4'
CALLER = 'e4'


def guarded_transport(budget_usd: float, usage_dir: Path):
    """As e3_f4_run.guarded_transport, ledger caller 'e4'."""
    import dataclasses
    import os
    from amidst.q1q5.api_budget import ApiGuard, GuardConfig
    from amidst.q1q5.openai_gateway import PRICES
    from amidst.live_mode.service_decider import guarded_responses_transport
    env = dict(os.environ, AMIDST_API_ENABLED='1', AMIDST_API_MAX_USD_TOTAL=str(budget_usd), AMIDST_API_MAX_USD_PER_DAY=str(budget_usd),
               AMIDST_API_MAX_USD_PER_CALL='0.2', AMIDST_API_MAX_TOKENS_PER_CALL='40000', AMIDST_API_MAX_CALLS_PER_DAY='5000',
               AMIDST_API_MAX_CALLS_PER_MIN='60', AMIDST_API_USAGE_DIR=str(usage_dir))
    cfg = GuardConfig.from_env(env)
    cfg = dataclasses.replace(cfg, prices={m: {'input_usd_per_mtok': a, 'output_usd_per_mtok': b} for m, (a, b) in PRICES.items()})
    guard = ApiGuard(cfg, usage_dir=usage_dir)

    class Caller:
        def run(self, caller, *a, **k):
            return guard.run(CALLER, *a, **k)
    return guarded_responses_transport(Caller(), 'gpt-6.1-terra', 30.0), guard


def make_decider(transport, scene, clock):
    from amidst.live_mode.people import PeopleTracker
    from amidst.live_mode.service_decider_e4 import ServiceLiveDeciderE4
    return ServiceLiveDeciderE4(transport, PeopleTracker(), scene, run_async=False, clock=clock, timeout_s=1e9,
                                gate_m=E3.CONFIG['gate_m'], target_color=E3.CONFIG['target_color'])


def replay(case, catalog: Path, scene, transport):
    """E3 replay (e3_f4_run.replay) with the E4 decider; ranking = the Agent's latest next_camera_ranking."""
    from PIL import Image
    from amidst.live_mode.server import State
    from amidst.live_mode.candidates import TrackSelection
    from amidst.live_mode.tracker import Projector, load_cameras
    C = E3.CONFIG
    clock = [0.0]
    state = State.__new__(State)
    state.projector = Projector(load_cameras(str(catalog)))
    state.args = SimpleNamespace(gate_m=C['gate_m'], gate_growth=0.0, max_gate=C['max_gate'], advisor='off')
    state.selection = TrackSelection(); state.selection.start(C['target_color'], False)
    state.tracker = state._new_tracker(C['target_color']); state.pending_acquire = []
    state.decider = make_decider(transport, scene, lambda: clock[0])
    rows = []
    for tick, dets0, paths in case['ticks']:
        t_s = tick * E3.TICK_US / 1e6
        clock[0] = t_s
        dets = copy.deepcopy(dets0)
        images = {c: Image.open(p).convert('RGB') for c, p in paths.items()}
        tr = state._infer_tracking(tick, t_s, dets, images, E3.SIZE)
        for im in images.values():
            im.close()
        active, est = tr.get('active_cam'), tr.get('est_xy')
        box = None
        if tr.get('state') == 'TRACKING' and not tr.get('lost_ticks') and active and est is not None:
            near = [d for d in dets.get(active, []) if d.get('est_xy') is not None and math.dist(d['est_xy'], est) <= C['box_radius_m']]
            if near:
                box = list(min(near, key=lambda d: math.dist(d['est_xy'], est))['bbox'])
        adv = tr.get('advisor') or {}
        rows.append({'tick': tick, 'tracking': {'state': tr.get('state'), 'active_cam': active, 'est_xy': est,
                                                'lost_ticks': tr.get('lost_ticks'), 'box': box},
                     'ranking': list(adv.get('next_camera_ranking') or []), 'trusted': adv.get('trusted'),
                     'decision_source': tr.get('decision_source', 'RULE_ONLY'),
                     'events': [e for e in tr.get('events') or [] if e.get('type') in ('ADJUDICATED', 'ADJUDICATE_ASK', 'SWITCH', 'ACQUIRE')]})
    d = state.decider
    calls = [dict(r, request=c, model_latency_s=m) for r, c, m in zip(d.records, d.calls_log, d.model_latency)]
    return rows, calls, {'asked': d.calls, 'answered': len(d.records), 'a3_chain': [], 'prefix_sha256': d.prefix_sha256}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True, help='E3 root of these cases')
    ap.add_argument('--cameras', type=Path, required=True, help='LIVE camera catalog (cameras.catalog.json)')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cases', nargs='+', required=True)
    ap.add_argument('--k', type=int, default=3)
    ap.add_argument('--budget-usd', type=float, required=True, help='ApiGuard total cap for this invocation')
    ap.add_argument('--usage-dir', type=Path, required=True, help='ApiGuard ledger of this invocation only (D352)')
    a = ap.parse_args()
    if a.budget_usd <= 0:
        raise SystemExit('--budget-usd must be > 0 (ApiGuard)')
    a.out.mkdir(parents=True, exist_ok=True)
    graph_raw = (ROOT / 'configs/q1q5/graphs/r004/camera_graph_v3.json').read_bytes()
    transport, _guard = guarded_transport(a.budget_usd, a.usage_dir)
    src = {p: E3.sha((ROOT / p).read_bytes()) for p in ['scripts/evaluation/e4_run.py', 'scripts/evaluation/e3_f4_run.py',
           'src/amidst/live_mode/service_decider_e4.py', 'src/amidst/live_mode/service_decider.py', 'src/amidst/live_mode/server.py',
           'src/amidst/live_mode/tracker.py', 'src/amidst/q1q5/agent_service.py', 'src/amidst/q1q5/scene_context.py']}
    from amidst.q1q5.scene_context import sha256_of
    for case_id in a.cases:
        case = E3.load_case(a.root, case_id)
        scene = E3.live_scene_context(a.cameras, case['cameras'])
        for k in range(1, a.k + 1):
            target = a.out / case_id / f'{ARM}.k{k}.json'
            if target.exists():
                print('SKIP_EXISTS', target, flush=True)
                continue
            t0 = time.time()
            rows, calls, dec = replay(case, a.cameras, scene, transport)
            doc = {'schema_version': 'e4.b-log.v1', 'case_id': case_id, 'arm': ARM, 'k': k, 'config': E3.CONFIG, 'tick_us': E3.TICK_US,
                   'size': list(E3.SIZE), 'inputs': {x: case[x] for x in ('index_content_sha256', 'records_file_sha256', 'rgb_index_sha256')},
                   'camera_catalog_sha256': E3.sha(a.cameras.read_bytes()), 'graph_sha256': E3.sha(graph_raw),
                   'scene_context_sha256': sha256_of(scene), 'source_sha256': src, 'decider': dec, 'calls': calls, 'rows': rows,
                   'identity': 'UNCONFIRMED', 'wall_s': round(time.time() - t0, 2)}
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(doc, allow_nan=False))
            print('RUN', case_id, ARM, k, len(rows), 'calls', len(calls), 'wall_s', doc['wall_s'], flush=True)


if __name__ == '__main__':
    main()
