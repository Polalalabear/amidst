"""Q2/Q5 metric computation shared by the baseline table and M1 (definitions: plan section 1.7)."""
from __future__ import annotations

from collections import Counter, defaultdict

from _common import UNKNOWN, flag, is_unknown, median_stat, num, prop

CALL_ERROR_TO = 'PROVIDER_TIMEOUT'
CALL_ERROR_SI = 'SCHEMA_INVALID'


def by_run(rows, value_fn):
    groups = defaultdict(list)
    for row in rows:
        value = value_fn(row)
        if value is not None:
            groups[row['run_id']].append(value)
    return groups


def event_split(events):
    """scored events with a known match, and counts of what was left out (plan 1.4 items 4 and 8)."""
    scored, not_scored, unknown_match = [], Counter(), 0
    for ev in events:
        if ev.get('scored') is not True:
            not_scored[ev.get('not_scored_label') if not is_unknown(ev.get('not_scored_label')) else UNKNOWN] += 1
        elif flag(ev.get('match')) is None:
            unknown_match += 1
        else:
            scored.append(ev)
    return scored, not_scored, unknown_match


def metrics(events, runs, steps, honesty, b=None):
    """All baseline-style metrics for the given rows (already filtered to one arm / request / scene)."""
    scored, not_scored, unknown_match = event_split(events)
    out = {'n_events_scored': len(scored), 'n_events_not_scored': sum(not_scored.values()),
           'not_scored_breakdown': '; '.join(f'{k}:{v}' for k, v in sorted(not_scored.items())) or 'NONE',
           'n_match_unknown': unknown_match}
    c = prop(by_run(scored, lambda e: int(e['match'])), b)
    out.update(C_evt_pct=c['pct'], C_evt_lo=c['lo'], C_evt_hi=c['hi'], C_evt_method=c['ci_method'])
    lat = by_run([e for e in scored if e['match']], lambda e: num(e.get('latency_ms')))
    n_latency_unknown = sum(1 for e in scored if e['match'] and num(e.get('latency_ms')) is None)
    s = median_stat(lat, b)
    out.update(L_sw_median_ms=s['median'], L_sw_lo=s['lo'], L_sw_hi=s['hi'], L_sw_p90_ms=s['p90'],
               L_sw_n=s['n'], L_sw_n_unknown=n_latency_unknown)
    minutes = [num(r.get('scoped_minutes')) for r in runs]
    fs = [num(r.get('false_switch_count')) for r in runs]
    if runs and all(m is not None and m > 0 for m in minutes) and all(f is not None for f in fs):
        out['FS_per_min'] = sum(fs) / sum(minutes)
    else:
        out['FS_per_min'] = UNKNOWN
    h = prop(by_run([x for x in honesty if x.get('expected_missing') is True],
                    lambda x: None if flag(x.get('output_missing_marker')) is None else int(x['output_missing_marker'])), b)
    out.update(M_honest_pct=h['pct'], M_honest_lo=h['lo'], M_honest_hi=h['hi'], M_honest_n=h['n'])
    t = median_stat(by_run(steps, lambda x: num(x.get('step_ms'))), b)
    out.update(T_step_median_ms=t['median'], T_step_p90_ms=t['p90'], T_step_n=t['n'])
    rn = [num(r.get('replay_n')) for r in runs]
    rs = [num(r.get('replay_hash_same_n')) for r in runs]
    out['R_hash_pct'] = (100 * sum(rs) / sum(rn)) if runs and all(x is not None for x in rn + rs) and sum(rn) > 0 else UNKNOWN
    return out


def call_flag(call, code):
    """1/0 for a call outcome, None when unknown. An explicit null error_code is a known success;
    UNKNOWN, an empty string or an absent key is unknown and leaves the denominator (plan 1.4 item 8)."""
    if 'error_code' not in call:
        return None
    value = call['error_code']
    if value is None:
        return 0
    return None if is_unknown(value) else int(value == code)


def call_rate(calls, code, b=None):
    out = prop(by_run(calls, lambda x: call_flag(x, code)), b)
    out['n_unknown'] = sum(call_flag(x, code) is None for x in calls)
    return out


def agent_rates(calls, steps, b=None):
    """TO and SI over calls, FB over decision steps (plan 1.7); unknown outcomes are counted, not scored."""
    to, si = call_rate(calls, CALL_ERROR_TO, b), call_rate(calls, CALL_ERROR_SI, b)
    known_steps = [s for s in steps if not is_unknown(s.get('decision_source'))]
    fb = prop(by_run(known_steps, lambda s: int(s['decision_source'] == 'RULE_FALLBACK')), b)
    fb['n_unknown'] = len(steps) - len(known_steps)
    return to, si, fb
