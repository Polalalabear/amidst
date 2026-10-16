"""Pilot PNG provenance must preserve the original rendered pixels and IDAT data."""

from __future__ import annotations

import importlib.util
import struct
import zlib
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

SPEC = importlib.util.spec_from_file_location(
    "pilot_export_policy", Path(__file__).parents[2] / "scripts/export_blender_pilot.py"
)
assert SPEC and SPEC.loader
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


def idat_and_validate_crc(content: bytes) -> bytes:
    chunks = []
    offset = 8
    while offset < len(content):
        length = struct.unpack(">I", content[offset : offset + 4])[0]
        chunk = content[offset + 4 : offset + 8 + length]
        crc = struct.unpack(">I", content[offset + 8 + length : offset + 12 + length])[0]
        assert zlib.crc32(chunk) == crc
        if chunk[:4] == b"IDAT":
            chunks.append(chunk)
        offset += length + 12
    assert offset == len(content)
    return b"".join(chunks)


def test_png_label_preserves_encoded_pixels_and_explicit_provenance(tmp_path: Path) -> None:
    path = tmp_path / "camera_frame.png"
    original = Image.new("RGB", (24, 16), (170, 40, 10))
    original.putpixel((10, 8), (1, 200, 2))
    original.save(path)
    before = path.read_bytes()
    metadata = {
        "DatasetLabel": "PILOT / SYNTHETIC SAMPLE",
        "DataKind": "SYNTHETIC",
        "SimulationTimestampSeconds": "3.6",
    }
    EXPORT.label_png(path, metadata)
    assert idat_and_validate_crc(before) == idat_and_validate_crc(path.read_bytes())
    with Image.open(path) as labeled:
        assert labeled.tobytes() == original.tobytes()
        assert all(labeled.info[key] == value for key, value in metadata.items())


def test_non_png_rejected_without_modification(tmp_path: Path) -> None:
    path = tmp_path / "invalid.png"
    path.write_bytes(b"not a PNG")
    with pytest.raises(ValueError, match="complete PNG"):
        EXPORT.label_png(path, {"DatasetLabel": "PILOT / SYNTHETIC SAMPLE"})
    assert path.read_bytes() == b"not a PNG"


def test_person_cylinder_has_exact_declared_height_without_capsule_head():
    calls = []
    body = SimpleNamespace()
    bpy = SimpleNamespace(
        context=SimpleNamespace(object=body),
        ops=SimpleNamespace(
            mesh=SimpleNamespace(primitive_cylinder_add=lambda **kw: calls.append(kw))
        ),
    )
    plan = {
        "target": {
            "kind": "PERSON_SIZED_CYLINDER",
            "height_scene_units": 1.7 / 0.0247,
            "radius_scene_units": 0.25 / 0.0247,
        },
        "probe_height_units": 0.85 / 0.0247,
    }
    assert EXPORT.make_target(bpy, plan) == [body]
    assert calls == [{"vertices": 32, "radius": 0.25 / 0.0247, "depth": 1.7 / 0.0247}]
    assert plan["render_target"]["body_center_above_foot"] == 0.85 / 0.0247
    assert "head_center_above_foot" not in plan["render_target"]


def test_person_cylinder_rejects_inconsistent_centre_height():
    plan = {
        "target": {
            "kind": "PERSON_SIZED_CYLINDER",
            "height_scene_units": 100,
            "radius_scene_units": 10,
        },
        "probe_height_units": 55,
    }
    with pytest.raises(ValueError, match="body centre"):
        EXPORT.make_target(None, plan)
