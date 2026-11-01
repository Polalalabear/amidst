"""DEMO-UI-B-T: human-readable recording titles in bootstrap (DEMO_UI_SUPPORT_V1 §3). Test-first; Codex implements."""
import pytest
from demo_ui_support_helpers import require_api_attr
from test_api import OTHER, TOKEN, api_fixture, authorize, selected

from amidst.q1q5.api import QAPI, APIError

CODE = 'RECORDING_TITLE_IMPLEMENTATION_MISSING'


def recorded(tmp_path):
    require_api_attr('RECORDING_TITLE_MAX_CHARS', CODE)
    api, run = api_fixture(tmp_path); r = selected(api, run)
    pin = api.call('q_record_response', {'session_ref': TOKEN, 'response_ref': r['session_id']}, authorize)
    return api, r, {k: pin[k] for k in ['recording_id', 'file', 'file_sha256']}


def replay(api, *pins):
    return QAPI(max_responses=8, max_media_refs=64, recording_store=api.recording_store, recordings=list(pins))


def test_title_comes_from_server_pin_and_is_listed_in_bootstrap(tmp_path):
    api, r, pin = recorded(tmp_path)
    from amidst.q1q5.api import RECORDING_TITLE_MAX_CHARS
    assert RECORDING_TITLE_MAX_CHARS == 80
    rows = replay(api, dict(pin, title='P1 工程場景・追蹤 A→B（SYNTHETIC）')).bootstrap()['recordings']
    assert rows[0]['title'] == 'P1 工程場景・追蹤 A→B（SYNTHETIC）' and rows[0]['title_source'] == 'RECORDING_INDEX'
    untitled = replay(api, pin).bootstrap()['recordings'][0]
    assert untitled['title'] is None and untitled['title_source'] == 'UNTITLED'
    for key in ('recording_id', 'recorded_at', 'source_kind', 'scene_id', 'run_id', 'response_kind', 'output_sha256'):
        assert rows[0][key] == untitled[key]


def test_title_does_not_change_recorded_bytes_or_replayed_response(tmp_path):
    api, r, pin = recorded(tmp_path)
    path = tmp_path / pin['file']; before = path.read_bytes()
    titled = replay(api, dict(pin, title='A4-1 追蹤'))
    played = titled.call('q_recorded_response', {'session_ref': OTHER, 'recording_id': pin['recording_id']}, authorize)
    assert played == r and path.read_bytes() == before and 'A4-1' not in before.decode()
    assert 'title' not in played


@pytest.mark.parametrize('title', ['', ' ', 'x' * 81, 7, None, 'line\nbreak', 'tab\there', '\x00'])
def test_invalid_titles_fail_closed(tmp_path, title):
    api, _, pin = recorded(tmp_path)
    with pytest.raises(APIError) as err:
        replay(api, dict(pin, title=title))
    assert err.value.status == 409


def test_other_pin_keys_are_still_refused(tmp_path):
    api, _, pin = recorded(tmp_path)
    with pytest.raises(APIError):
        replay(api, dict(pin, title='ok', label='extra'))
    with pytest.raises(APIError):
        replay(api, dict(pin, file_sha256='0' * 64, title='ok'))


def test_record_receipt_payload_cannot_set_titles(tmp_path):
    api, r, _ = recorded(tmp_path)
    with pytest.raises(APIError):
        api.call('q_record_response', {'session_ref': TOKEN, 'response_ref': r['session_id'], 'title': 'client title'}, authorize)


# --- run titles (UI-B #378 reads bootstrap runs[].title) ---

def titled_run(title):
    from dataclasses import fields, replace
    from test_api import run_binding

    from amidst.q1q5.api import QRun
    require_api_attr('RECORDING_TITLE_MAX_CHARS', CODE)
    if 'title' not in {f.name for f in fields(QRun)}:
        from demo_ui_support_helpers import missing
        missing(CODE)
    return replace(run_binding(), title=title)


def test_run_title_is_listed_in_bootstrap_and_optional():
    row = QAPI([titled_run('P1 工程場景（ENGINEERING）')], max_responses=8, max_media_refs=64).bootstrap()['runs'][0]
    assert row['title'] == 'P1 工程場景（ENGINEERING）' and row['title_source'] == 'RUN_REGISTRY'
    plain = QAPI([titled_run(None)], max_responses=8, max_media_refs=64).bootstrap()['runs'][0]
    assert plain['title'] is None and plain['title_source'] == 'UNTITLED'
    assert {k: v for k, v in row.items() if k not in {'title', 'title_source'}} == \
        {k: v for k, v in plain.items() if k not in {'title', 'title_source'}}


@pytest.mark.parametrize('title', ['', ' ', 'x' * 81, 7, 'line\nbreak'])
def test_invalid_run_titles_fail_closed(title):
    run = titled_run(title)
    with pytest.raises(APIError) as err:
        QAPI([run], max_responses=8, max_media_refs=64)
    assert err.value.status == 409
