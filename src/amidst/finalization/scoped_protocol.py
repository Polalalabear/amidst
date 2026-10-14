"""Build the joint Phase 1 definition before source export, without self hashing.

Original office settings supply the common research budget and metric profile.
The scoped union has a separate explicit human definition and intact authority.
The office child retains its original blocked/local statuses; a joint release
selects only its fresh Case 1 and the independently executed scoped Cases 2/3.
"""

from __future__ import annotations

import ast
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amidst.domain.metric_config import MetricConfig
from amidst.domain.stream import AggregationPolicy
from amidst.finalization.formal_route_inventory import InventoryBudget
from amidst.finalization.reviewed_authority import load_reviewed_authority, reviewed_metric_config
from amidst.finalization.reviewed_collision_lock import load_reviewed_collision_lock
from amidst.finalization.reviewed_pipeline import (
    digest,
    evaluate_dataset,
    fresh_process_inference,
    read_json,
    require_inference_freeze,
    safe_artifact,
    verify_reproduction,
    write_json,
)
from amidst.finalization.route_inventory import ReviewedCaseInferenceConfig
from amidst.finalization.scoped_authority import ScopedUnionPhysicalProvider
from amidst.finalization.scoped_class_search import ClassGenerationBudget
from amidst.finalization.scoped_export import load_export_authority, validate_recipes
from amidst.finalization.scoped_inference import (
    ScopedBudgetLineage,
    ScopedInferenceConfig,
    validate_scoped_inference_config,
)
from amidst.finalization.scoped_pipeline import validate_protocol
from amidst.finalization.scoped_route_inventory import ScopedRouteAuthorityBinding
from amidst.obstacle_volume_authority import content_sha256

OFFICE_APPLICATION = "data/finalization/human_review_applied_v1"
OFFICE_EXPORT_CONFIG = "configs/finalization/reviewed_case_export_with_movement_v2.json"
OFFICE_INFERENCE_CONFIG = "configs/finalization/reviewed_case_inference_with_collision_v3.json"
CLASS_DEFINITION = "FIXED_ENDPOINT_INTEGER_WINDING_CANONICAL_SHORTEST"


def config_from_original_parent(
    provider: ScopedUnionPhysicalProvider,
    parent: ReviewedCaseInferenceConfig,
    fresh_export_config_sha256: str,
) -> ScopedInferenceConfig:
    """Carry every original research setting unchanged into the new source scope."""
    parent = ReviewedCaseInferenceConfig.model_validate_json(parent.model_dump_json())
    cert = provider.certificate
    if parent.source_sha256 != provider.source_sha256 or (
        parent.protocol_sha256 != cert.pins.protocol_sha256
        or parent.human_decisions_sha256 != cert.pins.original_human_decisions_sha256
        or parent.metres_per_blender_unit != provider.contract.scale.metres_per_blender_unit
    ):
        raise ValueError("original parent source/protocol/HR/scale differs from the intact union")
    result = ScopedInferenceConfig(
        authority=ScopedRouteAuthorityBinding(
            pins=cert.pins,
            proposal_content_sha256=cert.proposal_content_sha256,
            decision_content_sha256=cert.human_decision_content_sha256,
            certificate_content_sha256=provider.certificate_content_sha256,
            union_wkb_sha256=cert.union_wkb_sha256,
        ),
        fresh_export_config_sha256=fresh_export_config_sha256,
        source_camera_plane_ids={
            b.camera.camera_id: "SCOPED_LANDMARK_PLANE:" + provider.scope_id
            for b in provider.proposal.camera_landmark_bindings
        },
        metres_per_blender_unit=parent.metres_per_blender_unit,
        movement=parent.movement,
        search_policy=parent.search_policy,
        reconstruction_policy=parent.reconstruction_policy,
        aggregation_policy=AggregationPolicy(
            max_visible_sample_gap_s=parent.aggregation_max_visible_sample_gap_s,
        ),
        budget_lineage=ScopedBudgetLineage(
            parent_inference_lock_content_sha256=content_sha256(parent.model_dump(mode="json")),
            parent_search_policy=parent.search_policy,
            changed_search_fields=(),
        ),
    )
    return validate_scoped_inference_config(result, provider)


def _python_module(root: Path, name: str) -> Path | None:
    if not name.startswith("amidst"):
        return None
    target = root / "src" / Path(*name.split("."))
    if target.with_suffix(".py").is_file():
        return target.with_suffix(".py")
    return target / "__init__.py" if (target / "__init__.py").is_file() else None


def producer_hashes(root: Path) -> dict[str, str]:
    """Hash final producers and transitive local imports, including dynamic roots.

    All finalization modules are explicit roots because orchestration imports
    stages lazily. Original projection diagnostics are script imports, so their
    roots are explicit too. Neither output definitions nor test files enter this
    population; rebuilding the definition cannot create a self-hash cycle.
    """
    roots = list((root / "src/amidst/finalization").glob("*.py"))
    roots += list((root / "scripts").glob("*phase1*case23*.py"))
    roots += [
        root / "scripts" / name
        for name in (
            "run_phase1_reviewed.py",
            "export_phase1_reviewed_inputs.py",
            "export_phase1_scoped_inputs.py",
            "export_blender_pilot.py",
            "phase1_projection_policy.py",
            "projection_multiview_model.py",
            "projection_mitigation_policy.py",
            "projection_uncertainty_model.py",
        )
    ]
    pending, found = list(roots), set()
    while pending:
        path = pending.pop()
        relative = path.relative_to(root).as_posix()
        if relative in found:
            continue
        safe_artifact(root, relative)
        found.add(relative)
        if path.is_relative_to(root / "src"):
            ancestor = path.parent
            while ancestor != root / "src":
                package = ancestor / "__init__.py"
                if package.is_file():
                    pending.append(package)
                ancestor = ancestor.parent
        for node in ast.walk(ast.parse(path.read_bytes(), filename=relative)):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level:
                    parts = list(path.relative_to(root / "src").with_suffix("").parts)
                    parts = parts[: -node.level]
                    module = ".".join((*parts, module)) if module else ".".join(parts)
                names = [module, *(module + "." + alias.name for alias in node.names)]
            for name in names:
                dependency = _python_module(root, name)
                if dependency is None and "." not in name:
                    local_script = root / "scripts" / (name + ".py")
                    dependency = local_script if local_script.is_file() else None
                if dependency is not None:
                    pending.append(dependency)
    return {relative: digest(root / relative) for relative in sorted(found)}


def protected_input_hashes(root: Path, source_config_path: Path) -> dict[str, str]:
    """Pin original approvals, actual cameras, physical inputs, and source settings."""
    paths = {
        source_config_path.resolve().relative_to(root.resolve()).as_posix(),
        "configs/benchmarks/protocol_v1.json",
        OFFICE_EXPORT_CONFIG,
        OFFICE_INFERENCE_CONFIG,
        "configs/finalization/reviewed_case_inventory_v1.json",
        "configs/finalization/reviewed_case_inference_lock_v1.json",
        "configs/finalization/reviewed_case_inference_lock_v2.json",
        "configs/finalization/proposed_reference_movement_policy_v1.json",
        "configs/finalization/case2_interior_branch_addendum_v1.json",
        "data/finalization/case23_scope_audit_20261014/human_approval.json",
        "data/finalization/reference_movement_approved_v1/approval_receipt.json",
        "data/finalization/reference_movement_approved_v1/approved_input_lock.json",
        "configs/physical_context_school_v3.json",
        "configs/physical_policy_runtime_school_v3.json",
        "configs/physical_collision_numerics_v1.json",
        "data/scene_audit/phase1_physical_policy_approval_20261006/source_evidence.json.gz",
        "human_review/review_template.json",
        "pyproject.toml",
        "uv.lock",
    }
    for directory in (
        OFFICE_APPLICATION,
        "data/finalization/reviewed_branch_scope_review_v2",
        "data/finalization/reviewed_corridor_scope_application_v1",
    ):
        # Only source/authority inputs; previews are not producers or approvals.
        paths.update(p.relative_to(root).as_posix() for p in (root / directory).glob("*.json"))
    decisions = read_json(root / OFFICE_APPLICATION / "human_decisions.json")
    for row in decisions["metadata"]["input_hashes"]:
        path = safe_artifact(root, row["path"])
        if digest(path) != row["sha256"]:
            raise ValueError("original human-reviewed input changed: " + row["path"])
        paths.add(row["path"])
    context = read_json(root / "configs/physical_context_school_v3.json")
    for value in context.values():
        if isinstance(value, str) and value.startswith(("data/", "configs/")):
            paths.add(value)
    return {relative: digest(safe_artifact(root, relative)) for relative in sorted(paths)}


def build_scoped_experiment(
    root: Path,
    source_config_path: Path,
    output: Path,
    *,
    provider: ScopedUnionPhysicalProvider | None = None,
) -> dict[str, Any]:
    """Issue a new definition only after all source code is final; never hash itself."""
    root = root.resolve()
    source_config_path = safe_artifact(
        root, source_config_path.resolve().relative_to(root).as_posix()
    )
    provider = load_export_authority(root) if provider is None else provider
    source_config = read_json(source_config_path)
    validate_recipes(source_config, provider)
    collision_lock = load_reviewed_collision_lock(root / OFFICE_INFERENCE_CONFIG, repo_root=root)
    parent = collision_lock.base_inference_lock.base_inference_config
    config = config_from_original_parent(provider, parent, digest(source_config_path))
    office = load_reviewed_authority(root / OFFICE_APPLICATION, repo_root=root)
    reviewed_metrics = reviewed_metric_config(office)
    metrics = MetricConfig.model_validate(reviewed_metrics.computation_config.model_dump())
    if office.source_sha256 != provider.source_sha256 or (
        office.human_decisions_sha256 != provider.certificate.pins.original_human_decisions_sha256
        or metrics.collision_tolerance_m != provider.contract.parameter("collision_tolerance_m")
        or source_config.get("inference_seed") != parent.inference_seed
        or source_config.get("export_seed") != 20261005
        or source_config.get("sampling_fps") != parent.sampling_fps
        or source_config.get("parent_export_config_file_sha256")
        != digest(root / "configs/finalization/reviewed_case_inventory_v1.json")
    ):
        raise ValueError("joint office/scoped source, original HR metrics, seed or sampling differ")
    protected = protected_input_hashes(root, source_config_path)
    producers = producer_hashes(root)
    if output.resolve() in {safe_artifact(root, p) for p in (*protected, *producers)}:
        raise ValueError("experiment output cannot overwrite or self-hash a protected input")
    document = {
        "schema_version": "phase1-scoped-case23-experiment-v1",
        "status": "FROZEN_BEFORE_NEW_SOURCE_SIMULATION_AND_INFERENCE",
        "class_definition": CLASS_DEFINITION,
        "source_sha256": provider.source_sha256,
        "protocol_file_sha256": provider.certificate.pins.protocol_sha256,
        "original_human_decisions_content_sha256": (
            provider.certificate.pins.original_human_decisions_sha256
        ),
        "inference_seed": parent.inference_seed,
        "export_seed": 20261005,
        "sampling_fps": parent.sampling_fps,
        "source_config_path": source_config_path.relative_to(root).as_posix(),
        "source_config_file_sha256": digest(source_config_path),
        "source_config_content_sha256": content_sha256(source_config),
        "source_case_ids": [case["case_id"] for case in source_config["cases"]],
        "inference_config": config.model_dump(mode="json"),
        "inference_config_content_sha256": content_sha256(config.model_dump(mode="json")),
        "metric_config": metrics.model_dump(mode="json"),
        "metric_config_content_sha256": content_sha256(metrics.model_dump(mode="json")),
        "metric_authority": reviewed_metrics.model_dump(mode="json"),
        "original_research_budget_modified": False,
        "class_generation_budget": ClassGenerationBudget().model_dump(mode="json"),
        "inventory_budget": InventoryBudget().model_dump(mode="json"),
        "resource_population_policy": (
            "INDEPENDENT_CLASS_RESOURCE_BOUNDS_SEPARATE_FROM_UNCHANGED_GRAPH_RESEARCH_BUDGET"
        ),
        "joint_release_selection": {
            "case1": "FRESH_ORIGINAL_REVIEWED_OFFICE_CHILD_CASE1",
            "case2": "FRESH_APPROVED_CORRIDOR_UNION_CHILD_CASE2",
            "case3": "FRESH_APPROVED_CORRIDOR_UNION_CHILD_CASE3",
            "other_child_case_rows_preserved": True,
            "stress_controls_are_formal_cases": False,
            "cross_case_aggregation": "NONE",
        },
        "office_child": {
            "application_path": OFFICE_APPLICATION,
            "export_config_path": OFFICE_EXPORT_CONFIG,
            "inference_config_path": OFFICE_INFERENCE_CONFIG,
            "selected_case_ids": ["case1"],
            "all_original_child_rows_retained": True,
            "child_local_scope_and_blocked_results_relabelled": False,
        },
        "protected_input_hashes": protected,
        "producer_hashes": producers,
        "ground_truth_available_to_inference": False,
        "definition_self_sha256_included": False,
        "old_results_relabelled": False,
        "formal_case_readiness": False,
        "phase2_modified": False,
    }
    validate_master_bindings(document, root)
    write_json(output, document)
    return document


def validate_master_bindings(master: dict[str, Any], root: Path) -> None:
    """Reject omitted pins, changed common metrics, or undeclared research deltas."""
    validate_protocol(master, root)
    source_path = safe_artifact(root, master["source_config_path"])
    config = ScopedInferenceConfig.model_validate(master["inference_config"])
    parent = load_reviewed_collision_lock(
        root / OFFICE_INFERENCE_CONFIG,
        repo_root=root,
    ).base_inference_lock.base_inference_config
    approved = read_json(root / OFFICE_APPLICATION / "approved_input_lock.json")
    settings, coverage = approved["automatic_settings"], approved["coverage"]
    expected_metrics = MetricConfig(
        metric_config_version="phase1-reviewed-metric-computation-v1",
        k_values=tuple(settings["k_values"]),
        coverage_epsilon_m=coverage["epsilon_m"],
        collision_tolerance_m=settings["physical_policy"]["collision_tolerance_m"],
    )
    if (
        master["protected_input_hashes"] != protected_input_hashes(root, source_path)
        or master["producer_hashes"] != producer_hashes(root)
        or master["source_sha256"] != parent.source_sha256
        or master["protocol_file_sha256"] != parent.protocol_sha256
        or master["original_human_decisions_content_sha256"] != parent.human_decisions_sha256
        or master["inference_seed"] != parent.inference_seed
        or master["export_seed"] != 20261005
        or master["sampling_fps"] != parent.sampling_fps
        or master["source_config_file_sha256"] != digest(source_path)
        or not isinstance(master["source_case_ids"], list)
        or len(set(master["source_case_ids"])) != len(master["source_case_ids"])
        or not {"case2", "case3"}.issubset(master["source_case_ids"])
        or config.fresh_export_config_sha256 != digest(source_path)
        or master["inference_config_content_sha256"]
        != content_sha256(config.model_dump(mode="json"))
        or master["metric_config"] != expected_metrics.model_dump(mode="json")
        or master["metric_config_content_sha256"]
        != content_sha256(expected_metrics.model_dump(mode="json"))
        or coverage["distance_metric"] != "ADE"
        or coverage["comparison"] != "STRICTLY_LESS_THAN"
        or master["original_research_budget_modified"] is not False
        or config.budget_lineage.changed_search_fields
        or config.budget_lineage.parent_search_policy != parent.search_policy
        or config.budget_lineage.parent_inference_lock_content_sha256
        != content_sha256(parent.model_dump(mode="json"))
        or config.search_policy != parent.search_policy
        or config.movement != parent.movement
        or config.reconstruction_policy != parent.reconstruction_policy
        or config.aggregation_policy.max_visible_sample_gap_s
        != parent.aggregation_max_visible_sample_gap_s
        or master["definition_self_sha256_included"] is not False
    ):
        raise ValueError("joint master omits an exact pin or changes original source/metric/budget")


@dataclass(frozen=True)
class OfficeChildPlan:
    """Original producer invocation; stages consume new directories only."""

    export_argv: tuple[str, ...]
    dataset: Path
    inference: Path
    evaluation: Path
    reproduction: Path
    application: Path
    config: Path


def office_child_plan(root: Path, source: Path, blender: Path, output: Path) -> OfficeChildPlan:
    return OfficeChildPlan(
        export_argv=(
            str(blender),
            "--background",
            "--disable-autoexec",
            str(source),
            "--python",
            str(root / "scripts/export_phase1_reviewed_inputs.py"),
            "--",
            "--config",
            str(root / OFFICE_EXPORT_CONFIG),
            "--application",
            str(root / OFFICE_APPLICATION),
            "--output",
            str(output / "dataset"),
        ),
        dataset=output / "dataset",
        inference=output / "inference_primary",
        evaluation=output / "evaluation",
        reproduction=output / "reproduction",
        application=root / OFFICE_APPLICATION,
        config=root / OFFICE_INFERENCE_CONFIG,
    )


def _office_manifest(master: dict[str, Any], root: Path, plan: OfficeChildPlan) -> dict[str, Any]:
    manifest = read_json(plan.dataset / "manifest.json")
    if manifest["source_sha256"] != master["source_sha256"] or (
        manifest["inference_seed"] != master["inference_seed"]
        or manifest["export_seed"] != master["export_seed"]
        or manifest["sampling_fps"] != master["sampling_fps"]
        or manifest["config_sha256"] != digest(root / OFFICE_EXPORT_CONFIG)
    ):
        raise ValueError("fresh office child differs from joint source/config/seed/sampling")
    return manifest


def export_office_child(
    root: Path,
    source: Path,
    blender: Path,
    output: Path,
    *,
    master_path: Path,
    export_runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """Use the exact original-office source producer in a new child directory.

    The original complete recipe/config bytes are retained. This also exports
    office Case 3 and preserves office Case 2's blocker; selecting joint Case 1
    grants no new authority to those original child rows.
    """
    master = read_json(master_path)
    validate_master_bindings(master, root)
    if output.exists():
        raise FileExistsError("office child requires a new output directory")
    before = digest(source), source.stat().st_size, source.stat().st_mtime_ns
    if before[0] != master["source_sha256"]:
        raise ValueError("office child source differs from the joint frozen definition")
    output.mkdir(parents=True)
    plan = office_child_plan(root, source, blender, output)
    process = export_runner(plan.export_argv, cwd=root, capture_output=True, text=True, check=False)
    if process.returncode:
        raise RuntimeError(process.stderr.strip() or process.stdout.strip())
    validate_master_bindings(master, root)
    manifest = _office_manifest(master, root, plan)
    if before != (digest(source), source.stat().st_size, source.stat().st_mtime_ns):
        raise RuntimeError("source changed during the original office child execution")
    validate_master_bindings(master, root)
    return manifest


def infer_office_child(
    root: Path,
    output: Path,
    *,
    master_path: Path,
) -> dict[str, Any]:
    """Freeze office primary inference without opening any reference partition."""
    master = read_json(master_path)
    validate_master_bindings(master, root)
    plan = office_child_plan(root, Path("UNUSED_SOURCE"), Path("UNUSED_BLENDER"), output)
    _office_manifest(master, root, plan)
    fresh_process_inference(
        plan.dataset, plan.application, plan.config, plan.inference, repo_root=root
    )
    freeze = require_inference_freeze(plan.inference)
    validate_master_bindings(master, root)
    return freeze


def require_joint_inference_boundary(
    joint_freeze_path: Path,
    master_path: Path,
    office_inference: Path,
) -> dict[str, Any]:
    """Check both primary freezes before an office evaluation/poison stage opens GT."""
    joint = read_json(joint_freeze_path)
    master = read_json(master_path)
    if joint.get("schema_version") != "phase1-joint-inference-freeze-v1" or (
        joint.get("master_file_sha256") != digest(master_path)
        or set(joint.get("children", {})) != {"office", "scoped"}
        or set(joint.get("datasets", {})) != {"office", "scoped"}
        or joint.get("source_sha256") != master["source_sha256"]
        or joint.get("ground_truth_read") is not False
        or joint.get("status") != "ALL_PRIMARY_CHILDREN_FROZEN_BEFORE_ANY_REFERENCE_EVALUATION"
        or joint.get("case_selection") != master["joint_release_selection"]
    ):
        raise ValueError("a complete same-master office/scoped joint inference freeze is required")
    for role, child in joint["children"].items():
        directory = safe_artifact(joint_freeze_path.parent, child["directory"])
        frozen = require_inference_freeze(directory)
        if (
            frozen.get("ground_truth_read") is not False
            or (
                frozen.get("status") != "FROZEN_BEFORE_EVALUATION"
                or digest(directory / "inference_freeze.json") != child["freeze_file_sha256"]
            )
            or (role == "office" and directory != office_inference.resolve())
        ):
            raise ValueError("joint primary inference freeze differs from its exact child")
        dataset = joint["datasets"][role]
        manifest_path = (
            safe_artifact(joint_freeze_path.parent, dataset["directory"]) / "manifest.json"
        )
        manifest_sha = digest(manifest_path)
        manifest = read_json(manifest_path)
        if dataset["manifest_file_sha256"] != manifest_sha or (
            frozen["dataset_manifest_sha256"] != manifest_sha
            or dataset["dataset_version"] != manifest.get("dataset_version")
            or manifest.get("source_sha256") != master["source_sha256"]
            or manifest.get("export_seed") != master["export_seed"]
            or manifest.get("inference_seed") != master["inference_seed"]
            or manifest.get("sampling_fps") != master["sampling_fps"]
        ):
            raise ValueError("joint dataset manifest/source/seed/sampling differs from its child")
        if role == "office":
            selected = master["office_child"]
            pins = master["protected_input_hashes"]
            if frozen["config_sha256"] != pins[selected["inference_config_path"]] or (
                digest(directory / "collision_inference_lock.json")
                != pins[selected["inference_config_path"]]
                or manifest.get("config_sha256") != pins[selected["export_config_path"]]
                or manifest.get("application_manifest_sha256")
                != pins[selected["application_path"] + "/manifest.json"]
                or manifest.get("human_decisions_sha256")
                != master["original_human_decisions_content_sha256"]
            ):
                raise ValueError("joint office child differs from original configuration/approval")
        elif frozen["config_sha256"] != digest(master_path) or (
            digest(directory / "experiment.json") != digest(master_path)
            or content_sha256(read_json(directory / "config.json"))
            != master["inference_config_content_sha256"]
            or manifest.get("full_experiment_config_file_sha256") != digest(master_path)
            or manifest.get("config_file_sha256") != master["source_config_file_sha256"]
            or [row["case_id"] for row in manifest.get("cases", [])] != master["source_case_ids"]
        ):
            raise ValueError(
                "joint scoped child differs from exact master/source config/case population"
            )
    return joint


def evaluate_office_child(
    root: Path,
    output: Path,
    *,
    master_path: Path,
    joint_freeze_path: Path,
    demos: bool = False,
) -> dict[str, Any]:
    master = read_json(master_path)
    validate_master_bindings(master, root)
    plan = office_child_plan(root, Path("UNUSED_SOURCE"), Path("UNUSED_BLENDER"), output)
    require_joint_inference_boundary(joint_freeze_path, master_path, plan.inference)
    _office_manifest(master, root, plan)
    return evaluate_dataset(
        plan.dataset,
        plan.inference,
        plan.application,
        plan.evaluation,
        repo_root=root,
        demos=demos,
    )


def reproduce_office_child(
    root: Path,
    output: Path,
    *,
    master_path: Path,
    joint_freeze_path: Path,
) -> dict[str, Any]:
    master = read_json(master_path)
    validate_master_bindings(master, root)
    plan = office_child_plan(root, Path("UNUSED_SOURCE"), Path("UNUSED_BLENDER"), output)
    require_joint_inference_boundary(joint_freeze_path, master_path, plan.inference)
    _office_manifest(master, root, plan)
    reproduction = verify_reproduction(
        plan.dataset,
        plan.inference,
        plan.application,
        plan.config,
        plan.reproduction,
        repo_root=root,
    )
    result = {
        "schema_version": "phase1-joint-original-office-child-v1",
        "master_file_sha256": digest(master_path),
        "source_sha256": master["source_sha256"],
        "protocol_file_sha256": master["protocol_file_sha256"],
        "metric_config_content_sha256": master["metric_config_content_sha256"],
        "inference_seed": master["inference_seed"],
        "dataset_manifest_file_sha256": digest(plan.dataset / "manifest.json"),
        "inference_freeze_file_sha256": digest(plan.inference / "inference_freeze.json"),
        "reproduction_status": reproduction["status"],
        "joint_selected_case_ids": ["case1"],
        "original_child_case_rows_preserved": True,
        "child_case2_blocker_or_office_case3_relabelled": False,
        "child_full_exit_claimed": False,
        "formal_joint_acceptance_granted": False,
    }
    write_json(output / "joint_child_receipt.json", result)
    return result
