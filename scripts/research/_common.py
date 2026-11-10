"""Shared helpers for the research analysis scripts: UNKNOWN handling, statistics, tables, plots.

Rules (research plan #397 sections 1.4, 1.5, 1.7): a missing or UNKNOWN value is shown as UNKNOWN and
leaves numerator and denominator; nothing is imputed. Intervals: proportions use a run-clustered
percentile bootstrap (10,000 resamples, seed 20261102), or Wilson when there is a single cluster.
"""
from __future__ import annotations

import csv
import json
import math
import random
import statistics
import sys
from pathlib import Path

UNKNOWN = 'UNKNOWN'
MISSING_TOKENS = {'', 'UNKNOWN', 'MISSING', 'NOT_RUN'}
SEED = 20261102
BOOTSTRAP_B = 10000
SOURCE_CLASSES = ('FORMAL', 'ENGINEERING', 'SYNTHETIC', 'PILOT')
CONTRACT = 'amidst.research-results.v0-draft'


def is_unknown(value):
    return value is None or (isinstance(value, str) and value.strip().upper() in MISSING_TOKENS)


def num(value):
    """A real number or None. Bools and unknown tokens are not numbers."""
    if is_unknown(value) or isinstance(value, bool):
        return None
    return float(value) if isinstance(value, (int, float)) else None


def flag(value):
    """True/False, or None for unknown. Only real booleans count."""
    return value if isinstance(value, bool) else None


def load_results(path, experiment):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('contract') != CONTRACT:
        raise SystemExit(f'input contract mismatch: expected {CONTRACT}')
    if data.get('experiment') != experiment:
        raise SystemExit(f"expected experiment {experiment}, got {data.get('experiment')}")
    if data.get('source_class') not in SOURCE_CLASSES:
        raise SystemExit('source_class must be one of ' + ', '.join(SOURCE_CLASSES))
    return data


def env8(data):
    value = data.get('env_manifest_sha256')
    return value[:8] if isinstance(value, str) and len(value) == 64 else UNKNOWN


def banner(data):
    return f"{data['source_class']} | env {env8(data)}"


# ---------------------------------------------------------------- statistics

def wilson(k, n, z=1.959964):
    if n == 0:
        return None
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return 100 * max(0.0, center - half), 100 * min(1.0, center + half)


def percentile_nr(values, p):
    """Nearest-rank percentile (the plan uses nearest-rank for P99; applied to P90 too)."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(p * len(ordered)) - 1)]


def cluster_bootstrap(groups, stat, b=None):
    """Percentile 95% CI resampling whole clusters. groups: {cluster: [items]}. None if <2 clusters."""
    keys = sorted(groups)
    if len(keys) < 2:
        return None
    rng = random.Random(SEED)
    draws = []
    for _ in range(b or BOOTSTRAP_B):
        pooled = [item for key in (rng.choice(keys) for _ in keys) for item in groups[key]]
        value = stat(pooled)
        if value is not None:
            draws.append(value)
    if not draws:
        return None
    return percentile_nr(draws, 0.025), percentile_nr(draws, 0.975)


def prop(groups, b=None):
    """groups: {run: [0/1 ...]}. Returns dict pct, lo, hi, n, ci_method ('UNKNOWN' when not computable)."""
    items = [x for g in groups.values() for x in g]
    n = len(items)
    if n == 0:
        return {'pct': UNKNOWN, 'lo': UNKNOWN, 'hi': UNKNOWN, 'n': 0, 'ci_method': UNKNOWN}
    pct = 100 * sum(items) / n
    nonempty = {k: v for k, v in groups.items() if v}
    if len(nonempty) == 1:
        lo, hi = wilson(sum(items), n)
        return {'pct': pct, 'lo': lo, 'hi': hi, 'n': n, 'ci_method': 'wilson'}
    ci = cluster_bootstrap(nonempty, lambda xs: 100 * sum(xs) / len(xs) if xs else None, b)
    lo, hi = ci if ci else (UNKNOWN, UNKNOWN)
    return {'pct': pct, 'lo': lo, 'hi': hi, 'n': n, 'ci_method': 'cluster_bootstrap'}


def median_stat(groups, b=None):
    """groups: {run: [numbers]}. Returns median, p90, CI of the median (UNKNOWN if <2 clusters)."""
    items = [x for g in groups.values() for x in g]
    if not items:
        return {'median': UNKNOWN, 'p90': UNKNOWN, 'lo': UNKNOWN, 'hi': UNKNOWN, 'n': 0}
    nonempty = {k: v for k, v in groups.items() if v}
    ci = cluster_bootstrap(nonempty, lambda xs: statistics.median(xs) if xs else None, b)
    lo, hi = ci if ci else (UNKNOWN, UNKNOWN)
    return {'median': statistics.median(items), 'p90': percentile_nr(items, 0.9), 'lo': lo, 'hi': hi, 'n': len(items)}


def sign_test_one_sided(wins, losses):
    """Exact one-sided sign test p for 'wins' (ties already removed). None when no discordant unit."""
    n = wins + losses
    if n == 0:
        return None
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


# ---------------------------------------------------------------- output

def cell(value, digits=1):
    if value is None:
        return UNKNOWN
    if isinstance(value, float):
        return f'{value:.{digits}f}'
    return str(value)


def write_table(outdir, stem, columns, rows, title, banner_text, notes=()):
    """Write <stem>.csv and <stem>.md. Missing cells are written as UNKNOWN."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    with (outdir / f'{stem}.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([cell(row.get(c), 4) for c in columns])
    lines = [f'# {title}', '', f'Source: {banner_text}', '']
    lines += [f'- {note}' for note in notes] + ([''] if notes else [])
    lines.append('| ' + ' | '.join(columns) + ' |')
    lines.append('|' + '|'.join(' --- ' for _ in columns) + '|')
    for row in rows:
        lines.append('| ' + ' | '.join(cell(row.get(c), 1).replace('|', '/') for c in columns) + ' |')
    (outdir / f'{stem}.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def ci_pair(d):
    return d['lo'], d['hi']


# ---------------------------------------------------------------- plotting (dataviz skill palette)

THEMES = {
    'light': {'bg': '#fcfcfb', 'ink': '#0b0b0b', 'ink2': '#52514e', 'muted': '#898781', 'grid': '#e1e0d9',
              's1': '#2a78d6', 's2': '#eb6834'},
    'dark': {'bg': '#1a1a19', 'ink': '#f0efec', 'ink2': '#c3c2b7', 'muted': '#898781', 'grid': '#2c2c2a',
             's1': '#3987e5', 's2': '#d95926'},
}


def plt_setup(theme='light'):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    t = THEMES[theme]
    plt.rcParams.update({
        'figure.facecolor': t['bg'], 'axes.facecolor': t['bg'], 'savefig.facecolor': t['bg'],
        'text.color': t['ink'], 'axes.labelcolor': t['ink2'], 'xtick.color': t['muted'], 'ytick.color': t['muted'],
        'axes.edgecolor': t['grid'], 'axes.grid': True, 'grid.color': t['grid'], 'grid.linewidth': 0.6,
        'axes.axisbelow': True, 'axes.spines.top': False, 'axes.spines.right': False,
        'svg.hashsalt': 'amidst', 'svg.fonttype': 'none', 'font.size': 10, 'hatch.linewidth': 0.8,
    })
    return plt, t


def new_fig(plt, title, banner_text, size=(7.5, 4.2), subtitle=None):
    fig, ax = plt.subplots(figsize=size)
    fig.suptitle(title, x=0.01, ha='left', fontsize=12, fontweight='bold')
    if subtitle:
        ax.set_title(subtitle, loc='left', fontsize=9, color=plt.rcParams['axes.labelcolor'])
    fig.text(0.01, 0.01, banner_text, fontsize=8, color=plt.rcParams['xtick.color'])
    return fig, ax


def save_fig(fig, outdir, name):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))
    fig.savefig(outdir / f'{name}.png', dpi=160, metadata={'Software': None})
    fig.savefig(outdir / f'{name}.svg', metadata={'Date': None})
    import matplotlib.pyplot as plt
    plt.close(fig)
    return [f'{name}.png', f'{name}.svg']


def bar_ci(ax, t, labels, stats, color, width=0.6, offset=0.0, label=None):
    """Bars for prop() dicts; UNKNOWN values become hatched empty bars labelled UNKNOWN."""
    xs = []
    for i, (name, s) in enumerate(zip(labels, stats)):
        x = i + offset
        xs.append(x)
        if isinstance(s['pct'], str):
            ax.bar(x, 100, width, fill=False, hatch='///', edgecolor=t['muted'], linewidth=0.8)
            ax.text(x, 50, 'UNKNOWN', ha='center', va='center', color=t['ink2'], fontsize=8)
            continue
        ax.bar(x, s['pct'], width, color=color, label=label if i == 0 else None)
        if not isinstance(s['lo'], str):
            ax.errorbar(x, s['pct'], yerr=[[s['pct'] - s['lo']], [s['hi'] - s['pct']]], color=t['ink2'], capsize=3, lw=1)
        ax.text(x, min(s['pct'] + 3, 97) if isinstance(s['hi'], str) else min(s['hi'] + 2, 97),
                f"{s['pct']:.0f}%\nn={s['n']}", ha='center', va='bottom', fontsize=8, color=t['ink'])
    ax.set_ylim(0, 112)
    return xs
