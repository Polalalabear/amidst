"""Physical prediction (DEMO_UI_SUPPORT_V1 §6): SYNTHETIC graph plus the pinned r004 v3 shape."""
import builtins
import json
import random
from copy import deepcopy
from pathlib import Path

import pytest

from amidst.q1q5 import physical_prediction as pp
from amidst.q1q5.physical_prediction import (
    PredictionInputError,
    PredictionParams,
    blind_prediction_for_track,
    build_blind_curve_response,
    evaluate_physical_prediction_route,
    predict_blind_trajectory,
    predict_next_cameras,
)

ROOT = Path(__file__).resolve().parents[2]
R004_V3 = ROOT / 'configs/q1q5/graphs/r004/camera_graph_v3.json'


def zone(zone_id, polygon, edges):
    return {'exit_zone_id': zone_id, 'roi_polygon_px': polygon, 'leads_to_edge_ids': edges}


def transition(tid, to, via, relation='UNKNOWN', walk='TOPOLOGICAL_ONLY', unknown=True, hops=1, length=None):
    return {'transition_id': tid, 'from_camera_id': 'A', 'to_camera_id': to, 'via_exit_zone_ids': via,
            'relation': relation, 'path_traversability': walk, 'path_has_unknown_state': unknown,
            'region_hops': hops, 'region_path': ['R1', 'R2'], 'nominal_path_length_m': length}


def graph(approval='APPROVED'):
    return {'schema_version': 'q-demo.camera-transition-graph.v1', 'approval_status': approval,
            'cameras': [
                {'camera_id': 'A', 'exit_zones': [
                    zone('A:east', [[860, 200], [960, 200], [960, 540], [860, 540]], ['E_AB']),
                    zone('A:north', [[300, 0], [660, 0], [660, 80], [300, 80]], ['E_AC'])]},
                {'camera_id': 'B', 'exit_zones': []}, {'camera_id': 'C', 'exit_zones': []},
                {'camera_id': 'D', 'exit_zones': []}],
            'transitions': [
                transition('T_A_B', 'B', ['A:east'], 'BLIND_GAP', 'APPROVED_WALKABLE', False, hops=2),
                transition('T_A_C', 'C', ['A:north']),
                transition('T_A_D', 'D', [], 'OVERLAP', length=3.0)]}


def boxes_right(camera='A', start=0, step=200_000, n=4):
    # foot point moves +x at 500 px/s
    return [{'camera_id': camera, 'source_time_us': start + i * step,
             'bbox_xyxy_px': [480 + 100 * i, 300, 520 + 100 * i, 400]} for i in range(n)]


def run(boxes=None, **kwargs):
    args = {'last_camera_id': 'A', 'last_observed_us': 600_000, 'as_of_us': 600_000,
            'boxes': boxes_right() if boxes is None else boxes, 'camera_graph': graph()}
    args.update(kwargs)
    return predict_next_cameras(**args)


def stable(doc):
    return {k: v for k, v in doc.items() if k not in {'content_sha256', 'inputs_after_as_of_dropped', 'as_of_us'}}


def test_direction_from_boxes_ranks_aligned_exit_first_and_labels_display_only():
    doc = run()
    assert doc['schema_version'] == 'q-demo.physical-prediction.v1' and doc['status'] == 'PREDICTED'
    assert doc['direction']['status'] == 'KNOWN' and doc['direction']['image_velocity_px_s'] == [500.0, 0.0]
    assert [e['exit_zone_id'] for e in doc['exits']] == ['A:east', 'A:north']
    first, *rest = doc['candidates']
    assert first['camera_id'] == 'B' and first['confidence'] == 'HIGH' and first['confidence_label_zh'] == '較高'
    assert {c['camera_id']: c['confidence'] for c in rest} == {'C': 'LOW', 'D': 'LOW'}
    assert doc['identity_verdict'] == 'UNCONFIRMED' and doc['physical_navigation'] == 'UNKNOWN'
    assert doc['gt_read'] is False and doc['used_for'] == 'DISPLAY_ONLY'
    assert doc['display_label'] == '物理預測（示意，非實際路徑）'


def test_only_data_at_or_before_as_of_is_used():
    base = run()
    future = boxes_right() + [{'camera_id': 'A', 'source_time_us': 700_000 + i * 100_000,
                               'bbox_xyxy_px': [400 - 200 * i, 0, 440 - 200 * i, 40]} for i in range(3)]
    leaked = run(boxes=future)
    assert stable(leaked) == stable(base) and leaked['inputs_after_as_of_dropped'] == 3
    later = run(boxes=future, as_of_us=2_000_000)
    assert later['inputs_after_as_of_dropped'] == 0
    assert later['direction'] == base['direction']  # samples after last_observed_us are ignored too
    with pytest.raises(PredictionInputError) as err:
        run(last_observed_us=700_000, as_of_us=600_000)
    assert err.value.code == 'FUTURE_INPUT'


@pytest.mark.parametrize('where,key', [
    ('box', 'ground_truth'), ('box', 'renderer_trajectory'), ('box', 'gt_position'), ('box', 'actor_id'),
    ('box', 'depth'), ('box', 'visibility'), ('graph', 'event_script'), ('graph', 'trajectory'),
])
def test_forbidden_inference_inputs_are_refused(where, key):
    boxes = boxes_right(); g = graph()
    if where == 'box':
        boxes[0][key] = 'SYNTHETIC'
    else:
        g['cameras'][0][key] = 'SYNTHETIC'
    with pytest.raises(PredictionInputError) as err:
        run(boxes=boxes, camera_graph=g)
    assert err.value.code == 'FORBIDDEN_INFERENCE_INPUT'


def test_unknown_direction_degrades_confidence_instead_of_guessing():
    doc = run(boxes=boxes_right(n=2))
    assert doc['direction']['status'] == 'UNKNOWN' and doc['direction']['image_velocity_px_s'] is None
    assert {c['confidence'] for c in doc['candidates']} == {'UNKNOWN'}
    still = [dict(b, bbox_xyxy_px=[480, 300, 520, 400]) for b in boxes_right()]
    assert {c['confidence'] for c in run(boxes=still)['candidates']} == {'UNKNOWN'}


def test_last_position_inside_exit_without_direction_is_medium_not_high():
    inside = [{'camera_id': 'A', 'source_time_us': 600_000, 'bbox_xyxy_px': [880, 300, 920, 400]}]
    doc = run(boxes=inside)
    assert doc['exits'][0]['match'] == 'LAST_POSITION_INSIDE'
    assert doc['candidates'][0]['camera_id'] == 'B' and doc['candidates'][0]['confidence'] == 'MEDIUM'


def test_draft_graph_never_reports_high():
    doc = run(camera_graph=graph('DRAFT'))
    assert doc['candidates'][0]['confidence'] == 'MEDIUM'
    assert doc['graph_approval_status'] == 'DRAFT'


def test_reproducible_and_order_independent():
    boxes = boxes_right(n=6)
    shuffled = deepcopy(boxes); random.Random(7).shuffle(shuffled)
    g = graph(); g2 = deepcopy(g); g2['transitions'].reverse()
    a, b = run(boxes=boxes, last_observed_us=1_000_000, as_of_us=1_000_000), \
        run(boxes=shuffled, camera_graph=g2, last_observed_us=1_000_000, as_of_us=1_000_000)
    assert a == b and a['content_sha256'] == b['content_sha256']
    json.dumps(a, allow_nan=False)


def test_camera_not_in_graph_reports_status_without_candidates():
    doc = run(last_camera_id='CAM_ENTRY', boxes=boxes_right(camera='CAM_ENTRY'))
    assert doc['status'] == 'CAMERA_NOT_IN_GRAPH' and doc['candidates'] == [] and doc['exits'] == []


def test_windows_follow_declared_basis():
    by = {c['camera_id']: c for c in run()['candidates']}
    assert by['B']['window_us'] == [600_000 + 2_000_000, 600_000 + 16_000_000]
    assert by['B']['window_basis'] == 'PARAMETER_PER_HOP'
    assert by['D']['window_us'] == [600_000, 600_000 + 6_000_000]
    assert by['D']['window_basis'] == 'NOMINAL_LENGTH_AND_SPEED_RANGE'


def test_sketch_points_only_from_supplied_display_positions():
    plain = run()
    assert all(c['sketch_points'] is None and c['sketch_basis'] == 'NODE_GRAPH_ONLY' for c in plain['candidates'])
    doc = run(display_positions={'A': [2.0, -5.5], 'B': [16.0, -5.5]})
    by = {c['camera_id']: c for c in doc['candidates']}
    assert by['B']['sketch_points'] == [[2.0, -5.5], [16.0, -5.5]]
    assert by['B']['sketch_basis'] == 'DISPLAY_POSITIONS_STRAIGHT_LINE' and by['C']['sketch_points'] is None


def test_truncation_is_reported():
    doc = run(params=PredictionParams(max_candidates=1))
    assert len(doc['candidates']) == 1 and doc['truncated_count'] == 2


def test_pure_function_reads_no_files(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError('physical prediction must not open files')
    monkeypatch.setattr(builtins, 'open', refuse)
    run()
    source = Path(pp.__file__).read_text(encoding='utf-8')
    for banned in ('import os', 'pathlib', 'amidst.evaluation', 'open(', 'urllib', 'socket'):
        assert banned not in source


def test_pinned_r004_v3_graph_shape_stays_medium_or_lower():
    g = json.loads(R004_V3.read_bytes())
    assert g['approval_status'] == 'DRAFT'
    w1 = next(c for c in g['cameras'] if c['camera_id'] == 'CAM_W1')
    polygon = w1['exit_zones'][0]['roi_polygon_px']
    cx = sum(p[0] for p in polygon) / len(polygon); cy = sum(p[1] for p in polygon) / len(polygon)
    boxes = [{'camera_id': 'CAM_W1', 'source_time_us': i * 200_000,
              'bbox_xyxy_px': [cx - 300 + 100 * i - 20, cy - 80, cx - 300 + 100 * i + 20, cy]} for i in range(4)]
    doc = predict_next_cameras(last_camera_id='CAM_W1', last_observed_us=600_000, as_of_us=600_000,
                               boxes=boxes, camera_graph=g)
    assert doc['status'] == 'PREDICTED' and doc['candidates']
    assert {c['confidence'] for c in doc['candidates']} <= {'MEDIUM', 'LOW', 'UNKNOWN'}
    assert all(c['sketch_points'] is None for c in doc['candidates'])


def test_blind_curve_clamps_high_and_medium_confidence_to_low_and_marks_inferred():
    static_pos = {'A': [2.0, -5.5], 'B': [16.0, -5.5], 'C': [2.0, 4.0]}
    blind = predict_blind_trajectory(
        as_of_us=600_000,
        last_camera_id='A',
        last_observed_us=600_000,
        boxes=boxes_right(),
        camera_graph=graph('APPROVED'),
        display_positions=static_pos,
        region_id='R1',
    )
    assert blind['status'] == 'ESTIMATED' and blind['reason'] is None
    assert blind['evidence_state'] == 'INFERRED'
    assert blind['confidence'] == 'LOW' and blind['confidence_label_zh'] == '低'
    assert blind['display_label'] == '物理預測（示意，非實際路徑）'
    assert blind['used_for'] == 'DISPLAY_ONLY'
    assert blind['identity_verdict'] == 'UNCONFIRMED'
    assert blind['physical_navigation'] == 'UNKNOWN'
    assert blind['gt_read'] is False
    assert blind['coordinate_frame'] == 'STATIC_PLAN_DISPLAY'
    assert blind['overhead'] == {
        'frame': 'STATIC_PLAN_DISPLAY',
        'last_position': [2.0, -5.5],
        'region_id': 'R1',
    }
    assert blind['curve'] == {
        'basis': 'DISPLAY_POSITIONS_STRAIGHT_LINE',
        'points': [[2.0, -5.5], [16.0, -5.5]],
    }
    assert blind['curve_points'] == [[2.0, -5.5], [16.0, -5.5]]
    assert blind['curve_basis'] == 'DISPLAY_POSITIONS_STRAIGHT_LINE'
    top = blind['candidates'][0]
    assert top['camera_id'] == 'B' and top['rank'] == 1
    assert top['model_confidence'] == 'HIGH'
    assert top['confidence'] == 'LOW' and top['confidence_label_zh'] == '低'
    assert all(c['confidence'] in {'LOW', 'UNKNOWN'} for c in blind['candidates'])
    assert blind['estimate'] is not None
    assert blind['estimate']['evidence_state'] == 'INFERRED'
    assert blind['estimate']['confidence'] == 'LOW'
    assert blind['estimate']['curve'] == blind['curve']

    # Wrapping an existing predict_next_cameras doc via build_blind_curve_response produces the same shape
    base_doc = run(display_positions=static_pos)
    wrapped = build_blind_curve_response(base_doc, camera_graph=graph('APPROVED'), display_positions=static_pos, region_id='R1')
    assert wrapped['status'] == 'ESTIMATED'
    assert wrapped['as_of_us'] == base_doc['as_of_us'] == 600_000
    assert wrapped['estimate']['as_of_us'] == base_doc['as_of_us'] == 600_000
    assert wrapped['curve_points'] == [[2.0, -5.5], [16.0, -5.5]]
    assert wrapped['candidates'][0]['confidence'] == 'LOW'
    assert wrapped['candidates'][0]['model_confidence'] == 'HIGH'
    assert blind_prediction_for_track is build_blind_curve_response
    assert evaluate_physical_prediction_route is build_blind_curve_response


def test_blind_curve_insufficient_samples_downgrades_to_unknown_confidence():
    blind = predict_blind_trajectory(
        as_of_us=600_000,
        boxes=boxes_right(n=2),
        camera_graph=graph('APPROVED'),
        display_positions={'A': [2.0, -5.5], 'B': [16.0, -5.5]},
    )
    assert blind['status'] == 'ESTIMATED'
    assert blind['evidence_state'] == 'INFERRED'
    assert blind['confidence'] == 'UNKNOWN' and blind['confidence_label_zh'] == '未知'
    assert all(c['confidence'] == 'UNKNOWN' for c in blind['candidates'])


def test_blind_curve_static_display_coordinate_mapping_and_node_graph_fallback():
    no_pos = build_blind_curve_response(
        as_of_us=600_000,
        boxes=boxes_right(),
        camera_graph=graph(),
    )
    assert no_pos['status'] == 'ESTIMATED'
    assert no_pos['coordinate_frame'] == 'NODE_GRAPH_ONLY'
    assert no_pos['overhead']['frame'] == 'NODE_GRAPH_ONLY'
    assert no_pos['overhead']['last_position'] is None
    assert no_pos['curve'] == {'basis': 'NODE_GRAPH_ONLY', 'points': []}
    assert no_pos['curve_points'] == []

    # Calibrated static map objects with xy_m are supported; UNKNOWN status falls back cleanly
    calibrated = {
        'A': {'status': 'CALIBRATED_STATIC', 'xy_m': [2.0, -5.5], 'basis_ref': 'static/calibration_v1.json'},
        'B': {'status': 'CALIBRATED_STATIC', 'xy_m': [16.0, -5.5], 'basis_ref': 'static/calibration_v1.json'},
        'C': {'status': 'UNKNOWN', 'xy_m': None, 'basis_ref': None},
    }
    mapped = build_blind_curve_response(
        as_of_us=600_000,
        boxes=boxes_right(),
        camera_graph=graph(),
        display_positions=calibrated,
    )
    assert mapped['coordinate_frame'] == 'STATIC_PLAN_DISPLAY'
    assert mapped['overhead']['frame'] == 'STATIC_PLAN_DISPLAY'
    assert mapped['overhead']['last_position'] == [2.0, -5.5]
    assert mapped['curve_points'] == [[2.0, -5.5], [16.0, -5.5]]
    assert mapped['curve_basis'] == 'DISPLAY_POSITIONS_STRAIGHT_LINE'


def test_blind_curve_strips_future_observations_and_fails_closed_when_only_future_exists():
    timeline = [
        {'kind': 'ON_CAMERA', 'camera_id': 'A', 'range_us': [0, 600_000], 'observation_ids': ['o1', 'o2', 'o3', 'o4', 'o_future']},
        {'kind': 'ON_CAMERA', 'camera_id': 'B', 'range_us': [900_000, 1_400_000], 'observation_ids': ['o_b1']},
    ]
    base_boxes = boxes_right()
    observations = {
        f'o{i + 1}': {'camera_id': 'A', 'timestamp_us': b['source_time_us'], 'bbox_xyxy_px': b['bbox_xyxy_px']}
        for i, b in enumerate(base_boxes)
    }
    observations['o_future'] = {'camera_id': 'A', 'timestamp_us': 750_000, 'bbox_xyxy_px': [10, 10, 50, 50]}
    observations['o_b1'] = {'camera_id': 'B', 'timestamp_us': 950_000, 'bbox_xyxy_px': [100, 100, 140, 200]}

    clipped = build_blind_curve_response(
        as_of_us=600_000,
        timeline=timeline,
        observations=observations,
        camera_graph=graph(),
        display_positions={'A': [2.0, -5.5], 'B': [16.0, -5.5]},
    )
    direct = build_blind_curve_response(
        as_of_us=600_000,
        boxes=base_boxes,
        camera_graph=graph(),
        display_positions={'A': [2.0, -5.5], 'B': [16.0, -5.5]},
    )
    assert clipped['status'] == 'ESTIMATED'
    assert clipped['inputs_after_as_of_dropped'] == 2
    assert clipped['last_camera_id'] == 'A' and clipped['last_observed_us'] == 600_000
    assert clipped['curve_points'] == direct['curve_points']
    assert clipped['direction'] == direct['direction']

    # When all observations are after as_of_us, stripping them leaves 0 valid observations -> fail closed
    only_future = [{'camera_id': 'A', 'source_time_us': 800_000 + i * 100_000,
                    'bbox_xyxy_px': [480 + 100 * i, 300, 520 + 100 * i, 400]} for i in range(4)]
    failed = build_blind_curve_response(
        as_of_us=600_000,
        boxes=only_future,
        camera_graph=graph(),
        display_positions={'A': [2.0, -5.5], 'B': [16.0, -5.5]},
    )
    assert failed['status'] == 'UNAVAILABLE'
    assert failed['confidence'] == 'UNKNOWN'
    assert failed['evidence_state'] == 'INFERRED'
    assert failed['curve_points'] == [] and failed['curve'] == {'basis': 'NODE_GRAPH_ONLY', 'points': []}
    assert failed['candidates'] == [] and failed['estimate'] is None
    assert failed['inputs_after_as_of_dropped'] == 4


def test_blind_curve_fails_closed_on_empty_or_missing_observations_and_unmapped_camera():
    empty_boxes = build_blind_curve_response(
        as_of_us=600_000,
        boxes=[],
        camera_graph=graph(),
        display_positions={'A': [2.0, -5.5], 'B': [16.0, -5.5]},
    )
    assert empty_boxes['status'] == 'UNAVAILABLE'
    assert empty_boxes['confidence'] == 'UNKNOWN'
    assert empty_boxes['curve_points'] == []
    assert empty_boxes['candidates'] == [] and empty_boxes['estimate'] is None

    empty_timeline = build_blind_curve_response(
        as_of_us=600_000,
        timeline=[{'kind': 'GAP', 'camera_id': None, 'range_us': [0, 600_000]}],
        observations={},
        camera_graph=graph(),
    )
    assert empty_timeline['status'] == 'UNAVAILABLE'
    assert empty_timeline['confidence'] == 'UNKNOWN'
    assert empty_timeline['curve_points'] == []

    unmapped = build_blind_curve_response(
        as_of_us=600_000,
        boxes=boxes_right(camera='CAM_ENTRY'),
        camera_graph=graph(),
    )
    assert unmapped['status'] == 'UNAVAILABLE'
    assert unmapped['confidence'] == 'UNKNOWN'
    assert unmapped['curve_points'] == []


@pytest.mark.parametrize('where,key', [
    ('box', 'ground_truth'), ('box', 'renderer_trajectory'), ('box', 'gt_position'), ('box', 'actor_id'),
    ('box', 'depth'), ('box', 'visibility'), ('box', 'script'), ('graph', 'event_script'),
    ('graph', 'trajectory'), ('pos', 'gt_xy'),
])
def test_blind_curve_rejects_and_fails_closed_on_forbidden_fields(where, key):
    boxes = boxes_right()
    g = graph()
    pos = {'A': [2.0, -5.5], 'B': [16.0, -5.5]}
    if where == 'box':
        boxes[0][key] = 'SYNTHETIC'
    elif where == 'graph':
        g['cameras'][0][key] = 'SYNTHETIC'
    else:
        pos['A'] = {'xy_m': [2.0, -5.5], key: 'SYNTHETIC'}

    with pytest.raises(PredictionInputError) as err:
        build_blind_curve_response(as_of_us=600_000, boxes=boxes, camera_graph=g, display_positions=pos)
    assert err.value.code == 'FORBIDDEN_INFERENCE_INPUT'

    closed = build_blind_curve_response(
        as_of_us=600_000,
        boxes=boxes,
        camera_graph=g,
        display_positions=pos,
        fail_closed=True,
    )
    assert closed['status'] == 'UNAVAILABLE'
    assert closed['reason'] == 'FORBIDDEN_INFERENCE_INPUT'
    assert closed['confidence'] == 'UNKNOWN'
    assert closed['curve_points'] == []
    assert closed['candidates'] == []


def test_doc_backward_scrub_and_mismatched_as_of_rejected_or_recomputed():
    pos = {'A': [2.0, -5.5], 'B': [16.0, -5.5]}
    doc = run(display_positions=pos, as_of_us=600_000, last_observed_us=600_000)
    assert doc['status'] == 'PREDICTED' and doc['as_of_us'] == 600_000

    # Backward scrub: passing an earlier as_of_us than doc.as_of_us or last_observed_us
    with pytest.raises(PredictionInputError) as err:
        build_blind_curve_response(doc, as_of_us=100_000, display_positions=pos)
    assert err.value.code == 'FUTURE_INPUT'

    closed_early = build_blind_curve_response(doc, as_of_us=100_000, display_positions=pos, fail_closed=True)
    assert closed_early['status'] == 'UNAVAILABLE'
    assert closed_early['reason'] == 'FUTURE_INPUT'
    assert closed_early['as_of_us'] == 100_000
    assert closed_early['confidence'] == 'UNKNOWN'
    assert closed_early['evidence_state'] == 'INFERRED'
    assert closed_early['curve_points'] == []

    # Mismatched later as_of_us without raw observation context
    with pytest.raises(PredictionInputError) as err:
        build_blind_curve_response(doc, as_of_us=800_000, display_positions=pos)
    assert err.value.code == 'DOC_AS_OF_MISMATCH'

    closed_late = build_blind_curve_response(doc, as_of_us=800_000, display_positions=pos, fail_closed=True)
    assert closed_late['status'] == 'UNAVAILABLE'
    assert closed_late['reason'] == 'DOC_AS_OF_MISMATCH'
    assert closed_late['as_of_us'] == 800_000

    # Matching as_of_us succeeds
    matched = build_blind_curve_response(doc, as_of_us=600_000, display_positions=pos)
    assert matched['status'] == 'ESTIMATED'
    assert matched['as_of_us'] == 600_000
    assert matched['curve_points'] == [[2.0, -5.5], [16.0, -5.5]]


def test_tampered_doc_hash_rejected_and_missing_display_positions_falls_back_to_node_graph():
    from amidst.q1q5.physical_prediction import _canonical_hash

    pos = {'A': [2.0, -5.5], 'B': [16.0, -5.5]}
    doc = run(display_positions=pos, as_of_us=600_000, last_observed_us=600_000)

    # 1. Modifying candidates while retaining old content_sha256 fails hash verification
    tampered = deepcopy(doc)
    tampered['candidates'][0]['sketch_points'] = [[777.0, 888.0], [999.0, 111.0]]
    with pytest.raises(PredictionInputError) as err:
        build_blind_curve_response(tampered, display_positions=pos)
    assert err.value.code == 'INVALID_PREDICTION_DOC_HASH'

    closed_hash = build_blind_curve_response(tampered, display_positions=pos, fail_closed=True)
    assert closed_hash['status'] == 'UNAVAILABLE'
    assert closed_hash['reason'] == 'INVALID_PREDICTION_DOC_HASH'

    # 2. Re-hashing tampered sketch points without passing display_positions must fall back to NODE_GRAPH_ONLY
    unhashed = {k: v for k, v in tampered.items() if k != 'content_sha256'}
    tampered['content_sha256'] = _canonical_hash(unhashed)

    no_pos = build_blind_curve_response(tampered, display_positions=None)
    assert no_pos['status'] == 'ESTIMATED'
    assert no_pos['coordinate_frame'] == 'NODE_GRAPH_ONLY'
    assert no_pos['overhead']['frame'] == 'NODE_GRAPH_ONLY'
    assert no_pos['overhead']['last_position'] is None
    assert no_pos['curve'] == {'basis': 'NODE_GRAPH_ONLY', 'points': []}
    assert no_pos['curve_points'] == []
    assert no_pos['curve_basis'] == 'NODE_GRAPH_ONLY'
    assert no_pos['candidates'][0]['sketch_points'] is None
    assert no_pos['candidates'][0]['sketch_basis'] == 'NODE_GRAPH_ONLY'

    # 3. Passing display positions that conflict with the doc sketch fails validation
    conflicting = {'A': [1.0, 1.0], 'B': [2.0, 2.0]}
    with pytest.raises(PredictionInputError) as err:
        build_blind_curve_response(tampered, display_positions=conflicting)
    assert err.value.code == 'INVALID_DISPLAY_POSITION'


def test_q_physical_prediction_api_route_e2e_wiring():
    import sys
    sys.path.insert(0, str(ROOT / 'tests/q1q5'))
    from test_api import OTHER, TOKEN, api_fixture, authorize, selected
    from amidst.q1q5.api import APIError

    api, run_obj = api_fixture()
    r = selected(api, run_obj)

    # Valid route call reproduces pure prediction
    res = api.call('q_physical_prediction', {'session_ref': TOKEN, 'response_ref': r['session_id'], 'as_of_us': 500_000}, authorize)
    assert res['schema_version'] == 'q-demo.physical-prediction.v1'
    # Integration (#445): the route now returns the build_blind_curve_response document (INFERRED, LOW, DISPLAY_ONLY).
    assert res['status'] == 'ESTIMATED'
    assert res['evidence_state'] == 'INFERRED' and res['confidence'] in {'LOW', 'UNKNOWN'}
    assert res['estimate']['evidence_state'] == 'INFERRED' and res['used_for'] == 'DISPLAY_ONLY'
    assert res['as_of_us'] == 500_000
    assert res['last_camera_id'] == 'A'
    assert res['candidates']

    # Cross-session forbidden
    with pytest.raises(APIError) as err:
        api.call('q_physical_prediction', {'session_ref': OTHER, 'response_ref': r['session_id'], 'as_of_us': 500_000}, authorize)
    assert err.value.status == 403

    # Invalid timestamp
    for bad in (-1, '1', 1.5, True):
        with pytest.raises(APIError) as err:
            api.call('q_physical_prediction', {'session_ref': TOKEN, 'response_ref': r['session_id'], 'as_of_us': bad}, authorize)
        assert err.value.status == 422
