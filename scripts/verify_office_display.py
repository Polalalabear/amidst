"""Read-only Office regression against existing lawful RGB/physical inputs; no GT access."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))


def main():
    from office_demo_backend import load_scene

    from amidst.workbench.blender_physical_source import load_physical_source
    from amidst.workbench.office_display import attach_office_display

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    bundle = args.evidence / "data/engineering/local_run/blender_camera_v1/office"
    fixture = json.loads((REPO / "configs/office_demo_fixture_v1.json").read_bytes())
    before_hash = hashlib.sha256((bundle / "safe_inputs.json").read_bytes()).hexdigest()
    scene = load_scene(bundle, fixture)
    scene.bind_physical(load_physical_source(args.evidence, "office"))
    cameras = fixture["camera_ids"]

    def evidence():
        return {"inputs": scene.export_safe_inputs(), "scope": scene.live_scope(),
                "queries": [scene.query(c, 0, 9.8) for c in cameras],
                "top_k": [scene.cross_camera_reconstruction(cameras, 0, 9.8, k)
                          for k in (1, 3, 5)],
                "physical_review": scene.physical_review(cameras, 0, 9.8)}

    original_snapshot, original_evidence = scene.snapshot(), evidence()
    attach_office_display(scene, REPO)
    snapshot = scene.snapshot()
    display = snapshot["presentation"].pop("supplemental_display")
    assert snapshot == original_snapshot, "Original Office snapshot changed"
    assert evidence() == original_evidence, "Observations/candidates/physical evidence changed"
    assert hashlib.sha256((bundle / "safe_inputs.json").read_bytes()).hexdigest() == before_hash
    assert before_hash == fixture["safe_inputs_sha256"]
    observations = [r for q in original_evidence["queries"] for r in q["observations"]]
    assert not [o for o in observations if 4.6 <= o["timestamp"] <= 8.4]
    print(json.dumps({"status": "PASS", "office_safe_inputs_sha256": before_hash,
                      "office_snapshot_unchanged": True, "all_observation_fields_unchanged": True,
                      "top_k_1_3_5_unchanged": True, "physical_review_unchanged": True,
                      "gap_4_6_to_8_4_missing": True,
                      "max_transform_error_metres": max(r["transform_max_error_metres"]
                                                        for r in display["instances"]),
                      "supplemental_bounds_metres": display["bounds_metres"],
                      "asset_sha256": display["asset_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
