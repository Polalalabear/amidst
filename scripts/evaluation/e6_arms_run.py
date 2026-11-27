"""E6 arms replay (inference side only) and ApiGuard dry-run estimate. #721, D377/D396.

Dry-run (no network, no key, no ledger; builds the real requests with a local canned transport):
  uv run python -B scripts/evaluation/e6_arms_run.py --root <E3 root> --cameras <catalog> --cases E3-A1 E3-B1 E3-C1 \
      --k 1 --dry-run
A paid run needs --budget-usd and --usage-dir and the coordinator's approval in chat; it is never part of this PR.
Never loads scoring inputs. Existing outputs are skipped, never overwritten. AO (original) is not run here.
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import e3_f4_run as frozen
import e5_run
from amidst.live_mode.aopen.arms import ARMS, ArmConfig, ArmDecider
from amidst.live_mode.aopen.decider import MODEL
from amidst.q1q5 import scene_context as sx

TICK_US, SIZE = e5_run.TICK_US, e5_run.SIZE
SCHEMA = 'e6.arm-log.v1'
OUTPUT_TOKENS = {'DEANCHOR': 300, 'DEANCHOR_HIST': 300, 'DEANCHOR_HIST_SUM': 450}


def replay(arm, case, catalog, scene, transport, *, k=1, poll_s=2.0, min_interval_s=1.0, call_cap_factor=1.5,
           timeout_s=30.0, sidecar=None, projector=None):
    from PIL import Image
    from amidst.live_mode.tracker import Projector, load_cameras
    ticks = case['ticks']
    duration = (ticks[-1][0] - ticks[0][0] + 1) * TICK_US / 1e6 if ticks else 0
    cap = math.ceil(duration / poll_s * call_cap_factor)
    state = sidecar if sidecar is not None else e5_run.make_sidecar(catalog)
    proj = projector if projector is not None else Projector(load_cameras(str(catalog)))
    d = ArmDecider(arm, transport, scene, proj, poll_s=poll_s, min_interval_s=min_interval_s, call_cap=cap, timeout_s=timeout_s)
    rows, t0, previous = [], time.monotonic(), None
    for tick, frozen_dets, paths in ticks:
        if previous is not None and tick != previous + 1:
            raise ValueError('NONCONTIGUOUS_TICKS')
        previous = tick
        dets = copy.deepcopy(frozen_dets)
        rule = state._infer_tracking(tick, tick * TICK_US / 1e6, dets, {}, SIZE)   # B1 sidecar: seed time only
        frames = {}
        try:
            for cam, path in paths.items():
                with Image.open(path) as image:
                    if image.size != SIZE:
                        raise ValueError('E6_FRAME_SIZE')
                    frames[cam] = image.convert('RGB')
            rows.append(d.step(tick, copy.deepcopy(dets), frames, copy.deepcopy(rule)))
        finally:
            for image in frames.values():
                image.close()
    return {'schema_version': SCHEMA, 'case_id': case['case_id'], 'arm': arm, 'k': k, 'tick_us': TICK_US, 'size': list(SIZE),
            'config': {'poll_s': poll_s, 'min_interval_s': min_interval_s, 'call_cap_per_segment': cap,
                       'call_cap_factor': call_cap_factor, 'timeout_s': timeout_s, 'model': MODEL, 'mode': 'offline'},
            'inputs': {key: case[key] for key in ('index_content_sha256', 'records_file_sha256', 'rgb_index_sha256')},
            'scene_context_sha256': sx.sha256_of(scene), 'identity': 'UNCONFIRMED',
            'wall_s': round(time.monotonic() - t0, 3), 'rows': rows, 'calls': d.calls, 'history': d.ledger.entries,
            'seed_tick': d.seed_tick, 'pending_at_end': d.pending is not None}


def canned_transport(body):
    """Dry-run only: no model, no network. Returns UNCERTAIN so request sizes can be measured."""
    return {'text': json.dumps({'answer': 'UNCERTAIN', 'next_camera_ranking': [], 'confidence': 'low'}), 'latency_s': 0.0,
            'usage': {}}


def prompt_tokens(body):
    """Same heuristic as service_decider.guarded_responses_transport: text chars / 3 + 1100 tokens per image."""
    parts = [p for it in body['input'] for p in it['content']]
    return (sum(len(p.get('text', '')) for p in parts if p.get('type') == 'input_text') // 3
            + 1100 * sum(1 for p in parts if p.get('type') == 'input_image'))


def dry_run(a):
    from amidst.q1q5.api_budget import estimate_run
    from amidst.q1q5.openai_gateway import PRICES
    prices = {m: {'input_usd_per_mtok': p, 'output_usd_per_mtok': q} for m, (p, q) in PRICES.items()}
    sizes, report = {arm: [] for arm in a.arms}, {}
    for cid in a.cases:
        case = frozen.load_case(a.root, cid)
        scene = frozen.live_scene_context(a.cameras, case['cameras'])
        sidecar = e5_run.make_sidecar(a.cameras)
        for arm in a.arms:
            seen = []

            def spy(body, seen=seen):
                seen.append(prompt_tokens(body))
                return canned_transport(body)
            doc = replay(arm, case, a.cameras, scene, spy, sidecar=e5_run.make_sidecar(a.cameras))
            sizes[arm] += seen
            report.setdefault(arm, {})[cid] = {'calls_per_replay': len(seen), 'avg_prompt_tokens': round(sum(seen) / len(seen)) if seen else 0,
                                               'call_cap': doc['config']['call_cap_per_segment']}
    out = {'schema_version': SCHEMA, 'dry_run': True, 'model': MODEL, 'k': a.k, 'cases': a.cases, 'arms': {}}
    total = 0.0
    for arm in a.arms:
        per = report[arm]
        # Upper bound: every ask up to the segment cap is made (cap, not the observed canned-answer count).
        cap_calls = sum(v['call_cap'] for v in per.values()) * a.k
        avg = round(sum(sizes[arm]) / len(sizes[arm])) if sizes[arm] else 0
        est = estimate_run(questions=cap_calls, model=MODEL, avg_prompt_tokens=avg, avg_output_tokens=OUTPUT_TOKENS[arm], prices=prices)
        out['arms'][arm] = {'per_case': per, 'estimate_upper_bound': est}
        total += est['est_total_usd'] or 0
    out['est_total_usd_upper_bound'] = round(total, 4)
    print(json.dumps(out, indent=1, sort_keys=True))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('root', 'cameras', 'out', 'usage-dir'):
        parser.add_argument('--' + key, type=Path)
    parser.add_argument('--cases', nargs='+', required=True)
    parser.add_argument('--arms', nargs='+', default=list(ARMS), choices=ARMS)
    parser.add_argument('--k', type=int, default=3)
    parser.add_argument('--budget-usd', type=float)
    parser.add_argument('--dry-run', action='store_true')
    a = parser.parse_args(argv)
    for key in ('root', 'cameras'):
        if getattr(a, key) is None:
            parser.error('--' + key + ' is required')
    for arm in a.arms:
        ArmConfig.of(arm)
    if a.dry_run:
        dry_run(a)
        return 0
    for key in ('out', 'usage_dir', 'budget_usd'):
        if getattr(a, key) is None:
            parser.error('--' + key.replace('_', '-') + ' is required for a paid run')
    raise SystemExit('PAID_RUN_NOT_AUTHORIZED: wait for the coordinator\'s approval in chat; dry-run first (D242)')


if __name__ == '__main__':
    main()
