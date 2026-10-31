"""Evaluation-only, UNFROZEN v2 plan adapter. Never an approval authority.

The private planning file is a PROPOSED configuration, not a runtime wire. Only
the #258 evaluation-script.v2 projection leaves it. Camera plan checks never
leave this module; no GT, renderer, media, runtime or inference imports.
"""
from dataclasses import dataclass

from amidst.evaluation import q5_switch_eval as v1
from amidst.evaluation import q5_switch_eval_v2 as scorer

VERSION = 'q5-script-adapter-v2.0'
PLAN_SCHEMA = 'q5-script-plan.v2'


class PlanError(ValueError):
    def __init__(self, category, message):
        self.category = category
        super().__init__(message)


def need(condition, category, message):
    if not condition:
        raise PlanError(category, message)


@dataclass(frozen=True)
class SyntheticPlanInputs:
    """Explicit in-memory fixture seam; never accepted from a JSON field/CLI."""


def _synthetic(controls, plan):
    if controls is None:
        return False
    need(isinstance(controls, SyntheticPlanInputs)
         and plan.get('status') == 'UNFROZEN'
         and all(isinstance(plan.get(k), str) and plan[k].startswith(('SYNTHETIC-', 'SYNTHETIC_'))
                 for k in ('run_id', 'clock_id', 'plan_id')),
         'SYNTHETIC_SCOPE_REQUIRED', 'Synthetic inputs cannot authorize a real plan')
    return True


def _parameters(raw, pin, plan, synthetic):
    need(v1.sha(raw) == pin, 'PARAMETER_INTEGRITY', 'Parameter bytes pin mismatch')
    doc = v1.load_json(raw)
    need(isinstance(doc, dict), 'PARAMETER_INTEGRITY', 'Parameter document required')
    if doc.get('schema_version') == 'q-demo.parameter-set.v1':
        rows = doc.get('parameters', [])
        values = {r['name']: r['value'] for r in rows}
        interval = doc.get('applies_to', {}).get('index_interval_us')
        if interval is not None:
            need('index_interval_us' not in values or values['index_interval_us'] == interval,
                 'PARAMETER_INTEGRITY', 'Conflicting index interval')
            values['index_interval_us'] = interval
        binding = {k: values.get(k) for k in scorer.PARAMETERS}
        binding.update(parameter_set_id=doc.get('parameter_set_id'), parameter_set_sha256=doc.get('content_sha256'))
        params = scorer.parameter_values(raw, pin, {'run_id': plan['run_id'], 'parameter_binding': binding}, binding)
    else:
        need(synthetic and set(doc) == set(scorer.PARAMETERS) | {'parameter_set_id'}
             and str(doc['parameter_set_id']).startswith('SYNTHETIC-'),
             'PARAMETER_INTEGRITY', 'Frozen q-demo parameter document required')
        binding = {**doc, 'parameter_set_sha256': v1.sha(v1.canonical(doc))}
        params = tuple(doc[k] for k in scorer.PARAMETERS)
        need(all(type(v) is int and v > 0 for v in params), 'PARAMETER_INTEGRITY', 'Positive integer parameters required')
        d, l, w, r, n = params
        need(l % d == w % d == r % d == 0 and w + d > r and n >= 2,
             'PARAMETER_INTEGRITY', 'Invalid parameter grid or search bound')
    expected = plan.get('parameter_binding')
    need(expected is None or expected == binding, 'PARAMETER_INTEGRITY', 'Plan parameter binding mismatch')
    if 'parameters' in plan:
        need(plan['parameters'] == {k: binding[k] for k in scorer.PARAMETERS},
             'PARAMETER_INTEGRITY', 'Plan numeric parameters differ from frozen document')
    return binding, params


def _camera_checks(camera, values, event, params, selected, synthetic):
    """Plan admission only; no returned timing can become a scoring anchor."""
    d, l, w, r, n = params
    check = values.get('plan_checks_only')
    need(synthetic and selected['UK-8'] == 'PLAN_CHECK_ONLY'
         and isinstance(check, dict) and check.get('evidence_kind') == 'SYNTHETIC_PLAN_CHECK_ONLY',
         'PLAN_CHECK_EVIDENCE_UNSELECTED', 'Timing-method evidence is unselected; UNKNOWN cannot pass')
    tl, tv, tx = check.get('t_L_us'), check.get('t_V_us'), event['t_x_us']
    need(type(tl) is int and type(tv) is int and tl >= 0 and tv >= 0,
         'PLAN_CHECK_EVIDENCE_UNSELECTED', 'Plan check times must be explicit')
    if values['kind'] == 'BLIND':
        tn = values.get('t_N_us')
        need(type(tn) is int and tn >= tx, 'PLAN_INVALID', 'BLIND plan entry must follow exit')
        need(tv >= tn - l, 'EARLY_VISIBLE_BLIND', 'Early-visible BLIND plan refused, including pending U-D6')
        need(tl <= tn - 1000000, 'BLIND_PLAN_CHECK', 'BLIND last-visible condition fails')
    else:
        need({event.get('origin_camera_id'), camera} == {'CAM_EXT_CAR', 'CAM_EXT_CLEAR'},
             'BLOCKED_GEOMETRY', 'D93 permits only the EXT pair; W1/W2 and BRANCH/WIDE remain closed')
        end = check.get('continuous_until_us')
        need(tv <= tx - l and tx - d <= tl <= tx and type(end) is int and end >= tx + l + r + 5000000,
             'OVERLAP_PLAN_CHECK', 'Synthetic P-OV1/P-OV2 duration/alignment fails')


def generate_script(plan_raw, *, expected_plan_sha256, parameters_raw, expected_parameters_sha256,
                    decisions_raw, expected_decisions_sha256, plan_path, formal=False, synthetic_controls=None):
    """Return (PROPOSED script, planned searches), or a classified refusal.

    This phase cannot freeze or approve a script. Formal evidence adapters and
    U6/U7 adoption are intentionally absent, rather than emulated by self pins.
    """
    try:
        return _generate(plan_raw, expected_plan_sha256=expected_plan_sha256,
            parameters_raw=parameters_raw, expected_parameters_sha256=expected_parameters_sha256,
            decisions_raw=decisions_raw, expected_decisions_sha256=expected_decisions_sha256,
            plan_path=plan_path, formal=formal, synthetic_controls=synthetic_controls)
    except scorer.EvaluationError as error:
        category = {'D94_FORBIDDEN_INTERVAL': 'D94_RETURN_GAP', 'PLANNED_SEARCH_BUDGET': 'SEARCHING_BUDGET'}.get(error.category, error.category)
        raise PlanError(category, str(error)) from error
    except v1.EvaluationError as error:
        raise PlanError('INPUT_INTEGRITY', str(error)) from error
    except (KeyError, TypeError, AttributeError, IndexError) as error:
        raise PlanError('PLAN_INVALID', 'Malformed private plan or parameter document') from error


def _generate(plan_raw, *, expected_plan_sha256, parameters_raw, expected_parameters_sha256,
              decisions_raw, expected_decisions_sha256, plan_path, formal, synthetic_controls):
    need(not formal, 'HUMAN_APPROVAL_UNSELECTED', 'Formal generation requires adopted U6/U7 evidence; this adapter emits UNFROZEN previews only')
    need(v1.sha(plan_raw) == expected_plan_sha256, 'INPUT_INTEGRITY', 'Plan bytes pin mismatch')
    plan = v1.load_json(plan_raw)
    need(isinstance(plan, dict) and plan.get('schema_version') == PLAN_SCHEMA, 'VERSION_UNSUPPORTED', 'Explicit v2 plan required; v1 is not converted')
    need(plan.get('status') == 'UNFROZEN', 'HUMAN_APPROVAL_UNSELECTED', 'Only explicitly UNFROZEN plans are supported')
    need(plan.get('geometry_status') != 'BLOCKED_GEOMETRY', 'BLOCKED_GEOMETRY', 'Blocked geometry is not an executable card')
    need(v1.sha(decisions_raw) == expected_decisions_sha256, 'INPUT_INTEGRITY', 'Decision config bytes pin mismatch')
    selected = scorer.config(decisions_raw)
    need(selected['U-D5'] != scorer.PENDING, 'PROPOSED_RULE_UNSELECTED', 'U-D5 is pending; no proposed plan is emitted')
    synthetic = _synthetic(synthetic_controls, plan)
    for key in ('run_id', 'clock_id', 'plan_id'):
        need(isinstance(plan.get(key), str) and plan[key].strip() and plan[key].strip().upper() != 'UNKNOWN', 'PLAN_UNRESOLVED', key + ' is UNKNOWN')
    query = plan.get('query_range_us')
    need(v1._range(query), 'PLAN_INVALID', 'Explicit query range required')
    need(type(plan.get('source_duration_us')) is int and plan['source_duration_us'] >= query[1], 'PLAN_INVALID', 'Source duration must cover query')
    need(isinstance(plan_path, str) and bool(plan_path.strip()), 'INPUT_INTEGRITY', 'Explicit plan locator required')
    binding, params = _parameters(parameters_raw, expected_parameters_sha256, plan, synthetic)
    original = plan.get('events')
    need(isinstance(original, list) and bool(original), 'PLAN_INVALID', 'Nonempty ordered events required')
    events, seen, previous, searches = [], set(), query[0], 0
    for source in original:
        eid, action, tx = source.get('event_id'), source.get('action'), source.get('t_x_us')
        need(isinstance(eid, str) and eid and eid not in seen, 'PLAN_INVALID', 'Unique event IDs required'); seen.add(eid)
        need(source.get('event_class') != 'UNKNOWN', 'PLAN_UNRESOLVED', 'Card event classification is unresolved')
        need(action in {'SWITCH', 'RETURN_TO_ORIGIN'} and type(tx) is int, 'PLAN_INVALID', 'First-batch action/exit required')
        event = {'event_id': eid, 'action': action, 'plan_anchor_us': {'t_X': tx}}
        if action == 'RETURN_TO_ORIGIN':
            event['plan_anchor_us']['t_N'] = source.get('t_n_us')
        else:
            cameras = source.get('cameras')
            need(isinstance(cameras, dict) and bool(cameras), 'PLAN_INVALID', 'Per-camera plans required')
            event['entry_windows_us'] = {}; event['plan_anchor_us']['t_N_by_camera'] = {}
            for camera, values in cameras.items():
                need(isinstance(camera, str) and camera and values.get('kind') in {'BLIND', 'OVERLAP'}, 'PLAN_INVALID', 'Explicit camera entry kind required')
                _camera_checks(camera, values, source, params, selected, synthetic)
                event['entry_windows_us'][camera] = {'kind': values['kind']}
                if values['kind'] == 'BLIND':
                    event['plan_anchor_us']['t_N_by_camera'][camera] = values.get('t_N_us')
        calculated, count, maximum = scorer.derive_plan_event(event, previous, query, params, selected)
        if calculated['event_class'] == 'LONG_GAP':
            need(selected['U-D9'] != scorer.PENDING, 'PROPOSED_RULE_UNSELECTED', 'LONG_GAP window choice is pending')
        need(source.get('event_class') in {None, calculated['event_class']}, 'PLAN_INVALID', 'Declared class differs from computed plan')
        window = calculated['decision_window_us']
        need(v1._range(window) and previous <= window[0] < window[1] <= query[1], 'PLAN_INVALID', 'Derived window outside query/order')
        for value in calculated.get('entry_windows_us', {}).values():
            span = value['range_us']
            need(v1._range(span) and query[0] <= span[0] < span[1] <= query[1], 'PLAN_INVALID', 'Derived entry outside query')
        searches += count
        budget = params[-1] - 2 if selected['U-D10'] == 'N_MAX_MINUS_TWO' else min(3, params[-1])
        need(searches <= budget, 'SEARCHING_BUDGET', 'Planned SEARCHING exceeds selected/default conservative budget')
        previous = window[1]; events.append(calculated)
    # Output is a whitelist projection. Source checks, geometry status and raw
    # plan fields never leak into the evaluation-script schema or safe bundles.
    script = {'schema_version': 'q5-evaluation-script.v2', 'status': 'PROPOSED',
              'approval_ref': None, 'approval_content_sha256': None,
              'run_id': plan['run_id'], 'clock_id': plan['clock_id'], 'session_query_range_us': query,
              'parameter_binding': binding, 'plan_ref': {'path': plan_path, 'sha256': expected_plan_sha256}, 'events': events}
    return script, searches
