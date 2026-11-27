"""E6 arms replay (inference side only), ApiGuard dry-run estimate and the guarded paid runs. #721, D377/D396/D398/D401.

Dry-run (no network, no key, no ledger; builds the real requests with a local canned transport):
  uv run python -B scripts/evaluation/e6_arms_run.py --root <root> --cameras <catalog> --cases <ids> --k <k> --dry-run
Two paid runs exist; everything else is refused (--paid and --max-usd are always required):
  DIAGNOSTIC  K=1, cases E3-A1 E3-B1 E3-C1, --max-usd <= 10 (prereg 2.1).
  FORMAL      K=3, all of E6-S01..E6-S12, --max-usd <= 32; needs E6_BATCH3_APPROVED=1 and the batch-3 freeze receipt
              (BATCH3_FREEZE.json: --receipt, else $E6_FREEZE_DIR, else <evidence root>/e6-batch3-freeze-20261127), and --arms must be
              exactly DEANCHOR + the receipt's SELECTED_AGENT (AO_ORIG runs through e5_run.py, not here).
  uv run python -B scripts/evaluation/e6_arms_run.py --root <root> --cameras <catalog> --cases ... --arms ... --k 3 --paid \
      --max-usd <usd> --baseline-json <RECONCILIATION_20261124.json> --out <dir> --extra-ledger <ledger dirs...>
Order: dry-run estimate -> estimate <= --max-usd -> D375 cumulative check (baseline + new ledger rows in <out>/ledger and every
--extra-ledger + estimate <= cap 90) -> only then a transport; every call goes through ApiGuard (own ledger <out>/ledger).
Outputs: <out>/<case>/<ARM>.k<n>.json (atomic), PRECHECK.json, STATUS.json, MANIFEST.sha256.
Never loads scoring inputs. Existing outputs are skipped, never overwritten. AO (original) is not run here.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import e3_f4_run as frozen
import e5_run
from amidst.live_mode.aopen.arms import ARMS, MAX_HISTORY, MAX_SENTENCE_CHARS, MAX_SENTENCES, ArmConfig, ArmDecider, HistoryLedger
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
    rows, t0, previous, stopped = [], time.monotonic(), None, None
    for tick, frozen_dets, paths in ticks:
        if previous is not None and tick != previous + 1:
            raise ValueError('NONCONTIGUOUS_TICKS')
        previous = tick
        if d.budget_exhausted:
            stopped = {'tick': tick, 'reason': d.calls[-1].get('error') or d.calls[-1].get('fallback_reason')}
            break
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
            'seed_tick': d.seed_tick, 'pending_at_end': d.pending is not None, 'stopped_early': stopped}


def canned_transport(body):
    """Dry-run only: no model, no network. Returns UNCERTAIN so request sizes can be measured."""
    return {'text': json.dumps({'answer': 'UNCERTAIN', 'next_camera_ranking': [], 'confidence': 'low'}), 'latency_s': 0.0,
            'usage': {}}


def prompt_tokens(body):
    """Same heuristic as service_decider.guarded_responses_transport: text chars / 3 + 1100 tokens per image."""
    parts = [p for it in body['input'] for p in it['content']]
    return (sum(len(p.get('text', '')) for p in parts if p.get('type') == 'input_text') // 3
            + 1100 * sum(1 for p in parts if p.get('type') == 'input_image'))


def estimate(a):
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
        # Prompt bound: observed mean of the canned run (answers all UNCERTAIN, short history) PLUS the largest possible history block.
        pad = worst_case_history_tokens(arm)
        avg = (round(sum(sizes[arm]) / len(sizes[arm])) if sizes[arm] else 0) + pad
        est = estimate_run(questions=cap_calls, model=MODEL, avg_prompt_tokens=avg, avg_output_tokens=OUTPUT_TOKENS[arm], prices=prices)
        out['arms'][arm] = {'per_case': per, 'history_padding_tokens': pad, 'estimate_upper_bound': est}
        total += est['est_total_usd'] or 0
    out['est_total_usd_upper_bound'] = round(total, 4)
    return out


def worst_case_history_tokens(arm):
    """Prompt tokens (chars/3, same heuristic) of the largest history block an arm can send: every call had a new answer,
    the ledger is full (MAX_HISTORY entries, long ids, all fields set), plus a full summary for SUM. DEANCHOR: one answer."""
    h = HistoryLedger()
    for _ in range(MAX_HISTORY + 2):
        h.add({'answer': 'SELECT', 'camera_id': 'CAM_EXT_CAR_LONG', 'detection_id': 'D99', 'box_xyxy': [319.55, 179.55, 319.95, 179.95],
               'confidence': 'medium', 'next_camera_ranking': ['CAM_EXT_CAR_LONG'] * 3, 'applied': True,
               'fallback_reason': 'CALL_BUDGET_EXHAUSTED', 'kind': 'LOST_EARLY', 'ask_tick': 99999}, 99999)
        h.entries[-1]['SYSTEM_OBSERVED'].update(followed_ticks=99999, followed_s=19999.8)
    cfg = ArmConfig.of(arm)
    chars = len(json.dumps(h.previous(), sort_keys=True)) if cfg.history == 'previous' else len(json.dumps(h.view(), sort_keys=True))
    if cfg.summary:
        chars += len(json.dumps([{'text': 'x' * MAX_SENTENCE_CHARS, 'sources': [f'H{i}' for i in range(1, MAX_HISTORY + 1)]}] * MAX_SENTENCES))
    return chars // 3 + 1


def dry_run(a):
    out = estimate(a)
    print(json.dumps(out, indent=1, sort_keys=True))
    return out


PAID_CASES = ('E3-A1', 'E3-B1', 'E3-C1')
PAID_K = 1
MAX_PAID_USD = 10.0
FORMAL_CASES = tuple(f'E6-S{i:02d}' for i in range(1, 13))
FORMAL_K = 3
MAX_FORMAL_USD = 32.0
RECEIPT_KEYS = ('SELECTED_AGENT', 'code_commit_sha', 'prompt_and_config_sha256', 'params', 'formal_dry_run_estimate', 'scorer_sha256')
CALLER = 'e6arms'


def default_receipt(a):
    """Batch-3 freeze receipt: --receipt, else $E6_FREEZE_DIR, else <evidence root>/e6-batch3-freeze-20261127 (evidence root = the
    parent of the baseline file's api-usage folder)."""
    if getattr(a, 'receipt', None):
        return Path(a.receipt)
    if os.environ.get('E6_FREEZE_DIR'):
        return Path(os.environ['E6_FREEZE_DIR']) / 'BATCH3_FREEZE.json'
    return Path(a.baseline_json).parent.parent / 'e6-batch3-freeze-20261127' / 'BATCH3_FREEZE.json'


def check_formal_gate(a):
    """Formal 12 segments: needs the approval env var AND the batch-3 freeze receipt, and exactly DEANCHOR + SELECTED_AGENT."""
    if os.environ.get('E6_BATCH3_APPROVED') != '1':
        raise SystemExit('FORMAL_NOT_APPROVED: E6_BATCH3_APPROVED=1 is required (batch-3 review + the user\'s approval, prereg 0.2)')
    path = default_receipt(a)
    if not path.is_file():
        raise SystemExit(f'FORMAL_RECEIPT_MISSING: {path}')
    raw = path.read_bytes()
    try:
        receipt = json.loads(raw)
    except ValueError:
        raise SystemExit('FORMAL_RECEIPT_UNREADABLE')
    missing = [k for k in RECEIPT_KEYS if not isinstance(receipt, dict) or k not in receipt]
    if missing:
        raise SystemExit('FORMAL_RECEIPT_INCOMPLETE: missing ' + ', '.join(missing))
    selected = receipt['SELECTED_AGENT']
    if selected not in ARMS:
        raise SystemExit('FORMAL_RECEIPT_BAD_SELECTED_AGENT')
    need = {'DEANCHOR', selected}
    if set(a.arms) != need or len(set(a.arms)) != len(a.arms):
        raise SystemExit(f'FORMAL_ARMS_REFUSED: arms must be exactly {sorted(need)} (DEANCHOR + SELECTED_AGENT from the receipt)')
    return {'path': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'SELECTED_AGENT': selected,
            'code_commit_sha': receipt['code_commit_sha']}


def check_paid_request(a):
    """Refuse everything except the two registered paid runs: the K=1 diagnostic (E3-A1/B1/C1, <= USD 10) and the formal K=3 run on
    E6-S01..S12 (<= USD 32, batch-3 gate). Returns (max_usd, mode, receipt-or-None)."""
    if not a.paid:
        raise SystemExit('PAID_RUN_NOT_AUTHORIZED: paid runs need --paid and --max-usd after the coordinator\'s approval (D242)')
    cases = list(a.cases)
    if len(set(cases)) != len(cases):
        raise SystemExit('PAID_COMBINATION_REFUSED: duplicate cases')
    if a.k == PAID_K and set(cases) <= set(PAID_CASES):
        mode, cap = 'DIAGNOSTIC', MAX_PAID_USD
    elif a.k == FORMAL_K and set(cases) == set(FORMAL_CASES):
        mode, cap = 'FORMAL', MAX_FORMAL_USD
    else:
        raise SystemExit(f'PAID_COMBINATION_REFUSED: only K={PAID_K} on {", ".join(PAID_CASES)} (diagnostic) or K={FORMAL_K} on all of '
                         f'{FORMAL_CASES[0]}..{FORMAL_CASES[-1]} (formal, batch-3 gate)')
    if a.max_usd is None or not math.isfinite(a.max_usd) or not 0 < a.max_usd <= cap:
        raise SystemExit(f'PAID_BUDGET_REFUSED: --max-usd must be in (0, {cap}] for the {mode.lower()} run')
    for key in ('out', 'baseline_json'):
        if getattr(a, key) is None:
            raise SystemExit('--' + key.replace('_', '-') + ' is required for a paid run')
    return a.max_usd, mode, (check_formal_gate(a) if mode == 'FORMAL' else None)


def ledger_total(usage_dir, since=None):
    """Sum of est_cost_usd of non-denied ledger rows (optionally only rows at/after an ISO timestamp)."""
    path = Path(usage_dir) / 'usage.jsonl'
    total = 0.0
    if path.exists():
        for line in path.read_text('utf-8').splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if (isinstance(row, dict) and row.get('outcome') != 'DENIED' and isinstance(row.get('est_cost_usd'), (int, float))
                    and (since is None or str(row.get('ts', '')) >= since)):
                total += row['est_cost_usd']
    return total


def cumulative_check(baseline_json, ledger_dirs, estimate_usd, max_usd):
    """D375: cumulative = baseline actual total + new ledger rows; cumulative + this run's upper bound must be <= cap."""
    base = json.loads(Path(baseline_json).read_text('utf-8'))
    actual, cap = float(base['actual_total_usd']), float(base['cap_usd'])
    since = str(base.get('effective_at', ''))
    # ISO strings with +08:00 do not sort against ledger 'Z' times; use UTC for the cut-off.
    from datetime import datetime, timezone
    try:
        since = datetime.fromisoformat(since).astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except ValueError:
        raise SystemExit('BASELINE_UNREADABLE: effective_at')
    new_rows = sum(ledger_total(d, since) for d in ledger_dirs)
    if estimate_usd > max_usd:
        raise SystemExit(f'ESTIMATE_OVER_MAX_USD: {estimate_usd:.4f} > {max_usd}')
    if actual + new_rows + estimate_usd > cap:
        raise SystemExit(f'CUMULATIVE_OVER_CAP: {actual} + {new_rows:.4f} + {estimate_usd:.4f} > {cap}')
    return {'baseline_actual_usd': actual, 'new_ledger_usd': round(new_rows, 6), 'estimate_usd': estimate_usd, 'cap_usd': cap}


def guarded_transport(max_usd, usage_dir, timeout_s, *, env=None, opener=None):
    """Every real attempt goes through ApiGuard (own ledger); the model key is read only inside the guarded call."""
    from amidst.live_mode.service_decider import guarded_responses_transport
    from amidst.q1q5.api_budget import ApiGuard, GuardConfig
    from amidst.q1q5.openai_gateway import PRICES
    cfg = GuardConfig(enabled=True, max_usd_total=max_usd, max_usd_per_day=max_usd, max_usd_per_call=0.2,
                      max_tokens_per_call=40000, max_calls_per_day=5000, max_calls_per_min=60,
                      prices={m: {'input_usd_per_mtok': x, 'output_usd_per_mtok': y} for m, (x, y) in PRICES.items()})
    guard = ApiGuard(cfg, usage_dir=usage_dir)

    class Caller:
        config = cfg

        def run(self, _caller, *args, **kwargs):
            return guard.run(CALLER, *args, **kwargs)
    kw = {} if opener is None else {'opener': opener}
    return guarded_responses_transport(Caller(), MODEL, timeout_s, env=env, **kw), guard


def write_manifest(out):
    lines = []
    for path in sorted(Path(out).rglob('*')):
        if path.is_file() and path.name != 'MANIFEST.sha256':
            lines.append(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(out).as_posix()}')
    (Path(out) / 'MANIFEST.sha256').write_text('\n'.join(lines) + '\n')
    return len(lines)


def atomic_write_json(target, doc):
    """Serialize first, write a temp file in the same folder, then os.replace: a final name is never a half-written file."""
    text = json.dumps(doc, allow_nan=False)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + '.tmp')
    with tmp.open('w') as stream:
        stream.write(text)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, target)


def finish(out, status, reason=None):
    """STATUS.json (COMPLETE | STOPPED | INCOMPLETE) then MANIFEST.sha256; leftover temp files are removed, not listed."""
    for tmp in Path(out).rglob('*.tmp'):
        tmp.unlink()
    atomic_write_json(Path(out) / 'STATUS.json', {'schema_version': SCHEMA, 'status': status, 'reason': reason})
    return write_manifest(out)


def paid_run(a, transport=None, guard=None):
    """Guarded K=1 diagnostic. ``transport``/``guard`` are injectable for offline tests; production builds them via ApiGuard."""
    from amidst.live_mode.aopen.arms import reject_forbidden
    max_usd, mode, receipt = check_paid_request(a)
    est = estimate(a)
    print(json.dumps({'DRY_RUN_FIRST': est['est_total_usd_upper_bound'], 'max_usd': max_usd}), flush=True)
    out = Path(a.out)
    usage_dir = out / 'ledger'
    cum = cumulative_check(a.baseline_json, [usage_dir] + [Path(d) for d in (a.extra_ledger or [])], est['est_total_usd_upper_bound'], max_usd)
    out.mkdir(parents=True, exist_ok=True)
    atomic_write_json(out / 'PRECHECK.json', {'schema_version': SCHEMA, 'mode': mode, 'receipt': receipt, 'cumulative': cum, 'estimate': est})
    if transport is None:
        transport, guard = guarded_transport(max_usd, usage_dir, 30.0)
    try:
        for cid in a.cases:
            case = frozen.load_case(a.root, cid)
            scene = frozen.live_scene_context(a.cameras, case['cameras'])
            for arm, k in [(arm, k) for arm in a.arms for k in range(1, a.k + 1)]:
                target = out / cid / f'{arm}.k{k}.json'
                if target.exists():                       # final names are only ever created by atomic_write_json
                    print('SKIP_EXISTS', cid, arm, k, flush=True)
                    continue
                doc = replay(arm, case, a.cameras, scene, transport, k=k)
                doc['config']['max_usd'] = max_usd
                reject_forbidden(doc, f'{cid}.{arm}', text=False)       # keys only: model free text is data, not a key
                atomic_write_json(target, doc)
                calls = doc['calls']
                print('RUN', cid, arm, k, 'ticks', len(doc['rows']), 'calls', len(calls), flush=True)
                if doc['stopped_early'] or any(c['fallback_reason'] == 'CALL_BUDGET_EXHAUSTED' for c in calls):
                    reason = 'CALL_BUDGET_EXHAUSTED: ' + json.dumps(doc['stopped_early'])
                    finish(out, 'STOPPED', reason)
                    raise SystemExit(reason + ' (output preserved; stop)')
                if calls and sum(c['fallback_reason'] in ('PROVIDER_TIMEOUT', 'PROVIDER_ERROR') for c in calls) / len(calls) > 0.1:
                    finish(out, 'STOPPED', 'PROVIDER_ERROR_RATE')
                    raise SystemExit('PROVIDER_ERROR_RATE: output preserved as missing-data run; no retry')
    except SystemExit:
        raise
    except BaseException as exc:
        finish(out, 'INCOMPLETE', type(exc).__name__ + ': ' + str(exc)[:200])
        raise
    return finish(out, 'COMPLETE')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ('root', 'cameras', 'out', 'baseline-json'):
        parser.add_argument('--' + key, type=Path)
    parser.add_argument('--cases', nargs='+', required=True)
    parser.add_argument('--arms', nargs='+', default=list(ARMS), choices=ARMS)
    parser.add_argument('--k', type=int, default=1)
    parser.add_argument('--max-usd', type=float)
    parser.add_argument('--extra-ledger', nargs='*', help='other ledger dirs whose rows after the baseline count toward the cap')
    parser.add_argument('--receipt', type=Path, help='batch-3 freeze receipt (formal run; default derived, see default_receipt)')
    parser.add_argument('--paid', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    a = parser.parse_args(argv)
    for key in ('root', 'cameras'):
        if getattr(a, key) is None:
            parser.error('--' + key + ' is required')
    for arm in a.arms:
        ArmConfig.of(arm)
    if a.dry_run and not a.paid:
        dry_run(a)
        return 0
    if a.dry_run and a.paid:
        parser.error('--dry-run and --paid are exclusive')
    paid_run(a)
    return 0


if __name__ == '__main__':
    main()
