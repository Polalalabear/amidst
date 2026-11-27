"""E8 Colab pack builder (#780): synthetic fixtures only (no local dataset, no GT from disk)."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts' / 'evaluation'))
_spec = importlib.util.spec_from_file_location('build_e8_colab_pack', ROOT / 'scripts/evaluation/build_e8_colab_pack.py')
B = importlib.util.module_from_spec(_spec)
sys.modules['build_e8_colab_pack'] = B
_spec.loader.exec_module(B)

from amidst.evaluation import e8_requests as R  # noqa: E402

ORDER = ['CAM_A', 'CAM_B']
RED = [20.0, 30.0, 60.0, 120.0]
BLUE = [200.0, 30.0, 240.0, 120.0]
B_RED = [100.0, 40.0, 130.0, 150.0]
SCENE = {'camera_transitions': [{'from': 'CAM_A', 'to': 'CAM_B'}], 'overlaps': [], 'cameras': [
    {'camera_id': 'CAM_A', 'ground_footprint_polygon_xy_m': [[0, -1], [10, -1], [10, 1], [0, 1]]},
    {'camera_id': 'CAM_B', 'ground_footprint_polygon_xy_m': [[20, -1], [30, -1], [30, 1], [20, 1]]}]}


class FakeProjector:
    def ground(self, cam, u, v, w, h):
        return [u / 10.0 + (100.0 if cam == 'CAM_B' else 0.0), 0.0]


def make_case(tmp, n=12):
    ticks = []
    for t in range(n):
        paths = {}
        for cam in ORDER:
            p = tmp / 'rgb' / cam / f'{t:06d}.png'
            p.parent.mkdir(parents=True, exist_ok=True)
            Image.new('RGB', (320, 180), (t, 0, 0)).save(p)
            paths[cam] = p
        ticks.append((t, {'CAM_A': [{'bbox': list(RED), 'score': 0.9, 'color': 'red', 'red_ratio': 0.5, 'blue_ratio': 0.0},
                                    {'bbox': list(BLUE), 'score': 0.4, 'color': 'blue', 'red_ratio': 0.0, 'blue_ratio': 0.4}],
                          'CAM_B': [{'bbox': list(B_RED), 'score': 0.7, 'color': 'red', 'red_ratio': 0.3, 'blue_ratio': 0.0}]}, paths))
    return {'case_id': 'E3-X1', 'ticks': ticks, 'cameras': ORDER, 'index_content_sha256': 'i', 'records_file_sha256': 'r',
            'rgb_index_sha256': 'g'}


def b1_doc(n=12, acquire=2):
    rows = []
    for t in range(n):
        tracking = ({'state': 'TRACKING', 'active_cam': 'CAM_A', 'est_xy': [4.0, 0.0], 'lost_ticks': 0, 'box': list(RED)} if t >= acquire
                    else {'state': 'SEARCHING', 'active_cam': None, 'est_xy': None, 'lost_ticks': 0, 'box': None})
        rows.append({'tick': t, 'tracking': tracking, 'ranking': [], 'decision_source': 'RULE_ONLY',
                     'events': [{'type': 'ACQUIRE'}] if t == acquire else []})
    return {'schema_version': 'e3-f4.b-log.v1', 'case_id': 'E3-X1', 'arm': 'B1', 'rows': rows}


def gt_loader(_root, _case):
    return {t: {'id': 'T', 'present': True, 'gt_visible': ['CAM_A'], 'gt_boxes': {'CAM_A': [18.0, 28.0, 62.0, 125.0]}} for t in range(12)}


@pytest.fixture()
def built(tmp_path):
    case = make_case(tmp_path)
    b1 = tmp_path / 'b1.json'
    b1.write_text(json.dumps(b1_doc()))
    cat = tmp_path / 'cameras.catalog.json'
    cat.write_text('{"cameras": []}')
    pts = [{'case_id': 'E3-X1', 'dataset_group': 'e3', 'family': 'E3-A', 'tick': t, 'type': 'REAPPEAR', 'root': tmp_path,
            'gt_root': tmp_path, 'b1': b1} for t in (5, 9)]
    out, mac = tmp_path / 'pack', tmp_path / 'mac' / 'index.json'
    res = B.build_e8_pack(out, pts, cat, mac_index=mac, case_loader=lambda root, cid: case, gt_loader=gt_loader,
                       scene_fn=lambda cams: SCENE, projector=FakeProjector())
    return out, mac, res


def load_reqs(out):
    return [json.loads(x) for x in (out / 'requests' / 'e8_part1.jsonl').read_text().splitlines()]


def test_pack_layout_and_counts(built):
    out, mac, res = built
    assert res['gate']['status'] == 'OK' and res['decision_points'] == 2
    assert res['requests'] == 2 * len(R.LEVELS) * len(R.PERMS)
    assert (out / 'part1' / 'ref' / 'E3-X1.jpg').is_file()
    assert (out / 'part1' / 'frames' / 'E3-X1' / 't000005' / 'CAM_B_p2.jpg').is_file()
    assert len((out / 'part2' / 'ticks' / 'E3-X1.jsonl').read_text().splitlines()) == 12
    assert not any('mac' in p.parts for p in out.rglob('*'))


def test_snapshot_keep_and_levels(built):
    out, _, _ = built
    reqs = {r['request_id']: r for r in load_reqs(out)}
    r2 = reqs['E3-X1|t5|L2|p0']
    assert r2['snapshot'] == {'state': 'TRACKING', 'active_cam': 'CAM_A', 'est_xy': [4.0, 0.0], 'lost_ticks': 0, 'seen_ago_s': 0.0}
    assert r2['keep_display'] == {'camera_id': 'CAM_A', 'detection_id': 'D1'}
    assert R.display_of({'answer': 'KEEP'}, r2) == {'kind': 'BOX', 'camera_id': 'CAM_A', 'detection_id': 'D1', 'via': 'KEEP'}
    assert 'snapshot' not in reqs['E3-X1|t5|L1|p0'] and 'colors' not in reqs['E3-X1|t5|L0c|p0']['options'][0]
    l0 = reqs['E3-X1|t5|L0|p0']['e7']
    assert l0['variable_text'].startswith('NOW t=1.0s.') and [c['detection_id'] for c in l0['candidates']] == ['D1', 'D2', 'D1']
    assert reqs['E3-X1|t5|L4|p1']['image_refs']['reference'] == 'part1/ref/E3-X1.jpg'


def test_orders_reproducible_and_table_order_free(built, tmp_path):
    out, _, _ = built
    reqs = {r['request_id']: r for r in load_reqs(out)}
    keys = lambda r: [(o['camera_id'], o['detection_id']) for o in r['options']]  # noqa: E731
    assert keys(reqs['E3-X1|t5|L3|p1']) == keys(reqs['E3-X1|t5|L3|p0'])[::-1]
    table = json.loads((out / 'scoring_only' / 'answer_table.json').read_text())
    assert set(table) == {'E3-X1|t5', 'E3-X1|t9'}
    assert table['E3-X1|t5']['expected_answer'] == 'SELECT' and table['E3-X1|t5']['expected_detection_ids'] == {'CAM_A': ['D1']}


def test_no_gt_in_pack_and_mac_index_outside(built):
    out, mac, _ = built
    for p in out.rglob('*'):
        if p.is_file() and p.suffix in ('.json', '.jsonl') and p.parent.name != 'scoring_only':
            text = p.read_text()
            assert 'gt_boxes' not in text and 'gt_visible' not in text and 'gt_regime' not in text, p
    idx = json.loads(mac.read_text())
    assert [d['type'] for d in idx['decision_points']] == ['REAPPEAR', 'REAPPEAR'] and idx['decision_points'][0]['no_seed'] is False


def test_gt_leak_deletes_pack(tmp_path):
    case = make_case(tmp_path)
    doc = b1_doc()
    doc['rows'][3]['tracking']['gt_boxes'] = {}
    b1 = tmp_path / 'b1.json'
    b1.write_text(json.dumps(doc))
    cat = tmp_path / 'cat.json'
    cat.write_text('{}')
    pts = [{'case_id': 'E3-X1', 'dataset_group': 'e3', 'family': 'E3-A', 'tick': 5, 'type': 'X', 'root': tmp_path, 'gt_root': tmp_path, 'b1': b1}]
    with pytest.raises(ValueError):
        B.build_e8_pack(tmp_path / 'pack', pts, cat, mac_index=tmp_path / 'm.json', case_loader=lambda r, c: case, gt_loader=gt_loader,
                     scene_fn=lambda cams: SCENE, projector=FakeProjector(), frames=False)
    assert not (tmp_path / 'pack').exists()


def test_keep_unresolved_and_reference():
    assert B.keep_display({'tracking': {'box': None}}, {}) is None
    with pytest.raises(ValueError):
        B.keep_display({'tracking': {'box': [1, 2, 3, 4], 'active_cam': 'CAM_A'}}, {'CAM_A': [{'bbox': [1, 2, 3, 5]}]})
    assert B.reference_of(b1_doc()['rows']) == {'tick': 2, 'camera_id': 'CAM_A', 'box': RED}
    assert B.reference_of(b1_doc(acquire=99)['rows']) is None
