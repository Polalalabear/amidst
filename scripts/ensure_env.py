#!/usr/bin/env python3
"""Cross-platform environment and hardware self-check CLI for Amidst Q1-Q5 demo.

Verifies:
- Python version >= 3.12 (the pyproject.toml minimum)
- Node.js availability (node --version)
- Git availability (git --version)
- uv availability (uv --version, optional tool inventory)
- pytest availability (pytest.__version__)
- Free disk space >= min_free_gib (default 8.0 GiB per D118)
- Required Python packages per pyproject (numpy, pydantic, networkx, shapely, PIL, pytest)
- Required repository directories (src/amidst/q1q5, frontend/workbench-v2, configs/q1q5)
- Complete hardware and OS inventory (OS, CPU, RAM, GPU/VRAM, Disk)

Exits 0 if all required checks pass, non-zero if any required check fails.
"""
from __future__ import annotations

import argparse
import ctypes
import importlib
import importlib.util
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tomllib
from typing import Any, Sequence

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet

REQUIRED_PACKAGES: tuple[str, ...] = (
    "numpy",
    "pydantic",
    "networkx",
    "shapely",
    "PIL",
    "pytest",
)

OPTIONAL_PACKAGES: tuple[str, ...] = ()

REQUIRED_DIRS: tuple[str, ...] = (
    "src/amidst/q1q5",
    "frontend/workbench-v2",
    "configs/q1q5",
)


def _run_cmd(cmd: Sequence[str], timeout: float = 5.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(cmd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def check_python(repo: Path | str = Path.cwd()) -> dict[str, Any]:
    ver_str = f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}"
    try:
        pyproject = Path(repo) / "pyproject.toml"
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        required = project["project"]["requires-python"]
        passed = SpecifierSet(required).contains(ver_str, prereleases=True)
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError, ValueError) as exc:
        required = "UNKNOWN"
        passed = False
        error = str(exc)
    exe_name = Path(sys.executable).name or "python"
    try:
        cwd = Path.cwd().resolve()
        exe_path = Path(sys.executable).resolve()
        if exe_path.is_relative_to(cwd):
            rel_exe = exe_path.relative_to(cwd).as_posix()
        else:
            rel_exe = exe_name
    except Exception:
        rel_exe = exe_name
    result = {
        "version": ver_str,
        "implementation": platform.python_implementation(),
        "executable": rel_exe,
        "required": required,
        "passed": passed,
    }
    if not passed and required == "UNKNOWN":
        result["error"] = error
    return result


def check_node() -> dict[str, Any]:
    node_bin = shutil.which("node")
    if not node_bin:
        return {"available": False, "version": None, "passed": False}
    try:
        proc = _run_cmd(["node", "--version"], timeout=5.0)
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
        proc = _run_cmd(["git", "--version"], timeout=5.0)
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


def check_uv() -> dict[str, Any]:
    uv_bin = shutil.which("uv")
    if not uv_bin:
        return {"available": False, "version": "UNKNOWN", "passed": True}
    try:
        proc = _run_cmd(["uv", "--version"], timeout=5.0)
        if proc.returncode == 0:
            return {"available": True, "version": proc.stdout.strip(), "passed": True}
        return {
            "available": False,
            "version": "UNKNOWN",
            "passed": True,
            "error": proc.stderr.strip(),
        }
    except Exception as exc:  # pragma: no cover
        return {"available": False, "version": "UNKNOWN", "passed": True, "error": str(exc)}


def check_pytest() -> dict[str, Any]:
    pkg = check_package("pytest")
    return {
        "available": bool(pkg.get("installed")),
        "version": pkg.get("version"),
        "passed": bool(pkg.get("passed")),
    }


def check_disk(path: Path, min_free_gib: float = 8.0) -> dict[str, Any]:
    probe_dir = path
    while not probe_dir.exists() and probe_dir.parent != probe_dir:
        probe_dir = probe_dir.parent
    try:
        usage = shutil.disk_usage(probe_dir)
        total_gib = usage.total / (1024 ** 3)
        free_gib = usage.free / (1024 ** 3)
        passed = free_gib >= min_free_gib
        rel_path = "."
        try:
            cwd = Path.cwd().resolve()
            if probe_dir.resolve() == cwd or probe_dir.resolve().is_relative_to(cwd):
                rel_path = probe_dir.resolve().relative_to(cwd).as_posix() or "."
            else:
                rel_path = "."
        except Exception:
            rel_path = "."
        return {
            "path": rel_path,
            "total_bytes": usage.total,
            "total_gib": round(total_gib, 3),
            "free_bytes": usage.free,
            "free_gib": round(free_gib, 3),
            "min_required_gib": float(min_free_gib),
            "passed": passed,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "path": ".",
            "total_bytes": 0,
            "total_gib": 0.0,
            "free_bytes": 0,
            "free_gib": 0.0,
            "min_required_gib": float(min_free_gib),
            "passed": False,
            "error": str(exc),
        }


def check_package(name: str, required: bool = True) -> dict[str, Any]:
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, AttributeError, ValueError) as exc:
        return {
            "installed": False,
            "version": None,
            "required": required,
            "error": str(exc),
            "passed": not required,
        }
    if spec is None:
        return {
            "installed": False,
            "version": None,
            "required": required,
            "passed": not required,
        }
    try:
        mod = importlib.import_module(name)
        ver = getattr(mod, "__version__", "installed")
        return {
            "installed": True,
            "version": str(ver),
            "required": required,
            "passed": True,
        }
    except Exception as exc:  # pragma: no cover
        return {
            "installed": False,
            "version": None,
            "required": required,
            "error": str(exc),
            "passed": not required,
        }


def check_project_dependencies(repo: Path) -> dict[str, Any]:
    """Compare installed runtime and development distributions to pyproject specs."""
    pyproject = repo / "pyproject.toml"
    try:
        project = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        raw_requirements = [
            ("runtime", raw) for raw in project["project"]["dependencies"]
        ]
        raw_requirements.extend(
            ("dev", raw)
            for raw in project.get("dependency-groups", {}).get("dev", [])
        )
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        return {
            "status": "FAIL",
            "passed": False,
            "source": "pyproject.toml",
            "reason": "PROJECT_REQUIREMENTS_UNAVAILABLE",
            "error": str(exc),
            "dependencies": [],
        }

    results: list[dict[str, Any]] = []
    for group, raw in raw_requirements:
        try:
            requirement = Requirement(raw)
            if requirement.marker is not None and not requirement.marker.evaluate():
                results.append(
                    {
                        "name": requirement.name,
                        "group": group,
                        "specifier": str(requirement.specifier),
                        "applicable": False,
                        "passed": True,
                    }
                )
                continue
            installed_version = metadata.version(requirement.name)
            passed = requirement.specifier.contains(installed_version, prereleases=True)
            results.append(
                {
                    "name": requirement.name,
                    "group": group,
                    "specifier": str(requirement.specifier),
                    "version": installed_version,
                    "applicable": True,
                    "passed": passed,
                }
            )
        except metadata.PackageNotFoundError:
            results.append(
                {
                    "name": requirement.name,
                    "group": group,
                    "specifier": str(requirement.specifier),
                    "version": None,
                    "applicable": True,
                    "passed": False,
                    "reason": "PACKAGE_NOT_INSTALLED",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "name": raw,
                    "group": group,
                    "applicable": True,
                    "passed": False,
                    "reason": "REQUIREMENT_CHECK_FAILED",
                    "error": str(exc),
                }
            )

    passed = bool(results) and all(item["passed"] for item in results)
    return {
        "status": "PASS" if passed else "FAIL",
        "passed": passed,
        "source": "pyproject.toml",
        "scope": ["project.dependencies", "dependency-groups.dev"],
        "dependencies": results,
    }
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


def collect_os_info() -> dict[str, Any]:
    return {
        "system": platform.system() or "UNKNOWN",
        "release": platform.release() or "UNKNOWN",
        "version": platform.version() or "UNKNOWN",
        "platform": platform.platform() or "UNKNOWN",
        "machine": platform.machine() or "UNKNOWN",
    }


def _windows_cpu_model() -> str | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        key_path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            val, _ = winreg.QueryValueEx(key, "ProcessorNameString")
            if isinstance(val, str) and val.strip():
                return val.strip()
    except Exception:
        pass
    return None


def _windows_physical_cores() -> int | None:
    if sys.platform != "win32":
        return None
    try:
        relation_processor_core = 0
        length = ctypes.c_ulong(0)
        kernel32 = ctypes.windll.kernel32
        kernel32.GetLogicalProcessorInformationEx(
            relation_processor_core, None, ctypes.byref(length)
        )
        if length.value <= 0:
            return None
        buf = (ctypes.c_ubyte * length.value)()
        ok = kernel32.GetLogicalProcessorInformationEx(
            relation_processor_core, buf, ctypes.byref(length)
        )
        if not ok:
            return None
        raw = bytes(buf)
        offset = 0
        cores = 0
        while offset + 8 <= len(raw):
            size = int.from_bytes(raw[offset + 4 : offset + 8], "little")
            if size <= 0:
                break
            cores += 1
            offset += size
        return cores if cores > 0 else None
    except Exception:
        return None


def collect_cpu_info() -> dict[str, Any]:
    logical_cores = os.cpu_count()
    model: str | None = None
    physical_cores: int | None = None

    if sys.platform == "win32":
        model = _windows_cpu_model()
        physical_cores = _windows_physical_cores()
    elif sys.platform == "darwin":
        try:
            p_brand = _run_cmd(["sysctl", "-n", "machdep.cpu.brand_string"], timeout=3.0)
            if p_brand.returncode == 0 and p_brand.stdout.strip():
                model = p_brand.stdout.strip()
            p_phys = _run_cmd(["sysctl", "-n", "hw.physicalcpu"], timeout=3.0)
            if p_phys.returncode == 0 and p_phys.stdout.strip().isdigit():
                physical_cores = int(p_phys.stdout.strip())
        except Exception:
            pass
    else:
        cpuinfo = Path("/proc/cpuinfo")
        if cpuinfo.is_file():
            try:
                text = cpuinfo.read_text(encoding="utf-8", errors="replace")
                for line in text.splitlines():
                    if ":" in line and line.lower().startswith("model name"):
                        model = line.split(":", 1)[1].strip()
                        break
                core_ids = {
                    line.split(":", 1)[1].strip()
                    for line in text.splitlines()
                    if line.lower().startswith("core id") and ":" in line
                }
                if core_ids:
                    physical_cores = len(core_ids)
            except Exception:
                pass

    if not model:
        proc_name = platform.processor()
        model = proc_name.strip() if proc_name and proc_name.strip() else "UNKNOWN"

    return {
        "model": model,
        "logical_cores": logical_cores if logical_cores is not None else "UNKNOWN",
        "physical_cores": physical_cores if physical_cores is not None else "UNKNOWN",
    }


def collect_ram_info() -> dict[str, Any]:
    total_bytes: int | None = None
    avail_bytes: int | None = None

    if sys.platform == "win32":
        try:
            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_bytes = int(stat.ullTotalPhys)
                avail_bytes = int(stat.ullAvailPhys)
        except Exception:
            pass
    elif sys.platform == "darwin":
        try:
            proc = _run_cmd(["sysctl", "-n", "hw.memsize"], timeout=3.0)
            if proc.returncode == 0 and proc.stdout.strip().isdigit():
                total_bytes = int(proc.stdout.strip())
        except Exception:
            pass
    else:
        meminfo = Path("/proc/meminfo")
        if meminfo.is_file():
            try:
                for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            total_bytes = int(parts[1]) * 1024
                    elif line.startswith("MemAvailable:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            avail_bytes = int(parts[1]) * 1024
            except Exception:
                pass

    if total_bytes is None or total_bytes <= 0:
        return {
            "total_bytes": "UNKNOWN",
            "total_gib": "UNKNOWN",
            "total_gb": "UNKNOWN",
        }

    result: dict[str, Any] = {
        "total_bytes": total_bytes,
        "total_gib": round(total_bytes / (1024 ** 3), 2),
        "total_gb": round(total_bytes / (1000 ** 3), 2),
    }
    if avail_bytes is not None and avail_bytes >= 0:
        result["available_gib"] = round(avail_bytes / (1024 ** 3), 2)
    return result


def collect_gpu_info() -> dict[str, Any]:
    gpus: list[dict[str, Any]] = []
    probe_source = "none"

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            proc = _run_cmd(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total,driver_version",
                    "--format=csv,noheader",
                ],
                timeout=5.0,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                for raw_line in proc.stdout.splitlines():
                    parts = [p.strip() for p in raw_line.split(",")]
                    if not parts or not parts[0]:
                        continue
                    name = parts[0]
                    vram_str = parts[1] if len(parts) > 1 else ""
                    driver = parts[2] if len(parts) > 2 else "UNKNOWN"
                    m = re.search(r"(\d+)", vram_str)
                    vram_mib: int | str = int(m.group(1)) if m else "UNKNOWN"
                    vram_gib: float | str = (
                        round(vram_mib / 1024.0, 2) if isinstance(vram_mib, int) else "UNKNOWN"
                    )
                    gpus.append(
                        {
                            "model": name,
                            "vram_mib": vram_mib,
                            "vram_gib": vram_gib,
                            "driver_version": driver,
                        }
                    )
                if gpus:
                    probe_source = "nvidia-smi"
        except Exception:
            pass

    if not gpus and sys.platform == "win32":
        try:
            ps_cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json -Compress",
            ]
            proc = _run_cmd(ps_cmd, timeout=5.0)
            if proc.returncode == 0 and proc.stdout.strip():
                try:
                    data = json.loads(proc.stdout.strip())
                    if isinstance(data, dict):
                        data = [data]
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        name = item.get("Name")
                        if not name or not str(name).strip():
                            continue
                        ram_val = item.get("AdapterRAM")
                        vram_mib_val: int | str = "UNKNOWN"
                        vram_gib_val: float | str = "UNKNOWN"
                        if isinstance(ram_val, (int, float)) and ram_val > 0:
                            vram_mib_val = int(ram_val // (1024 ** 2))
                            vram_gib_val = round(ram_val / (1024 ** 3), 2)
                        drv_ver = str(item.get("DriverVersion") or "UNKNOWN")
                        gpus.append(
                            {
                                "model": str(name).strip(),
                                "vram_mib": vram_mib_val,
                                "vram_gib": vram_gib_val,
                                "driver_version": drv_ver,
                            }
                        )
                    if gpus:
                        probe_source = "powershell_cim"
                except Exception:
                    pass
        except Exception:
            pass

    if not gpus and sys.platform == "win32":
        try:
            import winreg

            display_cls = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, display_cls) as root_key:
                for idx in range(16):
                    try:
                        with winreg.OpenKey(root_key, f"{idx:04d}") as sub_key:
                            desc, _ = winreg.QueryValueEx(sub_key, "DriverDesc")
                            if not isinstance(desc, str) or not desc.strip():
                                continue
                            vram_bytes: int | None = None
                            for val_name in (
                                "HardwareInformation.qwMemorySize",
                                "HardwareInformation.MemorySize",
                            ):
                                try:
                                    v, _ = winreg.QueryValueEx(sub_key, val_name)
                                    if isinstance(v, int) and v > 0:
                                        vram_bytes = v
                                        break
                                except OSError:
                                    continue
                            try:
                                drv, _ = winreg.QueryValueEx(sub_key, "DriverVersion")
                                driver_ver = str(drv)
                            except OSError:
                                driver_ver = "UNKNOWN"
                            vram_mib_val: int | str = (
                                int(vram_bytes // (1024 ** 2))
                                if vram_bytes is not None
                                else "UNKNOWN"
                            )
                            vram_gib_val: float | str = (
                                round(vram_bytes / (1024 ** 3), 2)
                                if vram_bytes is not None
                                else "UNKNOWN"
                            )
                            gpus.append(
                                {
                                    "model": desc.strip(),
                                    "vram_mib": vram_mib_val,
                                    "vram_gib": vram_gib_val,
                                    "driver_version": driver_ver,
                                }
                            )
                    except OSError:
                        continue
            if gpus:
                probe_source = "winreg_display_class"
        except Exception:
            pass

    if not gpus:
        return {
            "available": False,
            "model": "UNKNOWN",
            "vram_mib": "UNKNOWN",
            "vram_gib": "UNKNOWN",
            "driver_version": "UNKNOWN",
            "probe_source": probe_source,
            "gpus": [],
        }

    primary = gpus[0]
    return {
        "available": True,
        "model": primary["model"],
        "vram_mib": primary["vram_mib"],
        "vram_gib": primary["vram_gib"],
        "driver_version": primary["driver_version"],
        "probe_source": probe_source,
        "gpus": gpus,
    }


def collect_hardware_and_os(
    repo: Path | str = Path.cwd(), min_free_gib: float = 8.0
) -> dict[str, Any]:
    repo_path = Path(repo).resolve()
    return {
        "os": collect_os_info(),
        "cpu": collect_cpu_info(),
        "ram": collect_ram_info(),
        "gpu": collect_gpu_info(),
        "disk": check_disk(repo_path, min_free_gib=min_free_gib),
    }


def run_env_checks(
    repo: Path | str = Path.cwd(),
    min_free_gib: float = 8.0,
    required_packages: Sequence[str] = REQUIRED_PACKAGES,
    required_dirs: Sequence[str] = REQUIRED_DIRS,
    optional_packages: Sequence[str] = OPTIONAL_PACKAGES,
) -> dict[str, Any]:
    repo_path = Path(repo).resolve()
    py_info = check_python(repo_path)
    node_info = check_node()
    git_info = check_git()
    uv_info = check_uv()
    pytest_info = check_pytest()
    hw_os = collect_hardware_and_os(repo_path, min_free_gib=min_free_gib)
    disk_info = hw_os["disk"]

    pkg_results: dict[str, Any] = {}
    pkgs_passed = True
    for pkg in required_packages:
        res = check_package(pkg, required=True)
        pkg_results[pkg] = res
        if not res["passed"]:
            pkgs_passed = False

    opt_pkg_results: dict[str, Any] = {}
    for pkg in optional_packages:
        opt_pkg_results[pkg] = check_package(pkg, required=False)

    project_dependency_info = check_project_dependencies(repo_path)
    pkgs_passed = pkgs_passed and project_dependency_info["passed"]

    dir_info = check_directories(repo_path, required_dirs=required_dirs)

    all_passed = (
        py_info["passed"]
        and node_info["passed"]
        and git_info["passed"]
        and disk_info["passed"]
        and pkgs_passed
        and dir_info["passed"]
    )

    tool_versions = {
        "python": py_info["version"],
        "node": node_info["version"],
        "uv": uv_info["version"],
        "git": git_info["version"],
        "pytest": pytest_info["version"],
    }

    return {
        "status": "PASS" if all_passed else "FAIL",
        "python": py_info,
        "node": node_info,
        "uv": uv_info,
        "git": git_info,
        "pytest": pytest_info,
        "tool_versions": tool_versions,
        "hardware_and_os": hw_os,
        "disk": disk_info,
        "packages": pkg_results,
        "project_dependencies": project_dependency_info,
        "optional_packages": opt_pkg_results,
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
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write deterministic JSON receipt to the specified file path",
    )
    args = parser.parse_args(argv)

    receipt = run_env_checks(repo=args.repo, min_free_gib=args.min_free_gib)
    json_output = json.dumps(receipt, indent=2, sort_keys=True)

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json_output + "\n", encoding="utf-8")

    if args.json:
        print(json_output)
    else:
        hw = receipt["hardware_and_os"]
        print(f"Amidst Environment Self-Check: {receipt['status']}")
        print(
            f"  OS:     {hw['os']['system']} {hw['os']['release']} ({hw['os']['version']}, {hw['os']['machine']})"
        )
        print(
            f"  CPU:    {hw['cpu']['model']} (physical: {hw['cpu']['physical_cores']}, logical: {hw['cpu']['logical_cores']})"
        )
        print(f"  RAM:    {hw['ram']['total_gib']} GiB ({hw['ram']['total_gb']} GB)")
        print(
            f"  GPU:    {hw['gpu']['model']} (VRAM: {hw['gpu']['vram_mib']} MiB / {hw['gpu']['vram_gib']} GiB)"
        )
        print(f"  Python: {receipt['python']['version']} (passed: {receipt['python']['passed']})")
        print(f"  Node:   {receipt['node']['version']} (available: {receipt['node']['available']})")
        print(f"  uv:     {receipt['uv']['version']} (available: {receipt['uv']['available']})")
        print(f"  Git:    {receipt['git']['version']} (available: {receipt['git']['available']})")
        print(f"  pytest: {receipt['pytest']['version']} (available: {receipt['pytest']['available']})")
        print(
            f"  Disk:   {receipt['disk']['free_gib']} GiB free (target: >= {receipt['disk']['min_required_gib']} GiB, passed: {receipt['disk']['passed']})"
        )
        print("  Required Packages:")
        for pkg, details in receipt["packages"].items():
            state = (
                "installed (" + str(details.get("version")) + ")"
                if details["installed"]
                else "MISSING"
            )
            print(f"    - {pkg:10s}: {state}")
        print("  Optional Packages:")
        for pkg, details in receipt["optional_packages"].items():
            state = (
                "installed (" + str(details.get("version")) + ")"
                if details["installed"]
                else "not installed (optional)"
            )
            print(f"    - {pkg:10s}: {state}")
        print("  Directories:")
        for d, exists in receipt["directories"].items():
            print(f"    - {d:25s}: {'found' if exists else 'MISSING'}")

    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
