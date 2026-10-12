"""Encode local diagnostic Blender reconstruction media from safe frozen pixel features."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from amidst.workbench.blender_physical_media import materialize_physical_artifacts
from amidst.workbench.blender_physical_source import load_physical_source
from amidst.workbench.blender_scene import BlenderSceneAdapter
from amidst.workbench.scenes import load_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scenes = load_catalog(args.repo)
    selected = [scene for scene in scenes.values() if isinstance(scene, BlenderSceneAdapter)]
    if (len(selected) != 3 or {scene.snapshot()["source_binding"]["site_id"]
                              for scene in selected} != {"office", "classroom101", "auditorium"}):
        raise ValueError("THREE_BLENDER_SCENES_REQUIRED")
    for scene in selected:
        site = scene.snapshot()["source_binding"]["site_id"]
        scene.bind_physical(load_physical_source(args.repo, site))
    receipts = []
    for scene in selected:
        snapshot = scene.snapshot()
        if not snapshot["capabilities"].get("physical_cross_camera_reconstruction"):
            raise ValueError("PHYSICAL_SOURCE_UNAVAILABLE")
        site = snapshot["source_binding"]["site_id"]
        receipts.append(materialize_physical_artifacts(scene, args.output / site))
        print(json.dumps({"site_id": site, "status": "MATERIALIZED",
            "validation": receipts[-1]["validation"],
            "source_image_status": receipts[-1]["source_image_status"], "items": [
            {"kind": row["kind"], "sha256": row["sha256"], "byte_count": row["byte_count"]}
            for row in receipts[-1]["items"]]}, sort_keys=True), flush=True)
    if len(receipts) != 3:
        raise ValueError("THREE_BLENDER_SCENES_REQUIRED")


if __name__ == "__main__":
    main()
