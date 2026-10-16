#!/usr/bin/env python3
"""Create a safe contact-control bundle from fresh renders; never copy RGB or GT."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from amidst.engineering.registry import opaque_ref
from amidst.workbench.blender_scene import (
    ValidationRunPin, _calibration, _file_sha, _fingerprint, _frame_path,
    _json_bytes, _sha, load_blender_scene, strip_png_text,
)
from amidst.workbench.source_presentation import SOURCE_SHA256


def materialize(template: Path, dataset_path: Path, output: Path, run_id: str,
                *, person_office_gap: bool = False):
    if output.exists():
        raise FileExistsError(output)
    # Inherit independently pinned floor/scale/display evidence, never a renderer plane.
    baseline = load_blender_scene(template)
    inputs = baseline.export_safe_inputs()
    manifest = json.loads((template / "manifest.json").read_bytes())
    source = Path(manifest["source_path"])
    before = _fingerprint(source)
    dataset_path = dataset_path.resolve()
    raw = dataset_path.read_bytes()
    data = json.loads(raw)
    policy = data["render_policy"]
    expected_role = "FULLY_OBSERVED_CONTROL"
    if person_office_gap:
        import math
        target = data["trajectory"]["target"]
        if (data["site_id"] != "office"
                or not run_id.startswith("blender-contact-control-office-person-")
                or data.get("run_id") != run_id
                or target["kind"] != "PERSON_SIZED_CYLINDER_CONFIGURED_NOT_HUMAN_CERTIFIED"
                or not math.isclose(target["height_scene_units"] * 0.0247, 1.70)
                or not math.isclose(target["radius_scene_units"] * 0.0247, 0.25)):
            raise ValueError("PERSON_OFFICE_RUN_CONFIG_MISMATCH")
        expected_role = "OFFICE_PERSON_SIZE_RERENDER_DIAGNOSTIC"
    if before["sha256"] != SOURCE_SHA256 or data["source_scene"]["sha256_before"] != SOURCE_SHA256 or data["source_scene"]["sha256_after"] != SOURCE_SHA256:
        raise ValueError("CONTACT_CONTROL_SOURCE_MISMATCH")
    if data["site_id"] != inputs["source_binding"]["site_id"] or data["sample_role"] != expected_role or data["sampling_fps"] != 5 or len(data["timestamps"]) != 50 or policy["source_scene_saved"] is not False or policy["geometry_frame"] != 220 or policy["geometry_subframe"] != 0:
        raise ValueError("CONTACT_CONTROL_DATASET_MISMATCH")
    inputs["source_binding"].update(dataset_sha256=_sha(raw), run_id=run_id)
    inputs["cameras"] = [{"camera_id": c["camera_id"], "camera_ref": opaque_ref("camera", run_id, c["camera_id"]),
                          "calibration": _calibration(c), "authority": "SOURCE_CAMERA_CALIBRATION",
                          "coverage_status": "UNKNOWN"} for c in data["cameras"]]
    ids = {c["camera_id"] for c in inputs["cameras"]}
    if len(ids) != 2:
        raise ValueError("CONTACT_CONTROL_CAMERA_COUNT")
    frames = []
    for index, timestamp in enumerate(data["timestamps"]):
        if timestamp["index"] != index or timestamp["timestamp"] != index/5 or len(timestamp["per_camera"]) != 2 or {r["camera_id"] for r in timestamp["per_camera"]} != ids:
            raise ValueError("CONTACT_CONTROL_FRAME_CLOCK")
        # Explicit renderer field allowlist: camera/time/render locator/hash only.
        for row in timestamp["per_camera"]:
            camera_id, render = row["camera_id"], row["render"]
            path = _frame_path(dataset_path.parent, camera_id, index, render["path"])
            image = path.read_bytes()
            if _sha(image) != render["sha256"]:
                raise ValueError("CONTACT_CONTROL_MEDIA_HASH")
            from PIL import Image
            with Image.open(path) as decoded:
                if decoded.mode != "RGB" or decoded.size != (960,540):
                    raise ValueError("CONTACT_CONTROL_RGB_FORMAT")
            served = strip_png_text(image)
            frames.append({"frame_ref": opaque_ref("frame",run_id,camera_id,str(index),render["sha256"]),
                           "camera_id": camera_id,"timestamp": index/5,"width":960,"height":540,
                           "sha256":render["sha256"],"byte_count":len(image),"served_sha256":_sha(served),
                           "served_byte_count":len(served),"local_path":str(path),
                           "origin":"BLENDER_CAMERA_RGB","data_kind":"SYNTHETIC"})
    inputs["frames"] = frames
    encoded = _json_bytes(inputs)
    pin = ValidationRunPin(inputs["source_binding"]["site_id"],run_id,_sha(raw),_sha(encoded))
    manifest.update(inputs_sha256=pin.inputs_sha256, source_integrity=before,
                    dataset_path=str(dataset_path), asset_root=str(dataset_path.parent),
                    dataset_sha256=pin.dataset_sha256,frame_count=100,rendered=False)
    if _fingerprint(source) != before or _file_sha(dataset_path) != pin.dataset_sha256:
        raise ValueError("CONTACT_CONTROL_INPUT_CHANGED")
    output.mkdir(parents=True)
    (output/"safe_inputs.json").write_bytes(encoded)
    (output/"manifest.json").write_bytes(_json_bytes(manifest))
    (output/"validation_pin.json").write_bytes(_json_bytes(asdict(pin)))
    loaded = load_blender_scene(output, validation_pin=pin)
    for frame in inputs["frames"]:
        loaded.media(frame["frame_ref"])
    return {"run_id":run_id,"dataset_sha256":pin.dataset_sha256,"safe_inputs_sha256":pin.inputs_sha256,
            "frame_count":len(frames),"loader":"PASS","all_media_hashes":"PASS",
            "source_unchanged":_fingerprint(source)==before,"gt_used_for_inference":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for flag in ("template", "dataset", "output"):
        parser.add_argument("--"+flag,type=Path,required=True)
    parser.add_argument("--run-id",required=True)
    parser.add_argument("--person-office-gap", action="store_true")
    args=parser.parse_args()
    print(json.dumps(materialize(args.template,args.dataset,args.output,args.run_id,
                                person_office_gap=args.person_office_gap),indent=2))


if __name__ == "__main__":
    main()
