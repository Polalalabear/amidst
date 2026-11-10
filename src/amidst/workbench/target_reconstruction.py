"""Selected-observation view of the existing bounded association hypotheses.

This adapter selects evidence, not identities or a second reconstruction method.
Camera-graph proposals do not certify navigability, collision or body clearance.
"""

from __future__ import annotations

import copy
import math
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol

from amidst.workbench.blender_association import MAX_GRAPH_EDGES, MAX_GRAPH_NODES, MAX_TOP_K
from amidst.workbench.blender_motion import MAX_CAMERAS, MAX_POINTS, MAX_WINDOW_S

Json = dict[str, Any]
SCHEMA_VERSION = "workbench.target-reconstruction.v1"


class TargetScene(Protocol):
    scene_id: str

    def snapshot(self) -> Json: ...

    def cross_camera_reconstruction(
        self, camera_ids: Sequence[str], start: float, end: float, top_k: int = 3
    ) -> Json: ...


@dataclass(frozen=True)
class TargetLimits:
    deadline_s: float = 2.0
    max_records_scanned: int = 50000
    max_paths_scanned: int = MAX_TOP_K * MAX_GRAPH_NODES
    max_expansions: int = MAX_GRAPH_NODES


class _Exhausted(Exception):
    pass


class _Budget:
    def __init__(self, limits: TargetLimits, clock: Callable[[], float]) -> None:
        self.limits, self.clock = limits, clock
        self.deadline = clock() + limits.deadline_s
        self.counts = {"records_scanned": 0, "paths_scanned": 0, "expansions": 0}

    def check(self, kind: str | None = None) -> None:
        if self.clock() >= self.deadline:
            raise _Exhausted("DEADLINE_EXCEEDED")
        if kind is not None:
            if self.counts[kind] >= getattr(self.limits, "max_" + kind):
                raise _Exhausted("SCAN_BUDGET_EXHAUSTED")
            self.counts[kind] += 1

    def rows(self, rows: list[Json], cap: int) -> Iterator[Json]:
        self.check()
        if len(rows) > cap:
            raise _Exhausted("SOURCE_BUDGET_EXHAUSTED")
        for row in rows:
            self.check("records_scanned")
            yield row


def reconstruct_target(
    scene: TargetScene,
    camera_ids: Sequence[str],
    start: float,
    end: float,
    top_k: int,
    observation_ref: str,
    *,
    limits: TargetLimits | None = None,
    clock: Callable[[], float] | None = None,
) -> Json:
    """Keep canonical candidate ranks/refs and only the selected target's path.

    The canonical pool contains at most five scene hypotheses. Filtering can return
    fewer than K target continuations; it never fills the result with other people.
    The deadline is cooperative around bounded in-memory work and source checks.
    Startup/process hard timeouts are the caller's separate responsibility.
    """
    limits = limits or TargetLimits()
    budget = _Budget(limits, clock or monotonic)
    selected: Json | None = None
    association: Json | None = None
    targets: list[Json] = []
    reachable: list[Json] = []
    trace: list[Json] = []
    selection = {
        "scene_id": scene.scene_id,
        "camera_ids": sorted(camera_ids),
        "time_range": [start, end],
        "top_k": top_k,
        "observation_ref": observation_ref,
    }

    def record(decision: str, **evidence: Any) -> None:
        trace.append(
            {"step": len(trace) + 1, "mode": "DETERMINISTIC", "decision": decision, **evidence}
        )

    def result(status: str, reason: str) -> Json:
        record(reason)
        return {
            "schema_version": SCHEMA_VERSION,
            "status": status,
            "reason": reason,
            "selection": selection,
            "selected_observation": selected,
            "association": association,
            "target_candidates": targets if status == "READY" else [],
            "reachable_cameras": reachable if status == "READY" else [],
            "constraints": {
                "association_policy": copy.deepcopy(association["policy"]) if association else None,
                "candidate_pool_top_k": MAX_TOP_K,
                "returned_target_candidates": len(targets) if status == "READY" else 0,
                "physical_navigation_verdict": "UNKNOWN",
                "collision_verdict": "UNKNOWN",
                "reachable_camera_authority": "EVIDENCE_GRAPH_PROPOSAL_ONLY",
                "coordinate_frame": "RIGHT_HANDED_XYZ_Z_UP",
                "position_units": "METRES",
                "time_unit": "SECONDS",
                "observed_3d": False,
                "max_records_scanned": limits.max_records_scanned,
                "max_paths_scanned": limits.max_paths_scanned,
                "max_expansions": limits.max_expansions,
                "cooperative_deadline_s": limits.deadline_s,
                "hard_process_timeout_enforced_here": False,
                "counts": dict(budget.counts),
                "model_calls": 0,
                "tool_calls": 0,
                "retry_count": 0,
            },
            "trace": trace,
            "agent_used": False,
            "identity_verdict": "UNCONFIRMED",
            "formal_acceptance": False,
            "limitations": [
                "Camera-local pixel tracks do not confirm cross-camera person identity.",
                "Only the existing five-candidate scene pool is filtered; fewer than K may remain.",
                "Source-floor projections and configured speed caps do not certify physical paths.",
                "Long gaps remain MISSING with null positions; no smoothing or extrapolation.",
                "The monotonic deadline is cooperative; runner startup/hard timeout is separate.",
            ],
        }

    try:
        budget.check()
        snapshot = scene.snapshot()
        budget.check()
        baseline = snapshot.get("baseline", {})
        frames = list(budget.rows(baseline.get("frames", []), MAX_POINTS))
        known_cameras = {row["camera_id"] for row in frames}
        if (
            type(top_k) is not int
            or not 1 <= top_k <= MAX_TOP_K
            or isinstance(camera_ids, (str, bytes))
            or not 1 <= len(camera_ids) <= MAX_CAMERAS
            or len(set(camera_ids)) != len(camera_ids)
            or any(camera not in known_cameras for camera in camera_ids)
        ):
            raise ValueError("TARGET_CAMERA_OR_TOP_K_SCOPE_DENIED")
        if (
            isinstance(start, bool)
            or isinstance(end, bool)
            or not math.isfinite(start)
            or not math.isfinite(end)
            or start < 0
            or end < start
            or end - start > MAX_WINDOW_S
        ):
            raise ValueError("TARGET_FINITE_WINDOW_REQUIRED")
        for row in budget.rows(baseline.get("measurements", []), MAX_POINTS):
            if row["observation_ref"] == observation_ref:
                selected = copy.deepcopy(row)
                break
        if selected is None:
            return result("UNKNOWN", "OBSERVATION_NOT_FOUND")
        if selected["camera_id"] not in camera_ids:
            return result("UNKNOWN", "OBSERVATION_OUTSIDE_CAMERA_SELECTION")
        record(
            "SELECTED_SOURCE_OBSERVATION",
            observation_ref=observation_ref,
            frame_ref=selected["frame_ref"],
            track_ref=selected["track_ref"],
        )
        projection = None
        for row in budget.rows(baseline.get("projected_measurements", []), MAX_POINTS):
            if row["observation_ref"] == observation_ref:
                projection = row
                break
        if projection is not None:
            selected.update(copy.deepcopy(projection))
        if (
            projection is None
            or projection["projection_status"] != "PROJECTED"
            or projection["world_position"] is None
        ):
            return result("UNKNOWN", "SELECTED_PROJECTION_UNAVAILABLE")
        budget.check()
        # Reuse canonical graph/search. Query windows slice curves, never rankings.
        association = scene.cross_camera_reconstruction(camera_ids, start, end, MAX_TOP_K)
        budget.check()
        nodes = {
            row["node_ref"]: row
            for row in budget.rows(association["graph"]["nodes"], MAX_GRAPH_NODES)
        }
        selected_nodes: list[str] = []
        for ref, node in nodes.items():
            for source_ref in node["source_observation_refs"]:
                budget.check("records_scanned")
                if source_ref == observation_ref:
                    selected_nodes.append(ref)
                    break
        if not selected_nodes:
            return result("UNKNOWN", "SELECTED_NODE_UNAVAILABLE")
        record("SELECTED_CANONICAL_NODES", node_refs=selected_nodes)
        edges = list(budget.rows(association["graph"]["edges"], MAX_GRAPH_EDGES))
        outgoing: dict[str, list[Json]] = {}
        for edge in edges:
            outgoing.setdefault(edge["from_node_ref"], []).append(edge)
        # Bounded directed graph traversal proposes reachable evidence cameras.
        queue = list(selected_nodes)
        visited = set(selected_nodes)
        for ref in queue:
            budget.check("expansions")
            for edge in outgoing.get(ref, []):
                budget.check("records_scanned")
                to_ref = edge["to_node_ref"]
                node = nodes[to_ref]
                if node["canonical_time_range"][1] <= selected["timestamp"]:
                    continue
                if to_ref not in visited:
                    visited.add(to_ref)
                    queue.append(to_ref)
                    if node["camera_id"] != selected["camera_id"]:
                        reachable.append(
                            {
                                "camera_id": node["camera_id"],
                                "node_ref": to_ref,
                                "via_edge_ref": edge["edge_ref"],
                                "time_range": list(node["canonical_time_range"]),
                                "authority": "EVIDENCE_GRAPH_PROPOSAL_ONLY",
                                "navigation_verdict": "UNKNOWN",
                            }
                        )
        record("FILTERED_CAMERA_GRAPH", reachable_node_refs=[r["node_ref"] for r in reachable])
        for candidate in budget.rows(association["candidates"], MAX_TOP_K):
            for path in candidate["paths"]:
                budget.check("paths_scanned")
                if len(path["node_refs"]) > MAX_GRAPH_NODES:
                    raise _Exhausted("SOURCE_BUDGET_EXHAUSTED")
                selected_at = [
                    i for i, ref in enumerate(path["node_refs"]) if ref in selected_nodes
                ]
                if not selected_at:
                    continue
                # Earlier evidence in another camera is not a continuation of this click.
                later = path["node_refs"][min(selected_at) + 1 :]
                continuation = False
                for ref in later:
                    budget.check("records_scanned")
                    node = nodes[ref]
                    if (
                        node["camera_id"] != selected["camera_id"]
                        and node["canonical_time_range"][1] > selected["timestamp"]
                    ):
                        continuation = True
                if not continuation:
                    continue
                budget.check()
                targets.append(
                    {
                        "candidate_ref": candidate["candidate_ref"],
                        "rank": candidate["rank"],
                        "score": candidate["score"],
                        "score_scope": "ORIGINAL_SCENE_CANDIDATE",
                        "score_authority": "CONFIGURED_COMPATIBILITY_NOT_PROBABILITY",
                        "selected_edge_refs": list(path["edge_refs"]),
                        "identity_verdict": "UNCONFIRMED",
                        "paths": [copy.deepcopy(path)],
                    }
                )
                record(
                    "RETAINED_SELECTED_TARGET_PATH",
                    candidate_ref=candidate["candidate_ref"],
                    original_rank=candidate["rank"],
                    path_ref=path["path_ref"],
                )
                break
            if len(targets) >= top_k:
                break
        budget.check()
        if not targets:
            return result("UNKNOWN", "NO_SELECTED_TARGET_CROSS_CAMERA_CONTINUATION")
        return result("READY", "SELECTED_TARGET_CANDIDATES_AVAILABLE")
    except _Exhausted as error:
        return result("UNKNOWN", str(error))
