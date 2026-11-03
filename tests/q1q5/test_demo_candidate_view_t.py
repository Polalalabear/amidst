"""DEMO-UI-C-T: read-only candidate view outside review mode (DEMO_UI_SUPPORT_V1 §4). Test-first; Codex implements."""
import json

import pytest
from demo_ui_support_helpers import require_module, require_route, walk_keys
from test_api import OTHER, TOKEN, api_fixture, authorize, q1, selected

from amidst.q1q5.api import QAPI, APIError

CODE = 'CANDIDATE_VIEW_IMPLEMENTATION_MISSING'
TOP_KEYS = {'schema_version', 'response_ref', 'as_of_us', 'snapshots', 'display_role',
            'identity_verdict', 'physical_navigation', 'gt_read'}
SNAPSHOT_KEYS = {'candidate_snapshot_sha256', 'first_decision_source_time_us', 'exit_resolution',
                 'candidate_set_complete', 'truncated', 'truncated_count', 'candidates'}
CANDIDATE_KEYS = {'camera_id', 'rank', 'relation', 'transition_id', 'region_path', 'window_us',
                  'path_traversability', 'path_has_unknown_state'}
FIRST_DECISION_US = 800_000  # SYNTHETIC fixture: first decision row that references the snapshot


def ready():
    require_module('AMIDST_CANDIDATE_VIEW_MODULE', 'amidst.q1q5.candidate_view', CODE, ('candidate_view',))
    require_route('q_candidate_view', CODE)


def view(api, ref, as_of, token=TOKEN, auth=authorize):
    return api.call('q_candidate_view', {'session_ref': token, 'response_ref': ref, 'as_of_us': as_of}, auth)


def test_snapshots_appear_only_after_their_first_decision_time():
    ready(); api, run = api_fixture(); r = selected(api, run)
    before = view(api, r['session_id'], FIRST_DECISION_US - 1)
    assert set(before) == TOP_KEYS and before['snapshots'] == []
    at = view(api, r['session_id'], FIRST_DECISION_US)
    assert at['schema_version'] == 'q-demo.candidate-view.v1' and len(at['snapshots']) == 1
    snap = at['snapshots'][0]
    assert set(snap) == SNAPSHOT_KEYS and snap['first_decision_source_time_us'] == FIRST_DECISION_US
    assert all(set(c) == CANDIDATE_KEYS for c in snap['candidates'])
    assert snap['candidates'][0]['camera_id'] == 'B'
    later = view(api, r['session_id'], 10_000_000)
    assert later['snapshots'][:1] == at['snapshots']
    assert at['display_role'] == 'SYSTEM_CANDIDATES_READ_ONLY'
    assert at['identity_verdict'] == 'UNCONFIRMED' and at['physical_navigation'] == 'UNKNOWN' and at['gt_read'] is False


def test_internal_and_review_fields_are_not_exposed():
    ready(); api, run = api_fixture(); r = selected(api, run)
    keys = set(walk_keys(view(api, r['session_id'], 10_000_000)))
    for hidden in ('ranking_basis', 'candidate_ref', 'alternative_transition_ids', 'window_truncated_us',
                   'excluded_transitions', 'decision_id', 'tool_calls', 'llm_calls', 'agent_trace', 'evidence'):
        assert hidden not in keys


def test_non_review_read_does_not_request_audit_role_but_keeps_session_scope():
    ready(); api, run = api_fixture(); r = selected(api, run); seen = []

    def recording_authorize(token, scene, *, audit=False):
        seen.append(audit); authorize(token, scene, audit=audit)
    view(api, r['session_id'], FIRST_DECISION_US, auth=recording_authorize)
    assert seen and not any(seen)
    with pytest.raises(APIError) as err:
        view(api, r['session_id'], FIRST_DECISION_US, token=OTHER)
    assert err.value.status == 403


@pytest.mark.parametrize('as_of', [-1, True, 1.5, '800000', None])
def test_invalid_time_is_refused(as_of):
    ready(); api, run = api_fixture(); r = selected(api, run)
    with pytest.raises(APIError) as err:
        view(api, r['session_id'], as_of)
    assert err.value.status == 422


def test_extra_payload_fields_are_refused():
    ready(); api, run = api_fixture(); r = selected(api, run)
    with pytest.raises(APIError):
        api.call('q_candidate_view', {'session_ref': TOKEN, 'response_ref': r['session_id'], 'as_of_us': 0, 'mode': 'review'}, authorize)


def test_q1_response_has_no_snapshots():
    ready(); api, run = api_fixture()
    response = api.call('q1_camera_search', q1(run), authorize)
    assert view(api, response['output_sha256'], 10_000_000)['snapshots'] == []


def test_recorded_replay_gives_the_same_view(tmp_path):
    ready(); api, run = api_fixture(tmp_path); r = selected(api, run)
    pin = api.call('q_record_response', {'session_ref': TOKEN, 'response_ref': r['session_id']}, authorize)
    replay = QAPI(max_responses=8, max_media_refs=64, recording_store=api.recording_store,
                  recordings=[{k: pin[k] for k in ['recording_id', 'file', 'file_sha256']}])
    replay.call('q_recorded_response', {'session_ref': OTHER, 'recording_id': pin['recording_id']}, authorize)
    assert view(replay, r['session_id'], FIRST_DECISION_US, token=OTHER) == view(api, r['session_id'], FIRST_DECISION_US)


def test_pure_function_ignores_snapshots_without_a_decision_at_or_before_t():
    from importlib import import_module
    ready(); module = import_module('amidst.q1q5.candidate_view')
    api, run = api_fixture(); r = selected(api, run)
    bundle = api.responses[(TOKEN, r['session_id'])]
    orphan = dict(bundle['snapshots'][0], candidate_snapshot_sha256='f' * 64)
    doc = module.candidate_view(snapshots=bundle['snapshots'] + [orphan], decisions_jsonl=bundle['decisions'],
                                as_of_us=10_000_000, response_ref=r['session_id'])
    assert [s['candidate_snapshot_sha256'] for s in doc['snapshots']] == [bundle['snapshots'][0]['candidate_snapshot_sha256']]
    rows = [json.loads(line) for line in bundle['decisions'].splitlines()]
    assert min(x['source_time_us'] for x in rows if x['candidate_snapshot_sha256']) == FIRST_DECISION_US
