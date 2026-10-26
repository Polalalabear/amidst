"""Finite state sequences, deterministic schedules and visible unresolved gaps.

XFAILs assert desired safety/progress, not the current bug. Precondition failures
raise RuntimeError and cannot be hidden by the narrow raises=AssertionError mark.
"""

from functools import lru_cache

import pytest
from q5_audit_source import run_pinned


@pytest.mark.parametrize("length", range(7))
def test_all_local_sequences_up_to_six_ticks_match_independent_gap_oracle(length):
    evidence = run_pinned(f"""
from itertools import product
from copy import deepcopy
from test_linker import linker, record, observation, LinkError
checked = 0
ended_rejections = 0
arcs = set()
for events in product(('linked', 'empty', 'missing', 'ambiguous'), repeat={length}):
    tracker = linker()
    state = 'PLAYING'
    last_matched = 0
    for frame, event in enumerate(events, 1):
        if event == 'linked':
            row = record(frame, obs=[observation(frame)])
        elif event == 'missing':
            row = record(frame, 'MISSING')
        elif event == 'ambiguous':
            row = record(frame, obs=[observation(frame, 0), observation(frame, 1)])
        else:
            row = record(frame)
        if state == 'SEARCHING':
            before = deepcopy(vars(tracker))
            try:
                tracker.step(row)
            except LinkError:
                ended_rejections += 1
            else:
                raise AssertionError('Ended local segment was resurrected')
            assert before == vars(tracker)
            continue
        before = state
        previous_matched = last_matched
        # Independent oracle on event type and source ticks, not product fields.
        if event == 'linked':
            last_matched = frame
            state = 'PLAYING'
        else:
            state = 'SEARCHING' if frame - last_matched >= 3 else 'TEMP_LOST'
        step = tracker.step(row)
        assert step.state == state
        assert step.link['gap_samples'] == frame - previous_matched - int(event == 'linked')
        if event == 'linked':
            # A supported cell itself does not count as a missing cell.
            assert step.link['next_observation_id'] == observation(frame)['observation_id']
        else:
            assert step.link['next_observation_id'] is None and step.link['iou'] is None
        arcs.add((before, state))
    checked += 1
result = {{'sequences': checked, 'length': {length}, 'ended_rejections': ended_rejections,
           'arcs': sorted(arcs)}}
""")
    assert evidence["sequences"] == 4**length


@pytest.mark.parametrize("fault", ["duplicate", "backwards", "timestamp", "camera", "ambiguous"])
def test_rejected_or_ambiguous_events_cannot_silently_change_attachment(fault):
    result = run_pinned(f"""
from copy import deepcopy
from test_linker import linker, record, observation, LinkError
tracker = linker()
tracker.step(record(1, obs=[observation(1)]))
before = deepcopy(vars(tracker))
fault = {fault!r}
row = record(2, obs=[observation(2)])
if fault == 'duplicate': row = record(1, obs=[observation(1)])
elif fault == 'backwards': row = record(0, obs=[observation(0)])
elif fault == 'timestamp': row['timestamp_us'] += 1
elif fault == 'camera': row['camera_id'] = 'FOREIGN'
else: row['detections'].append(observation(2, 1))
if fault == 'ambiguous':
    step = tracker.step(row)
    assert step.link['decision'] == 'AMBIGUOUS_LINK'
    assert step.link['next_observation_id'] is None and tracker.last == before['last']
else:
    try: tracker.step(row)
    except LinkError: pass
    else: raise AssertionError('Bad input accepted')
    assert vars(tracker) == before
result = {{'fault': fault, 'last_observation': tracker.last['observation_id']}}
""")
    assert result["fault"] == fault


@pytest.mark.parametrize("source", ["evidence", "provider"])
def test_manual_override_wins_over_late_automatic_result_without_refunding_counts(source):
    result = run_pinned(f"""
from test_q5_agent import bindings, AgentController, PolicyProvider, auto, settings
pattern = {{'A': {{0: 'STRONG', 1: 'STRONG'}},
           'B': {{i: 'STRONG' for i in range(5, 10)}},
           'E': {{i: 'STRONG' for i in range(6, 10)}}}}
b = bindings(pattern, cameras=('A', 'B', 'E'))
holder = {{}}
normal = port([])
def manual(): holder['c'].request_manual_seed(seed_id(b, 'E', 6))
def evidence(index, snapshot, ref, context):
    manual()
    return normal(index, snapshot, ref, context)
def policy(payload, number):
    if number == 2: manual()
    return auto(payload, number)
if {source!r} == 'evidence':
    c = RuleController(request(b), bindings=b, evidence_provider=evidence,
                       selected_observation_id=seed_id(b))
else:
    q = request(b); q['switch_mode'] = 'AGENT_SEQUENTIAL'
    c = AgentController(q, bindings=b, evidence_provider=normal,
        selected_observation_id=seed_id(b), provider=PolicyProvider(policy),
        agent_settings=settings(), round_scheduler=lambda *a: None, clock=lambda: 0)
holder['c'] = c
r = c.run()
d = [json.loads(s) for s in r.decisions_bytes.splitlines()]
assert any(x['rejection_code'] == 'USER_OVERRIDE' for x in d)
assert not any(x['executed_action'] == 'SWITCH' for x in d)
assert r.response['timeline'][-1]['camera_id'] == 'E'
counts = [x['session_agent_rounds_used'] for x in d]
assert counts == sorted(counts)
assert max(x['searching_index'] for x in d) == 2
result = {{'source': {source!r}, 'manual_camera': 'E',
           'journal': bundle(r, b)}}
""")
    assert result["manual_camera"] == "E"


@pytest.mark.parametrize("budget", [1, 2])
def test_agent_round_exhaustion_transfers_session_to_rule_and_never_restarts_agent(budget):
    result = run_pinned(f"""
from test_q5_agent import bindings, run_agent
from q5_invariant_helpers import check_journal
b = bindings({{'A': {{0: 'STRONG', 1: 'STRONG'}}}}, session_max_agent_rounds={budget})
c, r, provider, calls = run_agent(b)
d = [json.loads(s) for s in r.decisions_bytes.splitlines()]
assert r.response['status'] == 'COMPLETE' and len(r.snapshots) > 1
assert len(provider.requests) <= {budget} and r.response['fallback_used']
report = check_journal(bundle(r, b))
assert not report.violations, report
result = {{'model_calls': len(provider.requests), 'researches': len(r.snapshots),
           'report': asdict(report)}}
""")
    assert result["model_calls"] <= budget and result["researches"] > 1


def test_sequential_identical_request_is_idempotent_and_has_no_extra_agent_calls():
    result = run_pinned("""
from test_api import api_fixture, q2, authorize
api, b = api_fixture(agent=True)
q = q2(b); q['switch_mode'] = 'AGENT_SEQUENTIAL'
payload = {'request': q, 'selected_observation_id': seed_id(b.bindings)}
runs = []
original = api._controller
def make(*a, **kw):
    c = original(*a, **kw); run = c.run
    def counted():
        runs.append(c.session_id)
        return run()
    c.run = counted
    return c
api._controller = make
first = api.call('q2_select_seed', payload, authorize)
second = api.call('q2_select_seed', payload, authorize)
result = {'same_response': first == second, 'executions': len(runs)}
""")
    assert result == {"same_response": True, "executions": 1}


def test_mechanical_rule_hashes_ignore_wall_latency_without_changing_raw_evidence():
    result = run_pinned("""
import itertools
import time
b = fixture()
first, _ = run(b)
previous = time.perf_counter
ticks = itertools.count(step=10)
try:
    time.perf_counter = lambda: next(ticks)
    second, _ = run(b)
finally:
    time.perf_counter = previous
result = {'output_equal': first.response['output_sha256'] == second.response['output_sha256'],
          'decisions_equal': first.decisions_bytes == second.decisions_bytes,
          'links_equal': first.links_bytes == second.links_bytes,
          'stats_differ': first.response['stats'] != second.response['stats']}
""")
    assert all(result.values()), result


@lru_cache(maxsize=1)
def known_gaps():
    return run_pinned("""
import threading
from test_agent_tools import tools_fixture, fetch, base
from test_api import api_fixture, selected, q2, authorize, APIError
from amidst.q1q5.api import POST_ROUTES
from amidst.q1q5.q5_agent import AgentController

def precondition(ok, message):
    if not ok: raise RuntimeError(message)

r, _ = run()
d = [json.loads(s) for s in r.decisions_bytes.splitlines()]
precondition(any(x['executed_action'] == 'SWITCH' for x in d), 'No switch to inspect')
switching = any(x['state_after'] == 'SWITCHING' for x in d)

t, _ = tools_fixture({'A': {0: 'STRONG', 1: 'STRONG'},
                     'E': {i: 'STRONG' for i in range(5, 10)}}, cameras=('A', 'B', 'E'))
e = fetch(t)
proposal = {'schema_version': 'q-demo.agent-decision.v1', **base(t),
    'candidate_snapshot_sha256': t.snapshot['candidate_snapshot_sha256'],
    'action': 'NEXT_CANDIDATE', 'candidate_ref': t.current()['candidate_ref'],
    'cited_observation_ids': [], 'rationale': 'SYNTHETIC no observation evidence'}
next_result = t.dispatch('submit_decision', proposal)
precondition(e['target_presence'] == 'NO_PERSON_DETECTED', 'First evidence changed')
chosen, _, _ = t.controller._select(t.snapshot, t.decision_time_us)
precondition(chosen is not None and chosen[0]['camera_id'] == 'E', 'RULE cannot reach E')

api, binding = api_fixture(agent=True)
lock = threading.Lock(); runs = []; original = api._controller
def make(*a, **kw):
    c = original(*a, **kw); execute = c.run
    def counted():
        with lock: runs.append(c.session_id)
        return execute()
    c.run = counted
    return c
api._controller = make
entered = threading.Event(); release = threading.Event(); old_bundle = api._bundle
first = [True]
def bundle_gate(*a, **kw):
    with lock:
        pause = first[0]; first[0] = False
    if pause:
        entered.set()
        if not release.wait(5): raise RuntimeError('Publication gate timed out')
    return old_bundle(*a, **kw)
api._bundle = bundle_gate
answers = []; errors = []
def execute():
    try: answers.append(selected(api, binding))
    except Exception as error: errors.append(repr(error))
thread = threading.Thread(target=execute)
thread.start()
try:
    precondition(entered.wait(5), 'Did not reach publication gate')
    execute()
finally:
    release.set(); thread.join(5)
precondition(not thread.is_alive() and not errors and len(answers) == 2, 'Race probe failed')
precondition(answers[0]['session_id'] == answers[1]['session_id'], 'Different sessions')

from dataclasses import replace
from test_api import run_binding, TOKEN
from test_q5_agent import PolicyProvider, auto, settings
from amidst.q1q5.api import QAPI
entered = threading.Event(); release = threading.Event()
def tick(timestamp, c):
    if timestamp == 200000:
        entered.set()
        if not release.wait(5): raise RuntimeError('Stop gate timed out')
def factory(q, **args):
    return AgentController(q, **args, provider=PolicyProvider(auto), agent_settings=settings(),
        round_scheduler=lambda *a: None, clock=lambda: 0, on_tick=tick)
binding = replace(run_binding(agent=True), agent_factory=factory)
stop_api = QAPI([binding], max_responses=128, max_media_refs=4096)
q = q2(binding); q['switch_mode'] = 'AGENT_SEQUENTIAL'
job = stop_api.call('q2_start_session', {'request': q,
    'selected_observation_id': seed_id(binding.bindings)}, authorize)
try:
    precondition(entered.wait(5), 'No active session for stop probe')
    active = next(iter(stop_api._active.values()))
    methods = [n for n in ('stop', 'cancel', 'request_stop') if callable(getattr(active, n, None))]
    routes = sorted(n for n in POST_ROUTES if 'stop' in n or 'cancel' in n)
    # Probe name is hypothetical, not an approved proposed wire endpoint.
    try:
        stop_api.call('q2_stop_session', {'session_ref': TOKEN,
            'response_ref': job['session_id']}, authorize)
    except APIError as error: stop_error = error.code
    else: stop_error = None
    workers = [t for t in threading.enumerate() if t.name == 'q-session-worker']
finally:
    release.set()
for worker in workers: worker.join(5)
precondition(all(not w.is_alive() for w in workers), 'Worker did not finish')
finished = stop_api.call('q2_poll_session', {'session_ref': TOKEN,
    'response_ref': job['session_id']}, authorize)
precondition(finished['status'] == 'COMPLETE', 'Unsupported stop damaged job')
result = {
    'switching': {'property_holds': switching, 'executed_switches': 1},
    'empty_next': {'property_holds': next_result['accepted'] and t.cursor == 1,
        'actual': next_result, 'cursor': t.cursor, 'rule_camera': chosen[0]['camera_id']},
    'publication': {'property_holds': len(runs) == 1, 'executions': len(runs),
        'responses': len(answers),
        'same_output': answers[0]['output_sha256'] == answers[1]['output_sha256']},
    'stop': {'property_holds': bool(methods and routes), 'methods': methods, 'routes': routes,
        'unsupported_route_error': stop_error, 'after_release_job': finished['status']},
}
""")


def test_known_gap_probe_preconditions_and_actual_evidence_are_explicit():
    cases = known_gaps()
    assert cases["switching"]["executed_switches"] == 1
    assert cases["empty_next"]["actual"]["rejection_code"] == "UNCITED_OR_FOREIGN_REF"
    assert cases["empty_next"]["cursor"] == 0 and cases["empty_next"]["rule_camera"] == "E"
    assert cases["publication"]["executions"] == 2
    assert cases["publication"]["responses"] == 2 and cases["publication"]["same_output"]
    assert cases["stop"]["unsupported_route_error"] == "FORBIDDEN_DATA_SCOPE"
    assert cases["stop"]["after_release_job"] == "COMPLETE"


@pytest.mark.parametrize("gap", ["switching", "empty_next", "publication", "stop"])
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason="UNRESOLVED: SWITCHING / #183 / publication race / missing Q5 stop; no product fix",
)
def test_unresolved_desired_property_remains_a_visible_expected_failure(gap):
    evidence = known_gaps()[gap]
    assert evidence["property_holds"], evidence
