"""F2 (#656): wall-clipped camera coverage (camera_projection.visibility_polygon) and the optional scene_context walls."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from amidst.q1q5 import camera_projection as cp
from amidst.q1q5 import scene_context as sx

ROOT = Path(__file__).resolve().parents[2]
GEOM_PATH = ROOT / 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json'
GEOM = json.loads(GEOM_PATH.read_text())
GATE_PATH = ROOT / 'docs/evaluation/F2_WALL_GATE_20261122.json'
WALLS = cp.walls_of(GEOM)


def _area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))) / 2


def test_walls_shrink_coverage_and_vertices_are_seen_not_through_walls():
    shrunk = 0
    for c in GEOM['cameras']:
        clipped, open_ = cp.visibility_polygon(c, WALLS), cp.visibility_polygon(c, [])
        assert _area(clipped) <= _area(open_) + 1e-6
        shrunk += _area(clipped) < _area(open_) - 1e-6
        (ox, oy, _), _, _ = cp.pose_of(c)
        for x, y in clipped:
            assert cp.sees_point(c, x, y, cp.COVER_Z)
            d = ((x - ox) ** 2 + (y - oy) ** 2) ** 0.5
            assert cp.ray_hit(ox, oy, __import__('math').atan2(y - oy, x - ox), WALLS) >= d - 1e-9
    assert shrunk >= 1


@pytest.mark.skipif(shutil.which('node') is None, reason='node not installed')
def test_python_matches_live_mode_js():
    js = ROOT / 'frontend/live-mode/src/coverage.mjs'
    code = (f"import {{coverageOf}} from {json.dumps(js.as_uri())}; import fs from 'node:fs';"
            f"const g=JSON.parse(fs.readFileSync({json.dumps(str(GEOM_PATH))},'utf8'));"
            "console.log(JSON.stringify(coverageOf(g).cameras.map(c=>[c.camera_id,c.polygon])));")
    out = subprocess.run(['node', '--input-type=module', '-e', code], capture_output=True, text=True, check=True).stdout
    js_polys = dict(json.loads(out))
    for c in GEOM['cameras']:
        py = cp.visibility_polygon(c, WALLS)
        assert len(py) == len(js_polys[c['camera_id']]), c['camera_id']
        for (a, b), (x, y) in zip(py, js_polys[c['camera_id']]):
            assert abs(a - x) < 1e-6 and abs(b - y) < 1e-6


def _catalog():
    return {'cameras': [c for c in GEOM['cameras'] if c['camera_id'] in ('CAM_W1', 'CAM_W2', 'CAM_WIDE')]}


REGION = {'regions': [], 'edges': [], 'approval_status': 'DRAFT'}
CAMG = {'cameras': [], 'transitions': [], 'approval_status': 'DRAFT'}


def test_scene_context_default_unclipped_and_static_option():
    plain = sx.build(REGION, CAMG, _catalog(), None, {'g.json': '0' * 64})
    again = sx.build(REGION, CAMG, _catalog(), None, {'g.json': '0' * 64}, static=None)
    assert sx.serialize(plain) == sx.serialize(again)
    assert 'WALL_GEOMETRY_NOT_IN_CONTEXT' in plain['incomplete'] and 'static_geometry' not in plain
    raw = GEOM_PATH.read_bytes()
    st = sx.static_geometry(raw, GATE_PATH.read_bytes(), 'r004')
    assert st['walls'] == WALLS and set(st['door_openings']) == set(GEOM['door_openings'])
    clipped = sx.build(REGION, CAMG, _catalog(), None, {'g.json': '0' * 64}, static=st)
    sx.assert_no_forbidden(clipped)
    assert 'WALL_GEOMETRY_NOT_IN_CONTEXT' not in clipped['incomplete']
    assert clipped['static_geometry']['source_sha256'] == __import__('hashlib').sha256(raw).hexdigest()
    assert st['source_sha256'] in clipped['sources'].values()
    text = sx.serialize(clipped)
    assert 'visible_area_polygon_xy_m' in text and 'WALL_CLIPPED' in text
    for banned in ('clearance_segments', 'floors', 'render_camera_sets', 'note'):   # only the two D346 fields enter
        assert banned not in text
    clipped_ids = clipped['static_geometry']['wall_clipped_cameras']
    assert set(clipped_ids) == set(st['validated_cameras']) & {c['camera_id'] for c in _catalog()['cameras']}
    for cam in clipped['cameras']:
        assert ('visible_area_polygon_xy_m' in cam) == (cam['camera_id'] in clipped_ids)
        if cam['camera_id'] not in clipped_ids:
            assert 'SCENE_CONTEXT_INCOMPLETE:WALLS_NOT_VALIDATED:' + cam['camera_id'] in clipped['incomplete']


def test_static_geometry_refuses_file_without_d346_exception():
    doc = json.loads(GEOM_PATH.read_text())
    doc.pop('must_not_enter_exceptions')
    with pytest.raises(ValueError, match='STATIC_GEOMETRY_NOT_AUTHORIZED'):
        sx.static_geometry(json.dumps(doc).encode(), GATE_PATH.read_bytes(), 'r004')


def test_simplified_polygon_stays_within_tolerance():
    for c in GEOM['cameras']:
        poly = cp.visibility_polygon(c, WALLS)
        simp = cp.simplify_polygon(poly, 0.1)
        assert len(simp) <= len(poly) and simp[0] == poly[0] and simp[-1] == poly[-1]
        assert abs(_area(simp) - _area(poly)) <= 0.05 * _area(poly) + 0.5


def test_wall_gate_binds_geometry_bytes_and_live_has_no_validated_camera():
    gate = json.loads(GATE_PATH.read_text())
    assert gate['geometry_sha256'] == __import__('hashlib').sha256(GEOM_PATH.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='WALL_GATE_GEOMETRY_MISMATCH'):
        sx.static_geometry(GEOM_PATH.read_bytes(), json.dumps({**gate, 'geometry_sha256': '0' * 64}).encode(), 'r004')
    with pytest.raises(ValueError, match='WALL_GATE_SOURCE_UNKNOWN'):
        sx.static_geometry(GEOM_PATH.read_bytes(), GATE_PATH.read_bytes(), 'nope')
    live = sx.static_geometry(GEOM_PATH.read_bytes(), GATE_PATH.read_bytes(), 'live')
    assert live['validated_cameras'] == []          # strict gate on 320-px LIVE frames: nothing is clipped
    ctx = sx.build(REGION, CAMG, {'cameras': GEOM['cameras']}, None, {'g.json': '0' * 64}, static=live)
    assert all('visible_area_polygon_xy_m' not in c for c in ctx['cameras'])
    assert sum(x.startswith('SCENE_CONTEXT_INCOMPLETE:WALLS_NOT_VALIDATED:') for x in ctx['incomplete']) == len(GEOM['cameras'])
