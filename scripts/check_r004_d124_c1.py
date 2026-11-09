"""D124 A4-c1 private static-reference check; never an inference input.

Reuses the byte-pinned D96 analytic projection functions. It reads static
calibration/mesh and declared planning waypoints, not RGB, animation or old
renderer journals. Declared witness points are not a measured person surface.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import types

NEW_RUN_ID = "ctrl-lcorr-s1-a4-5fps-v1-r004-d124-v1"
SOURCE_SHA256 = "466e6fbed500fa10899c0f5d0c659bd8d4a4400081e9c53d5834f41ecaa3809b"
ROUTE_PATH = "configs/q1q5/scripts/r004_a4_1_script_draft_v1.json"
FREEZE_PATH = "docs/engineering/R004_A4B4_SCRIPT_FREEZE_20261029.json"
METHOD_PATH = "scripts/check_r004_d92_static_projection.py"
PINS = {
    "catalog": "3eba8572e5a3992b5786cb56ded79a47f00bfc2b6d0ae74878e8f4176b4b899f",
    "geometry": "bed91c8bd56d113a4c6efe80877c05a5292f710145d6ef20b6ece69f97af988a",
    "route": "d304d0fcc17932e11dd54120fc06f88c96e28dbb07713c75e388e7664a4824a9",
    "freeze": "ab45a8322855dfa58bb26bf868554145240ff51653afa62f6efd800e09ad63fb",
    "method": "725eefabd58b7b809d114884ca79a135203aaa9af77c7f79e88847c7d20f92d7",
}
HEIGHTS = (0.0, 0.425, 0.85, 1.275, 1.5, 1.7, 1.9)
TIME_RANGE_S = (8.0, 11.0)
REQUIRED_T_V_S = 10.4
MINIMUM_AVAILABLE_BYTES = 8 * 1024**3


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def regular_bytes(path):
    path = Path(path)
    require(path.is_absolute() and path.resolve() == path and path.is_file(),
            "canonical regular input required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as stream:
        return stream.read()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    json.dumps(value, allow_nan=False)
    return value


def private_output(output, repo):
    output, repo = Path(output), Path(repo)
    require(output.is_absolute() and output.resolve() == output and not output.exists()
            and output.parent.is_dir() and output.suffix == ".json", "new canonical JSON output required")
    require("gt_private" in output.parts and not {"safe", "safe_static"}.intersection(output.parts)
            and not output.is_relative_to(repo), "report must stay outside repo in gt_private, never safe")
    return output


def require_output_space(output, reserve_bytes=0, *, disk_usage=shutil.disk_usage):
    require(disk_usage(Path(output).parent).free >= MINIMUM_AVAILABLE_BYTES + reserve_bytes,
            "STOP_BELOW_8_GIB")


def load_method(raw):
    module = types.ModuleType("_d124_pinned_d96_projection")
    exec(compile(raw, METHOD_PATH, "exec"), module.__dict__)
    return module


def static_reference(method, camera, triangles, points):
    """Same seven heights and 63-point declared cage as D96, with c1's clock."""
    origin = [camera["camera_to_world"][i][3] for i in range(3)]
    planes = method.make_shadow_planes(origin, triangles)
    rows = {
        str(height): method.visible_intervals(camera, triangles, points, height, planes,
                                               time_range_s=TIME_RANGE_S)
        for height in HEIGHTS
    }
    any_witness = method.merge([
        part for row in rows.values() for part in row["unoccluded_witness_intervals_s"]
    ])
    first = any_witness[0][0] if any_witness else None
    condition = ("UNKNOWN_NO_STATIC_WITNESS" if first is None else
                 "FAIL_ON_SELECTED_STATIC_REFERENCE" if first < REQUIRED_T_V_S else
                 "NOT_REFUTED_ON_SELECTED_STATIC_REFERENCE")
    samples = []
    for x in (-0.2, 0.0, 0.2):
        for y in (-0.2, 0.0, 0.2):
            for height in HEIGHTS:
                row = method.visible_intervals(camera, triangles, points, height, planes,
                                               time_range_s=TIME_RANGE_S, offset_xy=(x, y))
                samples.append({"offset_xy_m": [x, y], "height_m": height, **row})
    common = method.intersect_interval_sets(
        row["unoccluded_witness_intervals_s"] for row in samples)
    return {
        "camera_id": "CAM_W1", "by_witness_height_m": rows,
        "any_witness_intervals_s": any_witness, "first_static_witness_s": first,
        "required_t_V_earliest_s": REQUIRED_T_V_S, "selected_t_V_necessary_condition": condition,
        "declared_cage": {
            "role": "DECLARED_UPRIGHT_SAMPLE_CAGE_NOT_ACTOR_GEOMETRY",
            "width_xy_m": [0.4, 0.4], "height_m": 1.9, "sample_count": len(samples),
            "samples": samples, "all_sampled_witness_intervals_s": common,
            "full_cage_necessary_condition": "FAIL" if not common else "NOT_SUFFICIENT_FOR_PASS",
        },
    }


def audit(*, static_root, repo, new_run_id, producer_config, producer_config_sha256):
    repo, static_root = Path(repo), Path(static_root)
    require(repo.is_absolute() and repo.resolve() == repo and repo.is_dir(), "canonical repo required")
    require(static_root.is_absolute() and static_root.resolve() == static_root,
            "canonical static root required")
    require(new_run_id == NEW_RUN_ID, "D124 A4 new run required")
    paths = {"catalog": static_root / "safe_static/cameras.json",
             "geometry": static_root / "safe_static/static_geometry.PROPOSED.json",
             "route": repo / ROUTE_PATH, "freeze": repo / FREEZE_PATH,
             "method": repo / METHOD_PATH, "producer_config": Path(producer_config)}
    raw = {key: regular_bytes(path) for key, path in paths.items()}
    pins = {key: digest(value) for key, value in raw.items()}
    require(all(pins[key] == value for key, value in PINS.items()), "original input pin mismatch")
    require(pins["producer_config"] == producer_config_sha256, "producer config pin mismatch")
    catalog, geometry, route, freeze, config = (
        strict_json(raw[key]) for key in ("catalog", "geometry", "route", "freeze", "producer_config"))
    require(geometry["source_sha256"] == config["source_sha256"]
            == freeze["source_pins"]["source_sha256"] == SOURCE_SHA256, "source pin mismatch")
    require(config["freeze"] == {"path": FREEZE_PATH, "sha256": PINS["freeze"]}
            and config["catalog_sha256"] == freeze["source_pins"]["catalog_sha256"] == PINS["catalog"],
            "producer/freeze/catalog binding mismatch")
    run = config["runs"]["A4-1"]
    require(config["boundary"] == "PRIVATE_PRODUCER_ONLY_NEVER_INFERENCE_INPUT"
            and run["new_run_id"] == new_run_id and run["new_clock_id"]
            == "clock:r004:a4:declared-demo:v1:d124-v1", "producer run/clock boundary mismatch")
    require(config["render"]["fps"] == 5 and config["render"]["sample_interval_us"] == 200000
            and run["source_duration_us"] == 50000000 and run["sample_count_per_camera"] == 250,
            "D124 source grid changed")
    frozen = next(row for row in freeze["runs"] if row["scenario"] == "A4-1")
    require(frozen["producer_script"] == {"path": ROUTE_PATH, "sha256": PINS["route"]},
            "frozen route binding mismatch")
    waypoints = [row for row in route["planning_waypoints"]
                 if 8000000 <= row["planned_source_time_us"] <= 11000000]
    require([row["planned_source_time_us"] for row in waypoints]
            == [8000000, 8110731, 8155024, 11000000], "c1 declared control times changed")
    require(all(row["interpolation_to_next"] == "LINEAR_PROPOSED" for row in waypoints),
            "c1 planning interpolation changed")
    points = [row["foot_anchor_world_m"] for row in waypoints]
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    total = sum(lengths)
    require(total > 0, "nonempty c1 route required")
    distance = 0.0
    for row, length in zip(waypoints, lengths):
        expected = 8000000 + 3000000 * distance / total
        require(abs(row["planned_source_time_us"] - expected) <= 1.0,
                "D96 constant arc-speed reference differs from declared c1 times")
        distance += length
    cameras = [camera for camera in catalog["cameras"] if camera["camera_id"] == "CAM_W1"]
    require(len(cameras) == 1, "one pinned CAM_W1 calibration required")
    triangles = []
    for obj in geometry["objects"]:
        vertices = obj["vertices_world_m"]
        for face in obj["triangles_or_polygons"]:
            triangles.extend(tuple(vertices[i] for i in (face[0], face[k], face[k + 1]))
                             for k in range(1, len(face) - 1))
    result = static_reference(load_method(raw["method"]), cameras[0], triangles, points)
    require(all(digest(regular_bytes(paths[key])) == value for key, value in pins.items()),
            "input bytes changed during static check")
    return {
        "format": "D124_A4_C1_PRIVATE_STATIC_REFERENCE",
        "purpose": "PRIVATE_PRODUCER_EVALUATION_ONLY_NEVER_INFERENCE_INPUT",
        "new_run_id": new_run_id, "new_clock_id": run["new_clock_id"],
        "event_id": "A4-c1", "source_range_s": list(TIME_RANGE_S), "t_N_s": 11.0,
        "source_sha256": SOURCE_SHA256, "input_sha256": pins, "input_bytes_unchanged": True,
        "method": "PINHOLE_FRUSTUM_AND_ANALYTIC_STATIC_TRIANGLE_SHADOW_INTERVALS",
        "planning_role": "DECLARED_PLANNING_POLYLINE_NOT_MEASURED_ACTOR_TRACK",
        "points_world_m": points, "declared_control_times_us": [row["planned_source_time_us"] for row in waypoints],
        "reference_clock": "CONSTANT_ARC_SPEED_MATCHES_DECLARED_CONTROLS_WITHIN_ONE_MICROSECOND",
        "arc_length_m": total, "constant_arc_speed_m_s": total / 3.0,
        "triangle_count": len(triangles), "declared_witness_heights_m": list(HEIGHTS),
        "static_reference": result, "whole_body_visibility": "UNKNOWN",
        "detector_visibility": "UNKNOWN", "actual_t_V_s": None,
        "scoring_changed": False, "scoring_authority": "UNCHANGED_OWNER_DISPOSITION_REQUIRED",
        "collision": "UNKNOWN", "identity_verdict": "UNCONFIRMED",
        "rgb_read": False, "renderer_visibility_or_depth_read": False,
        "actor_track_read": False, "render_performed": False, "inference_performed": False,
        "limits": "Finite declared witnesses do not prove complete body surface visibility, actual sampled RGB appearance, detector observations or global route impossibility.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("static-root", "repo", "producer-config", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--new-run-id", required=True)
    parser.add_argument("--producer-config-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        output = private_output(args.output, args.repo)
        report = audit(static_root=args.static_root, repo=args.repo, new_run_id=args.new_run_id,
                       producer_config=args.producer_config,
                       producer_config_sha256=args.producer_config_sha256)
        raw = (json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
        require_output_space(output, len(raw))
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}))
        return 1
    print(json.dumps({"status": "PRIVATE_STATIC_REFERENCE_RECORDED",
                      "new_run_id": args.new_run_id,
                      "condition": report["static_reference"]["selected_t_V_necessary_condition"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
