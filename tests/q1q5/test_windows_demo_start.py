"""Tests for Windows demo startup script start_all_demo.ps1 (Issue #429).

Validates:
- Script existence and parameter parsing
- Pre-flight checks in -CheckOnly mode
- Auto-detection of verified local safe packs (p1-v4-stripped, cx7-d119)
- Manifest SHA-256 validation (accepts stripped pin 13ab3c55..., rejects invalid pins)
- Fail-closed error handling for missing assets and duplicate/invalid ports
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PS_SCRIPT = REPO_ROOT / "start_all_demo.ps1"
STRIPPED_MANIFEST_SHA = "13ab3c559fd63dd6f5d44ac7f6dabe1192274b368bfd1307f3a3bbd6682e5805"
P1_STRIPPED_DIR = REPO_ROOT / "p1-v4-stripped"
CX7_D119_DIR = REPO_ROOT / "cx7-d119"


def has_powershell() -> bool:
    return shutil.which("powershell") is not None


@pytest.mark.skipif(not has_powershell(), reason="PowerShell not available on this host")
def test_start_all_demo_ps1_exists() -> None:
    assert PS_SCRIPT.is_file(), f"Expected {PS_SCRIPT} to exist"


@pytest.mark.skipif(not has_powershell(), reason="PowerShell not available on this host")
@pytest.mark.skipif(
    not (P1_STRIPPED_DIR.is_dir() and CX7_D119_DIR.is_dir()),
    reason="Local safe packs p1-v4-stripped and cx7-d119 required for auto-detection test",
)
def test_start_all_demo_ps1_check_only_auto_detects_safe_packs() -> None:
    """Verifies that start_all_demo.ps1 -CheckOnly succeeds using auto-detected safe packs."""
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PS_SCRIPT),
        "-CheckOnly",
        "-Python",
        sys.executable,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    assert "Pre-flight checks passed successfully" in proc.stdout


@pytest.mark.skipif(not has_powershell(), reason="PowerShell not available on this host")
def test_start_all_demo_ps1_rejects_missing_p1_bundle(tmp_path: Path) -> None:
    """Rejects missing P1 bundle directory fail-closed."""
    missing_bundle = tmp_path / "nonexistent-p1-bundle"
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PS_SCRIPT),
        "-CheckOnly",
        "-Python",
        sys.executable,
        "-P1Bundle",
        str(missing_bundle),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode != 0
    assert "Pre-flight checks passed successfully" not in proc.stdout


@pytest.mark.skipif(not has_powershell(), reason="PowerShell not available on this host")
def test_start_all_demo_ps1_rejects_missing_cx7_root(tmp_path: Path) -> None:
    """Rejects missing CX-7 root directory fail-closed."""
    missing_cx7 = tmp_path / "nonexistent-cx7-root"
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PS_SCRIPT),
        "-CheckOnly",
        "-Python",
        sys.executable,
        "-CX7Root",
        str(missing_cx7),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode != 0
    assert "Pre-flight checks passed successfully" not in proc.stdout


@pytest.mark.skipif(not has_powershell(), reason="PowerShell not available on this host")
@pytest.mark.skipif(
    not (P1_STRIPPED_DIR.is_dir() and CX7_D119_DIR.is_dir()),
    reason="Local safe packs required for manifest validation test",
)
def test_start_all_demo_ps1_rejects_manifest_mismatch() -> None:
    """Rejects invalid manifest SHA-256 pin fail-closed."""
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PS_SCRIPT),
        "-CheckOnly",
        "-Python",
        sys.executable,
        "-ManifestSha",
        "bad" * 21 + "0",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode != 0
    assert "mismatch" in (proc.stdout + proc.stderr).lower()


@pytest.mark.skipif(not has_powershell(), reason="PowerShell not available on this host")
@pytest.mark.skipif(
    not (P1_STRIPPED_DIR.is_dir() and CX7_D119_DIR.is_dir()),
    reason="Local safe packs required for manifest validation test",
)
def test_start_all_demo_ps1_accepts_valid_stripped_manifest_sha() -> None:
    """Accepts valid stripped runtime manifest pin explicitly passed."""
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PS_SCRIPT),
        "-CheckOnly",
        "-Python",
        sys.executable,
        "-ManifestSha",
        STRIPPED_MANIFEST_SHA,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert "Pre-flight checks passed successfully" in proc.stdout


@pytest.mark.skipif(not has_powershell(), reason="PowerShell not available on this host")
def test_start_all_demo_ps1_duplicate_ports() -> None:
    """Rejects duplicate service ports fail-closed."""
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PS_SCRIPT),
        "-CheckOnly",
        "-Python",
        sys.executable,
        "-PortRec",
        "8765",
        "-PortLive",
        "8765",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode != 0


@pytest.mark.skipif(not has_powershell(), reason="PowerShell not available on this host")
def test_start_all_demo_ps1_invalid_port_range() -> None:
    """Rejects privileged or out-of-range ports (<1024 or >65535)."""
    cmd = [
        "powershell",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(PS_SCRIPT),
        "-CheckOnly",
        "-Python",
        sys.executable,
        "-PortRec",
        "80",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    assert proc.returncode != 0
