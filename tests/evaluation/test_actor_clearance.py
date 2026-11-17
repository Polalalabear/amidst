"""Unit tests for scripts/design/check_actor_clearance.py (D198, D207).

Synthetic waypoints and geometry, plus anchors on the committed v2 / v2.1 drafts and the
r004 2D scene geometry (no renders, no Ground Truth)."""
import importlib.util
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('check_actor_clearance',
                                               ROOT / 'scripts/design/check_actor_clearance.py')
cac = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cac)

S = 1_000_000


def actor(actor_id, *points):
    return {'actor_id': actor_id, 'waypoints': [{'t_us': t, 'xy': list(xy)} for t, xy in points]}


def run(*actors, **extra):
    raw = {'run_id': 'synthetic', 'walls': None, 'actors': list(actors)}
    raw.update(extra)
    return raw


def check(raw):
    return cac.check_document(raw)['runs'][0]


def test_head_on_collision_fails_pair_distance():
    rep = check(run(actor('T', (0, (0, 0)), (4 * S, (4, 0))),
                    actor('X', (0, (4, 0)), (4 * S, (0, 0)))))
    row = rep['checks']['pair_distance']['pairs'][0]
    assert row['status'] == 'FAIL' and row['min_distance_m'] == 0.0
    assert row['min_at_us'] == 2 * S
    assert rep['verdict'] == 'FAIL'


def test_crossing_between_grid_points_is_caught_only_by_interpolation():
    # 2.3 m/s each, 0.4 m lateral offset, closest approach at 0.1 s (between 5 fps grid points).
    # At the grid points 0.0 s / 0.2 s the distance is sqrt(0.46^2 + 0.4^2) = 0.61 m >= 0.6 m.
    rep = check(run(actor('T', (0, (-0.23, 0.0)), (S, (2.07, 0.0))),
                    actor('X', (0, (0.23, 0.4)), (S, (-2.07, 0.4)))))
    row = rep['checks']['pair_distance']['pairs'][0]
    assert row['grid_min_distance_m'] >= 0.6
    assert row['min_distance_m'] == pytest.approx(0.4, abs=1e-6)
    assert row['min_at_us'] == 100_000
    assert row['caught_only_by_interpolation'] is True
    assert row['status'] == 'FAIL'


def test_opposite_lane_passing_passes_distance_and_lateral():
    corridor = [{'corridor_id': 'C', 'along_axis': 'x', 'bounds_xy': [[0, 10], [0, 2.4]]}]
    rep = check(run(actor('T', (0, (0, 1.1)), (8 * S, (10, 1.1))),
                    actor('X', (0, (10, 1.95)), (8 * S, (0, 1.95))), corridors=corridor))
    assert rep['checks']['pair_distance']['status'] == 'PASS'
    side = rep['checks']['side_by_side']['pairs'][0]
    assert side['min_lateral_m'] == pytest.approx(0.85)
    assert side['status'] == 'PASS'
    assert rep['verdict'] == 'UNKNOWN'  # walls undeclared -> UNKNOWN, never PASS


def test_lateral_offset_below_lane_rule_fails_even_when_distance_ok():
    corridor = [{'corridor_id': 'C', 'along_axis': 'x', 'bounds_xy': [[0, 10], [0, 2.4]]}]
    rep = check(run(actor('T', (0, (0, 1.0)), (8 * S, (10, 1.0))),
                    actor('X', (0, (10, 1.7)), (8 * S, (0, 1.7))), corridors=corridor))
    assert rep['checks']['pair_distance']['status'] == 'PASS'  # 0.7 m >= 0.6 m
    assert rep['checks']['side_by_side']['status'] == 'FAIL'   # 0.7 m < 0.8 m


DOOR = [{'door_id': 'D', 'center_xy': [0, 0], 'normal_xy': [0, 1], 'width_m': 1.2}]


def test_door_conflict_when_two_actors_pass_within_stagger():
    rep = check(run(actor('T', (0, (0, 2)), (2 * S, (0, -2))),
                    actor('X', (S, (0.4, 2)), (3 * S, (0.4, -2))), doors=DOOR))
    door = rep['checks']['doors']['doors'][0]
    assert door['status'] == 'FAIL'
    codes = door['conflicts'][0]['codes']
    assert 'STAGGER_TOO_SHORT' in codes
    assert door['conflicts'][0]['ref_gap_us'] == S


def test_simultaneous_door_occupancy_is_flagged():
    rep = check(run(actor('T', (0, (-0.3, 2)), (2 * S, (-0.3, -2))),
                    actor('X', (100_000, (0.3, 2)), (2_100_000, (0.3, -2))), doors=DOOR))
    codes = rep['checks']['doors']['doors'][0]['conflicts'][0]['codes']
    assert codes == ['SIMULTANEOUS_OCCUPANCY', 'STAGGER_TOO_SHORT']


def test_door_wait_resolves_conflict():
    # X waits outside the door zone (y = 1.0 > 0.5 half depth) until T has passed.
    waiting = {'actor_id': 'X', 'waypoints': [
        {'t_us': S, 'xy': [0.4, 2]}, {'t_us': 2 * S, 'xy': [0.4, 1.0]},
        {'t_us': 3 * S, 'xy': [0.4, 1.0], 'hold_reason': 'DOOR_WAIT'}, {'t_us': 5 * S, 'xy': [0.4, -2]}]}
    rep = check(run(actor('T', (0, (0, 2)), (2 * S, (0, -2))), waiting, doors=DOOR))
    door = rep['checks']['doors']['doors'][0]
    assert door['status'] == 'PASS'
    refs = {p['actor_id']: p['ref_us'] for p in door['passages']}
    assert refs['X'] - refs['T'] >= 1_500_000
    assert all(p['kind'] == 'CROSS_X1' for p in door['passages'])


def test_second_crossing_of_a_held_passage_is_checked():
    # T steps out through the door, stands just outside inside the zone, then comes back at ~4 s.
    # X crosses at 4.5 s: the first crossing (1 s) is far away, the return crossing is not.
    t = actor('T', (0, (0, 1)), (S, (0, -0.2)), (3 * S, (0, -0.2)), (3_200_000, (0, 0.2)), (5 * S, (0, 2)))
    x = actor('X', (3_500_000, (0.4, -2)), (5_500_000, (0.4, 2)))
    door = check(run(t, x, doors=DOOR))['checks']['doors']['doors'][0]
    held = next(p for p in door['passages'] if p['actor_id'] == 'T')
    assert held['kind'] == 'CROSS_X2'
    assert door['status'] == 'FAIL'
    assert 'STAGGER_TOO_SHORT' in door['conflicts'][0]['codes']


def test_walls_unknown_and_advisory_does_not_change_verdict():
    raw = run(actor('T', (0, (0, 0.2)), (2 * S, (2, 0.2))),
              advisory_boundaries=[{'segment_id': 'edge', 'a': [0, 0], 'b': [5, 0]}])
    rep = check(raw)
    walls = rep['checks']['walls']
    assert walls['status'] == 'UNKNOWN'
    assert walls['advisory']['actors'][0]['advisory'] == 'ADVISORY_FAIL'
    assert rep['verdict'] == 'UNKNOWN'


def test_declared_wall_too_close_fails():
    raw = run(actor('T', (0, (0, 0.2)), (2 * S, (2, 0.2))),
              walls=[{'segment_id': 'south', 'a': [0, 0], 'b': [5, 0]}])
    walls = check(raw)['checks']['walls']
    assert walls['status'] == 'FAIL'
    assert walls['actors'][0]['min_clearance_m'] == pytest.approx(0.2)


def test_seed_exclusivity_and_speed():
    rep = check(run(actor('T', (0, (0, 0)), (2 * S, (2, 0))),
                    actor('X', (500_000, (5, 5)), (S, (9, 5))),
                    seed={'actor_id': 'T', 'exclusive_until_us': S}))
    assert rep['checks']['seed']['status'] == 'FAIL'
    assert rep['checks']['speed']['status'] == 'FAIL'  # 4 m in 0.5 s = 8 m/s


def test_cli_exit_codes(tmp_path):
    ok = run(actor('T', (0, (0, 0)), (S, (1, 0))), walls=[], render_camera_ids=[])
    path = tmp_path / 'ok.json'
    path.write_text(json.dumps(ok))
    assert cac.main([str(path)]) == 0
    path.write_text(json.dumps(run(actor('T', (0, (0, 0)), (S, (1, 0))))))
    assert cac.main([str(path)]) == 3
    path.write_text(json.dumps({'runs': [{'actors': []}]}))
    assert cac.main([str(path)]) == 2


# ------------------------------------------------------------------ D207: analytic walls, spawn/exit

V21_DRAFT = ROOT / 'docs/evaluation/R004_A4B4_SCENARIO_V2_1_4ACTOR_DRAFT.json'
V2_DRAFT = ROOT / 'docs/evaluation/R004_A4B4_SCENARIO_V2_4ACTOR_DRAFT.json'
GEOMETRY = ROOT / 'docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json'


def camera_looking_plus_x(cid='CAM_X', origin=(0.0, 0.0, 1.5)):
    """Blender convention: camera -Z looks along world +x, camera +Y is world +z. HFOV 90 deg."""
    x, y, z = origin
    return {'camera_id': cid, 'camera_to_world': [[0, 0, -1, x], [-1, 0, 0, y], [0, 1, 0, z], [0, 0, 0, 1]],
            'fx': 480.0, 'fy': 480.0, 'cx': 480.0, 'cy': 270.0, 'width': 960, 'height': 540,
            'clip_start': 0.05, 'clip_end': 100.0}


def synthetic_geometry(occluders=()):
    return {'clearance_segments': [{'segment_id': 'far', 'a': [100, 100], 'b': [101, 100]}],
            'occluders_full_height': list(occluders) or [{'occluder_id': 'far', 'a': [100, 100], 'b': [101, 100]}],
            'cameras': [camera_looking_plus_x()], 'floors': []}


def spawn_run(*actors, duration=10 * S, cams=('CAM_X',)):
    return {'run_id': 'synthetic', 'walls': 'FROM_GEOMETRY', 'duration_us': duration,
            'render_camera_ids': list(cams), 'actors': list(actors)}


def spawn_check(raw, geometry):
    return cac.check_document({'runs': [raw]}, geometry=geometry)['runs'][0]['checks']['spawn_exit']


def test_analytic_wall_distance_is_exact_with_time_and_position():
    # path (0,1)->(4,1) over 4 s passes the end of a wall stub (2,0)-(2,0.6): closest 0.4 m at x=2, t=2 s
    rep = check(run(actor('T', (0, (0, 1)), (4 * S, (4, 1))),
                    walls=[{'segment_id': 'stub', 'a': [2, 0], 'b': [2, 0.6]}]))
    row = rep['checks']['walls']['actors'][0]
    assert rep['checks']['walls']['method'] == 'ANALYTIC_SEGMENT_DISTANCE_PER_LEG'
    assert row['min_clearance_m'] == pytest.approx(0.4)
    assert row['at_us'] == 2 * S and row['position_xy'] == [2.0, 1.0]
    assert row['status'] == 'PASS'


def test_analytic_wall_catches_a_crossing_between_samples():
    # 0.2 m wide screen crossed in 2 ms of a 50 m/s leg; dense sampling (20 ms) would miss it
    rep = check(run(actor('T', (0, (0, 1)), (200_000, (10, 1))),
                    walls=[{'segment_id': 'thin', 'a': [5.05, 0.9], 'b': [5.05, 1.1]}]))
    row = rep['checks']['walls']['actors'][0]
    assert row['min_clearance_m'] == 0.0 and row['status'] == 'FAIL'
    assert row['at_us'] == 101_000


def test_path_segment_min_handles_parallel_and_stationary():
    assert cac.path_segment_min((0, 1), (4, 1), (0, 0), (4, 0)) == (pytest.approx(1.0), pytest.approx(0.0))
    d, _ = cac.path_segment_min((1, 1), (1, 1), (0, 0), (4, 0))
    assert d == pytest.approx(1.0)


def test_walls_from_geometry_uses_geometry_segments():
    geo = synthetic_geometry()
    geo['clearance_segments'] = [{'segment_id': 'near', 'a': [0, 0], 'b': [10, 0]}]
    rep = cac.check_document({'runs': [spawn_run(actor('T', (0, (0, 0.3)), (S, (1, 0.3))), cams=())]},
                             geometry=geo)['runs'][0]
    assert rep['checks']['walls']['actors'][0]['segment_id'] == 'near'
    assert rep['checks']['walls']['status'] == 'FAIL'
    with pytest.raises(cac.ScenarioError):
        cac.check_document({'runs': [spawn_run(actor('T', (0, (0, 0.3)), (S, (1, 0.3))))]})


def test_spawn_in_front_of_camera_is_in_view_fail():
    rep = spawn_check(spawn_run(actor('X', (2 * S, (6, 0)), (10 * S, (6, 0)))), synthetic_geometry())
    first = rep['actors'][0]
    assert first['kind'] == 'SPAWN' and first['status'] == 'FAIL'
    assert first['samples'][0]['cameras'][0]['status'] == 'IN_VIEW'
    assert rep['status'] == 'FAIL'


def test_spawn_behind_camera_is_out_of_frustum_pass():
    rep = spawn_check(spawn_run(actor('X', (2 * S, (-3, 0)), (10 * S, (-3, 0)))), synthetic_geometry())
    assert rep['actors'][0]['samples'][0]['cameras'][0]['status'] == 'OUT_OF_FRUSTUM'
    assert rep['status'] == 'PASS'


def test_spawn_behind_full_height_wall_is_occluded_pass_and_gap_is_fail():
    wall = {'occluder_id': 'W', 'a': [4, -3], 'b': [4, 3]}
    rep = spawn_check(spawn_run(actor('X', (2 * S, (8, 0)), (10 * S, (8, 0)))), synthetic_geometry([wall]))
    cam = rep['actors'][0]['samples'][0]['cameras'][0]
    assert cam['status'] == 'WALL_OCCLUDED' and cam['occluder_id'] == 'W'
    assert rep['status'] == 'PASS'
    short = {'occluder_id': 'short', 'a': [4, -0.1], 'b': [4, 0.1]}      # body sticks out on both sides
    rep = spawn_check(spawn_run(actor('X', (2 * S, (8, 0)), (10 * S, (8, 0)))), synthetic_geometry([short]))
    assert rep['actors'][0]['samples'][0]['cameras'][0]['status'] == 'IN_VIEW'


def test_partly_covered_by_two_walls_is_unknown_not_pass():
    # two pieces meet at y=0: every corner is blocked by one of them, but no single piece blocks all
    # (junction off the body axis: a sight line exactly through an end point counts as unblocked)
    walls = [{'occluder_id': 'S', 'a': [4, -3], 'b': [4, 0.1]}, {'occluder_id': 'N', 'a': [4, 0.1], 'b': [4, 3]}]
    rep = spawn_check(spawn_run(actor('X', (2 * S, (8, 0)), (10 * S, (8, 0)))), synthetic_geometry(walls))
    assert rep['actors'][0]['samples'][0]['cameras'][0]['status'] == 'UNKNOWN'
    assert rep['status'] == 'UNKNOWN'


def test_present_at_t0_needs_note_and_recording_end_counts_as_exit():
    geo = synthetic_geometry()
    raw = spawn_run(actor('T', (0, (6, 0)), (10 * S, (6, 0))))
    rep = spawn_check(raw, geo)
    assert rep['actors'][0]['kind'] == 'PRESENT_AT_T0' and rep['actors'][0]['status'] == 'FAIL'
    assert rep['actors'][1]['kind'] == 'STAYS_TO_RECORDING_END' and rep['actors'][1]['status'] == 'PASS'
    raw['actors'][0]['present_at_t0_note'] = 'seed person, visible by design'
    assert spawn_check(raw, geo)['status'] == 'PASS'


def test_despawn_in_view_fails_and_checks_last_render_frame():
    # disappears at 5.1 s in front of the camera; the last rendered frame (5.0 s) is checked too
    rep = spawn_check(spawn_run(actor('X', (2 * S, (-3, 0)), (5_100_000, (6, 0)))), synthetic_geometry())
    last = rep['actors'][1]
    assert last['kind'] == 'DESPAWN' and last['status'] == 'FAIL'
    assert [smp['t_us'] for smp in last['samples']] == [5_000_000, 5_100_000]


def test_spawn_exit_unknown_without_geometry_and_pass_without_cameras():
    raw = run(actor('T', (2 * S, (0, 0)), (3 * S, (1, 0))), walls=[])
    assert check(raw)['checks']['spawn_exit']['status'] == 'UNKNOWN'
    raw['render_camera_ids'] = []
    assert check(raw)['checks']['spawn_exit']['status'] == 'PASS'


def test_r004_geometry_is_source_bound():
    geo = json.loads(GEOMETRY.read_text(encoding='utf-8'))
    prov = geo['provenance']
    assert prov['source_blend']['sha256'] == '466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b'
    assert prov['camera_catalog']['sha256'] == '3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f'
    assert prov['codex_feasibility']['artifact_manifest_sha256'] == 'fcf478fe5212b360fc1ff71039c16ea846239d72bf9a322a1ef0b7b29f5c0b46'
    assert prov['gt_read'] is False and prov['rgb_read'] is False
    assert len(geo['clearance_segments']) == 260
    assert {c['camera_id'] for c in geo['cameras']} >= {c for s in geo['render_camera_sets'].values() for c in s}
    assert geo['door_openings']['R004_WEST_ENTRY']['width_m'] == pytest.approx(1.4)
    assert geo['door_openings']['PORTAL_R101']['center_xy'] == [8, 0]


def test_v2_draft_reproduces_codex_516_clearance_numbers():
    """The unchanged v2 routes against the measured geometry give Codex's #516 analytic numbers."""
    doc = json.loads(V2_DRAFT.read_text(encoding='utf-8'))
    geo = json.loads(GEOMETRY.read_text(encoding='utf-8'))
    for r in doc['runs']:
        r['walls'] = 'FROM_GEOMETRY'
    rep = cac.check_document(doc, geometry=geo)
    got = {(r['run_id'][:4], a['actor_id']): a['min_clearance_m'] for r in rep['runs'] for a in r['checks']['walls']['actors']}
    codex = {('A4-1', 'T'): 0.30, ('A4-1', 'A'): 0.0, ('A4-1', 'B'): 0.0, ('A4-1', 'C'): 0.35,
             ('B4-1', 'T'): 0.1971, ('B4-1', 'A'): 0.0, ('B4-1', 'B'): 0.199, ('B4-1', 'C'): 0.35}
    assert got == {k: pytest.approx(v, abs=1e-4) for k, v in codex.items()}
    # the committed v2 draft itself still has walls=null (UNKNOWN), unchanged by v2.1
    assert cac.check_document(json.loads(V2_DRAFT.read_text(encoding='utf-8')))['verdict'] == 'UNKNOWN'


def test_v21_draft_passes_every_check_with_margin():
    doc = json.loads(V21_DRAFT.read_text(encoding='utf-8'))
    rep = cac.check_document(doc)
    assert rep['verdict'] == 'PASS'
    for r in rep['runs']:
        assert r['verdict'] == 'PASS', r['check_status']
        assert set(r['check_status']) == {'pair_distance', 'side_by_side', 'doors', 'walls', 'spawn_exit', 'seed', 'speed'}
        assert min(a['min_clearance_m'] for a in r['checks']['walls']['actors']) >= 0.45 - 1e-6
        for row in r['checks']['spawn_exit']['actors']:
            if row['kind'] in ('SPAWN', 'DESPAWN'):
                assert all(c['status'] in ('OUT_OF_FRUSTUM', 'WALL_OCCLUDED')
                           for smp in row['samples'] for c in smp['cameras'])
            elif row['kind'] == 'PRESENT_AT_T0':
                assert row['actor_id'] == 'T'
    assert doc['hsv_config']['version'] == 'D131-DEMO-HSV-v1'
    assert doc['hsv_config']['crop_ratio'] == 0.5 and doc['hsv_config']['value_min'] == 0.2


def test_v21_keeps_the_v1_target_event_times():
    """D207: the target may move for clearance (<= 0.3 m here), but its v1 waypoint times stay."""
    v21 = json.loads(V21_DRAFT.read_text(encoding='utf-8'))
    v2 = json.loads(V2_DRAFT.read_text(encoding='utf-8'))
    for new_run, old_run in zip(v21['runs'], v2['runs']):
        new = [w for w in next(a for a in new_run['actors'] if a['actor_id'] == 'T')['waypoints']
               if w.get('v1_waypoint_index') is not None]
        old = next(a for a in old_run['actors'] if a['actor_id'] == 'T')['waypoints']
        assert [w['t_us'] for w in new] == [w['t_us'] for w in old]
        assert [w['v1_waypoint_index'] for w in new] == list(range(17))
        assert max(math.dist(w['xy'], w0['xy']) for w, w0 in zip(new, old)) <= 0.3 + 1e-9


def test_v21_b_hue_estimate_keeps_red_band_margin():
    doc = json.loads(V21_DRAFT.read_text(encoding='utf-8'))
    import colorsys
    for r in doc['runs']:
        b = next(a for a in r['actors'] if a['actor_id'] == 'B')
        rgb = [float(v) for v in b['appearance']['upper'].split('linear RGB ')[1].split(')')[0].split('/')]
        h, s_, v = colorsys.rgb_to_hsv(*rgb)
        assert h == pytest.approx(0.012, abs=1e-3) and s_ >= 0.2 and v >= 0.2
        # Codex #516 proxy offsets for H 0.02 were -0.00425..+0.00914; worst T render shift +0.0152
        lo_edge, hi_edge = 0.95 - 1.0, 0.05
        for est in (h - 0.00425, h + 0.00914, h + 0.0152):
            assert min(est - lo_edge, hi_edge - est) >= 0.02
