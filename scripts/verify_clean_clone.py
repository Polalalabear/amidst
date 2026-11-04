#!/usr/bin/env python3
"""Cross-platform clean clone verification CLI for Amidst Q1-Q5 demo.

Replaces verify_clean_clone.sh with a portable, structured Python script.
Executes:
1. Environment self-check (scripts/ensure_env.py)
2. Git diff check (git diff --check)
3. Architecture guard (scripts/check_architecture_guard.py)
4. Focused automated tests (pytest & node --test), unless --skip-tests

Emits a structured JSON verification receipt and exits 0 on PASS, non-zero on FAIL.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Sequence

# Import ensure_env from sibling or local script
try:
    from scripts.ensure_env import run_env_checks
except ImportError:
    # Fallback if scripts directory is in path or invoked directly
    try:
        from ensure_env import run_env_checks  # type: ignore[no-redef]
    except ImportError:
        run_env_checks = None  # type: ignore[assignment]


def check_git_diff(repo: Path) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "diff", "--check"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        passed = proc.returncode == 0
        findings = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
        if proc.stderr:
            findings.extend([line.strip() for line in proc.stderr.splitlines() if line.strip()])
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
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.stdout.strip():
            try:
                guard_output = json.loads(proc.stdout)
                status = guard_output.get("status", "FAIL")
                return {
                    "status": status,
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
    test_files = ["tests/q1q5/test_hsv_color.py"]
    if not quick:
        cross_platform_test = repo / "tests" / "q1q5" / "test_cross_platform_scripts.py"
        if cross_platform_test.is_file():
            test_files.append("tests/q1q5/test_cross_platform_scripts.py")

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-o",
        "pythonpath=src",
        "-q",
        *test_files,
    ]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        dt = round(time.monotonic() - t0, 3)
        return {
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "returncode": proc.returncode,
            "duration_sec": dt,
            "command": " ".join(cmd),
            "output": proc.stdout.strip() if proc.returncode != 0 else "All tests passed",
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "FAIL",
            "returncode": -1,
            "duration_sec": round(time.monotonic() - t0, 3),
            "command": " ".join(cmd),
            "error": str(exc),
        }


def run_node_tests(repo: Path) -> dict[str, Any]:
    test_file = repo / "frontend" / "workbench-v2" / "store.test.mjs"
    if not test_file.is_file():
        return {
            "status": "SKIPPED",
            "note": f"Node test file not found at {test_file}",
        }
    cmd = ["node", "--test", "frontend/workbench-v2/store.test.mjs"]
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        dt = round(time.monotonic() - t0, 3)
        return {
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "returncode": proc.returncode,
            "duration_sec": dt,
            "command": " ".join(cmd),
            "output": proc.stdout.strip() if proc.returncode != 0 else "Node tests passed",
        }
    except Exception as exc:  # pragma: no cover
        return {
            "status": "FAIL",
            "returncode": -1,
            "duration_sec": round(time.monotonic() - t0, 3),
            "command": " ".join(cmd),
            "error": str(exc),
        }


def run_clean_clone_verification(
    repo: Path | str = Path.cwd(),
    base: str = "origin/mainline/q1q5",
    quick: bool = False,
    skip_tests: bool = False,
    min_free_gib: float = 8.0,
) -> dict[str, Any]:
    repo_path = Path(repo).resolve()

    # 1. Environment check
    if run_env_checks is not None:
        env_receipt = run_env_checks(repo=repo_path, min_free_gib=min_free_gib)
    else:  # pragma: no cover
        env_receipt = {"status": "UNKNOWN", "note": "ensure_env module unavailable"}

    # 2. Git diff --check
    diff_receipt = check_git_diff(repo_path)

    # 3. Architecture guard
    arch_receipt = check_architecture(repo_path, base=base)

    # 4. Tests
    checks: dict[str, Any] = {
        "environment": env_receipt,
        "git_diff_check": diff_receipt,
        "architecture_guard": arch_receipt,
    }

    tests_passed = True
    if not skip_tests:
        py_receipt = run_python_tests(repo_path, quick=quick)
        node_receipt = run_node_tests(repo_path)
        checks["python_tests"] = py_receipt
        checks["node_tests"] = node_receipt
        if py_receipt.get("status") != "PASS" or node_receipt.get("status") not in {"PASS", "SKIPPED"}:
            tests_passed = False
    else:
        checks["tests"] = {"status": "SKIPPED", "reason": "--skip-tests requested"}

    all_passed = (
        env_receipt.get("status") == "PASS"
        and diff_receipt.get("status") == "PASS"
        and arch_receipt.get("status") == "PASS"
        and tests_passed
    )

    return {
        "status": "PASS" if all_passed else "FAIL",
        "repo": str(repo_path),
        "base": base,
        "quick": quick,
        "skip_tests": skip_tests,
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
    args = parser.parse_args(argv)

    receipt = run_clean_clone_verification(
        repo=args.repo,
        base=args.base,
        quick=args.quick,
        skip_tests=args.skip_tests,
        min_free_gib=args.min_free_gib,
    )

    json_str = json.dumps(receipt, indent=2, sort_keys=True)
    if args.json:
        print(json_str)
    else:
        print(f"Amidst Clean Clone Verification: {receipt['status']}")
        print(f"  Repo: {receipt['repo']}")
        print(f"  Base: {receipt['base']}")
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
