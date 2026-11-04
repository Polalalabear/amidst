"""Package only completed D124 RGB renders; producer journals remain private.

No tracking/indexing occurs here. New source-bound clocks preserve the declared
mapping. PNG hardlinks avoid a second physical RGB copy on the same filesystem.
Run the independent CX-7T D124 profile after reviewing and pinning these outputs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from amidst.q1q5.clock_mapping import ClockMapping, _content_hash
from render_r004_d124 import (AUTHORIZATION, MINIMUM_BYTES, ProducerError, json_bytes,
                              no_symlink_components, png_safe, require, require_space, sha)
from check_event_run_bundle import R004_BINDINGS, R004_RUNS, df_available


def exclusive(path, raw):
    no_symlink_components(path)
    require_space(path.parent, len(raw) + 65536)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(raw)


def completed_frames(root, scope, driver_sha, config_sha):
    """Validate full private producer closure before publishing any safe output."""
    private = root / scope["label"] / "gt_private"
    no_symlink_components(private)
    for name in ("LOCK.json", "completion.json", "render_r004_d124.py",
                 "producer_config.json", "frame_journal.jsonl"):
        no_symlink_components(private / name)
    lock = json.loads((private / "LOCK.json").read_bytes())
    completion = json.loads((private / "completion.json").read_bytes())
    run_id = scope["run_id"] + "-d124-v1"
    require(lock["run_id"] == run_id and lock["driver_sha256"] == driver_sha
            and lock["config_sha256"] == config_sha
            and lock["source_sha256"] == R004_BINDINGS["source_sha256"]
            and lock["freeze_sha256"] == R004_BINDINGS["freeze_sha256"]
            and lock["catalog_sha256"] == R004_BINDINGS["catalog_sha256"]
            and lock["original_run_id"] == scope["run_id"], "PRODUCER_LOCK_MISMATCH")
    require(sha(private / "render_r004_d124.py") == driver_sha
            and sha(private / "producer_config.json") == config_sha,
            "PRODUCER_SNAPSHOT_MISMATCH")
    expected = {(camera, i) for camera in scope["camera_ids"] for i in range(scope["frame_count"])}
    require(completion["render_complete"] is True
            and completion["run_id"] == run_id
            and completion["completed_frames"] == len(expected)
            and completion["expected_frames"] == len(expected)
            and completion["source_sha256_after"] == R004_BINDINGS["source_sha256"]
            and completion["freeze_sha256_after"] == R004_BINDINGS["freeze_sha256"],
            "FULL_RENDER_REQUIRED")
    rows = [json.loads(line) for line in (private / "frame_journal.jsonl").read_text().splitlines()]
    indexed = {(r["camera_id"], r["frame_index"]): r for r in rows}
    require(len(indexed) == len(rows) and set(indexed) == expected, "FULL_RENDER_GRID_REQUIRED")
    media = root / scope["label"] / "safe" / "media"
    no_symlink_components(media)
    actual = set()
    for path in media.rglob("*"):
        require(not path.is_symlink(), "SAFE_OUTPUT_SYMLINK")
        if path.is_file():
            actual.add(path.relative_to(media).as_posix())
    require(actual == {f"{cam}/{i:06d}.png" for cam, i in expected}, "EXTRA_SAFE_OUTPUT")
    inventory = []
    for camera in scope["camera_ids"]:
        for index in range(scope["frame_count"]):
            row = indexed[camera, index]
            require(type(row["frame_index"]) is int
                    and type(row["source_time_us"]) is int
                    and row["source_time_us"] == index * 200000, "SOURCE_GRID_CHANGED")
            path = media / camera / f"{index:06d}.png"
            raw = path.read_bytes()
            sanitized, pixel_sha = png_safe(raw)
            require(sanitized == raw and hashlib.sha256(raw).hexdigest() == row["safe_sha256"]
                    and pixel_sha == row["pixel_chunks_sha256"], "SAFE_PIXEL_PIN_MISMATCH")
            inventory.append({"camera_id": camera, "frame_index": index,
                              "filename": f"media/{camera}/{index:06d}.png",
                              "file_sha256": row["safe_sha256"], "source_time_us": index * 200000})
    return lock, inventory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-root", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    no_symlink_components(args.render_root)
    no_symlink_components(args.config)
    no_symlink_components(args.catalog)
    root = args.render_root.absolute()
    require_space(root, 8 * 1024**2)
    config_sha = sha(args.config)
    driver_sha = sha(ROOT / "scripts/render_r004_d124.py")
    config = json.loads(args.config.read_bytes())
    require(config["authorization_ref"] == AUTHORIZATION
            and sha(args.catalog) == R004_BINDINGS["catalog_sha256"], "PACKAGE_SOURCE_PIN_MISMATCH")
    telemetry = []
    no_symlink_components(root / "gt_private/control")
    for path in sorted((root / "gt_private/control").glob("*.json")):
        require(not path.is_symlink(), "CONTROL_SYMLINK")
        record = json.loads(path.read_bytes())
        require(record["exit_code"] == 0 and record["stopped_below_8_gib"] is False
                and record["disk_min_available_bytes"] >= MINIMUM_BYTES, "RENDER_DISK_OR_EXIT_FAILURE")
        if record["full"]:
            require(df_available(record["before_df_k"]) >= 19 * 1024**3 // 2,
                    "FULL_START_BELOW_9_5_GIB")
        telemetry.append(record)
    full = {r["invocation"]: r for r in telemetry if r["full"]}
    require(set(full) == {"A4-full", "B4-full"}, "FULL_RENDER_TELEMETRY_REQUIRED")
    # Validate all frames and locks before creating the new bundle.
    prepared = [(scope, *completed_frames(root, scope, driver_sha, config_sha)) for scope in R004_RUNS]
    bundle, mechanical = root / "bundle", root / "mechanical"
    require(not bundle.exists() and not mechanical.exists(), "PACKAGE_OUTPUT_ALREADY_EXISTS")
    safe = bundle / "safe_bundle"
    files, runs, pins = {}, [], {}
    for scope, lock, inventory in prepared:
        label, run_id = scope["label"], lock["run_id"]
        letter = "a4" if label == "A4-1" else "b4"
        clock = json.loads((ROOT / f"configs/q1q5/clocks/r004_{letter}_v1.json").read_bytes())
        require(sha(ROOT / f"configs/q1q5/clocks/r004_{letter}_v1.json") == scope["clock_sha256"],
                "SOURCE_CLOCK_PIN_MISMATCH")
        clock.update(run_id=run_id, clock_id=config["runs"][label]["new_clock_id"])
        clock["content_sha256"] = _content_hash(clock)
        ClockMapping.from_document(clock, expected_run_id=run_id)
        clock_ref = f"clocks/r004_{letter}_d124_v1.json"
        raw_clock = json_bytes(clock)
        exclusive(safe / clock_ref, raw_clock)
        files[clock_ref] = hashlib.sha256(raw_clock).hexdigest()
        frames = []
        for row in inventory:
            name = f"rgb/{run_id}/{row['camera_id']}/frame_{row['frame_index']:06d}.png"
            target = safe / name
            source = root / label / "safe" / row["filename"]
            require_space(target.parent, 65536)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(source, target, follow_symlinks=False)
            files[name] = row["file_sha256"]
            frames.append({key: row[key] for key in ("camera_id", "frame_index", "file_sha256")}
                          | {"filename": name})
        descriptor = {"run_id": run_id, "label": label, "camera_ids": scope["camera_ids"],
                      "catalog_sha256": R004_BINDINGS["catalog_sha256"], "clock_ref": clock_ref,
                      "sampling": {"fps": 5}, "frames": frames}
        run_ref = f"runs/{label}.json"
        raw_descriptor = json_bytes(descriptor)
        exclusive(safe / run_ref, raw_descriptor)
        files[run_ref] = hashlib.sha256(raw_descriptor).hexdigest()
        inventory_ref = f"evidence/{label}-inventory.json"
        raw_inventory = json_bytes(inventory)
        exclusive(mechanical / inventory_ref, raw_inventory)
        declaration = {"schema_version": "r004.render-run-declaration.d124.v1",
                       "run_id": run_id, "parent_run_id": scope["run_id"], "clock_id": clock["clock_id"],
                       "authorization_ref": AUTHORIZATION, "source_sha256": R004_BINDINGS["source_sha256"],
                       "catalog_sha256": R004_BINDINGS["catalog_sha256"],
                       "producer_code_sha256": driver_sha, "producer_config_sha256": config_sha,
                       "original_run_declaration_sha256": scope["run_declaration_sha256"],
                       "producer_script_sha256": scope["producer_script_sha256"],
                       "source_duration_us": scope["source_duration_us"], "fps": 5,
                       "sample_count_per_camera": scope["frame_count"], "camera_ids": scope["camera_ids"]}
        declaration_raw = json_bytes(declaration)
        exclusive(root / label / "gt_private/new_run_declaration.json", declaration_raw)
        pins[label] = {"clock_id": clock["clock_id"], "clock_sha256": files[clock_ref],
                       "run_declaration_sha256": hashlib.sha256(declaration_raw).hexdigest(),
                       "source_inventory_sha256": hashlib.sha256(raw_inventory).hexdigest()}
        runs.append({**pins[label], "run_id": run_id, "parent_run_id": scope["run_id"],
                     "source_clock_sha256": scope["clock_sha256"],
                     "source_run_declaration_sha256": scope["run_declaration_sha256"],
                     "producer_script_sha256": scope["producer_script_sha256"],
                     "source_inventory_ref": inventory_ref,
                     "render_before_source_sha256": R004_BINDINGS["source_sha256"],
                     "render_after_source_sha256": R004_BINDINGS["source_sha256"],
                     "disk_min_available_bytes": min(r["disk_min_available_bytes"] for r in telemetry
                                                     if r["invocation"].startswith(letter.upper()+"-"))})
    catalog_ref = "provenance/camera_catalog.json"
    exclusive(safe / catalog_ref, args.catalog.read_bytes())
    files[catalog_ref] = R004_BINDINGS["catalog_sha256"]
    manifest_raw = json_bytes({"files": files, "runs": [f"runs/{r['label']}.json" for r in R004_RUNS]})
    exclusive(safe / "manifest.json", manifest_raw)
    receipt = {"profile": "r004-a4b4-d124", "classification": "ENGINEERING", "projection": "D124",
               "human_approval_verified": False, "allowed_purposes": [],
               "bindings": {**R004_BINDINGS, "render_ref": AUTHORIZATION, "projection_ref": AUTHORIZATION,
                            "source_render_ref": R004_BINDINGS["render_ref"],
                            "producer_code_sha256": driver_sha, "producer_config_sha256": config_sha},
               "before_df_k": full["A4-full"]["before_df_k"],
               "after_df_k": subprocess.check_output(["df", "-k", str(root)], text=True),
               "safe_manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(), "runs": runs}
    exclusive(mechanical / "receipt.json", json_bytes(receipt))
    new_pins = {"producer_code_sha256": driver_sha, "producer_config_sha256": config_sha, "runs": pins}
    exclusive(mechanical / "checker_pins.json", json_bytes(new_pins))
    print(json.dumps({"status": "PACKAGED_NOT_VALIDATED", "safe_manifest_sha256": receipt["safe_manifest_sha256"],
                      "safe_manifest_entries": len(files), "frame_count": sum(len(x[2]) for x in prepared),
                      "receipt_sha256": sha(mechanical / "receipt.json"), "checker_pins": new_pins}, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProducerError as error:
        print("D124_PACKAGE_STOP", str(error))
        raise SystemExit(2) from error
