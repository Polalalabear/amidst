from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import pytest

from scripts import ensure_env, verify_clean_clone
from scripts.ensure_env import (
    check_disk,
    check_git,
    check_node,
    check_package,
    check_project_dependencies,
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
    check_architecture,
    check_clean_checkout,
    check_git_diff,
    check_git_rev_parse,
    run_clean_clone_verification,
    run_node_tests,
    run_python_tests,
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

    def fake_run(cmd: Any, **kwargs: Any) -> Any:
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
    assert report.get("status") in {"CHECKS_ONLY", "FAIL"}
    assert report.get("verification_scope") == "CHECKS_ONLY"
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
        "clean_checkout",
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


# ---------------------------------------------------------------------------
# Codex REVISE Behavioral Regressions (P1 & P2 Counter-example Guards)
# ---------------------------------------------------------------------------

def test_guard_failure_not_masked_or_filtered(monkeypatch: pytest.MonkeyPatch) -> None:
    """[P1] Guard failure must NOT be filtered or converted to returncode 0/PASS."""
    fake_guard_payload = {
        "status": "FAIL",
        "checks": {
            "schema_registry": {
                "status": "FAIL",
                "findings": [
                    {
                        "code": "SCHEMA_UNREGISTERED",
                        "path": "src/amidst/q1q5/untracked_probe.py",
                        "message": "Probe not registered",
                    }
                ],
                "scanned_files": 12,
            }
        },
    }

    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "check_architecture_guard.py" in " ".join(cmd):
            return subprocess.CompletedProcess(
                list(cmd),
                returncode=1,
                stdout=json.dumps(fake_guard_payload),
                stderr="",
            )
        return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    res = check_architecture(Path.cwd(), base="origin/mainline/q1q5")
    assert res["status"] == "FAIL"
    assert res["returncode"] == 1
    report = res.get("report", {})
    findings = report["checks"]["schema_registry"]["findings"]
    assert len(findings) == 1
    assert findings[0]["path"] == "src/amidst/q1q5/untracked_probe.py"


@pytest.mark.parametrize("raw_stdout", ["", "not-json"])
def test_guard_missing_or_invalid_json_fails_and_preserves_streams(
    monkeypatch: pytest.MonkeyPatch, raw_stdout: str
) -> None:
    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            list(cmd), returncode=0, stdout=raw_stdout, stderr="guard diagnostic\n"
        )

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    res = check_architecture(Path.cwd(), base="origin/mainline/q1q5")
    assert res["status"] == "FAIL"
    assert res["returncode"] == 0
    assert res["reason"] == "INVALID_GUARD_REPORT"
    assert res["stdout"] == raw_stdout
    assert res["stderr"] == "guard diagnostic\n"


def test_guard_report_requires_complete_check_findings_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    incomplete = {
        "status": "PASS",
        "checks": {"authority": {"status": "PASS", "findings": []}},
    }

    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            list(cmd), returncode=0, stdout=json.dumps(incomplete), stderr=""
        )

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    res = check_architecture(Path.cwd(), base="origin/mainline/q1q5")
    assert res["status"] == "FAIL"
    assert res["reason"] == "INVALID_GUARD_REPORT"


def test_whitespace_diff_failure_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    """[P2] Trailing whitespace on other files must NOT be suppressed when exitcode=2."""
    raw_diff_output = "other_module.py:10: trailing whitespace.\nanother_file.py:5: trailing whitespace.\n"

    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "diff" in cmd and "--check" in cmd:
            return subprocess.CompletedProcess(
                list(cmd),
                returncode=2,
                stdout=raw_diff_output,
                stderr="",
            )
        return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    res = check_git_diff(Path.cwd())
    assert res["status"] == "FAIL"
    assert res["returncode"] == 2
    assert len(res["findings"]) == 2
    assert "other_module.py:10: trailing whitespace." in res["findings"]


def test_missing_base_fails_rev_parse(monkeypatch: pytest.MonkeyPatch) -> None:
    """[P2] Failure to resolve base reference (e.g. exit 128) must result in FAIL."""
    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "rev-parse" in cmd:
            if "HEAD" in cmd:
                return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="a" * 40, stderr="")
            # Base reference fails
            return subprocess.CompletedProcess(list(cmd), returncode=128, stdout="", stderr="fatal: Not a valid object name")
        return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    res = check_git_rev_parse(Path.cwd(), base="invalid/base/ref")
    assert res["status"] == "FAIL"
    assert res["matches_base"] is False


def test_unclean_checkout_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """[P2] Dirty or untracked working tree must fail check_clean_checkout."""
    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "status" in cmd and "--porcelain=v1" in cmd:
            return subprocess.CompletedProcess(list(cmd), returncode=0, stdout=" M dirty_file.py\n?? untracked.py\n", stderr="")
        return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    res = check_clean_checkout(Path.cwd())
    assert res["status"] == "FAIL"
    assert res["reason"] == "CHECKOUT_NOT_CLEAN"
    assert len(res["changes"]) == 2


def test_missing_python_test_fails_without_guess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """[P2] Missing mandatory core python test file must report FAIL, not fallback/skip."""
    res = run_python_tests(tmp_path, quick=False)
    assert res["status"] == "FAIL"
    assert res["reason"] == "REQUIRED_PYTHON_TEST_MISSING"
    assert len(res["missing"]) > 0


def test_missing_node_test_fails_without_guess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """[P2] Missing mandatory node test file must report FAIL, not SKIPPED."""
    res = run_node_tests(tmp_path)
    assert res["status"] == "FAIL"
    assert res["reason"] == "REQUIRED_NODE_TEST_MISSING"


def test_node_unparseable_output_fails_without_guessing_24(monkeypatch: pytest.MonkeyPatch) -> None:
    """[P2] Node tests that output garbage or unparseable pass counts must NOT guess 24."""
    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "node" in cmd and "--test" in cmd:
            return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="unparseable random text without pass line\n", stderr="")
        return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    res = run_node_tests(Path.cwd())
    assert res["status"] == "INCOMPLETE"
    assert res["passed_count"] is None


def test_python_skip_fails_mandatory_core_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        xml_arg = next(arg for arg in cmd if str(arg).startswith("--junitxml="))
        Path(str(xml_arg).split("=", 1)[1]).write_text(
            '<testsuite tests="2" skipped="1"><testcase/><testcase><skipped/>'
            "</testcase></testsuite>",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(
            list(cmd), returncode=0, stdout="pytest complete", stderr=""
        )

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    res = run_python_tests(Path.cwd(), quick=True)
    assert res["status"] == "FAIL"
    assert res["passed_count"] == 1
    assert res["skipped_count"] == 1


def test_node_skip_fails_mandatory_core_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            list(cmd),
            returncode=0,
            stdout="1..2\n# tests 2\n# pass 1\n# fail 0\n# cancelled 0\n# skipped 1\n# todo 0\n",
            stderr="",
        )

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    res = run_node_tests(Path.cwd())
    assert res["status"] == "FAIL"
    assert res["passed_count"] == 1
    assert res["skipped_count"] == 1


def test_project_dependency_minimum_is_checked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["numpy>=2.5.3", "networkx>=3.7"]\n'
        '[dependency-groups]\ndev = ["pytest>=9.1.1"]\n',
        encoding="utf-8",
    )

    def fake_version(name: str) -> str:
        return {"numpy": "2.5.2", "networkx": "3.7", "pytest": "9.1.1"}[name]

    monkeypatch.setattr(ensure_env.metadata, "version", fake_version)
    res = check_project_dependencies(tmp_path)
    assert res["status"] == "FAIL"
    numpy = next(item for item in res["dependencies"] if item["name"] == "numpy")
    assert numpy["version"] == "2.5.2"
    assert numpy["specifier"] == ">=2.5.3"
    assert numpy["passed"] is False


def test_missing_version_parser_keeps_cli_available_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.12"\ndependencies = ["numpy>=2.5.3"]\n'
        '[dependency-groups]\ndev = ["pytest>=9.1.1"]\n',
        encoding="utf-8",
    )
    for directory in ("src/amidst/q1q5", "frontend/workbench-v2", "configs/q1q5"):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(ensure_env, "Requirement", None)
    monkeypatch.setattr(ensure_env, "SpecifierSet", None)
    monkeypatch.setattr(
        ensure_env,
        "collect_hardware_and_os",
        lambda repo, min_free_gib=8.0: {"disk": {"passed": True}},
    )
    monkeypatch.setattr(
        ensure_env,
        "check_node",
        lambda: {"available": True, "version": "v24", "passed": True},
    )
    monkeypatch.setattr(
        ensure_env,
        "check_git",
        lambda: {"available": True, "version": "git", "passed": True},
    )
    monkeypatch.setattr(
        ensure_env,
        "check_uv",
        lambda: {"available": True, "version": "uv", "passed": True},
    )
    monkeypatch.setattr(
        ensure_env,
        "check_pytest",
        lambda: {"available": True, "version": "pytest", "passed": True},
    )
    monkeypatch.setattr(
        ensure_env,
        "check_package",
        lambda name, required=True: {
            "installed": True,
            "version": "1",
            "required": required,
            "passed": True,
        },
    )

    with pytest.raises(SystemExit) as help_exit:
        ensure_env.main(["--help"])
    assert help_exit.value.code == 0
    assert "Cross-platform environment self-check" in capsys.readouterr().out

    exit_code = ensure_env.main(
        ["--repo", str(tmp_path), "--min-free-gib", "0", "--json"]
    )
    cli_output = capsys.readouterr().out
    receipt = json.loads(cli_output)
    assert exit_code == 1
    assert receipt["status"] == "FAIL"
    assert receipt["python"]["required"] == ">=3.12"
    assert receipt["python"]["reason"] == "VERSION_PARSER_UNAVAILABLE"
    assert receipt["project_dependencies"]["status"] == "UNKNOWN"
    assert receipt["project_dependencies"]["reason"] == "VERSION_PARSER_UNAVAILABLE"
    assert [
        item["required_spec"] for item in receipt["project_dependencies"]["dependencies"]
    ] == ["numpy>=2.5.3", "pytest>=9.1.1"]


def test_skip_tests_reports_checks_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """[P2] --skip-tests must yield CHECKS_ONLY, never a complete test-gate PASS."""
    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="b" * 40, stderr="")
        if "status" in cmd and "--porcelain" in cmd:
            return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")
        if "diff" in cmd:
            return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")
        if "check_architecture_guard.py" in " ".join(cmd):
            good = {
                "status": "PASS",
                "checks": {
                    name: {"status": "PASS", "findings": []}
                    for name in ("authority", "inference", "schemas")
                },
            }
            return subprocess.CompletedProcess(
                list(cmd), returncode=0, stdout=json.dumps(good), stderr=""
            )
        return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    receipt = run_clean_clone_verification(quick=False, skip_tests=True)
    assert receipt["status"] == "CHECKS_ONLY"
    assert receipt["verification_scope"] == "CHECKS_ONLY"


def test_quick_mode_reports_smoke_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """[P2] --quick mode must yield SMOKE_ONLY, never full focused PASS."""
    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "rev-parse" in cmd:
            return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="c" * 40, stderr="")
        if "status" in cmd and "--porcelain" in cmd:
            return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")
        if "diff" in cmd:
            return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")
        if "check_architecture_guard.py" in " ".join(cmd):
            good = {
                "status": "PASS",
                "checks": {
                    name: {"status": "PASS", "findings": []}
                    for name in ("authority", "inference", "schemas")
                },
            }
            return subprocess.CompletedProcess(
                list(cmd), returncode=0, stdout=json.dumps(good), stderr=""
            )
        if "pytest" in cmd:
            xml_arg = next(arg for arg in cmd if str(arg).startswith("--junitxml="))
            Path(str(xml_arg).split("=", 1)[1]).write_text(
                '<testsuite tests="1"><testcase/></testsuite>', encoding="utf-8"
            )
            return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="1 passed in 0.05s\n", stderr="")
        if "node" in cmd and "--test" in cmd:
            node = "1..24\n# tests 24\n# pass 24\n# fail 0\n# cancelled 0\n# skipped 0\n# todo 0\n"
            return subprocess.CompletedProcess(list(cmd), returncode=0, stdout=node, stderr="")
        return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    receipt = run_clean_clone_verification(quick=True, skip_tests=False)
    assert receipt["status"] == "SMOKE_ONLY"
    assert receipt["verification_scope"] == "SMOKE_ONLY"


def test_python_version_gate_312(monkeypatch: pytest.MonkeyPatch) -> None:
    """[P2] Python < 3.12 must fail check_python per pyproject.toml."""
    import sys
    monkeypatch.setattr(sys, "version_info", (3, 11, 8, "final", 0))
    py_res = check_python()
    assert py_res["passed"] is False
    assert py_res["required"] == ">=3.12"


def test_python_unparseable_output_fails_without_guessing(monkeypatch: pytest.MonkeyPatch) -> None:
    """[P2] Python tests that output unparseable summary must report FAIL with passed_count=None."""
    def fake_subprocess_run(cmd: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "pytest" in cmd:
            return subprocess.CompletedProcess(
                list(cmd),
                returncode=0,
                stdout="unparseable pytest output without summary\n",
                stderr="",
            )
        return subprocess.CompletedProcess(list(cmd), returncode=0, stdout="", stderr="")

    monkeypatch.setattr(verify_clean_clone, "_run_subprocess", fake_subprocess_run)
    res = run_python_tests(Path.cwd(), quick=True)
    assert res["status"] == "INCOMPLETE"
    assert res["passed_count"] is None


def test_python_tests_parses_real_count() -> None:
    """Verify run_python_tests parses passed_count from pytest output."""
    res = run_python_tests(Path.cwd(), quick=True)
    assert res["status"] == "PASS"
    assert res["passed_count"] == 14
    assert res["failed_count"] == 0
