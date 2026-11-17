"""Error-only UI capability reporting; SYNTHETIC sessions, no assets or model."""
import io
import json
import threading
from copy import deepcopy
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from test_api import OTHER, TOKEN, api_fixture, authorize, selected

from amidst.q1q5.api import POST_ROUTES, APIError


ACTIONS = ('q_camera_map', 'q_physical_prediction')


def request_fixture(action):
    api, run = api_fixture()
    response = selected(api, run)
    if action == 'q_camera_map':
        payload = {'session_ref': TOKEN, 'scene_id': run.catalog['scene_id'],
                   'run_id': run.catalog['run_id']}
    else:
        payload = {'session_ref': TOKEN, 'response_ref': response['session_id'], 'as_of_us': 500_000}
    return api, payload


def error(api, action, payload, auth=authorize):
    with pytest.raises(APIError) as exc:
        api.call(action, payload, auth)
    return exc.value.status, exc.value.code


@pytest.mark.parametrize('action', ACTIONS)
def test_unavailable_ui_still_requires_fresh_authorization(action):
    api, payload = request_fixture(action)

    def denied(*args, **kwargs):
        raise ValueError('denied')

    assert error(api, action, payload, denied) == (403, 'FORBIDDEN_DATA_SCOPE')
    assert error(api, action, payload | {'session_ref': 'SYNTHETIC_UNKNOWN'}) == (403, 'FORBIDDEN_DATA_SCOPE')


@pytest.mark.parametrize('action', ACTIONS)
@pytest.mark.parametrize('bad', [None, [], 'bad'])
def test_unavailable_ui_rejects_non_object_payload(action, bad):
    api, _ = request_fixture(action)
    assert error(api, action, bad) == (422, 'FORBIDDEN_INFERENCE_INPUT')


@pytest.mark.parametrize('action', ACTIONS)
@pytest.mark.parametrize('key', ['extra', 'ground_truth', 'renderer_trajectory', 'visibility', 'depth'])
def test_unavailable_ui_rejects_extra_and_private_input_keys(action, key):
    api, payload = request_fixture(action)
    result = api.dispatch(environ(action, payload | {key: 'SYNTHETIC_DECOY'}), authorize)
    assert result.status == 422
    assert json.loads(result.body) == {'error_code': 'FORBIDDEN_INFERENCE_INPUT'}


def test_map_preserves_scene_and_run_scope_errors():
    api, payload = request_fixture('q_camera_map')
    assert error(api, 'q_camera_map', payload | {'scene_id': 'FOREIGN'}) == (403, 'FORBIDDEN_DATA_SCOPE')
    assert error(api, 'q_camera_map', payload | {'run_id': 'NO_SUCH_RUN'}) == (503, 'Q_RUN_NOT_CONFIGURED')
    assert error(api, 'q_camera_map', payload | {'run_id': None}) == (422, 'FORBIDDEN_INFERENCE_INPUT')


@pytest.mark.parametrize('bad', [-1, True, 0.5, '1', None])
def test_physical_preserves_source_time_type_validation(bad):
    api, payload = request_fixture('q_physical_prediction')
    assert error(api, 'q_physical_prediction', payload | {'as_of_us': bad}) == (422, 'FORBIDDEN_INFERENCE_INPUT')


def test_physical_does_not_accept_foreign_unknown_or_non_q2_response():
    api, payload = request_fixture('q_physical_prediction')
    for invalid in (payload | {'session_ref': OTHER}, payload | {'response_ref': 'foreign'}):
        assert error(api, 'q_physical_prediction', invalid) == (403, 'FORBIDDEN_DATA_SCOPE')
    bundle = api.responses[(TOKEN, payload['response_ref'])]
    bundle['response']['schema_version'] = 'q-demo.q1-response.v1'
    # The stored response is hash-bound; a mutated response is an integrity error, not a scope error.
    assert error(api, 'q_physical_prediction', payload) == (409, 'DataIntegrityError')


def environ(action, payload):
    raw = json.dumps(payload).encode()
    return {'REQUEST_METHOD': 'POST', 'PATH_INFO': '/api/' + action, 'QUERY_STRING': '',
            'HTTP_HOST': '127.0.0.1:8766', 'CONTENT_TYPE': 'application/json',
            'CONTENT_LENGTH': str(len(raw)), 'wsgi.input': io.BytesIO(raw)}


@pytest.mark.parametrize('change', [
    {'HTTP_ORIGIN': 'http://foreign.invalid'},
    {'REQUEST_METHOD': 'GET'},
    {'PATH_INFO': '/api/q_unknown'},
])
def test_wsgi_unavailable_routes_do_not_bypass_transport_denials(change):
    api, payload = request_fixture('q_camera_map')
    result = api.dispatch(environ('q_camera_map', payload) | change, authorize)
    assert result.status == 403
    assert json.loads(result.body) == {'error_code': 'FORBIDDEN_DATA_SCOPE'}


@pytest.mark.parametrize('action', ACTIONS)
def test_routes_are_implemented_and_no_longer_report_unavailable(action):
    """Both routes were stubbed as 503 Q_RESOURCE_UNAVAILABLE; D126 implemented them (fe0d333)."""
    api, payload = request_fixture(action)
    assert action in POST_ROUTES
    result = api.dispatch(environ(action, payload), authorize)
    assert result.status == 200


@pytest.mark.parametrize('action', ACTIONS)
def test_recorded_wrapper_keeps_inference_disabled(action):
    from amidst.q1q5.demo_launcher import RecordedAPI

    api, _ = request_fixture(action)
    replay = RecordedAPI(api)
    assert error(replay, 'q2_start_session', {}) == (409, 'RECORDED_READ_ONLY')
