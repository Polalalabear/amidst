"""Evaluation-only adapter: r004 script plan -> `q5-evaluation-script.v1` (D79 window formula).

Plan times are planned targets (never GT, renderer trajectory, visibility or depth).
No inference, RGB or runtime imports; the scorer is not modified.

Pre-check scope (I1): S1 and S2 compare only *adjacent* SWITCH / RETURN events. When a NO_SWITCH sits
between two moving events, spacing between them is guaranteed by S4 (NO_SWITCH is >= 2 s after the
previous t_N and the next t_N is >= 9 s after it) together with the non-overlapping window check.

Formal approval (M1): `--formal` needs `approval_ref`, a nonempty string that contains the D89 link
(`D89_APPROVAL_URL`) and the SHA-256 (64 hex digits) of the plan content. The adapter recomputes that
hash with `plan_content_sha256` and refuses a missing, non-string, unlinked or mismatching value.
Hash scope: UTF-8 bytes of the plan as canonical JSON (sorted keys, separators `,` / `:`,
ensure_ascii=False) with only the top-level `approval_ref` field removed; every other field, including
status, run_id and clock_id, is hashed. Non-formal (PREVIEW) output is always PROPOSED with a null approval_ref.

Placeholders (L2): a value is UNKNOWN when it is None or a string that is empty, or equals `UNKNOWN`
after strip() and casefold(). Malformed plans (not an object, missing or non-string run_id / clock_id,
...) are reported as `PlanError` reasons, never as tracebacks.
"""
import hashlib
import json
import re

PLAN_SCHEMA = 'q5-script-plan.v1'
SCRIPT_SCHEMA = 'q5-evaluation-script.v1'
PLACEHOLDER = 'UNKNOWN'
D89_APPROVAL_URL = 'https://github.com/Polalalabear/amidst/issues/93#issuecomment-6423194857'
SCOPE_STATEMENT = ('本版只評空檔 ≤ 5.2 s、暫失 ≤ 1.8 s 的事件，超出範圍的情況依目前評分器會因多次 RETURN 判 miss，未納入')
ACTIONS = ('SWITCH', 'RETURN_TO_ORIGIN', 'NO_SWITCH')
MOVING = ('SWITCH', 'RETURN_TO_ORIGIN')
S_MIN_ANCHOR_SPACING_US = 8_000_000   # S2 (card adopts 8.0 s; hard floor W + R = 7.0 s)
S_MIN_DWELL_US = 5_000_000            # S1 (card)
S_NS_BEFORE_US = 2_000_000            # S4: t_X(NS) - t_N(previous)
S_NS_AFTER_US = 9_000_000             # S4: t_N(next) - t_X(NS)
S_HEAD_US = 3_000_000                 # S6: first t_X >= query start + 3 s
S_TAIL_US = 2_000_000                 # S6: query end >= last window end + 2 s
MIN_SWITCH_GAP_US = 1_000_000         # card §1.3
MIN_RETURN_LOSS_US = 400_000          # card §1.3
WARN_SWITCH_GAP_US = 4_000_000        # card §1.3 design ceiling
MAX_PLANNED_SEARCHING = 3             # card §1.7
NOT_CHECKED = ['S3 (future-window contamination)', 't_L <= t_N - 1.0 s', 't_V >= t_N - 0.6 s']


class PlanError(ValueError):
    """Raised with every failed pre-check reason, one per line."""

    def __init__(self, reasons):
        self.reasons = list(reasons)
        super().__init__('\n'.join(self.reasons))


def _int(value):
    return type(value) is int


def is_unknown(value):
    return value is None or (isinstance(value, str) and value.strip().casefold() in ('', PLACEHOLDER.casefold()))


def plan_content_sha256(plan):
    """SHA-256 hex of the canonical plan JSON without the top-level `approval_ref` (see module docstring)."""
    body = {k: v for k, v in plan.items() if k != 'approval_ref'}
    text = json.dumps(body, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _approval_reasons(plan):
    ref = plan.get('approval_ref')
    if not isinstance(ref, str) or not ref.strip():
        return ['formal output refused: approval_ref must be a nonempty string with the D89 link and plan SHA-256']
    reasons = []
    if D89_APPROVAL_URL not in ref:
        reasons.append('formal output refused: approval_ref lacks the D89 link')
    expected = plan_content_sha256(plan)
    found = re.findall(r'(?<![0-9A-Fa-f])[0-9A-Fa-f]{64}(?![0-9A-Fa-f])', ref)
    if expected not in [h.lower() for h in found]:
        reasons.append('formal output refused: approval_ref lacks the plan SHA-256 (expected %s)' % expected)
    return reasons


def load_plan(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise PlanError(['duplicate JSON key: ' + key])
            out[key] = value
        return out
    try:
        plan = json.loads(raw, object_pairs_hook=pairs)
    except ValueError as exc:
        raise PlanError(['malformed plan JSON: ' + str(exc)]) from exc
    if not isinstance(plan, dict):
        raise PlanError(['plan must be a JSON object'])
    return plan


def _params(plan, errors):
    params = plan.get('parameters')
    if not isinstance(params, dict) or not all(_int(params.get(k)) and params[k] > 0 for k in (
            'search_window_us', 'research_interval_us', 'link_max_gap_us', 'index_interval_us')):
        errors.append('parameters must give positive integer search_window_us, research_interval_us, link_max_gap_us, index_interval_us')
        return None
    return params


def derive_windows(plan):
    """Return (events with windows, errors). Truncation and NO_SWITCH yield follow D79 / card §1.4."""
    errors = []
    params = _params(plan, errors)
    query = plan.get('query_range_us')
    events = plan.get('events')
    if not (isinstance(query, list) and len(query) == 2 and all(_int(x) and x >= 0 for x in query) and query[0] < query[1]):
        errors.append('query_range_us must be [start, end) integer microseconds')
        query = None
    if not isinstance(events, list) or not events:
        errors.append('events must be a nonempty list')
        events = None
    if errors:
        return None, errors
    W, R, L = params['search_window_us'], params['research_interval_us'], params['link_max_gap_us']
    ids = set()
    for i, ev in enumerate(events):
        tag = ev.get('event_id') if isinstance(ev, dict) else None
        if not isinstance(ev, dict) or not isinstance(tag, str) or not tag or tag in ids:
            errors.append('event %d: missing or duplicate event_id' % i)
            continue
        ids.add(tag)
        if ev.get('action') not in ACTIONS:
            errors.append('%s: unknown action' % tag)
            continue
        if not _int(ev.get('t_x_us')):
            errors.append('%s: t_x_us must be an integer' % tag)
        if ev['action'] in MOVING:
            if not _int(ev.get('t_n_us')):
                errors.append('%s: %s needs integer t_n_us' % (tag, ev['action']))
        elif ev.get('t_n_us') is not None:
            errors.append('%s: NO_SWITCH must have t_n_us null' % tag)
        if ev['action'] == 'SWITCH':
            cams = ev.get('allowed_camera_ids')
            if not (isinstance(cams, list) and cams and all(isinstance(c, str) and c for c in cams)):
                errors.append('%s: SWITCH needs allowed_camera_ids' % tag)
        elif ev.get('allowed_camera_ids'):
            errors.append('%s: allowed_camera_ids only for SWITCH' % tag)
    if errors:
        return None, errors

    def unclipped_start(ev):
        return (ev['t_n_us'] if ev['action'] in MOVING else ev['t_x_us']) - W

    anchors = [ev['t_n_us'] if ev['action'] in MOVING else ev['t_x_us'] for ev in events]
    if anchors != sorted(anchors):
        errors.append('events must be ordered by anchor (t_n_us for SWITCH/RETURN, t_x_us for NO_SWITCH)')
        return None, errors
    prev_end, out = query[0], []
    for k, ev in enumerate(events):
        if ev['action'] in MOVING:
            start, end = max(prev_end, ev['t_n_us'] - W), ev['t_n_us'] + R
        else:
            # NO_SWITCH yields: the next window's *untruncated* start bounds this one.
            nxt = unclipped_start(events[k + 1]) if k + 1 < len(events) else query[1]
            start, end = max(prev_end, ev['t_x_us'] - W), min(ev['t_x_us'] + W, nxt, query[1])
        item = dict(ev)
        item['decision_window_us'] = [start, end]
        if ev['action'] == 'SWITCH':
            item['entry_window_us'] = [ev['t_n_us'] - L, ev['t_n_us'] + R]
        out.append(item)
        prev_end = end
    return out, errors


def precheck(plan):
    """Return report dict; report['ok'] is False when any reason rejects the plan."""
    errors, warnings = [], []
    if not isinstance(plan, dict):
        return {'schema_version': 'q5-script-precheck.v1', 'plan_id': None, 'scope_statement': SCOPE_STATEMENT,
                'not_checked_here': NOT_CHECKED, 'errors': ['plan must be a JSON object'], 'warnings': [], 'events': [],
                'ok': False}
    derived, derive_errors = derive_windows(plan)
    errors += derive_errors
    report = {'schema_version': 'q5-script-precheck.v1', 'plan_id': plan.get('plan_id'), 'scope_statement': SCOPE_STATEMENT,
              'not_checked_here': NOT_CHECKED, 'errors': errors, 'warnings': warnings, 'events': []}
    if derived is None:
        report['ok'] = False
        return report
    params, query = plan['parameters'], plan['query_range_us']
    W, R, L, D = (params[k] for k in ('search_window_us', 'research_interval_us', 'link_max_gap_us', 'index_interval_us'))
    max_gap, max_loss = W + D - R, D + L + R
    searches = 0
    for k, ev in enumerate(derived):
        tag, win = ev['event_id'], ev['decision_window_us']
        if ev['action'] == 'SWITCH':
            gap = ev['t_n_us'] - ev['t_x_us']
            if gap > max_gap:
                errors.append('%s: SWITCH gap %d us > %d us (W + Δ - R)' % (tag, gap, max_gap))
            if gap < MIN_SWITCH_GAP_US:
                errors.append('%s: SWITCH gap %d us < %d us (card §1.3 lower bound)' % (tag, gap, MIN_SWITCH_GAP_US))
            elif gap > WARN_SWITCH_GAP_US:
                warnings.append('%s: SWITCH gap %d us above card design ceiling %d us' % (tag, gap, WARN_SWITCH_GAP_US))
        if ev['action'] == 'RETURN_TO_ORIGIN':
            loss = ev['t_n_us'] - ev['t_x_us']
            if loss >= max_loss:
                errors.append('%s: RETURN loss %d us >= %d us (Δ + L + R)' % (tag, loss, max_loss))
            if loss < MIN_RETURN_LOSS_US:
                errors.append('%s: RETURN loss %d us < %d us (card §1.3 lower bound)' % (tag, loss, MIN_RETURN_LOSS_US))
        if ev['action'] in MOVING:
            searches += 1
        if not win[0] < win[1]:
            errors.append('%s: decision window is empty after truncation %s' % (tag, win))
        if not (query[0] <= win[0] and win[1] <= query[1]):
            errors.append('%s: decision window %s outside query %s' % (tag, win, query))
        if 'entry_window_us' in ev and not (query[0] <= ev['entry_window_us'][0] and ev['entry_window_us'][1] <= query[1]):
            errors.append('%s: entry window %s outside query' % (tag, ev['entry_window_us']))
        if k and win[0] < derived[k - 1]['decision_window_us'][1]:
            errors.append('%s: window overlaps previous window' % tag)
        # S1 / S2 between consecutive moving events; S4 around NO_SWITCH.
        if k:
            prev = derived[k - 1]
            if prev['action'] in MOVING and ev['action'] in MOVING:
                if ev['t_n_us'] - prev['t_n_us'] < S_MIN_ANCHOR_SPACING_US:
                    errors.append('%s: S2 t_N spacing %d us < %d us' % (tag, ev['t_n_us'] - prev['t_n_us'], S_MIN_ANCHOR_SPACING_US))
                if ev['t_x_us'] - prev['t_n_us'] < S_MIN_DWELL_US:
                    errors.append('%s: S1 dwell %d us < %d us' % (tag, ev['t_x_us'] - prev['t_n_us'], S_MIN_DWELL_US))
            if ev['action'] == 'NO_SWITCH' and prev['action'] in MOVING and ev['t_x_us'] - prev['t_n_us'] < S_NS_BEFORE_US:
                errors.append('%s: S4 NO_SWITCH only %d us after previous t_N (< %d us)' % (tag, ev['t_x_us'] - prev['t_n_us'], S_NS_BEFORE_US))
            if prev['action'] == 'NO_SWITCH' and ev['action'] in MOVING and ev['t_n_us'] - prev['t_x_us'] < S_NS_AFTER_US:
                errors.append('%s: S4 t_N only %d us after NO_SWITCH t_X (< %d us)' % (tag, ev['t_n_us'] - prev['t_x_us'], S_NS_AFTER_US))
        if ev['action'] == 'NO_SWITCH' and not any(e['action'] in MOVING for e in derived[k + 1:]):
            errors.append('%s: S5 NO_SWITCH has no later planned search in the session' % tag)
        report['events'].append({k2: ev[k2] for k2 in ('event_id', 'action', 'decision_window_us', 'entry_window_us') if k2 in ev})
    if searches > MAX_PLANNED_SEARCHING:
        errors.append('planned SEARCHING %d > %d' % (searches, MAX_PLANNED_SEARCHING))
    report['planned_searching'] = searches
    first = derived[0]
    if first['t_x_us'] < query[0] + S_HEAD_US:
        errors.append('S6: first t_X %d us < query start + %d us' % (first['t_x_us'], S_HEAD_US))
    if query[1] < derived[-1]['decision_window_us'][1] + S_TAIL_US:
        errors.append('S6: query end %d us < last window end + %d us' % (query[1], S_TAIL_US))
    duration = plan.get('source_duration_us')
    if not _int(duration) or duration < query[1]:
        errors.append('S6: source_duration_us must be an integer >= query end')
    report['ok'] = not errors
    return report


def generate_script(plan, *, formal):
    """Plan -> `q5-evaluation-script.v1`. `formal=True` refuses placeholders and unfrozen plans."""
    report = precheck(plan)
    reasons = list(report['errors'])
    if isinstance(plan, dict):
        for key in ('run_id', 'clock_id'):
            value = plan.get(key)
            if not isinstance(value, str):
                reasons.append('%s is missing or not a string' % key)
            elif formal and is_unknown(value):
                reasons.append('formal output refused: %s is %r' % (key, value))
        if formal:
            if plan.get('status') != 'FROZEN':
                reasons.append('formal output refused: plan status is %s (needs FROZEN with fixed hash)' % plan.get('status'))
            reasons += _approval_reasons(plan)
    if reasons:
        raise PlanError(reasons)
    derived, _ = derive_windows(plan)
    approval = plan['approval_ref'] if formal else None
    events = []
    for ev in derived:
        row = {'event_id': ev['event_id'], 'action': ev['action'], 'decision_window_us': ev['decision_window_us']}
        if ev['action'] == 'SWITCH':
            row['allowed_camera_ids'] = ev['allowed_camera_ids']
            row['entry_window_us'] = ev['entry_window_us']
        events.append(row)
    return {'schema_version': SCRIPT_SCHEMA, 'status': 'APPROVED' if approval else 'PROPOSED',
            'approval_ref': approval or None, 'run_id': plan['run_id'], 'clock_id': plan['clock_id'],
            'generator_mode': 'FORMAL' if formal else 'PREVIEW', 'plan_id': plan.get('plan_id'),
            'scope_statement': SCOPE_STATEMENT, 'events': events}


def dumps(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n'
