"""Focused unit tests for #728 reproduce pack (fetch_and_verify, symlinks, .gitattributes)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import pytest

from scripts.reproduce.check_symlinks import check_repo_symlinks, resolve_tracked_symlink
from scripts.reproduce.fetch_and_verify import ReproduceError, run_fetch_and_verify

REPO_ROOT = Path(__file__).resolve().parents[2]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _create_synthetic_pack(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    source = tmp_path / "downloaded"
    (repo / "configs" / "reproduce").mkdir(parents=True)
    (source / "data" / "sample").mkdir(parents=True)
    (source / "evidence" / "run1").mkdir(parents=True)

    cam_bytes = b'{"cameras": ["C1"]}\n'
    cam_file = source / "data" / "sample" / "cameras.json"
    cam_file.write_bytes(cam_bytes)

    rep_bytes = b'{"wrong_person_s": 114.0}\n'
    rep_file = source / "evidence" / "run1" / "report.json"
    rep_file.write_bytes(rep_bytes)

    m_bytes = f"{_sha256_bytes(rep_bytes)}  report.json\n".encode("utf-8")
    m_file = source / "evidence" / "run1" / "MANIFEST.sha256"
    m_file.write_bytes(m_bytes)

    manifest = {
        "manifest_format": "amidst.reproduce-artifact-manifest.v1",
        "format_version": 1,
        "artifacts": [
            {
                "id": "sample-cameras",
                "local_path": "local/data/sample/cameras.json",
                "entry_type": "file",
                "size_bytes": len(cam_bytes),
                "file_count": 1,
                "sha256": _sha256_bytes(cam_bytes),
                "manifest_file": None,
                "manifest_sha256": None,
                "purpose": "synthetic test",
                "cloud_location": "",
                "rebuildable": True,
                "status": "FINAL",
            },
            {
                "id": "sample-run1",
                "local_path": "local/evidence/run1",
                "entry_type": "dir",
                "size_bytes": len(rep_bytes) + len(m_bytes),
                "file_count": 2,
                "sha256": None,
                "manifest_file": "MANIFEST.sha256",
                "manifest_sha256": _sha256_bytes(m_bytes),
                "purpose": "synthetic test",
                "cloud_location": "",
                "rebuildable": True,
                "status": "FINAL",
            },
        ],
    }
    manifest_path = repo / "configs" / "reproduce" / "artifact_manifest_v1.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return repo, source, manifest_path


def test_fetch_and_verify_happy_path_and_verify_only(tmp_path: Path) -> None:
    repo, source, manifest_path = _create_synthetic_pack(tmp_path)

    # Dry-run verifies source without creating local/
    dry = run_fetch_and_verify(manifest_path, repo, source_dir=source, dry_run=True, deep=True)
    assert dry["status"] == "PASS"
    assert dry["checked_count"] == 2
    assert not (repo / "local").exists()

    # Copy and verify
    copied = run_fetch_and_verify(manifest_path, repo, source_dir=source, deep=True)
    assert copied["status"] == "PASS"
    assert (repo / "local" / "data" / "sample" / "cameras.json").is_file()
    assert (repo / "local" / "evidence" / "run1" / "report.json").is_file()

    # Verify-only passes on placed files
    verified = run_fetch_and_verify(manifest_path, repo, verify_only=True, deep=True)
    assert verified["status"] == "PASS"
    assert verified["checked_count"] == 2


def test_fetch_and_verify_hard_fails_on_sha256_mismatch(tmp_path: Path) -> None:
    repo, source, manifest_path = _create_synthetic_pack(tmp_path)
    # Tamper with file after manifest creation
    (source / "data" / "sample" / "cameras.json").write_bytes(b'{"cameras": ["TAMPERED"]}\n')

    with pytest.raises(ReproduceError, match="SHA256_MISMATCH"):
        run_fetch_and_verify(manifest_path, repo, source_dir=source)


def test_fetch_and_verify_hard_fails_on_missing_file(tmp_path: Path) -> None:
    repo, source, manifest_path = _create_synthetic_pack(tmp_path)
    (source / "data" / "sample" / "cameras.json").unlink()

    with pytest.raises(ReproduceError, match="SOURCE_ARTIFACT_MISSING"):
        run_fetch_and_verify(manifest_path, repo, source_dir=source)

    # Verify-only on empty repo also hard-fails
    with pytest.raises(ReproduceError, match="MISSING_FILE"):
        run_fetch_and_verify(manifest_path, repo, verify_only=True)


def test_fetch_and_verify_cli_exits_nonzero_on_mismatch(tmp_path: Path) -> None:
    repo, source, manifest_path = _create_synthetic_pack(tmp_path)
    (source / "evidence" / "run1" / "report.json").write_bytes(b"corrupted")
    script = REPO_ROOT / "scripts" / "reproduce" / "fetch_and_verify.py"

    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo",
            str(repo),
            "--manifest",
            str(manifest_path),
            "--source-dir",
            str(source),
            "--deep",
            "--json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != 0
    payload = json.loads(proc.stdout)
    assert payload["status"] == "FAIL"
    assert "SHA256_MISMATCH" in payload["error"]


def test_no_hardcoded_cloud_urls_or_credentials() -> None:
    manifest_text = (REPO_ROOT / "configs" / "reproduce" / "artifact_manifest_v1.json").read_text(encoding="utf-8")
    script_text = (REPO_ROOT / "scripts" / "reproduce" / "fetch_and_verify.py").read_text(encoding="utf-8")

    forbidden = re.compile(
        r"https?://|drive\.google\.com|dropbox\.com|onedrive|s3://|gs://|AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._-]{10,}",
        re.IGNORECASE,
    )
    assert forbidden.search(manifest_text) is None
    assert forbidden.search(script_text) is None

    manifest = json.loads(manifest_text)
    for item in manifest["artifacts"]:
        assert item["cloud_location"] == ""


def test_gitattributes_protects_data_and_evidence_hashes() -> None:
    gitattributes = REPO_ROOT / ".gitattributes"
    assert gitattributes.is_file()
    content = gitattributes.read_text(encoding="utf-8")
    for pattern in ("*.json -text", "*.jsonl -text", "*.csv -text", "*.sha256 -text", "*.png -text", "*.pth -text"):
        assert pattern in content


def test_tracked_symlinks_and_text_pointer_fallback(tmp_path: Path) -> None:
    # Real repo check: all 3 tracked symlinks must resolve cleanly on both Unix and Windows
    res = check_repo_symlinks(REPO_ROOT)
    assert res["status"] == "PASS"
    assert res["tracked_symlink_count"] >= 3
    tracked_paths = {item["path"] for item in res["items"]}
    assert "docs/DEVELOPMENT_RULES.md" in tracked_paths
    assert "docs/GEOMETRY_PROVIDER.md" in tracked_paths
    assert "docs/PHASE1_BENCHMARK_PROTOCOL.md" in tracked_paths

    # Synthetic text-pointer fallback test (simulates core.symlinks=false checkout)
    fake_repo = tmp_path / "fake_repo"
    (fake_repo / "docs" / "specs").mkdir(parents=True)
    target = fake_repo / "docs" / "specs" / "RULES.md"
    target.write_text("# Rules\n", encoding="utf-8")
    pointer = fake_repo / "docs" / "RULES.md"
    pointer.write_text("specs/RULES.md", encoding="utf-8")

    resolved, mode, raw = resolve_tracked_symlink(fake_repo, "docs/RULES.md")
    assert mode == "TEXT_POINTER_FALLBACK_OK"
    assert raw == "specs/RULES.md"
    assert resolved == target.resolve()
