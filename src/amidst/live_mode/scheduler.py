"""Observation scheduling from safe camera topology and backend tracking state only.

Graph adjacency is a capture hint, never physical travel or identity authority.
Uncovered cameras retain UNKNOWN topology and trigger a full registered-camera fallback.
"""

import hashlib
import json
import math
from pathlib import Path

DEFAULT_GRAPH = (
    Path(__file__).resolve().parents[3] / "configs/q1q5/graphs/r004/camera_graph_v3.json"
)
DEFAULT_GRAPH_SHA256 = "9896be113bf6e2b5f2d9344f1227484674fda2c2bb983d32a70d8ffcc4adfc7e"
DEFAULT_EXPAND_EVERY = 1
DEFAULT_RECENT_CANDIDATE_S = 2.0
# Historical replay_schedule imports remain supported; internal state is colour neutral.
DEFAULT_RECENT_RED_S = DEFAULT_RECENT_CANDIDATE_S


def load_graph(path, expected_sha256, catalog_sha256, camera_ids):
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise ValueError("GRAPH_HASH_MISMATCH")
    doc = json.loads(raw)
    if doc.get("schema_version") != "q-demo.camera-transition-graph.v1":
        raise ValueError("CAMERA_GRAPH_SCHEMA_REQUIRED")
    if "RUNTIME_INFERENCE" in doc.get("must_not_enter", []):
        raise ValueError("GRAPH_RUNTIME_FORBIDDEN")
    if doc.get("camera_catalog_sha256") != catalog_sha256:
        raise ValueError("GRAPH_CATALOG_MISMATCH")
    nodes = {c["camera_id"] for c in doc["cameras"]}
    if not nodes.issubset(camera_ids):
        raise ValueError("GRAPH_CAMERA_NOT_REGISTERED")
    return doc, {
        "graph_sha256": digest,
        "graph_id": doc.get("graph_id"),
        "uncovered_cameras": sorted(set(camera_ids) - nodes),
    }


class CameraScheduler:
    def __init__(
        self,
        graph,
        *,
        expand_every=DEFAULT_EXPAND_EVERY,
        mode="adaptive",
        graph_sha256=None,
        recent_candidate_s=DEFAULT_RECENT_CANDIDATE_S,
        target_color="red",
        **legacy,
    ):
        # Preserve the existing replay entry point without editing frozen B1 callers.
        if legacy:
            if set(legacy) != {"recent_red_s"}:
                raise TypeError("UNKNOWN_SCHEDULE_ARGUMENT")
            recent_candidate_s = legacy["recent_red_s"]
        if expand_every < 1 or mode not in ("adaptive", "all"):
            raise ValueError("INVALID_SCHEDULE_POLICY")
        if not math.isfinite(recent_candidate_s) or recent_candidate_s < 0:
            raise ValueError("INVALID_RECENT_CANDIDATE_WINDOW")
        self.recent_candidate_s = recent_candidate_s
        if target_color not in ("red", "blue"):
            raise ValueError("INVALID_TARGET_COLOR")
        self.target_color = target_color
        self.reset()
        self.adj = {c["camera_id"]: set() for c in graph["cameras"]}
        for edge in graph["transitions"]:
            a, b = edge["from_camera_id"], edge["to_camera_id"]
            if a not in self.adj or b not in self.adj:
                raise ValueError("GRAPH_EDGE_CAMERA_UNKNOWN")
            # Capture adjacency, not an assertion that physical travel is bidirectional.
            self.adj[a].add(b)
            self.adj[b].add(a)
        self.expand_every, self.mode, self.graph_sha256 = expand_every, mode, graph_sha256

    def set_target_color(self, color):
        if color not in ("red", "blue"):
            raise ValueError("INVALID_TARGET_COLOR")
        if color != self.target_color:
            self.target_color = color
            self.reset()

    def reset(self):
        self._recent_candidates = {}
        self._clock = None

    def _advance(self, t_s):
        if t_s is None:
            return self._clock
        if not math.isfinite(t_s) or t_s < 0:
            raise ValueError("CAPTURE_CLOCK_REQUIRED")
        if self._clock is not None and t_s < self._clock:
            self.reset()
        self._clock = t_s
        self._recent_candidates = {
            cam: seen for cam, seen in self._recent_candidates.items() if t_s - seen <= self.recent_candidate_s
        }
        return t_s

    def observe(self, detections, t_s):
        """Retain cameras with a pixel-derived session-colour candidate, not a confirmed identity.

        No position, GT, actor, scene or graph-edge inference enters this memory.
        The server supplies only registered cameras it actually inferred this round.
        """
        self._advance(t_s)
        if self.recent_candidate_s:
            for cam, rows in detections.items():
                if any(row.get("color") == self.target_color for row in rows):
                    self._recent_candidates[cam] = t_s

    def plan(self, active, lost_rounds, available, *, t_s=None):
        self._advance(t_s)
        available = list(dict.fromkeys(available))
        lost_rounds = max(0, int(lost_rounds))
        radius = 1 + lost_rounds // self.expand_every
        if self.mode == "all":
            selected = set(available)
            reason = "ALL_CAMERAS"
        elif active is None:
            selected = set(available)
            reason = "INITIAL_SEARCH"
        elif active not in self.adj:
            selected = set(available)
            reason = "GRAPH_SCOPE_UNKNOWN"
        elif lost_rounds >= 2 * self.expand_every:
            selected = set(available)
            reason = "LOST_ALL"
        else:
            selected = {active}
            front = {active}
            for _ in range(radius):
                front = {n for c in front for n in self.adj[c]} - selected
                selected.update(front)
            # Candidate coverage supplements graph adjacency without inventing topology.
            selected.update(self._recent_candidates)
            reason = "LOST_EXPAND" if radius > 1 else "ACTIVE_NEIGHBORS"
        return {
            "mode": self.mode,
            "camera_ids": [c for c in available if c in selected],
            "reason": reason,
            "lost_rounds": lost_rounds,
            "radius": radius,
            "graph_sha256": self.graph_sha256,
        }
