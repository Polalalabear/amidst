"""Unit tests for Workstream W3 cross-platform scripts and scene builder.

Tests:
1. scripts/ensure_env.py
2. scripts/verify_clean_clone.py
3. scripts/build_office_expanded_scene.py (D118 disk guard, ROOM indoor cameras, gt_read=False, COCO objects)
4. start_all_demo.ps1 (-CheckOnly mode and validation)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

from scripts.build_office_expanded_scene import (
    DEFAULT_MIN_FREE_GIB,
    EXPECTED_ROOMS,
    REQUIRED_COCO_CATEGORIES,
    DiskGuardError,
    build_office_expanded_scene,
    canonical_json_bytes,
    check_disk_guard,
    generate_camera_graph,
    generate_coco_objects,
    generate_region_graph,
    sha256_digest,
    validate_office_expanded_scene,
)
from scripts.ensure_env import (
    check_directories,
    check_disk,
    check_git,
    check_node,
    check_package,
    check_python,
    run_env_checks,
)
from scripts.verify_clean_clone import (
    check_architecture,
    check_git_diff,
    run_clean_clone_verification,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# 1. Tests for scripts/ensure_env.py
# ---------------------------------------------------------------------------

def test_ensure_env_components() -> None:
    py_info = check_python()
    assert py_info["passed"] is True
    assert "version" in py_info
    assert py_info["required"] == ">=3.11"

    node_info = check_node()
    assert "available" in node_info
    assert "version" in node_info

    git_info = check_git()
    assert "available" in git_info
    assert "version" in git_info

    disk_info = check_disk(REPO_ROOT, min_free_gib=0.001)
    assert disk_info["free_bytes"] > 0
    assert disk_info["free_gib"] > 0.0
    assert disk_info["passed"] is True

    dirs_info = check_directories(REPO_ROOT)
    assert dirs_info["passed"] is True
    assert dirs_info["directories"]["src/amidst/q1q5"] is True
    assert dirs_info["directories"]["frontend/workbench-v2"] is True
    assert dirs_info["directories"]["configs/q1q5"] is True


def test_ensure_env_disk_guard_fail() -> None:
    receipt = run_env_checks(repo=REPO_ROOT, min_free_gib=999999.0)
    assert receipt["disk"]["passed"] is False
    assert receipt["status"] == "FAIL"


def test_ensure_env_missing_directory(tmp_path: Path) -> None:
    receipt = run_env_checks(repo=tmp_path, required_dirs=["nonexistent_dir_999"])
    assert receipt["directories"]["nonexistent_dir_999"] is False
    assert receipt["directories_passed"] is False
    assert receipt["status"] == "FAIL"


def test_ensure_env_missing_package() -> None:
    receipt = run_env_checks(repo=REPO_ROOT, required_packages=["nonexistent_pkg_xyz_999"])
    assert receipt["packages"]["nonexistent_pkg_xyz_999"]["installed"] is False
    assert receipt["packages_passed"] is False
    assert receipt["status"] == "FAIL"


def test_ensure_env_cli() -> None:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "ensure_env.py"),
        "--repo",
        str(REPO_ROOT),
        "--min-free-gib",
        "0.001",
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.stdout.strip()
    receipt = json.loads(proc.stdout)
    assert "status" in receipt
    assert "python" in receipt
    assert "node" in receipt
    assert "git" in receipt
    assert "disk" in receipt
    assert "packages" in receipt
    assert "directories" in receipt


# ---------------------------------------------------------------------------
# 2. Tests for scripts/verify_clean_clone.py
# ---------------------------------------------------------------------------

def test_verify_clean_clone_diff_check() -> None:
    diff_res = check_git_diff(REPO_ROOT)
    assert diff_res["status"] == "PASS"
    assert diff_res["findings"] == []


def test_verify_clean_clone_architecture_guard() -> None:
    arch_res = check_architecture(REPO_ROOT, base="origin/mainline/q1q5")
    assert arch_res["status"] == "PASS"
    assert arch_res["returncode"] == 0


def test_verify_clean_clone_quick_skip_tests() -> None:
    receipt = run_clean_clone_verification(
        repo=REPO_ROOT,
        base="origin/mainline/q1q5",
        quick=True,
        skip_tests=True,
        min_free_gib=0.001,
    )
    assert receipt["repo"] == str(REPO_ROOT)
    assert receipt["base"] == "origin/mainline/q1q5"
    assert receipt["quick"] is True
    assert receipt["skip_tests"] is True
    assert "environment" in receipt["checks"]
    assert receipt["checks"]["git_diff_check"]["status"] == "PASS"
    assert receipt["checks"]["architecture_guard"]["status"] == "PASS"
    assert receipt["checks"]["tests"]["status"] == "SKIPPED"


def test_verify_clean_clone_cli() -> None:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "verify_clean_clone.py"),
        "--repo",
        str(REPO_ROOT),
        "--base",
        "origin/mainline/q1q5",
        "--quick",
        "--skip-tests",
        "--json",
        "--min-free-gib",
        "0.001",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.stdout.strip()
    receipt = json.loads(proc.stdout)
    assert "checks" in receipt
    assert "git_diff_check" in receipt["checks"]
    assert "architecture_guard" in receipt["checks"]


# ---------------------------------------------------------------------------
# 3. Tests for scripts/build_office_expanded_scene.py
# ---------------------------------------------------------------------------

def test_build_office_expanded_scene_in_memory() -> None:
    res = build_office_expanded_scene()
    assert res["status"] == "PASS"
    assert res["gt_read"] is False

    rg = res["region_graph"]
    cg = res["camera_graph"]
    manifest = res["scene_manifest"]

    assert rg["schema_version"] == "q-demo.region-graph.v1"
    assert cg["schema_version"] == "q-demo.camera-transition-graph.v1"
    assert manifest["gt_read"] is False

    # Check rooms R101 - R104 exist
    room_ids = {r["region_id"] for r in rg["regions"] if r["kind"] == "ROOM"}
    for expected in EXPECTED_ROOMS:
        assert expected in room_ids

    # Check every ROOM has an indoor MANUAL_ON_STATIC_FRAME camera
    cameras = cg["cameras"]
    for expected in EXPECTED_ROOMS:
        cam_id = f"CAM_{expected}_IN"
        matching_cams = [c for c in cameras if c["camera_id"] == cam_id]
        assert len(matching_cams) == 1, f"Missing indoor camera {cam_id}"
        covered = matching_cams[0]["covered_regions"]
        assert any(
            cov["region_id"] == expected and cov["basis"] == "MANUAL_ON_STATIC_FRAME"
            for cov in covered
        ), f"Camera {cam_id} missing MANUAL_ON_STATIC_FRAME for room {expected}"

    # Check all 8 COCO categories are present
    obj_cats = {o["category"] for o in manifest["objects"]}
    for expected_cat in REQUIRED_COCO_CATEGORIES:
        assert expected_cat in obj_cats, f"Missing required COCO category {expected_cat}"


def test_build_office_expanded_scene_write_and_hashes(tmp_path: Path) -> None:
    res = build_office_expanded_scene(out_dir=tmp_path, min_free_gib=0.001)
    assert res["status"] == "PASS"
    assert res["gt_read"] is False

    rg_file = tmp_path / "region_graph.json"
    cg_file = tmp_path / "camera_graph.json"
    manifest_file = tmp_path / "scene_manifest.json"

    assert rg_file.is_file()
    assert cg_file.is_file()
    assert manifest_file.is_file()

    rg_bytes = rg_file.read_bytes()
    cg_bytes = cg_file.read_bytes()
    manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))

    # Verify canonical SHA-256 matches
    assert hashlib.sha256(rg_bytes).hexdigest() == manifest_data["files"]["region_graph.json"]["sha256"]
    assert hashlib.sha256(cg_bytes).hexdigest() == manifest_data["files"]["camera_graph.json"]["sha256"]
    assert manifest_data["gt_read"] is False


def test_build_office_expanded_scene_disk_guard_failure(tmp_path: Path) -> None:
    out_dir = tmp_path / "should_not_be_created"
    with pytest.raises(DiskGuardError, match="D118 disk guard failure"):
        build_office_expanded_scene(out_dir=out_dir, min_free_gib=999999.0)

    assert not out_dir.exists()


def test_validate_office_expanded_scene_catches_gt_read() -> None:
    rg = generate_region_graph()
    cg = generate_camera_graph()
    manifest = {
        "gt_read": True,  # Violation!
        "objects": generate_coco_objects(),
    }
    with pytest.raises(ValueError, match="Ground truth isolation violation"):
        validate_office_expanded_scene(rg, cg, manifest)


def test_validate_office_expanded_scene_catches_missing_room_camera() -> None:
    rg = generate_region_graph()
    cg = generate_camera_graph()
    # Remove R103 camera
    cg["cameras"] = [c for c in cg["cameras"] if c["camera_id"] != "CAM_R103_IN"]
    manifest = {
        "gt_read": False,
        "objects": generate_coco_objects(),
    }
    with pytest.raises(ValueError, match="Classroom R103 has no indoor camera"):
        validate_office_expanded_scene(rg, cg, manifest)


def test_validate_office_expanded_scene_catches_non_manual_basis() -> None:
    rg = generate_region_graph()
    cg = generate_camera_graph()
    # Change R101 camera basis
    for cam in cg["cameras"]:
        if cam["camera_id"] == "CAM_R101_IN":
            cam["covered_regions"][0]["basis"] = "STATIC_VISIBILITY_INDEX"
    manifest = {
        "gt_read": False,
        "objects": generate_coco_objects(),
    }
    with pytest.raises(ValueError, match="lacks required MANUAL_ON_STATIC_FRAME"):
        validate_office_expanded_scene(rg, cg, manifest)


def test_validate_office_expanded_scene_catches_missing_coco_category() -> None:
    rg = generate_region_graph()
    cg = generate_camera_graph()
    # Omit backpack
    objects = [o for o in generate_coco_objects() if o["category"] != "backpack"]
    manifest = {
        "gt_read": False,
        "objects": objects,
    }
    with pytest.raises(ValueError, match="Required COCO object category 'backpack' missing"):
        validate_office_expanded_scene(rg, cg, manifest)


def test_build_office_expanded_scene_cli(tmp_path: Path) -> None:
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "build_office_expanded_scene.py"),
        "--out-dir",
        str(tmp_path),
        "--min-free-gib",
        "0.001",
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    receipt = json.loads(proc.stdout)
    assert receipt["status"] == "PASS"
    assert receipt["gt_read"] is False
    assert (tmp_path / "scene_manifest.json").is_file()


# ---------------------------------------------------------------------------
# 4. Tests for start_all_demo.ps1
# ---------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell not available on this host")
def test_start_all_demo_ps1_check_only() -> None:
    ps_script = REPO_ROOT / "start_all_demo.ps1"
    assert ps_script.is_file()

    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps_script),
        "-CheckOnly",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"PowerShell check-only failed: {proc.stderr}"
    assert "Pre-flight checks passed successfully" in proc.stdout


@pytest.mark.skipif(shutil.which("powershell") is None, reason="PowerShell not available on this host")
def test_start_all_demo_ps1_duplicate_ports() -> None:
    ps_script = REPO_ROOT / "start_all_demo.ps1"
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(ps_script),
        "-CheckOnly",
        "-PortRec",
        "8765",
        "-PortLive",
        "8765",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode != 0
