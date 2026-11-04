#!/usr/bin/env python3
"""Cross-platform clean clone verification CLI for Amidst Q1-Q5 demo.

Replaces verify_clean_clone.sh with a portable, structured Python script.
Executes:
1. Git HEAD & base SHA verification (git rev-parse HEAD / base)
2. Environment and hardware self-check (scripts/ensure_env.py)
3. Git diff check (git diff --check)
4. Architecture guard (scripts/check_architecture_guard.py)
5. Focused automated tests (pytest core Q1-Q5 & node --test workbench-v2), unless --skip-tests
6. Windows/POSIX compatibility audit (non-destructive capability and static check)

Emits a structured JSON verification receipt and exits 0 on PASS, non-zero on FAIL.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import locale
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from typing import Any, Sequence

# Import ensure_env from sibling or local script
try:
    from scripts.ensure_env import run_env_checks
except ImportError:
    try:
        from ensure_env import run_env_checks  # type: ignore[no-redef]
    except ImportError:
        run_env_checks = None  # type: ignore[assignment]

CORE_PYTHON_TESTS: tuple[str, ...] = (
    "tests/q1q5/test_hsv_color.py",
    "tests/q1q5/test_candidates.py",
    "tests/q1q5/test_clock_mapping.py",
    "tests/q1q5/test_graphs.py",
    "tests/q1q5/test_linker.py",
    "tests/q1q5/test_q3_parse.py",
    "tests/q1q5/test_q3_rules.py",
    "tests/q1q5/test_q4_evidence.py",
    "tests/q1q5/test_q5_controller.py",
    "tests/q1q5/test_event_modes.py",
)


def _run_subprocess(
    cmd: Sequence[str],
    cwd: Path | None = None,
    timeout: float = 30.0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def check_clean_checkout(repo: Path) -> dict[str, Any]:
    """Verify that the working tree is clean (no staged, unstaged, or untracked changes)."""
    try:
        proc = _run_subprocess(
            ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=normal"],
            timeout=15.0,
        )
        changes = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        passed = (proc.returncode == 0) and (len(changes) == 0)
        return {
            "status": "PASS" if passed else "FAIL",
            "returncode": proc.returncode,
            "changes": changes,
            "reason": None if passed else ("CHECKOUT_NOT_CLEAN" if proc.returncode == 0 else "STATUS_COMMAND_FAILED"),
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "FAIL",
            "returncode": -1,
            "reason": "CLEANLINESS_CHECK_FAILED",
            "error": str(exc),
        }


def check_git_rev_parse(repo: Path, base: str = "origin/mainline/q1q5") -> dict[str, Any]:
    try:
        p_head = _run_subprocess(["git", "-C", str(repo), "rev-parse", "HEAD"], timeout=10.0)
        head_sha = p_head.stdout.strip() if p_head.returncode == 0 else None
        p_base = _run_subprocess(["git", "-C", str(repo), "rev-parse", base], timeout=10.0)
        base_sha = p_base.stdout.strip() if p_base.returncode == 0 else None
        head_passed = bool(p_head.returncode == 0 and head_sha and len(head_sha) == 40)
        base_passed = bool(p_base.returncode == 0 and base_sha and len(base_sha) == 40)
        passed = head_passed and base_passed
        return {
            "status": "PASS" if passed else "FAIL",
            "head_sha": head_sha or "UNKNOWN",
            "base_ref": base,
            "base_sha": base_sha or "UNKNOWN",
            "matches_base": bool(head_sha and base_sha and head_sha == base_sha),
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "FAIL",
            "head_sha": "UNKNOWN",
            "base_ref": base,
            "base_sha": "UNKNOWN",
            "matches_base": False,
            "error": str(exc),
        }


def check_git_diff(repo: Path) -> dict[str, Any]:
    try:
        proc = _run_subprocess(
            ["git", "-C", str(repo), "diff", "--check"],
            timeout=15.0,
        )
        findings = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if proc.stderr:
            findings.extend([line.strip() for line in proc.stderr.splitlines() if line.strip()])
        passed = (proc.returncode == 0) and (len(findings) == 0)
        return {
            "status": "PASS" if passed else "FAIL",
            "returncode": proc.returncode,
            "findings": findings,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "FAIL",
            "returncode": -1,
            "findings": [f"Error running git diff --check: {exc}"],
        }


def check_architecture(repo: Path, base: str) -> dict[str, Any]:
    guard_script = repo / "scripts" / "check_architecture_guard.py"
    if not guard_script.is_file():
        return {
            "status": "FAIL",
            "returncode": -1,
            "error": f"Guard script not found at {guard_script}",
        }
    try:
        cmd = [
            sys.executable,
            str(guard_script),
            "--repo",
            str(repo),
            "--base",
            base,
        ]
        proc = _run_subprocess(cmd, timeout=30.0)
        if proc.stdout.strip():
            try:
                guard_output = json.loads(proc.stdout)
                guard_status = guard_output.get("status") if isinstance(guard_output, dict) else None
                passed = (proc.returncode == 0) and (guard_status == "PASS")
                return {
                    "status": "PASS" if passed else "FAIL",
                    "returncode": proc.returncode,
                    "report": guard_output,
                }
            except json.JSONDecodeError:
                pass
        return {
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "FAIL",
            "returncode": -1,
            "error": str(exc),
        }


def run_python_tests(repo: Path, quick: bool = False) -> dict[str, Any]:
    if quick:
        test_files = ["tests/q1q5/test_hsv_color.py"]
    else:
        test_files = list(CORE_PYTHON_TESTS)

    missing = [f for f in test_files if not (repo / f).is_file()]
    if missing:
        return {
            "status": "FAIL",
            "reason": "REQUIRED_PYTHON_TEST_MISSING",
            "missing": missing,
            "test_files": test_files,
        }

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        "pythonpath=src",
        *test_files,
    ]
    display_cmd = ["python", *cmd[1:]]
    t0 = time.monotonic()
    try:
        proc = _run_subprocess(cmd, cwd=repo, timeout=90.0)
        dt = round(time.monotonic() - t0, 3)
        stdout_clean = proc.stdout.strip()
        m_pass = re.search(r"(\d+)\s+passed", stdout_clean)
        m_fail = re.search(r"(\d+)\s+failed", stdout_clean)
        m_skip = re.search(r"(\d+)\s+skipped", stdout_clean)

        if not m_pass and proc.returncode != 0:
            passed_count = None
            failed_count = None
            status = "FAIL"
        elif not m_pass:
            passed_count = None
            failed_count = int(m_fail.group(1)) if m_fail else None
            status = "FAIL"
        else:
            passed_count = int(m_pass.group(1))
            failed_count = int(m_fail.group(1)) if m_fail else 0
            status = "PASS" if proc.returncode == 0 and failed_count == 0 else "FAIL"

        skipped_count = int(m_skip.group(1)) if m_skip else 0

        return {
            "status": status,
            "returncode": proc.returncode,
            "duration_sec": dt,
            "test_files": test_files,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "command": " ".join(display_cmd),
            "output": stdout_clean,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "FAIL",
            "returncode": -1,
            "duration_sec": round(time.monotonic() - t0, 3),
            "test_files": test_files,
            "command": " ".join(display_cmd),
            "error": str(exc),
        }


def run_node_tests(repo: Path) -> dict[str, Any]:
    test_file = repo / "frontend" / "workbench-v2" / "store.test.mjs"
    if not test_file.is_file():
        return {
            "status": "FAIL",
            "reason": "REQUIRED_NODE_TEST_MISSING",
            "file": "frontend/workbench-v2/store.test.mjs",
        }
    cmd = ["node", "--test", "frontend/workbench-v2/store.test.mjs"]
    t0 = time.monotonic()
    try:
        proc = _run_subprocess(cmd, cwd=repo, timeout=30.0)
        dt = round(time.monotonic() - t0, 3)
        stdout_clean = proc.stdout.strip()
        m_pass = re.search(r"(?:^|\s)pass\s+(\d+)", stdout_clean)
        m_fail = re.search(r"(?:^|\s)fail\s+(\d+)", stdout_clean)
        m_skip = re.search(r"(?:^|\s)skipped\s+(\d+)", stdout_clean)

        if not m_pass and proc.returncode != 0:
            passed_count = None
            failed_count = None
            status = "FAIL"
        elif not m_pass:
            passed_count = None
            failed_count = int(m_fail.group(1)) if m_fail else None
            status = "FAIL"
        else:
            passed_count = int(m_pass.group(1))
            failed_count = int(m_fail.group(1)) if m_fail else 0
            status = "PASS" if proc.returncode == 0 and failed_count == 0 else "FAIL"

        return {
            "status": status,
            "returncode": proc.returncode,
            "duration_sec": dt,
            "passed_count": passed_count,
            "failed_count": failed_count,
            "skipped_count": int(m_skip.group(1)) if m_skip else 0,
            "command": " ".join(cmd),
            "output": stdout_clean,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "FAIL",
            "returncode": -1,
            "duration_sec": round(time.monotonic() - t0, 3),
            "command": " ".join(cmd),
            "error": str(exc),
        }


def audit_windows_compatibility(repo: Path) -> dict[str, Any]:
    has_fcntl = importlib.util.find_spec("fcntl") is not None
    has_o_nofollow = hasattr(os, "O_NOFOLLOW")
    has_o_directory = hasattr(os, "O_DIRECTORY")
    pref_enc = locale.getpreferredencoding(False)

    legacy_posix_findings: list[dict[str, Any]] = []
    run_jobs = repo / "src" / "amidst" / "workbench" / "run_jobs.py"
    if run_jobs.is_file():
        txt = run_jobs.read_text(encoding="utf-8", errors="replace")
        if "import fcntl" in txt:
            legacy_posix_findings.append(
                {
                    "code": "POSIX_FCNTL_IMPORT",
                    "path": "src/amidst/workbench/run_jobs.py",
                    "detail": "Unconditional 'import fcntl' fails on Windows (affects legacy workbench run_jobs and linked_workbench imports).",
                }
            )

    for rel_path in ("src/amidst/q1q5/api.py", "src/amidst/q1q5/store.py"):
        target = repo / rel_path
        if target.is_file():
            txt = target.read_text(encoding="utf-8", errors="replace")
            if "O_NOFOLLOW" in txt or "O_DIRECTORY" in txt:
                legacy_posix_findings.append(
                    {
                        "code": "POSIX_OS_OPEN_FLAGS",
                        "path": rel_path,
                        "detail": "Uses POSIX-only os.O_NOFOLLOW / os.O_DIRECTORY flags not present in Windows CRT os module.",
                    }
                )

    test_api = repo / "tests" / "q1q5" / "test_api.py"
    if test_api.is_file():
        legacy_posix_findings.append(
            {
                "code": "WIN_SYMLINK_PRIVILEGE",
                "path": "tests/q1q5/test_api.py",
                "detail": "Creating symlinks on Windows requires elevated privileges or Developer Mode (fails with WinError 1314 without SeCreateSymbolicLinkPrivilege).",
            }
        )

    test_review_ui = repo / "tests" / "q1q5" / "test_review_ui_unavailable.py"
    if test_review_ui.is_file():
        legacy_posix_findings.append(
            {
                "code": "SANDBOX_LOOPBACK_HTTP",
                "path": "tests/q1q5/test_review_ui_unavailable.py",
                "detail": "Loopback HTTP server sockets fail under sandbox isolation with WinError 10013 / permission denied.",
            }
        )

    return {
        "status": "PASS",
        "host_platform": platform.system(),
        "posix_capabilities": {
            "has_fcntl": has_fcntl,
            "has_os_o_nofollow": has_o_nofollow,
            "has_os_o_directory": has_o_directory,
            "locale_preferred_encoding": pref_enc,
        },
        "fixes_applied_in_w_a1": [
            {
                "id": "W-A1-FIX-1",
                "target": "scripts/ensure_env.py, scripts/verify_clean_clone.py",
                "description": "Explicitly set encoding='utf-8', errors='replace' on all subprocess.run calls to prevent UnicodeDecodeError ('cp950') when reading UTF-8 symbols from node --test or pytest on Windows.",
            },
            {
                "id": "W-A1-FIX-2",
                "target": "scripts/ensure_env.py",
                "description": "Aligned environment dependencies and Python version (>=3.12) to match pyproject.toml requirements.",
            },
            {
                "id": "W-A1-FIX-3",
                "target": "scripts/ensure_env.py",
                "description": "Added Windows-native hardware & OS inventory probes via ctypes GlobalMemoryStatusEx (RAM), GetLogicalProcessorInformationEx (physical cores), winreg CentralProcessor\\0 (CPU model), and nvidia-smi + winreg Display fallback (GPU/VRAM).",
            },
        ],
        "legacy_posix_findings": legacy_posix_findings,
    }


def run_clean_clone_verification(
    repo: Path | str = Path.cwd(),
    base: str = "origin/mainline/q1q5",
    quick: bool = False,
    skip_tests: bool = False,
    min_free_gib: float = 8.0,
) -> dict[str, Any]:
    repo_path = Path(repo).resolve()

    # 1. Git HEAD & base SHA check
    git_rev = check_git_rev_parse(repo_path, base=base)

    # 2. Clean checkout check
    clean_checkout = check_clean_checkout(repo_path)

    # 3. Environment & hardware check
    if run_env_checks is not None:
        env_receipt = run_env_checks(repo=repo_path, min_free_gib=min_free_gib)
    else:  # pragma: no cover
        env_receipt = {"status": "UNKNOWN", "note": "ensure_env module unavailable"}

    # 4. Git diff --check
    diff_receipt = check_git_diff(repo_path)

    # 5. Architecture guard
    arch_receipt = check_architecture(repo_path, base=base)

    # 6. Windows/POSIX compatibility audit
    win_audit = audit_windows_compatibility(repo_path)

    checks: dict[str, Any] = {
        "git_rev_parse_head": git_rev,
        "clean_checkout": clean_checkout,
        "ensure_env": env_receipt,
        "environment": env_receipt,
        "git_diff_check": diff_receipt,
        "architecture_guard": arch_receipt,
        "windows_posix_audit": win_audit,
    }

    tests_passed = True
    if not skip_tests:
        py_receipt = run_python_tests(repo_path, quick=quick)
        node_receipt = run_node_tests(repo_path)
        checks["pytest_core"] = py_receipt
        checks["python_tests"] = py_receipt
        checks["node_workbench_v2"] = node_receipt
        checks["node_tests"] = node_receipt
        if py_receipt.get("status") != "PASS" or node_receipt.get("status") != "PASS":
            tests_passed = False
    else:
        skipped_entry = {"status": "SKIPPED", "reason": "--skip-tests requested"}
        checks["tests"] = skipped_entry

    all_passed = (
        git_rev.get("status") == "PASS"
        and clean_checkout.get("status") == "PASS"
        and env_receipt.get("status") == "PASS"
        and diff_receipt.get("status") == "PASS"
        and arch_receipt.get("status") == "PASS"
        and (tests_passed if not skip_tests else True)
    )

    if not all_passed:
        top_status = "FAIL"
    elif skip_tests:
        top_status = "CHECKS_ONLY"
    elif quick:
        top_status = "SMOKE_ONLY"
    else:
        top_status = "PASS"

    scope = "CHECKS_ONLY" if skip_tests else ("SMOKE_ONLY" if quick else "FULL_FOCUSED_GATE")

    return {
        "schema": "amidst.windows_clean_clone_baseline.v1",
        "issue_ref": "#419",
        "status": top_status,
        "verification_scope": scope,
        "repo": ".",
        "base": base,
        "head_sha": git_rev.get("head_sha", "UNKNOWN"),
        "base_sha": git_rev.get("base_sha", "UNKNOWN"),
        "quick": quick,
        "skip_tests": skip_tests,
        "hardware_and_os": env_receipt.get("hardware_and_os", {}),
        "tool_versions": env_receipt.get("tool_versions", {}),
        "checks": checks,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cross-platform clean clone verification CLI."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Path to repository root (default: current directory)",
    )
    parser.add_argument(
        "--base",
        default="origin/mainline/q1q5",
        help="Base git reference for architecture guard (default: origin/mainline/q1q5)",
    )
    parser.add_argument(
        "--min-free-gib",
        type=float,
        default=8.0,
        help="Minimum required free disk space in GiB (default: 8.0)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick verification mode (runs minimal focused test subset)",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip running pytest and node test suites",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured JSON verification receipt to stdout",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write structured JSON verification receipt to the specified file path",
    )
    args = parser.parse_args(argv)

    receipt = run_clean_clone_verification(
        repo=args.repo,
        base=args.base,
        quick=args.quick,
        skip_tests=args.skip_tests,
        min_free_gib=args.min_free_gib,
    )

    json_str = json.dumps(receipt, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json_str + "\n", encoding="utf-8")

    if args.json:
        print(json_str)
    else:
        print(f"Amidst Clean Clone Verification: {receipt['status']}")
        print(f"  Repo:               {receipt['repo']}")
        print(f"  HEAD SHA:           {receipt['head_sha']}")
        print(f"  Base ({receipt['base']}): {receipt['base_sha']}")
        print(f"  Environment:        {receipt['checks']['environment'].get('status')}")
        print(f"  Git diff check:     {receipt['checks']['git_diff_check'].get('status')}")
        print(f"  Architecture guard: {receipt['checks']['architecture_guard'].get('status')}")
        if "python_tests" in receipt["checks"]:
            print(f"  Python tests:       {receipt['checks']['python_tests'].get('status')}")
        if "node_tests" in receipt["checks"]:
            print(f"  Node tests:         {receipt['checks']['node_tests'].get('status')}")
        if "tests" in receipt["checks"]:
            print(f"  Tests:              {receipt['checks']['tests'].get('status')}")

    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
