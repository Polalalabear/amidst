#!/usr/bin/env python3
"""Baseline table B-1 (and charts G-B1..G-B3) from a CX-8 RULE_ONLY result file.

Input contract: scripts/research/README.md section "Input contract" (amidst.research-results.v0-draft,
experiment BASELINE). Reads only the result file. Never reads GT or recordings. UNKNOWN stays UNKNOWN.
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common as c  # noqa: E402
import _q2  # noqa: E402

COLUMNS = [
    'row', 'run_id', 'scene', 'request_sha256', 'source_class', 'fps', 'n_events_scored', 'n_events_not_scored',
    'not_scored_breakdown', 'n_match_unknown', 'C_evt_pct', 'C_evt_lo', 'C_evt_hi', 'C_evt_method',
    'L_sw_median_ms', 'L_sw_lo', 'L_sw_hi', 'L_sw_p90_ms', 'L_sw_n', 'L_sw_n_unknown', 'FS_per_min',
    'M_honest_pct', 'M_honest_lo', 'M_honest_hi', 'M_honest_n', 'T_step_median_ms', 'T_step_p90_ms',
    'R_hash_pct', 'recording_sha256', 'scorer_output_sha256', 'env_manifest_sha256',
]


def select(rows, run_ids, request=None):
    return [r for r in rows if r.get('run_id') in run_ids and (request is None or r.get('request_sha256') in (request, None))]


def build_rows(data, b=None):
    runs = [r for r in data.get('runs', []) if r.get('arm') == 'RULE_ONLY']
    ignored = sum(1 for r in data.get('events', []) if r.get('arm') != 'RULE_ONLY')
    rows, groups = [], defaultdict(list)

    def one(label, run_rows):
        ids = {r['run_id'] for r in run_rows}
        req = run_rows[0].get('request_sha256') if len(run_rows) == 1 else None
        ev = [e for e in select(data.get('events', []), ids, req) if e.get('arm') == 'RULE_ONLY']
        st = [s for s in select(data.get('steps', []), ids, req) if s.get('arm') == 'RULE_ONLY']
        hs = [h for h in select(data.get('honesty_steps', []), ids, req) if h.get('arm') == 'RULE_ONLY']
        row = {'row': label, 'run_id': run_rows[0]['run_id'] if len(run_rows) == 1 else 'ALL',
               'scene': run_rows[0].get('scene', c.UNKNOWN) if len(run_rows) == 1 else label.split(':')[-1],
               'request_sha256': run_rows[0].get('request_sha256', c.UNKNOWN) if len(run_rows) == 1 else 'ALL',
               'source_class': data['source_class'], 'fps': run_rows[0].get('fps', c.UNKNOWN) if len(run_rows) == 1 else c.UNKNOWN,
               'recording_sha256': run_rows[0].get('recording_sha256', c.UNKNOWN) if len(run_rows) == 1 else 'ALL',
               'scorer_output_sha256': data.get('scorer', {}).get('output_sha256', c.UNKNOWN),
               'env_manifest_sha256': data.get('env_manifest_sha256', c.UNKNOWN)}
        row.update(_q2.metrics(ev, run_rows, st, hs, b))
        return row

    for r in runs:
        rows.append(one('request', [r]))
        groups[r.get('scene', c.UNKNOWN)].append(r)
    for scene in sorted(groups):
        rows.append(one(f'TOTAL:{scene}', groups[scene]))
    if runs:
        rows.append(one('TOTAL:ALL', runs))
    return rows, ignored


def charts(rows, data, outdir, theme):
    plt, t = c.plt_setup(theme)
    banner = c.banner(data)
    made = []
    cols = [r for r in rows if r['row'] == 'request' or r['row'] == 'TOTAL:ALL']
    labels = [r['run_id'] if r['row'] == 'request' else 'ALL (run-clustered)' for r in cols]
    fig, ax = c.new_fig(plt, 'G-B1  Event correctness C_evt (RULE_ONLY baseline)', banner, subtitle='bars: C_evt %, whiskers: 95% CI, hatched: UNKNOWN')
    stats = [{'pct': r['C_evt_pct'], 'lo': r['C_evt_lo'], 'hi': r['C_evt_hi'], 'n': r['n_events_scored']} for r in cols]
    xs = c.bar_ci(ax, t, labels, stats, t['s1'])
    ax.set_xticks(range(len(labels)), [f"{lab}\nnot scored: {r['n_events_not_scored']}" for lab, r in zip(labels, cols)], fontsize=8)
    ax.set_ylabel('C_evt (%)')
    made += c.save_fig(fig, outdir, 'G-B1_c_evt')

    fig, ax = c.new_fig(plt, 'G-B2  Switch latency L_sw (matched events)', banner, subtitle='box: IQR, points: events')
    runs = [r for r in cols if r['row'] == 'request']
    for i, r in enumerate(runs):
        vals = [c.num(e.get('latency_ms')) for e in data.get('events', []) if e.get('run_id') == r['run_id']
                and e.get('arm') == 'RULE_ONLY' and e.get('scored') is True and e.get('match') is True]
        vals = [v for v in vals if v is not None]
        if not vals:
            ax.text(i, 0.5, 'UNKNOWN', ha='center', color=t['ink2'], transform=ax.get_xaxis_transform())
            continue
        ax.boxplot([vals], positions=[i], widths=0.4, showfliers=False, boxprops={'color': t['ink2']},
                   medianprops={'color': t['s2']}, whiskerprops={'color': t['ink2']}, capprops={'color': t['ink2']})
        ax.scatter([i + 0.0 + 0.04 * k for k in range(len(vals))], vals, s=22, color=t['s1'], zorder=3, edgecolor=t['bg'], linewidth=1)
        ax.text(i, ax.get_ylim()[1], f'n={len(vals)}', ha='center', va='top', fontsize=8)
    ax.set_xticks(range(len(runs)), [r['run_id'] for r in runs], fontsize=8)
    ax.set_ylabel('L_sw (ms)')
    made += c.save_fig(fig, outdir, 'G-B2_l_sw')

    total = next((r for r in rows if r['row'] == 'TOTAL:ALL'), None)
    fig, ax = c.new_fig(plt, 'G-B3  Scoring coverage (all events to scored)', banner, subtitle='events dropped by label, then scored')
    if total is None:
        ax.text(0.5, 0.5, 'UNKNOWN (no RULE_ONLY runs)', ha='center', transform=ax.transAxes)
    else:
        parts = []
        if total['not_scored_breakdown'] != 'NONE':
            parts = [(k.rsplit(':', 1)[0], int(k.rsplit(':', 1)[1])) for k in total['not_scored_breakdown'].split('; ')]
        parts += [('match UNKNOWN', total['n_match_unknown'])] if total['n_match_unknown'] else []
        scored = total['n_events_scored']
        left = scored + sum(v for _, v in parts)
        ax.barh(0, left, color=t['muted'], height=0.55)
        ax.text(left, 0, f' all: {left}', va='center', fontsize=8)
        for i, (name, v) in enumerate(parts, 1):
            left -= v
            ax.barh(i, v, left=left, color=t['muted'], hatch='///', fill=False, edgecolor=t['muted'], height=0.55)
            ax.text(left + v, i, f' -{v} {name}', va='center', fontsize=8)
        ax.barh(len(parts) + 1, scored, color=t['s1'], height=0.55)
        ax.text(scored, len(parts) + 1, f' scored: {scored}', va='center', fontsize=8)
        ax.set_yticks([])
        ax.invert_yaxis()
        ax.set_xlabel('events')
    made += c.save_fig(fig, outdir, 'G-B3_coverage')
    return made


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('results', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--theme', choices=['light', 'dark'], default='light')
    p.add_argument('--bootstrap-b', type=int, default=c.BOOTSTRAP_B)
    a = p.parse_args(argv)
    data = c.load_results(a.results, 'BASELINE')
    rows, ignored = build_rows(data, a.bootstrap_b)
    notes = ['UNKNOWN = not provided or not computable; never imputed. CI: Wilson for one run, run-clustered bootstrap for >=2 runs.',
             f'Events of non-RULE_ONLY arms ignored: {ignored}.']
    if data['source_class'] != 'FORMAL':
        notes.append(f"source_class is {data['source_class']}: not formal evidence (plan 1.3).")
    if not rows:
        notes.append('NO RULE_ONLY runs in input: nothing to tabulate (NOT_RUN).')
    c.write_table(a.out, 'baseline_B1', COLUMNS, rows, 'Table B-1 Baseline (RULE_ONLY)', c.banner(data), notes)
    made = charts(rows, data, a.out, a.theme) if rows else []
    print(f'wrote baseline_B1.csv/.md and {len(made)} chart files to {a.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
