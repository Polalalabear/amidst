from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any

import pytest

from scripts.ensure_env import (
    check_disk,
    check_git,
    check_node,
    check_package,
    check_pytest,
    check_python,
    check_uv,
    collect_cpu_info,
    collect_gpu_info,
    collect_hardware_and_os,
    collect_os_info,
    collect_ram_info,
    run_env_checks,
)
from scripts.verify_clean_clone import (
    audit_windows_compatibility,
    check_git_rev_parse,
    run_clean_clone_verification,
)


def test_hardware_and_os_keys() -> None:
    hw_os = collect_hardware_and_os()
    assert isinstance(hw_os, dict)
    assert set(hw_os.keys()) == {"os", "cpu", "ram", "gpu", "disk"}

    os_info = hw_os["os"]
    for key in ("system", "release", "version", "platform", "machine"):
        assert key in os_info
        assert os_info[key] != ""

    cpu_info = hw_os["cpu"]
    for key in ("model", "logical_cores", "physical_cores"):
        assert key in cpu_info
        assert cpu_info[key] is not None

    ram_info = hw_os["ram"]
    for key in ("total_bytes", "total_gib", "total_gb"):
        assert key in ram_info

    gpu_info = hw_os["gpu"]
    for key in (
        "available",
        "model",
        "vram_mib",
        "vram_gib",
        "driver_version",
        "probe_source",
        "gpus",
    ):
        assert key in gpu_info
    assert isinstance(gpu_info["gpus"], list)

    disk_info = hw_os["disk"]
    for key in (
        "path",
        "total_bytes",
        "total_gib",
        "free_bytes",
        "free_gib",
        "min_required_gib",
        "passed",
    ):
        assert key in disk_info
    assert disk_info["path"] == "."


def test_tool_versions_keys_and_inventory() -> None:
    env_receipt = run_env_checks()
    assert "tool_versions" in env_receipt
    tv = env_receipt["tool_versions"]
    for tool in ("python", "node", "uv", "git", "pytest"):
        assert tool in tv
        assert tv[tool] is not None


def test_graceful_unknown_when_tools_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    # 1. Missing uv
    monkeypatch.setattr(shutil, "which", lambda cmd: None if cmd == "uv" else shutil.which(cmd))
    uv_res = check_uv()
    assert uv_res["available"] is False
    assert uv_res["version"] == "UNKNOWN"
    assert uv_res["passed"] is True

    # 2. Missing node
    monkeypatch.setattr(shutil, "which", lambda cmd: None if cmd == "node" else shutil.which(cmd))
    node_res = check_node()
    assert node_res["available"] is False
    assert node_res["version"] is None
    assert node_res["passed"] is False

    # 3. Missing git
    monkeypatch.setattr(shutil, "which", lambda cmd: None if cmd == "git" else shutil.which(cmd))
    git_res = check_git()
    assert git_res["available"] is False
    assert git_res["version"] is None
    assert git_res["passed"] is False

    # 4. Missing nvidia-smi with no fallback GPU
    monkeypatch.setattr(
        shutil, "which", lambda cmd: None if cmd == "nvidia-smi" else shutil.which(cmd)
    )
    # Monkeypatch subprocess to fail any fallback probe as well
    from scripts import ensure_env

    def fake_run(cmd: Any, **kwargs: Any) -> Any:
        import subprocess

        return subprocess.CompletedProcess(list(cmd), returncode=1, stdout="", stderr="error")

    monkeypatch.setattr(ensure_env, "_run_cmd", fake_run)
    gpu_res = collect_gpu_info()
    assert "available" in gpu_res
    assert "model" in gpu_res
    assert "vram_mib" in gpu_res
    assert "vram_gib" in gpu_res
    assert "driver_version" in gpu_res


def test_clean_clone_verification_report_shape() -> None:
    report = run_clean_clone_verification(quick=True, skip_tests=True)
    assert isinstance(report, dict)
    assert report.get("schema") == "amidst.windows_clean_clone_baseline.v1"
    assert report.get("issue_ref") == "#419"
    assert report.get("status") in {"PASS", "FAIL"}
    assert report.get("repo") == "."
    assert "base" in report
    assert "head_sha" in report
    assert "base_sha" in report
    assert "hardware_and_os" in report
    assert "tool_versions" in report
    assert "checks" in report

    checks = report["checks"]
    for check_name in (
        "git_rev_parse_head",
        "ensure_env",
        "git_diff_check",
        "architecture_guard",
        "windows_posix_audit",
    ):
        assert check_name in checks
        assert "status" in checks[check_name]


def test_no_secrets_and_no_user_home_paths_in_report(monkeypatch: pytest.MonkeyPatch) -> None:
    secret_canary_token = "CANARY_TOKEN_SECRET_XYZ_98765"
    monkeypatch.setenv("AMIDST_API_KEY", secret_canary_token)
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_mocksupersecret1234567890abcdef")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "mock_aws_secret_canary_val")

    report = run_clean_clone_verification(quick=True, skip_tests=True)
    report_json = json.dumps(report, sort_keys=True)

    # 1. No secret env var values leak
    assert secret_canary_token not in report_json
    assert "ghp_mocksupersecret1234567890abcdef" not in report_json
    assert "mock_aws_secret_canary_val" not in report_json

    # 2. No absolute home paths of user
    home_dir = Path.home().resolve()
    home_str = str(home_dir)
    assert home_str not in report_json
    assert home_dir.as_posix() not in report_json

    # 3. Check existing committed/generated JSON report as well
    json_path = Path("docs/operations/WINDOWS_CLEAN_CLONE_BASELINE_20261104.json")
    if json_path.is_file():
        file_content = json_path.read_text(encoding="utf-8")
        assert home_str not in file_content
        assert home_dir.as_posix() not in file_content
        assert "Users" not in file_content or "Users/" not in file_content
