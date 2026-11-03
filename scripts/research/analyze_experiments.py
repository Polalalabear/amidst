#!/usr/bin/env python3
"""Metric tables (CSV + Markdown) and charts (PNG + SVG) for M1..M4 of the research plan #397.

  analyze_experiments.py m1 RESULTS.json --out DIR [--agent-arm AGENT_SEQUENTIAL]
  analyze_experiments.py m2 RESULTS.json --out DIR
  analyze_experiments.py m3 RESULTS.json --queries QUERIES.csv --out DIR
  analyze_experiments.py m4 RESULTS.json --out DIR

Input contract: scripts/research/README.md. UNKNOWN / missing values are shown as UNKNOWN and excluded
from numerators and denominators; nothing is imputed. Hypothesis verdict labels (plan 1.6) need the
Holm family and the gates across modules, so this script reports counts and p-values, and writes the
verdict as UNKNOWN. M3 reads only rows with evaluation_eligible=true.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402
import _q2  # noqa: E402

UNK = c.UNKNOWN
FAIR_FIELDS = ('parameter_set_sha256', 'candidate_snapshot_sha256', 'env_manifest_sha256')
FB_GATE = 20.0
LLM_SHARE_GATE = 50.0


def fmt_prop(d):
    return d['pct'], d['lo'], d['hi'], d['n']


# ------------------------------------------------------------------ M1

def m1_pairs(data, agent_arm):
    """Return fair units and the list of INVALID_COMPARISON reasons (plan 3.2)."""
    runs = defaultdict(dict)
    for r in data.get('runs', []):
        runs[(r['run_id'], r.get('request_sha256'))][r.get('arm')] = r
    invalid, valid_keys = [], set()
    for key, arms in sorted(runs.items(), key=lambda kv: str(kv[0])):
        if 'RULE_ONLY' not in arms or agent_arm not in arms:
            invalid.append((key[0], 'ARM_MISSING'))
            continue
        bad = [f for f in FAIR_FIELDS if c.is_unknown(arms['RULE_ONLY'].get(f)) or arms['RULE_ONLY'].get(f) != arms[agent_arm].get(f)]
        if bad:
            invalid.append((key[0], 'INVALID_COMPARISON:' + ','.join(bad)))
        else:
            valid_keys.add(key)
    scores = defaultdict(lambda: defaultdict(list))
    for e in data.get('events', []):
        key = (e['run_id'], e.get('request_sha256'))
        if key not in valid_keys or e.get('arm') not in ('RULE_ONLY', agent_arm) or e.get('scored') is not True:
            continue
        m = c.flag(e.get('match'))
        if m is not None:
            scores[(key, e['event_id'])][e['arm']].append(int(m))
    units = []
    for (key, event_id), arms in sorted(scores.items(), key=lambda kv: str(kv[0])):
        if arms.get('RULE_ONLY') and arms.get(agent_arm):
            units.append({'run_id': key[0], 'event_id': event_id, 'rule': statistics.mean(arms['RULE_ONLY']),
                          'agent': statistics.mean(arms[agent_arm])})
    return units, valid_keys, invalid


def m1(data, a):
    agent_arm = a.agent_arm
    units, valid, invalid = m1_pairs(data, agent_arm)
    plt, t = c.plt_setup(a.theme)
    b = a.bootstrap_b
    exploratory = agent_arm == 'AGENT_SEQUENTIAL_RELAXED'
    rows = []
    for arm in ('RULE_ONLY', agent_arm):
        sel = lambda rs: [r for r in rs if r.get('arm') == arm and (r['run_id'], r.get('request_sha256')) in valid]  # noqa: E731
        ev, st, ca, ru = (sel(data.get(k, [])) for k in ('events', 'steps', 'calls', 'runs'))
        scored, ns, unk = _q2.event_split(ev)
        cu = c.prop(_q2.by_run(units, lambda u, arm=arm: u['rule' if arm == 'RULE_ONLY' else 'agent']), b)
        lat = c.median_stat(_q2.by_run([e for e in scored if e['match']], lambda e: c.num(e.get('latency_ms'))), b)
        ms = c.median_stat(_q2.by_run(st, lambda s: c.num(s.get('step_ms'))), b)
        row = {'arm': arm + ('  [EXPLORATORY]' if exploratory and arm != 'RULE_ONLY' else ''),
               'K': len({e.get('repeat') for e in ev}) or UNK, 'n_units_paired': cu['n'],
               'C_evt_pct': cu['pct'], 'C_evt_lo': cu['lo'], 'C_evt_hi': cu['hi'],
               'L_sw_median_ms': lat['median'], 'L_sw_lo': lat['lo'], 'L_sw_hi': lat['hi'],
               'FS_per_min': (sum(c.num(r.get('false_switch_count')) or 0 for r in ru) / sum(c.num(r.get('scoped_minutes')) or 0 for r in ru))
               if ru and all(c.num(r.get('false_switch_count')) is not None and c.num(r.get('scoped_minutes')) for r in ru) else UNK,
               'T_step_median_ms': ms['median'], 'T_step_p90_ms': ms['p90']}
        if arm == 'RULE_ONLY':
            row.update(TO_pct='n/a', SI_pct='n/a', FB_pct='n/a', K_call_per_step='n/a', call_ms_median='n/a', tokens_per_call='n/a')
        else:
            to, si, fb = _q2.agent_rates(ca, st, b)
            toks = [(c.num(x.get('prompt_tokens')), c.num(x.get('completion_tokens'))) for x in ca]
            row.update(TO_pct=to['pct'], TO_lo=to['lo'], TO_hi=to['hi'], TO_n_calls=to['n'],
                       SI_pct=si['pct'], SI_lo=si['lo'], SI_hi=si['hi'],
                       FB_pct=fb['pct'], FB_lo=fb['lo'], FB_hi=fb['hi'], FB_n_steps=fb['n'],
                       K_call_per_step=len(ca) / len(st) if st else UNK,
                       call_ms_median=c.median_stat({'all': [x for x in (c.num(y.get('duration_ms')) for y in ca) if x is not None]}, b)['median'],
                       tokens_per_call=statistics.mean(p + q for p, q in toks) if toks and all(p is not None and q is not None for p, q in toks) else UNK)
        rows.append(row)
    wins = sum(u['agent'] > u['rule'] for u in units)
    losses = sum(u['agent'] < u['rule'] for u in units)
    ties = len(units) - wins - losses
    diffs = _q2.by_run(units, lambda u: u['agent'] - u['rule'])
    ci = c.cluster_bootstrap(diffs, lambda xs: 100 * statistics.mean(xs) if xs else None, b) if units else None
    fb_pct = rows[1]['FB_pct']
    ev_agent = [e for e in data.get('events', []) if e.get('arm') == agent_arm and (e['run_id'], e.get('request_sha256')) in valid]
    excluded = Counter()
    for e in ev_agent:
        if e.get('decision_source') == 'RULE_FALLBACK':
            excluded['RULE_FALLBACK_not_agent_evidence'] += 1
        if e.get('scored') is not True:
            excluded[f"not_scored:{e.get('not_scored_label') or UNK}"] += 1
    n_inv = Counter(reason for _, reason in invalid)
    excluded.update({f'pair:{k}': v for k, v in n_inv.items()})
    h1 = {'arm_compared': agent_arm, 'n_pairs': len(units), 'n_tie': ties, 'n_agent_better': wins, 'n_rule_better': losses,
          'diff_C_evt_pp': 100 * statistics.mean(u['agent'] - u['rule'] for u in units) if units else UNK,
          'diff_lo': ci[0] if ci else UNK, 'diff_hi': ci[1] if ci else UNK,
          'p_one_sided': c.sign_test_one_sided(wins, losses) if losses + wins else UNK,
          'p_holm': UNK, 'p_reverse_one_sided': c.sign_test_one_sided(losses, wins) if losses + wins else UNK,
          'p_reverse_holm': UNK,
          'gate_FB': UNK if isinstance(fb_pct, str) else ('PASS' if fb_pct <= FB_GATE else 'FAIL'),
          'verdict': UNK if not exploratory else 'EXPLORATORY_NOT_IN_H1',
          'excluded_counts': '; '.join(f'{k}={v}' for k, v in sorted(excluded.items())) or 'NONE'}
    notes = ['p_holm / p_reverse_holm / verdict are UNKNOWN: Holm runs across the H1 family and the verdict needs gates from other modules (plan 1.5, 1.6).',
             f'Pairs with unfair setup (plan 3.2) excluded as INVALID_COMPARISON: {len(invalid)}.' + (' ' + ', '.join(f'{r}:{why}' for r, why in invalid) if invalid else ''),
             'C_evt for the agent arm is the mean of K repeats per unit (plan 3.2); its Wilson CI (single run) treats that mean as a count and is approximate.']
    if exploratory:
        notes.append('EXPLORATORY: relaxed-timeout arm never enters the H1-Q2 verdict (plan 3.12).')
    if data['source_class'] != 'FORMAL':
        notes.append(f"source_class {data['source_class']}: not formal evidence.")
    cols1 = ['arm', 'K', 'n_units_paired', 'C_evt_pct', 'C_evt_lo', 'C_evt_hi', 'L_sw_median_ms', 'L_sw_lo', 'L_sw_hi', 'FS_per_min', 'TO_pct', 'TO_lo', 'TO_hi',
             'TO_n_calls', 'SI_pct', 'SI_lo', 'SI_hi', 'FB_pct', 'FB_lo', 'FB_hi', 'FB_n_steps', 'K_call_per_step', 'call_ms_median', 'tokens_per_call',
             'T_step_median_ms', 'T_step_p90_ms']
    suffix = '_relaxed' if exploratory else ''
    c.write_table(a.out, f'm1_M1-1{suffix}', cols1, rows, 'Table M1-1 per-arm comparison numbers', c.banner(data), notes)
    cols2 = list(h1)
    c.write_table(a.out, f'm1_M1-2{suffix}', cols2, [h1], 'Table M1-2 hypothesis test counts', c.banner(data), notes)
    made = m1_charts(plt, t, data, a, units, rows, valid, agent_arm)
    print(f'M1: {len(units)} paired units, {len(invalid)} invalid pairs; wrote tables and {len(made)} chart files to {a.out}')


def m1_charts(plt, t, data, a, units, rows, valid, agent_arm):
    banner, made = c.banner(data), []
    fig, ax = c.new_fig(plt, 'G-M1a  Paired unit accuracy, RULE vs Agent', banner,
                        subtitle=f"n={len(units)} units, ties={sum(u['agent'] == u['rule'] for u in units)}, discordant={sum(u['agent'] != u['rule'] for u in units)}")
    for i, u in enumerate(units):
        color = t['s1'] if u['agent'] > u['rule'] else (t['s2'] if u['agent'] < u['rule'] else t['muted'])
        jitter = (i % 7 - 3) * 0.012
        ax.plot([0 + jitter, 1 + jitter], [u['rule'], u['agent']], color=color, lw=1.2, alpha=0.8, marker='o', ms=4)
    ax.plot([], [], color=t['s1'], label='Agent better')
    ax.plot([], [], color=t['s2'], label='RULE better')
    ax.plot([], [], color=t['muted'], label='tie')
    ax.legend(frameon=False, fontsize=8, loc='upper left', bbox_to_anchor=(1.0, 1.0))
    ax.set_xticks([0, 1], ['RULE_ONLY', agent_arm], fontsize=8)
    ax.set_xlim(-0.3, 1.3)
    ax.set_ylim(-0.05, 1.05)
    ax.set_ylabel('unit accuracy (0..1)')
    made += c.save_fig(fig, a.out, 'G-M1a_paired')

    steps = [s for s in data.get('steps', []) if s.get('arm') == agent_arm and (s['run_id'], s.get('request_sha256')) in valid]
    runs = sorted({s['run_id'] for s in steps})
    fig, ax = c.new_fig(plt, 'G-M1b  Decision source share, Agent arm', banner, subtitle='share of decision steps; dashed line = 20% fallback gate')
    for i, run in enumerate(runs):
        ss = [s for s in steps if s['run_id'] == run and not c.is_unknown(s.get('decision_source'))]
        fb = 100 * sum(s['decision_source'] == 'RULE_FALLBACK' for s in ss) / len(ss) if ss else None
        if fb is None:
            ax.text(i, 50, 'UNKNOWN', ha='center', color=t['ink2'])
            continue
        ax.bar(i, 100 - fb, 0.55, color=t['s1'], label='AGENT' if i == 0 else None)
        ax.bar(i, fb, 0.55, bottom=100 - fb, color=t['s2'], label='RULE_FALLBACK' if i == 0 else None, edgecolor=t['bg'], linewidth=2)
        ax.text(i, 100 - fb / 2, f'{fb:.0f}%', ha='center', va='center', fontsize=8, color='#ffffff')
        ax.text(i, 102, f'n={len(ss)}' + (' >20%' if fb > FB_GATE else ''), ha='center', fontsize=8)
    ax.axhline(100 - FB_GATE, color=t['ink2'], ls='--', lw=1)
    ax.set_xticks(range(len(runs)), runs, fontsize=8)
    ax.set_ylim(0, 112)
    ax.set_ylabel('% of decision steps')
    if runs:
        ax.legend(frameon=False, fontsize=8, loc='upper left', bbox_to_anchor=(1.0, 1.0))
    made += c.save_fig(fig, a.out, 'G-M1b_decision_source')

    fig, ax = c.new_fig(plt, 'G-M1d  Switch latency ECDF (matched events)', banner)
    for arm, color in (('RULE_ONLY', t['s1']), (agent_arm, t['s2'])):
        vals = sorted(v for v in (c.num(e.get('latency_ms')) for e in data.get('events', [])
                      if e.get('arm') == arm and e.get('scored') is True and e.get('match') is True and (e['run_id'], e.get('request_sha256')) in valid) if v is not None)
        if vals:
            ax.step(vals, [(i + 1) / len(vals) for i in range(len(vals))], where='post', color=color, lw=2, label=f'{arm} (n={len(vals)})')
        else:
            ax.plot([], [], color=color, label=f'{arm} (UNKNOWN)')
    ax.set_xlabel('L_sw (ms)')
    ax.set_ylabel('cumulative share')
    ax.set_ylim(0, 1.02)
    ax.legend(frameon=False, fontsize=8, loc='lower right')
    made += c.save_fig(fig, a.out, 'G-M1d_latency_ecdf')

    ar = rows[1]
    fig, ax = c.new_fig(plt, 'G-M1e  Agent failure rates', banner, subtitle='whiskers: 95% CI; TO, SI over calls, FB over decision steps')
    stats = [{'pct': ar.get(f'{k}_pct', UNK), 'lo': ar.get(f'{k}_lo', UNK), 'hi': ar.get(f'{k}_hi', UNK),
              'n': ar.get('TO_n_calls' if k != 'FB' else 'FB_n_steps', 0)} for k in ('TO', 'SI', 'FB')]
    c.bar_ci(ax, t, ['TO\n(calls)', 'SI\n(calls)', 'FB\n(steps)'], stats, t['s2'])
    ax.set_xticks(range(3), ['TO (calls)', 'SI (calls)', 'FB (steps)'], fontsize=8)
    ax.set_ylabel('%')
    made += c.save_fig(fig, a.out, 'G-M1e_failure_rates')
    return made


# ------------------------------------------------------------------ M2

def m2(data, a):
    ev = data.get('events', [])
    std = [e for e in ev if e.get('category') == 'STANDARD']
    both = [e for e in std if e.get('v1_label') in ('MATCH', 'MISMATCH') and e.get('v2_label') in ('MATCH', 'MISMATCH')]
    dis = [e for e in both if e['v1_label'] != e['v2_label']]
    ns = [e for e in ev if e.get('category') != 'STANDARD']
    known_ns = [e for e in ns if not c.is_unknown(e.get('v2_expected_label'))]
    ok_ns = [e for e in known_ns if e['v2_label'] == e['v2_expected_label']]
    rn, rs = c.num(data.get('recompute', {}).get('n')), c.num(data.get('recompute', {}).get('same_n'))
    row = {'n_std_both_scored': len(both), 'A_std_pct': 100 * (len(both) - len(dis)) / len(both) if both else UNK,
           'n_disagree': len(dis), 'disagree_rule_refs': '; '.join(f"{e['event_id']}:{e.get('rule_ref') or UNK}" for e in dis) or 'NONE',
           'n_not_scored_events': len(ns), 'n_not_scored_expected_unknown': len(ns) - len(known_ns),
           'L_ns_pct': 100 * len(ok_ns) / len(known_ns) if known_ns else UNK,
           'R_v2_pct': 100 * rs / rn if rn and rs is not None else UNK,
           'gate_A_std_ge_99': UNK if not both else ('PASS' if (len(both) - len(dis)) / len(both) >= 0.99 else 'FAIL'),
           'gate_L_ns_eq_100': UNK if not known_ns else ('PASS' if len(ok_ns) == len(known_ns) else 'FAIL'),
           'gate_R_v2_eq_100': UNK if not (rn and rs is not None) else ('PASS' if rs == rn else 'FAIL')}
    cols = list(row)
    notes = ['Events whose label is UNKNOWN on either side are left out of A_std; not-scored events without v2_expected_label are left out of L_ns (counted above).']
    c.write_table(a.out, 'm2_M2-1', cols, [row], 'Table M2-1 scorer v1 vs v2', c.banner(data), notes)
    labels = sorted({e.get('v1_label', UNK) for e in ev} | {e.get('v2_label', UNK) for e in ev}, key=str)
    counts = Counter((e.get('v1_label', UNK), e.get('v2_label', UNK)) for e in ev)
    plt, t = c.plt_setup(a.theme)
    fig, ax = c.new_fig(plt, 'G-M2a  Scorer v1 x v2 labels', c.banner(data), size=(7.5, 5.2), subtitle=f'n={len(ev)} events; rows v1, columns v2')
    ax.grid(False)
    for i, l1 in enumerate(labels):
        for j, l2 in enumerate(labels):
            n = counts.get((l1, l2), 0)
            ax.add_patch(plt.Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=t['s1'] if (n and l1 == l2) else t['bg'],
                                       alpha=min(1, 0.25 + 0.2 * n) if (n and l1 == l2) else 1,
                                       edgecolor=t['s2'] if (n and l1 != l2) else t['grid'], lw=2 if (n and l1 != l2) else 0.8, hatch='///' if (n and l1 != l2) else None))
            if n:
                ax.text(j, i, str(n), ha='center', va='center', fontsize=9)
    ax.set_xlim(-0.5, len(labels) - 0.5)
    ax.set_ylim(len(labels) - 0.5, -0.5)
    ax.set_xticks(range(len(labels)), labels, rotation=40, ha='right', fontsize=7)
    ax.set_yticks(range(len(labels)), labels, fontsize=7)
    ax.set_xlabel('v2 label')
    ax.set_ylabel('v1 label')
    made = c.save_fig(fig, a.out, 'G-M2a_confusion')
    print(f'M2: A_std={c.cell(row["A_std_pct"])} L_ns={c.cell(row["L_ns_pct"])} R_v2={c.cell(row["R_v2_pct"])}; wrote {len(made)} chart files to {a.out}')


# ------------------------------------------------------------------ M3

NOT_APPROVED = '評測集未核定 (evaluation set not approved): no rows with evaluation_eligible=true; M3 outputs are empty.'
FIELDS = ('intent', 'class', 'color', 'time_us', 'camera', 'region')
M3_COLUMNS = ['arm', 'wording_type', 'n_questions_scored', 'E_q3_pct', 'E_q3_lo', 'E_q3_hi', 'P_cam_pct', 'R_cam_pct',
              'LLM_share_pct'] + [f'F_q3_{f}_pct' for f in FIELDS]


def eligible_queries(path):
    """Rows with evaluation_eligible=true. A missing column or any other value is NOT eligible."""
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle))
    has_col = bool(rows) and 'evaluation_eligible' in rows[0]
    keep = [r for r in rows if str(r.get('evaluation_eligible', '')).strip().lower() == 'true']
    return keep, len(rows), has_col


def m3(data, a):
    queries, total, has_col = eligible_queries(a.queries)
    if not queries:
        c.write_table(a.out, 'm3_M3-1', M3_COLUMNS, [], 'Table M3-1 (EMPTY)', c.banner(data),
                      [NOT_APPROVED, f"query rows read: {total}; evaluation_eligible column {'present' if has_col else 'ABSENT (treated as not eligible)'}."])
        print('WARNING: ' + NOT_APPROVED)
        return
    meta = {q['query_id']: q for q in queries}
    qs = [x for x in data.get('questions', []) if x.get('query_id') in meta]
    dropped = len(data.get('questions', [])) - len(qs)
    plt, t = c.plt_setup(a.theme)
    rows, per_arm_wt = [], {}
    arms = sorted({x['arm'] for x in qs}, key=lambda s: (s != 'RULE_ONLY', s))
    for arm in arms:
        for wt in ['ALL'] + sorted({meta[x['query_id']]['wording_type'] for x in qs}):
            sel = [x for x in qs if x['arm'] == arm and (wt == 'ALL' or meta[x['query_id']]['wording_type'] == wt)]
            fam = lambda x: meta[x['query_id']]['family_id']  # noqa: E731
            known = [x for x in sel if c.flag(x.get('correct')) is not None]
            e = c.prop(_group(known, fam, lambda x: int(x['correct'])), a.bootstrap_b)
            tp = sum(c.num(x.get('camera_tp')) or 0 for x in sel)
            fp = sum(c.num(x.get('camera_fp')) or 0 for x in sel)
            fn = sum(c.num(x.get('camera_fn')) or 0 for x in sel)
            cam_known = all(c.num(x.get(k)) is not None for x in sel for k in ('camera_tp', 'camera_fp', 'camera_fn')) and sel
            row = {'arm': arm, 'wording_type': wt, 'n_questions_scored': e['n'], 'E_q3_pct': e['pct'], 'E_q3_lo': e['lo'], 'E_q3_hi': e['hi'],
                   'P_cam_pct': 100 * tp / (tp + fp) if cam_known and tp + fp else UNK, 'R_cam_pct': 100 * tp / (tp + fn) if cam_known and tp + fn else UNK,
                   'LLM_share_pct': (100 * sum(x.get('parsed_by') == 'LLM' for x in sel) / len(sel) if sel and arm != 'RULE_ONLY' and all(not c.is_unknown(x.get('parsed_by')) for x in sel) else ('n/a' if arm == 'RULE_ONLY' else UNK))}
            for f in FIELDS:
                fk = [x for x in sel if c.flag(x.get('field_correct', {}).get(f)) is not None]
                row[f'F_q3_{f}_pct'] = 100 * sum(x['field_correct'][f] for x in fk) / len(fk) if fk else UNK
            rows.append(row)
            per_arm_wt[(arm, wt)] = (e, row)
    base_arm = arms[0]
    llm_arms = [x for x in arms if x != base_arm]
    h = []
    for other in llm_arms:
        paired = defaultdict(dict)
        for x in qs:
            if x['arm'] in (base_arm, other) and c.flag(x.get('correct')) is not None:
                paired[x['query_id']][x['arm']] = int(x['correct'])
        pairs = [p for p in paired.values() if base_arm in p and other in p]
        w = sum(p[other] > p[base_arm] for p in pairs)
        l = sum(p[other] < p[base_arm] for p in pairs)
        share = per_arm_wt[(other, 'ALL')][1]['LLM_share_pct']
        h.append({'hypothesis': 'H1-Q3', 'comparison': f'{other} vs {base_arm}', 'n_pairs': len(pairs), 'n_both_right': sum(p[other] and p[base_arm] for p in pairs),
                  'n_both_wrong': sum(not p[other] and not p[base_arm] for p in pairs), 'n_llm_better': w, 'n_base_better': l,
                  'p_one_sided': c.sign_test_one_sided(w, l) if w + l else UNK, 'p_holm': UNK,
                  'gate_LLM_share': UNK if isinstance(share, str) else ('PASS' if share >= LLM_SHARE_GATE else 'FAIL'),
                  'verdict': UNK})
        # H1-QW: per family d = G_PV(base) - G_PV(LLM)
        fam_acc = defaultdict(lambda: defaultdict(list))
        for x in qs:
            if c.flag(x.get('correct')) is not None:
                fam_acc[meta[x['query_id']]['family_id']][(x['arm'], meta[x['query_id']]['wording_type'])].append(int(x['correct']))
        ds = []
        for fam, acc in fam_acc.items():
            try:
                g = {arm: statistics.mean(acc[(arm, 'P')]) - statistics.mean(acc[(arm, 'V')]) for arm in (base_arm, other)}
            except (KeyError, statistics.StatisticsError):
                continue
            ds.append(g[base_arm] - g[other])
        w2, l2 = sum(d > 0 for d in ds), sum(d < 0 for d in ds)
        h.append({'hypothesis': 'H1-QW', 'comparison': f'{other} vs {base_arm}', 'n_pairs': len(ds), 'n_both_right': UNK, 'n_both_wrong': UNK,
                  'n_llm_better': w2, 'n_base_better': l2, 'p_one_sided': c.sign_test_one_sided(w2, l2) if w2 + l2 else UNK,
                  'p_holm': UNK, 'gate_LLM_share': share if isinstance(share, str) else ('PASS' if share >= LLM_SHARE_GATE else 'FAIL'), 'verdict': UNK})
    notes = [f'Eligible query rows: {len(queries)} of {total}; result rows dropped (query not eligible / not in set): {dropped}.',
             'Verdict and p_holm are UNKNOWN: Holm runs across H1-Q3, H1-Q1, H1-QW, H1-Q2 (plan 1.5).',
             'H1-QW: unit = question family; d = G_PV(base) - G_PV(LLM); families lacking P or V questions are skipped. event_class groups are not split here (UNKNOWN: the three event groups are not user-confirmed).']
    if data['source_class'] != 'FORMAL':
        notes.append(f"source_class {data['source_class']}: not formal evidence.")
    c.write_table(a.out, 'm3_M3-1', M3_COLUMNS, rows, 'Table M3-1 Q3/Q1 per arm and wording type', c.banner(data), notes)
    c.write_table(a.out, 'm3_M3-2', list(h[0]) if h else ['hypothesis'], h, 'Table M3-2 hypothesis test counts', c.banner(data), notes)
    made = m3_charts(plt, t, data, a, per_arm_wt, arms, h)
    print(f'M3: {len(queries)} eligible queries; wrote tables and {len(made)} chart files to {a.out}')


def _group(items, key_fn, value_fn):
    g = defaultdict(list)
    for x in items:
        g[key_fn(x)].append(value_fn(x))
    return g


def m3_charts(plt, t, data, a, per_arm_wt, arms, h):
    banner, made = c.banner(data), []
    present = {wt for (_, wt) in per_arm_wt if wt != 'ALL'}
    wts = [w for w in 'PVTC' if w in present] + sorted(present - set('PVTC'))
    fig, ax = c.new_fig(plt, 'G-M3a  Q3 field accuracy', banner, subtitle='per arm; fields accuracy %', size=(8.5, 4.4))
    cols = ['E_q3'] + [f'F_q3_{f}' for f in FIELDS]
    w = 0.8 / max(1, len(arms))
    for k, arm in enumerate(arms):
        row = per_arm_wt[(arm, 'ALL')][1]
        vals = [row['E_q3_pct']] + [row[f'F_q3_{f}_pct'] for f in FIELDS]
        for i, v in enumerate(vals):
            x = i + (k - (len(arms) - 1) / 2) * w
            if isinstance(v, str):
                ax.bar(x, 100, w * 0.9, fill=False, hatch='///', edgecolor=t['muted'])
                continue
            ax.bar(x, v, w * 0.9, color=[t['s1'], t['s2']][k % 2], label=arm if i == 0 else None, edgecolor=t['bg'], linewidth=1)
            ax.text(x, v + 1, f'{v:.0f}', ha='center', fontsize=7)
    ax.set_xticks(range(len(cols)), ['whole'] + list(FIELDS), fontsize=8)
    ax.set_ylim(0, 112)
    ax.set_ylabel('%')
    ax.legend(frameon=False, fontsize=8, loc='upper left', bbox_to_anchor=(1.0, 1.0))
    made += c.save_fig(fig, a.out, 'G-M3a_field_accuracy')

    fig, ax = c.new_fig(plt, 'G-M3e  E_q3 by wording type', banner, subtitle='P precise, V vague, T time, C combined; numbers = n')
    for k, arm in enumerate(arms):
        xs, ys, los, his, ns = [], [], [], [], []
        for i, wt in enumerate(wts):
            e = per_arm_wt[(arm, wt)][0]
            if isinstance(e['pct'], str):
                continue
            xs.append(i); ys.append(e['pct']); ns.append(e['n'])
            los.append(e['pct'] - e['lo'] if not isinstance(e['lo'], str) else 0)
            his.append(e['hi'] - e['pct'] if not isinstance(e['hi'], str) else 0)
        ax.errorbar(xs, ys, yerr=[los, his], color=[t['s1'], t['s2']][k % 2], marker='o', lw=2, capsize=3, label=arm)
        for x, y, n in zip(xs, ys, ns):
            ax.text(x + (0.06 if k else -0.06), y + (4 if k else -9), f'n={n}', ha='left' if k else 'right', fontsize=7)
    ax.set_xticks(range(len(wts)), wts)
    ax.set_ylim(0, 112)
    ax.set_ylabel('E_q3 (%)')
    ax.legend(frameon=False, fontsize=8, loc='upper left', bbox_to_anchor=(1.0, 1.0))
    made += c.save_fig(fig, a.out, 'G-M3e_wording')
    return made


# ------------------------------------------------------------------ M4

def m4(data, a):
    plt, t = c.plt_setup(a.theme)
    rows = []
    base = data.get('baseline', {})
    for m in data.get('models', []):
        name = m['model']
        calls = [x for x in data.get('calls', []) if x.get('model') == name]
        durs = {'all': [v for v in (c.num(x.get('duration_ms')) for x in calls) if v is not None]}
        dm = c.median_stat(durs, a.bootstrap_b)
        to = c.prop(_q2.by_run(calls, lambda x: int(x.get('error_code') == _q2.CALL_ERROR_TO)), a.bootstrap_b)
        si = c.prop(_q2.by_run(calls, lambda x: int(x.get('error_code') == _q2.CALL_ERROR_SI)), a.bootstrap_b)
        for module, key, unit_key in (('Q2', 'events', 'match'), ('Q3', 'questions', 'correct')):
            items = [x for x in data.get(key, []) if x.get('model') == name and c.flag(x.get(unit_key)) is not None]
            p = c.prop(_q2.by_run(items, lambda x, k=unit_key: int(x[k])), a.bootstrap_b)
            b0 = c.num(base.get(module))
            rows.append({'model': name, 'module': module, 'llm_digest': m.get('llm_digest', UNK), 'quant': m.get('quant', UNK),
                         'llm_loaded_size_gib': m.get('llm_loaded_size_gib', UNK), 'peak_rss_gib': m.get('peak_rss_gib', UNK),
                         'llm_processor': m.get('llm_processor', UNK), 'n': p['n'], 'score_pct': p['pct'], 'score_lo': p['lo'], 'score_hi': p['hi'],
                         'baseline_pct': b0 if b0 is not None else UNK, 'diff_pp': (p['pct'] - b0) if b0 is not None and not isinstance(p['pct'], str) else UNK,
                         'TO_pct': to['pct'], 'SI_pct': si['pct'], 'call_ms_median': dm['median'], 'call_ms_p90': dm['p90'], 'n_calls': dm['n']})
    cols = list(rows[0]) if rows else ['model']
    c.write_table(a.out, 'm4_M4-1', cols, rows, 'Table M4-1 candidate models [EXPLORATORY]', c.banner(data),
                  ['All M4 results are EXPLORATORY (plan 6.5). H1 uses only the pre-fixed model.', 'Score is C_evt (Q2) or E_q3 (Q3), see module column.'])
    made = []
    for module in ('Q2', 'Q3'):
        mr = [r for r in rows if r['module'] == module]
        fig, ax = c.new_fig(plt, f'G-M4  Cost vs score, {module}  [EXPLORATORY]', c.banner(data),
                            subtitle='x: median call ms (log), y: score %, size: loaded GiB, hatched ring = size UNKNOWN')
        for r in mr:
            if isinstance(r['call_ms_median'], str) or isinstance(r['score_pct'], str):
                continue
            size = r['llm_loaded_size_gib']
            s = 60 + 90 * size if not isinstance(size, str) else 90
            ax.scatter(r['call_ms_median'], r['score_pct'], s=s, color=t['s1'], edgecolor=t['bg'], linewidth=2, zorder=3,
                       hatch=None if not isinstance(size, str) else '///')
            if not isinstance(r['score_lo'], str):
                ax.errorbar(r['call_ms_median'], r['score_pct'], yerr=[[r['score_pct'] - r['score_lo']], [r['score_hi'] - r['score_pct']]], color=t['ink2'], lw=1, capsize=3, zorder=2)
            ax.annotate(f"{r['model']}\nn={r['n']}", (r['call_ms_median'], r['score_pct']), textcoords='offset points', xytext=(8, 6), fontsize=7)
        b0 = c.num(base.get(module))
        if b0 is not None:
            ax.axhline(b0, color=t['ink2'], ls='--', lw=1)
            ax.text(0.01, b0, 'Baseline', transform=ax.get_yaxis_transform(), ha='left', va='bottom', fontsize=8)
        else:
            ax.text(0.99, 0.02, 'Baseline: UNKNOWN', transform=ax.transAxes, ha='right', fontsize=8, color=t['ink2'])
        ax.set_xscale('log')
        ax.set_ylim(0, 105)
        ax.set_xlabel('median call latency (ms, log)')
        ax.set_ylabel('score (%)')
        made += c.save_fig(fig, a.out, f'G-M4_{module}')
    print(f'M4: {len(rows)} model-module rows; wrote {len(made)} chart files to {a.out}')


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('m1', 'm2', 'm3', 'm4'):
        s = sub.add_parser(name)
        s.add_argument('results', type=Path)
        s.add_argument('--out', type=Path, required=True)
        s.add_argument('--theme', choices=['light', 'dark'], default='light')
        s.add_argument('--bootstrap-b', type=int, default=c.BOOTSTRAP_B)
        if name == 'm1':
            s.add_argument('--agent-arm', default='AGENT_SEQUENTIAL', choices=['AGENT_SEQUENTIAL', 'AGENT_SEQUENTIAL_RELAXED'])
        if name == 'm3':
            s.add_argument('--queries', type=Path, required=True)
    a = p.parse_args(argv)
    data = c.load_results(a.results, a.cmd.upper())
    {'m1': m1, 'm2': m2, 'm3': m3, 'm4': m4}[a.cmd](data, a)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
