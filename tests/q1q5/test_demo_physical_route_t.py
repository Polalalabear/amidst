"""DEMO-UI-E-T: server route around the Claude-owned physical prediction (DEMO_UI_SUPPORT_V1 §6.4). Codex wires it."""
import pytest
from demo_ui_support_helpers import require_route
from test_api import OTHER, TOKEN, api_fixture, authorize, selected

from amidst.q1q5.api import APIError
from amidst.q1q5.physical_prediction import build_blind_curve_response

CODE = 'PHYSICAL_ROUTE_IMPLEMENTATION_MISSING'


def call(api, ref, as_of, token=TOKEN, auth=authorize):
    return api.call('q_physical_prediction', {'session_ref': token, 'response_ref': ref, 'as_of_us': as_of}, auth)


def expected(api, run, r, as_of):
    bundle = api.responses[(TOKEN, r['session_id'])]
    segment = [s for s in r['timeline'] if s['kind'] == 'ON_CAMERA' and s['range_us'][0] <= as_of][-1]
    obs = [bundle['observations'][o] for o in segment['observation_ids'] if bundle['observations'][o]['timestamp_us'] <= as_of]
    boxes = [{'camera_id': o['camera_id'], 'source_time_us': o['timestamp_us'], 'bbox_xyxy_px': o['bbox_xyxy_px']} for o in obs]
    # D126: the route returns the blind-interval curve response built over the pure prediction (fe0d333).
    return build_blind_curve_response(as_of_us=as_of, camera_graph=run.bindings.graphs.camera, boxes=boxes,
                                      last_camera_id=segment['camera_id'],
                                      last_observed_us=max(b['source_time_us'] for b in boxes),
                                      display_positions=None, fail_closed=True)


@pytest.mark.parametrize('as_of', [500_000, 1_500_000])
def test_route_reproduces_pure_prediction_from_data_at_or_before_t(as_of):
    require_route('q_physical_prediction', CODE)
    api, run = api_fixture(); r = selected(api, run)
    assert call(api, r['session_id'], as_of) == expected(api, run, r, as_of)


def test_route_is_session_scoped_without_audit_and_validates_time():
    require_route('q_physical_prediction', CODE)
    api, run = api_fixture(); r = selected(api, run); seen = []

    def recording(token, scene, *, audit=False):
        seen.append(audit); authorize(token, scene, audit=audit)
    call(api, r['session_id'], 500_000, auth=recording)
    assert seen and not any(seen)
    with pytest.raises(APIError) as err:
        call(api, r['session_id'], 500_000, token=OTHER)
    assert err.value.status == 403
    for bad in (-1, True, 1.5, '1'):
        with pytest.raises(APIError) as err:
            call(api, r['session_id'], bad)
        assert err.value.status == 422
