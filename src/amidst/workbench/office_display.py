"""Pinned Office presentation companion. Never attaches to inference/physical inputs."""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


def _encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_office_display(repo: Path, scope: dict[str, Any]) -> dict[str, Any]:
    """Validate once at Office startup; missing/stale assets fail closed."""
    config = json.loads((repo / "configs/office_demo_display_v1.json").read_bytes())
    asset = repo / config["asset"]
    if (not asset.resolve().is_relative_to(repo.resolve()) or asset.is_symlink()
            or asset.stat().st_size > config["max_asset_bytes"]
            or _sha(asset) != config["asset_sha256"]):
        raise ValueError("OFFICE_DISPLAY_ASSET_MISMATCH")
    with gzip.open(asset, "rb") as stream:
        raw = stream.read(config["max_raw_bytes"] + 1)
    if len(raw) > config["max_raw_bytes"]:
        raise ValueError("OFFICE_DISPLAY_RESOURCE_LIMIT")
    data = json.loads(raw)
    policy = {k: v for k, v in config.items() if k not in {"asset_sha256", "exporter_sha256"}}
    expected = {
        "schema_version": "office-supplemental-display.v1", "units": "METRES",
        "geometry_local_units": "NATIVE_BU", "authority": "PARTIAL_DISPLAY_CONTEXT",
        "display_only": True, "physical_authority_changed": False,
        "navigation_authority": "UNKNOWN", "whole_auditorium_complete": False,
        "source_geometry_modified": False,
        "config_policy_sha256": hashlib.sha256(_encoded(policy)).hexdigest(),
        "exporter_sha256": _sha(repo / "scripts/materialize_office_display.py"),
        **{k: config[k] for k in ("source_sha256", "scale_sha256", "source_archive_sha256",
                                  "office_inputs_sha256", "auditorium_inputs_sha256",
                                  "evaluated_scene", "model_revision", "metres_per_bu",
                                  "coordinate_frame")},
    }
    if any(data.get(k) != v for k, v in expected.items()):
        raise ValueError("OFFICE_DISPLAY_PROVENANCE_MISMATCH")
    if (scope.get("scene_id") != "blender-office" or scope.get("units") != "METRES"
            or any(scope.get(k) != config[k] for k in (
                "source_sha256", "scale_sha256", "metres_per_bu", "model_revision"))
            or scope.get("inputs_sha256") != config["office_inputs_sha256"]):
        raise ValueError("OFFICE_DISPLAY_SCOPE_MISMATCH")
    definitions = data["geometries"]
    specs = {row["object_id"]: row for row in config["objects"]}
    instances = data["instances"]
    if (len(definitions) != 19 or len(instances) != 94
            or Counter(row["object_id"] for row in instances) != Counter(specs.keys())):
        raise ValueError("OFFICE_DISPLAY_INVENTORY_MISMATCH")
    for key, geometry in definitions.items():
        if hashlib.sha256(_encoded(geometry)).hexdigest() != key:
            raise ValueError("OFFICE_DISPLAY_GEOMETRY_MISMATCH")
        vertices = geometry["vertices"]
        if not vertices or any(len(p) != 3 or not all(math.isfinite(v) for v in p)
                               for p in vertices):
            raise ValueError("OFFICE_DISPLAY_INVALID_VERTEX")
        if any(len(t) != 3 or any(type(i) is not int or not 0 <= i < len(vertices) for i in t)
               for t in geometry["triangles"]):
            raise ValueError("OFFICE_DISPLAY_INVALID_TRIANGLE")
    for row in instances:
        spec = specs[row["object_id"]]
        expected_matrix = [[v * config["metres_per_bu"] if a < 3 else v for v in line]
                           for a, line in enumerate(spec["matrix_world_bu"])]
        if (row["geometry_ref"] != spec["geometry_sha256"]
                or row["matrix_world_metres"] != expected_matrix
                or row["assembly"] != spec["assembly"] or row["kind"] != spec["kind"]
                or len(definitions[row["geometry_ref"]]["triangles"]) != spec["triangles"]
                or not 0 <= row["transform_max_error_metres"] < 1e-5):
            raise ValueError("OFFICE_DISPLAY_INSTANCE_MISMATCH")
    return {**data, "asset_sha256": config["asset_sha256"]}


def attach_office_display(scene: Any, repo: Path) -> None:
    """Only the adapter's public display snapshot is extended; source/index stay frozen."""
    display = load_office_display(repo, scene.live_scope())
    scene._snapshot["presentation"]["supplemental_display"] = display
