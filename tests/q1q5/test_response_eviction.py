"""Bounded response/job/media memory with oldest-first eviction (demo back end must not stop at the cap).

SYNTHETIC inputs only (the existing test_api fixtures): no Ground Truth, renderer trajectory, visibility or depth.
"""
import pytest
from test_api import api_fixture, q1, run_binding
import test_core_search_track_t as core_helpers
from test_core_search_track_t import core_search, core_track, manual_api

from amidst.q1q5.api import QAPI, APIError


def authorize(token, scene, *, audit=False):
    if not str(token).startswith('SYN_') or scene != 'SYNTHETIC_SCENE':
        raise ValueError('denied')


@pytest.fixture(autouse=True)
def _any_synthetic_session(monkeypatch):
    monkeypatch.setattr(core_helpers, 'authorize', authorize)


def tok(i):
    return f'SYN_{i:04d}'


def small_api(limit):
    api, run = api_fixture()
    return QAPI([run], max_responses=limit, max_media_refs=4096), run


def prediction(api, token, ref):
    return api.call('q_candidate_view', {'session_ref': token, 'response_ref': ref, 'as_of_us': 0}, authorize)


def code_of(fn, *args):
    with pytest.raises(APIError) as exc:
        fn(*args)
    return exc.value.status, exc.value.code


def test_600_searches_and_tracks_succeed_with_bounded_memory():
    api, run = manual_api()
    api.max_responses = 128
    refs = []
    for i in range(600):
        out = core_search(api, run, token=tok(i)) if i % 2 == 0 else core_track(api, run, token=tok(i))
        assert out['status'] and out['output_sha256']
        refs.append((tok(i), out['output_sha256']))
        assert len(api.responses) <= 128
    assert len(api.responses) == 128
    assert len(api._expired) >= 600 - 128


def test_evicted_reference_reports_expired_and_unknown_reference_stays_forbidden():
    api, run = manual_api()
    api.max_responses = 4
    first = core_search(api, run, token=tok(0))['output_sha256']
    for i in range(1, 9):
        core_search(api, run, token=tok(i))
    assert (tok(0), first) not in api.responses
    assert code_of(prediction, api, tok(0), first) == (410, 'Q_RESPONSE_EXPIRED')
    assert code_of(prediction, api, tok(0), 'never-issued') == (403, 'FORBIDDEN_DATA_SCOPE')
    # The newest reference is still served (404-style lookups are unchanged for live responses).
    newest = core_search(api, run, token=tok(8))['output_sha256']
    assert (tok(8), newest) in api.responses


def test_eviction_is_oldest_first():
    api, run = manual_api()
    api.max_responses = 3
    seen = [(tok(i), core_search(api, run, token=tok(i))['output_sha256']) for i in range(5)]
    assert list(api.responses) == seen[2:]


def test_eviction_releases_media_refs_and_frame_cache():
    api, run = small_api(3)
    for i in range(8):
        api.call('q1_camera_search', q1(run, tok(i)), authorize)
    live_tokens = {t for t, _ in api.responses}
    assert len(live_tokens) == 3
    assert {t for t, _ in api.media_refs} <= live_tokens
    assert {k[0] for k in api._frame_refs} <= live_tokens
    assert api.media_refs  # live responses keep theirs
    gone = tok(0)
    assert not [k for k in api.media_refs if k[0] == gone]
    assert not [k for k in api._frame_refs if k[0] == gone]
    assert any(k[0] == 'media' and k[1] == gone for k in api._expired)


def test_media_reference_cap_evicts_oldest_instead_of_failing():
    api, run = small_api(128)
    api.max_media_refs = 4
    for i in range(6):
        api.call('q1_camera_search', q1(run, tok(i)), authorize)
        assert len(api.media_refs) <= 4


def test_expired_media_grant_is_explicit():
    api, run = small_api(2)
    api.call('q1_camera_search', q1(run, tok(0)), authorize)
    refs = [ref for t, ref in api.media_refs if t == tok(0)]
    assert refs
    for i in range(1, 5):
        api.call('q1_camera_search', q1(run, tok(i)), authorize)
    assert code_of(api.call, 'q_media_grant', {'session_ref': tok(0), 'media_token': refs[0]}, authorize) == (410, 'Q_RESPONSE_EXPIRED')


def test_running_session_is_never_evicted():
    api, run = manual_api()
    api.max_responses = 2
    first = core_search(api, run, token=tok(0))['output_sha256']
    protected = (tok(0), first)
    api._active[protected] = object()  # a RUNNING session
    for i in range(1, 6):
        core_search(api, run, token=tok(i))
    assert protected in api.responses and len(api.responses) == 2
    api._active.clear()


def test_jobs_are_capped_and_running_job_is_kept():
    api, _ = small_api(3)
    running = ('SYN_RUN', 'job-run')
    api._jobs[running] = {'scene_id': 'SYNTHETIC_SCENE', 'public': {'status': 'RUNNING'}, 'generation': 0}
    api._active[running] = object()
    for i in range(10):
        with api._lock:
            api._evict_jobs()
            api._jobs[(tok(i), f'job-{i}')] = {'scene_id': 'SYNTHETIC_SCENE', 'public': {'status': 'COMPLETE'}, 'generation': 0}
        assert len(api._jobs) <= 3
    assert running in api._jobs
    assert code_of(api.call, 'q2_poll_session', {'session_ref': tok(0), 'response_ref': 'job-0'}, authorize) == (410, 'Q_RESPONSE_EXPIRED')
    api._active.clear()


def test_every_slot_running_still_refuses_explicitly():
    api, run = manual_api()
    api.max_responses = 1
    first = core_search(api, run, token=tok(0))['output_sha256']
    api._active[(tok(0), first)] = object()
    assert code_of(core_search, api, run, tok(1)) == (409, 'Q_RESPONSE_LIMIT')
    api._active.clear()


def test_integrity_check_still_rejects_tampered_bundle():
    api, run = manual_api()
    out = core_search(api, run, token=tok(0))
    bundle = api.responses[(tok(0), out['output_sha256'])]
    bundle['response']['output_sha256'] = 'x' * 64
    with pytest.raises(APIError):
        api._save_response(tok(1), bundle)
