#!/usr/bin/env python3
"""Generate isolated SYNTHETIC multi-room JSON fixtures, never a Blender scene.

Derived from Argon #411 at 35bafff5a6c65343d374176412a92a88fb7ca147.
Room/camera/object labels are invented test data, with no static-frame review,
real camera calibration, source assets or authority for production inference.
No rendering or scene reconstruction is implemented. Output needs a new directory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import os
from typing import Any, Sequence

DEFAULT_MIN_FREE_GIB = 8.0

REQUIRED_COCO_CATEGORIES: tuple[str, ...] = (
    "person",
    "chair",
    "backpack",
    "laptop",
    "book",
    "bottle",
    "cup",
    "clock",
)

EXPECTED_ROOMS: tuple[str, ...] = (
    "R101",
    "R102",
    "R103",
    "R104",
)


class DiskGuardError(RuntimeError):
    """Raised when available disk space is below D118 threshold."""


def check_disk_guard(target: Path, min_free_gib: float = DEFAULT_MIN_FREE_GIB) -> float:
    """Verify disk space before any write per D118."""
    probe = target
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    usage = shutil.disk_usage(probe)
    free_gib = usage.free / (1024 ** 3)
    if free_gib < min_free_gib:
        raise DiskGuardError(
            f"D118 disk guard failure: {free_gib:.3f} GiB available at {probe}, requires >= {min_free_gib} GiB"
        )
    return free_gib


def canonical_json_bytes(data: Any) -> bytes:
    """Deterministic JSON byte representation."""
    return json.dumps(data, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def sha256_digest(raw: bytes) -> str:
    """Hex SHA-256 digest of bytes."""
    return hashlib.sha256(raw).hexdigest()


def generate_region_graph() -> dict[str, Any]:
    """Generate region_graph for expanded office scene."""
    regions = [
        {
            "region_id": "CORR_MAIN",
            "kind": "CORRIDOR_SEGMENT",
            "floor_id": "FLOOR_1",
            "display_name": "主走廊 Main Corridor",
        },
        {
            "region_id": "R101",
            "kind": "ROOM",
            "floor_id": "FLOOR_1",
            "display_name": "教室 R101 Class 101",
        },
        {
            "region_id": "R102",
            "kind": "ROOM",
            "floor_id": "FLOOR_1",
            "display_name": "教室 R102 Class 102",
        },
        {
            "region_id": "R103",
            "kind": "ROOM",
            "floor_id": "FLOOR_1",
            "display_name": "教室 R103 Class 103",
        },
        {
            "region_id": "R104",
            "kind": "ROOM",
            "floor_id": "FLOOR_1",
            "display_name": "教室 R104 Class 104",
        },
    ]

    edges = []
    for room_id in EXPECTED_ROOMS:
        edges.append(
            {
                "edge_id": f"E_CORR_{room_id}",
                "regions": ["CORR_MAIN", room_id],
                "direction": "BIDIRECTIONAL",
                "state": "UNKNOWN",
                "traversability": "TOPOLOGICAL_ONLY",
                "via": {
                    "kind": "PORTAL",
                    "ref": f"DOOR_{room_id}",
                },
                "basis_refs": ["synthetic-fixture:office_multi_room"],
            }
        )

    return {
        "schema_version": "q-demo.region-graph.v1",
        "scene_id": "SYN_OFFICE_MULTI_ROOM",
        "scene_revision": "SYN_FIXTURE_V1",
        "approval_status": "SYNTHETIC_FIXTURE_ONLY",
        "regions": regions,
        "edges": edges,
    }


def generate_camera_graph() -> dict[str, Any]:
    """Invent fixture coverage without claiming a reviewed static source frame."""
    cameras = [
        {
            "camera_id": "CAM_CORR",
            "covered_regions": [
                {
                    "region_id": "CORR_MAIN",
                    "basis": "SYNTHETIC_FIXTURE_ONLY",
                    "fixture_ref": "synthetic-fixture:CAM_CORR:CORR_MAIN",
                    "visible_area_m2": None,
                }
            ],
            "entry_zones": [],
            "exit_zones": [],
        }
    ]

    for room_id in EXPECTED_ROOMS:
        cam_id = f"CAM_{room_id}_IN"
        cameras.append(
            {
                "camera_id": cam_id,
                "covered_regions": [
                    {
                        "region_id": room_id,
                        "basis": "SYNTHETIC_FIXTURE_ONLY",
                        "fixture_ref": f"synthetic-fixture:{cam_id}:{room_id}",
                        "visible_area_m2": None,
                    }
                ],
                "entry_zones": [],
                "exit_zones": [],
            }
        )

    return {
        "schema_version": "q-demo.camera-transition-graph.v1",
        "scene_id": "SYN_OFFICE_MULTI_ROOM",
        "scene_revision": "SYN_FIXTURE_V1",
        "approval_status": "SYNTHETIC_FIXTURE_ONLY",
        "cameras": cameras,
        "transitions": [],
    }


def generate_coco_objects() -> list[dict[str, Any]]:
    """Generate COCO-identifiable objects inventory covering all 8 required categories."""
    return [
        {
            "object_id": "obj_person_101",
            "category": "person",
            "region_id": "R101",
            "description": "Student in R101",
        },
        {
            "object_id": "obj_chair_101",
            "category": "chair",
            "region_id": "R101",
            "description": "Desk chair in R101",
        },
        {
            "object_id": "obj_backpack_102",
            "category": "backpack",
            "region_id": "R102",
            "description": "School backpack in R102",
        },
        {
            "object_id": "obj_laptop_102",
            "category": "laptop",
            "region_id": "R102",
            "description": "Laptop on teacher desk in R102",
        },
        {
            "object_id": "obj_book_103",
            "category": "book",
            "region_id": "R103",
            "description": "Open textbook in R103",
        },
        {
            "object_id": "obj_bottle_103",
            "category": "bottle",
            "region_id": "R103",
            "description": "Reusable water bottle in R103",
        },
        {
            "object_id": "obj_cup_104",
            "category": "cup",
            "region_id": "R104",
            "description": "Coffee cup in R104",
        },
        {
            "object_id": "obj_clock_104",
            "category": "clock",
            "region_id": "R104",
            "description": "Wall clock in R104",
        },
    ]


def validate_office_synthetic_fixture(
    region_graph: dict[str, Any],
    camera_graph: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Validate all invariants for the expanded Office scene."""
    # 1. gt_read must be explicitly False
    if manifest.get("gt_read") is not False:
        raise ValueError(
            f"Ground truth isolation violation: manifest gt_read is {manifest.get('gt_read')}, must be False"
        )
    if (manifest.get("data_origin") != "SYNTHETIC_FIXTURE_ONLY"
            or manifest.get("production_inference_allowed") is not False
            or region_graph.get("approval_status") != "SYNTHETIC_FIXTURE_ONLY"
            or camera_graph.get("approval_status") != "SYNTHETIC_FIXTURE_ONLY"):
        raise ValueError("Fixture must explicitly deny production inference authority")

    # 2. Schema versions
    if region_graph.get("schema_version") != "q-demo.region-graph.v1":
        raise ValueError(f"Invalid region_graph schema_version: {region_graph.get('schema_version')}")
    if camera_graph.get("schema_version") != "q-demo.camera-transition-graph.v1":
        raise ValueError(f"Invalid camera_graph schema_version: {camera_graph.get('schema_version')}")

    # 3. Room inventory
    regions = region_graph.get("regions", [])
    rooms = [r for r in regions if r.get("kind") == "ROOM"]
    room_ids = {r["region_id"] for r in rooms}

    for expected in EXPECTED_ROOMS:
        if expected not in room_ids:
            raise ValueError(f"Required classroom {expected} missing from region_graph")

    # 4. Invented coverage remains fixture-only; it is not a source-frame review.
    cameras = camera_graph.get("cameras", [])
    room_coverage: dict[str, list[dict[str, Any]]] = {rid: [] for rid in room_ids}

    for cam in cameras:
        for cov in cam.get("covered_regions", []):
            rid = cov.get("region_id")
            if rid in room_coverage:
                room_coverage[rid].append(cov)

    for rid, cov_list in room_coverage.items():
        if not cov_list:
            raise ValueError(f"Classroom {rid} has no indoor camera covering it")
        fixture_cov = [c for c in cov_list if c.get("basis") == "SYNTHETIC_FIXTURE_ONLY"]
        if not fixture_cov:
            raise ValueError(
                f"Classroom {rid} camera lacks SYNTHETIC_FIXTURE_ONLY coverage basis"
            )

    # 5. COCO categories
    objects = manifest.get("objects", [])
    present_categories = {obj.get("category") for obj in objects}
    for cat in REQUIRED_COCO_CATEGORIES:
        if cat not in present_categories:
            raise ValueError(f"Required COCO object category '{cat}' missing from scene objects")

    return {
        "status": "PASS",
        "rooms_verified": sorted(room_ids),
        "cameras_verified": [c["camera_id"] for c in cameras],
        "coco_categories_verified": sorted(present_categories),
        "gt_read": False,
    }


def build_office_synthetic_fixture(
    out_dir: Path | str | None = None,
    min_free_gib: float = DEFAULT_MIN_FREE_GIB,
) -> dict[str, Any]:
    """Generate test-only JSON, refusing existing or symlinked output locations.

    Enforces D118 disk space guard before writing.
    """
    region_graph = generate_region_graph()
    camera_graph = generate_camera_graph()
    coco_objects = generate_coco_objects()

    rg_bytes = canonical_json_bytes(region_graph)
    cg_bytes = canonical_json_bytes(camera_graph)

    rg_sha = sha256_digest(rg_bytes)
    cg_sha = sha256_digest(cg_bytes)

    manifest: dict[str, Any] = {
        "manifest_id": "synthetic-office-multi-room-v1",
        "scene_id": "SYN_OFFICE_MULTI_ROOM",
        "scene_revision": "SYN_FIXTURE_V1",
        "data_origin": "SYNTHETIC_FIXTURE_ONLY",
        "gt_read": False,
        "note": "Invented test fixture only. No real scene, calibration, review, or inference authority.",
        "production_inference_allowed": False,
        "files": {
            "region_graph.json": {
                "path": "region_graph.json",
                "sha256": rg_sha,
                "size_bytes": len(rg_bytes),
            },
            "camera_graph.json": {
                "path": "camera_graph.json",
                "sha256": cg_sha,
                "size_bytes": len(cg_bytes),
            },
        },
        "rooms": list(EXPECTED_ROOMS),
        "corridors": ["CORR_MAIN"],
        "cameras": [c["camera_id"] for c in camera_graph["cameras"]],
        "coco_categories": list(REQUIRED_COCO_CATEGORIES),
        "objects": coco_objects,
    }

    # Validate before write
    val_result = validate_office_synthetic_fixture(region_graph, camera_graph, manifest)

    if out_dir is not None:
        target_dir = Path(out_dir).absolute()
        if target_dir.resolve() != target_dir:
            raise ValueError("Output path must be canonical and contain no symlink components")
        # Enforce D118 disk guard
        free_gib = check_disk_guard(target_dir, min_free_gib=min_free_gib)
        # Do not reuse a run directory or follow a pre-existing file/symlink.
        target_dir.mkdir(parents=True, exist_ok=False)

        rg_path = target_dir / "region_graph.json"
        cg_path = target_dir / "camera_graph.json"
        manifest_path = target_dir / "scene_manifest.json"

        manifest_bytes = canonical_json_bytes(manifest)
        for path, raw in ((rg_path, rg_bytes), (cg_path, cg_bytes), (manifest_path, manifest_bytes)):
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
                stream.write(raw)

        return {
            "status": "PASS",
            "out_dir": str(target_dir),
            "free_gib_at_write": round(free_gib, 3),
            "gt_read": False,
            "files": {
                "region_graph": {"path": str(rg_path), "sha256": rg_sha},
                "camera_graph": {"path": str(cg_path), "sha256": cg_sha},
                "scene_manifest": {
                    "path": str(manifest_path),
                    "sha256": sha256_digest(manifest_bytes),
                },
            },
            "validation": val_result,
        }

    return {
        "status": "PASS",
        "gt_read": False,
        "region_graph": region_graph,
        "camera_graph": camera_graph,
        "scene_manifest": manifest,
        "validation": val_result,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate test-only SYNTHETIC Office JSON; does not build or render a Blender scene."
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        help="Output directory to write region_graph.json, camera_graph.json, and scene_manifest.json",
    )
    parser.add_argument(
        "--min-free-gib",
        type=float,
        default=DEFAULT_MIN_FREE_GIB,
        help="Minimum required free disk space in GiB per D118 (default: 8.0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON receipt to stdout",
    )
    args = parser.parse_args(argv)

    try:
        receipt = build_office_synthetic_fixture(
            out_dir=args.out_dir,
            min_free_gib=args.min_free_gib,
        )
    except DiskGuardError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(f"Office SYNTHETIC fixture (no scene authority): {receipt['status']}")
        if "out_dir" in receipt:
            print(f"  Output directory: {receipt['out_dir']}")
            for name, meta in receipt["files"].items():
                print(f"    - {name}: {meta['sha256'][:16]}... ({meta['path']})")
        print(f"  Rooms: {', '.join(receipt['validation']['rooms_verified'])}")
        print(f"  Cameras: {', '.join(receipt['validation']['cameras_verified'])}")
        print(f"  COCO categories: {', '.join(receipt['validation']['coco_categories_verified'])}")
        print(f"  gt_read: {receipt['gt_read']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
