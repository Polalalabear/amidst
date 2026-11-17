"""Observation scheduling from safe camera topology and backend tracking state only.

Graph adjacency is a capture hint, never physical travel or identity authority.
Uncovered cameras retain UNKNOWN topology and trigger a full registered-camera fallback.
"""

import hashlib
import json
from pathlib import Path

DEFAULT_GRAPH = (
    Path(__file__).resolve().parents[3] / "configs/q1q5/graphs/r004/camera_graph_v3.json"
)
DEFAULT_GRAPH_SHA256 = "9896be113bf6e2b5f2d9344f1227484674fda2c2bb983d32a70d8ffcc4adfc7e"
DEFAULT_EXPAND_EVERY = 1


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
        self, graph, *, expand_every=DEFAULT_EXPAND_EVERY, mode="adaptive", graph_sha256=None
    ):
        if expand_every < 1 or mode not in ("adaptive", "all"):
            raise ValueError("INVALID_SCHEDULE_POLICY")
        self.adj = {c["camera_id"]: set() for c in graph["cameras"]}
        for edge in graph["transitions"]:
            a, b = edge["from_camera_id"], edge["to_camera_id"]
            if a not in self.adj or b not in self.adj:
                raise ValueError("GRAPH_EDGE_CAMERA_UNKNOWN")
            # Capture adjacency, not an assertion that physical travel is bidirectional.
            self.adj[a].add(b)
            self.adj[b].add(a)
        self.expand_every, self.mode, self.graph_sha256 = expand_every, mode, graph_sha256

    def plan(self, active, lost_rounds, available):
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
            reason = "LOST_EXPAND" if radius > 1 else "ACTIVE_NEIGHBORS"
        return {
            "mode": self.mode,
            "camera_ids": [c for c in available if c in selected],
            "reason": reason,
            "lost_rounds": lost_rounds,
            "radius": radius,
            "graph_sha256": self.graph_sha256,
        }
