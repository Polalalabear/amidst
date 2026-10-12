"""Independent physical-layer port receipts over source-bound Blender features."""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Sequence
from typing import Any, Protocol

from amidst.engineering.registry import content_hash
from amidst.workbench.blender_association import BaselineAssociationIndex
from amidst.workbench.blender_physical import BlenderPhysicalIndex
from amidst.workbench.blender_ports import run_blender_port_probe
from amidst.workbench.scenes import SceneAdapter

Json = dict[str, Any]


class PhysicalProbeScene(Protocol):
    scene_id: str
    index: Any
    _physical_source: Any

    def snapshot(self) -> Json: ...
    def export_physical_source(self) -> Json: ...
    def physical_cross_camera_reconstruction(self, camera_ids: Sequence[str], start: float,
                                           end: float, top_k: int = 3) -> Json: ...


def run_physical_port_probe(scene: SceneAdapter, motion: Any = None,
                            association: Any = None, physical_media: Any = None) -> Json:
    """Old ports retain their scope; added checks never certify missing geometry."""
    from typing import cast

    base = run_blender_port_probe(scene, motion, association)
    adapter = cast(PhysicalProbeScene, scene)
    safe_source = adapter.export_physical_source()
    snapshot = adapter.index.snapshot()
    before = content_hash(snapshot)
    cameras = sorted(row["camera_id"] for row in scene.snapshot()["cameras"])
    full = adapter.physical_cross_camera_reconstruction(cameras, 0, 9.8, 3)
    fresh = BlenderPhysicalIndex(BaselineAssociationIndex(snapshot), adapter._physical_source)
    rerun = fresh.reconstruct(cameras, 0, 9.8, 3)
    poisoned = copy.deepcopy(snapshot)
    poisoned["ground_truth"] = {"preferred_candidate": "must-not-enter-physical-ranking"}
    poison_index = BlenderPhysicalIndex(BaselineAssociationIndex(poisoned),
                                        adapter._physical_source)
    isolated = poison_index.reconstruct(cameras, 0, 9.8, 3)
    parity = all(content_hash(full[key]) == content_hash(rerun[key]) for key in (
        "candidates", "rejected_candidates", "baseline_candidate", "decision_ledger"))
    poison_parity = all(content_hash(rerun[key]) == content_hash(isolated[key]) for key in (
        "candidates", "rejected_candidates", "baseline_candidate", "decision_ledger"))
    original_preserved = content_hash(adapter.index.snapshot()) == before
    scope = full["source_binding"]
    common = {"data_kind": "ACTUAL_BLENDER", "source_binding": scope}
    summary = safe_source["summary"]
    source_port = {**common, "port": "physical.source_constraints",
        "from_layer": "pinned.source_geometry_and_policy",
        "to_layer": "purpose_gated.support_and_known_colliders",
        "input": {"evidence_hashes": full["evidence_hashes"],
                  "source_features": full["source_features"], "snapshot_sha256": before},
        "output": {"physical_source_sha256": summary["physical_source_sha256"],
                   "coverage": summary["coverage"], "policy": summary["policy"],
                   "portals_summary": summary["portals_summary"],
                   "units": safe_source["units"], "geometry_is_partial": True,
                   "new_geometry_authority": False},
        "status": "PASS" if safe_source["units"] == "METRES" else "FAIL"}
    decisions = [{"rank": c["rank"], "original_rank": c.get("original_rank"),
                  "verdict": c["physical"]["verdict"],
                  "scores": c["physical"]["scores"],
                  "reason_codes": [r["code"] for r in c["physical"]["reasons"]],
                  "unknown_codes": sorted({r["code"] for r in c["physical"]["unknowns"]})}
                 for c in full["candidates"]]
    candidate_port = {**common, "port": "physical.candidate_filter",
        "from_layer": "source_clock.cross_camera_bounded_pool",
        "to_layer": "nominal_connected_interval_physical_decisions",
        "input": {"base_association_sha256": full["base_association_sha256"],
                  "pool_limit": full["search"].get("pool_budget", 256)},
        "output": {"physical_sha256": full["physical_sha256"], "search": full["search"],
                   "decision_ledger_sha256": full["decision_ledger_sha256"],
                   "decisions": decisions, "rerun_parity": parity,
                   "original_observations_preserved": original_preserved,
                   "gt_poisoning_changes_decisions": not poison_parity,
                   "long_gap_chord_is_observed_motion": False},
        "status": "PASS" if parity and poison_parity and original_preserved else "FAIL"}
    top_port = {**common, "port": "physical.reranked_top_k",
        "from_layer": "physical_decisions_and_explicit_engineering_score",
        "to_layer": "retained_top_k_rejected_diagnostics_and_baseline",
        "input": {"requested_top_k": 3, "canonical_time_range": [0, 9.8]},
        "output": {"returned_top_k": len(full["candidates"]), "decisions": decisions,
                   "rejected_curve_candidates": len(full["rejected_candidates"]),
                   "baseline_retained": bool(full["baseline_candidate"]),
                   "status": full["status"], "formal_acceptance": False,
                   "agent_used": False, "global_optimality_certified": False},
        "status": "PASS" if len({c["candidate_ref"] for c in full["candidates"]}) ==
            len(full["candidates"]) and len(full["candidates"]) <= 3 else "FAIL"}
    manifest = {"status": "UNAVAILABLE", "items": []}
    binaries = []
    media_failed = False
    if physical_media is not None:
        try:
            manifest = physical_media.manifest(adapter)
            for item in manifest.get("items", []):
                mime, raw = physical_media.media(adapter, item["media_ref"])
                binaries.append({"kind": item["kind"], "mime_type": mime, "byte_count": len(raw),
                                 "sha256": hashlib.sha256(raw).hexdigest(),
                                 "matches_manifest": hashlib.sha256(raw).hexdigest() ==
                                    item["sha256"] and len(raw) == item["byte_count"]})
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            media_failed = True
            # Only this optional boundary fails; source/candidate/legacy receipts survive.
            # Exception strings may contain filesystem locators and are never exported.
            manifest = {"status": "UNAVAILABLE", "items": [],
                        "reason": "INVALID_OR_STALE_ARTIFACT"}
    media_ready = manifest["status"] == "AVAILABLE" and not media_failed
    video_port = {**common, "port": "physical.video",
        "from_layer": "physical_ranked_candidates_source_rgb_and_model",
        "to_layer": "pre_materialized_reason_curve_and_replay_media",
        "input": {"physical_sha256": full["physical_sha256"]},
        "output": {"manifest": manifest, "binary_checks": binaries,
                   "source_images_replaced_by_substitute": False,
                   "produced_at_query": False},
        "status": "FAIL" if media_failed else "PASS" if media_ready and len(binaries) == 2 and all(
            row["matches_manifest"] for row in binaries) else "FAIL" if media_ready else "DEFERRED"}
    added = [source_port, candidate_port, top_port, video_port]
    ports = base["ports"] + added
    completed = [p for p in ports if p["status"] != "DEFERRED"]
    return {**base, "schema_version": "workbench.blender-physical-ports.v1", "ports": ports,
        "status": "PASS" if all(p["status"] == "PASS" for p in completed) else "FAIL",
        "summary": {**base["summary"], "ports_total": len(ports), "total": len(completed),
            "passed": sum(p["status"] == "PASS" for p in completed),
            "deferred": sum(p["status"] == "DEFERRED" for p in ports),
            "actual_blender_ports": sum(p["data_kind"] == "ACTUAL_BLENDER"
                                        for p in completed),
            "physical_status": full["status"], "physical_video_materialized": media_ready}}
