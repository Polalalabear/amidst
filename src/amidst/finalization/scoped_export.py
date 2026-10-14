"""Freeze and validate a new source export inside the approved cell union.

Simulation recipes are consumed here only. Inference receives a separate 2D
partition; a successful source export never grants formal Case readiness.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import math
from dataclasses import asdict
from pathlib import Path
from typing import Any

from amidst.finalization.reviewed_authority import review_content_sha256
from amidst.finalization.reviewed_reference_movement import load_reference_movement_approval
from amidst.finalization.scoped_authority import (
    ScopeAuthorityPins,
    ScopedUnionPhysicalProvider,
    ScopeHumanDecision,
    ScopeProposal,
    ScopeUnionCertificate,
    load_scoped_authority,
)
from amidst.obstacle_volume_authority import content_sha256
from amidst.physical_collision import CollisionNumerics
from amidst.physical_policy_contract import load_physical_policy_contract


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path: Path) -> Any:
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def load_export_authority(root: Path) -> ScopedUnionPhysicalProvider:
    """Regenerate the original approved proofs, with independent preserved pins."""
    review = root / "data/finalization/reviewed_branch_scope_review_v2"
    application = root / "data/finalization/reviewed_corridor_scope_application_v1"
    pins = ScopeAuthorityPins.model_validate_json((review / "pins.json").read_bytes())
    if file_sha256(root / "configs/benchmarks/protocol_v1.json") != pins.protocol_sha256:
        raise ValueError("original protocol bytes differ from the approval pins")
    if review_content_sha256(
        read_json(
            root / "data/finalization/human_review_applied_v1/human_decisions.json",
        )
    ) != (pins.original_human_decisions_sha256):
        raise ValueError("original human decision bytes differ from approval pins")
    proposal = ScopeProposal.model_validate_json((application / "proposal.json").read_bytes())
    decision = ScopeHumanDecision.model_validate_json(
        (application / "human_decision.json").read_bytes(),
    )
    certificate = ScopeUnionCertificate.model_validate_json(
        (application / "certificate.json").read_bytes(),
    )
    return load_scoped_authority(
        proposal,
        decision,
        certificate,
        read_json(
            root / "data/scene_audit/phase1_physical_policy_approval_20261006/"
            "source_evidence.json.gz"
        ),
        load_physical_policy_contract(root / "configs/physical_policy_runtime_school_v3.json"),
        CollisionNumerics.model_validate_json(
            (root / "configs/physical_collision_numerics_v1.json").read_bytes(),
        ),
        expected_pins=pins,
        expected_certificate_content_sha256=content_sha256(
            certificate.model_dump(mode="json"),
        ),
        camera_export=read_json(review / "actual_source_cameras.json"),
    )


def validate_recipes(config: dict[str, Any], provider: ScopedUnionPhysicalProvider) -> None:
    """Reject unapproved paths, sampling changes, overspeed and interior dwell."""
    if config.get("schema_version") != "phase1-scoped-source-export-v1" or (
        config.get("sampling_fps") != 5
        or config.get("config_locked_before_simulation") is not True
        or config.get("metres_per_blender_unit") != 0.0247
    ):
        raise ValueError("scoped export requires the preserved frozen 5 Hz policy")
    if config.get("source_sha256") != provider.certificate.pins.source_sha256:
        raise ValueError("export source differs from approved union")
    cameras = {binding.camera.camera_id for binding in provider.proposal.camera_landmark_bindings}
    cases = config.get("cases")
    if not isinstance(cases, list) or not cases or len({c["case_id"] for c in cases}) != len(cases):
        raise ValueError("nonempty unique source recipes required")
    for case in cases:
        if not case.get("camera_ids") or not set(case["camera_ids"]).issubset(cameras):
            raise ValueError("export camera is outside the exact approved source bindings")
        waypoints = case["waypoints"]
        if len(waypoints) < 2:
            raise ValueError("recipe requires increasing source waypoint times")
        if any(len(w["position"]) != 3 for w in waypoints):
            raise ValueError("source recipes require three coordinate components")
        points = tuple(
            (float(w["position"][0]), float(w["position"][1]), float(w["position"][2]))
            for w in waypoints
        )
        provider.validate_polyline(points)
        for index, (before, after) in enumerate(zip(waypoints[:-1], waypoints[1:], strict=True)):
            start, end = float(before["timestamp"]), float(after["timestamp"])
            if not math.isfinite(start + end) or start < 0 or end <= start:
                raise ValueError("strictly increasing finite source timestamps required")
            if any(
                not math.isclose(t * 5, round(t * 5), rel_tol=0, abs_tol=1e-10)
                for t in (start, end)
            ):
                raise ValueError("waypoints must use the original exact 5 Hz grid")
            distance = math.dist(points[index], points[index + 1])
            if distance == 0 and index != 0:
                raise ValueError("only independently approved departure dwell is supported")
            if distance / (end - start) > 32 + 1e-12:
                raise ValueError("recipe exceeds the approved 32 BU/s speed")


def freeze_export(
    config_path: Path,
    source: Path,
    output: Path,
    *,
    root: Path,
    experiment_path: Path | None = None,
    provider: ScopedUnionPhysicalProvider | None = None,
) -> dict[str, Any]:
    provider = provider or load_export_authority(root)
    config = read_json(config_path)
    validate_recipes(config, provider)
    if file_sha256(source) != provider.certificate.pins.source_sha256:
        raise ValueError("preserved Blender source does not match approved source SHA")
    if output.exists():
        raise FileExistsError("export lock must be a new immutable version")
    camera_bindings = [
        b.model_dump(mode="json") for b in provider.proposal.camera_landmark_bindings
    ]
    parent_movement = read_json(
        root / "configs/finalization/reviewed_case_export_with_movement_v2.json"
    )
    movement = load_reference_movement_approval(
        root / parent_movement["reference_movement_approval_receipt_path"],
        root / parent_movement["reference_movement_policy_path"],
        expected_receipt_content_sha256=parent_movement[
            "reference_movement_approval_receipt_content_sha256"
        ],
        expected_source_sha256=provider.source_sha256,
        expected_protocol_sha256=provider.certificate.pins.protocol_sha256,
        expected_original_human_decisions_sha256=provider.certificate.pins.original_human_decisions_sha256,
    )
    experiment_sha = None
    if experiment_path is not None:
        from amidst.finalization.scoped_pipeline import validate_protocol

        experiment = read_json(experiment_path)
        validate_protocol(experiment, root)
        if experiment["inference_config"]["fresh_export_config_sha256"] != file_sha256(config_path):
            raise ValueError("full experiment differs from the frozen source configuration")
        experiment_sha = file_sha256(experiment_path)
    snapshot = {
        "schema_version": "phase1-scoped-export-lock-v1",
        "status": "FROZEN_BEFORE_SOURCE_SIMULATION",
        "formal_case_readiness": False,
        "config": config,
        "config_file_sha256": file_sha256(config_path),
        "source_sha256": file_sha256(source),
        "source_size_bytes": source.stat().st_size,
        "source_mtime_ns": source.stat().st_mtime_ns,
        "authority": {
            "pins": provider.certificate.pins.model_dump(mode="json"),
            "proposal_content_sha256": provider.certificate.proposal_content_sha256,
            "decision_content_sha256": provider.certificate.human_decision_content_sha256,
            "certificate_content_sha256": provider.certificate_content_sha256,
            "union_wkb_sha256": provider.certificate.union_wkb_sha256,
        },
        "camera_bindings": camera_bindings,
        "scope_id": provider.proposal.scope_id,
        "floor": provider.proposal.floor.model_dump(mode="json"),
        "source_saved": False,
        "original_producers_modified": False,
        "reference_movement_approval": asdict(movement),
        "full_experiment_config_file_sha256": experiment_sha,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(snapshot, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    return snapshot
