#!/usr/bin/env python3
"""Generate tiny explicit SYNTHETIC inputs for CQ-27's paired acceptance tests."""
import argparse
import base64
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from amidst.q1q5.yyin_main_pack import CAMERAS, canonical, sha


def make(output):
    output = Path(output).absolute()
    if output.resolve() != output or output.exists() or "SYNTHETIC" not in str(output):
        raise ValueError("New canonical SYNTHETIC directory required")
    output.mkdir()
    source = output / "source"
    source.mkdir()
    image = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl6ZLsAAAAASUVORK5CYII=")
    files, checks = {}, []
    for cam in CAMERAS:
        name = "images/static/" + cam + ".png"
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image)
        files[name] = sha(image)
        checks.append({"camera_id": cam, "static_image_ref": name, "static_image_sha256": sha(image),
            "car_question_eligible": cam in {"CAM_ENTRY", "CAM_EXT_CAR"},
            "pack_instruction": "SYNTHETIC測試畫面；不可用作正式題目。"})
    catalog = canonical({"fixture_role": "SYNTHETIC", "cameras": [{"camera_id": c} for c in CAMERAS]})
    path = source / "provenance/camera_catalog.json"
    path.parent.mkdir()
    path.write_bytes(catalog)
    files["provenance/camera_catalog.json"] = sha(catalog)
    manifest = canonical({"fixture_role": "SYNTHETIC", "files": files})
    (source / "MANIFEST.json").write_bytes(manifest)
    clock = {"schema_version": "q-demo.clock-mapping.v1", "mapping_kind": "DECLARED_DEMO_CLOCK",
        "run_id": "SYNTHETIC-A4", "clock_id": "SYNTHETIC-CLOCK", "source_duration_us": 50_000_000,
        "timezone": "Asia/Taipei", "rate": 1, "t0_us": 0, "wall_origin": "2026-11-01T14:00:00+08:00"}
    clock["content_sha256"] = sha(canonical(clock))
    freeze = {"fixture_role": "SYNTHETIC", "catalog_sha256": sha(catalog),
        "source_manifest_file_sha256": sha(manifest), "camera_ids": list(CAMERAS)}
    run = {"run_id": clock["run_id"], "clock_id": clock["clock_id"], "source_duration_us": 50_000_000,
        "clock_mapping_content_sha256": clock["content_sha256"], "clock_mapping_file_sha256": sha(canonical(clock)),
        "camera_catalog_sha256": sha(catalog), "camera_catalog_freeze_sha256": sha(canonical(freeze))}
    objects = {"fixture_role": "SYNTHETIC", "manifest_sha256": sha(manifest),
        "provenance_sha256": {"camera_catalog.json": sha(catalog)}, "camera_checks": checks}
    inputs = {"source_pack": {"path": str(source), "manifest_sha256": sha(manifest)}}
    for name, doc in (("clock", clock), ("run", run), ("catalog_receipt", freeze), ("object_list", objects)):
        raw = canonical(doc)
        path = output / (name + ".json")
        path.write_bytes(raw)
        inputs[name] = {"path": str(path), "sha256": sha(raw)}
    config = output / "inputs.json"
    config.write_bytes(canonical(inputs))
    return config


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    print(make(p.parse_args().output))
