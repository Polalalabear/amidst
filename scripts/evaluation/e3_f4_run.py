"""F4 (#658) E3 arms on the frozen #663 corpus. Inference side only: frozen PNGs + frozen detection index + camera catalog.

No case file, GT, annotation, expected event or scoring catalog is read here (preregistration §5.2); scoring is
``e3_f4_score.py``. Every arm replays the same LIVE tracker path as ``scripts/evaluation/e3_cases/baseline.py`` (State._infer_tracking,
all-camera schedule, gate 4 m, score .15 / CAM_ENTRY .05, HSV .2, advisor off, relock disabled):

  B1  rule; search order = undirected graph-hop distance from the active camera (CameraScheduler topology).
  B2  B1 display; search order = F2 spatial ranking (ground distance from the last estimate to each camera's ground footprint
      from calibration, scene_context v1 + static geometry 'live' gate; ties by graph hops then id). schedule=all, so only the
      order differs from B1, never the display.
  A1  B1 + agent_service decider (service_decider.ServiceLiveDecider), request WITHOUT scene_context.
  A2  same decider with scene_context (D340 mode).
  A3  A2 with simulated asynchrony (preregistration §7): an answer takes effect at the first tick after t_call + its measured latency;
      the selected person must still be continued by the people tracker (else EXPIRED, nothing shown from it).

Per tick the B log row has ``tracking`` = {state, active_cam, est_xy, lost_ticks, box} (box = the active camera's detection whose
projected position is within 1.5 m of the estimate, same rule for every arm), ``ranking`` (search order) and the decider status.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import sys
import time
from collections import deque
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

ARMS = ('B1', 'B2', 'A1', 'A2', 'A3')
TICK_US = 200_000
SIZE = (320, 180)
CONFIG = {'schedule': 'all', 'gate_m': 4.0, 'gate_growth': 0.0, 'max_gate': 8.0, 'min_score': .15, 'CAM_ENTRY_min_score': .05,
          'color_weak': .2, 'relock': 'disabled', 'target_color': 'red', 'box_radius_m': 1.5}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


# ------------------------------------------------------------------------------------------------ frozen inputs
def load_case(root: Path, case_id: str) -> dict:
    import numpy as np
    from PIL import Image
    from amidst.live_mode.color import judge
    manifest_path = root / 'indexes' / case_id / 'detection_index.json'
    m = json.loads(manifest_path.read_text())
    raw = (manifest_path.parent / m['records_ref']).read_bytes()
    if sha(raw) != m['records_file_sha256']:
        raise ValueError('INDEX_PIN_MISMATCH')
    rgb_path = root / 'rgb' / case_id / 'rgb_index.json'
    if sha(rgb_path.read_bytes()) != m['rgb_index_sha256']:
        raise ValueError('RGB_DESCRIPTOR_PIN_MISMATCH')
    rgb = json.loads(rgb_path.read_text())
    frames = {(r['camera_id'], r['frame_index']): r for r in rgb['records']}
    order = [f['cam'] for f in json.loads((root / f'{case_id}.replay1.wire.json').read_text())[0]['frames']]   # capture camera order
    grouped = {}
    for row in map(json.loads, raw.splitlines()):
        grouped.setdefault(row['frame_index'], []).append(row)
    ticks = []
    for tick, rows in sorted(grouped.items()):
        by_cam = {r['camera_id']: r for r in rows}
        dets, paths = {}, {}
        for cam in order:
            row, pin = by_cam[cam], frames[cam, tick]
            path = root / pin['relative_path']
            data = path.read_bytes()
            if sha(data) != row['rgb_file_sha256']:
                raise ValueError('INDEX_RGB_PIN_MISMATCH')
            arr = np.asarray(Image.open(io.BytesIO(data)).convert('RGB'))
            dets[cam] = [{'bbox': d['bbox_xyxy_px'], 'score': d['score'], **judge(arr, d['bbox_xyxy_px'], CONFIG['color_weak'])}
                         for d in row['detections'] if d['class_label'] == 'person'
                         and d['score'] >= (CONFIG['CAM_ENTRY_min_score'] if cam == 'CAM_ENTRY' else CONFIG['min_score'])]
            paths[cam] = path
        ticks.append((tick, dets, paths))
    return {'case_id': case_id, 'ticks': ticks, 'cameras': order, 'index_content_sha256': m['content_sha256'],
            'records_file_sha256': m['records_file_sha256'], 'rgb_index_sha256': m['rgb_index_sha256']}


# ------------------------------------------------------------------------------------------------ search orders
def graph_hops(graph, active):
    adj = {c['camera_id']: set() for c in graph['cameras']}
    for e in graph['transitions']:
        adj[e['from_camera_id']].add(e['to_camera_id']); adj[e['to_camera_id']].add(e['from_camera_id'])
    if active not in adj:
        return {}
    dist, todo = {active: 0}, deque([active])
    while todo:
        a = todo.popleft()
        for b in sorted(adj[a] - dist.keys()):
            dist[b] = dist[a] + 1; todo.append(b)
    return dist


def rank_b1(graph, active, cameras):
    d = graph_hops(graph, active)
    return sorted([c for c in cameras if c in d], key=lambda c: (d[c], c))


def _seg_dist(p, a, b):
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def poly_dist(p, poly):
    from amidst.q1q5.camera_projection import point_in_polygon
    if len(poly) >= 3 and point_in_polygon(p[0], p[1], poly):
        return 0.0
    return min(_seg_dist(p, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))) if poly else math.inf


def rank_b2(scene, graph, est, active, cameras):
    d = graph_hops(graph, active)
    foot = {c['camera_id']: c.get('ground_footprint_polygon_xy_m') or [] for c in scene['cameras']}
    if est is None:
        return rank_b1(graph, active, cameras)
    return sorted(cameras, key=lambda c: (round(poly_dist(est, foot.get(c, [])), 3), d.get(c, 99), c))


# ------------------------------------------------------------------------------------------------ scene context (A2/A3, B2)
def live_scene_context(catalog_path: Path, cameras):
    from amidst.q1q5 import scene_context as sx
    from amidst.q1q5.scene_graphs import R004_PINS, load_scene_graphs
    raw = catalog_path.read_bytes()
    g = load_scene_graphs('r004')
    shas = {**R004_PINS, 'camera_catalog.json': sha(raw)}
    static = sx.static_geometry((ROOT / 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json').read_bytes(),
                                (ROOT / 'docs/evaluation/F2_WALL_GATE_20261122.json').read_bytes(), 'live')
    return sx.build(g.region, g.camera, json.loads(raw), sorted(cameras), shas, g.tracking_scope, static=static)


# ------------------------------------------------------------------------------------------------ deciders
def make_decider(arm, transport, scene, clock):
    from amidst.live_mode.people import PeopleTracker
    from amidst.live_mode.service_decider import ServiceLiveDecider

    class Recording(ServiceLiveDecider):
        """Records every request's image SHA-256s (A1/A2 parity check) and, for A3, holds an answer until its measured latency passed."""

        def __init__(self, *a, simulate_latency=False, **k):
            super().__init__(*a, **k)
            self.simulate_latency, self.calls_log, self.model_latency = simulate_latency, [], []

        def build_input(self, t_s, people, frames, tracking):
            inp, ids = super().build_input(t_s, people, frames, tracking)
            self.calls_log.append({'t_s': round(t_s, 3), 'images': {cam: sha(b) for cam, b in inp.frames},
                                   'reference': sha(inp.reference_jpeg) if inp.reference_jpeg else None,
                                   'candidates': len(inp.candidates), 'scene': inp.include_scene})
            return inp, ids

        def _poll(self):
            with self._lock:
                rec = self._done
            if self.simulate_latency and self._pending is not None and rec is not None and self.clock() - self._pending['t0'] < float(rec.latency_s or 0.0):
                return None                                       # still "in flight" in simulated time
            res = super()._poll()
            if res is not None:
                self.model_latency.append(None if rec is None else rec.latency_s)
            return res

    return Recording(transport, PeopleTracker(), scene if arm in ('A2', 'A3') else None, run_async=False, clock=clock,
                     timeout_s=30.0 if arm == 'A3' else 1e9, simulate_latency=arm == 'A3', gate_m=CONFIG['gate_m'])


def guarded_transport(budget_usd: float, usage_dir: Path):
    from amidst.q1q5.api_budget import ApiGuard, GuardConfig
    from amidst.q1q5.openai_gateway import PRICES
    from amidst.live_mode.service_decider import guarded_responses_transport
    import os
    env = dict(os.environ, AMIDST_API_ENABLED='1', AMIDST_API_MAX_USD_TOTAL=str(budget_usd), AMIDST_API_MAX_USD_PER_DAY=str(budget_usd),
               AMIDST_API_MAX_USD_PER_CALL='0.2', AMIDST_API_MAX_TOKENS_PER_CALL='40000', AMIDST_API_MAX_CALLS_PER_DAY='5000',
               AMIDST_API_MAX_CALLS_PER_MIN='60', AMIDST_API_USAGE_DIR=str(usage_dir))
    cfg = GuardConfig.from_env(env)
    import dataclasses
    cfg = dataclasses.replace(cfg, prices={m: {'input_usd_per_mtok': a, 'output_usd_per_mtok': b} for m, (a, b) in PRICES.items()})
    guard = ApiGuard(cfg, usage_dir=usage_dir)

    class Caller:          # ledger caller 'e3_f4' (the LIVE transport says 'live_agent')
        def run(self, caller, *a, **k):
            return guard.run('e3_f4', *a, **k)
    return guarded_responses_transport(Caller(), 'gpt-6.1-terra', 30.0), guard


# ------------------------------------------------------------------------------------------------ one replay
def replay(case, arm, catalog: Path, graph, scene, transport=None):
    from PIL import Image
    from amidst.live_mode.server import State
    from amidst.live_mode.candidates import TrackSelection
    from amidst.live_mode.tracker import Projector, load_cameras
    clock = [0.0]
    state = State.__new__(State)
    state.projector = Projector(load_cameras(str(catalog)))
    state.args = SimpleNamespace(gate_m=CONFIG['gate_m'], gate_growth=0.0, max_gate=CONFIG['max_gate'], advisor='off')
    state.selection = TrackSelection(); state.selection.start(CONFIG['target_color'], False)
    state.tracker = state._new_tracker(CONFIG['target_color']); state.pending_acquire = []
    state.decider = make_decider(arm, transport, scene, lambda: clock[0]) if arm.startswith('A') else None
    rows, cams = [], case['cameras']
    for tick, dets0, paths in case['ticks']:
        t_s = tick * TICK_US / 1e6
        clock[0] = t_s
        dets = copy.deepcopy(dets0)
        images = {c: Image.open(p).convert('RGB') for c, p in paths.items()} if state.decider is not None else {}
        tr = state._infer_tracking(tick, t_s, dets, images, SIZE)
        for im in images.values():
            im.close()
        active, est = tr.get('active_cam'), tr.get('est_xy')
        box = None
        if tr.get('state') == 'TRACKING' and not tr.get('lost_ticks') and active and est is not None:
            near = [d for d in dets.get(active, []) if d.get('est_xy') is not None and math.dist(d['est_xy'], est) <= CONFIG['box_radius_m']]
            if near:
                box = list(min(near, key=lambda d: math.dist(d['est_xy'], est))['bbox'])
        adv = tr.get('advisor') or {}
        if arm == 'B2':
            ranking = rank_b2(scene, graph, est, active, cams)
        elif arm.startswith('A'):
            hint = adv.get('next_camera_hint')
            ranking = [hint] if hint else []
        else:
            ranking = rank_b1(graph, active, cams)
        rows.append({'tick': tick, 'tracking': {'state': tr.get('state'), 'active_cam': active, 'est_xy': est,
                                                'lost_ticks': tr.get('lost_ticks'), 'box': box},
                     'ranking': ranking, 'decision_source': tr.get('decision_source', 'RULE_ONLY'),
                     'events': [e for e in tr.get('events') or [] if e.get('type') in ('ADJUDICATED', 'ADJUDICATE_ASK', 'SWITCH', 'ACQUIRE')]})
    d = state.decider
    calls = [] if d is None else [dict(r, request=c, model_latency_s=m) for r, c, m in zip(d.records, d.calls_log, d.model_latency)]
    return rows, calls, (None if d is None else {'asked': d.calls, 'answered': len(d.records)})


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, required=True, help='E3_ROOT (local/evidence/e3-652-20261122)')
    ap.add_argument('--cameras', type=Path, required=True, help='LIVE camera catalog (cameras.catalog.json)')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cases', nargs='+', required=True)
    ap.add_argument('--arms', nargs='+', default=list(ARMS), choices=ARMS)
    ap.add_argument('--k', type=int, default=3)
    ap.add_argument('--budget-usd', type=float, default=0.0, help='ApiGuard total cap for this invocation (A arms need > 0)')
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    graph_raw = (ROOT / 'configs/q1q5/graphs/r004/camera_graph_v3.json').read_bytes(); graph = json.loads(graph_raw)
    transport = guard = None
    if any(x.startswith('A') for x in a.arms):
        if a.budget_usd <= 0:
            raise SystemExit('A arms need --budget-usd > 0 (ApiGuard)')
        transport, guard = guarded_transport(a.budget_usd, a.out / 'usage')
    src = {p: sha((ROOT / p).read_bytes()) for p in ['scripts/evaluation/e3_f4_run.py', 'src/amidst/live_mode/service_decider.py',
           'src/amidst/live_mode/server.py', 'src/amidst/live_mode/tracker.py', 'src/amidst/q1q5/agent_service.py', 'src/amidst/q1q5/scene_context.py']}
    for case_id in a.cases:
        case = load_case(a.root, case_id)
        scene = live_scene_context(a.cameras, case['cameras'])
        for arm in a.arms:
            for k in range(1, (a.k if arm.startswith('A') else 1) + 1):
                target = a.out / case_id / f'{arm}.k{k}.json'
                if target.exists():
                    print('SKIP_EXISTS', target, flush=True); continue
                t0 = time.time()
                rows, calls, dec = replay(case, arm, a.cameras, graph, scene, transport)
                doc = {'schema_version': 'e3-f4.b-log.v1', 'case_id': case_id, 'arm': arm, 'k': k, 'config': CONFIG, 'tick_us': TICK_US,
                       'size': list(SIZE), 'inputs': {x: case[x] for x in ('index_content_sha256', 'records_file_sha256', 'rgb_index_sha256')},
                       'camera_catalog_sha256': sha(a.cameras.read_bytes()), 'graph_sha256': sha(graph_raw),
                       'scene_context_sha256': __import__('amidst.q1q5.scene_context', fromlist=['sha256_of']).sha256_of(scene),
                       'source_sha256': src, 'decider': dec, 'calls': calls, 'rows': rows, 'identity': 'UNCONFIRMED',
                       'wall_s': round(time.time() - t0, 2)}
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(doc, allow_nan=False))
                print('RUN', case_id, arm, k, len(rows), 'calls', len(calls), 'wall_s', doc['wall_s'], flush=True)


if __name__ == '__main__':
    main()
