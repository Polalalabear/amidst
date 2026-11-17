"""Index only hash-pinned safe RGB. No authored plan or producer private input is accepted."""

import argparse
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from amidst.q1q5.detection_index import OfficialRTDetrR18, build_detection_index, write_index
from amidst.q1q5.hsv_color import HSVConfig
from check_d124_demo_default import conformance, local_rule_tracks
from render_r004_d124 import json_bytes, no_symlink_components, require, require_space, sha


def canonical(d):
    return json.dumps(
        d, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode()


class FourActorSafeRun:
    def __init__(self, root, config, expected_manifest):
        self.root = root
        require(sha(root / "SAFE_MANIFEST.json") == expected_manifest, "SAFE_MANIFEST_PIN")
        safe = json.loads((root / "SAFE_MANIFEST.json").read_text())
        inventory = safe["files"]
        self.inventory = inventory
        for rel in inventory:
            self.safe_path(rel)
        require(config["run_descriptor"] in safe["runs"], "RUN_NOT_ALLOWLISTED")
        descriptor = json.loads(self.read(config["run_descriptor"]))
        require(
            descriptor["run_id"] == config["run_id"]
            and descriptor["clock_id"] == config["clock_id"],
            "RUN_CLOCK_PIN",
        )
        require(
            sha(root / config["run_descriptor"]) == config["run_descriptor_sha256"],
            "DESCRIPTOR_PIN",
        )
        require(inventory[descriptor["clock_ref"]] == config["clock_sha256"], "CLOCK_PIN")
        require(
            inventory["provenance/camera_catalog.json"] == config["catalog_sha256"], "CATALOG_PIN"
        )
        clock = json.loads(self.read(descriptor["clock_ref"]))
        require(
            clock["run_id"] == descriptor["run_id"]
            and clock["clock_id"] == descriptor["clock_id"]
            and clock["source_duration_us"] == descriptor["duration_us"],
            "CLOCK_CONTENT",
        )
        require(
            hashlib.sha256(self.read("provenance/camera_catalog.json")).hexdigest()
            == config["catalog_sha256"],
            "CATALOG_BYTES",
        )
        self.camera_ids = tuple(descriptor["camera_ids"])
        count = descriptor["sample_count_per_camera"]
        self._rows = {(f["camera_id"], f["frame_index"]): f for f in descriptor["frames"]}
        require(
            len(self._rows) == len(descriptor["frames"])
            and set(self._rows) == {(c, i) for c in self.camera_ids for i in range(count)},
            "FULL_SAFE_GRID",
        )
        require(
            all(inventory.get(f["relative_path"]) == f["sha256"] for f in self._rows.values()),
            "RGB_ALLOWLIST_PIN",
        )
        projection = [
            {"camera_id": c, "frame_index": i, "file_sha256": self._rows[c, i]["sha256"]}
            for c, i in sorted(self._rows)
        ]
        rgb_pin = hashlib.sha256(canonical(projection)).hexdigest()
        self.manifest = {
            "scene_id": descriptor["scene_id"],
            "run_id": descriptor["run_id"],
            "clock_id": descriptor["clock_id"],
            "sampling": {
                "fps": descriptor["fps"],
                "duration_s": descriptor["duration_us"] / 1e6,
                "sample_count_per_camera": count,
                "image_size_px": descriptor["image_size_px"],
            },
            "allowlist": [{"role": "rgb_index", "file_sha256": rgb_pin}],
        }
        self.files = {"rgb_index": {"records": projection, "missing": []}}

    def safe_path(self, rel):
        p = Path(rel)
        require(
            not p.is_absolute()
            and ".." not in p.parts
            and str(p) == rel
            and rel.split("/")[0] in {"rgb", "runs", "clocks", "config", "provenance"},
            "UNSAFE_INPUT_NAME",
        )
        path = self.root / p
        no_symlink_components(path)
        require(
            path.is_file() and path.resolve().is_relative_to(self.root.resolve()),
            "MISSING_SAFE_FILE",
        )
        return path

    def read(self, rel):
        path = self.safe_path(rel)
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == self.inventory[rel], "SAFE_BYTE_PIN")
        return raw

    def rgb_record(self, camera_id, frame_index):
        f = self._rows.get((camera_id, frame_index))
        return (
            {
                "file_sha256": f["sha256"],
                "timestamp_s": float(Fraction(frame_index, self.manifest["sampling"]["fps"])),
            }
            if f
            else None
        )

    def read_rgb(self, camera_id, frame_index):
        require_space(self.root)
        return self.read(self._rows[camera_id, frame_index]["relative_path"])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--safe-root", type=Path, required=True)
    p.add_argument("--safe-manifest-sha256", required=True)
    p.add_argument("--label", choices=["A4-1", "B4-1"], required=True)
    p.add_argument("--model-source", type=Path, required=True)
    p.add_argument("--weights", type=Path, required=True)
    a = p.parse_args()
    cfg_path = a.safe_root / f"config/{a.label}.json"
    cfg = json.loads(cfg_path.read_text())
    run = FourActorSafeRun(a.safe_root, cfg, a.safe_manifest_sha256)
    require(sha(cfg_path) == run.inventory[f"config/{a.label}.json"], "CONFIG_PIN")
    require(cfg["weights_sha256"] == sha(a.weights), "WEIGHTS_PIN")
    output = a.safe_root / "indexes" / a.label
    require(not output.exists(), "INDEX_OUTPUT_EXISTS")
    require_space(a.safe_root, 16 * 1024**2)
    hashes = {
        p.relative_to(a.model_source).as_posix(): sha(p)
        for p in (a.model_source / "src").rglob("*.py")
    }
    events = []
    minimum = require_space(a.safe_root)
    frames = 0

    def observe(stage, operation):
        nonlocal frames, minimum
        minimum = min(minimum, require_space(a.safe_root))
        t = time.monotonic_ns()
        result = operation()
        events.append({"stage": stage, "elapsed_ns": time.monotonic_ns() - t})
        if stage == "rgb_read":
            frames += 1
            if frames % 50 == 0:
                print("INDEX_PROGRESS", a.label, frames, flush=True)
        return result

    started = time.monotonic()
    predictor = OfficialRTDetrR18(
        a.model_source,
        a.weights,
        source_hashes=hashes,
        seed=cfg["seed"],
        threads=cfg["threads"],
        observer=observe,
    )
    artifact = build_detection_index(
        run,
        predictor,
        scene_revision="r004",
        stride_samples=cfg["stride_samples"],
        index_grid_origin_frame=cfg["index_grid_origin_frame"],
        index_score_floor=cfg["index_score_floor"],
        color_config=HSVConfig(**cfg["hsv_config"]),
        observer=observe,
    )
    rows = [json.loads(l) for l in artifact.records_bytes.splitlines()]
    require(all(r["frame_state"] == "INFERRED" for r in rows), "INCOMPLETE_INFERENCE")
    write_index(artifact, output)
    raw = (output / "detection_index.json").read_bytes()
    mechanical = conformance(raw, artifact.records_bytes, cfg)
    tracks = local_rule_tracks(artifact.manifest, artifact.records_bytes, cfg)
    with (output / "cx8_rule_only.json").open("xb") as f:
        f.write(canonical(tracks) + b"\n")
    replay = local_rule_tracks(artifact.manifest, artifact.records_bytes, cfg)
    require(canonical(tracks) == canonical(replay), "TRACK_REPLAY_MISMATCH")
    receipt = {
        "gt_read": False,
        "profile": "DEMO_DEFAULT",
        "formal_eligible": False,
        "safe_manifest_sha256": a.safe_manifest_sha256,
        "config_sha256": sha(cfg_path),
        "weights_sha256": sha(a.weights),
        "model_source_sha256": hashlib.sha256(canonical(hashes)).hexdigest(),
        "model_source_files": hashes,
        "stats": artifact.stats,
        "elapsed_s": time.monotonic() - started,
        "minimum_free_bytes": minimum,
        "code_git_sha": __import__("subprocess")
        .check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True)
        .strip(),
        "index_sha256": sha(output / "detection_index.json"),
        "records_sha256": sha(output / "detection_index.records.jsonl"),
        "local_tracks_sha256": sha(output / "cx8_rule_only.json"),
        "conformance": mechanical,
        "tracking_scope": tracks["scope"],
        "inference_inputs": "safe allowlisted RGB/run/clock/config/catalog only; no authored routes, geometry or producer private data",
    }
    for name, value in [("receipt.json", receipt), ("timings.json", events)]:
        require_space(output)
        with (output / name).open("xb") as f:
            f.write(json_bytes(value))
    import os

    os.link(output / "detection_index.records.jsonl", output / "records.jsonl")
    print("INDEX_COMPLETE", a.label, artifact.stats, len(tracks["tracks"]), flush=True)


if __name__ == "__main__":
    main()
