"""#630 coverage-gap model: synthetic geometry plus three positions whose camera sets were recorded in the #619 smoke."""
from pathlib import Path

from amidst.evaluation.live_coverage_gap import (
    GRAPH_V3_CAMERAS, gap_segments, load_geometry, make_camera, route_profile, segments_cross,
    sees_floor_point, uncovered_count, visible_cameras)

GEOMETRY = Path(__file__).resolve().parents[2] / "docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json"


def test_camera_sees_ahead_not_behind_or_beyond_fov():
    cam = make_camera("C", (0.0, 0.0, 3.0), 0.0, 20.0, 685.5, 685.5)
    assert sees_floor_point(cam, [], 6.0, 0.0)
    assert not sees_floor_point(cam, [], -6.0, 0.0)
    assert not sees_floor_point(cam, [], 3.0, 6.0)  # 63 deg off-axis, hfov is 70 deg
    assert not sees_floor_point(cam, [], 6.0, 0.0, max_dist=5.0)


def test_occluder_blocks_sight_line():
    cam = make_camera("C", (0.0, 0.0, 3.0), 0.0, 20.0, 685.5, 685.5)
    wall = [((3.0, -1.0), (3.0, 1.0))]
    assert segments_cross((0, 0), (6, 0), *wall[0])
    assert not sees_floor_point(cam, wall, 6.0, 0.0)


def test_gap_segments_and_uncovered_count():
    ticks = [{"tick": i, "t_sim": i * 1.0, "xy": (float(i), 0.0)} for i in range(6)]
    segs = gap_segments(ticks, lambda t: t["tick"] not in (2, 3, 4))
    assert segs == [{"start_tick": 2, "end_tick": 4, "t_start": 2.0, "duration_s": 2.0, "n": 3,
                     "from_xy": [2.0, 0.0], "to_xy": [4.0, 0.0]}]
    cam = make_camera("C", (0.0, 0.0, 3.0), 0.0, 20.0, 685.5, 685.5)
    assert uncovered_count([(6.0, 0.0), (-6.0, 0.0)], {}, [], set(), extra=[cam]) == 1


def test_repo_geometry_matches_recorded_visibility_of_hardset_positions():
    cams, occ, _ = load_geometry(GEOMETRY)
    graph = set(GRAPH_V3_CAMERAS)
    # H1-1 tick 0 (recorded gt_visible: ENTRY, EXT_CAR, W2); hard point (-13, -1): only W2; reappear (-9.8, 7.8): EXT_CLEAR
    assert sorted(visible_cameras(cams, occ, -10.0, -0.4)) == ["CAM_ENTRY", "CAM_EXT_CAR", "CAM_W2"]
    assert visible_cameras(cams, occ, -13.0, -1.0, ids=graph) == ["CAM_W2"]
    assert visible_cameras(cams, occ, -9.8, 7.8, ids=graph) == ["CAM_EXT_CLEAR"]
    assert visible_cameras(cams, occ, -13.0, 4.0, ids=graph) == []


def test_route_profile_h1_1_leaves_near_coverage_into_far_then_blind():
    cams, occ, _ = load_geometry(GEOMETRY)
    prof = route_profile([(-10, -0.4), (-13, -1), (-13, 3)], cams, occ, set(GRAPH_V3_CAMERAS))
    assert [r["class"] for r in prof] == ["near", "far", "blind"]
