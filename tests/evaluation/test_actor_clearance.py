"""Unit tests for scripts/design/check_actor_clearance.py (D198). Synthetic waypoints only."""
import importlib.util
import json
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
    ok = run(actor('T', (0, (0, 0)), (S, (1, 0))), walls=[])
    path = tmp_path / 'ok.json'
    path.write_text(json.dumps(ok))
    assert cac.main([str(path)]) == 0
    path.write_text(json.dumps(run(actor('T', (0, (0, 0)), (S, (1, 0))))))
    assert cac.main([str(path)]) == 3
    path.write_text(json.dumps({'runs': [{'actors': []}]}))
    assert cac.main([str(path)]) == 2
