#!/usr/bin/env python3
"""Cross-platform check and fallback resolver for Git-tracked symlinks (#728).

On Unix (macOS/Linux), Git checks out mode-120000 entries as OS symlinks.
On platforms or filesystems without symlink support (e.g. Windows with
``core.symlinks=false``), Git checks them out as single-line plain-text files
containing the relative POSIX target path.

This read-only helper:
1. Lists all Git-tracked symlinks (mode ``120000``) via ``git ls-files -s``.
2. Verifies each symlink target exists (whether real symlink or text-pointer fallback).
3. Exposes ``resolve_tracked_symlink(repo, rel_path)`` for scripts that need to
   read tracked symlinked docs cross-platform without modifying the working tree.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys
from typing import Any


def list_git_symlinks(repo: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-s"],
        capture_output=True,
        text=True,
        check=True,
    )
    symlinks: list[str] = []
    for line in proc.stdout.splitlines():
        if line.startswith("120000 "):
            _, path_part = line.split("\t", 1)
            symlinks.append(path_part.strip())
    return sorted(symlinks)


def resolve_tracked_symlink(repo: Path, rel_posix: str) -> tuple[Path | None, str, str | None]:
    """Resolve a tracked symlink path on Unix or Windows text-pointer checkouts.

    Returns ``(resolved_target_path, mode, raw_target_text)`` where mode is one of:
      - ``SYMLINK_OK``
      - ``TEXT_POINTER_FALLBACK_OK``
      - ``BROKEN_SYMLINK``
      - ``MISSING``
    """
    entry = repo / Path(*PurePosixPath(rel_posix).parts)
    if entry.is_symlink():
        raw_target = str(entry.readlink())
        resolved = (entry.parent / Path(*PurePosixPath(raw_target).parts)).resolve()
        if resolved.is_file():
            return resolved, "SYMLINK_OK", raw_target
        return None, "BROKEN_SYMLINK", raw_target

    if not entry.is_file():
        return None, "MISSING", None

    # Plain-text pointer fallback (Git checkout when core.symlinks=false)
    raw_text = entry.read_text(encoding="utf-8", errors="replace").strip()
    if raw_text and "\n" not in raw_text and "\r" not in raw_text:
        candidate = (entry.parent / Path(*PurePosixPath(raw_text).parts)).resolve()
        if candidate.is_file():
            return candidate, "TEXT_POINTER_FALLBACK_OK", raw_text
    return None, "BROKEN_SYMLINK", raw_text


def check_repo_symlinks(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    tracked = list_git_symlinks(repo)
    items: list[dict[str, Any]] = []
    ok = True
    for rel in tracked:
        target_path, mode, raw_target = resolve_tracked_symlink(repo, rel)
        if mode not in ("SYMLINK_OK", "TEXT_POINTER_FALLBACK_OK"):
            ok = False
        items.append(
            {
                "path": rel,
                "mode": mode,
                "raw_target": raw_target,
                "resolved_target": target_path.relative_to(repo).as_posix()
                if target_path and target_path.is_relative_to(repo)
                else (str(target_path) if target_path else None),
            }
        )
    return {
        "status": "PASS" if ok else "FAIL",
        "tracked_symlink_count": len(tracked),
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Git-tracked symlinks and cross-platform fallback (#728).")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    result = check_repo_symlinks(args.repo)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Symlink check: {result['status']} ({result['tracked_symlink_count']} tracked symlink(s))")
        for item in result["items"]:
            print(f"  [{item['mode']}] {item['path']} -> {item['resolved_target']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
