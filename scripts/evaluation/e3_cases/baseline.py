"""Pixel-index-only B1 replay and user-authorized graph-distance fallback.

No case, annotation, renderer state or GT is accepted here. Join target truth only
in the separate evaluation finalizer after these unconditioned snapshots are frozen.
"""
from __future__ import annotations
from collections import deque
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))
from amidst.q1q5.detection_index import content_hash


def graph_ranking(graph, active):
    adjacent = {c["camera_id"]: set() for c in graph["cameras"]}
    for edge in graph["transitions"]:
        a, b = edge["from_camera_id"], edge["to_camera_id"]
        adjacent[a].add(b); adjacent[b].add(a)
    if active not in adjacent:
        return {"basis": "GRAPH_DISTANCE_FALLBACK", "status": "UNKNOWN_ORIGIN_OUTSIDE_GRAPH", "ranking": []}
    distances = {active: 0}; todo = deque([active])
    while todo:
        a = todo.popleft()
        for b in sorted(adjacent[a] - distances.keys()):
            distances[b] = distances[a] + 1; todo.append(b)
    ordered = sorted((c for c in distances if c != active), key=lambda c: (distances[c], c))
    return {"basis": "GRAPH_DISTANCE_FALLBACK", "status": "READY", "ranking": [
        {"camera_id": c, "rank": i, "path_distance_hops": distances[c]} for i, c in enumerate(ordered, 1)],
        "tie_policy": "camera_id ascending; representation only, no probability",
        "topology": "undirected adjacency, matching CameraScheduler; excludes current camera",
        "limitations": "Topological distance only, no approved physical path; CAM_ENTRY absent from graph; no F2 ranking."}


def main():
    import numpy as np
    from PIL import Image
    from amidst.live_mode.color import judge
    from amidst.live_mode.server import State
    from amidst.live_mode.candidates import TrackSelection
    from amidst.live_mode.tracker import Projector, load_cameras
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--cameras", required=True)
    ap.add_argument("--main-sha", required=True)
    ap.add_argument("--cases", nargs="+", required=True)
    a = ap.parse_args()
    graph_path = ROOT / "configs/q1q5/graphs/r004/camera_graph_v3.json"
    graph_bytes = graph_path.read_bytes(); graph = json.loads(graph_bytes)
    source = {"main_sha": a.main_sha, "graph_sha256": hashlib.sha256(graph_bytes).hexdigest(),
              "files": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in [
                  "src/amidst/live_mode/server.py", "src/amidst/live_mode/tracker.py",
                  "src/amidst/live_mode/candidates.py", "src/amidst/live_mode/scheduler.py",
                  "src/amidst/live_mode/color.py"]}}
    for case_id in a.cases:
        manifest_path = a.root / "indexes" / case_id / "detection_index.json"
        m = json.loads(manifest_path.read_text())
        raw = (manifest_path.parent / m["records_ref"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != m["records_file_sha256"]:
            raise ValueError("INDEX_PIN_MISMATCH")
        rgb = json.loads((a.root / "rgb" / case_id / "rgb_index.json").read_text())
        if hashlib.sha256((a.root / "rgb" / case_id / "rgb_index.json").read_bytes()).hexdigest() != m["rgb_index_sha256"]:
            raise ValueError("RGB_DESCRIPTOR_PIN_MISMATCH")
        frames = {(r["camera_id"], r["frame_index"]): r for r in rgb["records"]}
        camera_order = [f["cam"] for f in json.loads((a.root / f"{case_id}.replay1.wire.json").read_text())[0]["frames"]]
        grouped = {}
        for row in map(json.loads, raw.splitlines()):
            grouped.setdefault(row["frame_index"], []).append(row)
        state = State.__new__(State)
        state.projector = Projector(load_cameras(a.cameras))
        state.args = SimpleNamespace(gate_m=4.0, gate_growth=0.0, max_gate=8.0, advisor="off")
        state.selection = TrackSelection(); state.selection.start("red", False)
        state.tracker = state._new_tracker("red"); state.decider = None; state.pending_acquire = []
        results = []
        for tick, rows in sorted(grouped.items()):
            dets = {}; images = {}
            # Preserve registered camera order from RGB source, as the LIVE capture does.
            by_cam = {r["camera_id"]: r for r in rows}
            for cam in camera_order:
                row = by_cam[cam]; pin = frames[cam, tick]; pixel_bytes = (a.root / pin["relative_path"]).read_bytes()
                if hashlib.sha256(pixel_bytes).hexdigest() != row["rgb_file_sha256"]:
                    raise ValueError("INDEX_RGB_PIN_MISMATCH")
                import io
                image = Image.open(io.BytesIO(pixel_bytes)).convert("RGB"); images[cam] = image
                arr = np.asarray(image)
                dets[cam] = [{"bbox": d["bbox_xyxy_px"], "score": d["score"],
                    **judge(arr, d["bbox_xyxy_px"], .2)} for d in row["detections"]
                    if d["class_label"] == "person" and d["score"] >= (.05 if cam == "CAM_ENTRY" else .15)]
            result = state._infer_tracking(tick, tick / 5, dets, images, (320, 180))
            for image in images.values():
                image.close()
            snapshot = {"tick": tick, "timestamp_us": tick * 200000, "active_cam": state.tracker.active,
                        "tracking": result, **graph_ranking(graph, state.tracker.active),
                        "rule_camera_order": "NONE: merged LIVE exposes seen_cams, not a ranked K=3 camera list",
                        "source": source, "index_sha256": m["content_sha256"]}
            snapshot["snapshot_sha256"] = content_hash(snapshot)
            results.append(snapshot)
        target = a.root / "baseline" / f"{case_id}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(results, sort_keys=True, allow_nan=False) + "\n")
        print("BASELINE_FROZEN", case_id, len(results), flush=True)


if __name__ == "__main__":
    main()
