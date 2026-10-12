"""Encode local diagnostic Blender reconstruction media from safe frozen pixel features."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from amidst.workbench.blender_motion_media import materialize_motion_artifacts
from amidst.workbench.blender_scene import BlenderSceneAdapter
from amidst.workbench.scenes import load_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    scenes = load_catalog(args.repo)
    receipts = []
    for scene in scenes.values():
        snapshot = scene.snapshot()
        if (not isinstance(scene, BlenderSceneAdapter)
                or not snapshot["capabilities"].get("frame_query")):
            continue
        site = snapshot["source_binding"]["site_id"]
        receipts.append(materialize_motion_artifacts(scene, args.output / site))
        print(json.dumps({"site_id": site, "status": "MATERIALIZED",
            "validation": receipts[-1]["validation"],
            "source_image_status": receipts[-1]["source_image_status"], "items": [
            {"kind": row["kind"], "sha256": row["sha256"], "byte_count": row["byte_count"]}
            for row in receipts[-1]["items"]]}, sort_keys=True), flush=True)
    if len(receipts) != 3:
        raise ValueError("THREE_BLENDER_SCENES_REQUIRED")


if __name__ == "__main__":
    main()
