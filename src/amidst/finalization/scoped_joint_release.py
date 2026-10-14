"""Assemble fresh Case 1–3 child evidence without relabelling historical results."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from amidst.finalization.reviewed_pipeline import (
    digest,
    read_json,
    require_inference_freeze,
    write_benchmark_tables,
    write_json,
)
from amidst.finalization.scoped_protocol import (
    require_joint_inference_boundary,
    validate_master_bindings,
)


def freeze_joint_inference(release: Path, master_path: Path, *, root: Path) -> dict[str, Any]:
    master = read_json(master_path)
    validate_master_bindings(master, root)
    children = {}
    manifests = {}
    for role in ("office", "scoped"):
        directory = release / role / "inference_primary"
        frozen = require_inference_freeze(directory)
        manifest_path = release / role / "dataset/manifest.json"
        manifest = read_json(manifest_path)
        if frozen["dataset_manifest_sha256"] != digest(manifest_path) or (
            manifest["source_sha256"] != master["source_sha256"]
            or manifest["export_seed"] != master["export_seed"]
            or manifest["inference_seed"] != master["inference_seed"]
        ):
            raise ValueError("joint child dataset/freeze/source/seeds differ: " + role)
        children[role] = {
            "directory": str(directory.relative_to(release)),
            "freeze_file_sha256": digest(directory / "inference_freeze.json"),
        }
        manifests[role] = {
            "directory": str(manifest_path.parent.relative_to(release)),
            "manifest_file_sha256": digest(manifest_path),
            "dataset_version": manifest["dataset_version"],
        }
    path = release / "joint_inference_freeze.json"
    if path.exists():
        raise FileExistsError("new complete joint inference boundary required")
    document = {
        "schema_version": "phase1-joint-inference-freeze-v1",
        "status": "ALL_PRIMARY_CHILDREN_FROZEN_BEFORE_ANY_REFERENCE_EVALUATION",
        "ground_truth_read": False,
        "master_file_sha256": digest(master_path),
        "source_sha256": master["source_sha256"],
        "children": children,
        "datasets": manifests,
        "case_selection": master["joint_release_selection"],
    }
    write_json(path, document)
    require_joint_inference_boundary(path, master_path, release / "office/inference_primary")
    return document


def assemble_joint_release(release: Path, master_path: Path, *, root: Path) -> dict[str, Any]:
    """Keep per-case metrics and exact population limits; no overall weighted score."""
    master = read_json(master_path)
    validate_master_bindings(master, root)
    joint = require_joint_inference_boundary(
        release / "joint_inference_freeze.json", master_path, release / "office/inference_primary"
    )
    office = read_json(release / "office/evaluation/verification.json")
    scoped = read_json(release / "scoped/evaluation/summary.json")
    if (
        office.get("dataset_manifest_sha256") != joint["datasets"]["office"]["manifest_file_sha256"]
        or office.get("primary_inference_freeze_sha256")
        != joint["children"]["office"]["freeze_file_sha256"]
        or office.get("evaluation_inference_freeze_verified") is not True
    ):
        raise ValueError("office evaluation differs from the fresh joint child")
    scoped_manifest = read_json(
        release / joint["datasets"]["scoped"]["directory"] / "manifest.json"
    )
    if (
        scoped.get("dataset_manifest_file_sha256")
        != joint["datasets"]["scoped"]["manifest_file_sha256"]
        or scoped.get("inference_freeze_file_sha256")
        != joint["children"]["scoped"]["freeze_file_sha256"]
        or scoped.get("source_sha256") != master["source_sha256"]
        or scoped.get("dataset_version") != scoped_manifest["dataset_version"]
        or sorted(case["case_id"] for case in scoped.get("cases", []))
        != sorted(master["source_case_ids"])
    ):
        raise ValueError("scoped evaluation differs from the complete fresh joint child")
    office_case = office["measurements"].get("case1", {})
    blockers = []
    if set(office_case) != {"shortest_path", "geometry", "spatiotemporal"}:
        blockers.append("CASE1_MISSING_DECLARED_BASELINES")
    primary = office_case.get("spatiotemporal", {})
    for metric in (
        "ade_m",
        "fde_m",
        "projection_error_m",
        "feasible_candidate_recall",
        "collision_rate",
        "constraint_violation_rate",
        "impossible_transition_rate",
        "path_length_error_m",
        "travel_time_error_s",
        "inference_runtime_s",
        "expanded_states",
        "termination_reason",
    ):
        if primary.get(metric) is None:
            blockers.append("CASE1_MISSING_" + metric.upper())
    if any(
        primary.get("metrics_at_k", {}).get(str(k), {}).get(field) is None
        for k in (1, 2, 3)
        for field in ("min_ade_at_k_m", "min_fde_at_k_m", "coverage_at_k")
    ):
        blockers.append("CASE1_REQUIRED_K_METRICS_NOT_EVALUATED")
    for metric in ("ade_m", "fde_m"):
        if primary.get(metric) is not None and primary[metric] > 0.5:
            blockers.append("CASE1_INITIAL_TARGET_" + metric.upper())
    for metric in ("collision_rate", "constraint_violation_rate", "impossible_transition_rate"):
        if primary.get(metric) != 0:
            blockers.append("CASE1_INVALID_" + metric.upper())
    case_results = [
        {
            "case_id": "case1",
            "status": "PASS" if not blockers else "BLOCKED",
            "blockers": list(blockers),
            "authority_scope": "ORIGINAL_APPROVED_RESTRICTED_OFFICE",
        }
    ]
    case_results += [case for case in scoped["cases"] if case["case_id"] in {"case2", "case3"}]
    if {c["case_id"] for c in case_results} != {"case1", "case2", "case3"}:
        blockers.append("INCOMPLETE_JOINT_CASE1_3_POPULATION")
    for case in scoped["cases"]:
        if case["status"] != "PASS":
            blockers.append(case["case_id"] + ":CASE_STATUS_NOT_PASS")
        blockers += [case["case_id"] + ":" + b for b in case["blockers"]]
    if primary.get("candidate_count") != 1:
        blockers.append("CASE1_UNIQUE_ROUTE_NOT_PROVEN")
    office_rows = read_json(release / "office/evaluation/benchmark_table.json")["rows"]
    office_rows += read_json(release / "office/evaluation/ablations/benchmark_table.json")["rows"]
    selected_office = [
        dict(
            row,
            gap_id="ALL_CASE1_GAPS_ORIGINAL_AGGREGATION",
            child_dataset="office",
            child_original_status=row["status"],
        )
        for row in office_rows
        if row["case_id"] == "case1"
    ]
    selected_scoped = [
        dict(row, child_dataset="scoped", child_original_status=row["status"])
        for row in read_json(release / "scoped/evaluation/benchmark_table.json")["rows"]
    ]
    raw_rows = selected_office + selected_scoped
    fields = tuple(dict.fromkeys(key for row in raw_rows for key in row))
    rows = [{key: row.get(key) for key in fields} for row in raw_rows]
    write_benchmark_tables(release, rows)
    controls = {
        case["case_id"]: case
        for case in scoped["cases"]
        if case["case_id"] not in {"case2", "case3"}
    }
    main3 = next((c for c in scoped["cases"] if c["case_id"] == "case3"), None)
    short = controls.get("case3_short_control")
    long = controls.get("case3_long_stress")
    growth = {
        "main": main3,
        "short_control": short,
        "long_stress": long,
        "same_physical_bounds": True,
        "all_actual_recoveries_preserved": True,
        "different_schedules_do_not_imply_matched_gap_endpoints": True,
        "population_comparison": "SOURCE_RECIPE_FAMILY_WITH_SEPARATE_ACTUAL_GAP_ANCHORS",
        "plateau_allowed_at_FIXED_PATH_LENGTH_DETOUR_LIMIT": True,
        "frozen_actual_gap_queries": {
            case["case_id"]: [
                {
                    "gap_id": gap["gap_id"],
                    "time_range": gap["time_range"],
                    "endpoint_positions_bu": read_json(
                        release
                        / "scoped/inference_primary"
                        / case["case_id"]
                        / gap["gap_directory"]
                        / "navigation.json"
                    )["endpoint_positions_bu"],
                }
                for gap in case["gaps"]
            ]
            for case in read_json(release / "scoped/inference_primary/summary.json")["cases"]
            if case["case_id"].startswith("case3")
        },
    }
    if not main3 or not short or not long:
        blockers.append("CASE3_STRESS_FAMILY_NOT_EXECUTED")
    if main3 and not any(n >= 2 for n in main3["candidate_counts"]):
        blockers.append("CASE3_DETOUR_ALTERNATIVES_NOT_RETAINED")
    if (
        main3
        and short
        and not max(main3["candidate_counts"], default=0)
        > max(short["candidate_counts"], default=0)
    ):
        blockers.append("CASE3_NO_CANDIDATE_GROWTH_DEMONSTRATED")
    write_json(release / "case3_growth.json", growth)
    result = {
        "schema_version": "phase1-joint-formal-verification-v1",
        "status": "PHASE1_FINALIZATION_BLOCKED",
        "freeze_allowed": False,
        "formal_case_execution_complete": not blockers,
        "blockers": blockers,
        "cases": case_results,
        "master_file_sha256": digest(master_path),
        "joint_inference_freeze_file_sha256": digest(release / "joint_inference_freeze.json"),
        "source_sha256": joint["source_sha256"],
        "datasets": joint["datasets"],
        "child_results_preserved": {
            "office": "office/evaluation/verification.json",
            "scoped": "scoped/evaluation/summary.json",
        },
        "selected_case1_original_child_status": office["status"],
        "selected_case2_3_scoped_child_status": scoped["status"],
        "benchmark_rows": len(rows),
        "cross_case_overall_coverage": None,
        "cross_case_weighting_status": "UNAPPROVED_NO_OVERALL_TARGET_PASS_CLAIMED",
        "reproduction_status": "PENDING",
        "repository_validation_status": "PENDING",
        "formal_scope": "SOURCE_BOUND_OFFICE_AND_EXACT_SIX_CELL_UNION_ONLY",
        "same_camera_scoped_transition_rate_status": (
            "N/A_ZERO_DECLARED_TRANSITIONS_WITH_INDEPENDENT_HOLD_VALIDATION"
        ),
        "school_surface_authority": "NOT_CERTIFIED",
        "case4_status": "DEFERRED",
        "phase2_modified": False,
        "historical_child_statuses_rewritten": False,
    }
    write_json(release / "verification.json", result)
    return result
