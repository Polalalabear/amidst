#!/usr/bin/env python3
"""Cross-platform environment self-check CLI for Amidst Q1-Q5 demo.

Verifies:
- Python version >= 3.11
- Node.js availability (node --version)
- Git availability (git --version)
- Free disk space >= min_free_gib (default 8.0 GiB per D118)
- Required Python packages (numpy, pydantic, networkx, shapely, PIL, pytest)
- Required repository directories (src/amidst/q1q5, frontend/workbench-v2, configs/q1q5)

Exits 0 if all required checks pass, non-zero if any required check fails.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Sequence

REQUIRED_PACKAGES: tuple[str, ...] = (
    "numpy",
    "pydantic",
    "networkx",
    "shapely",
    "PIL",
    "pytest",
)

REQUIRED_DIRS: tuple[str, ...] = (
    "src/amidst/q1q5",
    "frontend/workbench-v2",
    "configs/q1q5",
)


def check_python() -> dict[str, Any]:
    ver_str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    passed = sys.version_info >= (3, 11)
    return {
        "version": ver_str,
        "required": ">=3.11",
        "passed": passed,
    }


def check_node() -> dict[str, Any]:
    node_bin = shutil.which("node")
    if not node_bin:
        return {"available": False, "version": None, "passed": False}
    try:
        proc = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            return {"available": True, "version": proc.stdout.strip(), "passed": True}
        return {
            "available": False,
            "version": None,
            "passed": False,
            "error": proc.stderr.strip(),
        }
    except Exception as exc:  # pragma: no cover
        return {"available": False, "version": None, "passed": False, "error": str(exc)}


def check_git() -> dict[str, Any]:
    git_bin = shutil.which("git")
    if not git_bin:
        return {"available": False, "version": None, "passed": False}
    try:
        proc = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0:
            return {"available": True, "version": proc.stdout.strip(), "passed": True}
        return {
            "available": False,
            "version": None,
            "passed": False,
            "error": proc.stderr.strip(),
        }
    except Exception as exc:  # pragma: no cover
        return {"available": False, "version": None, "passed": False, "error": str(exc)}


def check_disk(path: Path, min_free_gib: float = 8.0) -> dict[str, Any]:
    probe_dir = path
    while not probe_dir.exists() and probe_dir.parent != probe_dir:
        probe_dir = probe_dir.parent
    try:
        usage = shutil.disk_usage(probe_dir)
        free_gib = usage.free / (1024 ** 3)
        passed = free_gib >= min_free_gib
        return {
            "path": str(probe_dir),
            "free_bytes": usage.free,
            "free_gib": round(free_gib, 3),
            "min_required_gib": float(min_free_gib),
            "passed": passed,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "path": str(probe_dir),
            "free_bytes": 0,
            "free_gib": 0.0,
            "min_required_gib": float(min_free_gib),
            "passed": False,
            "error": str(exc),
        }


def check_package(name: str) -> dict[str, Any]:
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, AttributeError, ValueError) as exc:
        return {"installed": False, "version": None, "error": str(exc), "passed": False}
    if spec is None:
        return {"installed": False, "version": None, "passed": False}
    try:
        mod = importlib.import_module(name)
        ver = getattr(mod, "__version__", "installed")
        return {"installed": True, "version": str(ver), "passed": True}
    except Exception as exc:  # pragma: no cover
        return {"installed": False, "version": None, "error": str(exc), "passed": False}


def check_directories(
    repo: Path, required_dirs: Sequence[str] = REQUIRED_DIRS
) -> dict[str, Any]:
    results: dict[str, bool] = {}
    all_passed = True
    for rel_dir in required_dirs:
        target = repo / rel_dir
        exists = target.is_dir()
        results[rel_dir] = exists
        if not exists:
            all_passed = False
    return {"directories": results, "passed": all_passed}


def run_env_checks(
    repo: Path | str = Path.cwd(),
    min_free_gib: float = 8.0,
    required_packages: Sequence[str] = REQUIRED_PACKAGES,
    required_dirs: Sequence[str] = REQUIRED_DIRS,
) -> dict[str, Any]:
    repo_path = Path(repo).resolve()
    py_info = check_python()
    node_info = check_node()
    git_info = check_git()
    disk_info = check_disk(repo_path, min_free_gib=min_free_gib)

    pkg_results: dict[str, Any] = {}
    pkgs_passed = True
    for pkg in required_packages:
        res = check_package(pkg)
        pkg_results[pkg] = res
        if not res["passed"]:
            pkgs_passed = False

    dir_info = check_directories(repo_path, required_dirs=required_dirs)

    all_passed = (
        py_info["passed"]
        and node_info["passed"]
        and git_info["passed"]
        and disk_info["passed"]
        and pkgs_passed
        and dir_info["passed"]
    )

    return {
        "status": "PASS" if all_passed else "FAIL",
        "python": py_info,
        "node": node_info,
        "git": git_info,
        "disk": disk_info,
        "packages": pkg_results,
        "packages_passed": pkgs_passed,
        "directories": dir_info["directories"],
        "directories_passed": dir_info["passed"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Cross-platform environment self-check for Amidst Q1-Q5 demo."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path.cwd(),
        help="Path to repository root (default: current directory)",
    )
    parser.add_argument(
        "--min-free-gib",
        type=float,
        default=8.0,
        help="Minimum required free disk space in GiB per D118 (default: 8.0)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output deterministic JSON receipt to stdout",
    )
    args = parser.parse_args(argv)

    receipt = run_env_checks(repo=args.repo, min_free_gib=args.min_free_gib)
    json_output = json.dumps(receipt, indent=2, sort_keys=True)

    if args.json:
        print(json_output)
    else:
        print(f"Amidst Environment Self-Check: {receipt['status']}")
        print(f"  Python: {receipt['python']['version']} (passed: {receipt['python']['passed']})")
        print(f"  Node:   {receipt['node']['version']} (available: {receipt['node']['available']})")
        print(f"  Git:    {receipt['git']['version']} (available: {receipt['git']['available']})")
        print(
            f"  Disk:   {receipt['disk']['free_gib']} GiB free (target: >= {receipt['disk']['min_required_gib']} GiB, passed: {receipt['disk']['passed']})"
        )
        print("  Packages:")
        for pkg, details in receipt["packages"].items():
            state = "installed (" + str(details.get("version")) + ")" if details["installed"] else "MISSING"
            print(f"    - {pkg:10s}: {state}")
        print("  Directories:")
        for d, exists in receipt["directories"].items():
            print(f"    - {d:25s}: {'found' if exists else 'MISSING'}")

    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
