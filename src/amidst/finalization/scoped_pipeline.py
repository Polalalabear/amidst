"""Isolated scoped orchestration; all inference precedes reference access."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from amidst.benchmark.baselines import BaselineUnavailableError
from amidst.domain.dataset import FrameSampleDataset
from amidst.domain.metric_config import MetricConfig
from amidst.domain.stream import ObservationAggregation
from amidst.finalization.formal_route_inventory import (
    InventoryBudget,
    WindingClassInventory,
    build_scoped_visibility_network,
    enumerate_visibility_route_classes,
)
from amidst.finalization.reviewed_collision import load_reviewed_collision_bundle
from amidst.finalization.reviewed_pipeline import (
    digest,
    freeze_inference,
    read_json,
    safe_artifact,
    write_json,
)
from amidst.finalization.reviewed_reference_movement import load_reference_movement_approval
from amidst.finalization.scoped_authority import ScopedUnionPhysicalProvider
from amidst.finalization.scoped_class_search import (
    ClassGenerationBudget,
    ScopedClassSearchResult,
    produce_scoped_class_candidates,
)
from amidst.finalization.scoped_evaluation import evaluate_scoped_run
from amidst.finalization.scoped_export import load_export_authority
from amidst.finalization.scoped_inference import (
    ScopedBaselineRun,
    ScopedInferenceConfig,
    ScopedNavigationGraph,
    bind_scoped_gaps,
    build_scoped_navigation,
    run_scoped_baseline,
)
from amidst.finalization.scoped_projection import ScopedSourceContext, project_scoped_observations
from amidst.finalization.scoped_visualization import ScopedDemoRecord, write_scoped_demo
from amidst.finalization.source_class_eligibility import (
    SourceClassEligibilityCertificate,
    certify_source_class_eligibility_intervals,
)
from amidst.observation.aggregation import aggregate_frames
from amidst.obstacle_volume_authority import content_sha256

METHODS = ("shortest_path", "geometry", "spatiotemporal")
ABLATIONS = (
    "remove_travel_time",
    "remove_collision",
    "remove_topology",
    "shortest_path_only",
    "full_deterministic_graph",
)


def validate_protocol(master: dict[str, Any], root: Path) -> None:
    """Keep the original protocol and the explicit direct-human addendum distinct."""
    if master.get("schema_version") != "phase1-scoped-case23-experiment-v1":
        raise ValueError("frozen scoped experiment definition required")
    cases = master.get("source_case_ids", [])
    if (
        not isinstance(cases, list)
        or len(cases) != len(set(cases))
        or not {"case2", "case3"}.issubset(cases)
    ):
        raise ValueError("complete unique frozen Case2/3 source case inventory required")
    if master.get("class_definition") != "FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST":
        raise ValueError("route K must use the independently frozen class definition")
    for relative, expected in master["protected_input_hashes"].items():
        if digest(safe_artifact(root, relative)) != expected:
            raise ValueError("protected scoped experiment input changed: " + relative)
    addendum = read_json(root / "configs/finalization/case2_interior_branch_addendum_v1.json")
    decision = read_json(root / "data/finalization/case23_scope_audit_20261014/human_approval.json")
    authority = ScopedInferenceConfig.model_validate(master["inference_config"]).authority
    if decision.get("decision") != "APPROVE" or (
        decision.get("addendum_content_sha256") != content_sha256(addendum)
        or addendum.get("parent_protocol_file_sha256")
        != digest(
            root / "configs/benchmarks/protocol_v1.json",
        )
        or addendum.get("all_other_protocol_gates_preserved") is not True
        or addendum.get("physical_scope_expanded") is not False
        or addendum.get("formal_case_readiness_granted") is not False
        or addendum.get("proposal_content_sha256") != authority.proposal_content_sha256
        or addendum.get("union_certificate_content_sha256") != authority.certificate_content_sha256
        or decision.get("source_sha256") != authority.pins.source_sha256
        or decision.get("scope_id") != addendum.get("scope_id")
        or decision.get("parent_protocol_file_sha256")
        != addendum.get("parent_protocol_file_sha256")
    ):
        raise ValueError("the scoped Case 2 definition lacks its exact human approval")
    for relative, expected in master["producer_hashes"].items():
        if digest(safe_artifact(root, relative)) != expected:
            raise ValueError("scoped producer changed after experiment freeze: " + relative)


def infer_scoped_dataset(
    dataset: Path,
    master_path: Path,
    output: Path,
    *,
    root: Path,
    reordered: bool = False,
    provider: ScopedUnionPhysicalProvider | None = None,
) -> dict[str, Any]:
    """Open only inference artifacts; evaluation/simulation paths stay unopened."""
    master = read_json(master_path)
    validate_protocol(master, root)
    config = ScopedInferenceConfig.model_validate(master["inference_config"])
    config_sha = content_sha256(config.model_dump(mode="json"))
    manifest = read_json(dataset / "manifest.json")
    if manifest.get("schema_version") != "phase1-scoped-source-dataset-v1" or (
        manifest.get("config_file_sha256") != config.fresh_export_config_sha256
        or manifest.get("full_experiment_config_file_sha256") != digest(master_path)
    ):
        raise ValueError("dataset differs from the new frozen source configuration")
    manifest_cases = [case["case_id"] for case in manifest.get("cases", [])]
    if sorted(manifest_cases) != sorted(master["source_case_ids"]):
        raise ValueError("dataset case population differs from complete frozen source inventory")
    for relative, expected in manifest.get("producer_hashes", {}).items():
        if master["producer_hashes"].get(relative) != expected:
            raise ValueError("dataset exporter differs from frozen producer: " + relative)
    for relative, expected in manifest["artifacts"].items():
        if (
            Path(relative).parts[0] == "inference"
            and digest(
                safe_artifact(dataset, relative),
            )
            != expected
        ):
            raise ValueError("source inference input changed: " + relative)
    if output.exists():
        raise FileExistsError("new inference output required")
    provider = provider or load_export_authority(root)
    if provider.source_sha256 != manifest["source_sha256"]:
        raise ValueError("source dataset differs from intact scoped authority")
    collision_binding = read_json(
        root / "configs/finalization/reviewed_case_inference_with_collision_v3.json",
    )["known_collision"]
    collisions = load_reviewed_collision_bundle(
        root / collision_binding["context_path"],
        repo_root=root,
        expected_manifest_sha256=collision_binding["physical_manifest_file_sha256"],
        expected_source_sha256=provider.source_sha256,
        contract=provider.contract,
        floor_ids=(provider.proposal.floor.floor_id,),
        local_certificate_content_sha256=provider.certificate_content_sha256,
        semantic_receipt_content_sha256=provider.semantic_review_content_sha256,
        scope_ids=tuple(collision_binding["scope_ids"]),
    )
    output.mkdir(parents=True)
    write_json(output / "config.json", config.model_dump(mode="json"))
    write_json(output / "experiment.json", master)
    write_json(output / "collision_authority.json", collisions.receipt())
    summaries: list[dict[str, Any]] = []
    for identity in sorted(row["case_id"] for row in manifest["cases"]):
        case_preprocessing_started = time.monotonic()
        directory = output / identity
        observed = (dataset / "inference" / identity / "observations.json").read_bytes()
        context = (dataset / "inference" / identity / "context.json").read_bytes()
        # Reorder only computational evidence, preserving the issued context/hash.
        # The projection adapter owns its original input-bound IDs. Geometry order
        # checks are performed separately instead of forging a file SHA here.
        projected = project_scoped_observations(observed, context, provider)
        if (
            projected.context.config_file_sha256 != config.fresh_export_config_sha256
            or projected.context.export_lock_file_sha256 != manifest.get("export_lock_file_sha256")
            or projected.context.authority != config.authority
        ):
            raise ValueError("source context differs from frozen config/export lock/authority")
        frames = projected.frames
        samples = tuple(reversed(frames.samples)) if reordered else frames.samples
        aggregation: ObservationAggregation = aggregate_frames(samples, config.aggregation_policy)
        write_json(directory / "projection.json", projected.sidecar)
        write_json(directory / "frames.json", frames.model_dump(mode="json"))
        write_json(directory / "aggregation.json", aggregation.model_dump(mode="json"))
        write_json(directory / "scoped_context.json", projected.context.model_dump(mode="json"))
        gaps = bind_scoped_gaps(
            aggregation,
            provider,
            config,
            expected_stream_binding=projected.computation_context.binding,
            projection_sidecar=projected.sidecar,
            projection_observations_sha256=hashlib.sha256(observed).hexdigest(),
        )
        native = {sample.sample_id: sample for sample in projected.native_frames.samples}
        offsets = {
            b.camera.camera_id: b.landmark_offset_bu[2] for b in projected.context.camera_bindings
        }
        preprocessing_runtime = time.monotonic() - case_preprocessing_started
        navigation_runtime = 0.0
        variant_runtimes: dict[str, list[float]] = {}
        case_records: list[dict[str, Any]] = []
        for ordinal, gap in enumerate(gaps):
            gap_dir = directory / f"gap{ordinal:02d}"
            endpoints = []
            for bound, sample_id in (
                (gap.start, gap.start.sample_ids[-1]),
                (gap.end, gap.end.sample_ids[0]),
            ):
                point = native[sample_id].projected_point
                if point is None:
                    raise ValueError("actual observed endpoint lacks its retained projection")
                p = point.world_position
                endpoints.append((p[0], p[1], p[2] - offsets[bound.observation.camera_id]))
            navigation_started = time.monotonic()
            navigation = build_scoped_navigation(
                gap,
                provider,
                config,
                endpoint_positions_bu=(endpoints[0], endpoints[1]),
            )
            network, source_edges = build_scoped_visibility_network(
                provider,
                expected_binding=config.authority,
                start_bu=endpoints[0],
                end_bu=endpoints[1],
                camera_ids=(gap.start.observation.camera_id,),
                spatial_context_id=navigation.graph.spatial_context_id,
            )
            if network.navigation.config != navigation.graph or source_edges != (
                navigation.source_edge_polylines_bu
            ):
                raise ValueError("public source visibility mapping differs between consumers")
            navigation_runtime += time.monotonic() - navigation_started
            write_json(gap_dir / "gap.json", gap.model_dump(mode="json"))
            write_json(gap_dir / "navigation.json", navigation.model_dump(mode="json"))
            raw = run_scoped_baseline(
                gap,
                navigation,
                "spatiotemporal",
                aggregation=aggregation,
                provider=provider,
                config=config,
                frozen_config_sha256=config_sha,
                collision_bundle=collisions,
                projection_sidecar=projected.sidecar,
                projection_observations_sha256=hashlib.sha256(observed).hexdigest(),
            )
            write_json(gap_dir / "raw_visibility_graph.json", raw.model_dump(mode="json"))
            results: list[dict[str, Any]] = []
            inventory_cache: dict[bool, Any] = {}
            eligibility_cache: dict[bool, SourceClassEligibilityCertificate] = {}
            variants = [(method, None) for method in METHODS] + [
                ("spatiotemporal", ablation) for ablation in ABLATIONS
            ]
            for method, ablation in variants:
                variant = ablation or method
                travel = method == "spatiotemporal" and ablation != "remove_travel_time"
                begun = time.monotonic()
                inference_runtime: float | None = None
                try:
                    production = produce_scoped_class_candidates(
                        provider,
                        network,
                        navigation.source_edge_polylines_bu,
                        expected_binding=config.authority,
                        start_bu=endpoints[0],
                        end_bu=endpoints[1],
                        camera_id=gap.start.observation.camera_id,
                        gap_duration_s=gap.end.observation.start_time
                        - gap.start.observation.end_time,
                        movement=config.movement,
                        policy=config.search_policy,
                        travel_time_filter=travel,
                        generation_budget=ClassGenerationBudget.model_validate(
                            master["class_generation_budget"],
                        ),
                    )
                    run = run_scoped_baseline(
                        gap,
                        navigation,
                        method,
                        aggregation=aggregation,
                        provider=provider,
                        config=config,
                        frozen_config_sha256=config_sha,
                        ablation_id=ablation,
                        collision_bundle=collisions,
                        class_candidates=production,
                        projection_sidecar=projected.sidecar,
                        projection_observations_sha256=hashlib.sha256(observed).hexdigest(),
                    )
                    inference_runtime = time.monotonic() - begun
                    inventory = inventory_cache.get(travel)
                    if inventory is None:
                        inventory = enumerate_visibility_route_classes(
                            provider,
                            network,
                            navigation.source_edge_polylines_bu,
                            expected_binding=config.authority,
                            start_bu=endpoints[0],
                            end_bu=endpoints[1],
                            camera_id=gap.start.observation.camera_id,
                            gap_duration_s=gap.end.observation.start_time
                            - gap.start.observation.end_time,
                            movement=config.movement,
                            policy=config.search_policy,
                            travel_time_filter=travel,
                            budget=InventoryBudget.model_validate(master["inventory_budget"]),
                        )
                        inventory_cache[travel] = inventory
                    eligibility = eligibility_cache.get(travel)
                    if eligibility is None:
                        eligibility = certify_source_class_eligibility_intervals(
                            provider,
                            network,
                            navigation.source_edge_polylines_bu,
                            expected_binding=config.authority,
                            start_bu=endpoints[0],
                            end_bu=endpoints[1],
                            camera_id=gap.start.observation.camera_id,
                            gap_duration_s=gap.end.observation.start_time
                            - gap.start.observation.end_time,
                            movement=config.movement,
                            policy=config.search_policy,
                            travel_time_filter=travel,
                            budget=InventoryBudget.model_validate(master["inventory_budget"]),
                        )
                        eligibility_cache[travel] = eligibility
                    write_json(
                        gap_dir / variant / "source_eligibility.json",
                        eligibility.model_dump(mode="json"),
                    )
                    write_json(gap_dir / variant / "run.json", run.model_dump(mode="json"))
                    write_json(
                        gap_dir / variant / "inventory.json", inventory.model_dump(mode="json")
                    )
                    write_json(
                        gap_dir / variant / "production.json", production.model_dump(mode="json")
                    )
                    results.append(
                        {
                            "variant": variant,
                            "status": "EXECUTED",
                            "candidate_count": len(run.geometric_result.routes),
                            "timed_candidate_count": len(run.event.candidates),
                            "termination_reason": str(run.event.termination_reason),
                            "generation_complete": production.complete,
                            "inventory_complete": inventory.complete,
                        }
                    )
                except BaselineUnavailableError as error:
                    record = {"variant": variant, "status": "N/A", "reason": str(error)}
                    write_json(gap_dir / variant / "unavailable.json", record)
                    results.append(record)
                if inference_runtime is not None:
                    variant_runtimes.setdefault(variant, []).append(inference_runtime)
                write_json(
                    gap_dir / variant / "runtime.json",
                    {
                        "inference_runtime_s": inference_runtime,
                        "measurement_boundary": "PRODUCTION_CLASS_SEARCH_AND_CORE_INFERENCE_ONLY",
                        "independent_inventory_or_evaluation_included": False,
                    },
                )
            case_records.append(
                {
                    "gap_directory": gap_dir.name,
                    "gap_id": gap.gap_id,
                    "time_range": [gap.start.observation.end_time, gap.end.observation.start_time],
                    "variants": results,
                }
            )
        write_json(
            directory / "runtime.json",
            {
                "case_id": identity,
                "shared_projection_aggregation_binding_runtime_s": preprocessing_runtime,
                "shared_source_navigation_runtime_s": navigation_runtime,
                "case_inference_runtime_s_by_variant": {
                    variant: preprocessing_runtime + navigation_runtime + sum(values)
                    for variant, values in variant_runtimes.items()
                },
                "measurement_boundary": (
                    "EXCLUSIVE_COMMON_PREPROCESSING_PLUS_VARIANT_GAP_INFERENCE_ONCE"
                ),
                "independent_inventory_evaluation_reporting_included": False,
                "shared_work_attributed_once_to_each_independently_comparable_variant": True,
                "whole_run_authority_regeneration_not_included": True,
            },
        )
        summaries.append(
            {
                "case_id": identity,
                "gap_count": len(gaps),
                "gaps": case_records,
                "all_source_recoveries_retained": True,
            }
        )
    summary = {
        "schema_version": "phase1-scoped-inference-summary-v1",
        "status": "SCOPED_INFERENCE_COMPLETE_EVALUATION_PENDING",
        "ground_truth_read": False,
        "cases": summaries,
    }
    write_json(output / "summary.json", summary)
    freeze_inference(
        output,
        dataset_manifest_sha256=digest(dataset / "manifest.json"),
        config_sha256=digest(master_path),
    )
    return summary


def _scoped_table_rows(
    case_id: str, gap_id: str, variant: str, result: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = []
    for k in (1, 2, 3):
        at_k = result.get("metrics_at_k", {}).get(str(k), {})
        rows.append(
            {
                "case_id": case_id,
                "gap_id": gap_id,
                "method_id": variant,
                "k": k,
                "status": result["status"],
                "result_type": result.get("result_type", "N/A"),
                "ade_m": result.get("ade_m"),
                "fde_m": result.get("fde_m"),
                "min_ade_at_k_m": at_k.get("min_ade_at_k_m"),
                "min_fde_at_k_m": at_k.get("min_fde_at_k_m"),
                "coverage_at_k": at_k.get("coverage_at_k"),
                "candidate_count": result.get("candidate_count"),
                "timed_candidate_count": result.get("timed_candidate_count"),
                "timing_unavailable_route_count": result.get("timing_unavailable_route_count"),
                "timing_hypothesis_count": result.get("timing_hypothesis_count"),
                "feasible_candidate_recall": result.get("feasible_candidate_recall"),
                "candidate_recall_numerator": result.get("feasible_candidate_recall_numerator"),
                "candidate_recall_denominator": result.get("feasible_candidate_recall_denominator"),
                "candidate_recall_status": result.get("feasible_candidate_recall_status"),
                "collision_rate": result.get("collision_rate"),
                "constraint_violation_rate": result.get("constraint_violation_rate"),
                "impossible_transition_rate": result.get("impossible_transition_rate"),
                "transition_count": result.get("transition_count"),
                "transition_status": result.get("impossible_transition_status"),
                "source_bound_hold_relation_invalid_rate": result.get(
                    "source_bound_hold_relation_invalid_rate"
                ),
                "projection_error_m": result.get("projection_error_m"),
                "path_length_error_m": result.get("path_length_error_m"),
                "travel_time_error_s": result.get("travel_time_error_s"),
                "search_nodes": result.get("search_nodes"),
                "termination_reason": result.get("termination_reason"),
                "gap_inference_runtime_s": result.get("runtime_s"),
                "case_inference_runtime_s": result.get("case_inference_runtime_s"),
                "runtime_repeated_for_k_only_do_not_sum": True,
                "blockers": result.get("reason", ""),
            }
        )
    return rows


def _scoped_plots(measurements: list[dict[str, Any]], output: Path) -> dict[str, Any]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output.mkdir(parents=True)
    artifacts = []
    skips = []
    metric_units = {
        "projection_error_m": "m",
        "ade_m": "m",
        "fde_m": "m",
        "path_length_error_m": "m",
        "travel_time_error_s": "s",
        "candidate_count": "distinct routes",
        "feasible_candidate_recall": "fraction",
        "source_eligible_class_count": "source classes",
        "collision_rate": "fraction",
        "constraint_violation_rate": "fraction",
        "impossible_transition_rate": "fraction",
        "source_bound_hold_relation_invalid_rate": "fraction",
        "runtime_s": "s (gap inference)",
        "case_inference_runtime_s": "s (case inference, once)",
        "search_nodes": "expanded states",
        "min_ade_at_k_m": "m",
        "min_fde_at_k_m": "m",
        "coverage_at_k": "fraction",
    }
    for metric, unit in metric_units.items():
        fig, ax = plt.subplots(figsize=(12, 5), constrained_layout=True)
        available = False
        for variant in dict.fromkeys(m["variant"] for m in measurements):
            selected = [m for m in measurements if m["variant"] == variant]
            labels = [m["case_id"] + "/" + m["gap_id"] for m in selected]
            k_values = (
                (1, 2, 3)
                if metric in ("min_ade_at_k_m", "min_fde_at_k_m", "coverage_at_k")
                else (None,)
            )
            for k in k_values:
                values = [
                    m.get(metric) if k is None else m["metrics_at_k"].get(str(k), {}).get(metric)
                    for m in selected
                ]
                if any(value is not None for value in values):
                    available = True
                    ax.plot(
                        labels,
                        [float("nan") if value is None else value for value in values],
                        marker="o",
                        label=variant + ("" if k is None else f" K={k}"),
                    )
        if not available:
            skips.append({"metric": metric, "reason": "N/A_NO_MEASURED_POPULATION_VALUES"})
            plt.close(fig)
            continue
        ax.set(title=metric, ylabel=unit)
        ax.tick_params(axis="x", rotation=35)
        ax.legend(fontsize=7, bbox_to_anchor=(1.02, 1), loc="upper left")
        for suffix in ("png", "pdf"):
            path = output / (metric + "." + suffix)
            fig.savefig(
                path,
                dpi=160,
                metadata={"CreationDate": None, "ModDate": None} if suffix == "pdf" else None,
            )
            artifacts.append({"file": path.name, "sha256": digest(path)})
        plt.close(fig)
    from collections import Counter

    counts = Counter(m["termination_reason"] for m in measurements)
    fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
    ax.bar(list(counts), list(counts.values()))
    ax.set(title="termination_reason", ylabel="Executed variant-gap runs (K not repeated)")
    for suffix in ("png", "pdf"):
        path = output / ("termination_reason." + suffix)
        fig.savefig(
            path,
            dpi=160,
            metadata={"CreationDate": None, "ModDate": None} if suffix == "pdf" else None,
        )
        artifacts.append({"file": path.name, "sha256": digest(path)})
    plt.close(fig)
    receipt = {
        "artifacts": artifacts,
        "skipped": skips,
        "population": "VARIANT_PER_ACTUAL_GAP_NO_DUPLICATED_RUNTIME_K",
        "evaluation_only": True,
        "layout": "INDIVIDUAL_CHART_PER_METRIC_NO_SUBPLOT_COLLAGE",
    }
    write_json(output / "receipt.json", receipt)
    return receipt


def evaluate_scoped_dataset(
    dataset: Path,
    inference: Path,
    output: Path,
    *,
    root: Path,
    provider: ScopedUnionPhysicalProvider | None = None,
) -> dict[str, Any]:
    """Freeze and verify all predictions, then open evaluation-only references."""
    from amidst.finalization.reviewed_pipeline import (
        require_inference_freeze,
        write_benchmark_tables,
    )

    freeze = require_inference_freeze(inference)
    master = read_json(inference / "experiment.json")
    validate_protocol(master, root)
    manifest = read_json(dataset / "manifest.json")
    if freeze["dataset_manifest_sha256"] != digest(dataset / "manifest.json"):
        raise ValueError("reference dataset manifest differs from frozen inference")
    config = ScopedInferenceConfig.model_validate(read_json(inference / "config.json"))
    metrics = MetricConfig.model_validate(master["metric_config"])
    provider = provider or load_export_authority(root)
    collision_binding = read_json(
        root / "configs/finalization/reviewed_case_inference_with_collision_v3.json"
    )["known_collision"]
    collisions = load_reviewed_collision_bundle(
        root / collision_binding["context_path"],
        repo_root=root,
        expected_manifest_sha256=collision_binding["physical_manifest_file_sha256"],
        expected_source_sha256=provider.source_sha256,
        contract=provider.contract,
        floor_ids=(provider.proposal.floor.floor_id,),
        local_certificate_content_sha256=provider.certificate_content_sha256,
        semantic_receipt_content_sha256=provider.semantic_review_content_sha256,
        scope_ids=tuple(collision_binding["scope_ids"]),
    )
    original = read_json(root / "configs/finalization/reviewed_case_export_with_movement_v2.json")
    approval = load_reference_movement_approval(
        root / original["reference_movement_approval_receipt_path"],
        root / original["reference_movement_policy_path"],
        expected_receipt_content_sha256=original[
            "reference_movement_approval_receipt_content_sha256"
        ],
        expected_source_sha256=provider.source_sha256,
        expected_protocol_sha256=provider.certificate.pins.protocol_sha256,
        expected_original_human_decisions_sha256=provider.certificate.pins.original_human_decisions_sha256,
    )
    if output.exists():
        raise FileExistsError("fresh scoped evaluation output required")
    output.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    measurements: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    demos: list[dict[str, Any]] = []
    summary = read_json(inference / "summary.json")
    if sorted(case["case_id"] for case in summary.get("cases", [])) != sorted(
        master["source_case_ids"]
    ):
        raise ValueError("inference case population differs from complete frozen source inventory")
    for case in summary["cases"]:
        identity = case["case_id"]
        directory = inference / identity
        sidecar = read_json(directory / "projection.json")
        frames = FrameSampleDataset.model_validate(read_json(directory / "frames.json"))
        aggregation = ObservationAggregation.model_validate(
            read_json(directory / "aggregation.json")
        )
        context = ScopedSourceContext.model_validate_json(
            (directory / "scoped_context.json").read_bytes()
        )
        demo_records = []
        primary_results = []
        case_runtime = read_json(directory / "runtime.json")
        for gap in case["gaps"]:
            gap_name = gap["gap_directory"]
            gap_dir = directory / gap_name
            nav = ScopedNavigationGraph.model_validate(read_json(gap_dir / "navigation.json"))
            for variant in gap["variants"]:
                name = variant["variant"]
                prefix = "/".join((identity, gap_name, name))
                if variant["status"] == "N/A":
                    result = read_json(gap_dir / name / "unavailable.json")
                else:
                    run = ScopedBaselineRun.model_validate(read_json(gap_dir / name / "run.json"))
                    inventory = WindingClassInventory.model_validate(
                        read_json(gap_dir / name / "inventory.json")
                    )
                    certificate = SourceClassEligibilityCertificate.model_validate(
                        read_json(gap_dir / name / "source_eligibility.json")
                    )

                    def load_reference(filename: str, case_id: str = identity) -> bytes:
                        relative = "/".join(("evaluation", case_id, filename))
                        path = safe_artifact(dataset, relative)
                        if digest(path) != manifest["artifacts"][relative]:
                            raise ValueError("evaluation reference changed: " + relative)
                        return path.read_bytes()

                    result = evaluate_scoped_run(
                        run,
                        lambda: load_reference("ground_truth.json"),
                        sidecar,
                        inventory,
                        metrics,
                        provider,
                        inference_directory=inference,
                        frozen_input_paths={
                            "run": prefix + "/run.json",
                            "inventory": prefix + "/inventory.json",
                            "source_eligibility": prefix + "/source_eligibility.json",
                            "projection": identity + "/projection.json",
                            "frames": identity + "/frames.json",
                            "navigation": identity + "/" + gap_name + "/navigation.json",
                            "config": "config.json",
                            "metrics": ("experiment.json", "metric_config"),
                        },
                        config=config,
                        navigation=nav,
                        frames=frames,
                        dataset_version=manifest["dataset_version"],
                        runtime_s=read_json(gap_dir / name / "runtime.json")["inference_runtime_s"],
                        collision_bundle=collisions,
                        annotations_loader=lambda: load_reference(
                            "reference_movement_annotations.json"
                        ),
                        reference_approval=approval,
                        source_eligibility=certificate,
                        seed=42,
                    )
                    result["case_inference_runtime_s"] = case_runtime[
                        "case_inference_runtime_s_by_variant"
                    ][name]
                    measurements.append(
                        dict(result, case_id=identity, gap_id=gap_name, variant=name)
                    )
                    if name == "spatiotemporal":
                        primary_results.append(result)
                        network, _ = build_scoped_visibility_network(
                            provider,
                            expected_binding=config.authority,
                            start_bu=nav.endpoint_positions_bu[0],
                            end_bu=nav.endpoint_positions_bu[1],
                            camera_ids=(run.gap_binding.start.observation.camera_id,),
                            spatial_context_id=nav.graph.spatial_context_id,
                        )
                        production = ScopedClassSearchResult.model_validate(
                            read_json(gap_dir / name / "production.json")
                        )
                        demo_records.append(
                            ScopedDemoRecord(aggregation, run, production, nav, context, network)
                        )
                write_json(output / "metrics" / identity / gap_name / (name + ".json"), result)
                rows.extend(_scoped_table_rows(identity, gap_name, name, result))
        blockers = []
        if not primary_results:
            blockers.append("NO_SOURCE_GAPS_EXECUTED")
        for index, result in enumerate(primary_results):
            required = (
                "ade_m",
                "fde_m",
                "projection_error_m",
                "path_length_error_m",
                "travel_time_error_s",
                "feasible_candidate_recall",
                "collision_rate",
                "constraint_violation_rate",
            )
            blockers.extend(
                f"gap{index:02d}:MISSING_{field.upper()}"
                for field in required
                if result.get(field) is None
            )
            if result.get("collision_rate") != 0 or result.get("constraint_violation_rate") != 0:
                blockers.append(f"gap{index:02d}:PHYSICAL_VIOLATIONS_OR_UNKNOWN")
            if result.get("source_bound_hold_relation_invalid_rate") != 0:
                blockers.append(f"gap{index:02d}:INVALID_SOURCE_HOLD")
            if not result.get("search_complete"):
                blockers.append(f"gap{index:02d}:INCOMPLETE_SEARCH")
            if any(
                result["metrics_at_k"].get(str(k), {}).get(field) is None
                for k in (1, 2, 3)
                for field in ("min_ade_at_k_m", "min_fde_at_k_m", "coverage_at_k")
            ):
                blockers.append(f"gap{index:02d}:REQUIRED_K_METRICS_NOT_EVALUATED")
            if (
                identity == "case2"
                and result["metrics_at_k"].get("3", {}).get("coverage_at_k") != 1
            ):
                blockers.append(f"gap{index:02d}:CASE2_REFERENCE_COMPATIBLE_ROUTE_MISSING_AT_K3")
            if identity == "case3" and (result.get("fde_m") is None or result["fde_m"] > 1.0):
                blockers.append(f"gap{index:02d}:CASE3_FDE_TARGET_NOT_MET")
        if identity == "case2" and not any(
            r["candidate_count"] >= 2 and r["source_eligible_class_count"] >= 2
            for r in primary_results
        ):
            blockers.append("CASE2_TWO_DISTINCT_SOURCE_CLASSES_NOT_DEMONSTRATED")
        cases.append(
            {
                "case_id": identity,
                "status": "PASS" if not blockers else "BLOCKED",
                "blockers": blockers,
                "gap_count": len(primary_results),
                "candidate_counts": [r["candidate_count"] for r in primary_results],
                "gap_durations_s": [g["time_range"][1] - g["time_range"][0] for g in case["gaps"]],
                "actual_handoff_count": 0,
                "impossible_transition_rate": None,
                "transition_status": "N/A_NO_DECLARED_CAMERA_OR_FLOOR_TRANSITIONS",
            }
        )
        if demo_records and identity in {"case2", "case3"}:
            demos.append(
                write_scoped_demo(
                    demo_records, provider, output / "demos" / identity, case_id=identity
                )
            )
    write_benchmark_tables(output, rows)
    charts = _scoped_plots(measurements, output / "charts")
    result = {
        "schema_version": "phase1-scoped-evaluation-summary-v1",
        "status": "SCOPED_CASE23_VALIDATED"
        if all(c["status"] == "PASS" for c in cases)
        else "SCOPED_CASE23_BLOCKED",
        "source_sha256": provider.source_sha256,
        "dataset_version": manifest["dataset_version"],
        "dataset_manifest_file_sha256": digest(dataset / "manifest.json"),
        "inference_freeze_file_sha256": digest(inference / "inference_freeze.json"),
        "cases": cases,
        "demos": demos,
        "charts": charts,
        "benchmark_row_count": len(rows),
        "cross_case_coverage_at_3": None,
        "cross_case_coverage_status": (
            "N/A_CROSS_CASE_WEIGHTING_NOT_APPROVED_SEPARATE_GAP_VALUES_REPORTED"
        ),
        "original_protocol_preserved": True,
        "case2_addendum_content_sha256": content_sha256(
            read_json(root / "configs/finalization/case2_interior_branch_addendum_v1.json")
        ),
        "phase1_full_exit_granted": False,
    }
    write_json(output / "summary.json", result)
    return result
