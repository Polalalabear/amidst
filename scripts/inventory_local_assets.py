#!/usr/bin/env python3
"""Read-only inventory and classification tool for ``local/`` assets (#729, D384, D387).

STRICTLY READ-ONLY: never deletes, moves, or modifies anything under ``local/``.
Scans a ``local/`` root (or compatible datapack root), cross-references merged repo
docs/configs/code/demo-pin/reproduce-manifest, classifies each item into:
  - KEEP
  - DELETABLE_CANDIDATE
  - UNCERTAIN
and flags ``is_obviously_stale_or_broken`` for a dedicated Markdown section (D387).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sys
from typing import Any

# Reuse LOCAL path regex from check_local_artifact_refs.py when available.
try:
    from scripts.check_local_artifact_refs import GOOD as _LOCAL_REF_RE
except ImportError:
    try:
        from check_local_artifact_refs import GOOD as _LOCAL_REF_RE  # type: ignore[no-redef]
    except ImportError:
        _LOCAL_REF_RE = re.compile(
            r"(?<![\w/.-])(?:local/(?:data|evidence|archive)/|\$\{?AMIDST_ARTIFACTS\}?/)[^\s`\"'|)\]>,;]+"
        )

AREAS = ("data", "evidence", "archive")
SKIP_REPO_DIRS = {".git", ".venv", "node_modules", "__pycache__", ".pytest_cache", "local", ".local"}
SCAN_TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".toml", ".py", ".mjs", ".js", ".sh", ".ps1", ".command", ".txt"}

# Protected original asset patterns (NEVER mark deletable — list only, never delete).
PROTECTED_EXTS = {".blend", ".blend1", ".blend2", ".mp4", ".mov", ".mkv", ".avi", ".webm"}
PROTECTED_NAME_TOKENS = {
    "gt",
    "gt_private",
    "gt-private",
    "gt-boxes",
    "gt_boxes",
    "ground_truth",
    "ground-truth",
    "calibration",
    "calib",
    "raw_video",
    "raw-video",
    "original_assets",
}

# Obvious cache / temp / broken / stale markers.
CACHE_EXACT_NAMES = {
    "uv-cache",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".ds_store",
    "thumbs.db",
    "tmp",
    "temp",
    ".tmp",
}
CACHE_EXTS = {".tmp", ".temp", ".part", ".partial", ".bak", ".swp", ".pyc"}
STALE_OR_BROKEN_TOKENS = (
    "failed",
    "aborted",
    "broken",
    "corrupt",
    "corrupted",
    "incomplete",
    "stale",
    "obsolete",
    "deprecated",
    "old-",
    "-old",
    "_old",
    "scratch",
    "debug-tmp",
)

MANIFEST_FILENAMES = ("MANIFEST.sha256", "EVIDENCE_MANIFEST.json", "MANIFEST.json")
VERSION_SERIES_RE = re.compile(r"^(?P<prefix>.+?)[-_]v(?P<ver>\d+)$", re.IGNORECASE)
DATE_SERIES_RE = re.compile(r"^(?P<prefix>.+?)[-_](?P<date>20\d{6})(?:[-_].*)?$")


def _norm_local_ref(raw: str) -> str | None:
    """Normalize a matched reference into canonical ``local/<area>/...`` posix form."""
    cleaned = raw.strip().rstrip(".,;:)'\"`")
    if cleaned.startswith("$AMIDST_ARTIFACTS/"):
        cleaned = "local/evidence/" + cleaned[len("$AMIDST_ARTIFACTS/"):]
    elif cleaned.startswith("${AMIDST_ARTIFACTS}/"):
        cleaned = "local/evidence/" + cleaned[len("${AMIDST_ARTIFACTS}/"):]
    if not cleaned.startswith("local/"):
        return None
    parts = [p for p in PurePosixPath(cleaned).parts if p not in ("", ".")]
    if len(parts) < 2 or parts[0] != "local":
        return None
    # Strip template placeholders like <foo> or {a,b}
    clean_parts: list[str] = []
    for part in parts:
        if any(ch in part for ch in ("<", ">", "{", "}", "*", "…", "$")):
            break
        clean_parts.append(part)
    if len(clean_parts) < 3:
        return None
    return "/".join(clean_parts)


def scan_repo_references(repo: Path) -> dict[str, Any]:
    """Scan merged repo docs, configs, and code for all ``local/...`` references.

    Returns:
      - refs_by_prefix: dict[local_rel_path, list[dict(file, line, is_archive_doc)]]
      - path_map_generations: dict[local_rel_path, str] from configs/local_path_map_v1.json
      - demo_pin_paths: set[str]
      - reproduce_manifest_paths: set[str]
    """
    repo = repo.resolve()
    refs_by_path: dict[str, list[dict[str, Any]]] = {}
    path_map_generations: dict[str, str] = {}
    demo_pin_paths: set[str] = {"local/data/demo-owned-v1"}
    reproduce_manifest_paths: set[str] = set()

    def add_ref(local_path: str, source_file: str, line_no: int | None = None, kind: str = "text_ref") -> None:
        norm = _norm_local_ref(local_path)
        if not norm:
            return
        is_archive_doc = source_file.startswith("docs/archive/") or source_file.startswith("docs/history/")
        entry = {
            "file": source_file,
            "line": line_no,
            "kind": kind,
            "is_archive_doc": is_archive_doc,
        }
        bucket = refs_by_path.setdefault(norm, [])
        if entry not in bucket:
            bucket.append(entry)

    # 1. Structured configs: demo_integration_local.json
    demo_cfg = repo / "configs" / "demo_integration_local.json"
    if demo_cfg.is_file():
        try:
            data = json.loads(demo_cfg.read_text(encoding="utf-8"))
            owned_root = data.get("owned_root")
            if isinstance(owned_root, str) and owned_root.startswith("local/"):
                demo_pin_paths.add(owned_root.rstrip("/"))
                add_ref(owned_root, "configs/demo_integration_local.json", kind="demo_config")
        except (OSError, ValueError):
            pass

    # 2. Structured configs: local_path_map_v1.json
    path_map_file = repo / "configs" / "local_path_map_v1.json"
    if path_map_file.is_file():
        try:
            data = json.loads(path_map_file.read_text(encoding="utf-8"))
            for item in data.get("entries", []):
                new_p = item.get("new")
                gen = item.get("generation")
                if isinstance(new_p, str) and new_p.startswith("local/"):
                    norm = _norm_local_ref(new_p)
                    if norm and isinstance(gen, str):
                        path_map_generations[norm] = gen.upper()
        except (OSError, ValueError):
            pass

    # 3. Structured configs: configs/reproduce/artifact_manifest_v1.json (#728)
    repro_manifest = repo / "configs" / "reproduce" / "artifact_manifest_v1.json"
    if repro_manifest.is_file():
        try:
            data = json.loads(repro_manifest.read_text(encoding="utf-8"))
            for item in data.get("artifacts", []):
                lp = item.get("local_path")
                if isinstance(lp, str):
                    norm = _norm_local_ref(lp)
                    if norm:
                        reproduce_manifest_paths.add(norm)
                        add_ref(norm, "configs/reproduce/artifact_manifest_v1.json", kind="reproduce_manifest")
        except (OSError, ValueError):
            pass

    # 4. Walk repo text files for explicit local/... references
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_REPO_DIRS)
        for fname in sorted(filenames):
            fpath = Path(dirpath) / fname
            if fpath.is_symlink():
                continue
            if fpath.suffix.lower() not in SCAN_TEXT_SUFFIXES:
                continue
            rel = fpath.relative_to(repo).as_posix()
            # Skip local_path_map_v1.json raw text scan because it lists OBSOLETE entries too.
            if rel == "configs/local_path_map_v1.json":
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for idx, line in enumerate(text.splitlines(), 1):
                for match in _LOCAL_REF_RE.finditer(line):
                    add_ref(match.group(0), rel, idx, kind="text_ref")

    return {
        "refs_by_path": refs_by_path,
        "path_map_generations": path_map_generations,
        "demo_pin_paths": sorted(demo_pin_paths),
        "reproduce_manifest_paths": sorted(reproduce_manifest_paths),
    }


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _inspect_entry(entry_path: Path, rel_local_path: str) -> dict[str, Any]:
    """Read-only inspection of one file or directory under local/."""
    is_symlink = entry_path.is_symlink()
    if is_symlink:
        return {
            "local_path": rel_local_path,
            "entry_type": "symlink",
            "size_bytes": 0,
            "file_count": 0,
            "mtime_utc": None,
            "sha256": None,
            "hash_kind": "symlink_not_followed",
            "manifest_file": None,
            "protected_reasons": [],
            "unreadable": False,
        }

    try:
        st = entry_path.stat()
    except OSError:
        return {
            "local_path": rel_local_path,
            "entry_type": "unreadable",
            "size_bytes": 0,
            "file_count": 0,
            "mtime_utc": None,
            "sha256": None,
            "hash_kind": "unreadable",
            "manifest_file": None,
            "protected_reasons": [],
            "unreadable": True,
        }

    mtime_utc = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    protected_reasons: set[str] = set()

    def check_protected(p: Path, rel_posix: str) -> None:
        if p.suffix.lower() in PROTECTED_EXTS:
            protected_reasons.add(f"protected_ext:{p.suffix.lower()}")
        for part in PurePosixPath(rel_posix).parts:
            low = part.lower()
            if low in PROTECTED_NAME_TOKENS:
                protected_reasons.add(f"protected_path_token:{low}")

    if entry_path.is_file():
        check_protected(entry_path, rel_local_path)
        sha = _sha256_file(entry_path)
        return {
            "local_path": rel_local_path,
            "entry_type": "file",
            "size_bytes": st.st_size,
            "file_count": 1,
            "mtime_utc": mtime_utc,
            "sha256": sha,
            "hash_kind": "file_sha256",
            "manifest_file": None,
            "protected_reasons": sorted(protected_reasons),
            "unreadable": False,
        }

    # Directory inspection (strictly read-only, does not follow symlinks)
    check_protected(entry_path, rel_local_path)
    total_bytes = 0
    file_count = 0
    latest_mtime = st.st_mtime
    listing_lines: list[str] = []
    manifest_file: Path | None = None

    for candidate in MANIFEST_FILENAMES:
        cand_path = entry_path / candidate
        if cand_path.is_file() and not cand_path.is_symlink():
            manifest_file = cand_path
            break

    for dirpath, dirnames, filenames in os.walk(entry_path, followlinks=False):
        dirnames.sort()
        filenames.sort()
        d_rel = Path(dirpath).relative_to(entry_path).as_posix()
        if d_rel != ".":
            check_protected(Path(dirpath), f"{rel_local_path}/{d_rel}")
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.is_symlink():
                continue
            f_rel = f"{d_rel}/{fname}" if d_rel != "." else fname
            check_protected(fpath, f"{rel_local_path}/{f_rel}")
            try:
                fst = fpath.stat()
            except OSError:
                continue
            total_bytes += fst.st_size
            file_count += 1
            if fst.st_mtime > latest_mtime:
                latest_mtime = fst.st_mtime
            listing_lines.append(f"{f_rel}\t{fst.st_size}")

    mtime_utc = datetime.fromtimestamp(latest_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if manifest_file is not None:
        sha = _sha256_file(manifest_file)
        hash_kind = "manifest_sha256"
        manifest_rel = f"{rel_local_path}/{manifest_file.name}"
    elif file_count == 0:
        sha = None
        hash_kind = "empty_dir"
        manifest_rel = None
    else:
        sha = hashlib.sha256("\n".join(listing_lines).encode("utf-8")).hexdigest()
        hash_kind = "dir_listing_sha256"
        manifest_rel = None

    return {
        "local_path": rel_local_path,
        "entry_type": "dir",
        "size_bytes": total_bytes,
        "file_count": file_count,
        "mtime_utc": mtime_utc,
        "sha256": sha,
        "hash_kind": hash_kind,
        "manifest_file": manifest_rel,
        "protected_reasons": sorted(protected_reasons),
        "unreadable": False,
    }


def _collect_targets(local_root: Path) -> list[tuple[Path, str]]:
    """Collect asset entries under ``local_root`` at bundle granularity.

    Supports both standard ``local/{data,evidence,archive}/<item>`` layouts and
    top-level files directly under ``local_root`` (e.g. ``demo-pin.json``, ``MANIFEST.sha256``).
    """
    targets: list[tuple[Path, str]] = []
    if not local_root.is_dir():
        return targets

    for child in sorted(local_root.iterdir(), key=lambda p: p.name):
        if child.name in AREAS and child.is_dir() and not child.is_symlink():
            area_children = sorted(child.iterdir(), key=lambda p: p.name)
            if not area_children:
                continue
            for item in area_children:
                targets.append((item, f"local/{child.name}/{item.name}"))
        else:
            targets.append((child, f"local/{child.name}"))
    return targets


def _match_references(local_path: str, refs_by_path: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Match exact, ancestor, or descendant references for ``local_path``."""
    matched: list[dict[str, Any]] = []
    seen: set[tuple[str, int | None, str]] = set()
    prefix = local_path.rstrip("/")
    for ref_path, sources in refs_by_path.items():
        if ref_path == prefix or ref_path.startswith(prefix + "/") or prefix.startswith(ref_path + "/"):
            for src in sources:
                key = (src["file"], src["line"], src["kind"])
                if key not in seen:
                    seen.add(key)
                    matched.append({**src, "matched_ref": ref_path})
    return sorted(matched, key=lambda s: (s["file"], s["line"] or 0, s["matched_ref"]))


def _detect_superseded(items: list[dict[str, Any]]) -> dict[str, str]:
    """Detect older version/date siblings within the same parent area."""
    by_parent: dict[str, list[str]] = {}
    for item in items:
        p = PurePosixPath(item["local_path"])
        by_parent.setdefault(str(p.parent), []).append(p.name)

    superseded: dict[str, str] = {}
    for parent, names in by_parent.items():
        ver_groups: dict[str, list[tuple[int, str]]] = {}
        date_groups: dict[str, list[tuple[str, str]]] = {}
        for name in names:
            vm = VERSION_SERIES_RE.match(name)
            if vm:
                ver_groups.setdefault(vm.group("prefix"), []).append((int(vm.group("ver")), name))
            dm = DATE_SERIES_RE.match(name)
            if dm:
                date_groups.setdefault(dm.group("prefix"), []).append((dm.group("date"), name))

        for group in ver_groups.values():
            if len(group) > 1:
                group.sort()
                newest = group[-1][1]
                for _, name in group[:-1]:
                    superseded[f"{parent}/{name}"] = f"{parent}/{newest}"

        for group in date_groups.values():
            unique_dates = sorted({d for d, _ in group})
            if len(unique_dates) > 1:
                newest_date = unique_dates[-1]
                newest_name = sorted(n for d, n in group if d == newest_date)[-1]
                for d, name in group:
                    if d < newest_date:
                        superseded.setdefault(f"{parent}/{name}", f"{parent}/{newest_name}")
    return superseded


def _is_cache_or_temp(local_path: str) -> bool:
    p = PurePosixPath(local_path)
    low_name = p.name.lower()
    if low_name in CACHE_EXACT_NAMES:
        return True
    if p.suffix.lower() in CACHE_EXTS:
        return True
    return False


def _stale_marker_match(local_path: str) -> str | None:
    low_name = PurePosixPath(local_path).name.lower()
    for token in STALE_OR_BROKEN_TOKENS:
        if token in low_name:
            return token
    return None


def inventory_local_assets(repo: Path, local_root: Path) -> dict[str, Any]:
    """Run full read-only inventory and classification."""
    repo = repo.resolve()
    local_root = local_root.resolve()
    ref_index = scan_repo_references(repo)
    refs_by_path = ref_index["refs_by_path"]
    path_map_generations = ref_index["path_map_generations"]
    demo_pin_paths = set(ref_index["demo_pin_paths"])
    reproduce_manifest_paths = set(ref_index["reproduce_manifest_paths"])

    # Also honor local/demo-pin.json if present inside local_root
    demo_pin_file = local_root / "demo-pin.json"
    if demo_pin_file.is_file() and not demo_pin_file.is_symlink():
        demo_pin_paths.add("local/demo-pin.json")

    raw_targets = _collect_targets(local_root)
    inspected = [_inspect_entry(p, rel) for p, rel in raw_targets]
    superseded_map = _detect_superseded(inspected)

    # First pass: classify everything except duplicate-of-KEEP detection
    results: list[dict[str, Any]] = []
    for item in inspected:
        lp = item["local_path"]
        refs = _match_references(lp, refs_by_path)
        active_refs = [r for r in refs if not r["is_archive_doc"]]
        archive_refs = [r for r in refs if r["is_archive_doc"]]
        path_map_gen = path_map_generations.get(lp)
        in_repro = any(lp == rp or rp.startswith(lp + "/") or lp.startswith(rp + "/") for rp in reproduce_manifest_paths)
        in_demo = any(lp == dp or dp.startswith(lp + "/") or lp.startswith(dp + "/") for dp in demo_pin_paths)
        is_archive_area = lp.startswith("local/archive/")

        classification: str
        is_obviously_stale_or_broken = False
        stale_reason: str | None = None
        reasons: list[str] = []

        if item["entry_type"] in ("symlink", "unreadable"):
            classification = "UNCERTAIN"
            reasons.append("symlink_or_unreadable: requires human verification")
        elif item["protected_reasons"]:
            classification = "KEEP"
            reasons.append("protected_original_asset (list only, never delete): " + ", ".join(item["protected_reasons"]))
            if in_repro:
                reasons.append("required_by_reproduce_manifest")
            if active_refs:
                reasons.append(f"referenced_in_repo ({len(active_refs)} active ref(s))")
        elif in_repro:
            classification = "KEEP"
            reasons.append("required_by_reproduce_manifest (#728)")
        elif in_demo:
            classification = "KEEP"
            reasons.append("required_by_8785_demo_pin")
        elif active_refs:
            classification = "KEEP"
            reasons.append(f"referenced_in_active_repo_sources ({len(active_refs)} ref(s))")
        else:
            # No active references and not a protected original asset
            if item["entry_type"] == "dir" and item["file_count"] == 0:
                classification = "DELETABLE_CANDIDATE"
                is_obviously_stale_or_broken = True
                stale_reason = "empty_or_zero_byte"
                reasons.append("empty directory with zero active references")
            elif item["entry_type"] == "file" and item["size_bytes"] == 0:
                classification = "DELETABLE_CANDIDATE"
                is_obviously_stale_or_broken = True
                stale_reason = "empty_or_zero_byte"
                reasons.append("0-byte file with zero active references")
            elif _is_cache_or_temp(lp):
                classification = "DELETABLE_CANDIDATE"
                is_obviously_stale_or_broken = True
                stale_reason = "rebuildable_cache_or_temp"
                reasons.append("rebuildable cache or OS/temp artifact with zero active references")
            elif _stale_marker_match(lp):
                tok = _stale_marker_match(lp)
                classification = "DELETABLE_CANDIDATE"
                is_obviously_stale_or_broken = True
                stale_reason = f"failed_aborted_or_stale_marker:{tok}"
                reasons.append(f"name matches stale/broken marker '{tok}' with zero active references")
            elif path_map_gen == "OBSOLETE":
                classification = "DELETABLE_CANDIDATE"
                is_obviously_stale_or_broken = True
                stale_reason = "local_path_map_obsolete"
                reasons.append("marked OBSOLETE in configs/local_path_map_v1.json with zero active references")
            elif lp in superseded_map:
                newer = superseded_map[lp]
                classification = "DELETABLE_CANDIDATE"
                is_obviously_stale_or_broken = True
                stale_reason = f"superseded_by_newer_version:{newer}"
                reasons.append(f"superseded by newer version '{newer}' with zero active references")
            elif archive_refs:
                classification = "UNCERTAIN"
                reasons.append(f"referenced_only_in_archive_docs ({len(archive_refs)} archive ref(s)); needs human review")
            elif path_map_gen in ("CITED", "CURRENT"):
                classification = "UNCERTAIN"
                reasons.append(f"path_map_generation={path_map_gen} without direct active local/ ref; needs human review")
            elif is_archive_area:
                classification = "UNCERTAIN"
                reasons.append("unreferenced item under local/archive/; confirm historical value before deleting")
            else:
                classification = "DELETABLE_CANDIDATE"
                reasons.append("unreferenced asset outside protected/reproduce/demo lists")

        results.append(
            {
                **item,
                "reference_sources": refs,
                "active_reference_count": len(active_refs),
                "archive_reference_count": len(archive_refs),
                "path_map_generation": path_map_gen,
                "classification": classification,
                "is_obviously_stale_or_broken": is_obviously_stale_or_broken,
                "obviously_stale_or_broken_reason": stale_reason,
                "rationale": "; ".join(reasons),
            }
        )

    # Second pass: flag unreferenced duplicates of KEEP items (by sha256)
    keep_hashes: dict[str, str] = {}
    for r in results:
        if r["classification"] == "KEEP" and r["sha256"]:
            keep_hashes.setdefault(r["sha256"], r["local_path"])

    for r in results:
        if r["classification"] != "KEEP" and r["sha256"] and r["sha256"] in keep_hashes:
            kept_origin = keep_hashes[r["sha256"]]
            if not r["protected_reasons"] and r["entry_type"] not in ("symlink", "unreadable"):
                r["classification"] = "DELETABLE_CANDIDATE"
                r["rationale"] = f"duplicate_of:{kept_origin} (matching {r['hash_kind']}); " + r["rationale"]

    summary: dict[str, dict[str, int]] = {}
    for cls in ("KEEP", "DELETABLE_CANDIDATE", "UNCERTAIN"):
        subset = [r for r in results if r["classification"] == cls]
        summary[cls] = {
            "item_count": len(subset),
            "file_count": sum(r["file_count"] for r in subset),
            "size_bytes": sum(r["size_bytes"] for r in subset),
        }
    obvious_subset = [r for r in results if r["is_obviously_stale_or_broken"]]
    summary["OBVIOUSLY_STALE_OR_BROKEN"] = {
        "item_count": len(obvious_subset),
        "file_count": sum(r["file_count"] for r in obvious_subset),
        "size_bytes": sum(r["size_bytes"] for r in obvious_subset),
    }

    return {
        "tool": "scripts/inventory_local_assets.py",
        "read_only": True,
        "generated_at_utc": datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "repo_root": str(repo),
        "local_root": str(local_root),
        "total_items": len(results),
        "total_files": sum(r["file_count"] for r in results),
        "total_bytes": sum(r["size_bytes"] for r in results),
        "summary": summary,
        "items": results,
    }


def _fmt_bytes(num: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    val = float(num)
    for unit in units:
        if val < 1024.0 or unit == units[-1]:
            return f"{val:.1f} {unit}" if unit != "B" else f"{int(val)} B"
        val /= 1024.0
    return f"{num} B"


def _fmt_refs(refs: list[dict[str, Any]], limit: int = 3) -> str:
    if not refs:
        return "無引用（0）"
    shown = []
    for r in refs[:limit]:
        loc = f"{r['file']}:{r['line']}" if r.get("line") else r["file"]
        shown.append(f"`{loc}`")
    extra = f" 等共 {len(refs)} 處" if len(refs) > limit else ""
    return ", ".join(shown) + extra


def render_markdown(report: dict[str, Any]) -> str:
    """Render human-readable Markdown report with dedicated D387 section."""
    s = report["summary"]
    lines: list[str] = [
        "# `local/` 資產盤點與分類報告（唯讀）",
        "",
        f"- 產生時間（UTC）：`{report['generated_at_utc']}`",
        f"- 掃描模式：**STRICTLY READ-ONLY（未刪除、未移動、未修改任何檔案）**",
        f"- 總計：{report['total_items']} 項、{report['total_files']} 檔、{_fmt_bytes(report['total_bytes'])}（{report['total_bytes']} bytes）",
        "",
        "## 彙總",
        "",
        "| 分類 | 項目數 | 檔數 | 大小 |",
        "| --- | ---: | ---: | ---: |",
        f"| 保留（`KEEP`） | {s['KEEP']['item_count']} | {s['KEEP']['file_count']} | {_fmt_bytes(s['KEEP']['size_bytes'])} |",
        f"| 可刪候選（`DELETABLE_CANDIDATE`） | {s['DELETABLE_CANDIDATE']['item_count']} | {s['DELETABLE_CANDIDATE']['file_count']} | {_fmt_bytes(s['DELETABLE_CANDIDATE']['size_bytes'])} |",
        f"| └ 其中：明顯過期或錯誤（D387 專節） | {s['OBVIOUSLY_STALE_OR_BROKEN']['item_count']} | {s['OBVIOUSLY_STALE_OR_BROKEN']['file_count']} | {_fmt_bytes(s['OBVIOUSLY_STALE_OR_BROKEN']['size_bytes'])} |",
        f"| 不確定（`UNCERTAIN`） | {s['UNCERTAIN']['item_count']} | {s['UNCERTAIN']['file_count']} | {_fmt_bytes(s['UNCERTAIN']['size_bytes'])} |",
        "",
    ]

    # Dedicated D387 section: Obviously Stale or Broken
    obvious = [i for i in report["items"] if i["is_obviously_stale_or_broken"]]
    lines += [
        "## 明顯過期或錯誤（Obviously Stale or Broken — D387）",
        "",
        "> 本節依 D387 獨立列出明顯過期、損毀或可重建快取項目，附每項理由與引用反查結果。**本工具絕不自動刪除**；下列指令皆已註解，須由使用者核准後於自己的終端機手動執行。",
        "",
    ]
    if obvious:
        lines += [
            "| 路徑 | 大小 | 檔數 | 修改時間 (UTC) | 引用反查結果 | 理由 | SHA-256 / MANIFEST |",
            "| --- | ---: | ---: | --- | --- | --- | --- |",
        ]
        for i in obvious:
            sha_disp = f"`{i['sha256'][:12]}…` ({i['hash_kind']})" if i["sha256"] else f"`NONE` ({i['hash_kind']})"
            lines.append(
                f"| `{i['local_path']}` | {_fmt_bytes(i['size_bytes'])} | {i['file_count']} | `{i['mtime_utc']}` | "
                f"{_fmt_refs(i['reference_sources'])} | {i['rationale']} | {sha_disp} |"
            )
        lines += [
            "",
            "### 建議刪除檢核清單（僅供使用者於自己終端機核對後手動取消註解執行）",
            "",
            "```bash",
            "# Review-only checklist generated by scripts/inventory_local_assets.py (NOT auto-executed).",
            "# Remove the leading '# ' ONLY after explicit human approval.",
        ]
        for i in obvious:
            flag = "-rf" if i["entry_type"] == "dir" else "-f"
            lines.append(f"# rm {flag} -- \"{i['local_path']}\"  # {_fmt_bytes(i['size_bytes'])}; {i['obviously_stale_or_broken_reason']}")
        lines += ["```", ""]
    else:
        lines += ["（本次掃描未發現明顯過期或錯誤項目。）", ""]

    def render_section(title: str, cls: str) -> None:
        subset = [i for i in report["items"] if i["classification"] == cls]
        lines.extend([f"## {title}", ""])
        if not subset:
            lines.extend(["（無項目）", ""])
            return
        lines.extend([
            "| 路徑 | 大小 | 檔數 | 修改時間 (UTC) | 引用反查結果 | 理由 | SHA-256 / MANIFEST |",
            "| --- | ---: | ---: | --- | --- | --- | --- |",
        ])
        for i in subset:
            sha_disp = f"`{i['sha256'][:12]}…` ({i['hash_kind']})" if i["sha256"] else f"`NONE` ({i['hash_kind']})"
            lines.append(
                f"| `{i['local_path']}` | {_fmt_bytes(i['size_bytes'])} | {i['file_count']} | `{i['mtime_utc']}` | "
                f"{_fmt_refs(i['reference_sources'])} | {i['rationale']} | {sha_disp} |"
            )
        lines.append("")

    render_section("保留（KEEP）", "KEEP")
    render_section("可刪候選（DELETABLE_CANDIDATE）", "DELETABLE_CANDIDATE")
    render_section("不確定（UNCERTAIN）", "UNCERTAIN")

    protected = [i for i in report["items"] if i["protected_reasons"]]
    lines.extend([
        "## 受保護原始資產（只列不刪 / Protected Original Assets）",
        "",
        f"共偵測到 {len(protected)} 項含受保護原始資產（`.blend`、原始影片、GT、校正資料），均已強制保留為 `KEEP`，未列入任何可刪清單。",
        "",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Strictly read-only inventory & classification of local/ assets (#729).")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1], help="Repository root for reference scanning")
    parser.add_argument("--local-root", type=Path, required=True, help="Path to local/ (or compatible datapack root) to scan read-only")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional output path for JSON report")
    parser.add_argument("--md-out", type=Path, default=None, help="Optional output path for Markdown report")
    args = parser.parse_args(argv)

    if not args.local_root.is_dir():
        print(f"ERROR: local root does not exist or is not a directory: {args.local_root}", file=sys.stderr)
        return 2

    report = inventory_local_assets(args.repo, args.local_root)
    md_text = render_markdown(report)

    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.md_out is not None:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(md_text, encoding="utf-8")

    s = report["summary"]
    print(
        f"Inventory complete (READ-ONLY): total={report['total_items']} items "
        f"({report['total_files']} files, {_fmt_bytes(report['total_bytes'])}); "
        f"KEEP={s['KEEP']['item_count']}, "
        f"DELETABLE_CANDIDATE={s['DELETABLE_CANDIDATE']['item_count']} "
        f"(OBVIOUSLY_STALE_OR_BROKEN={s['OBVIOUSLY_STALE_OR_BROKEN']['item_count']}), "
        f"UNCERTAIN={s['UNCERTAIN']['item_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
