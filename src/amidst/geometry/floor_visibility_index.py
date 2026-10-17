"""Bounded raster support for positive static-source visibility, not blind-area proof."""

from __future__ import annotations

import copy
import hashlib
from collections import Counter
from pathlib import Path

from shapely.geometry import box, shape
from shapely.prepared import prep

from amidst.engineering.registry import content_hash
from amidst.geometry.visibility_policy import cell_status


def build_visibility_index(
    rays,
    physical,
    *,
    ray_file_sha256,
    physical_file_sha256,
    run_parameters,
    calibration_sha256,
    floor_sha256,
):
    if rays["output_sha256"] != content_hash(
        {k: v for k, v in rays.items() if k != "output_sha256"}
    ):
        raise ValueError("RAY_OUTPUT_HASH_MISMATCH")
    if (
        rays["source_sha256"] != physical["source_sha256"]
        or rays["gt_read"] is not False
        or rays["renderer_visibility_read"] is not False
    ):
        raise ValueError("VISIBILITY_SOURCE_MISMATCH")
    config = rays["config"]
    grid = rays["sample_grid"]
    step = grid["step_m"]
    nx, ny = grid["nx"], grid["ny"]
    origin = grid["origin_m"]
    if (
        config["cell_size_m"] != 2 * step
        or run_parameters["target_proxy"]["height_m"] != config["height_m"]
        or run_parameters["body_radius_m"] != config["body_radius_m"]
    ):
        raise ValueError("VISIBILITY_RUN_PARAMETERS_MISMATCH")
    if config["probe_offsets_m"] != [
        config["floor_clearance_m"],
        config["floor_clearance_m"] + config["height_m"] / 2,
        config["floor_clearance_m"] + config["height_m"],
    ]:
        raise ValueError("VISIBILITY_PROBE_OFFSETS_MISMATCH")
    support = prep(shape(physical["floor"]["geometry"]))
    entries = []
    for camera in rays["cameras"]:
        codes = camera["sample_status_codes"]
        if len(codes) != nx * ny:
            raise ValueError("VISIBILITY_GRID_INCOMPLETE")
        polygons = []
        cell_codes = []
        counts = Counter()
        for ix in range(0, nx - 2, 2):
            for iy in range(0, ny - 2, 2):
                x, y = origin[0] + ix * step, origin[1] + iy * step
                cell = box(x, y, x + 2 * step, y + 2 * step)
                statuses = [
                    {0: "NOT_VISIBLE", 1: "VISIBLE", 2: "UNKNOWN"}[codes[(ix + a) * ny + iy + b]]
                    for a in range(3)
                    for b in range(3)
                ]
                status = (
                    cell_status(statuses)
                    if support.covers(cell)
                    else "UNKNOWN_OUTSIDE_SOURCE_FLOOR_SUPPORT"
                )
                counts[status] += 1
                cell_codes.append(
                    "V"
                    if status == "SAMPLED_VISIBLE"
                    else "U"
                    if status.startswith("UNKNOWN")
                    else "N"
                )
                if status == "SAMPLED_VISIBLE":
                    polygons.append(
                        [
                            [x, y],
                            [x + 2 * step, y],
                            [x + 2 * step, y + 2 * step],
                            [x, y + 2 * step],
                            [x, y],
                        ]
                    )
        entry = {
            "camera_id": camera["camera_id"],
            "visibility_ref": "visidx:"
            + content_hash({"camera": camera["camera_id"], "ray_sha": ray_file_sha256})[:24],
            "valid_time_range_s": config["valid_time_range_s"],
            "method": "SOURCE_MESH_RAYCAST",
            "floor_z_m": config["floor_z_m"],
            "polygons": polygons,
            "cell_size_m": config["cell_size_m"],
            "area_m2": len(polygons) * config["cell_size_m"] ** 2,
            "negative_evidence_eligible": True,
            "sampling": {
                "xy_samples_per_cell": 9,
                "probe_offsets_m": config["probe_offsets_m"],
                "definition": "ANY_PROBE_VISIBLE_AT_EACH_OF_NINE_XY_SAMPLES",
                "continuous_unsampled_visibility": "UNKNOWN",
                "cell_codes": " ".join(cell_codes),
                "cell_status_counts": dict(counts),
                "sample_grid": grid,
                "head_or_torso_only_visible_samples": camera["head_or_torso_only_visible_samples"],
            },
            "provenance": {
                "source_sha256": rays["source_sha256"],
                "safe_inputs_sha256": rays["safe_inputs_sha256"],
                "run_ref": config["run_id"],
                "clock_id": config["clock_id"],
                "run_parameters": copy.deepcopy(run_parameters),
                "calibration_sha256": calibration_sha256,
                "floor_sha256": floor_sha256,
                "physical_map_sha256": physical_file_sha256,
                "ray_file_sha256": ray_file_sha256,
                "config_sha256": rays["config_sha256"],
                "producer": "floor-visibility-index",
                "gt_read": False,
            },
        }
        entry["sha256"] = content_hash(entry)
        entries.append(entry)
    result = {
        "schema_version": "office-demo.floor-visibility-index.v1",
        "builder_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "export_producer_sha256": rays.get("producer_sha256"),
        "probe_policy_sha256": rays.get("policy_sha256"),
        "source_sha256": rays["source_sha256"],
        "run_id": config["run_id"],
        "clock_id": config["clock_id"],
        "safe_inputs_sha256": rays["safe_inputs_sha256"],
        "config": config,
        "entries": entries,
        "mesh_counts": rays["mesh_counts"],
        "authority": "BOUNDED_SAMPLED_VISIBILITY_NOT_GLOBAL_BLIND_AREA_PROOF",
        "gt_read": False,
        "annotations_as_occluders": False,
        "renderer_visibility_read": False,
    }
    result["output_sha256"] = content_hash(result)
    return result
