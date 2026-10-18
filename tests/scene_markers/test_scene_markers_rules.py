"""One passing synthetic bundle (built from the CS-B design) and one failing case per rule.

SYNTHETIC: documents come from ``scene_marker_fixtures``; no real run, image or private file is
read.  Each failing case mutates the passing bundle and expects the named rule to FAIL with the
named issue code.
"""

from __future__ import annotations

import copy
from collections.abc import Callable
from typing import Any

import pytest
from scene_marker_fixtures import build_bundle, sha, synthetic_matrix

from amidst.scene_markers import RULES, ValidationParams, validate_documents

Bundle = dict[str, Any]


def run(bundle: Bundle, **kwargs: Any) -> dict[str, Any]:
    return validate_documents(**bundle, **kwargs)


def obj(b: Bundle, id_: str) -> dict[str, Any]:
    return next(o for o in b["static"]["objects"] if o["id"] == id_)


def walk(b: Bundle, id_: str) -> dict[str, Any]:
    return next(w for w in b["static"]["walkable"] if w["id"] == id_)


def portal(b: Bundle, id_: str) -> dict[str, Any]:
    return next(p for p in b["static"]["portals"] if p["id"] == id_)


def cam(b: Bundle, id_: str) -> dict[str, Any]:
    return next(c for c in b["cameras"]["cameras"] if c["camera_id"] == id_)


def codes(report: dict[str, Any], rule_id: str) -> set[str]:
    return {
        i["code"] for i in report["issues"] if i["rule_id"] == rule_id and i["severity"] == "ERROR"
    }


def rule_result(report: dict[str, Any], rule_id: str) -> str:
    return next(r["result"] for r in report["rules"] if r["rule_id"] == rule_id)


# ---------------------------------------------------------------- passing examples


@pytest.mark.parametrize("event", ["a", "b1"])
def test_conforming_bundle_passes_every_rule(event: str) -> None:
    report = run(build_bundle(event))
    assert report["status"] == "PASS", [i for i in report["issues"] if i["severity"] == "ERROR"]
    assert report["summary"]["errors"] == 0
    skipped = {r["rule_id"] for r in report["rules"] if r["result"] == "SKIPPED"}
    assert skipped == {"RUN-003"}  # no file bytes in memory
    assert report["summary"]["rules_total"] == len(RULES) == 48
    assert report["checked_schema_version"] == "controlled-scene.static.v1"


def test_event_a_warns_only_that_n1_is_unbound() -> None:
    report = run(build_bundle("a"))
    warns = [i for i in report["issues"] if i["severity"] == "WARN"]
    assert [(w["code"], w["id"]) for w in warns] == [("CAMERA_UNBOUND", "CAM_N1")]
    assert not [i for i in run(build_bundle("b1"))["issues"] if i["severity"] == "WARN"]


def test_report_is_deterministic_and_self_hashed() -> None:
    a, b = run(build_bundle("a")), run(build_bundle("a"))
    assert a == b
    assert len(a["output_sha256"]) == 64
    changed = copy.deepcopy(build_bundle("a"))
    changed["static"]["scene_version"] = 1
    changed["manifest"]["source_sha256"] = sha("other")
    assert run(changed)["output_sha256"] != a["output_sha256"]


def test_headline_design_values_are_literal_in_the_conforming_bundle() -> None:
    """Independent of the template: the numbers the task names, written out in the test."""
    b = build_bundle("a")
    w2 = cam(b, "CAM_W2")["camera_to_world"]
    assert [w2[0][3], w2[1][3], w2[2][3]] == [14.4, 2.1, 1.8]  # D48
    removed = sum(w for w in (0.24, 0.0385, 0.12, 0.12, 0.28, 0.288, 0.288, 0.168, 0.168, 0.36))
    assert removed == pytest.approx(2.0705)
    report = run(b)
    assert report["status"] == "PASS"
    assert len([o for o in b["static"]["objects"] if o["id"].startswith("OBSTACLE_")]) == 5
    assert len(walk(b, "WALK_R102")["holes_m"]) == 1
    assert all(len(w["holes_m"]) == 0 for w in b["static"]["walkable"] if w["id"] != "WALK_R102")


# ---------------------------------------------------------------- failing examples
# (case id, rule, expected code, mutation)


def _drop(key: str, section: str = "static") -> Callable[[Bundle], None]:
    return lambda b: b[section].pop(key)


def _set(path: list[Any], value: Any, section: str = "static") -> Callable[[Bundle], None]:
    def go(b: Bundle) -> None:
        node: Any = b[section]
        for key in path[:-1]:
            node = node[key]
        node[path[-1]] = value

    return go


def m_remove_object(id_: str) -> Callable[[Bundle], None]:
    return lambda b: b["static"]["objects"].remove(obj(b, id_))


def m_duplicate_object(b: Bundle) -> None:
    b["static"]["objects"].append(copy.deepcopy(obj(b, "WALL_N_E1")))


def m_extra_object(b: Bundle) -> None:
    extra = copy.deepcopy(obj(b, "OBSTACLE_SCREEN_W"))
    extra["id"] = "OBSTACLE_SCREEN_EXTRA"
    extra["bounds_m"] = [[12, 0.5, 0], [12.1, 0.9, 3.2]]
    extra["footprint_m"] = [[12, 0.5], [12.1, 0.5], [12.1, 0.9], [12, 0.9]]
    b["static"]["objects"].append(extra)


def m_lowercase_id(b: Bundle) -> None:
    obj(b, "ROOM_R101")["id"] = "room_r101"


def m_wrong_prefix(b: Bundle) -> None:
    obj(b, "WALL_R101_W")["id"] = "OBSTACLE_R101_W"


def m_dangling_connection(b: Bundle) -> None:
    walk(b, "WALK_CORNER")["connections"][0]["to_walk_id"] = "WALK_NOWHERE"


def m_dangling_portal(b: Bundle) -> None:
    walk(b, "WALK_R101")["connections"][0]["via_portal_id"] = "PORTAL_GONE"


def m_prefilled_approval(b: Bundle) -> None:
    walk(b, "WALK_R101")["approval"] = {
        "status": "NOT_EVALUATED",
        "verified_by": ["C7 v1", "K7 v1"],
        "verification_sha256": sha("x"),
    }


def m_approved_without_ref(b: Bundle) -> None:
    obj(b, "WALL_N_E1")["approval_status"] = "APPROVED"


def m_display_only_collision(b: Bundle) -> None:
    obj(b, "ROOM_R101")["allowed_purposes"] = ["DISPLAY", "COLLISION"]


def m_wall_walkability(b: Bundle) -> None:
    obj(b, "WALL_N_E1")["allowed_purposes"] = ["WALKABILITY"]


def m_floor_raised(b: Bundle) -> None:
    b["static"]["floors"][0]["support_plane"]["point_m"] = [0, 0, 0.4959]


def m_two_floors(b: Bundle) -> None:
    second = copy.deepcopy(b["static"]["floors"][0])
    second["floor_id"] = "FLOOR_UPPER"
    b["static"]["floors"].append(second)


def m_vertex_z(b: Bundle) -> None:
    ring = walk(b, "WALK_CORNER")["polygon_m"]
    ring[0] = [*ring[0], 0.2]


def m_clockwise(b: Bundle) -> None:
    w = walk(b, "WALK_CORNER")
    w["polygon_m"] = w["polygon_m"][::-1]


def m_bowtie(b: Bundle) -> None:
    walk(b, "WALK_CORNER")["polygon_m"] = [[15, 0], [17.4, 2.4], [17.4, 0], [15, 2.4]]


def m_ccw_hole(b: Bundle) -> None:
    w = walk(b, "WALK_R102")
    w["holes_m"][0] = w["holes_m"][0][::-1]


def m_hole_on_boundary(b: Bundle) -> None:
    walk(b, "WALK_R102")["holes_m"] = [[[17.6, 7.8], [17.6, 10.2], [18.15, 10.2], [18.15, 7.8]]]
    walk(b, "WALK_R102")["polygon_m"] = [
        [17.52, 7],
        [22.4, 7],
        [22.4, 11],
        [17.52, 11],
        [17.52, 9.6],
        [17.4, 9.6],
        [17.4, 8.4],
        [17.52, 8.4],
    ]


def m_touching_hole(b: Bundle) -> None:
    # a hole that shares an edge with the outer ring (should have been an outer-ring notch)
    w = walk(b, "WALK_R102")
    w["holes_m"] = [[[22.4, 7.8], [22.4, 10.2], [22.0, 10.2], [22.0, 7.8]]]


def m_overlap(b: Bundle) -> None:
    walk(b, "WALK_CORNER")["polygon_m"] = [[14, 0], [17.4, 0], [17.4, 2.4], [14, 2.4]]


def m_asymmetric(b: Bundle) -> None:
    walk(b, "WALK_CORR_N")["connections"] = [
        c for c in walk(b, "WALK_CORR_N")["connections"] if c["to_walk_id"] != "WALK_CORNER"
    ]


def m_null_via_without_edge(b: Bundle) -> None:
    walk(b, "WALK_VEST_W")["connections"].append({"to_walk_id": "WALK_R102", "via_portal_id": None})
    walk(b, "WALK_R102")["connections"].append({"to_walk_id": "WALK_VEST_W", "via_portal_id": None})


def m_connection_removed_both_ways(b: Bundle) -> None:
    walk(b, "WALK_CORNER")["connections"] = [
        c for c in walk(b, "WALK_CORNER")["connections"] if c["to_walk_id"] != "WALK_CORR_N"
    ]
    walk(b, "WALK_CORR_N")["connections"] = [
        c for c in walk(b, "WALK_CORR_N")["connections"] if c["to_walk_id"] != "WALK_CORNER"
    ]


def m_cut_not_applied(b: Bundle) -> None:
    walk(b, "WALK_CORR_W")["polygon_m"] = [
        [0, 0],
        [15, 0],
        [15, 2.4],
        [0, 2.4],
    ]  # SCREEN_W / CORNER_N cut-outs left walkable


def m_hole_instead_of_notch(b: Bundle) -> None:
    walk(b, "WALK_CORR_N")["holes_m"] = [[[15.2, 5.25], [15.2, 5.6], [15.8, 5.6], [15.8, 5.25]]]
    walk(b, "WALK_CORR_N")["polygon_m"] = [[15, 2.4], [17.4, 2.4], [17.4, 12], [15, 12]]


def m_footprint_vs_bounds(b: Bundle) -> None:
    obj(b, "OBSTACLE_SCREEN_W")["footprint_m"] = [[10.4, 0], [10.7, 0], [10.7, 0.8], [10.4, 0.8]]


def m_clearance(b: Bundle) -> None:
    o = obj(b, "OBSTACLE_SCREEN_CORNER_N")  # the superseded y=1.55 position (D50 moved it to 1.60)
    o["bounds_m"] = [[14.5, 1.55, 0], [14.65, 2.4, 3.2]]
    o["footprint_m"] = [[14.5, 1.55], [14.65, 1.55], [14.65, 2.4], [14.5, 2.4]]


def m_aabb(b: Bundle) -> None:
    w = obj(b, "WALL_N_E1")
    w["bounds_m"] = [[17.4, 2.4, 0], [17.52, 8.4, 3.0]]
    w["height_m"] = 3.0


def m_portal_width(b: Bundle) -> None:
    portal(b, "PORTAL_R101")["opening_m"]["width_m"] = 1.0


def m_portal_off(b: Bundle) -> None:
    portal(b, "PORTAL_R101")["opening_m"]["a"] = [7.4, 1.0]
    portal(b, "PORTAL_R101")["opening_m"]["width_m"] = math_dist([7.4, 1.0], [8.6, 0])


def math_dist(a: list[float], c: list[float]) -> float:
    return ((a[0] - c[0]) ** 2 + (a[1] - c[1]) ** 2) ** 0.5


def m_portal_sill(b: Bundle) -> None:
    portal(b, "PORTAL_R102")["opening_m"]["sill_z_m"] = 0.1


def m_matrix_scaled(b: Bundle) -> None:
    for row in cam(b, "CAM_W1")["camera_to_world"][:3]:
        row[0] *= 1.01


def m_matrix_mirrored(b: Bundle) -> None:
    for row in cam(b, "CAM_W1")["camera_to_world"][:3]:
        row[0] = -row[0]


def m_image_size(b: Bundle) -> None:
    cam(b, "CAM_W1")["width"] = 1920


def m_focal(b: Bundle) -> None:
    cam(b, "CAM_W1")["fx"] = cam(b, "CAM_W1")["fx"] + 5


def m_shared_clock(b: Bundle) -> None:
    other = copy.deepcopy(b["cameras"]["run_bindings"][0])
    other["run_id"] = "ctrl-lcorr-s1-b1-5fps-v1-r001"  # B1 reuses A's clock
    b["cameras"]["run_bindings"].append(other)


def m_w2_old_position(b: Bundle) -> None:
    c = cam(b, "CAM_W2")
    c["camera_to_world"] = synthetic_matrix([14.5, 2.1, 1.8], 205, 10)  # D48 superseded x=14.5


def m_w2_old_yaw(b: Bundle) -> None:
    c = cam(b, "CAM_W2")
    c["camera_to_world"] = synthetic_matrix([14.4, 2.1, 1.8], 202, 10)  # D50 superseded yaw 202°


def m_w2_rolled(b: Bundle) -> None:
    cam(b, "CAM_W2")["camera_to_world"] = synthetic_matrix([14.4, 2.1, 1.8], 205, 10, roll_deg=3.0)


def m_camera_in_screen(b: Bundle) -> None:
    c = cam(b, "CAM_W2")
    c["camera_to_world"] = synthetic_matrix([14.55, 2.0, 1.8], 205, 10)


def m_scene_mismatch(b: Bundle) -> None:
    b["manifest"]["scene_version"] = 2


def m_bad_clock(b: Bundle) -> None:
    b["manifest"]["clock_id"] = "clock:other"


def m_duration(b: Bundle) -> None:
    b["manifest"]["sampling"]["duration_s"] = 10.1


def m_last_is_duration(b: Bundle) -> None:
    b["manifest"]["sampling"]["last_timestamp_s"] = 10.0


def m_drop_record(b: Bundle) -> None:
    b["rgb_index"]["records"].pop(7)


def m_in_both(b: Bundle) -> None:
    rec = b["rgb_index"]["records"][3]
    b["rgb_index"]["missing"].append(
        {
            "camera_id": rec["camera_id"],
            "frame_index": rec["frame_index"],
            "timestamp_s": rec["timestamp_s"],
            "reason": "RGB_RECORD_ABSENT",
        }
    )


def m_bad_ref(b: Bundle) -> None:
    b["rgb_index"]["records"][5]["rgb_ref"] = "rgb/CAM_W2/frame_000005.png"


def m_bad_timestamp(b: Bundle) -> None:
    b["rgb_index"]["records"][9]["timestamp_s"] = 9.9


def m_out_of_range(b: Bundle) -> None:
    rec = copy.deepcopy(b["rgb_index"]["records"][0])
    rec["frame_index"] = 50
    rec["timestamp_s"] = 10.0
    rec["rgb_ref"] = f"rgb/{rec['camera_id']}/frame_000050.png"
    b["rgb_index"]["records"].append(rec)


def m_event_cameras(b: Bundle) -> None:
    b["rgb_index"]["records"] = [
        r for r in b["rgb_index"]["records"] if r["camera_id"] != "CAM_R102_CTRL"
    ]
    b["cameras"]["run_bindings"] = [
        x for x in b["cameras"]["run_bindings"] if x["camera_id"] != "CAM_R102_CTRL"
    ]


def m_event_samples(b: Bundle) -> None:
    b["manifest"]["sampling"]["duration_s"] = 8
    b["manifest"]["sampling"]["sample_count_per_camera"] = 40
    b["manifest"]["sampling"]["last_timestamp_s"] = 7.8
    b["rgb_index"]["records"] = [r for r in b["rgb_index"]["records"] if r["frame_index"] < 40]


def m_actor_key(b: Bundle) -> None:
    b["static"]["objects"][0]["actor_id"] = "P1"


def m_seed_in_manifest(b: Bundle) -> None:
    b["manifest"]["sampling"]["random_seed"] = 12345


def m_private_path(b: Bundle) -> None:
    obj(b, "WALL_N_E1")["geometry_ref"] = (
        "private_evaluation/ctrl-lcorr-s1-a-5fps-v1-r001/gt/mask.png"
    )


def m_absolute_path(b: Bundle) -> None:
    b["rgb_index"]["records"][0]["rgb_ref"] = "/Users/someone/data/frame_000000.png"


def m_traversal(b: Bundle) -> None:
    obj(b, "WALL_N_E1")["geometry_ref"] = "geometry/../../private/WALL.json"


def m_blend_ref(b: Bundle) -> None:
    obj(b, "WALL_N_E1")["geometry_ref"] = "assets/controlled_scene_v1_s001_r001.blend"


def m_allowlist_private(b: Bundle) -> None:
    b["manifest"]["allowlist"].append(
        {"role": "event_query", "filename": "persons.sim.json", "file_sha256": sha("p")}
    )


def m_bad_hash(b: Bundle) -> None:
    obj(b, "WALL_N_E1")["geometry_sha256"] = "ABC123"


def m_null_hash(b: Bundle) -> None:
    b["static"]["source_static_sha256"] = None


CASES: list[tuple[str, str, str, Callable[[Bundle], None]]] = [
    ("sch001-missing-frame-id", "SCH-001", "FIELD_MISSING", _drop("frame_id")),
    ("sch001-wrong-unit", "SCH-001", "FIELD_VALUE", _set(["length_unit"], "ft")),
    (
        "sch002-floor-field",
        "SCH-002",
        "FIELD_MISSING",
        lambda b: b["static"]["floors"][0].pop("approved_scope_ref"),
    ),
    (
        "sch003-object-field",
        "SCH-003",
        "FIELD_MISSING",
        lambda b: obj(b, "WALL_N_E1").pop("geometry_sha256"),
    ),
    (
        "sch003-bad-class",
        "SCH-003",
        "ENUM_VALUE",
        lambda b: obj(b, "WALL_N_E1").update({"class": "PILLAR"}),
    ),
    (
        "sch004-walk-field",
        "SCH-004",
        "FIELD_MISSING",
        lambda b: walk(b, "WALK_CORNER").pop("connections"),
    ),
    (
        "sch004-bad-status",
        "SCH-004",
        "ENUM_VALUE",
        lambda b: walk(b, "WALK_CORNER").update({"status": "OPEN"}),
    ),
    (
        "sch005-solid-field",
        "SCH-005",
        "FIELD_MISSING",
        lambda b: obj(b, "WALL_N_E1").pop("body_policy_ref"),
    ),
    (
        "sch005-bad-scope",
        "SCH-005",
        "ENUM_VALUE",
        lambda b: obj(b, "WALL_N_E1").update({"collision_scope": "MESH"}),
    ),
    (
        "sch006-door-closed",
        "SCH-006",
        "FIELD_VALUE",
        lambda b: portal(b, "PORTAL_R101").update({"state": "CLOSED"}),
    ),
    ("sch006-stairs", "SCH-006", "STAIR_NOT_ALLOWED", _set(["stairs"], [{"id": "STAIR_X"}])),
    (
        "sch007-distortion",
        "SCH-007",
        "FIELD_VALUE",
        lambda b: cam(b, "CAM_W1").update({"distortion": {"k1": 0.1}}),
    ),
    (
        "sch007-run-field-in-optics",
        "SCH-007",
        "RUN_FIELD_IN_OPTICS",
        lambda b: cam(b, "CAM_W1").update({"clock_id": "clock:x"}),
    ),
    (
        "sch008-binding-field",
        "SCH-008",
        "FIELD_MISSING",
        lambda b: b["cameras"]["run_bindings"][0].pop("binding_sha256"),
    ),
    (
        "sch008-clock-format",
        "SCH-008",
        "CLOCK_ID_FORMAT",
        lambda b: b["cameras"]["run_bindings"][0].update({"clock_id": "clock-A"}),
    ),
    (
        "sch009-sampling-format",
        "SCH-009",
        "FIELD_VALUE",
        _set(["sampling", "format"], "JPEG", "manifest"),
    ),
    ("sch009-no-allowlist", "SCH-009", "FIELD_MISSING", _drop("allowlist", "manifest")),
    ("sch010-no-missing-array", "SCH-010", "FIELD_TYPE", _drop("missing", "rgb_index")),
    (
        "sch010-empty-reason",
        "SCH-010",
        "FIELD_VALUE",
        lambda b: b["rgb_index"]["missing"].append(
            {"camera_id": "CAM_W1", "frame_index": 0, "timestamp_s": 0.0, "reason": ""}
        ),
    ),
    ("sch011-profile-run", "SCH-011", "FIELD_MISSING", _drop("run_id", "runtime_profile")),
    ("hsh001-format", "HSH-001", "HASH_FORMAT", m_bad_hash),
    ("hsh001-null", "HSH-001", "HASH_FORMAT", m_null_hash),
    ("id001-lowercase", "ID-001", "ID_FORMAT", m_lowercase_id),
    ("id002-prefix", "ID-002", "ID_PREFIX", m_wrong_prefix),
    ("id003-duplicate", "ID-003", "ID_DUPLICATE", m_duplicate_object),
    ("id004-dangling-walk", "ID-004", "DANGLING_REF", m_dangling_connection),
    ("id004-dangling-portal", "ID-004", "DANGLING_REF", m_dangling_portal),
    (
        "id005-missing-obstacle",
        "ID-005",
        "EXPECTED_ID_MISSING",
        m_remove_object("OBSTACLE_SCREEN_N"),
    ),
    ("id005-extra-obstacle", "ID-005", "UNEXPECTED_ID", m_extra_object),
    (
        "id005-wrong-class",
        "ID-005",
        "EXPECTED_CLASS_MISMATCH",
        lambda b: obj(b, "OBSTACLE_SCREEN_N").update({"class": "WALL"}),
    ),
    ("apr001-approved-no-ref", "APR-001", "APPROVAL_INCOMPLETE", m_approved_without_ref),
    ("apr001-prefilled", "APR-001", "APPROVAL_PREFILLED", m_prefilled_approval),
    ("apr002-display-only", "APR-002", "DISPLAY_ONLY_PURPOSE", m_display_only_collision),
    ("apr003-wall-walkability", "APR-003", "PURPOSE_NOT_CANDIDATE", m_wall_walkability),
    ("flr001-raised-floor", "FLR-001", "FLOOR_Z_NOT_ZERO", m_floor_raised),
    ("flr001-two-floors", "FLR-001", "FLOOR_COUNT", m_two_floors),
    ("flr001-vertex-z", "FLR-001", "FLOOR_Z_NOT_ZERO", m_vertex_z),
    ("wlk001-clockwise", "WLK-001", "POLYGON_ORIENTATION", m_clockwise),
    ("wlk001-bowtie", "WLK-001", "POLYGON_SELF_INTERSECT", m_bowtie),
    ("wlk001-ccw-hole", "WLK-001", "POLYGON_ORIENTATION", m_ccw_hole),
    ("wlk002-hole-touches-outer", "WLK-002", "HOLE_NOT_INTERIOR", m_touching_hole),
    ("wlk003-overlap", "WLK-003", "WALK_OVERLAP", m_overlap),
    ("wlk004-asymmetric", "WLK-004", "CONNECTION_ASYMMETRIC", m_asymmetric),
    ("wlk004-null-via-no-edge", "WLK-004", "CONNECTION_NO_SHARED_EDGE", m_null_via_without_edge),
    ("wlk005-connection-missing", "WLK-005", "CONNECTION_MISSING", m_connection_removed_both_ways),
    ("wlk005-connection-unexpected", "WLK-005", "CONNECTION_UNEXPECTED", m_null_via_without_edge),
    ("wlk006-cut-not-applied", "WLK-006", "CUT_NOT_REMOVED", m_cut_not_applied),
    ("wlk006-total-area", "WLK-006", "CUT_TOTAL_MISMATCH", m_cut_not_applied),
    ("wlk006-hole-count", "WLK-006", "HOLE_COUNT", m_hole_instead_of_notch),
    ("obs001-footprint-bounds", "OBS-001", "FOOTPRINT_BOUNDS_MISMATCH", m_footprint_vs_bounds),
    ("obs002-solid-on-walkable", "OBS-002", "SOLID_OVERLAPS_WALKABLE", m_cut_not_applied),
    ("obs003-clearance", "OBS-003", "CLEARANCE_TOO_SMALL", m_clearance),
    ("obs004-aabb", "OBS-004", "AABB_MISMATCH", m_aabb),
    ("prt001-width", "PRT-001", "PORTAL_WIDTH", m_portal_width),
    ("prt001-off-walkable", "PRT-001", "PORTAL_OFF_WALKABLE", m_portal_off),
    ("prt002-sill", "PRT-002", "PORTAL_DIMENSION", m_portal_sill),
    ("cam001-scaled", "CAM-001", "MATRIX_NOT_ORTHONORMAL", m_matrix_scaled),
    ("cam001-mirrored", "CAM-001", "MATRIX_DETERMINANT", m_matrix_mirrored),
    ("cam002-image-size", "CAM-002", "IMAGE_SIZE_MISMATCH", m_image_size),
    ("cam002-focal", "CAM-002", "FOCAL_SENSOR_MISMATCH", m_focal),
    ("cam003-shared-clock", "CAM-003", "CLOCK_SHARED_ACROSS_RUNS", m_shared_clock),
    ("cam004-w2-old-x", "CAM-004", "CAMERA_POSITION", m_w2_old_position),
    ("cam004-w2-old-yaw", "CAM-004", "CAMERA_ORIENTATION", m_w2_old_yaw),
    ("cam004-w2-roll", "CAM-004", "CAMERA_ROLL", m_w2_rolled),
    ("cam005-inside-screen", "CAM-005", "CAMERA_TOO_CLOSE", m_camera_in_screen),
    ("run001-scene-version", "RUN-001", "SCENE_VERSION_MISMATCH", m_scene_mismatch),
    ("run001-clock-id", "RUN-001", "CLOCK_ID_FORMAT", m_bad_clock),
    ("run002-duration", "RUN-002", "DURATION_NOT_INTEGER_GRID", m_duration),
    ("run002-last-is-duration", "RUN-002", "LAST_TIMESTAMP", m_last_is_duration),
    ("run004-incomplete", "RUN-004", "RGB_INDEX_INCOMPLETE", m_drop_record),
    ("run004-in-both", "RUN-004", "RGB_INDEX_DUPLICATE", m_in_both),
    ("run004-bad-ref", "RUN-004", "RGB_REF_FORMAT", m_bad_ref),
    ("run004-timestamp", "RUN-004", "RGB_INDEX_TIMESTAMP", m_bad_timestamp),
    ("run004-out-of-range", "RUN-004", "RGB_INDEX_OUT_OF_RANGE", m_out_of_range),
    ("run005-cameras", "RUN-005", "EVENT_CAMERAS", m_event_cameras),
    ("run005-samples", "RUN-005", "EVENT_SAMPLING_MISMATCH", m_event_samples),
    ("split001-actor", "SPLIT-001", "PRIVATE_FIELD_IN_SAFE_FILE", m_actor_key),
    ("split001-seed", "SPLIT-001", "PRIVATE_FIELD_IN_SAFE_FILE", m_seed_in_manifest),
    ("split002-private-path", "SPLIT-002", "PRIVATE_REFERENCE_IN_SAFE_FILE", m_private_path),
    ("split002-absolute", "SPLIT-002", "PRIVATE_REFERENCE_IN_SAFE_FILE", m_absolute_path),
    ("split002-traversal", "SPLIT-002", "PRIVATE_REFERENCE_IN_SAFE_FILE", m_traversal),
    ("split002-blend", "SPLIT-002", "PRIVATE_REFERENCE_IN_SAFE_FILE", m_blend_ref),
    ("split003-allowlist", "SPLIT-003", "ALLOWLIST_FILENAME_NOT_SAFE", m_allowlist_private),
]


@pytest.mark.parametrize(("case_id", "rule_id", "code", "mutate"), CASES, ids=[c[0] for c in CASES])
def test_failing_example(
    case_id: str, rule_id: str, code: str, mutate: Callable[[Bundle], None]
) -> None:
    event = "b1" if rule_id in {"RUN-005"} and case_id == "run005-cameras" else "a"
    bundle = build_bundle(event)
    mutate(bundle)
    report = run(bundle)
    assert report["status"] == "FAIL"
    assert rule_result(report, rule_id) == "FAIL", (
        f"{rule_id} should fail; got {codes(report, rule_id)}"
    )
    assert code in codes(report, rule_id), (code, codes(report, rule_id))


def test_every_rule_except_file_based_ones_has_a_failing_example() -> None:
    covered = {c[1] for c in CASES}
    file_based = {"IO-001", "IO-002", "RUN-003"}  # covered in test_scene_markers_cli.py
    assert {r.rule_id for r in RULES} - covered == file_based


def test_private_values_are_never_echoed() -> None:
    bundle = build_bundle("a")
    m_private_path(bundle)
    text = str(run(bundle)["issues"])
    assert "ctrl-lcorr-s1-a-5fps-v1-r001" not in text and "mask.png" not in text


def test_forbidden_keys_leave_visibility_index_ref_alone() -> None:
    assert (
        rule_result(run(build_bundle("a")), "SPLIT-001") == "PASS"
    )  # run_bindings[].visibility_index_ref is a safe field


# ---------------------------------------------------------------- tolerances are parameters


def test_clearance_threshold_is_a_parameter() -> None:
    bundle = build_bundle("a")
    assert (
        rule_result(run(bundle, params=ValidationParams(min_clearance_m=0.11)), "OBS-003") == "FAIL"
    )
    assert (
        rule_result(run(bundle, params=ValidationParams(min_clearance_m=0.10)), "OBS-003") == "PASS"
    )


def test_camera_tolerances_are_parameters() -> None:
    bundle = build_bundle("a")
    m_w2_old_yaw(bundle)
    assert rule_result(run(bundle), "CAM-004") == "FAIL"
    assert (
        rule_result(run(bundle, params=ValidationParams(camera_angle_tol_deg=5.0)), "CAM-004")
        == "PASS"
    )
    shifted = build_bundle("a")
    m_w2_old_position(shifted)
    assert (
        rule_result(run(shifted, params=ValidationParams(camera_pos_tol_m=0.2)), "CAM-004")
        == "PASS"
    )


def test_cut_tolerances_are_parameters() -> None:
    bundle = build_bundle("a")
    m_cut_not_applied(
        bundle
    )  # SCREEN_W and SCREEN_CORNER_N cut-outs (0.24 m² in total) left walkable
    assert {"CUT_TOTAL_MISMATCH", "CUT_NOT_REMOVED"} <= codes(run(bundle), "WLK-006")
    loose = ValidationParams(
        cut_total_area_tol_m2=1.0,
        cut_item_area_tol_m2=1.0,
        walk_total_area_tol_m2=1.0,
        walk_shape_tol_m2=1.0,
    )
    assert rule_result(run(bundle, params=loose), "WLK-006") == "PASS"


def test_unknown_parameter_is_rejected() -> None:
    with pytest.raises(ValueError):
        ValidationParams.from_overrides({"clearence_m": 0.1})
    assert (
        ValidationParams.from_overrides(
            {"min_clearance_m": "0.2", "allow_extra_ids": "true"}
        ).allow_extra_ids
        is True
    )


def test_extra_ids_can_be_allowed_explicitly() -> None:
    bundle = build_bundle("a")
    m_extra_object(bundle)
    assert rule_result(run(bundle), "ID-005") == "FAIL"
    assert (
        rule_result(run(bundle, params=ValidationParams(allow_extra_ids=True)), "ID-005") == "PASS"
    )


def test_design_layer_can_be_disabled() -> None:
    bundle = build_bundle("a")
    m_w2_old_yaw(bundle)
    report = run(bundle, design=False)
    assert report["design_layer"] == "DISABLED"
    assert {
        r["rule_id"] for r in report["rules"] if r["layer"] == "design" and r["result"] == "SKIPPED"
    } == {r.rule_id for r in RULES if r.layer == "design"}
    assert report["status"] == "PASS"


# ---------------------------------------------------------------- semantics worth pinning


def test_missing_entry_counts_as_grid_coverage_but_not_as_a_record() -> None:
    bundle = build_bundle("a")
    rec = bundle["rgb_index"]["records"].pop(12)
    bundle["rgb_index"]["missing"].append(
        {
            "camera_id": rec["camera_id"],
            "frame_index": rec["frame_index"],
            "timestamp_s": rec["timestamp_s"],
            "reason": "RGB_RECORD_ABSENT",
        }
    )
    report = run(bundle)
    assert rule_result(report, "RUN-004") == "PASS"
    assert rule_result(report, "RUN-005") == "PASS"  # records + missing still total 150


def test_preview_run_skips_the_expected_grid() -> None:
    bundle = build_bundle("a")
    run_id = "ctrl-lcorr-s1-preview-5fps-v1-r001"
    bundle["manifest"].update(
        {
            "run_id": run_id,
            "clock_id": f"clock:{run_id}",
            "purpose": "CALIBRATION_PREVIEW",
            "complete": False,
        }
    )
    bundle["runtime_profile"]["run_id"] = run_id
    for binding in bundle["cameras"]["run_bindings"]:
        binding.update({"run_id": run_id, "clock_id": f"clock:{run_id}"})
    bundle["rgb_index"]["records"] = bundle["rgb_index"]["records"][:4]
    report = run(bundle)
    assert rule_result(report, "RUN-004") == "SKIPPED"
    assert report["status"] == "PASS", [i for i in report["issues"] if i["severity"] == "ERROR"]


def test_not_evaluated_scopes_are_reported_unknown_not_permitted() -> None:
    report = run(build_bundle("a"))
    scopes = {(s["scope"], s["id"]) for s in report["unknown_scopes"]}
    assert ("object_purposes", "WALL_N_E1") in scopes and (
        "walkable_verification",
        "WALK_R102",
    ) in scopes
    assert "WALL_N_E1" in {s["id"] for s in report["unknown_scopes"]}
    assert report["checked_purposes"] == [
        "COLLISION",
        "DISPLAY",
        "OCCLUSION",
        "VISIBILITY_INDEX",
        "WALKABILITY",
    ]


def test_a_crashing_rule_fails_closed() -> None:
    bundle = build_bundle("a")
    bundle["static"]["objects"][0]["bounds_m"] = "not-a-box"
    bundle["static"]["walkable"][0]["polygon_m"] = None
    report = run(bundle)
    assert report["status"] == "FAIL"
    assert rule_result(report, "SCH-003") == "FAIL"


def test_walls_above_body_height_do_not_block_the_doorway() -> None:
    """WALL_R101_LINTEL sits over the door (z 2.4–3.2): it must not be required to cut the floor."""
    bundle = build_bundle("a")
    lintel = obj(bundle, "WALL_R101_LINTEL")
    assert lintel["base_z_m"] == pytest.approx(2.4)
    assert rule_result(run(bundle), "OBS-002") == "PASS"
