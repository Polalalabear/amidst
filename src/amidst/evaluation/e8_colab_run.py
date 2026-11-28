"""E8 Colab orchestration (#780; design E8_DESIGN_V1.md §6.2-§6.3). INFERENCE SIDE: never reads the answer table.

The notebook ``notebooks/e8_colab_eval.ipynb`` calls these functions cell by cell. Checkpoints, zip handling and RUN_NOTES reuse
``e7_colab_runtime``; model loading reuses ``e7_decider_eval`` (``.raw`` entry points); requests, rendering and answers reuse
``e8_requests``; the closed loop reuses ``e8_handoff`` (``e3_f4_run.replay``).
"""
from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any, Callable

from amidst.evaluation import e8_handoff as H
from amidst.evaluation import e8_requests as R
from amidst.evaluation.e7_colab_runtime import load_group_checkpoint, save_group_checkpoint

LAYA_MODELS = ('laya_text', 'laya_typed')
QWEN_MODELS = ('qwen3b', 'qwen7b')
MODEL_LEVELS = {'laya_text': ('L0', 'L0c', 'L1', 'L2', 'L3'), 'laya_typed': ('L0', 'L0c', 'L1', 'L2', 'L3'),
                'qwen3b': ('L0', 'L0c', 'L1', 'L2', 'L3', 'L4'), 'qwen7b': ('L0', 'L0c', 'L1', 'L2', 'L3', 'L4', 'L3F')}
TIME_LIMIT_H = 4.0               # design §6.3: above this (A100 projection) Qwen L0 runs p0 only
TIMING_SAMPLE = 20
PART2_RULE_GROUPS = ('FIRST_RED', 'NEAREST_RED')
PART2_TRIGGERS_PER_CASE = 50     # planning figure only (SMOKE KEEP-only decider: 25 / 271 ticks, 12 / 150 ticks)


# ------------------------------------------------------------------------------------------------ pack
def load_pack(pack_root: Path) -> dict[str, Any]:
    root = Path(pack_root)
    reqs = [json.loads(x) for x in (root / 'requests' / 'e8_part1.jsonl').read_text().splitlines() if x.strip()]
    info = json.loads((root / 'PACK_INFO.json').read_text())
    cases = json.loads((root / 'part2' / 'cases.json').read_text())
    bases = {r['base_id'] for r in reqs}
    if len(bases) != info['decision_points']:
        raise RuntimeError(f"G5_DECISION_POINTS {len(bases)} != {info['decision_points']}")
    return {'root': root, 'requests': reqs, 'info': info, 'cases': cases}


def scene_for(pack: dict, case_id: str) -> dict:
    return json.loads((pack['root'] / pack['cases'][case_id]['scene']).read_text())


# ------------------------------------------------------------------------------------------------ backends
def smoke_laya(state: dict, questions: dict) -> dict:
    """Deterministic stand-in (SMOKE_MODE): a hash of the input picks one criterion."""
    keys = list(questions['pick']['criteria'])
    h = int(hashlib.sha256(json.dumps([state, questions], sort_keys=True, default=str).encode()).hexdigest(), 16)
    return {'choice': keys[h % len(keys)], 'confidence': 0.5}


def smoke_vlm(system: str | None, text: str, images: list, max_new: int) -> str:
    h = int(hashlib.sha256(text.encode()).hexdigest(), 16)
    if system is None:   # L0: E7 AO format
        return json.dumps({'answer': 'UNCERTAIN', 'camera_id': None, 'detection_id': None, 'box_xyxy': None,
                           'next_camera_ranking': [], 'confidence': 0.5, 'reason_codes': ['SMOKE'], 'reason': 'smoke'})
    opts = [ln[2] for ln in text.splitlines() if ln.startswith('- ') and len(ln) > 3 and ln[2].isupper() and ln[3] == ' ']
    pick = h % (len(opts) + 2)
    if pick < len(opts):
        return json.dumps({'answer': 'SELECT', 'option': opts[pick], 'confidence': 'low'})
    return json.dumps({'answer': ('KEEP', 'NOT_VISIBLE')[pick - len(opts)], 'option': None, 'confidence': 'low'})


def answer_fn(model: str, *, laya_raw: Callable | None = None, vlm_raw: Callable | None = None, pack: dict | None = None) -> Callable:
    """request -> (answer | None, error | None, latency_s). ``vlm_raw(system, text, [(label, PIL)], max_new)``; image paths are
    resolved against the pack root here."""
    def _laya(req):
        t0 = time.perf_counter()
        ans, err = R.answer_with_laya(req, laya_raw)
        return ans, err, time.perf_counter() - t0

    def _vlm(req):
        from PIL import Image

        def raw(system, text, images, max_new):
            pil = []
            for label, rel in images:
                with Image.open(pack['root'] / rel) as im:
                    pil.append((label, im.convert('RGB')))
            return vlm_raw(system, text, pil, max_new)
        t0 = time.perf_counter()
        scene = scene_for(pack, req['case_id']) if req['level'] == 'L3F' else None
        ans, err = R.answer_with_vlm(req, raw, scene=scene)
        return ans, err, time.perf_counter() - t0
    return _laya if model in LAYA_MODELS else _vlm


# ------------------------------------------------------------------------------------------------ Part 1
def part1_groups(requests: list[dict], model: str, *, qwen_l0_p0_only: bool = False) -> list[tuple[str, str, list[dict]]]:
    out = []
    for lv in MODEL_LEVELS[model]:
        for perm in R.PERMS:
            if qwen_l0_p0_only and model in QWEN_MODELS and lv == 'L0' and perm != 'p0':
                continue
            reqs = [r for r in requests if r['level'] == lv and r['perm'] == perm]
            if reqs:
                out.append((lv, perm, reqs))
    return out


def run_group(model: str, level: str, perm: str, reqs: list[dict], ask: Callable, output_dir: Path, fingerprint: dict,
              *, audit: Callable | None = None) -> tuple[dict, bool]:
    """One (model, level, order) group with a resumable checkpoint. Returns (result, resumed)."""
    mode = f'{level}_{perm}'
    done = load_group_checkpoint(output_dir, model, mode, fingerprint)
    if done is not None:
        return done, True
    records, lats = [], []
    for req in reqs:
        ans, err, lat = ask(req)
        rec = R.make_record(req, model, ans, err, latency_s=round(lat, 4))
        if audit is not None:
            rec['laya_truncation'] = audit(req)
        records.append(rec)
        lats.append(lat)
    result = {'model': model, 'level': level, 'perm': perm, 'n': len(records), 'records': records,
              'latency_p50_s': statistics.median(lats) if lats else None,
              'format_invalid': sum(1 for r in records if r['error'] is not None)}
    save_group_checkpoint(output_dir, model, mode, result, fingerprint)
    return result, False


def timing_sample(reqs: list[dict], ask: Callable, n: int = TIMING_SAMPLE) -> float:
    lats = [ask(r)[2] for r in reqs[:n]]
    return statistics.median(lats) if lats else 0.0


def projected_hours(requests: list[dict], medians: dict[str, dict[str, float]], *, laya_s: float = 0.04, install_h: float = 0.25,
                    qwen_l0_p0_only: bool = False, part2_cases: int = 28) -> float:
    """Design §6.3 re-estimate from measured medians: medians[model] = {'L0': s, 'text': s, 'L4': s, 'L3F': s}."""
    total = install_h * 3600
    for model in LAYA_MODELS:
        total += sum(len(g[2]) for g in part1_groups(requests, model)) * laya_s
    for model in QWEN_MODELS:
        med = medians.get(model) or {}
        for lv, _perm, reqs in part1_groups(requests, model, qwen_l0_p0_only=qwen_l0_p0_only):
            kind = lv if lv in ('L0', 'L4', 'L3F') else 'text'
            total += len(reqs) * med.get(kind, med.get('text', 1.0))
        total += part2_cases * PART2_TRIGGERS_PER_CASE * med.get('text', 1.0) * 2      # ZERO_LATENCY + MEASURED (worst case)
    return total / 3600


def laya_audit_fn(laya_infer, model: str) -> Callable:
    """Truncation covariate (V6) with laya's own tokenizer; UNKNOWN when the agent exposes none."""
    tok = getattr(laya_infer.agent(), 'tokenizer', None)
    if tok is None:
        return lambda req: {'status': 'UNKNOWN_NO_TOKENIZER'}

    def audit(req):
        state, questions, _ = R.render_laya(req)
        return R.laya_truncation(state, questions, lambda t: tok(t, add_special_tokens=False)['input_ids'], model)
    return audit


# ------------------------------------------------------------------------------------------------ Part 2
def baseline_ask(policy: str) -> Callable:
    def ask(req):
        return R.baseline_answer(policy, req), None, 0.0
    return ask


def b1_gate(pack: dict, graph: dict) -> dict[str, dict]:
    """V2 / G1: B1 reproduced on every case; the caller stops on any failure (no case is skipped)."""
    out = {}
    for cid, meta in pack['cases'].items():
        rows = _rows(pack, cid)
        res = H.run_case(rows, meta['cameras'], pack['root'] / 'part2' / 'cameras.catalog.json', graph, scene_for(pack, cid))
        frozen = json.loads((pack['root'] / meta['b1_frozen']).read_text())['rows']
        out[cid] = H.b1_reproduced(res['rows'], frozen)
    return out


def _rows(pack: dict, cid: str) -> list[dict]:
    return [json.loads(x) for x in (pack['root'] / pack['cases'][cid]['ticks']).read_text().splitlines() if x.strip()]


def run_part2_group(pack: dict, graph: dict, group: str, ask: Callable, level: str, latency: str, output_dir: Path,
                    fingerprint: dict) -> tuple[dict, bool]:
    """One closed-loop group over every case; b-logs in the e3-f4.b-log.v1 row format for the Mac scorer. Resumable."""
    mode = f'part2_{latency}'
    done = load_group_checkpoint(output_dir, group, mode, fingerprint)
    if done is not None:
        return done, True
    blogs = {}
    for cid, meta in pack['cases'].items():
        rows = _rows(pack, cid)
        scene = scene_for(pack, cid)
        dec = H.E8HandoffDecider(ask, case_id=cid, dataset_group=meta['dataset_group'], camera_ids=meta['cameras'],
                                 cands_by_tick={r['tick']: r['cands'] for r in rows}, level=level, scene=scene,
                                 scene_sha256=meta['scene_context_sha256'], latency=latency)
        res = H.run_case(rows, meta['cameras'], pack['root'] / 'part2' / 'cameras.catalog.json', graph, scene, dec)
        blogs[cid] = {'schema_version': 'e3-f4.b-log.v1', 'case_id': cid, 'arm': group, 'k': 1, 'rows': res['rows'], 'calls': [],
                      'e8': {'level': level, 'latency_mode': latency, 'log': res['log']}, 'identity': 'UNCONFIRMED'}
    result = {'group': group, 'level': level, 'latency': latency, 'blogs': blogs,
              'asks': sum(len(b['e8']['log']) for b in blogs.values())}
    save_group_checkpoint(output_dir, group, mode, result, fingerprint)
    return result, False
