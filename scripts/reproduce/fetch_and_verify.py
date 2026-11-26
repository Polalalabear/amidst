#!/usr/bin/env python3
"""Place and SHA-256 verify LOCAL reproduce artifacts (#728, #733, D380, D384).

Reads ``configs/reproduce/artifact_manifest_v1.json`` (or ``--manifest``),
copies artifacts from a user-provided local download directory into
``<repo>/local/...`` (unless ``--verify-only`` or ``--dry-run``), and verifies
SHA-256 / MANIFEST SHA-256 for every entry.

Stops immediately with non-zero exit code on ANY missing file or hash mismatch.
Contains ZERO hardcoded cloud URLs or credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
from typing import Any


DEFAULT_MANIFEST_REL = Path("configs/reproduce/artifact_manifest_v1.json")


class ReproduceError(RuntimeError):
    """Hard failure on missing artifact, unsafe path, or SHA-256 mismatch."""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _dir_listing_sha256(root: Path) -> tuple[str, int, int]:
    lines: list[str] = []
    file_count = 0
    total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        filenames.sort()
        d_rel = Path(dirpath).relative_to(root).as_posix()
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.is_symlink():
                continue
            f_rel = f"{d_rel}/{fname}" if d_rel != "." else fname
            size = fpath.stat().st_size
            lines.append(f"{f_rel}\t{size}")
            file_count += 1
            total_bytes += size
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest(), file_count, total_bytes


def _validate_local_rel(local_path: str) -> PurePosixPath:
    if not isinstance(local_path, str) or not local_path or "\\" in local_path or "\0" in local_path:
        raise ReproduceError(f"UNSAFE_LOCAL_PATH: {local_path!r}")
    p = PurePosixPath(local_path)
    if p.is_absolute() or ".." in p.parts or len(p.parts) < 3 or p.parts[0] != "local":
        raise ReproduceError(f"LOCAL_PATH_MUST_BE_UNDER_LOCAL: {local_path!r}")
    return p


def _resolve_source_entry(source_dir: Path, rel_local: PurePosixPath) -> Path:
    """Locate artifact in source_dir whether the user downloaded with or without leading 'local/'."""
    without_local = PurePosixPath(*rel_local.parts[1:])
    cand_direct = source_dir / Path(*without_local.parts)
    if cand_direct.exists():
        return cand_direct
    cand_with_local = source_dir / Path(*rel_local.parts)
    if cand_with_local.exists():
        return cand_with_local
    raise ReproduceError(
        f"SOURCE_ARTIFACT_MISSING: expected {cand_direct} or {cand_with_local}"
    )


def _resolve_target_entry(repo_root: Path, local_root: Path | None, rel_local: PurePosixPath) -> Path:
    if local_root is not None:
        return local_root / Path(*rel_local.parts[1:])
    return repo_root / Path(*rel_local.parts)


def _verify_sha256_manifest_lines(dir_path: Path, manifest_rel: str) -> int:
    """Verify every '<sha256>  <relpath>' line inside a MANIFEST.sha256 file."""
    mpath = dir_path / manifest_rel
    checked = 0
    for lineno, raw in enumerate(mpath.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise ReproduceError(f"INVALID_MANIFEST_LINE: {mpath}:{lineno}")
        expected_sha, rel_item = parts[0].lower(), parts[1].strip()
        if rel_item.startswith("./"):
            rel_item = rel_item[2:]
        if PurePosixPath(rel_item) == PurePosixPath(manifest_rel):
            # Some frozen MANIFEST.sha256 files were created via `shasum * > MANIFEST.sha256`
            # and list themselves as 0-byte; the manifest file itself is already verified
            # against manifest_sha256 above.
            continue
        item_path = dir_path / Path(*PurePosixPath(rel_item).parts)
        if not item_path.is_file():
            raise ReproduceError(f"MANIFEST_ITEM_MISSING: {item_path} (listed in {mpath}:{lineno})")
        actual_sha = _sha256_file(item_path)
        if actual_sha != expected_sha:
            raise ReproduceError(
                f"SHA256_MISMATCH: {item_path} expected={expected_sha} actual={actual_sha}"
            )
        checked += 1
    return checked


def verify_entry(entry: dict[str, Any], target_path: Path, deep: bool = False) -> dict[str, Any]:
    """Verify one artifact entry in place. Raises ReproduceError immediately on mismatch."""
    entry_id = entry.get("id") or entry.get("local_path")
    entry_type = entry.get("entry_type", "file")

    if entry_type == "file":
        if not target_path.is_file():
            raise ReproduceError(f"MISSING_FILE ({entry_id}): {target_path}")
        expected_sha = entry.get("sha256")
        if not expected_sha:
            raise ReproduceError(f"MANIFEST_MISSING_SHA256 ({entry_id}): file entry must declare sha256")
        actual_sha = _sha256_file(target_path)
        if actual_sha.lower() != expected_sha.lower():
            raise ReproduceError(
                f"SHA256_MISMATCH ({entry_id}): {target_path} expected={expected_sha} actual={actual_sha}"
            )
        return {
            "id": entry_id,
            "local_path": entry["local_path"],
            "entry_type": "file",
            "verified_hash": actual_sha,
            "hash_kind": "file_sha256",
            "status": "VERIFIED",
        }

    if entry_type == "dir":
        if not target_path.is_dir():
            raise ReproduceError(f"MISSING_DIR ({entry_id}): {target_path}")
        manifest_file = entry.get("manifest_file")
        expected_msha = entry.get("manifest_sha256")
        if manifest_file and expected_msha:
            mpath = target_path / manifest_file
            if not mpath.is_file():
                raise ReproduceError(f"MISSING_MANIFEST_FILE ({entry_id}): {mpath}")
            actual_msha = _sha256_file(mpath)
            if actual_msha.lower() != expected_msha.lower():
                raise ReproduceError(
                    f"MANIFEST_SHA256_MISMATCH ({entry_id}): {mpath} expected={expected_msha} actual={actual_msha}"
                )
            deep_checked = 0
            if deep and manifest_file.endswith(".sha256"):
                deep_checked = _verify_sha256_manifest_lines(target_path, manifest_file)
            return {
                "id": entry_id,
                "local_path": entry["local_path"],
                "entry_type": "dir",
                "verified_hash": actual_msha,
                "hash_kind": "manifest_sha256",
                "deep_files_checked": deep_checked,
                "status": "VERIFIED",
            }
        expected_listing = entry.get("dir_listing_sha256")
        if expected_listing:
            actual_listing, file_count, total_bytes = _dir_listing_sha256(target_path)
            if actual_listing.lower() != expected_listing.lower():
                raise ReproduceError(
                    f"DIR_LISTING_SHA256_MISMATCH ({entry_id}): {target_path} "
                    f"expected={expected_listing} actual={actual_listing}"
                )
            return {
                "id": entry_id,
                "local_path": entry["local_path"],
                "entry_type": "dir",
                "verified_hash": actual_listing,
                "hash_kind": "dir_listing_sha256",
                "file_count": file_count,
                "size_bytes": total_bytes,
                "status": "VERIFIED",
            }
        raise ReproduceError(f"MANIFEST_NO_VERIFIABLE_HASH ({entry_id}): declare manifest_sha256 or dir_listing_sha256")

    raise ReproduceError(f"UNSUPPORTED_ENTRY_TYPE ({entry_id}): {entry_type!r}")


def _copy_artifact(src: Path, dst: Path, entry_type: str) -> None:
    if entry_type == "file":
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    elif entry_type == "dir":
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        raise ReproduceError(f"UNSUPPORTED_ENTRY_TYPE: {entry_type!r}")


def run_fetch_and_verify(
    manifest_path: Path,
    repo_root: Path,
    *,
    source_dir: Path | None = None,
    local_root: Path | None = None,
    verify_only: bool = False,
    dry_run: bool = False,
    deep: bool = False,
    only_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Execute copy (if not verify_only/dry_run) and fail-fast SHA-256 verification."""
    if not manifest_path.is_file():
        raise ReproduceError(f"MANIFEST_NOT_FOUND: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        raise ReproduceError(f"MANIFEST_EMPTY_ARTIFACTS: {manifest_path}")

    if not verify_only and source_dir is None:
        raise ReproduceError("SOURCE_DIR_REQUIRED: pass --source-dir <downloaded_folder> or --verify-only")
    if source_dir is not None and not source_dir.is_dir():
        raise ReproduceError(f"SOURCE_DIR_NOT_FOUND: {source_dir}")

    selected = [a for a in artifacts if not only_ids or a.get("id") in only_ids]
    if not selected:
        raise ReproduceError("NO_MATCHING_ARTIFACTS_SELECTED")

    results: list[dict[str, Any]] = []
    for entry in selected:
        rel_local = _validate_local_rel(entry["local_path"])
        target_path = _resolve_target_entry(repo_root, local_root, rel_local)
        entry_type = entry.get("entry_type", "file")

        if not verify_only:
            assert source_dir is not None
            src_path = _resolve_source_entry(source_dir, rel_local)
            if dry_run:
                # Verify source in place during dry-run without copying
                rec = verify_entry(entry, src_path, deep=deep)
                rec["action"] = f"DRY_RUN_WOULD_COPY -> {target_path}"
                results.append(rec)
                continue
            _copy_artifact(src_path, target_path, entry_type)

        if dry_run and verify_only:
            rec = verify_entry(entry, target_path, deep=deep)
            rec["action"] = "DRY_RUN_VERIFY_ONLY"
            results.append(rec)
        else:
            rec = verify_entry(entry, target_path, deep=deep)
            rec["action"] = "VERIFIED_ONLY" if verify_only else "COPIED_AND_VERIFIED"
            results.append(rec)

    return {
        "status": "PASS",
        "manifest": str(manifest_path),
        "mode": "verify-only" if verify_only else ("dry-run" if dry_run else "copy-and-verify"),
        "checked_count": len(results),
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Place and SHA-256 verify LOCAL reproduce artifacts (#728). Fail-fast on any mismatch."
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root (default: auto-detected from script path)",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=f"Path to artifact manifest JSON (default: <repo>/{DEFAULT_MANIFEST_REL.as_posix()})",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=None,
        help="User-downloaded local folder containing artifacts (required unless --verify-only)",
    )
    parser.add_argument(
        "--local-root",
        type=Path,
        default=None,
        help="Override target local/ root (default: <repo>/local)",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify existing files under local/ (or --local-root) without copying",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate source availability and hashes without writing to destination",
    )
    parser.add_argument(
        "--deep",
        action="store_true",
        help="Also verify every file listed inside MANIFEST.sha256 directory manifests",
    )
    parser.add_argument(
        "--id",
        dest="only_ids",
        action="append",
        default=None,
        help="Verify/copy only specific artifact id(s) (repeatable)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON receipt to stdout",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo.resolve()
    manifest_path = (args.manifest or (repo_root / DEFAULT_MANIFEST_REL)).resolve()

    try:
        receipt = run_fetch_and_verify(
            manifest_path=manifest_path,
            repo_root=repo_root,
            source_dir=args.source_dir.resolve() if args.source_dir else None,
            local_root=args.local_root.resolve() if args.local_root else None,
            verify_only=args.verify_only,
            dry_run=args.dry_run,
            deep=args.deep,
            only_ids=set(args.only_ids) if args.only_ids else None,
        )
    except ReproduceError as exc:
        err = {"status": "FAIL", "error": str(exc)}
        if args.json:
            print(json.dumps(err, ensure_ascii=False, indent=2))
        else:
            print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
    else:
        print(f"PASS ({receipt['mode']}): verified {receipt['checked_count']} artifact(s)")
        for item in receipt["results"]:
            print(f"  [OK] {item['id']} -> {item['local_path']} ({item['hash_kind']}: {item['verified_hash'][:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
