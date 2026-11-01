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
