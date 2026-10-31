"""Evaluation-only v2. Decisions default pending; no runtime/GT/media imports.

v1 dispatch is byte-preserving. Explicit selections measure proposed rules; they
are not evidence of human approval. Formal LIMIT/overlap evidence has no adopted
adapter here and fails closed; explicit synthetic controls cannot grant it.
"""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from amidst.evaluation import q5_switch_eval as v1

VERSION = 'q5-switch-eval-v2.0'
PENDING = 'PENDING_USER'
CHOICES = {
    'U-D1': {'M1', 'M2', 'M3'},
    'U-D2': {'REPORT_EXCESS_ONLY', 'EXCESS_IS_MISS'},
    'U-D4': {'E1', 'E2', 'E3'},
    'U-D5': {'RECOMPUTE_AND_REJECT', 'TRUST_SCRIPT_WINDOWS'},
    'U-D6': {'REJECT_EARLY_BLIND'},
    'U-D7': {'MAIN_STANDARD_AND_CLASS_RATIOS', 'MAIN_RATIO_ONLY'},
    'U-D8': {'NEW_V2_MODULE'},
    'U-D9': {'CLAMPED_WINDOW_START', 'D79_WINDOW_START'},
    'U-D10': {'N_MAX_MINUS_TWO', 'THREE'},
    'UK-8': {'PLAN_CHECK_ONLY'},
}
PARAMETERS = ('index_interval_us', 'link_max_gap_us', 'search_window_us',
              'research_interval_us', 'session_max_research_rounds')


class EvaluationError(v1.EvaluationError):
    def __init__(self, category, message):
        self.category = category
        super().__init__(message)


def need(ok, category, message):
    if not ok:
        raise EvaluationError(category, message)


def config(raw):
    values = v1.load_json(raw)
    need(isinstance(values, dict) and values.keys() <= CHOICES.keys(), 'DECISION_CONFIG_INVALID', 'Unknown or fixed decision key')
    out = {}
    for key, choices in CHOICES.items():
        value = values.get(key, PENDING)
        need(isinstance(value, str) and value in choices | {PENDING}, 'DECISION_CONFIG_INVALID', 'Unsupported decision value: ' + key)
        out[key] = value
    return out


@dataclass(frozen=True)
class SyntheticControls:
    """In-memory testing seam, not an authority receipt or product wire schema."""
    overlap_pair: tuple = ()
    exit_strip_present: bool = False


def _synthetic(controls, script, response):
    if controls is None:
        return False
    need(isinstance(controls, SyntheticControls)
         and script.get('status') == 'PROPOSED'
         and str(script.get('run_id', '')).startswith('SYNTHETIC_')
         and str(response.get('session_id', '')).startswith('SYNTHETIC_'),
         'SYNTHETIC_SCOPE_REQUIRED', 'Synthetic controls cannot be used on a production scope')
    return True


def freeze_output(response_raw, decisions_raw, *, expected_response_sha256, expected_decisions_sha256):
    """Verify output before any script read, including unscored LIMIT inspection."""
    try:
        v1.require(v1.sha(response_raw) == expected_response_sha256
                   and v1.sha(decisions_raw) == expected_decisions_sha256, 'Frozen output file hash mismatch')
        response = v1.load_json(response_raw)
        v1.require(isinstance(response, dict), 'Q2 response required')
        if response.get('status') == 'COMPLETE':
            return v1.freeze_output(response_raw, decisions_raw,
                expected_response_sha256=expected_response_sha256,
                expected_decisions_sha256=expected_decisions_sha256)
        v1.require(response.get('status') == 'ENDED_BY_LIMIT', 'Only COMPLETE or inspectable ENDED_BY_LIMIT')
        v1.require(v1.digest(response, 'output_sha256') == response.get('output_sha256'), 'Response content hash mismatch')
        # Reuse v1's journal/schema/session validation without altering v1. The
        # temporary COMPLETE value is solely a validator input; the returned
        # frozen bytes retain ENDED_BY_LIMIT and its original hashes/status.
        check = deepcopy(response)
        check['status'] = 'COMPLETE'
        check['output_sha256'] = v1.digest(check, 'output_sha256')
        v1.freeze_output(v1.canonical(check), decisions_raw,
            expected_response_sha256=v1.sha(v1.canonical(check)),
            expected_decisions_sha256=expected_decisions_sha256)
        records = [v1.load_json(line) for line in decisions_raw.splitlines()]
        ended = [r for r in records if r.get('state_after') == 'ENDED']
        v1.require(len(ended) == 1 and ended[0] == records[-1]
                   and ended[0].get('accepted') is True
                   and ended[0].get('executed_action') is None, 'LIMIT needs one final same-session ENDED')
        return v1.FrozenOutput(v1.canonical(response), v1.canonical(records),
                               expected_response_sha256, expected_decisions_sha256)
    except v1.EvaluationError as error:
        raise EvaluationError('OUTPUT_INTEGRITY', str(error)) from error


def searching_starts(records):
    starts = {}
    for row in records:
        index = row.get('searching_index')
        if (type(index) is int and index > 0 and index not in starts
                and row.get('accepted') is True and row.get('state_after') == 'SEARCHING'
                and row.get('executed_action') is None):
            starts[index] = row
    return list(starts.values())


def searching_count(records, window):
    need(v1._range(window), 'SCRIPT_PLAN_MISMATCH', 'Invalid SEARCHING count window')
    return sum(window[0] <= r['source_time_us'] < window[1] for r in searching_starts(records))


def parameter_values(raw, pin, script, scope):
    need(v1.sha(raw) == pin, 'PARAMETER_INTEGRITY', 'Parameter file pin mismatch')
    p = v1.load_json(raw)
    digest = v1.sha(v1.canonical({k: v for k, v in p.items() if k not in {'content_sha256', 'parameter_set_id', 'stats'}}))
    bind = script.get('parameter_binding', {})
    need(p.get('schema_version') == 'q-demo.parameter-set.v1'
         and p.get('content_sha256') == digest == bind.get('parameter_set_sha256') == scope.get('parameter_set_sha256')
         and p.get('parameter_set_id') == 'pset:q-demo:' + digest[:16] == bind.get('parameter_set_id'),
         'PARAMETER_INTEGRITY', 'Parameter content/response/script binding mismatch')
    if scope.get('parameter_set_id') is not None:
        need(scope['parameter_set_id'] == p['parameter_set_id'], 'PARAMETER_INTEGRITY', 'Response parameter ID mismatch')
    need(script['run_id'] in p.get('applies_to', {}).get('run_ids', []), 'PARAMETER_INTEGRITY', 'Parameter run mismatch')
    rows = p.get('parameters', [])
    values = {r['name']: r['value'] for r in rows}
    need(len(values) == len(rows), 'PARAMETER_INTEGRITY', 'Duplicate parameter')
    # Real parameter documents put the index interval in applies_to; synthetic
    # fixtures also exercise an explicit named interval. Conflicts are rejected.
    interval = p.get('applies_to', {}).get('index_interval_us')
    if interval is not None:
        need('index_interval_us' not in values or values['index_interval_us'] == interval, 'PARAMETER_INTEGRITY', 'Interval conflict')
        values['index_interval_us'] = interval
    for key in PARAMETERS:
        need(type(values.get(key)) is int and values[key] > 0 and values[key] == bind.get(key),
             'PARAMETER_INTEGRITY', 'Missing or inconsistent parameter: ' + key)
    d, l, w, r, n = [values[key] for key in PARAMETERS]
    need(l % d == r % d == w % d == 0 and w + d > r and n >= 2,
         'PARAMETER_INTEGRITY', 'Invalid parameter grid/bounds')
    return d, l, w, r, n


def _ceil(a, b):
    return -(-a // b)


def derive_plan_event(event, previous_end, query, parameters, selected):
    """Shared integer planning arithmetic for the scorer and evaluation adapter.

    Returns the derived event, planned searches and ideal return maximum. This
    performs no geometry/visibility check and grants no plan or script approval.
    """
    d, l, w, r, n = parameters
    anchor = event.get('plan_anchor_us', {})
    tx = anchor.get('t_X')
    need(type(tx) is int and query[0] <= tx < query[1], 'SCRIPT_PLAN_MISMATCH', 'Plan exit outside query')
    action = event['action']
    maximum, searches, entry = None, 0, {}
    if action == 'SWITCH':
        windows = event.get('entry_windows_us')
        need(isinstance(windows, dict) and bool(windows), 'SCRIPT_PLAN_MISMATCH', 'Entry windows required')
        times = anchor.get('t_N_by_camera')
        need(isinstance(times, dict), 'SCRIPT_PLAN_MISMATCH', 'Per-camera anchors required')
        blind = [c for c, v in windows.items() if v.get('kind') == 'BLIND']
        need(set(times) == set(blind), 'SCRIPT_PLAN_MISMATCH', 'Camera anchor map mismatch')
        all_times, gaps = [], []
        for camera, value in windows.items():
            need(isinstance(camera, str) and bool(camera) and value.get('kind') in {'BLIND', 'OVERLAP'}, 'SCRIPT_PLAN_MISMATCH', 'Unknown camera entry kind')
            tn = times[camera] if value['kind'] == 'BLIND' else tx + l
            need(type(tn) is int and tn >= tx, 'SCRIPT_PLAN_MISMATCH', 'Invalid plan entry')
            all_times.append(tn)
            if value['kind'] == 'BLIND':
                gaps.append(tn - tx)
            entry[camera] = [max(query[0], tn - l), tn + r]
        gap = max(gaps, default=0)
        expected_class = 'LONG_GAP' if gap > w + d - r else 'STANDARD'
        maximum = max(1, _ceil(gap - (w + l), r) + 1) if expected_class == 'LONG_GAP' else 0
        searches = maximum + 1
        start = min(all_times) - w
        if expected_class == 'LONG_GAP' and selected['U-D9'] != 'D79_WINDOW_START':
            start = min(min(all_times), tx + w + d - r) - w
        window = [max(query[0], previous_end, start), max(all_times) + r]
    elif action == 'RETURN_TO_ORIGIN':
        tn = anchor.get('t_N')
        need(type(tn) is int and tn >= tx, 'SCRIPT_PLAN_MISMATCH', 'Invalid RETURN anchor')
        duration = tn - tx
        need(not l + r < duration < d + l + r, 'D94_FORBIDDEN_INTERVAL', 'D94 rejects L+R < d < Delta+L+R')
        expected_class = 'LONG_LOSS' if duration >= d + l + r else 'STANDARD'
        maximum = max(0, _ceil(duration - l, r))
        searches = maximum if expected_class == 'LONG_LOSS' else 1
        window = [max(query[0], previous_end, tn - w), tn + r]
    else:
        expected_class = 'STANDARD'
        window = event['decision_window_us']
    need(searches <= n, 'PLANNED_SEARCH_BUDGET', 'Event exceeds session search bound')
    out = deepcopy(event)
    out.update(event_class=expected_class, decision_window_us=window)
    if entry:
        out['entry_windows_us'] = {c: {'kind': event['entry_windows_us'][c]['kind'], 'range_us': span}
                                   for c, span in entry.items()}
    if expected_class.startswith('LONG_'):
        out['return_count_max'] = maximum
    return out, searches, maximum


def derive(event, previous_end, query, parameters, selected):
    calculated, searches, maximum = derive_plan_event(event, previous_end, query, parameters, selected)
    kind = event['event_class']
    need(kind == calculated['event_class'], 'SCRIPT_PLAN_MISMATCH', 'Event class differs from plan')
    for camera, value in calculated.get('entry_windows_us', {}).items():
        if value['kind'] == 'OVERLAP':
            need(event['entry_windows_us'][camera].get('range_us') == value['range_us'],
                 'SCRIPT_PLAN_MISMATCH', 'D93 O1 is fixed, even when U-D5 is pending')
    if selected['U-D5'] == 'RECOMPUTE_AND_REJECT':
        need(event['decision_window_us'] == calculated['decision_window_us'], 'SCRIPT_PLAN_MISMATCH', 'Decision window differs from plan')
        for camera, value in calculated.get('entry_windows_us', {}).items():
            need(event['entry_windows_us'][camera]['range_us'] == value['range_us'], 'SCRIPT_PLAN_MISMATCH', 'Entry window differs from plan')
        if kind.startswith('LONG_'):
            need(event.get('return_count_max') == maximum, 'SCRIPT_PLAN_MISMATCH', 'Return bound differs from plan')
    return maximum, searches


def _empty_ratio():
    return {'numerator': 0, 'denominator': 0, 'value': None}


def compare_script(frozen, script_raw, *, expected_script_sha256, parameters_raw=None,
                   expected_parameters_sha256=None, plan_raw=None, expected_plan_sha256=None,
                   decisions_raw=b'{}', expected_decisions_config_sha256=None, synthetic_controls=None, legacy_script_raw=None):
    need(isinstance(frozen, v1.FrozenOutput), 'OUTPUT_INTEGRITY', 'Output must be frozen first')
    need(v1.sha(script_raw) == expected_script_sha256, 'SCRIPT_INTEGRITY', 'Evaluation script pin mismatch')
    script = v1.load_json(script_raw)
    response, records = v1.load_json(frozen.response_bytes), v1.load_json(frozen.decisions_bytes)
    if not isinstance(script, dict) or script.get('schema_version') != 'q5-evaluation-script.v2':
        v1.require(response['status'] == 'COMPLETE', 'Only COMPLETE sessions are scoreable')
        return v1.compare_script(frozen, script_raw, expected_script_sha256=expected_script_sha256)
    need(script.get('schema_version') == 'q5-evaluation-script.v2', 'SCRIPT_INTEGRITY', 'Unsupported evaluation script')
    need(expected_decisions_config_sha256 == v1.sha(decisions_raw), 'DECISION_CONFIG_INVALID', 'Decision config bytes pin required')
    selected = config(decisions_raw)
    if 'lifted_from_v1_sha256' in script:
        return compare_lifted_script(frozen, script, expected_script_sha256, legacy_script_raw, expected_decisions_config_sha256)
    synthetic = _synthetic(synthetic_controls, script, response)
    scope = response['resolved_scope']; query = script.get('session_query_range_us')
    need(v1._range(query) and {'run_id': script.get('run_id'), 'range_us': query} in scope.get('resolved_source_ranges_us', [])
         and script.get('run_id') == scope['run_ids'][0] and script.get('clock_id') == scope['clock_ids'][0], 'SCRIPT_INTEGRITY', 'Script session range/run/clock mismatch')
    need(script.get('status') in {'PROPOSED', 'APPROVED'}, 'SCRIPT_INTEGRITY', 'Script status required')
    if script['status'] == 'APPROVED':
        approval_pin = script.get('approval_content_sha256')
        need(isinstance(script.get('approval_ref'), str) and bool(script['approval_ref'])
             and isinstance(approval_pin, str) and len(approval_pin) == 64
             and all(c in '0123456789abcdef' for c in approval_pin), 'SCRIPT_INTEGRITY', 'Approved content pin required')
    need(isinstance(parameters_raw, bytes) and isinstance(plan_raw, bytes), 'PARAMETER_INTEGRITY', 'Frozen parameters and plan bytes required')
    parameters = parameter_values(parameters_raw, expected_parameters_sha256, script, scope)
    need(v1.sha(plan_raw) == expected_plan_sha256 == script.get('plan_ref', {}).get('sha256'), 'SCRIPT_PLAN_MISMATCH', 'Plan bytes pin mismatch')
    v1.load_json(plan_raw)  # Integrity only: no t_V/t_L/GT method is selected here.
    # v1 validates timeline/decision bindings and provides the exact observed
    # action representation. A private validation window changes no input file.
    validation = {'schema_version': 'q5-evaluation-script.v1', 'status': 'PROPOSED',
        'approval_ref': None, 'run_id': script['run_id'], 'clock_id': script['clock_id'],
        'events': [{'event_id': 'VALIDATION_ONLY', 'action': 'NO_SWITCH', 'decision_window_us': query}]}
    raw = v1.canonical(validation)
    try:
        verified = v1.compare_script(frozen, raw, expected_script_sha256=v1.sha(raw))
    except v1.EvaluationError as error:
        raise EvaluationError('OUTPUT_INTEGRITY', str(error)) from error
    executed = sorted(verified['events'][0]['observed'], key=lambda a: (a['decision_time_us'], a['decision_id']))
    limited = response['status'] == 'ENDED_BY_LIMIT'
    ended = [row for row in records if row.get('state_after') == 'ENDED']
    cutoff = ended[-1]['source_time_us'] if limited else query[1]
    need(query[0] <= cutoff <= query[1], 'OUTPUT_INTEGRITY', 'ENDED cutoff outside query')
    events = script.get('events'); need(isinstance(events, list) and bool(events), 'SCRIPT_INTEGRITY', 'Nonempty event list required')
    rows, seen, covered = [], set(), set(); last_end = query[0]; planned = 0
    for event in events:
        eid, window = event.get('event_id'), event.get('decision_window_us')
        need(isinstance(eid, str) and eid and eid not in seen, 'SCRIPT_INTEGRITY', 'Duplicate/missing event ID'); seen.add(eid)
        need(v1._range(window) and last_end <= window[0] < window[1] <= query[1], 'SCRIPT_PLAN_MISMATCH', 'Events must be ordered/disjoint/in scope')
        action, kind = event.get('action'), event.get('event_class')
        need(action in {'SWITCH', 'RETURN_TO_ORIGIN', 'NO_SWITCH'} and kind in {'STANDARD', 'LONG_GAP', 'LONG_LOSS'}, 'SCRIPT_PLAN_MISMATCH', 'Unsupported event class/action')
        maximum, searches = derive(event, last_end, query, parameters, selected); planned += searches; last_end = window[1]
        budget = parameters[-1] - 2 if selected['U-D10'] == 'N_MAX_MINUS_TWO' else min(3, parameters[-1])
        need(planned <= budget, 'PLANNED_SEARCH_BUDGET', 'Plan exceeds selected/default conservative search budget')
        observed = [a for a in executed if window[0] <= a['decision_time_us'] < window[1]]
        covered.update(a['decision_id'] for a in observed)
        returns = sum(a['action'] == 'RETURN_TO_ORIGIN' for a in observed)
        switches = [a for a in observed if a['action'] == 'SWITCH']
        entry_map = event.get('entry_windows_us', {})
        overlap = any(e.get('kind') == 'OVERLAP' for e in entry_map.values())
        for entry in entry_map.values():
            need(v1._range(entry.get('range_us')) and query[0] <= entry['range_us'][0] < entry['range_us'][1] <= query[1], 'SCRIPT_PLAN_MISMATCH', 'Entry outside scope')
        match, reason = None, None
        if limited and selected['U-D4'] in {PENDING, 'E1', 'E3'}:
            reason = 'NOT_SCORED_PENDING_DECISION' if selected['U-D4'] == PENDING else 'NOT_SCORED_LIMIT'
        elif limited and not synthetic:
            reason = 'PREFIX_EVIDENCE_UNSELECTED'
        elif limited and window[1] > cutoff:
            reason = 'COVERAGE_MISSING'
        elif overlap and not (synthetic and set(synthetic_controls.overlap_pair) == {'CAM_EXT_CAR', 'CAM_EXT_CLEAR'}
                              and synthetic_controls.exit_strip_present and len(entry_map) == 1
                              and set(entry_map) <= set(synthetic_controls.overlap_pair)):
            reason = 'OVERLAP_AUTHORITY_UNSELECTED'
        elif kind.startswith('LONG_') and (selected['U-D1'] == PENDING or selected['U-D2'] == PENDING
             or selected['U-D5'] == PENDING or selected['U-D6'] == PENDING
             or selected['U-D7'] == PENDING or kind == 'LONG_GAP' and selected['U-D9'] == PENDING):
            reason = 'NOT_SCORED_PENDING_DECISION'
        else:
            if action == 'SWITCH':
                chosen = observed[-1] if observed else None
                valid = chosen is not None and chosen['action'] == 'SWITCH' and chosen['camera_id'] in entry_map
                if valid:
                    span = entry_map[chosen['camera_id']]['range_us']
                    valid = span[0] <= chosen['entry_time_us'] < span[1]
                pattern = len(observed) == 1 if kind == 'STANDARD' else len(switches) == 1 and observed[-1]['action'] == 'SWITCH'
                if kind.startswith('LONG_') and selected['U-D1'] == 'M3':
                    pattern = bool(observed) and observed[-1]['action'] == 'SWITCH'
                match = bool(pattern and valid)
            elif action == 'RETURN_TO_ORIGIN':
                match = (len(observed) == 1 if kind == 'STANDARD' else bool(observed)) and not switches
            else:
                complete = any(r['source_time_us'] >= window[1] for r in records)
                match = not switches if complete else None
                if match is None:
                    reason = 'COVERAGE_MISSING'
            if kind.startswith('LONG_') and (selected['U-D1'] == 'M2' or kind == 'LONG_LOSS' and selected['U-D2'] == 'EXCESS_IS_MISS') and returns > maximum:
                match = False
        groups = {a['source_group'] for a in observed}; group = next(iter(groups)) if len(groups) == 1 else 'OTHER'
        starts = [s for s in searching_starts(records) if window[0] <= s['source_time_us'] < window[1]]
        rows.append({'event_id': eid, 'event_class': kind, 'expected_action': action, 'match': match,
            'reason': reason, 'source_group': group, 'observed': observed, 'return_count': returns,
            'return_count_max': maximum, 'return_count_exceeds_max': maximum is not None and returns > maximum,
            'searching_count': len(starts), 'user_searching_count': sum(s.get('decided_by') == 'USER' for s in starts),
            'overlap': overlap, 'entry_window_us': next(iter(entry_map.values()))['range_us'] if len(entry_map) == 1 else None,
            'matched_camera_kind': entry_map.get(switches[-1]['camera_id'], {}).get('kind') if switches and match is True else None})
    main = [] if limited else [r for r in rows if not r['overlap']]
    overlap_rows = [r for r in rows if r['overlap']]
    status = 'MEASURED_PROPOSED_RULES'
    if all(r['match'] is None for r in rows):
        status = 'NOT_SCORED_PENDING_DECISION' if any(r['reason'] == 'NOT_SCORED_PENDING_DECISION' for r in rows) else 'NOT_SCORED'
    elif limited:
        status = 'MEASURED_PARTIAL_ENDED_BY_LIMIT'
    elif overlap_rows and not main:
        status = 'OVERLAP_P_OV2_UNVERIFIED'
    report = {'schema_version': 'q5-switch-eval-report.v2', 'scorer_version': VERSION, 'status': status,
        'run_id': script['run_id'], 'clock_id': script['clock_id'], 'script_status': script['status'],
        'human_approval_verified': False, 'synthetic_controls': synthetic, 'formal_accepted': False,
        'response_file_sha256': frozen.response_file_sha256, 'decisions_file_sha256': frozen.decisions_file_sha256,
        'script_file_sha256': expected_script_sha256, 'parameter_file_sha256': expected_parameters_sha256,
        'plan_file_sha256': expected_plan_sha256, 'decisions_config_sha256': expected_decisions_config_sha256,
        'selected_decisions': selected, 'events': rows, 'event_match_ratio': v1._ratio(main),
        'standard_event_match_ratio': v1._ratio([r for r in main if r['event_class'] == 'STANDARD']),
        'by_event_class': {k: v1._ratio([r for r in main if r['event_class'] == k]) for k in ('STANDARD', 'LONG_GAP', 'LONG_LOSS')},
        'overlap_ratio': v1._ratio([] if limited else overlap_rows),
        'partial_ratio': v1._ratio([r for r in rows if not r['overlap']]) if limited else _empty_ratio(),
        'partial_overlap_ratio': v1._ratio(overlap_rows) if limited else _empty_ratio(),
        'cutoff_us': cutoff if limited else None, 'planned_searching_count': planned,
        'uncovered_executed_actions': [a for a in executed if a['decision_id'] not in covered],
        'agent_used_reported': response.get('agent_used'), 'fallback_used_reported': response.get('fallback_used'),
        'limits': ['Evaluation only; identity remains UNCONFIRMED.', 'Selections and self-consistent hashes do not verify human approval.',
                   'Formal LIMIT prefix and OVERLAP evidence adapters are unselected and fail closed.']}
    if selected['U-D7'] == 'MAIN_RATIO_ONLY':
        # D93 and LIMIT exclusions remain, regardless of presentation choice.
        del report['standard_event_match_ratio']
        del report['by_event_class']
    report['output_sha256'] = v1.digest(report, 'output_sha256')
    return report


def lift_v1_script(raw):
    """Compatibility projection only; cannot be used as a native v2 plan."""
    script = v1.load_json(raw)
    v1.require(isinstance(script, dict) and script.get('schema_version') == 'q5-evaluation-script.v1', 'Explicit v1 script required')
    out = deepcopy(script); out['schema_version'] = 'q5-evaluation-script.v2'
    out['lifted_from_v1_sha256'] = v1.sha(raw)
    for event in out['events']:
        event['event_class'] = 'STANDARD'
        if event['action'] == 'SWITCH':
            span = event.pop('entry_window_us')
            event['entry_windows_us'] = {camera: {'kind': 'BLIND', 'range_us': list(span)} for camera in event.pop('allowed_camera_ids')}
    return out


def compare_lifted_script(frozen, script, script_pin, legacy_raw, decisions_pin):
    need(isinstance(legacy_raw, bytes) and v1.sha(legacy_raw) == script['lifted_from_v1_sha256'],
         'SCRIPT_INTEGRITY', 'Lift requires the original v1 bytes')
    need(script == lift_v1_script(legacy_raw), 'SCRIPT_PLAN_MISMATCH', 'Lift must preserve every original v1 field')
    need(v1.load_json(frozen.response_bytes)['status'] == 'COMPLETE', 'OUTPUT_INTEGRITY', 'v1 lift requires COMPLETE')
    report = deepcopy(v1.compare_script(frozen, legacy_raw, expected_script_sha256=v1.sha(legacy_raw)))
    report.update(schema_version='q5-switch-eval-report.v2', scorer_version=VERSION,
        script_file_sha256=script_pin, lifted_from_v1_sha256=v1.sha(legacy_raw),
        decisions_config_sha256=decisions_pin, standard_event_match_ratio=report['event_match_ratio'],
        by_event_class={'STANDARD': report['event_match_ratio']}, human_approval_verified=False, formal_accepted=False)
    for row in report['events']:
        row['event_class'] = 'STANDARD'
    report['output_sha256'] = v1.digest(report, 'output_sha256')
    return report


def score_files(paths, pins, *, decisions_raw, synthetic_controls=None):
    def read(name):
        path = Path(paths[name])
        need(path.resolve() == path.absolute() and path.is_file() and not path.is_symlink(), 'INPUT_PATH_INVALID', 'Canonical regular file required')
        return path.read_bytes()
    frozen = freeze_output(read('response'), read('decisions'),
        expected_response_sha256=pins['response'], expected_decisions_sha256=pins['decisions'])
    script_raw = read('script')  # Deliberately after successful output verification.
    script = v1.load_json(script_raw)
    if not isinstance(script, dict) or script.get('schema_version') != 'q5-evaluation-script.v2':
        return compare_script(frozen, script_raw, expected_script_sha256=pins['script'])
    return compare_script(frozen, script_raw, expected_script_sha256=pins['script'],
        parameters_raw=read('parameters'), expected_parameters_sha256=pins['parameters'],
        plan_raw=read('plan'), expected_plan_sha256=pins['plan'],
        decisions_raw=decisions_raw, expected_decisions_config_sha256=pins.get('decisions_config', v1.sha(decisions_raw)), synthetic_controls=synthetic_controls,
        legacy_script_raw=read('legacy_script') if 'legacy_script' in paths else None)
