"""CQ-41 replay boundaries; model/network calls are forbidden in these tests."""
import errno
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest
from test_api import TOKEN, api_fixture, authorize, q2
from test_q5_controller import seed_id

from amidst.q1q5.api import APIError, raw_json
from amidst.q1q5.demo_launcher import LauncherError, bind_demo, prepare_demo


def factory(tmp_path):
    api, run = api_fixture(tmp_path)
    request = q2(run)
    request['seed'] = {'kind': 'OBSERVATION', 'observation_id': seed_id(run.bindings)}
    response = api.call('q2_session', request, authorize)
    pin = api.call('q_record_response', {'session_ref': TOKEN, 'response_ref': response['session_id']}, authorize)
    app = SimpleNamespace(api=api, spec={'default_recording_id': pin['recording_id']},
                          manifest={'source_commit': 'a' * 40})
    return app, response


@pytest.mark.parametrize('live', [False, True])
def test_no_model_or_outbound_network_still_replays_exact_response_bytes(tmp_path, monkeypatch, live):
    app, original = factory(tmp_path)
    def no_network(*args, **kwargs):
        pytest.fail('outbound connection attempted')
    monkeypatch.setattr(socket, 'create_connection', no_network)
    app, report = prepare_demo(tmp_path, 'a' * 64, tmp_path.parent / (tmp_path.name + '-state'),
                               live=live, app_factory=lambda *args, **kwargs: app)
    assert app.api.bootstrap()['data_origin'] == 'RECORDED'
    assert app.api.runs  # RGB playback retains exact pinned run metadata
    replay = app.api.call('q_recorded_response', {'session_ref': TOKEN, 'recording_id': report['recording_id']}, authorize)
    assert raw_json(replay) == raw_json(original)
    assert report['model_calls'] == 0 and report['mode'] == 'RECORDED'
    assert bool(report['fallback_reason']) is live
    with pytest.raises(APIError, match='RECORDED_READ_ONLY'):
        app.api.call('q2_start_session', {'request': q2(next(iter(app.api.runs.values()))),
                                        'selected_observation_id': None}, authorize)


def test_wrong_manifest_pin_is_rejected_before_starting_server(tmp_path):
    (tmp_path / 'MANIFEST.json').write_text('{}')
    with pytest.raises(ValueError):
        prepare_demo(tmp_path, '0' * 64, tmp_path.parent / (tmp_path.name + '-state'))


def test_existing_or_in_bundle_state_is_rejected(tmp_path):
    with pytest.raises(LauncherError, match='NEW_CANONICAL_STATE'):
        prepare_demo(tmp_path, 'a' * 64, tmp_path / 'state')


def test_occupied_port_has_an_explicit_error(monkeypatch):
    def occupied(*args):
        raise OSError(errno.EADDRINUSE, 'occupied')
    monkeypatch.setattr('amidst.q1q5.demo_launcher.server', occupied)
    with pytest.raises(LauncherError, match='PORT_IN_USE'):
        bind_demo(None, 12345)


def test_replay_without_a_pinned_default_recording_fails_closed(tmp_path):
    app = SimpleNamespace(spec={'default_recording_id': 'unknown'}, api=SimpleNamespace(recordings={}))
    with pytest.raises(LauncherError, match='PINNED_DEFAULT_RECORDING_REQUIRED'):
        prepare_demo(tmp_path, 'a' * 64, tmp_path.parent / (tmp_path.name + '-state'),
                     app_factory=lambda *args, **kwargs: app)
