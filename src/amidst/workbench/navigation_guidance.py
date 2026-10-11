"""Import-built label/feature navigation for a bounded, local mock Agent.

Labels select registered resources, never inferred identities or behavior verdicts.
The graph describes configured retrieval links; its hops are not physical feasibility.
Only camera/time index queries run at request time. Source files, media, evaluation,
event catalogs, geometry coordinates and feature vectors do not enter Agent context.
"""

from __future__ import annotations

import copy
import json
import math
from collections import defaultdict, deque
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from amidst.domain.trajectory import TerminationReason
from amidst.engineering.access import digest
from amidst.engineering.registry import opaque_ref
from amidst.workbench.scenes import SceneAdapter

Json = dict[str, Any]
Behavior = Literal["walking", "running", "enter_exit"]
MAX_HOPS = 3
MAX_NODES = 12
MAX_EDGES = 24
MAX_CAMERAS = 4
MAX_FEATURES = 8
MAX_CANDIDATES = 8
MAX_MEDIA_REFS = 4
MAX_AGENT_INPUT_BYTES = 64 * 1024
# SceneAdapter queries read at most 128 events and 128 observations per camera.
MAX_RECORD_READS = MAX_CAMERAS * 256
BEHAVIORS = (("walking", "行走"), ("running", "跑步"), ("enter_exit", "出入"))


class _DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class NavigationNode(_DTO):
    node_ref: str
    kind: Literal["CAMERA", "REGION"]
    resource_id: str


class NavigationEdge(_DTO):
    from_ref: str
    to_ref: str
    relation: Literal["CONFIGURED_CAMERA_LINK", "REGISTERED_COVERAGE", "CONFIGURED_REGION_LINK"]


class FeatureSummary(_DTO):
    record_ref: str
    record_kind: Literal["EVENT", "OBSERVATION"]
    camera_ids: list[str]
    time_range: list[float] = Field(min_length=2, max_length=2)
    region_ids: list[str]
    event_kind: Literal[
        "ENTER_DOOR", "EXIT_DOOR", "TURN_CORNER", "DWELL", "POSSIBLE_LOITERING",
        "LOST_NEAR_CORNER", "INFERRED_GAP_ALTERNATIVES", "UNKNOWN",
    ]
    evidence_state: Literal["PROJECTED", "INFERRED_GAP", "UNKNOWN"]
    support_state: Literal["SUPPORTED", "UNKNOWN", "GAP_ALTERNATIVES"]
    candidate_count: int = Field(ge=0)
    ordered_candidate_refs: list[str]
    omitted_candidate_count: int = Field(ge=0)
    trajectory_hypothesis_count: int = Field(ge=0)
    media_refs: list[str]
    omitted_media_count: int = Field(ge=0)
    complete: bool | None
    termination_reason: str | None
    uncertainty: Literal["PROVISIONAL_SOURCE_EVIDENCE"] = "PROVISIONAL_SOURCE_EVIDENCE"


class GuidanceScope(_DTO):
    scene_id: str
    place_id: str
    model_id: str
    model_revision: str
    run_id: str
    clock_id: str
    source_ref: str
    spatial_context_id: str
    freeze_ref: str
    observation_mode: Literal["photos_only", "photos_plus_observations"]
    decision_stage: Literal["RESULTS"] = "RESULTS"


class Selection(_DTO):
    camera_id: str
    time_range: list[float] = Field(min_length=2, max_length=2)
    behavior: Behavior
    behavior_authority: Literal["USER_SELECTED_INTENT"] = "USER_SELECTED_INTENT"
    top_k: int = Field(ge=1, le=MAX_FEATURES)


class Budget(_DTO):
    max_hops: int = MAX_HOPS
    max_nodes: int = MAX_NODES
    max_edges: int = MAX_EDGES
    max_camera_queries: int = MAX_CAMERAS
    max_records_read: int = MAX_RECORD_READS
    max_agent_features: int = MAX_FEATURES
    max_candidate_refs_per_feature: int = MAX_CANDIDATES
    max_detail_actions: int = 2
    max_agent_input_bytes: int = MAX_AGENT_INPUT_BYTES


class Telemetry(_DTO):
    import_built_index: Literal[True] = True
    global_scan: Literal[False] = False
    graph_nodes_visited: int = Field(ge=0, le=MAX_NODES)
    graph_edges_touched: int = Field(ge=0, le=MAX_EDGES)
    camera_queries: int = Field(ge=0, le=MAX_CAMERAS)
    records_read: int = Field(ge=0, le=MAX_RECORD_READS)
    index_entries_touched: int = Field(ge=0)
    frames_read: Literal[0] = 0
    bytes_read: Literal[0] = 0
    features_returned: int = Field(ge=0, le=MAX_FEATURES)
    truncation_reasons: list[str]
    scoped_inventory_complete: bool
    graph_search_complete: None = None


class BoundedAction(_DTO):
    tool: Literal["get_event_detail"]
    record_ref: str


class AgentInput(_DTO):
    schema_version: Literal["workbench.navigation.agent-input.v1"] = (
        "workbench.navigation.agent-input.v1"
    )
    status: Literal["READY", "NEEDS_INPUT"]
    label: str | None
    scope: GuidanceScope
    selection: Selection
    navigation_nodes: list[NavigationNode]
    navigation_edges: list[NavigationEdge]
    features: list[FeatureSummary]
    budget: Budget = Field(default_factory=Budget)
    telemetry: Telemetry
    allowed_next_actions: list[BoundedAction]
    instructions: list[str]
    uncertainty: list[str]


_INSTRUCTIONS = [
    "Use only supplied scoped references and bounded actions; no catalog/filesystem/SQL scan.",
    "Top-K bounds evidence summaries, never chooses a unique identity or trajectory.",
    "Preserve canonical candidate order; omitted alternatives remain unresolved.",
    "Behavior is user-selected intent, not an observed behavior classification.",
    "Configured retrieval edges do not establish physical feasibility or camera coverage.",
]


class GuidanceIndex:
    """Build once per immutable scene/run; requests cannot scan the imported catalog."""

    def __init__(self, scene: SceneAdapter) -> None:
        self.scene = scene
        service = scene.service
        context = service.context()
        if context["decision_stage"] != "RESULTS" or not context.get("freeze_ref"):
            raise ValueError("GUIDANCE_RESULTS_ONLY")
        self._binding = digest(service.guard.binding)
        self._scope = GuidanceScope.model_validate({
            "scene_id": scene.scene_id,
            **{key: context[key] for key in GuidanceScope.model_fields if key != "scene_id"},
        })
        snapshot = scene.snapshot()
        self._time_range = tuple(float(t) for t in snapshot["time_range"])
        self._cameras = {c.camera_id: c for c in service.cameras.values()}
        self._nodes: dict[str, NavigationNode] = {}
        self._aliases: dict[str, set[str]] = defaultdict(set)
        self._adjacency: dict[str, tuple[NavigationEdge, ...]] = {}
        edges: dict[str, list[NavigationEdge]] = defaultdict(list)
        self._node_ids: dict[tuple[str, str], str] = {}

        def node(kind: Literal["CAMERA", "REGION"], resource_id: str) -> str:
            ref = opaque_ref("navnode", self._binding, kind, resource_id)
            self._nodes[ref] = NavigationNode(node_ref=ref, kind=kind, resource_id=resource_id)
            self._node_ids[kind, resource_id] = ref
            self._aliases[resource_id.strip().casefold()].add(ref)
            self._aliases[f"{kind.lower()}:{resource_id}".casefold()].add(ref)
            return ref

        for camera_id in sorted(self._cameras):
            node("CAMERA", camera_id)
        topology = service.index.topology(service.scope)
        self._topology_complete = topology.topology_complete
        regions = {str(o["properties"]["region_id"]) for o in snapshot["objects"]
                   if o["kind"] == "REGION"}
        regions.update(r for c in topology.camera_regions for r in c.region_ids)
        regions.update(r for link in topology.region_links
                       for r in (link.from_region_id, link.to_region_id))
        for region_id in sorted(regions):
            node("REGION", region_id)
        for row in snapshot["cameras"]:
            self._aliases[str(row["label"]).strip().casefold()].add(
                self._node_ids["CAMERA", str(row["camera_id"])])
        for row in snapshot["objects"]:
            if row["kind"] == "REGION":
                self._aliases[str(row["label"]).strip().casefold()].add(
                    self._node_ids["REGION", str(row["properties"]["region_id"])])
        for purpose, aliases in {
            "navigation": ("navigation", "導航"),
            "observations": ("observations", "觀測"),
            "behavior": ("behavior", "行為"),
        }.items():
            for alias in aliases:
                self._aliases[alias].add(purpose)
        for alias in (self._scope.place_id, snapshot["label"]):
            self._aliases[str(alias).strip().casefold()].add("navigation")
        for link in topology.camera_links:
            origin = self._node_ids["CAMERA", link.from_camera_id]
            edges[origin].append(NavigationEdge(
                from_ref=origin, to_ref=self._node_ids["CAMERA", link.to_camera_id],
                relation="CONFIGURED_CAMERA_LINK"))
        for row in topology.camera_regions:
            origin = self._node_ids["CAMERA", row.camera_id]
            for region_id in row.region_ids:
                edges[origin].append(NavigationEdge(
                    from_ref=origin, to_ref=self._node_ids["REGION", region_id],
                    relation="REGISTERED_COVERAGE"))
        for region_link in topology.region_links:
            origin = self._node_ids["REGION", region_link.from_region_id]
            edges[origin].append(NavigationEdge(
                from_ref=origin, to_ref=self._node_ids["REGION", region_link.to_region_id],
                relation="CONFIGURED_REGION_LINK"))
        self._adjacency = {ref: tuple(sorted(rows, key=lambda e: (
            self._nodes[e.to_ref].kind, self._nodes[e.to_ref].resource_id, e.relation)))
                           for ref, rows in edges.items()}
        self._features: dict[str, FeatureSummary] = {}
        for kind, records in (("EVENT", service.events), ("OBSERVATION", service.observations)):
            for ref, record in records.items():
                candidates = record.get("candidates", [])
                media = [r for r in record.get("media_refs", []) if r in service.frames]
                termination = record.get("termination_reason")
                termination = termination if termination in set(TerminationReason) else None
                event_kind = record.get("kind")
                evidence_state = record.get("evidence_state")
                support_state = record.get("support_state")
                self._features[ref] = FeatureSummary.model_validate({
                    "record_ref": ref, "record_kind": kind,
                    "camera_ids": [c for c in record["camera_ids"] if c in self._cameras],
                    "time_range": record["time_range"],
                    "region_ids": [r for r in record["region_ids"] if r in regions],
                    "event_kind": event_kind if event_kind in {
                        "ENTER_DOOR", "EXIT_DOOR", "TURN_CORNER", "DWELL", "POSSIBLE_LOITERING",
                        "LOST_NEAR_CORNER", "INFERRED_GAP_ALTERNATIVES",
                    } else "UNKNOWN",
                    "evidence_state": evidence_state if evidence_state in {
                        "PROJECTED", "INFERRED_GAP",
                    } else "UNKNOWN",
                    "support_state": support_state if support_state in {
                        "SUPPORTED", "GAP_ALTERNATIVES",
                    } else "UNKNOWN",
                    "candidate_count": len(candidates),
                    "ordered_candidate_refs": [
                        opaque_ref("navcandidate", ref, str(i))
                        for i in range(min(len(candidates), MAX_CANDIDATES))],
                    "omitted_candidate_count": max(0, len(candidates) - MAX_CANDIDATES),
                    "trajectory_hypothesis_count": len(record.get("trajectories", [])),
                    "media_refs": media[:MAX_MEDIA_REFS],
                    "omitted_media_count": max(0, len(media) - MAX_MEDIA_REFS),
                    "complete": record.get("complete"), "termination_reason": termination,
                })

    def presets(self) -> Json:
        """Human dropdown data uses dataset defaults; it is not an Agent catalog tool."""
        return {
            "scene_id": self.scene.scene_id, "place_id": self._scope.place_id,
            "time_range": list(self._time_range), "clock_id": self._scope.clock_id,
            "cameras": [{"camera_id": c.camera_id, "label": c.camera_id}
                        for c in self._cameras.values()],
            "behaviors": [{"value": value, "label": label} for value, label in BEHAVIORS],
            "behavior_authority": "USER_SELECTED_INTENT",
            "labels": ["navigation", "observations", "behavior"],
            "defaults": {"camera_id": next(iter(self._cameras), ""),
                         "start": self._time_range[0], "end": self._time_range[1],
                         "behavior": "walking", "label": "navigation", "top_k": 3},
        }

    def _navigate(self, anchor: str) -> tuple[list[str], list[NavigationEdge], list[str], int]:
        visited, pending, reasons = [anchor], deque([(anchor, 0)]), []
        result: list[NavigationEdge] = []
        touched = 0
        seen = {anchor}
        while pending:
            current, hops = pending.popleft()
            adjacent = self._adjacency.get(current, ())
            if hops >= MAX_HOPS:
                if adjacent:
                    reasons.append("HOP_BUDGET")
                continue
            for edge in adjacent:
                if touched >= MAX_EDGES:
                    return visited, result, [*reasons, "EDGE_BUDGET"], touched
                touched += 1
                if edge.to_ref not in seen:
                    if len(visited) >= MAX_NODES:
                        return visited, result, [*reasons, "NODE_BUDGET"], touched
                    seen.add(edge.to_ref)
                    visited.append(edge.to_ref)
                    pending.append((edge.to_ref, hops + 1))
                result.append(edge)
        return visited, result, reasons, touched

    def guide(self, label: str, camera_id: str, start: float, end: float,
              behavior: str = "walking", top_k: int = 3) -> Json:
        """Resolve an exact label, BFS static links, query finite camera/time buckets."""
        if digest(self.scene.service.guard.binding) != self._binding:
            raise ValueError("GUIDANCE_SCOPE_CHANGED")
        if self.scene.service.guard.stage != "RESULTS":
            raise ValueError("GUIDANCE_RESULTS_ONLY")
        if camera_id not in self._cameras:
            raise ValueError("CAMERA_SCOPE_DENIED")
        if (isinstance(start, bool) or isinstance(end, bool)
                or not math.isfinite(start) or not math.isfinite(end)
                or not self._time_range[0] <= start <= end <= self._time_range[1]):
            raise ValueError("GUIDANCE_TIME_SCOPE_DENIED")
        if behavior not in {b[0] for b in BEHAVIORS}:
            raise ValueError("GUIDANCE_BEHAVIOR_DENIED")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= MAX_FEATURES:
            raise ValueError("GUIDANCE_TOP_K_DENIED")
        targets = self._aliases.get(label.strip().casefold(), set())
        reasons: list[str] = []
        visited: list[str] = []
        edges: list[NavigationEdge] = []
        features: list[FeatureSummary] = []
        camera_queries = records_read = entries_touched = eligible = edges_touched = 0
        canonical_label: str | None = next(iter(targets)) if len(targets) == 1 else None
        if not targets or len(targets) > 1:
            reasons.append("UNKNOWN_LABEL" if not targets else "AMBIGUOUS_LABEL")
        else:
            visited, edges, reasons, edges_touched = self._navigate(
                self._node_ids["CAMERA", camera_id])
            if canonical_label in self._nodes and canonical_label not in visited:
                reasons.append("LABEL_OUTSIDE_BOUNDED_GRAPH")
            else:
                cameras = [self._nodes[r].resource_id for r in visited
                           if self._nodes[r].kind == "CAMERA"]
                if canonical_label in self._nodes:
                    target = self._nodes[canonical_label]
                    if target.kind == "CAMERA":
                        cameras = [target.resource_id]
                if len(cameras) > MAX_CAMERAS:
                    reasons.append("CAMERA_QUERY_BUDGET")
                seen_refs: set[str] = set()
                for selected_camera in cameras[:MAX_CAMERAS]:
                    response = self.scene.query(selected_camera, start, end)
                    receipt = response["retrieval"]
                    camera_queries += 1
                    records_read += receipt["records_read"]
                    entries_touched += receipt["index_entries_touched"]
                    if receipt["truncated"]:
                        reasons.append("SCOPED_INDEX_TRUNCATED")
                    for kind in ("events", "observations"):
                        for record in response[kind]:
                            ref = record.get("event_ref", record.get("observation_ref"))
                            if ref not in self._features:
                                raise ValueError("GUIDANCE_FEATURE_INDEX_STALE")
                            if ref in seen_refs:
                                continue
                            seen_refs.add(ref)
                            feature = self._features[ref]
                            if canonical_label == "observations" and feature.record_kind != (
                                "OBSERVATION"
                            ):
                                continue
                            if canonical_label in self._nodes:
                                target = self._nodes[canonical_label]
                                if (target.kind == "REGION"
                                        and target.resource_id not in feature.region_ids):
                                    continue
                            eligible += 1
                            if len(features) < top_k:
                                features.append(feature)
                if eligible > len(features):
                    reasons.append("FEATURE_TOP_K_BUDGET")
        if any(f.omitted_candidate_count for f in features):
            reasons.append("CANDIDATE_REF_BUDGET")
        if any(f.omitted_media_count for f in features):
            reasons.append("MEDIA_REF_BUDGET")
        needs_input = any(r in {"UNKNOWN_LABEL", "AMBIGUOUS_LABEL", "LABEL_OUTSIDE_BOUNDED_GRAPH"}
                          for r in reasons)
        actions = [BoundedAction(tool="get_event_detail", record_ref=f.record_ref)
                   for f in features if f.record_kind == "EVENT"][:2]
        agent_input = AgentInput(
            status="NEEDS_INPUT" if needs_input else "READY", label=canonical_label,
            scope=self._scope,
            selection=Selection(camera_id=camera_id, time_range=[start, end],
                                behavior=cast(Behavior, behavior), top_k=top_k),
            navigation_nodes=[self._nodes[r] for r in visited], navigation_edges=edges,
            features=features, allowed_next_actions=actions,
            telemetry=Telemetry(
                graph_nodes_visited=len(visited), graph_edges_touched=edges_touched,
                camera_queries=camera_queries, records_read=records_read,
                index_entries_touched=entries_touched, features_returned=len(features),
                truncation_reasons=list(dict.fromkeys(reasons)),
                scoped_inventory_complete=not reasons and self._topology_complete),
            instructions=_INSTRUCTIONS,
            uncertainty=["SYNTHETIC_ENGINEERING_ONLY", "USER_INTENT_IS_NOT_CLASSIFICATION",
                         "IDENTITY_UNCONFIRMED", "SCOPED_RETRIEVAL_IS_NOT_GRAPH_EXHAUSTIVENESS"],
        ).model_dump(mode="json")
        if len(json.dumps(agent_input, separators=(",", ":"), allow_nan=False).encode()) > (
            MAX_AGENT_INPUT_BYTES
        ):
            raise ValueError("GUIDANCE_CONTEXT_BYTE_BUDGET")
        return {"status": agent_input["status"], "agent_input": agent_input,
                "agent_output": mock_decide(agent_input)}


def mock_decide(agent_input: Json) -> Json:
    """Explicit mock decision: retain all supplied alternatives; no provider call."""
    value = AgentInput.model_validate(agent_input)
    return {
        "schema_version": "workbench.navigation.agent-output.v1", "provider": "LOCAL_MOCK",
        "decision": "NEEDS_INPUT" if value.status == "NEEDS_INPUT" else (
            "INSPECT_SCOPED_EVIDENCE" if value.features else "NO_SCOPED_EVIDENCE"),
        "selected_refs": [f.record_ref for f in value.features],
        "candidate_alternatives": [
            {"record_ref": f.record_ref, "ordered_candidate_refs": f.ordered_candidate_refs,
             "candidate_count": f.candidate_count,
             "omitted_candidate_count": f.omitted_candidate_count}
            for f in value.features if f.record_kind == "EVENT"
        ],
        "confirmed_identity": None, "behavior_verdict": "UNKNOWN",
        "uncertainty": copy.deepcopy(value.uncertainty),
        "next_bounded_actions": [action.model_dump(mode="json")
                                 for action in value.allowed_next_actions],
    }
