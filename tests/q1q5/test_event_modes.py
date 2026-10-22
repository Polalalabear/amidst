"""Mechanical policy/event/replay checks, not human answers or formal metrics."""
from copy import deepcopy
import pytest
from amidst.q1q5.event_modes import event_flags, record_mode, compare_modes, EventModeError
from amidst.q1q5.store import canonical_hash
from amidst.q1q5.q5_controller import RuleController
from amidst.q1q5.q5_agent import AgentController
from amidst.q1q5.q4_evidence import candidate_evidence
from test_q5_agent import bindings, request, seed_id, settings, PolicyProvider, auto


def seal(r):
    r['output_sha256'] = canonical_hash(r, exclude=('output_sha256', 'stats'))
    return r


def observed(left, right, camera='A'):
    return {'kind': 'ON_CAMERA', 'range_us': [left, right], 'camera_id': camera, 'observation_ids': ['obs:SYNTHETIC:' + camera]}


def gap(left, right):
    return {'kind': 'GAP', 'range_us': [left, right], 'camera_shown': 'A'}


def response(timeline):
    return seal({'schema_version': 'q-demo.q2-response.v1', 'identity_verdict': 'UNCONFIRMED',
                 'provenance': {'gt_read': False}, 'timeline': timeline})


@pytest.mark.parametrize('threshold', [None, 0, -1, True, 1.5])
def test_no_implicit_or_noninteger_lost_threshold(threshold):
    with pytest.raises(EventModeError):
        event_flags(response([]), lost_after_us=threshold)


def test_no_loss_before_seed_and_no_notification_at_query_right_boundary():
    assert event_flags(response([gap(0, 9)]), lost_after_us=2) == []
    assert event_flags(response([observed(0, 1), gap(1, 3)]), lost_after_us=2) == []


def test_deadline_recovery_does_not_flash_lost_and_switch_flag_has_bound_refs():
    later = observed(3, 5, 'B'); later['observation_ids'].append('obs:SYNTHETIC:future')
    flags = event_flags(response([observed(0, 1), gap(1, 3), later]), lost_after_us=2)
    assert [f['type'] for f in flags] == ['FOUND']
    assert flags[0]['timestamp_us'] == 3 and flags[0]['switch'] and flags[0]['observation_ids']
    assert flags[0]['observation_ids'] == ['obs:SYNTHETIC:B']


def test_long_gap_notifies_once_keeps_camera_then_recovers_same_camera_without_cut():
    flags = event_flags(response([observed(0, 1), gap(1, 3), gap(3, 6), observed(6, 8)]), lost_after_us=2)
    assert [(f['type'], f['timestamp_us'], f['camera_id']) for f in flags] == [('LOST', 3, 'A'), ('FOUND', 6, 'A')]
    assert all(not f['switch'] and f['absence_verdict'] == 'UNKNOWN' for f in flags)


@pytest.mark.parametrize('timeline', [[observed(0, 2), gap(1, 4)], [observed(0, 1), gap(2, 4)], [gap(-1, 2)], [observed(0, True)]])
def test_malformed_or_discontinuous_source_ranges_fail_closed(timeline):
    with pytest.raises(EventModeError):
        event_flags(response(timeline), lost_after_us=2)


def test_response_tamper_and_identity_claim_fail_closed():
    r = response([observed(0, 1)]); r['timeline'][0]['camera_id'] = 'B'
    with pytest.raises(EventModeError): event_flags(r, lost_after_us=2)
    r = response([]); r['identity_verdict'] = 'CONFIRMED'; seal(r)
    with pytest.raises(EventModeError): event_flags(r, lost_after_us=2)


def pair():
    b = bindings(); q = request(b); seed = seed_id(b)
    evidence = lambda i, s, r, c: candidate_evidence(i, s, r, **c)
    result = RuleController(q, bindings=b, evidence_provider=evidence, selected_observation_id=seed).run()
    backend = record_mode('BACKEND_FLAGS', q, result, selected_seed=seed, lost_after_us=600000)
    aq = deepcopy(q); aq['switch_mode'] = 'AGENT_SEQUENTIAL'
    controller = AgentController(aq, bindings=b, evidence_provider=evidence, selected_observation_id=seed,
                                 provider=PolicyProvider(auto), agent_settings=settings(), round_scheduler=lambda *x: None, clock=lambda: 0)
    ar = controller.run()
    agent = record_mode('AGENT_DECISIONS', aq, ar, selected_seed=seed, lost_after_us=600000, trace=controller.trace())
    return backend, agent, q, result


def test_real_q4_kernel_pair_is_same_source_and_backend_uses_zero_model_calls():
    backend, agent, _, _ = pair()
    report = compare_modes(backend, agent, lost_after_us=600000, source_kind='SYNTHETIC')
    assert backend['metrics']['provider_calls'] == 0 and agent['metrics']['provider_calls'] == 2
    assert backend['metrics']['switches'] == agent['metrics']['switches'] == 1
    assert report['accuracy'] is None and report['counts_for_acceptance'] is False


@pytest.mark.parametrize('change', ['seed', 'scope', 'request', 'flags', 'hash'])
def test_comparison_rejects_changed_source_seed_policy_or_bytes(change):
    backend, agent, _, _ = pair()
    if change == 'seed': agent['selected_seed'] = 'other'
    if change == 'scope': agent['response']['resolved_scope']['scene_revision'] = 'other'
    if change == 'request': agent['request']['time']['range_us'][0] = 1
    if change == 'flags': agent['flags'] = []
    if change != 'hash': agent['content_sha256'] = canonical_hash(agent, exclude=('content_sha256',))
    else: agent['content_sha256'] = '0' * 64
    with pytest.raises(EventModeError): compare_modes(backend, agent, lost_after_us=600000, source_kind='SYNTHETIC')


def test_recording_rejects_wrong_kernel_mode_or_changed_journal():
    _, _, q, r = pair()
    with pytest.raises(EventModeError): record_mode('AGENT_DECISIONS', q, r, selected_seed='x', lost_after_us=2)
    object.__setattr__(r, 'links_bytes', b'corrupt')
    with pytest.raises(EventModeError): record_mode('BACKEND_FLAGS', q, r, selected_seed='x', lost_after_us=2)
