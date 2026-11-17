"""Close producer output into a safe allowlist. No inference occurs in this process."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from amidst.q1q5.clock_mapping import ClockMapping, _content_hash
from render_r004_d124 import (
    json_bytes,
    no_symlink_components,
    png_safe,
    require,
    require_space,
    sha,
)
from r004_4actor_common import CATALOG_SHA, SOURCE_SHA


def put(path, raw):
    require_space(path.parent, len(raw) + 65536)
    no_symlink_components(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as f:
        f.write(raw)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--render-root", type=Path, required=True)
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--baseline-config-dir", type=Path, required=True)
    a = p.parse_args()
    require(sha(a.catalog) == CATALOG_SHA, "CATALOG_PIN")
    root = a.render_root / "bundle" / "safe"
    require(not root.exists(), "SAFE_BUNDLE_ALREADY_EXISTS")
    prepared = []
    for label, n, cams in [
        ("A4-1", 250, {"CAM_ENTRY", "CAM_EXT_CAR", "CAM_EXT_CLEAR", "CAM_W1"}),
        ("B4-1", 210, {"CAM_W1", "CAM_W2", "CAM_BRANCH", "CAM_R101_IN", "CAM_WIDE"}),
    ]:
        private = a.render_root / label / "gt_private"
        lock = json.loads((private / "LOCK.json").read_text())
        complete = json.loads((private / "completion.json").read_text())
        require(
            complete["complete"] and complete["completed_frames"] == n * len(cams),
            "RENDER_INCOMPLETE",
        )
        require(
            complete["source_sha256_after"] == lock["source_sha256"] == SOURCE_SHA, "SOURCE_PIN"
        )
        require(lock["catalog_sha256"] == CATALOG_SHA, "CATALOG_PIN")
        require(
            lock["driver_sha256"] == sha(a.repo / "scripts/render_r004_4actor.py"), "DRIVER_DRIFT"
        )
        run = json.loads((a.render_root / label / "safe/run.json").read_text())
        require(run["run_id"] == lock["run_id"] and set(run["camera_ids"]) == cams, "RUN_SCOPE")
        require(
            {(f["camera_id"], f["frame_index"]) for f in run["frames"]}
            == {(c, i) for c in cams for i in range(n)},
            "INCOMPLETE_GRID",
        )
        for f in run["frames"]:
            src = a.render_root / label / "safe" / f["relative_path"]
            require(not src.is_symlink() and sha(src) == f["sha256"], "RGB_PIN")
            sanitized, _ = png_safe(src.read_bytes())
            require(sanitized == src.read_bytes(), "RGB_NOT_SANITIZED")
        prepared.append((label, run))
    inventory = {}
    for label, run in prepared:
        clock = json.loads(
            (a.repo / f"configs/q1q5/clocks/r004_{label[:2].lower()}_v1.json").read_text()
        )
        clock.update(run_id=run["run_id"], clock_id=run["clock_id"])
        clock["content_sha256"] = _content_hash(clock)
        ClockMapping.from_document(clock, expected_run_id=run["run_id"])
        clock_rel = f"clocks/{label}.json"
        put(root / clock_rel, json_bytes(clock))
        inventory[clock_rel] = sha(root / clock_rel)
        frames = []
        for f in run["frames"]:
            name = f"rgb/{run['run_id']}/{f['camera_id']}/{f['frame_index']:06d}.png"
            dst = root / name
            require_space(dst.parent, 65536)
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.link(a.render_root / label / "safe" / f["relative_path"], dst, follow_symlinks=False)
            inventory[name] = f["sha256"]
            frames.append({**f, "relative_path": name})
        descriptor = {**run, "frames": frames, "clock_ref": clock_rel}
        descriptor_rel = f"runs/{label}.json"
        put(root / descriptor_rel, json_bytes(descriptor))
        inventory[descriptor_rel] = sha(root / descriptor_rel)
        baseline = json.loads((a.baseline_config_dir / f"{label}-config.json").read_text())
        names = [
            "profile",
            "formal_eligible",
            "formal_parameters",
            "formal_run_allowed",
            "human_approval_verified",
            "mode",
            "stride_samples",
            "index_grid_origin_frame",
            "index_score_floor",
            "query_min_score",
            "hsv_config",
            "parameters",
            "seed",
            "threads",
            "weights_sha256",
        ]
        cfg = {k: baseline[k] for k in names}
        cfg.update(
            scene_id=run["scene_id"],
            scene_revision="r004",
            run_id=run["run_id"],
            clock_id=run["clock_id"],
            run_descriptor=descriptor_rel,
            run_descriptor_sha256=inventory[descriptor_rel],
            clock_sha256=inventory[clock_rel],
            catalog_sha256=CATALOG_SHA,
        )
        cfg_rel = f"config/{label}.json"
        put(root / cfg_rel, json_bytes(cfg))
        inventory[cfg_rel] = sha(root / cfg_rel)
    put(root / "provenance/camera_catalog.json", a.catalog.read_bytes())
    inventory["provenance/camera_catalog.json"] = CATALOG_SHA
    graph = a.repo / "configs/q1q5/graphs/r004/camera_graph_v3_1.json"
    put(root / "provenance/camera_graph_v3_1.json", graph.read_bytes())
    inventory["provenance/camera_graph_v3_1.json"] = sha(graph)
    manifest = {
        "schema": "amidst.r004-4actor-safe.v1",
        "files": inventory,
        "runs": ["runs/A4-1.json", "runs/B4-1.json"],
        "source_blend_sha256": SOURCE_SHA,
        "catalog_sha256": CATALOG_SHA,
        "scope": "ENGINEERING_DEMO; identity UNCONFIRMED; physical navigation UNKNOWN",
    }
    put(root / "SAFE_MANIFEST.json", json_bytes(manifest))
    print("SAFE_PREPARED", len(inventory), sha(root / "SAFE_MANIFEST.json"), flush=True)


if __name__ == "__main__":
    main()
