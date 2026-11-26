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
import subprocess
import sys
from typing import Any

# Match ANY local/<relpath> (including local/runtime/..., local/manifests/..., local/logs/...,
# local/.migration-d169, local/data/..., local/evidence/..., local/archive/..., ./local/...,
# ~/amidst/local/..., and $AMIDST_ARTIFACTS/...) while avoiding system paths like /usr/local/bin.
_LOCAL_REF_RE = re.compile(
    r"(?:(?<![\w/.-])|(?<=~/amidst/)|(?<=\./))"
    r"(?:local/[A-Za-z0-9._-]+(?:/[^\s`\"'|)\]>,;]*)?|\$\{?AMIDST_ARTIFACTS\}?/[^\s`\"'|)\]>,;]+)"
)

AREAS = ("data", "evidence", "archive")
SKIP_REPO_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", "local", ".local"}
SCAN_TEXT_SUFFIXES = {
    ".md", ".json", ".yaml", ".yml", ".toml", ".py", ".mjs", ".js", ".ts", ".tsx", ".jsx",
    ".sh", ".ps1", ".command", ".txt", ".cfg", ".ini", ".bat", ".cmd", ".html", ".css",
}

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
    """Normalize a matched reference into canonical ``local/...`` posix form."""
    cleaned = raw.strip().rstrip(".,;:)'\"`/")
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
    if len(clean_parts) < 2:
        return None
    # Bare area roots (local/data, local/evidence, local/archive) are too broad to
    # keep every child inside those areas; require at least local/<area>/<item>.
    if clean_parts[1] in AREAS and len(clean_parts) < 3:
        return None
    return "/".join(clean_parts)


def _ancestor_prefixes(norm: str) -> list[str]:
    """Return ``norm`` and every valid non-area ancestor under ``local/``.

    Ensures a reference to ``local/X/child`` propagates to ``local/X`` (e.g.
    ``local/runtime/live-main`` -> ``["local/runtime/live-main", "local/runtime"]``),
    while not collapsing ``local/evidence/run1`` into bare ``local/evidence``.
    """
    parts = PurePosixPath(norm).parts
    if len(parts) < 2 or parts[0] != "local":
        return []
    min_len = 3 if parts[1] in AREAS else 2
    return ["/".join(parts[:i]) for i in range(len(parts), min_len - 1, -1)]


def _scan_text_for_refs(
    text: str,
    source_file: str,
    add_ref_fn: Any,
    *,
    kind: str = "text_ref",
    is_archive_doc: bool | None = None,
) -> None:
    for idx, line in enumerate(text.splitlines(), 1):
        for match in _LOCAL_REF_RE.finditer(line):
            add_ref_fn(match.group(0), source_file, idx, kind=kind, is_archive_doc=is_archive_doc)


def _scan_github_refs_json(
    json_path: Path,
    add_ref_fn: Any,
) -> tuple[bool, bool, list[str]]:
    """Load pre-fetched or test-injected GitHub issue/PR & open-branch references."""
    warnings: list[str] = []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return False, False, [f"Failed to read --github-refs-json ({json_path}): {exc}"]

    issues_scanned = False
    branches_scanned = False

    def ingest_items(items: Any, default_prefix: str, kind: str) -> None:
        if not isinstance(items, list):
            return
        for idx, item in enumerate(items, 1):
            if isinstance(item, str):
                _scan_text_for_refs(item, f"{default_prefix}#{idx}", add_ref_fn, kind=kind, is_archive_doc=False)
                continue
            if not isinstance(item, dict):
                continue
            src = str(item.get("source") or item.get("branch") or f"{default_prefix}#{item.get('number', idx)}")
            for raw_p in item.get("paths") or []:
                if isinstance(raw_p, str):
                    add_ref_fn(raw_p, src, None, kind=kind, is_archive_doc=False)
            text = item.get("text") or item.get("body") or ""
            if isinstance(text, str) and text:
                _scan_text_for_refs(text, src, add_ref_fn, kind=kind, is_archive_doc=False)

    if isinstance(data, list):
        issues_scanned = True
        ingest_items(data, "github:issue", "github_issue_pr")
    elif isinstance(data, dict):
        for key in ("issues_and_prs", "issues", "prs", "references"):
            if key in data:
                issues_scanned = True
                ingest_items(data[key], f"github:{key}", "github_issue_pr")
        if "open_pr_branches" in data:
            branches_scanned = True
            ingest_items(data["open_pr_branches"], "github:pr-branch", "open_pr_branch")
        if not issues_scanned and not branches_scanned:
            warnings.append(f"--github-refs-json ({json_path}) contained no recognized keys.")

    return issues_scanned, branches_scanned, warnings


def _scan_git_branches(repo: Path, add_ref_fn: Any) -> tuple[bool, list[str]]:
    """Scan local and remote git branches for ``local/...`` references (read-only)."""
    warnings: list[str] = []
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), "for-each-ref", "--format=%(refname:short)", "refs/heads", "refs/remotes/origin"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, [f"git branch scan failed: {exc}"]
    if proc.returncode != 0:
        return False, [f"git for-each-ref failed: {proc.stderr.strip()}"]

    branches = [
        b.strip()
        for b in proc.stdout.splitlines()
        if b.strip() and b.strip() not in ("HEAD", "origin/HEAD")
    ]
    for branch in branches:
        try:
            gproc = subprocess.run(
                ["git", "-C", str(repo), "grep", "-I", "-n", "-E", r"local/|AMIDST_ARTIFACTS", branch],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            warnings.append(f"git grep on branch {branch} failed: {exc}")
            continue
        if gproc.returncode not in (0, 1):
            continue
        prefix = f"{branch}:"
        for line in gproc.stdout.splitlines():
            if not line.startswith(prefix):
                continue
            rest = line[len(prefix):]
            parts = rest.split(":", 2)
            if len(parts) < 3:
                continue
            rel_file, line_str, content = parts
            if rel_file == "configs/local_path_map_v1.json":
                continue
            try:
                lno = int(line_str)
            except ValueError:
                lno = None
            is_arch = rel_file.startswith("docs/archive/") or rel_file.startswith("docs/history/")
            for match in _LOCAL_REF_RE.finditer(content):
                add_ref_fn(
                    match.group(0),
                    f"git-branch:{branch}:{rel_file}",
                    lno,
                    kind="open_pr_branch",
                    is_archive_doc=is_arch,
                )
    return True, warnings


def _parse_paginated_json_array(raw: str) -> list[dict[str, Any]]:
    """Parse JSON array output from ``gh api --paginate`` (supports concatenated or slurped pages)."""
    text = raw.strip()
    if not text:
        return []
    decoder = json.JSONDecoder()
    idx = 0
    length = len(text)
    items: list[dict[str, Any]] = []
    while idx < length:
        while idx < length and text[idx].isspace():
            idx += 1
        if idx >= length:
            break
        obj, end = decoder.raw_decode(text, idx)
        idx = end
        if isinstance(obj, list):
            for elem in obj:
                if isinstance(elem, list):
                    for sub in elem:
                        if isinstance(sub, dict):
                            items.append(sub)
                elif isinstance(elem, dict):
                    items.append(elem)
        else:
            raise ValueError(f"Expected JSON array from gh api --paginate, got {type(obj).__name__}")
    return items


def _collect_github_refs_via_gh(
    repo: Path,
    add_ref_fn: Any,
    *,
    github_limit: int | None = None,
    runner: Any = None,
) -> tuple[bool, bool, bool, list[str]]:
    """Query ALL GitHub issues/PRs, their comments, and open PR diffs via paginated ``gh api``.

    Returns ``(issues_ok, branches_ok, truncated, warnings)``.
    If any ``gh`` call fails, times out, returns invalid JSON, or hits ``github_limit``,
    ``truncated`` is set to ``True``, the affected ``*_ok`` flag is set to ``False``, and a
    clear warning is emitted.
    """
    warnings: list[str] = []
    truncated = False
    run_fn = runner or subprocess.run

    def _run_gh(cmd: list[str], *, timeout: int = 300) -> tuple[bool, str, str]:
        try:
            proc = run_fn(
                cmd,
                cwd=str(repo),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout,
            )
        except FileNotFoundError:
            return False, "", "gh CLI not found in PATH"
        except subprocess.TimeoutExpired as exc:
            return False, "", f"gh CLI timed out after {exc.timeout}s"
        except subprocess.SubprocessError as exc:
            return False, "", f"gh CLI failed: {exc}"
        if proc.returncode != 0:
            return False, proc.stdout, (proc.stderr or "").strip() or f"gh exited {proc.returncode}"
        return True, proc.stdout, ""

    # 1. All issues AND PRs (GitHub REST /issues?state=all returns both issues and pull requests)
    ok_i, out_i, err_i = _run_gh(
        ["gh", "api", "--paginate", "repos/{owner}/{repo}/issues?state=all&per_page=100"]
    )
    if ok_i:
        try:
            issues_items = _parse_paginated_json_array(out_i)
            if github_limit is not None and github_limit > 0 and len(issues_items) >= github_limit:
                warnings.append(
                    f"GitHub issues/PRs scan truncated at --github-limit={github_limit} "
                    f"(fetched {len(issues_items)} items); re-run without --github-limit for a complete scan"
                )
                truncated = True
                ok_i = False
                issues_items = issues_items[:github_limit]
            for item in issues_items:
                num = item.get("number")
                is_pr = "pull_request" in item
                src = f"github:pr#{num}" if is_pr else f"github:issue#{num}"
                _scan_text_for_refs(
                    f"{item.get('title') or ''}\n{item.get('body') or ''}",
                    src,
                    add_ref_fn,
                    kind="github_issue_pr",
                    is_archive_doc=False,
                )
        except ValueError as exc:
            warnings.append(f"Failed to parse paginated GitHub issues/PRs JSON: {exc}")
            truncated = True
            ok_i = False
    else:
        warnings.append(f"GitHub issues/PRs scan failed/incomplete ({err_i})")
        truncated = True

    # 2. All issue and PR conversation comments (paginated across the entire repo)
    ok_c, out_c, err_c = _run_gh(
        ["gh", "api", "--paginate", "repos/{owner}/{repo}/issues/comments?per_page=100"]
    )
    if ok_c:
        try:
            comment_items = _parse_paginated_json_array(out_c)
            if github_limit is not None and github_limit > 0 and len(comment_items) >= github_limit:
                warnings.append(
                    f"GitHub issue/PR comments scan truncated at --github-limit={github_limit} "
                    f"(fetched {len(comment_items)} comments); re-run without --github-limit for a complete scan"
                )
                truncated = True
                ok_c = False
                comment_items = comment_items[:github_limit]
            for comment in comment_items:
                cid = comment.get("id")
                issue_url = str(comment.get("issue_url") or "")
                issue_num = issue_url.rstrip("/").split("/")[-1] if issue_url else ""
                src = f"github:issue#{issue_num}:comment#{cid}" if issue_num else f"github:comment#{cid}"
                _scan_text_for_refs(
                    str(comment.get("body") or ""),
                    src,
                    add_ref_fn,
                    kind="github_issue_pr",
                    is_archive_doc=False,
                )
        except ValueError as exc:
            warnings.append(f"Failed to parse paginated GitHub comments JSON: {exc}")
            truncated = True
            ok_c = False
    else:
        warnings.append(f"GitHub issue/PR comments scan failed/incomplete ({err_c})")
        truncated = True

    issues_ok = ok_i and ok_c

    # 3. Open PRs (paginated) + open PR diffs
    branches_ok = False
    ok_p, out_p, err_p = _run_gh(
        ["gh", "api", "--paginate", "repos/{owner}/{repo}/pulls?state=open&per_page=100"]
    )
    if ok_p:
        try:
            open_prs = _parse_paginated_json_array(out_p)
            if github_limit is not None and github_limit > 0 and len(open_prs) >= github_limit:
                warnings.append(
                    f"GitHub open PRs scan truncated at --github-limit={github_limit} "
                    f"(fetched {len(open_prs)} PRs); re-run without --github-limit for a complete scan"
                )
                truncated = True
                ok_p = False
                open_prs = open_prs[:github_limit]
            branches_ok = ok_p
            for pr in open_prs:
                num = pr.get("number")
                head_info = pr.get("head")
                head_ref = (head_info.get("ref") if isinstance(head_info, dict) else None) or pr.get("headRefName") or ""
                ok_d, out_d, err_d = _run_gh(["gh", "pr", "diff", str(num)], timeout=120)
                if ok_d:
                    _scan_text_for_refs(
                        out_d,
                        f"github:pr#{num}:branch:{head_ref}",
                        add_ref_fn,
                        kind="open_pr_branch",
                        is_archive_doc=False,
                    )
                else:
                    warnings.append(f"Open PR #{num} ({head_ref}) diff scan failed: {err_d}")
                    branches_ok = False
                    truncated = True
        except ValueError as exc:
            warnings.append(f"Failed to parse paginated GitHub open PRs JSON: {exc}")
            branches_ok = False
            truncated = True
    else:
        warnings.append(f"GitHub open PRs scan failed/incomplete ({err_p})")
        truncated = True

    return issues_ok, branches_ok, truncated, warnings


def scan_repo_references(
    repo: Path,
    *,
    include_github: bool = False,
    github_refs_json: Path | None = None,
    include_git_branches: bool = False,
    github_limit: int | None = None,
    gh_runner: Any = None,
) -> dict[str, Any]:
    """Scan merged repo docs, configs, code, and optional GitHub/branch sources for ``local/...`` references.

    Returns:
      - refs_by_path: dict[local_rel_path, list[dict(file, line, kind, is_archive_doc, original_ref)]]
      - path_map_generations: dict[local_rel_path, str] from configs/local_path_map_v1.json
      - path_map_paths: list[str] of all local/... paths listed in configs/local_path_map_v1.json
      - demo_pin_paths: set[str]
      - reproduce_manifest_paths: set[str]
      - external_ref_scan: dict(github_issues_prs_scanned, open_pr_branches_scanned, truncated, warning)
    """
    repo = repo.resolve()
    refs_by_path: dict[str, list[dict[str, Any]]] = {}
    path_map_generations: dict[str, str] = {}
    path_map_paths: set[str] = set()
    demo_pin_paths: set[str] = {"local/data/demo-owned-v1"}
    reproduce_manifest_paths: set[str] = set()

    def add_ref(
        local_path: str,
        source_file: str,
        line_no: int | None = None,
        kind: str = "text_ref",
        is_archive_doc: bool | None = None,
    ) -> None:
        norm = _norm_local_ref(local_path)
        if not norm:
            return
        arch = (
            is_archive_doc
            if is_archive_doc is not None
            else (source_file.startswith("docs/archive/") or source_file.startswith("docs/history/"))
        )
        entry = {
            "file": source_file,
            "line": line_no,
            "kind": kind,
            "is_archive_doc": arch,
            "original_ref": norm,
        }
        # Propagate to norm AND every valid non-area ancestor (e.g. local/runtime/live-main -> local/runtime)
        for prefix_path in _ancestor_prefixes(norm):
            bucket = refs_by_path.setdefault(prefix_path, [])
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
                    if norm:
                        path_map_paths.add(norm)
                        if isinstance(gen, str):
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

    # 4. Walk ALL repo text files (docs/, docs/agents/, configs/, scripts/, src/, frontend/, tests/, root)
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
            _scan_text_for_refs(text, rel, add_ref, kind="text_ref")

    # 5. Optional external reference scans: GitHub issues/PRs and open/git branches
    github_issues_prs_scanned = False
    open_pr_branches_scanned = False
    truncated = False
    ext_warnings: list[str] = []

    if github_refs_json is not None:
        gh_i, gh_b, warns = _scan_github_refs_json(github_refs_json, add_ref)
        github_issues_prs_scanned = github_issues_prs_scanned or gh_i
        open_pr_branches_scanned = open_pr_branches_scanned or gh_b
        ext_warnings.extend(warns)

    if include_github:
        gh_i, gh_b, gh_trunc, warns = _collect_github_refs_via_gh(
            repo,
            add_ref,
            github_limit=github_limit,
            runner=gh_runner,
        )
        github_issues_prs_scanned = github_issues_prs_scanned or gh_i
        open_pr_branches_scanned = open_pr_branches_scanned or gh_b
        truncated = truncated or gh_trunc
        ext_warnings.extend(warns)

    if include_git_branches:
        gb_ok, warns = _scan_git_branches(repo, add_ref)
        open_pr_branches_scanned = open_pr_branches_scanned or gb_ok
        ext_warnings.extend(warns)

    missing_scopes: list[str] = []
    if not github_issues_prs_scanned:
        missing_scopes.append("GitHub issues/PRs")
    if not open_pr_branches_scanned:
        missing_scopes.append("open PR branches")
    if missing_scopes:
        ext_warnings.append(
            f"{' and '.join(missing_scopes)} were NOT scanned (or were truncated); human review or re-running with "
            "--include-github --include-git-branches (or --github-refs-json) without truncation is required before deleting any candidate."
        )

    external_ref_scan = {
        "github_issues_prs_scanned": github_issues_prs_scanned,
        "open_pr_branches_scanned": open_pr_branches_scanned,
        "truncated": truncated,
        "warning": "; ".join(ext_warnings),
    }

    return {
        "refs_by_path": refs_by_path,
        "path_map_generations": path_map_generations,
        "path_map_paths": sorted(path_map_paths),
        "demo_pin_paths": sorted(demo_pin_paths),
        "reproduce_manifest_paths": sorted(reproduce_manifest_paths),
        "external_ref_scan": external_ref_scan,
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


def inventory_local_assets(
    repo: Path,
    local_root: Path,
    *,
    include_github: bool = False,
    github_refs_json: Path | None = None,
    include_git_branches: bool = False,
    github_limit: int | None = None,
    gh_runner: Any = None,
) -> dict[str, Any]:
    """Run full read-only inventory and classification."""
    repo = repo.resolve()
    local_root = local_root.resolve()
    ref_index = scan_repo_references(
        repo,
        include_github=include_github,
        github_refs_json=github_refs_json,
        include_git_branches=include_git_branches,
        github_limit=github_limit,
        gh_runner=gh_runner,
    )
    refs_by_path = ref_index["refs_by_path"]
    path_map_generations = ref_index["path_map_generations"]
    path_map_paths = set(ref_index["path_map_paths"])
    demo_pin_paths = set(ref_index["demo_pin_paths"])
    reproduce_manifest_paths = set(ref_index["reproduce_manifest_paths"])
    external_ref_scan = ref_index["external_ref_scan"]

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
        in_path_map = any(lp == pm or pm.startswith(lp + "/") or lp.startswith(pm + "/") for pm in path_map_paths)
        in_repro = any(lp == rp or rp.startswith(lp + "/") or lp.startswith(rp + "/") for rp in reproduce_manifest_paths)
        in_demo = any(lp == dp or dp.startswith(lp + "/") or lp.startswith(dp + "/") for dp in demo_pin_paths)
        path_map_only_reference = bool(in_path_map and not refs and not in_repro and not in_demo)
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
                "path_map_only_reference": path_map_only_reference,
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
        "external_ref_scan": external_ref_scan,
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


def _fmt_refs(
    refs: list[dict[str, Any]],
    limit: int = 3,
    *,
    path_map_only: bool = False,
    path_map_gen: str | None = None,
) -> str:
    if not refs:
        if path_map_only:
            gen_tag = f"（generation=`{path_map_gen}`）" if path_map_gen else ""
            return f"`[path_map_only]` 僅列於 `configs/local_path_map_v1.json`{gen_tag}"
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
    ext = report.get("external_ref_scan") or {
        "github_issues_prs_scanned": False,
        "open_pr_branches_scanned": False,
        "truncated": False,
        "warning": "GitHub issues/PRs and open PR branches were NOT scanned; human review is required before deleting any candidate.",
    }
    ext_incomplete = (
        (not ext.get("github_issues_prs_scanned"))
        or (not ext.get("open_pr_branches_scanned"))
        or bool(ext.get("truncated"))
    )
    lines: list[str] = [
        "# `local/` 資產盤點與分類報告（唯讀）",
        "",
        f"- 產生時間（UTC）：`{report['generated_at_utc']}`",
        "- 掃描模式：**STRICTLY READ-ONLY（未刪除、未移動、未修改任何檔案）**",
        f"- 外部引用反查：`github_issues_prs_scanned={ext.get('github_issues_prs_scanned')}`、`open_pr_branches_scanned={ext.get('open_pr_branches_scanned')}`、`truncated={bool(ext.get('truncated'))}`",
        f"- 總計：{report['total_items']} 項、{report['total_files']} 檔、{_fmt_bytes(report['total_bytes'])}（{report['total_bytes']} bytes）",
        "",
    ]
    if ext_incomplete:
        lines += [
            f"> **⚠️ 外部引用掃描未完整警示**：{ext.get('warning') or 'GitHub issue/PR 或 open PR 分支未完整掃描（或已截斷），刪除任何候選項目之前必須在最新 origin/main clone 上補跑 `--include-github --include-git-branches`。'}",
            "",
        ]
    lines += [
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
        "> 本節依 D387 獨立列出明顯過期、損毀或可重建快取項目，附每項理由與引用反查結果。**本工具絕不自動刪除**；僅在外部反查完整且無截斷時才附上已註解之檢核指令，並須由使用者核准後於自己的終端機手動執行。",
        "",
    ]
    if ext_incomplete:
        lines += [
            f"> **⚠️ 刪除前必讀**：{ext.get('warning')}",
            "",
        ]
    if obvious:
        lines += [
            "| 路徑 | 大小 | 檔數 | 修改時間 (UTC) | 引用反查結果 | 理由 | SHA-256 / MANIFEST |",
            "| --- | ---: | ---: | --- | --- | --- | --- |",
        ]
        for i in obvious:
            sha_disp = f"`{i['sha256'][:12]}…` ({i['hash_kind']})" if i["sha256"] else f"`NONE` ({i['hash_kind']})"
            ref_disp = _fmt_refs(
                i["reference_sources"],
                path_map_only=bool(i.get("path_map_only_reference")),
                path_map_gen=i.get("path_map_generation"),
            )
            lines.append(
                f"| `{i['local_path']}` | {_fmt_bytes(i['size_bytes'])} | {i['file_count']} | `{i['mtime_utc']}` | "
                f"{ref_disp} | {i['rationale']} | {sha_disp} |"
            )
        if ext_incomplete:
            lines += [
                "",
                "### 建議刪除檢核清單（已暫停輸出 / Withheld）",
                "",
                "> **⛔ 刪除指令已暫停輸出**：外部引用反查尚未完整執行或發生截斷"
                f"（`github_issues_prs_scanned={ext.get('github_issues_prs_scanned')}`、"
                f"`open_pr_branches_scanned={ext.get('open_pr_branches_scanned')}`、"
                f"`truncated={bool(ext.get('truncated'))}`）。"
                "請在最新 `origin/main` clone 上執行 `--include-github --include-git-branches` 且確認無截斷後，再重新產生供人工核對之刪除指令。",
                "",
            ]
        else:
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
        if cls == "DELETABLE_CANDIDATE" and ext_incomplete:
            lines.extend([
                f"> **⚠️ 刪除前必讀**：{ext.get('warning')}",
                ">",
                "> **⛔ 刪除指令已暫停輸出**：在 `--include-github --include-git-branches` 完整無截斷執行完成前，本節不輸出任何刪除指令。",
                "",
            ])
        if not subset:
            lines.extend(["（無項目）", ""])
            return
        lines.extend([
            "| 路徑 | 大小 | 檔數 | 修改時間 (UTC) | 引用反查結果 | 理由 | SHA-256 / MANIFEST |",
            "| --- | ---: | ---: | --- | --- | --- | --- |",
        ])
        for i in subset:
            sha_disp = f"`{i['sha256'][:12]}…` ({i['hash_kind']})" if i["sha256"] else f"`NONE` ({i['hash_kind']})"
            ref_disp = _fmt_refs(
                i["reference_sources"],
                path_map_only=bool(i.get("path_map_only_reference")),
                path_map_gen=i.get("path_map_generation"),
            )
            lines.append(
                f"| `{i['local_path']}` | {_fmt_bytes(i['size_bytes'])} | {i['file_count']} | `{i['mtime_utc']}` | "
                f"{ref_disp} | {i['rationale']} | {sha_disp} |"
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
    parser.add_argument(
        "--include-github",
        action="store_true",
        help="Also query all GitHub issues/PRs (bodies+comments via paginated gh api) and open PR diffs",
    )
    parser.add_argument(
        "--github-limit",
        type=int,
        default=None,
        help="Optional finite cap on fetched GitHub items (for debugging/testing; hitting this cap marks the scan truncated)",
    )
    parser.add_argument(
        "--github-refs-json",
        type=Path,
        default=None,
        help="Optional offline JSON snapshot of GitHub issue/PR and open-branch references",
    )
    parser.add_argument(
        "--include-git-branches",
        action="store_true",
        help="Also scan local and remote git branches for local/ references via git grep",
    )
    args = parser.parse_args(argv)

    if not args.local_root.is_dir():
        print(f"ERROR: local root does not exist or is not a directory: {args.local_root}", file=sys.stderr)
        return 2

    report = inventory_local_assets(
        args.repo,
        args.local_root,
        include_github=args.include_github,
        github_refs_json=args.github_refs_json,
        include_git_branches=args.include_git_branches,
        github_limit=args.github_limit,
    )
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
