"""Synthetic packaging closure checks; no actual producer plans, GT or media."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import zlib

import pytest


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
SPEC = importlib.util.spec_from_file_location("package_d124", REPO / "scripts/package_r004_d124.py")
PACKAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACKAGE)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value))


def synthetic_png(color=17):
    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))
    pixels = (b"\x00" + bytes([color]) * (960 * 3)) * 540
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 960, 540, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


@pytest.fixture
def full_render(tmp_path):
    root = tmp_path / "new-render"
    scope = {"label": "SYNTHETIC", "run_id": "synthetic-parent",
             "camera_ids": ["SYNTHETIC_CAM"], "frame_count": 2}
    private = root / scope["label"] / "gt_private"
    media = root / scope["label"] / "safe/media/SYNTHETIC_CAM"
    private.mkdir(parents=True)
    media.mkdir(parents=True)
    driver, config = b"synthetic driver bytes", b"synthetic config bytes"
    driver_sha, config_sha = digest(driver), digest(config)
    (private / "render_r004_d124.py").write_bytes(driver)
    (private / "producer_config.json").write_bytes(config)
    lock = {"run_id": "synthetic-parent-d124-v1", "original_run_id": "synthetic-parent",
            "driver_sha256": driver_sha, "config_sha256": config_sha,
            **{key: PACKAGE.R004_BINDINGS[key] for key in (
                "source_sha256", "freeze_sha256", "catalog_sha256")}}
    write_json(private / "LOCK.json", lock)
    completion = {"render_complete": True, "run_id": lock["run_id"], "completed_frames": 2,
                  "expected_frames": 2, "source_sha256_after": lock["source_sha256"],
                  "freeze_sha256_after": lock["freeze_sha256"]}
    write_json(private / "completion.json", completion)
    rows = []
    for index in range(2):
        raw = synthetic_png(17 + index)
        (media / f"{index:06d}.png").write_bytes(raw)
        _, pixel_sha = PACKAGE.png_safe(raw)
        rows.append({"camera_id": "SYNTHETIC_CAM", "frame_index": index,
                     "source_time_us": index * 200000, "safe_sha256": digest(raw),
                     "pixel_chunks_sha256": pixel_sha, "producer_only": "SYNTHETIC_PRIVATE_MARKER"})
    (private / "frame_journal.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
    return root, scope, driver_sha, config_sha, private, media, completion, rows


def inspect(fixture):
    return PACKAGE.completed_frames(*fixture[:4])


def test_full_closure_returns_only_whitelisted_safe_inventory_fields(full_render):
    _, inventory = inspect(full_render)
    assert len(inventory) == 2
    assert all(set(row) == {"camera_id", "frame_index", "filename", "file_sha256", "source_time_us"}
               for row in inventory)
    assert "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(inventory)
    assert [row["source_time_us"] for row in inventory] == [0, 200000]


def test_preview_cannot_be_packaged_as_full_render(full_render):
    private, completion = full_render[4], full_render[6]
    write_json(private / "completion.json", completion | {"render_complete": False})
    with pytest.raises(PACKAGE.ProducerError, match="FULL_RENDER_REQUIRED"):
        inspect(full_render)


def test_full_claim_cannot_hide_missing_grid_sample(full_render):
    private, rows = full_render[4], full_render[7]
    (private / "frame_journal.jsonl").write_text(json.dumps(rows[0]) + "\n")
    with pytest.raises(PACKAGE.ProducerError, match="FULL_RENDER_GRID_REQUIRED"):
        inspect(full_render)


def test_new_valid_png_with_different_pixels_is_rejected(full_render):
    (full_render[5] / "000000.png").write_bytes(synthetic_png(100))
    with pytest.raises(PACKAGE.ProducerError, match="SAFE_PIXEL_PIN_MISMATCH"):
        inspect(full_render)


def test_even_unreferenced_safe_output_is_rejected(full_render):
    (full_render[5] / "unexpected.txt").write_text("synthetic")
    with pytest.raises(PACKAGE.ProducerError, match="EXTRA_SAFE_OUTPUT"):
        inspect(full_render)


@pytest.mark.parametrize("key", ["run_id", "original_run_id", "driver_sha256", "config_sha256",
                               "source_sha256", "freeze_sha256", "catalog_sha256"])
def test_wrong_lock_cannot_be_relabelled_as_new_render(full_render, key):
    path = full_render[4] / "LOCK.json"
    write_json(path, json.loads(path.read_bytes()) | {key: "WRONG"})
    with pytest.raises(PACKAGE.ProducerError, match="PRODUCER_LOCK_MISMATCH"):
        inspect(full_render)


@pytest.mark.parametrize("filename", ["render_r004_d124.py", "producer_config.json"])
def test_changed_snapshot_is_rejected(full_render, filename):
    (full_render[4] / filename).write_bytes(b"changed")
    with pytest.raises(PACKAGE.ProducerError, match="PRODUCER_SNAPSHOT_MISMATCH"):
        inspect(full_render)


@pytest.mark.parametrize("location", ["private", "media", "LOCK.json", "frame_journal.jsonl"])
def test_symlinked_input_components_are_rejected(full_render, location):
    private, media = full_render[4], full_render[5].parent
    target = private if location == "private" else media if location == "media" else private / location
    saved = target.with_name(target.name + "-retained")
    target.rename(saved)
    target.symlink_to(saved, target_is_directory=saved.is_dir())
    with pytest.raises(PACKAGE.ProducerError, match="OUTPUT_SYMLINK"):
        inspect(full_render)
