"""#412 adapter regressions: synthetic requests and fake transports only."""
import json
import socket
from copy import deepcopy

import pytest
from test_api import OTHER, TOKEN, api_fixture, authorize, selected
from test_openai_prediction_t import GOOD, Transport, adapter, completion, request

from amidst.q1q5.api import APIError, QAPI
from amidst.q1q5.demo_launcher import RecordedAPI
from amidst.q1q5.openai_prediction import OpenAIPredictionAdapter
from amidst.q1q5.store import canonical_hash


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('NETWORK_BLOCKED_IN_TEST')
    for name in ('connect', 'connect_ex'):
        monkeypatch.setattr(socket.socket, name, refuse)
    for name in ('create_connection', 'getaddrinfo'):
        monkeypatch.setattr(socket, name, refuse)


@pytest.mark.parametrize('next_as_of', [400_000, 700_000])
def test_same_query_changed_request_fails_closed_without_rebinding_cached_answer(next_as_of):
    transport = Transport(completion(GOOD))
    model = adapter(transport)
    first_request = request()
    first = model.predict(session_id='SYNTHETIC', query_id='Q', request=first_request)
    changed = request(as_of=next_as_of)
    changed['candidate_camera_ids'] = ['C']
    refused = model.predict(session_id='SYNTHETIC', query_id='Q', request=changed)
    assert refused['status'] == 'UNAVAILABLE' and refused['reason'] == 'REQUEST_NOT_WHITELISTED'
    assert refused['candidates'] == [] and refused['attempts'] == 0
    assert refused['request_sha256'] == canonical_hash(changed)
    assert first['request_sha256'] == canonical_hash(first_request)
    first['candidates'][0]['camera_id'] = 'MUTATED'
    cached = model.predict(session_id='SYNTHETIC', query_id='Q', request=first_request)
    assert cached['candidates'] == GOOD['candidates'] and len(transport.calls) == 1


@pytest.mark.parametrize('enabled,mode', [(False, 'LIVE'), (True, 'REPLAY')])
def test_disabled_and_replay_never_read_credentials(enabled, mode):
    class UnreadableEnvironment(dict):
        def get(self, key, *default):
            raise AssertionError('CREDENTIAL_READ_FORBIDDEN')
    model = OpenAIPredictionAdapter(enabled=enabled, mode=mode, env=UnreadableEnvironment())
    result = model.predict(session_id='SYNTHETIC', query_id='Q', request=request())
    assert result['reason'] == ('REPLAY_MISS' if enabled else 'DISABLED')


def external(api, response, as_of=500_000, token=TOKEN):
    return api.call('q_external_prediction', {'session_ref': token, 'response_ref': response['session_id'],
                                            'as_of_us': as_of}, authorize)


def test_enabled_fake_live_adapter_is_called_with_only_as_of_evidence():
    transport = Transport(completion(GOOD))
    api, run = api_fixture(openai_prediction_adapter=adapter(transport))
    response = selected(api, run)
    result = external(api, response)
    assert api.bootstrap()['external_prediction'] == {'enabled': True, 'mode': 'LIVE'}
    assert result['status'] == 'AVAILABLE' and result['candidates'] == GOOD['candidates']
    sent = json.loads(json.loads(transport.calls[0]['body'])['messages'][1]['content'])
    assert all(segment['range_us'][1] <= 500_000 for segment in sent['observed'])
    assert result['request_sha256'] == canonical_hash(sent)
    assert external(api, response)['source'] == 'CACHE'
    assert external(api, response, as_of=400_000)['candidates'] == []
    assert len(transport.calls) == 1
    with pytest.raises(APIError) as exc:
        external(api, response, token=OTHER)
    assert exc.value.status == 403
    assert len(transport.calls) == 1


def test_recorded_only_external_replay_is_keyless_and_matches_the_live_request(tmp_path):
    records = []
    live, run = api_fixture(tmp_path, openai_prediction_adapter=adapter(Transport(completion(GOOD)), recorder=records.append))
    response = selected(live, run)
    predicted = external(live, response)
    pin = live.call('q_record_response', {'session_ref': TOKEN, 'response_ref': response['session_id']}, authorize)
    descriptor = {key: pin[key] for key in ('recording_id', 'file', 'file_sha256')}
    camera_map = live.call('q_camera_map', {'session_ref': TOKEN, 'scene_id': run.catalog['scene_id'],
                                          'run_id': run.catalog['run_id']}, authorize)
    def transport_forbidden(**kwargs):
        raise AssertionError('REPLAY_TRANSPORT_FORBIDDEN')
    replay_model = OpenAIPredictionAdapter(enabled=True, mode='REPLAY', env={}, replay=records,
                                          transport=transport_forbidden)
    replay = RecordedAPI(QAPI(max_responses=8, max_media_refs=64, recording_store=live.recording_store,
                              recordings=[descriptor], camera_maps=[camera_map], openai_prediction_adapter=replay_model))
    played = replay.call('q_recorded_response', {'session_ref': OTHER, 'recording_id': pin['recording_id']}, authorize)
    result = external(replay, played, token=OTHER)
    assert replay.bootstrap()['external_prediction'] == {'enabled': True, 'mode': 'REPLAY'}
    assert result['source'] == 'REPLAY' and result['attempts'] == 0
    assert result['request_sha256'] == predicted['request_sha256']
    assert result['candidates'] == predicted['candidates']


def test_recorded_wrapper_disables_live_external_requests():
    transport = Transport()
    api, run = api_fixture(openai_prediction_adapter=adapter(transport))
    response = selected(api, run)
    replay = RecordedAPI(api)
    assert replay.bootstrap()['external_prediction'] == {'enabled': False, 'mode': 'OFF'}
    with pytest.raises(APIError) as exc:
        external(replay, response)
    assert (exc.value.code, exc.value.status) == ('RECORDED_READ_ONLY', 409)
    assert transport.calls == []


@pytest.mark.parametrize('field', ['scene_id', 'run_id', 'detection_index_sha256', 'parameter_set_sha256', 'clock_mapping_sha256'])
def test_core_recording_rejects_rehashed_foreign_scope(field):
    from test_core_search_track_t import core_track, manual_api
    api, run = manual_api()
    response = core_track(api, run)
    original = api.responses[(TOKEN, response.get('session_id') or response['output_sha256'])]
    corrupted = deepcopy(original)
    corrupted['response']['resolved_scope'][field] = 'FOREIGN_SYNTHETIC'
    corrupted['response']['output_sha256'] = canonical_hash(corrupted['response'], exclude=('output_sha256', 'stats'))
    with pytest.raises(APIError) as exc:
        api._verify_bundle(corrupted)
    assert (exc.value.code, exc.value.status) == ('DataIntegrityError', 409)


def test_bootstrap_regions_do_not_mutate_the_parser_catalog():
    api, run = api_fixture()
    before = deepcopy(run.catalog)
    assert api.bootstrap()['runs'][0]['regions']
    assert run.catalog == before and api.runs[(run.catalog['scene_id'], run.catalog['run_id'])].catalog == before
