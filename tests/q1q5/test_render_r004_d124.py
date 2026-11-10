"""Pure producer checks with synthetic inputs; no Blender, media or private data."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
from types import SimpleNamespace
import zlib

import pytest


REPO = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("render_d124", REPO / "scripts/render_r004_d124.py")
PRODUCER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PRODUCER)


def points(*rows):
    return [{"planned_source_time_us": t, "foot_anchor_world_m": xyz} for t, xyz in rows]


def chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def png(*extra, pixels=b"\x00\x11\x22\x33"):
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + b"".join(extra) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b""))


def test_motion_preserves_linear_position_turns_at_boundary_and_holds_on_stops():
    route = points((0, [1, 2, 0]), (10, [1, 2, 0]), (20, [3, 2, 0]),
                   (30, [3, 4, 0]), (40, [3, 4, 0]), (50, [1, 4, 0]))
    position, yaw = PRODUCER.route_pose(route, 5, initial_yaw=0.7)
    assert position == [1, 2, 0] and yaw == 0.7
    assert PRODUCER.route_pose(route, 15) == ([2, 2, 0], 0)
    assert PRODUCER.route_pose(route, 20) == ([3, 2, 0], math.pi / 2)
    assert PRODUCER.route_pose(route, 25) == ([3, 3, 0], math.pi / 2)
    assert PRODUCER.route_pose(route, 35) == ([3, 4, 0], math.pi / 2)
    assert PRODUCER.route_pose(route, 40) == ([3, 4, 0], math.pi)
    assert PRODUCER.route_pose(route, 50) == ([1, 4, 0], math.pi)


def test_final_stop_keeps_last_direction_and_front_axis_is_explicit():
    route = points((0, [0, 0, 0]), (10, [0, -2, 0]), (20, [0, -2, 0]))
    assert PRODUCER.route_pose(route, 20)[1] == -math.pi / 2
    assert PRODUCER.route_pose(route, 5, front_axis="+Y")[1] == -math.pi
    with pytest.raises(PRODUCER.ProducerError, match="FRONT_AXIS_UNRESOLVED"):
        PRODUCER.route_pose(route, 5, front_axis="UNKNOWN")
    for time in (-1, 21):
        with pytest.raises(PRODUCER.ProducerError, match="NO_ROUTE_EXTRAPOLATION"):
            PRODUCER.route_pose(route, time)


@pytest.mark.parametrize("route", [points((0, [0, 0, 0])),
    points((0, [0, 0, 0]), (0, [1, 0, 0])),
    points((0, [0, 0, 0]), (1, [float("nan"), 0, 0]))])
def test_bad_route_is_rejected(route):
    with pytest.raises(PRODUCER.ProducerError):
        PRODUCER.validate_waypoints(route)


def test_disk_thresholds_at_boundaries(tmp_path):
    floor, start, reserve = PRODUCER.MINIMUM_BYTES, PRODUCER.FULL_START_BYTES, 32 * 1024**2
    disk = lambda free: lambda _: SimpleNamespace(free=free)
    assert PRODUCER.require_start_space(tmp_path, False, reserve, disk_usage=disk(start)) == start
    with pytest.raises(PRODUCER.ProducerError, match="STOP_BELOW_8_GIB_OR_FRAME_RESERVE"):
        PRODUCER.require_start_space(tmp_path, False, reserve, disk_usage=disk(start - 1))
    assert PRODUCER.require_start_space(tmp_path, True, reserve, disk_usage=disk(floor + reserve)) == floor + reserve
    assert PRODUCER.require_space(tmp_path, disk_usage=disk(floor)) == floor
    for free in (floor - 1, floor + reserve - 1):
        with pytest.raises(PRODUCER.ProducerError):
            PRODUCER.require_space(tmp_path, reserve, disk_usage=disk(free))


def test_metadata_is_stripped_without_changing_idat_or_pixels():
    clean = png()
    annotated = png(chunk(b"tEXt", b"Comment\x00PRIVATE_LOCATOR"),
                    chunk(b"iTXt", b"Other\x00\x00\x00\x00\x00PRIVATE_LOCATOR"),
                    chunk(b"eXIf", b"synthetic-exif"))
    safe, pixel_hash = PRODUCER.png_safe(annotated, (1, 1))
    assert safe == clean
    assert pixel_hash == hashlib.sha256(zlib.compress(b"\x00\x11\x22\x33")).hexdigest()
    assert b"PRIVATE_LOCATOR" not in safe


@pytest.mark.parametrize("raw", [png()[:-1], png() + b"extra", png(chunk(b"ABCD", b"x")),
                                  png(pixels=b"\x05\x11\x22\x33"), png(pixels=b"\x00\x11")])
def test_malformed_png_is_rejected(raw):
    with pytest.raises(PRODUCER.ProducerError):
        PRODUCER.png_safe(bytes(raw), (1, 1))


def test_crc_and_grid_dimensions_are_verified():
    raw = bytearray(png())
    raw[20] ^= 1
    with pytest.raises(PRODUCER.ProducerError, match="PNG_CRC"):
        PRODUCER.png_safe(bytes(raw), (1, 1))
    with pytest.raises(PRODUCER.ProducerError, match="PNG_FORMAT"):
        PRODUCER.png_safe(png())


def test_pinned_bytes_and_symlink_are_fail_closed(tmp_path):
    path = tmp_path / "pin.json"
    path.write_bytes(b"synthetic")
    pin = hashlib.sha256(b"synthetic").hexdigest()
    assert PRODUCER.read_pinned(path, pin) == b"synthetic"
    path.write_bytes(b"changed")
    with pytest.raises(PRODUCER.ProducerError, match="INPUT_PIN_MISMATCH"):
        PRODUCER.read_pinned(path, pin)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(PRODUCER.ProducerError, match="INPUT_PIN_MISMATCH"):
        PRODUCER.read_pinned(link, PRODUCER.sha(path))


def test_resume_requires_exact_lock_and_never_accepts_existing_root_without_resume(tmp_path):
    root = tmp_path / "new-run"
    lock = {"driver_sha256": "1" * 64, "config_sha256": "2" * 64}
    PRODUCER.validate_output_resume(root, lock, False)
    (root / "gt_private").mkdir(parents=True)
    (root / "gt_private/LOCK.json").write_text(json.dumps(lock))
    with pytest.raises(PRODUCER.ProducerError, match="EXISTING_OUTPUT_REQUIRES_RESUME"):
        PRODUCER.validate_output_resume(root, lock, False)
    PRODUCER.validate_output_resume(root, lock, True)
    with pytest.raises(PRODUCER.ProducerError, match="RESUME_LOCK_MISMATCH"):
        PRODUCER.validate_output_resume(root, lock | {"config_sha256": "3" * 64}, True)
    (root / "safe").symlink_to(tmp_path)
    with pytest.raises(PRODUCER.ProducerError, match="OUTPUT_SYMLINK"):
        PRODUCER.validate_output_resume(root, lock, True)


@pytest.mark.parametrize("selection", ["-1", "1-0", "5", "1-5", "", "1,word"])
def test_frame_selectors_cannot_add_frames(selection):
    with pytest.raises(PRODUCER.ProducerError):
        PRODUCER.parse_frame_indices(selection, 5)


def test_frame_selector_and_producer_grid_are_explicit():
    assert PRODUCER.parse_frame_indices(None, 5) == [0, 1, 2, 3, 4]
    assert PRODUCER.parse_frame_indices("0,2-4,2", 5) == [0, 2, 3, 4]
    config = json.loads((REPO / "configs/q1q5/producers/r004_d124_v1.json").read_bytes())
    assert config["authorization_ref"] == PRODUCER.AUTHORIZATION
    assert config["render"]["minimum_available_bytes"] == PRODUCER.MINIMUM_BYTES
    assert config["render"]["full_render_start_available_bytes"] == PRODUCER.FULL_START_BYTES
    assert config["render"]["maximum_png_bytes"] * 2 <= config["render"]["frame_reserve_bytes"]
    assert config["render"]["raw_retained"] is False
    assert config["render"]["source_file_saved_or_copied"] is False
    for scenario, duration in (("A4-1", 50000000), ("B4-1", 42000000)):
        run = config["runs"][scenario]
        assert run["source_duration_us"] == duration == run["sample_count_per_camera"] * 200000
        assert run["new_run_id"].endswith("-d124-v1")
        assert run["new_clock_id"].endswith(":v1:d124-v1")
