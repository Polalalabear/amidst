"""Bounded cross-camera hypotheses from pixel-derived, floor-only local motion.

No semantic identity is asserted. Connected local segments are immutable evidence
nodes; configured temporal, distance and speed checks admit provisional edges.
Ranking uses an explicit compatibility score, never GT, agents or scene meshes.
"""
from __future__ import annotations

import copy
import itertools
import math
from collections.abc import Sequence
from typing import Any

from amidst.engineering.registry import content_hash, opaque_ref
from amidst.workbench.blender_motion import (
    MAX_INTERPOLATION_GAP_S,
    MAX_SPEED_M_S,
    MAX_WINDOW_S,
    BaselineMotionIndex,
)

Json = dict[str, Any]
ASSOCIATION_VERSION = "bounded-floor-cross-camera-v1"
MAX_TOP_K = 5
MAX_GRAPH_NODES = 64
MAX_GRAPH_EDGES = 256
BEAM_WIDTH = 256
MAX_OVERLAP_DISTANCE_M = 0.75
_BRIDGE_STEP_S = 0.2
_SPEED_EPSILON = 1e-9


def _refs(rows: Sequence[Json], field: str) -> list[str]:
    return list(dict.fromkeys(ref for row in rows for ref in row.get(field, [])))


def _overlaps(interval: Sequence[float], start: float, end: float) -> bool:
    return interval[0] <= end and interval[1] >= start


def _finite_speed(a: Json, b: Json) -> float | None:
    dt = b["timestamp"] - a["timestamp"]
    if dt <= 0:
        return None
    speed = math.dist(a["world_position"], b["world_position"]) / dt
    return speed if math.isfinite(speed) else None


class BaselineAssociationIndex:
    """Build canonical graph/search once; window queries only slice its curves."""

    def __init__(self, snapshot: Json) -> None:
        self.motion = BaselineMotionIndex(snapshot)
        cameras = sorted({row["camera_id"] for row in snapshot["frames"]})
        times = [float(row["timestamp"]) for row in snapshot["frames"]]
        self._full = self.motion.reconstruct(cameras, min(times), max(times))
        self.source_features = self._full["source_features"]
        self._cameras = tuple(cameras)
        self._scope_hash = content_hash({"source_binding": self._full["source_binding"],
                                         "motion_sha256": self._full["reconstruction_sha256"]})
        self._policy: Json = {
            "algorithm_version": ASSOCIATION_VERSION,
            "authority": "CONFIGURED_ENGINEERING_CONSTRAINTS",
            "geometry_authority": "SOURCE_BOUND_FLOOR_ONLY",
            "position_units": "METRES", "time_unit": "SECONDS",
            "speed_units": "METRES_PER_SECOND", "max_speed_m_s": MAX_SPEED_M_S,
            "max_gap_s": MAX_WINDOW_S, "speed_numeric_tolerance_m_s": _SPEED_EPSILON,
            "max_bridge_interpolation_s": MAX_INTERPOLATION_GAP_S,
            "max_overlap_distance_m": MAX_OVERLAP_DISTANCE_M,
            "overlap_basis": "COMMON_SOURCE_CLOCK_SAMPLES_AND_SWITCH_SPEED",
            "score_authority": "CONFIGURED_COMPATIBILITY_NOT_PROBABILITY",
            "uncertainty_authority": "PIXEL_HEURISTIC_NOT_METRIC_ERROR_BOUND",
            "max_top_k": MAX_TOP_K, "max_path_points": 400, "max_graph_nodes": MAX_GRAPH_NODES,
            "max_graph_edges": MAX_GRAPH_EDGES, "beam_width": BEAM_WIDTH,
            "one_incoming_one_outgoing": True, "identity_confirmed": False,
            "behavior_confirmed": False, "same_track_gap_repair": False,
            "extrapolation": False, "collision_checked": False,
            "walkability_checked": False, "navigation_checked": False,
            "agent_used": False,
        }
        self._nodes: dict[str, Json] = {}
        for track in self._full["tracks"]:
            segments: list[list[Json]] = []
            for sample in track["samples"]:
                if sample["world_position"] is None:
                    continue
                if not segments or not sample["connect_from_previous"]:
                    segments.append([])
                segments[-1].append(copy.deepcopy(sample))
            for ordinal, segment in enumerate(segments):
                canonical_range = [segment[0]["timestamp"], segment[-1]["timestamp"]]
                ref = opaque_ref("node", self._scope_hash, track["track_ref"],
                                 content_hash(segment))
                for sample in segment:
                    sample["node_ref"] = ref
                    sample["camera_id"] = track["camera_id"]
                self._nodes[ref] = {
                    "node_ref": ref, "track_ref": track["track_ref"],
                    "camera_id": track["camera_id"], "segment_ordinal": ordinal,
                    "canonical_time_range": canonical_range, "samples": segment,
                    "source_observation_refs": _refs(segment, "source_observation_refs"),
                    "source_frame_refs": _refs(segment, "source_frame_refs"),
                    "identity_verdict": "UNCONFIRMED", "behavior_verdict": "UNKNOWN",
                    "state": "CAMERA_LOCAL_PROJECTED_SEGMENT",
                    "geometry_authority": "SOURCE_BOUND_FLOOR_ONLY",
                }
        if len(self._nodes) > MAX_GRAPH_NODES:
            raise ValueError("ASSOCIATION_GRAPH_NODE_BUDGET")
        self._ordered = sorted(self._nodes, key=lambda ref: (
            self._nodes[ref]["canonical_time_range"][1],
            self._nodes[ref]["canonical_time_range"][0], ref))
        edges, rejected = [], []
        for i, left_ref in enumerate(self._ordered):
            for right_ref in self._ordered[i + 1:]:
                left, right = self._nodes[left_ref], self._nodes[right_ref]
                if left["camera_id"] == right["camera_id"]:
                    continue
                edge, reason = self._edge(left, right)
                if edge is not None:
                    edges.append(edge)
                else:
                    rejected.append({"from_node_ref": left_ref, "to_node_ref": right_ref,
                                     "reason": reason, "state": "REJECTED"})
        if len(edges) > MAX_GRAPH_EDGES:
            raise ValueError("ASSOCIATION_GRAPH_EDGE_BUDGET")
        self._edges = {row["edge_ref"]: row for row in edges}
        self._rejected = rejected
        self._route_prefix_rejections = 0
        self._canonical: dict[tuple[str, ...], Json] = {}
        for count in range(1, len(cameras) + 1):
            for subset in itertools.combinations(cameras, count):
                self._canonical[subset] = self._search(subset)
        self.association_sha256 = content_hash({
            "source_binding": self._full["source_binding"],
            "source_features": self.source_features,
            "motion_reconstruction_sha256": self._full["reconstruction_sha256"],
            "policy": self._policy, "nodes": list(self._nodes.values()),
            "edges": list(self._edges.values()), "rejected_edges": self._rejected,
            "search": [{"camera_ids": list(key), **value}
                       for key, value in self._canonical.items()],
        })
        self.reconstruction_sha256 = self.association_sha256

    def _edge(self, left: Json, right: Json) -> tuple[Json | None, str | None]:
        a, b = left["samples"][-1], right["samples"][0]
        gap = b["timestamp"] - a["timestamp"]
        distance = math.dist(a["world_position"], b["world_position"])
        if not math.isfinite(distance):
            return None, "NUMERICAL_FAILURE"
        support: list[Json] = []
        if gap > 0:
            speed = distance / gap
            if gap > MAX_WINDOW_S:
                return None, "TIME_GAP_CAP"
            if not math.isfinite(speed) or speed > MAX_SPEED_M_S + _SPEED_EPSILON:
                return None, "SPEED_CAP"
            kind = "CROSS_CAMERA_TIME_GAP"
            score = 1 / (1 + gap) + 1 / (1 + speed)
            missing = gap > MAX_INTERPOLATION_GAP_S
        else:
            # Arbitrarily close endpoints cannot certify simultaneous compatibility.
            left_at = {row["timestamp"]: row for row in left["samples"]}
            right_at = {row["timestamp"]: row for row in right["samples"]}
            common = sorted(set(left_at).intersection(right_at))
            if not common:
                return None, "NO_COMMON_SOURCE_CLOCK_SAMPLE"
            distances = [math.dist(left_at[t]["world_position"], right_at[t]["world_position"])
                         for t in common]
            if any(not math.isfinite(value) for value in distances):
                return None, "NUMERICAL_FAILURE"
            if max(distances) > MAX_OVERLAP_DISTANCE_M:
                return None, "OVERLAP_POSITION_CONFLICT"
            next_samples = [row for row in right["samples"]
                            if row["timestamp"] > a["timestamp"]]
            switch_speed = _finite_speed(a, next_samples[0]) if next_samples else None
            if next_samples and (switch_speed is None
                                 or switch_speed > MAX_SPEED_M_S + _SPEED_EPSILON):
                return None, "OVERLAP_SWITCH_SPEED_CAP"
            support = [{"timestamp": t, "distance_m": d,
                        "source_observation_refs": _refs([left_at[t], right_at[t]],
                                                         "source_observation_refs"),
                        "source_frame_refs": _refs([left_at[t], right_at[t]],
                                                   "source_frame_refs")}
                       for t, d in zip(common, distances, strict=True)]
            kind = "CROSS_CAMERA_OVERLAP" if next_samples else "CROSS_CAMERA_CORROBORATING_OVERLAP"
            speed, distance = switch_speed, max(distances)
            score = 1 + 1 / (1 + distance) + (1 / (1 + speed) if speed is not None else 0)
            missing = False
        ref = opaque_ref("edge", self._scope_hash, left["node_ref"], right["node_ref"], kind)
        return {
            "edge_ref": ref, "from_node_ref": left["node_ref"],
            "to_node_ref": right["node_ref"], "kind": kind,
            "time_range": [min(a["timestamp"], b["timestamp"]),
                           max(a["timestamp"], b["timestamp"])],
            "gap_s": max(0.0, gap), "distance_m": distance,
            "implied_speed_m_s": speed, "compatibility_score": score,
            "score_authority": "CONFIGURED_COMPATIBILITY_NOT_PROBABILITY",
            "state": "INFERRED_CROSS_CAMERA", "overlap_support": support,
            "source_observation_refs": _refs([a, b], "source_observation_refs"),
            "source_frame_refs": _refs([a, b], "source_frame_refs"),
            "endpoint_uncertainties": [a["uncertainty"], b["uncertainty"]],
            "from_timestamp": a["timestamp"], "to_timestamp": b["timestamp"],
            "from_world_position": list(a["world_position"]),
            "to_world_position": list(b["world_position"]),
            "missing_reason": "CROSS_CAMERA_LONG_GAP" if missing else None,
            "geometry_authority": "SOURCE_BOUND_FLOOR_ONLY",
            "bridge_missing": missing, "collision_checked": False,
            "identity_verdict": "UNCONFIRMED", "behavior_verdict": "UNKNOWN",
        }, None

    def _consistent(self, selected: tuple[str, ...]) -> bool:
        outgoing: dict[str, str] = {}
        incoming: set[str] = set()
        for ref in selected:
            edge = self._edges[ref]
            a, b = edge["from_node_ref"], edge["to_node_ref"]
            if a in outgoing or b in incoming:
                return False
            outgoing[a] = b
            incoming.add(b)
        for root in outgoing.keys() - incoming:
            path: list[Json] = []
            cursor: str | None = root
            while cursor is not None:
                node = self._nodes[cursor]
                for previous in path:
                    # A hard local disconnection cannot be repaired indirectly.
                    if previous["track_ref"] == node["track_ref"]:
                        return False
                    if previous["camera_id"] != node["camera_id"]:
                        previous_at = {row["timestamp"]: row for row in previous["samples"]}
                        node_at = {row["timestamp"]: row for row in node["samples"]}
                        common = set(previous_at).intersection(node_at)
                        if any(math.dist(previous_at[t]["world_position"],
                                         node_at[t]["world_position"]) > MAX_OVERLAP_DISTANCE_M
                               for t in common):
                            return False
                    if previous["camera_id"] == node["camera_id"] and _overlaps(
                        previous["canonical_time_range"], *node["canonical_time_range"]
                    ):
                        return False
                path.append(node)
                cursor = outgoing.get(cursor)
            path_nodes = [row["node_ref"] for row in path]
            route = self._route_samples(path_nodes, [ref for ref in selected if
                self._edges[ref]["from_node_ref"] in path_nodes])
            if not self._route_valid(route):
                self._route_prefix_rejections += 1
                return False
        return True

    def _score(self, selected: tuple[str, ...]) -> float:
        return float(sum(self._edges[ref]["compatibility_score"] for ref in selected))

    def _search(self, cameras: tuple[str, ...]) -> Json:
        nodes = [ref for ref in self._ordered if self._nodes[ref]["camera_id"] in cameras]
        node_set = set(nodes)
        edges = sorted((ref for ref, row in self._edges.items()
                        if row["from_node_ref"] in node_set and row["to_node_ref"] in node_set),
                       key=lambda ref: (-self._edges[ref]["compatibility_score"], ref))
        beam: list[tuple[str, ...]] = [()]
        pruned, evaluated = False, 1
        prefix_before = self._route_prefix_rejections
        for edge in edges:
            expanded = list(beam)
            for state in beam:
                proposal = tuple(sorted((*state, edge)))
                evaluated += 1
                if self._consistent(proposal):
                    expanded.append(proposal)
            expanded = sorted(set(expanded), key=lambda state: (-self._score(state), state))
            if len(expanded) > BEAM_WIDTH:
                pruned = True
            beam = expanded[:BEAM_WIDTH]
        candidates = [self._candidate(state, nodes) for state in beam[:MAX_TOP_K]]
        baseline = self._candidate((), nodes)
        prefix_rejections = self._route_prefix_rejections - prefix_before
        return {"candidates": candidates, "baseline_candidate": baseline,
                "search": {"algorithm": "DETERMINISTIC_EDGE_ASSIGNMENT_BEAM",
                           "complete": not pruned and not prefix_rejections, "truncated": pruned,
                           "prefix_route_guard_rejections": prefix_rejections,
                           "prefix_route_guard": "REJECT_UNSAFE_PREFIX_NO_LATER_REPAIR",
                           "beam_width": BEAM_WIDTH, "edges_considered": len(edges),
                           "hypotheses_evaluated": evaluated,
                           "total_unique_hypotheses": len(beam),
                           "returned_candidate_budget": MAX_TOP_K,
                           "score_optimality": "BOUNDED_BEAM_NOT_GLOBALLY_CERTIFIED" if pruned
                           else "PREFIX_GUARDED_NOT_GLOBALLY_CERTIFIED" if prefix_rejections
                           else "EXACT_ENUMERATION"}}

    def _candidate(self, selected: tuple[str, ...], nodes: list[str]) -> Json:
        outgoing = {self._edges[ref]["from_node_ref"]: (self._edges[ref]["to_node_ref"], ref)
                    for ref in selected}
        incoming = {self._edges[ref]["to_node_ref"] for ref in selected}
        paths = []
        for root in nodes:
            if root in incoming:
                continue
            path_nodes, path_edges = [root], []
            while path_nodes[-1] in outgoing:
                node, edge = outgoing[path_nodes[-1]]
                path_nodes.append(node)
                path_edges.append(edge)
            paths.append(self._path(path_nodes, path_edges))
        selected_nodes = {ref for edge in selected for ref in (
            self._edges[edge]["from_node_ref"], self._edges[edge]["to_node_ref"])}
        score = self._score(selected)
        ref = opaque_ref("candidate", self._scope_hash, content_hash(selected))
        return {
            "candidate_ref": ref, "score": score, "cost": -score,
            "score_terms": [{"edge_ref": edge,
                             "compatibility_score": self._edges[edge]["compatibility_score"]}
                            for edge in selected],
            "selected_edge_refs": list(selected),
            "unassociated_node_refs": [ref for ref in nodes if ref not in selected_nodes],
            "paths": paths, "identity_verdict": "UNCONFIRMED",
            "behavior_verdict": "UNKNOWN", "authority": "PROVISIONAL_ENGINEERING_HYPOTHESIS",
            "is_unassociated_baseline": not selected,
            "unresolved_local_gaps": [{"camera_id": track["camera_id"],
                                       "track_ref": track["track_ref"], **copy.deepcopy(gap)}
                                      for track in self._full["tracks"]
                                      if track["camera_id"] in {self._nodes[n]["camera_id"]
                                                                for n in nodes}
                                      for gap in track["gaps"]],
        }

    def _route_samples(self, nodes: list[str], edges: list[str]) -> list[Json]:
        priorities = sorted(nodes, key=lambda ref: (
            self._nodes[ref]["canonical_time_range"][0],
            -self._nodes[ref]["canonical_time_range"][1], ref))
        at = {ref: {row["timestamp"]: row for row in self._nodes[ref]["samples"]}
              for ref in nodes}
        times = sorted({timestamp for points in at.values() for timestamp in points})
        route: list[Json] = []
        for timestamp in times:
            supporting = [ref for ref in priorities if timestamp in at[ref]]
            primary = supporting[0]
            sample = copy.deepcopy(at[primary][timestamp])
            sample["overlap_support"] = [
                {"node_ref": ref, "camera_id": self._nodes[ref]["camera_id"],
                 "world_position": list(at[ref][timestamp]["world_position"]),
                 "state": at[ref][timestamp]["state"],
                 "source_observation_refs": at[ref][timestamp]["source_observation_refs"],
                 "source_frame_refs": at[ref][timestamp]["source_frame_refs"],
                 "uncertainty": at[ref][timestamp]["uncertainty"]}
                for ref in supporting[1:]]
            if not route:
                sample["connect_from_previous"] = False
            elif route[-1]["node_ref"] != primary:
                left = route[-1]
                # In a canonical chain a source switch may bypass a contained
                # corroborating node; retain every responsible edge reference.
                links = [self._edges[ref] for ref in edges if
                         self._edges[ref]["from_node_ref"] == left["node_ref"] or
                         self._edges[ref]["to_node_ref"] == primary]
                gap = timestamp - left["timestamp"]
                disjoint = (self._nodes[left["node_ref"]]["canonical_time_range"][1] <
                            self._nodes[primary]["canonical_time_range"][0])
                missing = disjoint and gap > MAX_INTERPOLATION_GAP_S
                edge_refs = [row["edge_ref"] for row in links]
                source_refs = _refs([left, sample], "source_observation_refs")
                frame_refs = _refs([left, sample], "source_frame_refs")
                if missing:
                    route.append({
                        "timestamp": (left["timestamp"] + timestamp) / 2,
                        "world_position": None, "state": "MISSING", "node_ref": None,
                        "camera_id": None, "association_edge_refs": edge_refs,
                        "connect_from_previous": False, "pixel_observed": False,
                        "source_observation_refs": source_refs, "source_frame_refs": frame_refs,
                        "uncertainty": None, "missing_reason": "CROSS_CAMERA_LONG_GAP",
                        "missing_time_range": [left["timestamp"], timestamp],
                    })
                elif disjoint:
                    steps = max(1, math.ceil(gap / _BRIDGE_STEP_S))
                    for step in range(1, steps):
                        fraction = step / steps
                        route.append({
                            "timestamp": left["timestamp"] + fraction * gap,
                            "world_position": [a + fraction * (b - a) for a, b in zip(
                                left["world_position"], sample["world_position"], strict=True)],
                            "state": "INFERRED_CROSS_CAMERA", "node_ref": None,
                            "camera_id": None, "association_edge_refs": edge_refs,
                            "connect_from_previous": True, "pixel_observed": False,
                            "observation_ref": None, "frame_ref": None,
                            "source_observation_refs": source_refs, "source_frame_refs": frame_refs,
                            "uncertainty": max(left["uncertainty"], sample["uncertainty"]),
                            "geometry_authority": "SOURCE_BOUND_FLOOR_ONLY", "missing_reason": None,
                        })
                sample["connect_from_previous"] = not missing
                sample["association_edge_refs"] = edge_refs
            route.append(sample)
        return route

    @staticmethod
    def _route_valid(samples: list[Json]) -> bool:
        if len(samples) > 400:
            return False
        for a, b in zip(samples, samples[1:], strict=False):
            if (not b["connect_from_previous"] or a["world_position"] is None
                    or b["world_position"] is None):
                continue
            speed = _finite_speed(a, b)
            if speed is None or speed > MAX_SPEED_M_S + _SPEED_EPSILON:
                return False
        return True

    def _path(self, nodes: list[str], edges: list[str]) -> Json:
        samples = self._route_samples(nodes, edges)
        if not self._route_valid(samples):
            raise ValueError("ASSOCIATION_PATH_SPEED_CONTRADICTION")
        gaps = [{"gap_ref": opaque_ref("gap", self._scope_hash,
                                       content_hash(sample["association_edge_refs"]),
                                       content_hash(sample["missing_time_range"])),
                 "time_range": sample["missing_time_range"], "state": "MISSING",
                 "reason": sample["missing_reason"],
                 "source_observation_refs": sample["source_observation_refs"],
                 "source_frame_refs": sample["source_frame_refs"]}
                for sample in samples if sample["state"] == "MISSING"]
        velocities = []
        path_ref = opaque_ref("path", self._scope_hash, content_hash([nodes, edges]))
        for a, b in zip(samples, samples[1:], strict=False):
            if (not b["connect_from_previous"] or a["world_position"] is None
                    or b["world_position"] is None):
                continue
            speed = _finite_speed(a, b)
            if speed is None or speed > MAX_SPEED_M_S + _SPEED_EPSILON:
                raise ValueError("ASSOCIATION_PATH_SPEED_CONTRADICTION")
            dt = b["timestamp"] - a["timestamp"]
            cross = (a.get("node_ref") != b.get("node_ref")
                     or a["state"] == "INFERRED_CROSS_CAMERA"
                     or b["state"] == "INFERRED_CROSS_CAMERA")
            velocities.append({
                "interval_ref": opaque_ref("interval", path_ref,
                                            content_hash([a["timestamp"], b["timestamp"]])),
                "timestamp": (a["timestamp"] + b["timestamp"]) / 2,
                "time_range": [a["timestamp"], b["timestamp"]],
                "velocity_xyz": [(y - x) / dt for x, y in zip(
                    a["world_position"], b["world_position"], strict=True)],
                "speed_m_s": speed,
                "state": "INFERRED_CROSS_CAMERA" if cross else "INFERRED_FINITE_DIFFERENCE",
                "source_observation_refs": _refs([a, b], "source_observation_refs"),
                "source_frame_refs": _refs([a, b], "source_frame_refs"),
                "endpoint_uncertainties": [a["uncertainty"], b["uncertainty"]],
                "geometry_authority": "SOURCE_BOUND_FLOOR_ONLY",
            })
        return {
            "path_ref": path_ref, "node_refs": nodes, "edge_refs": edges,
            "camera_ids": sorted({self._nodes[ref]["camera_id"] for ref in nodes}),
            "canonical_time_range": [min(self._nodes[ref]["canonical_time_range"][0]
                                         for ref in nodes),
                                     max(self._nodes[ref]["canonical_time_range"][1]
                                         for ref in nodes)],
            "samples": samples, "velocities": velocities, "gaps": gaps,
            "source_observation_refs": _refs([sample for node in nodes
                                               for sample in self._nodes[node]["samples"]],
                                              "source_observation_refs"),
            "source_frame_refs": _refs([sample for node in nodes
                                         for sample in self._nodes[node]["samples"]],
                                        "source_frame_refs"),
            "event_ref": opaque_ref("event", path_ref),
            "identity_verdict": "UNCONFIRMED", "behavior_verdict": "UNKNOWN",
            "geometry_authority": "SOURCE_BOUND_FLOOR_ONLY",
            "authority": "PROVISIONAL_ENGINEERING_EVENT_RECONSTRUCTION",
        }

    @staticmethod
    def _slice_candidate(candidate: Json, start: float, end: float) -> Json:
        result = copy.deepcopy(candidate)
        paths = []
        for path in result["paths"]:
            if not _overlaps(path["canonical_time_range"], start, end):
                continue
            original = path["samples"]
            samples = [row for row in original if start <= row["timestamp"] <= end]
            if samples and samples[0] is not original[0]:
                samples[0]["canonical_connect_from_previous"] = samples[0]["connect_from_previous"]
                samples[0]["connect_from_previous"] = False
                samples[0]["window_clipped_before"] = True
            path["samples"] = samples
            path["velocities"] = [row for row in path["velocities"]
                                  if start <= row["timestamp"] <= end]
            path["gaps"] = [row for row in path["gaps"] if _overlaps(row["time_range"], start, end)]
            paths.append(path)
        result["paths"] = paths
        result["unresolved_local_gaps"] = [gap for gap in result["unresolved_local_gaps"]
                                           if _overlaps(gap["time_range"], start, end)]
        return result

    def reconstruct(self, camera_ids: Sequence[str], start: float, end: float,
                    top_k: int = 3) -> Json:
        if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
            raise ValueError("ASSOCIATION_TOP_K_BUDGET")
        local = self.motion.reconstruct(camera_ids, start, end)
        camera_tuple = tuple(sorted(camera_ids))
        canonical = self._canonical[camera_tuple]
        candidates = [self._slice_candidate(row, start, end)
                      for row in canonical["candidates"][:top_k]]
        usable = any(row["world_position"] is not None for candidate in candidates
                     for path in candidate["paths"] for row in path["samples"])
        if not usable:
            candidates = []
        for rank, candidate in enumerate(candidates, 1):
            candidate["rank"] = rank
        # Canonical graph metadata remains complete for selected cameras, so
        # candidate references never dangle when a time window hides a path.
        chosen_nodes = {ref for ref, node in self._nodes.items()
                        if node["camera_id"] in camera_tuple}
        graph_nodes = [copy.deepcopy(self._nodes[ref]) for ref in self._ordered
                       if ref in chosen_nodes]
        for node in graph_nodes:
            node["samples"] = [row for row in node["samples"]
                               if start <= row["timestamp"] <= end]
        graph_edges = [copy.deepcopy(row) for row in self._edges.values()
                       if row["from_node_ref"] in chosen_nodes
                       and row["to_node_ref"] in chosen_nodes]
        rejected = [copy.deepcopy(row) for row in self._rejected
                    if row["from_node_ref"] in chosen_nodes
                       and row["to_node_ref"] in chosen_nodes]
        baseline = self._slice_candidate(canonical["baseline_candidate"], start, end)
        edges_considered = canonical["search"]["edges_considered"]
        associated = any(row["selected_edge_refs"] for row in candidates)
        status = ("NO_RESULT" if not usable else "READY" if associated
                  else "NO_CROSS_CAMERA_EVIDENCE")
        return {
            "schema_version": "workbench.blender-association.v1", "status": status,
            "association_result_reason": "NO_USABLE_POINTS" if not usable else
                "CANDIDATES_AVAILABLE" if associated else "NO_ELIGIBLE_CROSS_CAMERA_EDGE"
                if not edges_considered else "NO_FEASIBLE_PREFIX_GUARDED_ROUTE",
            "source_binding": copy.deepcopy(self._full["source_binding"]),
            "source_features": self.source_features,
            "source_hashes": copy.deepcopy(self._full["source_hashes"]),
            "association_sha256": self.association_sha256,
            "reconstruction_sha256": self.association_sha256,
            "motion_reconstruction_sha256": self._full["reconstruction_sha256"],
            "floor_plane": copy.deepcopy(self._full["floor_plane"]),
            "source_time_range": list(self._full["source_time_range"]),
            "selection": {"camera_ids": list(camera_tuple), "time_range": [start, end],
                          "top_k": top_k}, "policy": copy.deepcopy(self._policy),
            "tracks": local["tracks"], "camera_coverage": local["camera_coverage"],
            "graph": {"nodes": graph_nodes, "edges": graph_edges, "rejected_edges": rejected,
                      "canonical_time_range": list(self._full["source_time_range"]),
                      "scope": "SELECTED_CAMERAS_FULL_SOURCE_TIME",
                      "sample_time_range": [start, end]},
            "candidates": candidates, "baseline_candidate": baseline,
            "search": {**copy.deepcopy(canonical["search"]), "requested_top_k": top_k,
                       "returned_top_k": len(candidates), "fabricated_candidates": False,
                       "canonical_search_scope": "SELECTED_CAMERAS_FULL_SOURCE_TIME"},
            "summary": {"candidates": len(candidates), "graph_nodes": len(graph_nodes),
                        "eligible_edges": len(graph_edges), "rejected_edges": len(rejected),
                        "local_tracks": len(local["tracks"]),
                        "local_motion": local["summary"],
                        "associated_candidates": sum(bool(row["selected_edge_refs"])
                                                     for row in candidates)},
            "retrieval": {**local["retrieval"], "canonical_graph_built_at_import": True,
                          "graph_nodes_read": len(graph_nodes),
                          "graph_edges_read": len(graph_edges),
                          "image_scan_at_query": False,
                          "bounded_precomputed_candidate_scan": True,
                          "candidate_points_read": sum(len(path["samples"])
                              for candidate in canonical["candidates"][:top_k]
                              for path in candidate["paths"])},
            "agent_used": False, "formal_acceptance": False,
            "limitations": [
                "Association is a provisional hypothesis, not confirmed cross-camera identity.",
                "Floor positions are RGB projections; observed positions are never averaged.",
                "Scores/caps/proximity and pixel uncertainty are configured, not probabilities.",
                "Long cross-camera gaps remain MISSING, without extrapolation or detours.",
                "Hard local gaps are not repaired through a cross-camera path.",
                "Partial source model is display context; collision/walkability are unverified.",
                "Rendered targets/motion are synthetic substitutes; no real stream is used.",
            ],
        }
