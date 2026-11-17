"""Evaluation metrics and statistical tests for Agent decision evaluation (WP4/WP5).

Design: docs/design/AGENT_DECISION_V1.md §3.2, §3.4, §4.2, §4.4.
No actor names are ever included in exported metric structures.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
import hashlib
import json
import math
import random


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def compute_camera_recall(
    covered_frames: Sequence[tuple[str, int]],
    target_gt_frames: Sequence[tuple[str, int]],
) -> dict:
    """Compute per-camera recall R_cam (macro and micro) without exposing actor identifiers."""
    covered_set = {(str(cam), int(ts)) for cam, ts in covered_frames}
    by_cam_total: Counter[str] = Counter()
    by_cam_hit: Counter[str] = Counter()
    for cam, ts in target_gt_frames:
        c = str(cam)
        t = int(ts)
        by_cam_total[c] += 1
        if (c, t) in covered_set:
            by_cam_hit[c] += 1

    per_cam = {
        cam: float(by_cam_hit[cam] / total)
        for cam, total in sorted(by_cam_total.items())
        if total > 0
    }
    total_gt = sum(by_cam_total.values())
    total_hit = sum(by_cam_hit.values())
    macro = float(sum(per_cam.values()) / len(per_cam)) if per_cam else 0.0
    micro = float(total_hit / total_gt) if total_gt > 0 else 0.0
    return {'per_camera': per_cam, 'macro': macro, 'micro': micro}


def compute_switch_metrics(
    switch_count: int,
    false_switch_count: int,
    total_frames: int,
    duration_us: int,
) -> dict:
    """Compute single-view switch ratio and false switch rate FS (per minute)."""
    switch_ratio = float(switch_count / total_frames) if total_frames > 0 else 0.0
    minutes = duration_us / 60_000_000.0 if duration_us > 0 else 0.0
    fs_per_min = float(false_switch_count / minutes) if minutes > 0.0 else 0.0
    return {
        'switch_count': int(switch_count),
        'false_switch_count': int(false_switch_count),
        'switch_ratio': switch_ratio,
        'FS_per_min': fs_per_min,
    }


def compute_fallback_and_call_rates(records: Sequence[Mapping]) -> dict:
    """Compute FB (total and by fallback_reason), TO (timeout rate), and SI (schema invalid rate)."""
    n_steps = len(records)
    fb_reasons: Counter[str] = Counter()
    n_fallback = 0
    total_calls = 0
    timeout_calls = 0
    schema_invalid_calls = 0

    for rec in records:
        if rec.get('decision_source') == 'RULE_FALLBACK':
            n_fallback += 1
            reason = str(rec.get('fallback_reason') or 'UNKNOWN')
            fb_reasons[reason] += 1
        for att in rec.get('attempts', []):
            total_calls += 1
            outcome = att.get('outcome')
            if outcome == 'PROVIDER_TIMEOUT':
                timeout_calls += 1
            elif outcome in ('INVALID_RESPONSE', 'ILLEGAL_CANDIDATE'):
                schema_invalid_calls += 1

    fb_rate = float(n_fallback / n_steps) if n_steps > 0 else 0.0
    fb_by_reason = {k: float(v / n_steps) for k, v in sorted(fb_reasons.items())} if n_steps > 0 else {}
    to_rate = float(timeout_calls / total_calls) if total_calls > 0 else 0.0
    si_rate = float(schema_invalid_calls / total_calls) if total_calls > 0 else 0.0
    return {
        'FB': fb_rate,
        'FB_by_reason': fb_by_reason,
        'TO': to_rate,
        'SI': si_rate,
        'n_steps': n_steps,
        'n_calls': total_calls,
    }


def compute_consistency_k(answers_by_question: Mapping[str, Sequence[str]]) -> dict:
    """Compute Cons_K (exact K-run agreement rate) and Fleiss' kappa across K runs."""
    if not answers_by_question:
        return {'Cons_K': 0.0, 'fleiss_kappa': 0.0, 'n_questions': 0}

    rows = [list(ans) for _, ans in sorted(answers_by_question.items()) if ans]
    if not rows:
        return {'Cons_K': 0.0, 'fleiss_kappa': 0.0, 'n_questions': 0}

    n_items = len(rows)
    k_raters = len(rows[0])
    unanimous = sum(1 for r in rows if len(set(r)) == 1)
    cons_k = float(unanimous / n_items)

    if k_raters <= 1:
        return {'Cons_K': cons_k, 'fleiss_kappa': 1.0, 'n_questions': n_items}

    categories = sorted({a for r in rows for a in r})
    if len(categories) <= 1:
        return {'Cons_K': cons_k, 'fleiss_kappa': 1.0, 'n_questions': n_items}

    p_i_list: list[float] = []
    cat_totals: Counter[str] = Counter()
    for r in rows:
        c = Counter(r)
        for cat, cnt in c.items():
            cat_totals[cat] += cnt
        p_i = sum(cnt * (cnt - 1) for cnt in c.values()) / (k_raters * (k_raters - 1))
        p_i_list.append(p_i)

    p_bar = sum(p_i_list) / n_items
    total_ratings = n_items * k_raters
    p_e = sum((cat_totals[cat] / total_ratings) ** 2 for cat in categories)
    if abs(1.0 - p_e) < 1e-12:
        kappa = 1.0
    else:
        kappa = float((p_bar - p_e) / (1.0 - p_e))
    return {'Cons_K': cons_k, 'fleiss_kappa': kappa, 'n_questions': n_items}


def compute_replay_hash_consistency(replay_runs: Sequence[Sequence[Mapping]]) -> dict:
    """Compute R_hash across multiple replay runs; gate requires R_hash == 1.0 (100%)."""
    if not replay_runs or not replay_runs[0]:
        return {'R_hash': 0.0, 'gate_passed': False, 'status': 'FAIL'}
    n_steps = len(replay_runs[0])
    if any(len(run) != n_steps for run in replay_runs):
        return {'R_hash': 0.0, 'gate_passed': False, 'status': 'FAIL'}

    matched = 0
    for idx in range(n_steps):
        hashes = {hashlib.sha256(canonical_bytes(run[idx])).hexdigest() for run in replay_runs}
        if len(hashes) == 1:
            matched += 1
    r_hash = float(matched / n_steps)
    passed = matched == n_steps
    return {'R_hash': r_hash, 'gate_passed': passed, 'status': 'PASS' if passed else 'FAIL'}


def compute_cost_per_question(records: Sequence[Mapping], price_table: Mapping | None = None) -> dict:
    """Compute cost per question if a dated/sourced price table is provided, else UNKNOWN."""
    if not price_table or not isinstance(price_table.get('models'), Mapping):
        return {'usd_per_question': 'UNKNOWN', 'total_usd': 'UNKNOWN'}
    if not records:
        return {'usd_per_question': 0.0, 'total_usd': 0.0}
    models_prices = price_table['models']
    total_usd = 0.0
    for rec in records:
        model = (rec.get('provider') or {}).get('model')
        if model not in models_prices:
            return {'usd_per_question': 'UNKNOWN', 'total_usd': 'UNKNOWN'}
        p_in = float(models_prices[model]['input_usd_per_mtok'])
        p_out = float(models_prices[model]['output_usd_per_mtok'])
        for att in rec.get('attempts', []):
            pt = int(att.get('prompt_tokens') or 0)
            ct = int(att.get('completion_tokens') or 0)
            total_usd += (pt * p_in + ct * p_out) / 1e6
    return {
        'usd_per_question': float(total_usd / len(records)),
        'total_usd': float(total_usd),
    }


def paired_sign_test(wins_agent: int, wins_baseline: int, *, n_scored: int) -> dict:
    """Exact one-sided sign test (Agent > Baseline) and power verdict (design §3.4, §4.2)."""
    n_discordant = int(wins_agent + wins_baseline)
    if n_scored < 20 or n_discordant < 10:
        verdict = 'INSUFFICIENT'
    elif n_discordant < 30:
        verdict = 'INCONCLUSIVE_UNDERPOWERED'
    else:
        verdict = 'POWERED'

    if n_discordant == 0:
        p_val = 1.0
    else:
        p_val = float(
            sum(math.comb(n_discordant, k) for k in range(wins_agent, n_discordant + 1)) / (2 ** n_discordant)
        )
    return {
        'wins_agent': int(wins_agent),
        'wins_baseline': int(wins_baseline),
        'n_discordant': n_discordant,
        'p_value_one_sided': p_val,
        'verdict': verdict,
    }


def cluster_bootstrap_ci(
    cluster_items: Sequence[tuple[str, float]],
    *,
    n_boot: int = 1000,
    seed: int = 0,
) -> dict:
    """Cluster bootstrap 95% confidence interval by run/cluster."""
    by_cluster: dict[str, list[float]] = {}
    for cid, val in cluster_items:
        by_cluster.setdefault(str(cid), []).append(float(val))
    clusters = sorted(by_cluster.keys())
    n_clusters = len(clusters)
    if n_clusters == 0:
        return {'n_clusters': 0, 'ci95': None, 'status': 'INSUFFICIENT'}

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(n_boot):
        sampled = [clusters[rng.randrange(n_clusters)] for _ in range(n_clusters)]
        vals = [v for c in sampled for v in by_cluster[c]]
        means.append(sum(vals) / len(vals))
    means.sort()
    lo_idx = max(0, int(math.floor(0.025 * len(means))))
    hi_idx = min(len(means) - 1, int(math.ceil(0.975 * len(means))) - 1)
    return {
        'n_clusters': n_clusters,
        'ci95': [float(means[lo_idx]), float(means[hi_idx])],
        'status': 'OK' if n_clusters >= 10 else 'UNDER_10_CLUSTERS',
    }


def holm_bonferroni(p_values: Mapping[str, float], *, alpha: float = 0.05) -> dict[str, dict]:
    """Holm-Bonferroni step-down multiple-testing correction."""
    ordered = sorted(p_values.items(), key=lambda kv: kv[1])
    m = len(ordered)
    out: dict[str, dict] = {}
    prev_adj = 0.0
    still_rejecting = True
    for i, (name, p) in enumerate(ordered):
        adj = min(1.0, max(prev_adj, float(p) * (m - i)))
        prev_adj = adj
        if adj > alpha:
            still_rejecting = False
        out[name] = {'p_raw': float(p), 'p_holm': adj, 'reject': still_rejecting}
    return out
