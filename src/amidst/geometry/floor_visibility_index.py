"""Bounded raster support for positive static-source visibility, not blind-area proof."""

from __future__ import annotations

import copy
import hashlib
from collections import Counter
from pathlib import Path

from shapely.geometry import box, shape
from shapely.prepared import prep

from amidst.engineering.registry import content_hash
from amidst.geometry.visibility_policy import cell_status, predicted_leg_area_px, sample_status


def build_visibility_index(
    rays,
    physical,
    *,
    ray_file_sha256,
    physical_file_sha256,
    run_parameters,
    calibration_sha256,
    floor_sha256,
    calibrations,
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
    if grid.get("order") != "X_MAJOR_Y_MINOR":
        raise ValueError("VISIBILITY_GRID_ORDER_MISMATCH")
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
    if calibration_sha256 != content_hash(list(calibrations.values())):
        raise ValueError("VISIBILITY_CALIBRATION_HASH_MISMATCH")
    rule = config["visibility_rule"]
    if rule not in {"ANY_PROBE_VISIBLE", "FOOT_AND_TORSO_PROBES_VISIBLE"}:
        raise ValueError("VISIBILITY_RULE_UNSUPPORTED")
    detector = config["detector"]
    factor = config.get("detectability_factor", 4)
    if (
        type(factor) not in (int, float)
        or not 0 < factor < float("inf")
        or type(detector.get("min_pixels")) is not int
        or detector["min_pixels"] <= 0
        or type(detector.get("difference_threshold")) is not int
        or not 0 <= detector["difference_threshold"] <= 255
        or not all(
            isinstance(detector.get(k), str) and detector[k] for k in ("producer", "version")
        )
    ):
        raise ValueError("VISIBILITY_DETECTOR_CONFIG_INVALID")
    required = factor * detector["min_pixels"]
    support = prep(shape(physical["floor"]["geometry"]))
    entries = []
    for camera in rays["cameras"]:
        codes = camera["sample_status_codes"]
        if len(codes) != nx * ny:
            raise ValueError("VISIBILITY_GRID_INCOMPLETE")
        probes = camera["probe_status_codes"]
        if camera["probe_order"] != ["foot", "waist", "head"]:
            raise ValueError("VISIBILITY_PROBE_ORDER_MISMATCH")
        legend = {0: "OCCLUDED", 1: "VISIBLE", 2: "UNKNOWN", 3: "OUTSIDE_FOV", 4: "CLIPPED"}
        if len(probes) != nx * ny or any(
            len(p) != 3 or any(type(c) is not int or c not in legend for c in p) for p in probes
        ):
            raise ValueError("VISIBILITY_PROBE_GRID_INCOMPLETE")
        decoded = [[legend[c] for c in p] for p in probes]
        if any(
            codes[i]
            != {"NOT_VISIBLE": 0, "VISIBLE": 1, "UNKNOWN": 2}[sample_status(p, "ANY_PROBE_VISIBLE")]
            for i, p in enumerate(decoded)
        ):
            raise ValueError("VISIBILITY_SAMPLE_PROBE_MISMATCH")
        combinations = Counter("".join("1" if c == 1 else "0" for c in p) for p in probes)
        declared_counts = camera["probe_visible_counts"]
        if any(declared_counts.get(f"{i:03b}", 0) != combinations[f"{i:03b}"] for i in range(8)):
            raise ValueError("VISIBILITY_PROBE_COUNTS_MISMATCH")
        areas = [
            predicted_leg_area_px(
                calibrations[camera["camera_id"]],
                [origin[0] + ix * step, origin[1] + iy * step],
                config["floor_z_m"],
                *config["probe_offsets_m"][:2],
                config["body_radius_m"],
            )
            for ix in range(nx)
            for iy in range(ny)
        ]
        polygons, suggestions, cell_codes, min_areas, admitted_areas = [], [], [], [], []
        counts = {r: Counter() for r in ("ANY_PROBE_VISIBLE", "FOOT_AND_TORSO_PROBES_VISIBLE")}
        removed = Counter(visibility_rule=0, detectability=0)
        for ix in range(0, nx - 2, 2):
            for iy in range(0, ny - 2, 2):
                x, y = origin[0] + ix * step, origin[1] + iy * step
                cell = box(x, y, x + 2 * step, y + 2 * step)
                indices = [(ix + a) * ny + iy + b for a in range(3) for b in range(3)]
                supported = support.covers(cell)
                status_by_rule = {
                    r: cell_status([sample_status(decoded[i], r) for i in indices])
                    if supported
                    else "UNKNOWN_OUTSIDE_SOURCE_FLOOR_SUPPORT"
                    for r in counts
                }
                minimum = min(areas[i] for i in indices)
                min_areas.append(minimum)
                any_visible = status_by_rule["ANY_PROBE_VISIBLE"] == "SAMPLED_VISIBLE"
                strict_visible = (
                    status_by_rule["FOOT_AND_TORSO_PROBES_VISIBLE"] == "SAMPLED_VISIBLE"
                )
                ring = [
                    [x, y],
                    [x + 2 * step, y],
                    [x + 2 * step, y + 2 * step],
                    [x, y + 2 * step],
                    [x, y],
                ]
                if any_visible:
                    suggestions.append(ring)
                    if not strict_visible:
                        removed["visibility_rule"] += 1
                    elif minimum < required:
                        removed["detectability"] += 1
                if strict_visible and minimum < required:
                    status_by_rule["FOOT_AND_TORSO_PROBES_VISIBLE"] = (
                        "UNKNOWN_BELOW_DETECTABILITY_THRESHOLD"
                    )
                for r, status in status_by_rule.items():
                    counts[r][status] += 1
                status = status_by_rule[rule]
                cell_codes.append(
                    "V"
                    if status == "SAMPLED_VISIBLE"
                    else "U"
                    if status.startswith("UNKNOWN")
                    else "N"
                )
                # ANY is a suggestion rule; it can never populate negative evidence.
                if rule == "FOOT_AND_TORSO_PROBES_VISIBLE" and status == "SAMPLED_VISIBLE":
                    polygons.append(ring)
                    admitted_areas.append(minimum)
        entry = {
            "camera_id": camera["camera_id"],
            "visibility_ref": "visidx:"
            + content_hash({"camera": camera["camera_id"], "ray_sha": ray_file_sha256})[:24],
            "valid_time_range_s": config["valid_time_range_s"],
            "method": "SOURCE_MESH_RAYCAST",
            "floor_z_m": config["floor_z_m"],
            "polygons": polygons,
            "suggestion_polygons": suggestions,
            "suggestion_area_m2": len(suggestions) * config["cell_size_m"] ** 2,
            "visibility_rule": rule,
            "detectability": {
                "min_predicted_px": min(admitted_areas) if admitted_areas else None,
                "required_px": required,
                "detectability_factor": factor,
                "detector": copy.deepcopy(detector),
                "projection_basis": "CAMERA_FACING_VERTICAL_FOOT_TO_WAIST_QUADRILATERAL_AREA",
            },
            "cells_removed": dict(removed) | {"total": len(suggestions) - len(polygons)},
            "cell_size_m": config["cell_size_m"],
            "area_m2": len(polygons) * config["cell_size_m"] ** 2,
            "negative_evidence_eligible": rule == "FOOT_AND_TORSO_PROBES_VISIBLE",
            "sampling": {
                "xy_samples_per_cell": 9,
                "probe_offsets_m": config["probe_offsets_m"],
                "definition": "ALL_NINE_XY_SAMPLES_UNDER_DECLARED_RULE_AND_DETECTABILITY",
                "continuous_unsampled_visibility": "UNKNOWN",
                "cell_codes": " ".join(cell_codes),
                "cell_status_counts": {r: dict(c) for r, c in counts.items()},
                "cell_min_predicted_px": min_areas,
                "probe_status_codes": probes,
                "probe_order": camera["probe_order"],
                "probe_visible_counts": declared_counts,
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
