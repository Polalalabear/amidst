"""Bounded SYNTHETIC regressions for core evidence and local association."""
from copy import deepcopy
from dataclasses import replace

import pytest

from amidst.q1q5.core_query import (
    CoreRequestError,
    execute_core_search,
    execute_core_track,
    single_view_sequence,
)
from amidst.q1q5.store import DetectionSnapshot
from test_api import TOKEN, run_binding
from test_core_search_track_t import full_wall
from test_q5_controller import fixture, repin, seal_parameters


def bound_run(pattern=None, frames=4):
    b = fixture(pattern=pattern or {'A': {i: 'STRONG' for i in range(frames)}},
                cameras=('A',), frames=frames)
    run = run_binding(b)
    return replace(run, catalog={**run.catalog, 'camera_ids': ['A']})


def track_request(run, **change):
    return {
        'schema_version': 'q-core.track-request.v1', 'session_ref': TOKEN,
        'scene_id': run.catalog['scene_id'], 'run_id': run.catalog['run_id'],
        'feature': {'class_label': 'person', 'color_label': None},
        'region_ids': [], 'time': None,
        'playback_now_us': run.bindings.clock.duration_us, **change,
    }


def search_request(run, **change):
    return {
        'schema_version': 'q-core.search-request.v1', 'session_ref': TOKEN,
        'scene_id': run.catalog['scene_id'], 'run_id': run.catalog['run_id'],
        'feature': {'class_label': 'person', 'color_label': None},
        'region_ids': [], 'time': full_wall(run), **change,
    }


def changed_records(run, change):
    records = deepcopy(list(run.bindings.index.records))
    change(records)
    index = repin(DetectionSnapshot(deepcopy(run.bindings.index.manifest), tuple(records)))
    return replace(run, bindings=replace(run.bindings, index=index,
                                        index_sha256=index.manifest['content_sha256']))


def test_low_score_boxes_do_not_become_tracks():
    run = bound_run()
    run = changed_records(run, lambda rows: [det.update(score=.01)
                          for row in rows for det in row['detections'] or []])
    result = execute_core_track(track_request(run), run)
    assert result['sightings'] == []
    assert result['provenance']['linker'] is None


def test_zero_iou_replacement_starts_an_independent_local_hypothesis():
    run = bound_run(frames=2)
    run = changed_records(run, lambda rows: rows[1]['detections'][0].update(
        bbox_xyxy_px=[1000, 1000, 1010, 1010]))
    result = execute_core_track(track_request(run), run)
    sightings = result['sightings']
    assert len(sightings) == 2 and len({s['track_ref'] for s in sightings}) == 2
    assert all(len(s['observation_ids']) == 1 for s in sightings)
    assert result['provenance']['linker'] == 'q2-iou-linker'
    assert all(s['link_provenance']['parameter_set_sha256'] == run.bindings.parameter_sha256
               for s in sightings)


def test_ambiguous_frame_does_not_attach_both_people_to_the_predecessor():
    run = bound_run(frames=2)
    run = changed_records(run, lambda rows: rows[1]['detections'].append(
        deepcopy(rows[1]['detections'][0])))
    result = execute_core_track(track_request(run), run)
    assert result['status'] == 'PARTIAL' and 'AMBIGUOUS_LINK' in result['reasons']
    assert len(result['sightings']) == 3
    assert len({s['track_ref'] for s in result['sightings']}) == 3
    assert all(len(s['observation_ids']) == 1 for s in result['sightings'])


def test_missing_frame_stays_out_of_observed_sighting_ranges():
    run = bound_run({'A': {0: 'STRONG', 1: 'MISSING', 2: 'STRONG'}}, frames=3)
    result = execute_core_track(track_request(run), run)
    assert result['status'] == 'PARTIAL' and 'INCOMPLETE_EVIDENCE' in result['reasons']
    assert [s['range_us'] for s in result['sightings']] == [[0, 200_000], [400_000, 600_000]]
    assert {s['track_ref'] for s in result['sightings']} == {result['sightings'][0]['track_ref']}
    assert result['single_view'][1]['kind'] == 'GAP'


def test_unapproved_link_parameter_fails_closed_before_tracking():
    run = bound_run()
    p = deepcopy(run.bindings.parameter_set)
    next(item for item in p['parameters'] if item['name'] == 'link_min_score')['status'] = 'PROPOSED'
    seal_parameters(p)
    run = replace(run, bindings=replace(run.bindings, parameter_set=p,
                                       parameter_sha256=p['content_sha256']))
    result = execute_core_track(track_request(run), run)
    assert result['status'] == 'UNKNOWN' and 'PARAMETERS_NOT_APPROVED' in result['reasons']
    assert result['sightings'] == [] and result['provenance']['linker'] is None


def test_source_clock_mismatch_is_refused_instead_of_rebound():
    run = bound_run()
    run = changed_records(run, lambda rows: rows[0].update(clock_id='SYNTHETIC_OTHER_CLOCK'))
    with pytest.raises(CoreRequestError, match='DataIntegrityError'):
        execute_core_track(track_request(run), run)


@pytest.mark.parametrize('has_hit', [False, True])
def test_q1_partial_evidence_and_camera_coverage_survive_core_wrapper(has_hit):
    pattern = {'A': {0: 'MISSING', 1: 'STRONG' if has_hit else None}}
    run = bound_run(pattern, frames=2)
    result = execute_core_search(search_request(run), run,
                                 media_token_for_frame=lambda _: 'SYNTHETIC_MEDIA')
    assert result['status'] == 'PARTIAL' and 'INCOMPLETE_EVIDENCE' in result['reasons']
    assert bool(result['hits']) == has_hit
    if not has_hit:
        assert result['not_evaluated_cameras'] == [
            {'camera_id': 'A', 'reason': 'INCOMPLETE_COVERAGE'}]


def test_missing_clock_or_index_is_unknown_instead_of_negative():
    run = bound_run()
    request = search_request(run)
    for changes, reason in [({'clock': None}, 'CLOCK_MAPPING_MISSING'),
                            ({'index': None}, 'INDEX_NOT_AVAILABLE')]:
        missing = replace(run, bindings=replace(run.bindings, **changes))
        result = execute_core_search(request, missing)
        assert result['status'] == 'UNKNOWN' and reason in result['reasons']
        assert result['hits'] == []


def test_zero_playback_time_uses_no_future_detection():
    run = bound_run()
    result = execute_core_track(track_request(run, playback_now_us=0), run)
    assert result['sightings'] == [] and result['single_view'] == []
    assert result['as_of_us'] == 0 and result['resolved_time']['source_range_us'] == [0, 0]


def test_same_camera_overlap_keeps_current_camera_until_it_is_no_longer_seen():
    sightings = [{'camera_id': 'A', 'range_us': [0, 5]},
                 {'camera_id': 'A', 'range_us': [4, 10]},
                 {'camera_id': 'B', 'range_us': [3, 20]}]
    result = single_view_sequence(sightings, as_of_us=20)
    assert [(s['camera_id'], s['range_us']) for s in result] == [('A', [0, 10]), ('B', [10, 20])]


def test_search_reference_is_repeatable_session_independent_and_source_bound():
    run = bound_run()
    request = search_request(run)
    media = lambda _: 'SYNTHETIC_MEDIA'
    first = execute_core_search(request, run, media_token_for_frame=media)
    repeat = execute_core_search(deepcopy(request), run, media_token_for_frame=media)
    assert repeat == first
    other_session = execute_core_search({**request, 'session_ref': 'SYNTHETIC_OTHER_SESSION'},
                                        run, media_token_for_frame=media)
    assert other_session['query_id'] == first['query_id']
    changed = changed_records(run, lambda rows: rows[0]['detections'][0].update(score=.91))
    assert changed.bindings.index_sha256 != run.bindings.index_sha256
    different_source = execute_core_search(request, changed, media_token_for_frame=media)
    assert different_source['query_id'] != first['query_id']
    for changes in ({'clock': None}, {'index': None}):
        unavailable = replace(run, bindings=replace(run.bindings, **changes))
        a = execute_core_search(request, unavailable, media_token_for_frame=media)
        b = execute_core_search(deepcopy(request), unavailable, media_token_for_frame=media)
        assert a['status'] == 'UNKNOWN' and a == b


# --- #445 integration: blind-interval curve is wired into the track response -------------------------

def test_track_blind_uses_blind_curve_response_when_prediction_is_available():
    run = bound_run(pattern={'A': {0: 'STRONG', 1: 'STRONG'}}, frames=5)
    result = execute_core_track(track_request(run), run, physical_prediction_available=True)
    assert result['single_view'][-1]['kind'] in {'GAP', 'LOST'}
    blind = result['blind']
    assert blind['schema_version'] == 'q-demo.physical-prediction.v1' and blind['status'] == 'ESTIMATED'
    assert blind['evidence_state'] == 'INFERRED' and blind['confidence'] in {'LOW', 'UNKNOWN'}
    assert blind['estimate']['evidence_state'] == 'INFERRED' and blind['used_for'] == 'DISPLAY_ONLY'
    assert blind['identity_verdict'] == 'UNCONFIRMED' and blind['physical_navigation'] == 'UNKNOWN'
    assert blind['as_of_us'] == result['as_of_us'] and blind['last_camera_id'] == 'A'
    # Only observations at or before the last observed frame feed the curve.
    assert blind['last_observed_us'] <= result['single_view'][0]['range_us'][1]


def test_track_blind_stays_unavailable_without_the_prediction_route():
    run = bound_run(pattern={'A': {0: 'STRONG', 1: 'STRONG'}}, frames=5)
    result = execute_core_track(track_request(run), run)
    assert result['blind'] == {'status': 'UNAVAILABLE', 'reason': 'PREDICTION_UNAVAILABLE', 'estimate': None}


def test_track_blind_is_absent_while_the_target_is_on_camera():
    run = bound_run()
    result = execute_core_track(track_request(run), run, physical_prediction_available=True)
    assert result['single_view'][-1]['kind'] == 'ON_CAMERA' and result['blind'] is None
