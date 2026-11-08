"""Q_CORE_SEARCH_TRACK_V1 acceptance tests (D126, #93). Codex implements; these are the acceptance gate.

Tests that need ``amidst.q1q5.core_query`` or the ``q_core_search``/``q_core_track`` routes skip with an
explicit code until they exist; ``AMIDST_REQUIRE_IMPL=1`` turns every such skip into a failure.
Inputs are the pinned r004 graphs, hand-written SYNTHETIC fixtures and the existing SYNTHETIC API
fixture only: no Ground Truth, renderer trajectory, visibility/depth or script keyframes.
"""
import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from demo_ui_support_helpers import missing, require_module, require_route
from test_api import TOKEN, api_fixture, authorize, q1, run_binding, selected
from test_graphs import fixture as graph_fixture
from test_graphs import seal as seal_graphs

from amidst.q1q5.api import POST_ROUTES, QAPI, APIError
from amidst.q1q5.clock_mapping import ClockMapping
from amidst.q1q5.graphs import load_graphs
from amidst.q1q5.physical_prediction import predict_next_cameras
from amidst.q1q5.store import canonical_hash

REPO = Path(__file__).parents[2]
FIXTURES = Path(__file__).parent / 'fixtures'
MANUAL = 'MANUAL_ON_STATIC_FRAME'
MODULE_CODE = 'CORE_QUERY_MODULE_MISSING'
SEARCH_CODE = 'CORE_SEARCH_ROUTE_MISSING'
TRACK_CODE = 'CORE_TRACK_ROUTE_MISSING'
ATTRS = ('CoreRequestError', 'validate_search_request', 'validate_track_request', 'location_hits',
         'intersect_hits', 'single_view_sequence', 'blind_estimate')
# Exact keys refused by api._safe_request; the graph's own static `visibility_ref` is not one of them.
FORBIDDEN_KEYS = {'gt', 'ground_truth', 'actor', 'actor_id', 'material_id', 'script', 'event_script', 'trajectory',
                  'renderer_trajectory', 'visibility', 'depth', 'mask', 'private_evaluation', 'production_manifest'}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


R004 = {'region': load(REPO / 'configs/q1q5/graphs/r004/region_graph_v3_1.json'),
        'camera': load(REPO / 'configs/q1q5/graphs/r004/camera_graph_v3_1.json')}
SYN = load(FIXTURES / 'core_multi_room.synthetic.json')
SYN_GRAPHS = {'region': SYN['region_graph'], 'camera': SYN['camera_graph']}
VECTORS = load(FIXTURES / 'core_single_view_vectors.synthetic.json')['vectors']
GRAPHS = {'r004': R004, 'synthetic_multi_room': SYN_GRAPHS}
REGION_CASES = [(name, region['region_id']) for name, g in GRAPHS.items() for region in g['region']['regions']]


def core():
    return require_module('AMIDST_CORE_QUERY_MODULE', 'amidst.q1q5.core_query', MODULE_CODE, ATTRS)


def keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from keys(child)


def assert_no_private_keys(doc):
    bad = [k for k in keys(doc) if k.lower() in FORBIDDEN_KEYS or (k.lower().startswith('gt_') and k != 'gt_read')]
    assert not bad, bad


def expected_location(camera_graph, region_ids, run_camera_ids=None):
    """Test oracle for §2.2: manual static-frame coverage only, restricted to the run catalog."""
    hits = {}
    for camera in camera_graph['cameras']:
        if run_camera_ids is not None and camera['camera_id'] not in run_camera_ids:
            continue
        for cover in camera['covered_regions']:
            if cover['region_id'] in region_ids and cover['basis'] == MANUAL:
                hits.setdefault(camera['camera_id'], set()).add(cover['region_id'])
    return hits


# --- Pinned data and fixture consistency (runs now) -------------------------------------------------

@pytest.mark.parametrize('name', sorted(GRAPHS))
def test_graph_references_are_consistent(name):
    graph = GRAPHS[name]
    regions = {r['region_id'] for r in graph['region']['regions']}
    assert len(regions) == len(graph['region']['regions'])
    cameras = [c['camera_id'] for c in graph['camera']['cameras']]
    assert len(set(cameras)) == len(cameras)
    for camera in graph['camera']['cameras']:
        for cover in camera['covered_regions']:
            assert cover['region_id'] in regions, (camera['camera_id'], cover['region_id'])
    assert any(cover['basis'] == MANUAL for c in graph['camera']['cameras'] for cover in c['covered_regions'])


def test_synthetic_fixtures_are_synthetic_and_carry_no_private_inputs():
    for doc in (SYN, load(FIXTURES / 'core_single_view_vectors.synthetic.json')):
        assert doc['data_origin'] == 'SYNTHETIC' and doc['gt_read'] is False
        assert_no_private_keys(doc)
    rooms = [r for r in SYN['region_graph']['regions'] if r['kind'] == 'ROOM']
    assert len(rooms) >= 3  # multi-classroom case, not the two-room r004 shape
    assert any(c['basis'] != MANUAL for cam in SYN['camera_graph']['cameras'] for c in cam['covered_regions'])


def test_single_view_vectors_are_well_formed():
    for vector in VECTORS:
        segments, as_of = vector['single_view'], vector['as_of_us']
        for left, right in zip(segments, segments[1:]):
            assert left['range_us'][1] == right['range_us'][0], vector['id']
        for seg in segments:
            assert seg['range_us'][0] < seg['range_us'][1] <= as_of
            assert (seg['kind'] == 'ON_CAMERA') == (seg['evidence_state'] == 'OBSERVED') == (seg['camera_id'] is not None)
        if segments:
            assert segments[-1]['range_us'][1] == as_of
            assert segments[-1]['kind'] != 'GAP'


def test_expanded_scene_rooms_have_an_indoor_manual_camera():
    """#445 scene expansion uses reviewed r005, without changing legacy r004 coverage."""
    from amidst.q1q5.scene_graphs import load_scene_graphs, room_coverage_pending
    graph = load_scene_graphs('r005')
    assert room_coverage_pending(graph) is None
    assert len([r for r in graph.region['regions'] if r['kind'] == 'ROOM']) == 4
    for camera in graph.camera['cameras']:
        assert all(c['visibility_ref'].startswith('human-review:336bd2f8')
                   for c in camera['covered_regions'] if c['basis'] == MANUAL)


def test_physical_prediction_route_is_unavailable_or_the_existing_shape():
    """§4.2: before wiring, 503 fail-closed; after wiring, the DEMO_UI_SUPPORT_V1 §6.4 document."""
    api, run = api_fixture()
    r = selected(api, run)
    try:
        doc = api.call('q_physical_prediction', {'session_ref': TOKEN, 'response_ref': r['session_id'],
                                                 'as_of_us': 500_000}, authorize)
    except APIError as exc:
        assert 'q_physical_prediction' not in POST_ROUTES
        assert (exc.status, exc.code) == (503, 'Q_RESOURCE_UNAVAILABLE')
        return
    assert doc['schema_version'] == 'q-demo.physical-prediction.v1'
    assert doc['used_for'] == 'DISPLAY_ONLY' and doc['gt_read'] is False
    assert doc['identity_verdict'] == 'UNCONFIRMED' and doc['physical_navigation'] == 'UNKNOWN'


# --- Pure module: location hits, intersection ------------------------------------------------------

@pytest.mark.parametrize('graph_name,region_id', REGION_CASES)
def test_location_hits_follow_manual_coverage_for_every_region(graph_name, region_id):
    m = core()
    camera_graph = GRAPHS[graph_name]['camera']
    result = m.location_hits(deepcopy(camera_graph), [region_id])
    expected = expected_location(camera_graph, {region_id})
    assert set(result['hits']) == set(expected)
    for camera_id, basis in result['hits'].items():
        assert [b['kind'] for b in basis] == ['LOCATION']
        assert basis[0]['region_id'] == region_id and basis[0]['coverage_basis'] == MANUAL
    unsupported = {c['camera_id'] for c in camera_graph['cameras']
                   if any(x['region_id'] == region_id and x['basis'] != MANUAL for x in c['covered_regions'])}
    reported = {row['camera_id'] for row in result['not_evaluated'] if row['reason'] == 'COVERAGE_BASIS_UNSUPPORTED'}
    assert unsupported - set(expected) <= reported


@pytest.mark.parametrize('graph_name', sorted(GRAPHS))
def test_location_hits_for_all_rooms_is_the_union(graph_name):
    m = core()
    graph = GRAPHS[graph_name]
    rooms = [r['region_id'] for r in graph['region']['regions'] if r['kind'] == 'ROOM']
    result = m.location_hits(deepcopy(graph['camera']), rooms)
    assert set(result['hits']) == set(expected_location(graph['camera'], set(rooms)))


def test_location_hits_respect_the_run_camera_catalog():
    m = core()
    camera_graph = SYN_GRAPHS['camera']
    region_ids = [r['region_id'] for r in SYN_GRAPHS['region']['regions']]
    catalog = sorted(c['camera_id'] for c in camera_graph['cameras'])[:2]
    result = m.location_hits(deepcopy(camera_graph), region_ids, run_camera_ids=catalog)
    assert set(result['hits']) == set(expected_location(camera_graph, set(region_ids), catalog))
    outside = set(expected_location(camera_graph, set(region_ids))) - set(catalog)
    assert outside <= {r['camera_id'] for r in result['not_evaluated'] if r['reason'] == 'CAMERA_NOT_IN_RUN'}


def test_intersection_keeps_only_cameras_with_both_bases():
    m = core()
    loc = {'SYN_CAM_HALL': [{'kind': 'LOCATION', 'region_id': 'SYN_HALL', 'coverage_basis': MANUAL, 'visibility_ref': 'synthetic:h'}],
           'SYN_CAM_ROOM_1_IN': [{'kind': 'LOCATION', 'region_id': 'SYN_ROOM_1', 'coverage_basis': MANUAL, 'visibility_ref': 'synthetic:r1'}]}
    obj = {'SYN_CAM_ROOM_1_IN': [{'kind': 'OBJECT', 'class_label': 'chair', 'color_label': None, 'evidence_state': 'OBSERVED',
                                  'observation_ids': ['obs:SYN:1'], 'detection_index_sha256': '0' * 64}],
           'SYN_CAM_ROOM_3_IN': [{'kind': 'OBJECT', 'class_label': 'chair', 'color_label': None, 'evidence_state': 'OBSERVED',
                                  'observation_ids': ['obs:SYN:3'], 'detection_index_sha256': '0' * 64}]}
    result = m.intersect_hits(deepcopy(loc), deepcopy(obj))
    assert set(result) == {'SYN_CAM_ROOM_1_IN'}
    assert [b['kind'] for b in result['SYN_CAM_ROOM_1_IN']] == ['LOCATION', 'OBJECT']
    assert m.intersect_hits(deepcopy(loc), {}) == {}


# --- Pure module: request validation ----------------------------------------------------------------

def syn_clock():
    d = {'schema_version': 'q-demo.clock-mapping.v1', 'run_id': 'SYNTHETIC_RUN', 'clock_id': 'SYNTHETIC_CLOCK',
         'timezone': 'Asia/Taipei', 'wall_origin': '2026-11-01T13:00:00+08:00', 'mapping_kind': 'DECLARED_DEMO_CLOCK',
         't0_us': 0, 'rate': 1, 'source_duration_us': 1_800_000_000, 'mapping_version': 'SYNTHETIC',
         'declaration_source': 'SYNTHETIC', 'declared_by': 'SYNTHETIC', 'declared_at': '2026-10-21T00:00:00+08:00'}
    d['content_sha256'] = canonical_hash(d)
    return ClockMapping(d)


def catalog():
    return dict(region_ids=[r['region_id'] for r in SYN['region_graph']['regions']],
                class_labels=list(SYN['class_labels']), class_aliases={'人': 'person', '椅子': 'chair'},
                color_labels=list(SYN['color_labels']), clock_mapping=syn_clock())


WALL = {'kind': 'WALL', 'timezone': 'Asia/Taipei',
        'wall_range': ['2026-11-01T13:00:00+08:00', '2026-11-01T13:30:00+08:00']}


def search_request(**change):
    q = {'schema_version': 'q-core.search-request.v1', 'session_ref': 'SYNTHETIC_SESSION_A',
         'scene_id': 'SYNTHETIC_MULTI_ROOM', 'run_id': 'SYNTHETIC_RUN', 'time': deepcopy(WALL),
         'region_ids': ['SYN_ROOM_1'], 'feature': {'class_label': 'person', 'color_label': None}}
    q.update(change)
    return q


def track_request(**change):
    q = {'schema_version': 'q-core.track-request.v1', 'session_ref': 'SYNTHETIC_SESSION_A',
         'scene_id': 'SYNTHETIC_MULTI_ROOM', 'run_id': 'SYNTHETIC_RUN',
         'feature': {'class_label': 'person', 'color_label': 'red'}, 'region_ids': [], 'time': None,
         'playback_now_us': 42_000_000}
    q.update(change)
    return q


def without(q, key):
    q = deepcopy(q)
    del q[key]
    return q


def code_of(fn, request):
    m = core()
    with pytest.raises(m.CoreRequestError) as exc:
        fn(request, **catalog())
    return exc.value.code


@pytest.mark.parametrize('request_,code', [
    (without(search_request(), 'time'), 'TIME_REQUIRED'),
    (search_request(time=None), 'TIME_REQUIRED'),
    (search_request(time=WALL | {'wall_range': ['2026-11-01T13:30:00+08:00', '2026-11-01T13:00:00+08:00']}), 'TIME_ORDER'),
    (search_request(time=WALL | {'wall_range': ['2026-11-01T13:00:00+08:00', '2026-11-01T13:00:00+08:00']}), 'TIME_ORDER'),
    (search_request(time=WALL | {'wall_range': ['2026-11-01T13:00:00', '2026-11-01T13:30:00']}), 'TIME_INVALID'),
    (search_request(time=WALL | {'wall_range': ['13:00', '13:30']}), 'TIME_INVALID'),
    (search_request(time=WALL | {'kind': 'SOURCE'}), 'TIME_INVALID'),
    (search_request(time=WALL | {'wall_range': ['2026-11-01T23:30:00+08:00', '2026-11-02T00:30:00+08:00']}), 'TIME_CROSSES_MIDNIGHT'),
    (search_request(time=WALL | {'timezone': 'UTC'}), 'TIME_ZONE_MISMATCH'),
    (search_request(time=WALL | {'wall_range': ['2026-11-01T13:00:00+09:00', '2026-11-01T13:30:00+09:00']}), 'TIME_ZONE_MISMATCH'),
    (search_request(region_ids=[], feature=None), 'LOCATION_OR_FEATURE_REQUIRED'),
    (search_request(region_ids=['NOT_A_REGION']), 'REGION_UNKNOWN'),
    (search_request(region_ids=['SYN_ROOM_1', 'SYN_ROOM_1']), 'FORBIDDEN_INFERENCE_INPUT'),
    (search_request(feature={'class_label': 'unicorn', 'color_label': None}), 'UNSUPPORTED_CLASS'),
    (search_request(feature={'class_label': 'person', 'color_label': 'purple'}), 'COLOR_UNKNOWN'),
    (search_request(feature={'class_label': 'chair', 'color_label': 'red'}), 'UNSUPPORTED_CONDITION'),
    (search_request(query_min_score=0.1), 'FORBIDDEN_INFERENCE_INPUT'),
    (search_request(camera_ids=['SYN_CAM_HALL']), 'FORBIDDEN_INFERENCE_INPUT'),
    (search_request(ground_truth={'x': 1}), 'FORBIDDEN_INFERENCE_INPUT'),
])
def test_search_validation_errors_are_explicit(request_, code):
    assert code_of(core().validate_search_request, request_) == code


@pytest.mark.parametrize('change', [
    {'feature': None},                                                           # location only
    {'region_ids': []},                                                          # feature only
    {},                                                                          # both
    {'region_ids': [], 'feature': {'class_label': 'chair', 'color_label': None}},  # COCO object
])
def test_search_accepts_location_or_feature_or_both(change):
    m = core()
    normalized = m.validate_search_request(search_request(**change), **catalog())
    assert normalized['region_ids'] == search_request(**change)['region_ids']


def test_search_class_alias_is_normalized():
    m = core()
    normalized = m.validate_search_request(search_request(feature={'class_label': '人', 'color_label': 'red'}), **catalog())
    assert normalized['feature'] == {'class_label': 'person', 'color_label': 'red'}


@pytest.mark.parametrize('request_,code', [
    (without(track_request(), 'feature'), 'FEATURE_REQUIRED'),
    (track_request(feature=None), 'FEATURE_REQUIRED'),
    (without(track_request(), 'playback_now_us'), 'NOW_REQUIRED'),
    (track_request(playback_now_us=-1), 'NOW_REQUIRED'),
    (track_request(playback_now_us=True), 'NOW_REQUIRED'),
    (track_request(playback_now_us=1.5), 'NOW_REQUIRED'),
    (track_request(region_ids=['NOT_A_REGION']), 'REGION_UNKNOWN'),
    (track_request(feature={'class_label': 'unicorn', 'color_label': None}), 'UNSUPPORTED_CLASS'),
    (track_request(time=WALL | {'timezone': 'UTC'}), 'TIME_ZONE_MISMATCH'),
    (track_request(gt_track=[1]), 'FORBIDDEN_INFERENCE_INPUT'),
])
def test_track_validation_errors_are_explicit(request_, code):
    assert code_of(core().validate_track_request, request_) == code


@pytest.mark.parametrize('change', [{}, {'region_ids': ['SYN_ROOM_2']}, {'time': deepcopy(WALL)},
                                    {'feature': {'class_label': 'chair', 'color_label': None}}])
def test_track_accepts_feature_with_optional_location_and_time(change):
    """Non-person classes validate; the route answers UNSUPPORTED (§3.2), not a 422."""
    core().validate_track_request(track_request(**change), **catalog())


# --- Pure module: single view and blind estimate ----------------------------------------------------

@pytest.mark.parametrize('vector', VECTORS, ids=[v['id'] for v in VECTORS])
def test_single_view_sequence_matches_shared_vectors(vector):
    m = core()
    assert m.single_view_sequence(deepcopy(vector['sightings']), as_of_us=vector['as_of_us']) == vector['single_view']


def prediction_doc(last_camera='A', moving=True):
    _, c = graph_fixture()
    boxes = [{'camera_id': 'A', 'source_time_us': t, 'bbox_xyxy_px': [10 + (k * 20 if moving else 0), 10, 30 + (k * 20 if moving else 0), 50]}
             for k, t in enumerate([0, 200_000, 400_000, 600_000])]
    return predict_next_cameras(last_camera_id=last_camera, last_observed_us=600_000, as_of_us=800_000,
                                boxes=boxes, camera_graph=c)


@pytest.mark.parametrize('kwargs', [{}, {'moving': False}, {'last_camera': 'NOT_IN_GRAPH'}])
def test_blind_estimate_is_inferred_low_confidence_display_only(kwargs):
    m = core()
    doc = prediction_doc(**kwargs)
    est = m.blind_estimate(deepcopy(doc))
    assert est['schema_version'] == 'q-core.blind-estimate.v1'
    assert est['evidence_state'] == 'INFERRED' and est['used_for'] == 'DISPLAY_ONLY'
    assert est['confidence'] in {'LOW', 'UNKNOWN'}
    assert est['identity_verdict'] == 'UNCONFIRMED' and est['physical_navigation'] == 'UNKNOWN' and est['gt_read'] is False
    assert est['prediction_ref'] == {'schema_version': doc['schema_version'], 'content_sha256': doc['content_sha256']}
    assert est['content_sha256'] == canonical_hash(est, exclude=('content_sha256',))
    assert [(c['camera_id'], c['rank']) for c in est['candidates']] == [(c['camera_id'], c['rank']) for c in doc['candidates']]
    for mine, theirs in zip(est['candidates'], doc['candidates']):
        assert mine['confidence'] in {'LOW', 'UNKNOWN'} and mine['model_confidence'] == theirs['confidence']
    if doc['status'] != 'PREDICTED':
        assert est['candidates'] == [] and est['confidence'] == 'UNKNOWN'
    assert est['curve']['basis'] in {'DISPLAY_POSITIONS_STRAIGHT_LINE', 'NODE_GRAPH_ONLY'}
    if est['curve']['basis'] == 'NODE_GRAPH_ONLY':
        assert est['curve']['points'] == []
    assert_no_private_keys(est)


# --- Routes (SYNTHETIC API fixture with manual coverage) -------------------------------------------

def manual_api():
    """Existing SYNTHETIC API run, with camera coverage re-declared as manual static-frame coverage."""
    run = run_binding()
    b = run.bindings
    r, c = deepcopy(b.graphs.region), deepcopy(b.graphs.camera)
    for camera in c['cameras']:
        for cover in camera['covered_regions']:
            cover['basis'] = MANUAL
    seal_graphs(r, c)
    graphs = load_graphs(r, c, region_sha256=r['content_sha256'], camera_sha256=c['content_sha256'])
    b = replace(b, graphs=graphs, region_graph_sha256=r['content_sha256'], camera_graph_sha256=c['content_sha256'])
    run = replace(run, bindings=b)
    return QAPI([run], max_responses=128, max_media_refs=4096), run


def full_wall(run):
    d = run.bindings.clock.document
    end = datetime.fromisoformat(d['wall_origin']) + timedelta(microseconds=d['source_duration_us'] - d['t0_us'])
    return {'kind': 'WALL', 'timezone': d['timezone'], 'wall_range': [d['wall_origin'], end.isoformat()]}


def core_search(api, run, token=TOKEN, **change):
    q = {'schema_version': 'q-core.search-request.v1', 'session_ref': token, 'scene_id': run.catalog['scene_id'],
         'run_id': run.catalog['run_id'], 'time': full_wall(run), 'region_ids': [],
         'feature': {'class_label': 'person', 'color_label': None}}
    q.update(change)
    return api.call('q_core_search', q, authorize)


def core_track(api, run, token=TOKEN, **change):
    q = {'schema_version': 'q-core.track-request.v1', 'session_ref': token, 'scene_id': run.catalog['scene_id'],
         'run_id': run.catalog['run_id'], 'feature': {'class_label': 'person', 'color_label': None},
         'region_ids': [], 'time': None, 'playback_now_us': run.bindings.clock.document['source_duration_us']}
    q.update(change)
    return api.call('q_core_track', q, authorize)


def api_error(fn, *args, **kwargs):
    with pytest.raises(APIError) as exc:
        fn(*args, **kwargs)
    return exc.value.status, exc.value.code


def q1_cameras(api, run):
    """Object hits must equal Q1 at the server-chosen score (§2.1): query_min_score, else the index floor."""
    params = {p['name']: p['value'] for p in run.bindings.parameter_set['parameters']}
    score = params.get('query_min_score', run.bindings.index.manifest['detector']['index_score_floor'])
    q = q1(run)
    q['time'] = {'kind': 'WALL', 'wall_range': full_wall(run)['wall_range']}
    q['condition'] = {'class_label': 'person', 'min_count_per_frame': 1, 'color': None, 'query_min_score': score}
    q['page_size'] = 1000
    response = api.call('q1_camera_search', q, authorize)
    return {r['camera_id']: r for r in response['results']}


def run_regions(run):
    return [r['region_id'] for r in run.bindings.graphs.region['regions']]


def check_search_envelope(response):
    assert response['schema_version'] == 'q-core.search-response.v1'
    assert response['status'] in {'READY', 'NO_MATCH', 'PARTIAL', 'OUT_OF_RANGE', 'UNKNOWN'}
    assert response['identity_verdict'] == 'UNCONFIRMED' and response['provenance']['gt_read'] is False
    assert response['output_sha256'] == canonical_hash(response, exclude=('output_sha256', 'stats'))
    assert [h['rank'] for h in response['hits']] == list(range(1, len(response['hits']) + 1))
    assert_no_private_keys(response)


def test_search_route_location_only_is_data_driven_over_every_region():
    require_route('q_core_search', SEARCH_CODE)
    api, run = manual_api()
    camera_graph = run.bindings.graphs.camera
    for region_id in run_regions(run):
        response = core_search(api, run, region_ids=[region_id], feature=None)
        check_search_envelope(response)
        expected = expected_location(camera_graph, {region_id}, run.catalog['camera_ids'])
        assert {h['camera_id'] for h in response['hits']} == set(expected), region_id
        for hit in response['hits']:
            assert hit['target_observed'] is False
            assert [b['kind'] for b in hit['basis']] == ['LOCATION']
            assert hit['basis'][0]['region_id'] == region_id and hit['basis'][0]['coverage_basis'] == MANUAL
            assert hit['wall_range'][0].endswith('+08:00')


def test_search_route_feature_only_matches_existing_q1_index():
    require_route('q_core_search', SEARCH_CODE)
    api, run = manual_api()
    response = core_search(api, run, region_ids=[])
    check_search_envelope(response)
    expected = q1_cameras(api, run)
    assert expected, 'SYNTHETIC fixture must contain person detections'
    assert {h['camera_id'] for h in response['hits']} == set(expected)
    for hit in response['hits']:
        obj = [b for b in hit['basis'] if b['kind'] == 'OBJECT']
        assert hit['target_observed'] is True and len(obj) == 1
        assert obj[0]['evidence_state'] == 'OBSERVED' and obj[0]['observation_ids']
        assert [s['range_us'] for s in hit['segments']] == [s['range_us'] for s in expected[hit['camera_id']]['matched_segments']]


def test_search_route_both_filled_is_the_intersection():
    require_route('q_core_search', SEARCH_CODE)
    api, run = manual_api()
    objects = set(q1_cameras(api, run))
    for region_id in run_regions(run):
        location = set(expected_location(run.bindings.graphs.camera, {region_id}, run.catalog['camera_ids']))
        response = core_search(api, run, region_ids=[region_id])
        check_search_envelope(response)
        assert {h['camera_id'] for h in response['hits']} == location & objects, region_id
        for hit in response['hits']:
            assert [b['kind'] for b in hit['basis']] == ['LOCATION', 'OBJECT']


@pytest.mark.parametrize('change,code', [
    ({'region_ids': [], 'feature': None}, 'LOCATION_OR_FEATURE_REQUIRED'),
    ({'time': None}, 'TIME_REQUIRED'),
    ({'region_ids': ['NOT_A_REGION']}, 'REGION_UNKNOWN'),
    ({'feature': {'class_label': 'unicorn', 'color_label': None}}, 'UNSUPPORTED_CLASS'),
    ({'feature': {'class_label': 'car', 'color_label': 'red'}}, 'UNSUPPORTED_CONDITION'),
    ({'trajectory': []}, 'FORBIDDEN_INFERENCE_INPUT'),
])
def test_search_route_validation_is_422(change, code):
    require_route('q_core_search', SEARCH_CODE)
    api, run = manual_api()
    assert api_error(core_search, api, run, **change) == (422, code)


def test_search_route_is_session_scoped():
    require_route('q_core_search', SEARCH_CODE)
    api, run = manual_api()
    assert api_error(core_search, api, run, token='NOT_A_SESSION')[0] == 403


def test_track_route_non_person_is_unsupported_not_pretended():
    require_route('q_core_track', TRACK_CODE)
    api, run = manual_api()
    response = core_track(api, run, feature={'class_label': 'car', 'color_label': None})
    assert response['schema_version'] == 'q-core.track-response.v1'
    assert response['status'] == 'UNSUPPORTED' and 'CLASS_NOT_SUPPORTED_BY_LINKER' in response['reasons']
    assert response['sightings'] == [] and response['multi_view'] == [] and response['single_view'] == []
    assert response['blind'] is None
    assert_no_private_keys(response)


@pytest.mark.parametrize('change,code', [
    ({'feature': None}, 'FEATURE_REQUIRED'),
    ({'playback_now_us': -5}, 'NOW_REQUIRED'),
    ({'region_ids': ['NOT_A_REGION']}, 'REGION_UNKNOWN'),
    ({'depth': 1}, 'FORBIDDEN_INFERENCE_INPUT'),
])
def test_track_route_validation_is_422(change, code):
    require_route('q_core_track', TRACK_CODE)
    api, run = manual_api()
    assert api_error(core_track, api, run, **change) == (422, code)


def check_track(response, as_of):
    m = core()
    assert response['schema_version'] == 'q-core.track-response.v1'
    assert response['status'] in {'TRACKING', 'LOST', 'NO_SIGHTING', 'PARTIAL', 'UNKNOWN'}
    assert response['as_of_us'] == as_of
    assert response['identity_verdict'] == 'UNCONFIRMED' and response['physical_navigation'] == 'UNKNOWN'
    assert response['provenance']['gt_read'] is False
    assert response['output_sha256'] == canonical_hash(response, exclude=('output_sha256', 'stats'))
    assert_no_private_keys(response)
    for s in response['sightings']:
        assert s['evidence_state'] == 'OBSERVED' and s['observation_ids']
        assert s['range_us'][0] < s['range_us'][1] <= as_of  # never uses evidence after "now"
    assert response['single_view'] == m.single_view_sequence(deepcopy(response['sightings']), as_of_us=as_of)
    assert {v['camera_id'] for v in response['multi_view']} == {s['camera_id'] for s in response['sightings']}
    last = response['single_view'][-1]['kind'] if response['single_view'] else None
    if last in {'GAP', 'LOST'}:
        blind = response['blind']
        assert blind is not None
        if 'q_physical_prediction' not in POST_ROUTES:
            assert blind == {'status': 'UNAVAILABLE', 'reason': 'PREDICTION_UNAVAILABLE', 'estimate': None}
        elif blind['status'] == 'ESTIMATED':
            assert blind['estimate']['evidence_state'] == 'INFERRED'
            assert blind['estimate']['confidence'] in {'LOW', 'UNKNOWN'}
    else:
        assert response['blind'] is None
    if response['status'] == 'LOST':
        assert last == 'LOST'
    if response['status'] == 'TRACKING':
        assert response['single_view'][-1]['kind'] == 'ON_CAMERA'
        assert response['single_view'][-1]['range_us'][1] == as_of


def test_track_route_now_uses_playback_clock_and_only_past_evidence():
    require_route('q_core_track', TRACK_CODE)
    api, run = manual_api()
    duration = run.bindings.clock.document['source_duration_us']
    full = core_track(api, run)
    check_track(full, duration)
    assert full['resolved_time']['kind'] == 'PLAYBACK_NOW'
    assert full['sightings'], 'SYNTHETIC fixture must contain person detections'
    early = duration // 4
    partial = core_track(api, run, playback_now_us=early)
    check_track(partial, early)


def test_track_route_explicit_time_window():
    require_route('q_core_track', TRACK_CODE)
    api, run = manual_api()
    wall = full_wall(run)
    response = core_track(api, run, time=wall)
    check_track(response, run.bindings.clock.document['source_duration_us'])


def test_track_route_is_session_scoped():
    require_route('q_core_track', TRACK_CODE)
    api, run = manual_api()
    assert api_error(core_track, api, run, token='NOT_A_SESSION')[0] == 403
