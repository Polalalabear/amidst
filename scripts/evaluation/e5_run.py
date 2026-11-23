"""E5 A-open replay, inference side only: frozen pixels/detections and calibration/configuration.

Usage (Claude runs only after review; no pilot or paid call is part of Codex delivery):
  uv run python -B scripts/evaluation/e5_run.py --root <E3-root> --cameras <catalog> \
      --out <runs> --cases E3-A1 --k 3 --mode offline --budget-usd 25 --usage-dir <ledger> --dry-run
Drop --dry-run for an authorized run, with that process's own ledger and approved budget.
Export E5_EXTRA for the frozen preregistration appendix with --print-prompt (no other args required).
Never loads scoring inputs. Existing outputs are skipped, never overwritten. B1 is a private
sidecar, not a fallback; the only bridge to AO is the first reference crop/time and rule information.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import e3_f4_run as frozen
from amidst.live_mode.aopen.decider import AOpenDecider, E5_EXTRA, MODEL
from amidst.q1q5 import scene_context as sx

TICK_US, SIZE = 200_000, (320, 180)
SOURCE_PATHS = (
    'scripts/evaluation/e5_run.py', 'src/amidst/live_mode/aopen/decider.py', 'src/amidst/live_mode/aopen/neutral.py',
    'scripts/evaluation/e3_f4_run.py', 'src/amidst/live_mode/server.py', 'src/amidst/live_mode/tracker.py',
    'src/amidst/live_mode/candidates.py', 'src/amidst/live_mode/people.py', 'src/amidst/live_mode/color.py',
    'src/amidst/live_mode/service_decider.py', 'src/amidst/q1q5/agent_service.py', 'src/amidst/q1q5/scene_context.py',
    'src/amidst/q1q5/api_budget.py', 'docs/contracts/E5_AOPEN_INTERFACE_V1.md',
    'docs/evaluation/E5_PREREGISTRATION_20261123.md',
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def make_sidecar(catalog):
    from amidst.live_mode.candidates import TrackSelection
    from amidst.live_mode.server import State
    from amidst.live_mode.tracker import Projector, load_cameras
    state = State.__new__(State)
    state.projector = Projector(load_cameras(str(catalog)))
    state.args = SimpleNamespace(gate_m=frozen.CONFIG['gate_m'], gate_growth=frozen.CONFIG['gate_growth'],
                                 max_gate=frozen.CONFIG['max_gate'], advisor='off')
    state.selection = TrackSelection()
    state.selection.start(frozen.CONFIG['target_color'], False)
    state.tracker = state._new_tracker(frozen.CONFIG['target_color'])
    state.pending_acquire, state.decider = [], None
    return state


def guarded_transport(budget_usd, usage_dir, timeout_s):
    """Every real attempt goes through ApiGuard; model key is read only inside the guarded fn."""
    from amidst.live_mode.service_decider import guarded_responses_transport
    from amidst.q1q5.api_budget import ApiGuard, GuardConfig
    from amidst.q1q5.openai_gateway import PRICES
    cfg = GuardConfig(enabled=True, max_usd_total=budget_usd, max_usd_per_day=budget_usd,
                      max_usd_per_call=0.2, max_tokens_per_call=40000, max_calls_per_day=5000,
                      max_calls_per_min=60,
                      prices={m: {'input_usd_per_mtok': a, 'output_usd_per_mtok': b} for m, (a, b) in PRICES.items()})
    guard = ApiGuard(cfg, usage_dir=usage_dir)

    class Caller:
        def run(self, _caller, *args, **kwargs):
            return guard.run('e5', *args, **kwargs)
    return guarded_responses_transport(Caller(), MODEL, timeout_s), guard


def replay(case, catalog, scene, transport, *, mode='offline', k=1, poll_s=2.0, min_interval_s=1.0,
           call_cap_factor=1.5, timeout_s=30.0, sidecar=None, projector=None):
    from PIL import Image
    from amidst.live_mode.tracker import Projector, load_cameras
    if not math.isfinite(call_cap_factor) or call_cap_factor <= 0:
        raise ValueError('BAD_CALL_CAP_FACTOR')
    ticks = case['ticks']
    duration = (ticks[-1][0] - ticks[0][0] + 1) * TICK_US / 1e6 if ticks else 0
    cap = math.ceil(duration / poll_s * call_cap_factor) if poll_s > 0 else 0
    state = sidecar if sidecar is not None else make_sidecar(catalog)
    ao_projector = projector if projector is not None else Projector(load_cameras(str(catalog)))
    d = AOpenDecider(transport, scene, ao_projector, mode=mode, poll_s=poll_s,
                    min_interval_s=min_interval_s, call_cap=cap, timeout_s=timeout_s)
    rows, t0 = [], time.monotonic()
    previous_tick = None
    for tick, frozen_dets, paths in ticks:
        if previous_tick is not None and tick != previous_tick + 1:
            raise ValueError('NONCONTIGUOUS_TICKS')
        previous_tick = tick
        dets = copy.deepcopy(frozen_dets)  # _infer_tracking projects this private B1 copy in place
        rule = state._infer_tracking(tick, tick * TICK_US / 1e6, dets, {}, SIZE)
        frames = {}
        try:
            for cam, path in paths.items():
                with Image.open(path) as image:
                    if image.size != SIZE:
                        raise ValueError('E5_FRAME_SIZE')
                    frames[cam] = image.convert('RGB')
            # Decider sees a separate observation copy, not B1 selection/tracker objects.
            rows.append(d.step(tick, copy.deepcopy(dets), frames, copy.deepcopy(rule)))
        finally:
            for image in frames.values():
                image.close()
    return {'schema_version': 'e5.b-log.v1', 'case_id': case['case_id'], 'arm': 'AO' if mode == 'offline' else 'AOL', 'k': k,
            'tick_us': TICK_US, 'size': list(SIZE),
            'config': {'poll_s': poll_s, 'min_interval_s': min_interval_s, 'call_cap_per_segment': cap,
                       'call_cap_factor': call_cap_factor, 'timeout_s': timeout_s, 'mode': mode,
                       'neutral_iou': 0.3, 'coast_ticks': 2, 'occluded_hold_s': 2.0, 'model': MODEL,
                       'b1': copy.deepcopy(frozen.CONFIG)},
            'inputs': {key: case[key] for key in ('index_content_sha256', 'records_file_sha256', 'rgb_index_sha256')},
            'camera_catalog_sha256': sha(catalog.read_bytes()),
            'graph_sha256': sha((ROOT / 'configs/q1q5/graphs/r004/camera_graph_v3.json').read_bytes()),
            'scene_context_sha256': sx.sha256_of(scene),
            'source_sha256': {path: sha((ROOT / path).read_bytes()) for path in SOURCE_PATHS},
            'prompt_extra_sha256': sha(E5_EXTRA.encode()), 'identity': 'UNCONFIRMED',
            'wall_s': round(time.monotonic() - t0, 3), 'rows': rows, 'calls': d.calls, 'seed_tick': d.seed_tick,
            'pending_at_end': d.pending is not None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--print-prompt', action='store_true')
    # These become required after the prompt-only early exit.
    for key in ('root', 'cameras', 'out', 'usage-dir'):
        parser.add_argument('--' + key, type=Path)
    parser.add_argument('--cases', nargs='+')
    parser.add_argument('--k', type=int, default=3)
    parser.add_argument('--mode', choices=('offline', 'simlive'), default='offline')
    parser.add_argument('--poll-s', type=float, default=2.0)
    parser.add_argument('--min-interval-s', type=float, default=1.0)
    parser.add_argument('--call-cap-factor', type=float, default=1.5)
    parser.add_argument('--timeout-s', type=float, default=30.0)
    parser.add_argument('--budget-usd', type=float)
    parser.add_argument('--dry-run', action='store_true', help='Estimate only; no transport, credentials or ledger opened')
    a = parser.parse_args(argv)
    if a.print_prompt:
        print(E5_EXTRA)
        return 0
    for key in ('root', 'cameras', 'out', 'usage_dir', 'cases', 'budget_usd'):
        if getattr(a, key) is None:
            parser.error('--' + key.replace('_', '-') + ' is required')
    if a.k <= 0 or any(not math.isfinite(v) or v <= 0 for v in
                       (a.poll_s, a.min_interval_s, a.call_cap_factor, a.timeout_s, a.budget_usd)):
        parser.error('k and resource limits must be finite and positive')
    from amidst.q1q5.api_budget import estimate_run
    from amidst.q1q5.openai_gateway import PRICES
    prices = {m: {'input_usd_per_mtok': p, 'output_usd_per_mtok': q} for m, (p, q) in PRICES.items()}
    arm = 'AO' if a.mode == 'offline' else 'AOL'
    transport = None
    for cid in a.cases:
        remaining = [(k, a.out / cid / f'{arm}.k{k}.json') for k in range(1, a.k + 1)
                     if not (a.out / cid / f'{arm}.k{k}.json').exists()]
        if not remaining:
            print('SKIP_EXISTS', cid, flush=True)
            continue
        case = frozen.load_case(a.root, cid)
        duration = (case['ticks'][-1][0] - case['ticks'][0][0] + 1) / 5 if case['ticks'] else 0
        cap = math.ceil(duration / a.poll_s * a.call_cap_factor)
        # Dry-run precedes any paid attempt, and can also be requested as an estimate-only run.
        print('DRY_RUN', cid, json.dumps(estimate_run(questions=cap * len(remaining), model=MODEL,
              avg_prompt_tokens=8800, avg_output_tokens=300, prices=prices)), flush=True)
        if a.dry_run:
            continue
        scene = frozen.live_scene_context(a.cameras, case['cameras'])
        if transport is None:
            transport, _guard = guarded_transport(a.budget_usd, a.usage_dir, a.timeout_s)
        for k, target in remaining:
            doc = replay(case, a.cameras, scene, transport, mode=a.mode, k=k, poll_s=a.poll_s,
                         min_interval_s=a.min_interval_s, call_cap_factor=a.call_cap_factor, timeout_s=a.timeout_s)
            doc['config']['cost_cap_usd'] = a.budget_usd
            target.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also protects against a concurrent invocation or a race after SKIP_EXISTS.
            with target.open('x') as stream:
                json.dump(doc, stream, allow_nan=False)
            print('RUN', cid, arm, k, 'ticks', len(doc['rows']), 'calls', len(doc['calls']), flush=True)
            calls = doc['calls']
            if any(c['fallback_reason'] == 'CALL_BUDGET_EXHAUSTED' for c in calls):
                raise SystemExit('CALL_BUDGET_EXHAUSTED: output preserved; stop this invocation')
            if calls and sum(c['fallback_reason'] in ('PROVIDER_TIMEOUT', 'PROVIDER_ERROR') for c in calls) / len(calls) > 0.1:
                raise SystemExit('PROVIDER_ERROR_RATE: output preserved as missing-data run; no retry')
    return 0


if __name__ == '__main__':
    main()
