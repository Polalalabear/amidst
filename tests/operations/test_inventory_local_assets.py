"""Unit tests for scripts/inventory_local_assets.py (#729, D387)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from scripts.inventory_local_assets import inventory_local_assets, render_markdown


def _snapshot_tree(root: Path) -> dict[str, bytes]:
    snap: dict[str, bytes] = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file():
            snap[rel] = p.read_bytes()
        elif p.is_dir():
            snap[rel + "/"] = b"<DIR>"
    return snap


def _build_synthetic_repo_and_local(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    local = tmp_path / "local"
    (repo / "docs" / "operations").mkdir(parents=True)
    (repo / "docs" / "archive").mkdir(parents=True)
    (repo / "configs" / "reproduce").mkdir(parents=True)

    # Active doc references one evidence folder
    (repo / "docs" / "operations" / "REPORT.md").write_text(
        "Evidence at `local/evidence/e5-kept-run/report.json`.\n",
        encoding="utf-8",
    )
    # Archive-only doc references one archive folder
    (repo / "docs" / "archive" / "OLD_DOC.md").write_text(
        "Old ref `local/evidence/archive-only-ref`.\n",
        encoding="utf-8",
    )
    # Demo integration config
    (repo / "configs" / "demo_integration_local.json").write_text(
        json.dumps({"owned_root": "local/data/demo-owned-v1"}),
        encoding="utf-8",
    )
    # Local path map with OBSOLETE and CITED entries
    (repo / "configs" / "local_path_map_v1.json").write_text(
        json.dumps(
            {
                "entries": [
                    {"old": "~/amidst-artifacts/old-obsolete", "new": "local/archive/old-obsolete", "generation": "OBSOLETE"},
                    {"old": "~/amidst-artifacts/cited-no-ref", "new": "local/evidence/cited-no-ref", "generation": "CITED"},
                ]
            }
        ),
        encoding="utf-8",
    )
    # Reproduce manifest (#728)
    (repo / "configs" / "reproduce" / "artifact_manifest_v1.json").write_text(
        json.dumps({"artifacts": [{"local_path": "local/data/repro-required/cameras.json"}]}),
        encoding="utf-8",
    )

    # Create synthetic local/ contents
    # 1. KEEP: actively referenced evidence with MANIFEST.sha256
    kept_ev = local / "evidence" / "e5-kept-run"
    kept_ev.mkdir(parents=True)
    (kept_ev / "report.json").write_text('{"ok": true}\n', encoding="utf-8")
    (kept_ev / "MANIFEST.sha256").write_text("abc  report.json\n", encoding="utf-8")

    # 2. KEEP: demo owned root
    demo_dir = local / "data" / "demo-owned-v1"
    demo_dir.mkdir(parents=True)
    (demo_dir / "marker.txt").write_text("demo\n", encoding="utf-8")

    # 3. KEEP: required by reproduce manifest
    repro_dir = local / "data" / "repro-required"
    repro_dir.mkdir(parents=True)
    (repro_dir / "cameras.json").write_text("{}\n", encoding="utf-8")

    # 4. KEEP (protected original asset, even though unreferenced!)
    orig_dir = local / "data" / "scene-original-unreferenced"
    orig_dir.mkdir(parents=True)
    (orig_dir / "school_r004.blend").write_bytes(b"BLENDER-FAKE-BYTES")

    # 5. KEEP (protected GT directory, even though unreferenced!)
    gt_dir = local / "data" / "gt_private"
    gt_dir.mkdir(parents=True)
    (gt_dir / "tracks.json").write_text("[]\n", encoding="utf-8")

    # 6. DELETABLE_CANDIDATE + OBVIOUSLY_STALE_OR_BROKEN: empty dir
    (local / "evidence" / "empty-run").mkdir(parents=True)

    # 7. DELETABLE_CANDIDATE + OBVIOUSLY_STALE_OR_BROKEN: rebuildable cache
    cache_dir = local / "evidence" / "uv-cache"
    cache_dir.mkdir(parents=True)
    (cache_dir / "wheel.bin").write_bytes(b"12345")

    # 8. DELETABLE_CANDIDATE + OBVIOUSLY_STALE_OR_BROKEN: failed run marker
    failed_dir = local / "evidence" / "e5-failed-run"
    failed_dir.mkdir(parents=True)
    (failed_dir / "error.log").write_text("boom\n", encoding="utf-8")

    # 9. DELETABLE_CANDIDATE + OBVIOUSLY_STALE_OR_BROKEN: OBSOLETE in path map
    obs_dir = local / "archive" / "old-obsolete"
    obs_dir.mkdir(parents=True)
    (obs_dir / "x.txt").write_text("old\n", encoding="utf-8")

    # 10. DELETABLE_CANDIDATE (normal unreferenced)
    unref_dir = local / "evidence" / "misc-unreferenced"
    unref_dir.mkdir(parents=True)
    (unref_dir / "notes.txt").write_text("hello\n", encoding="utf-8")

    # 11. UNCERTAIN: referenced only in docs/archive/
    arch_ref = local / "evidence" / "archive-only-ref"
    arch_ref.mkdir(parents=True)
    (arch_ref / "old.json").write_text("{}\n", encoding="utf-8")

    # 12. UNCERTAIN: CITED in path_map without active ref
    cited_dir = local / "evidence" / "cited-no-ref"
    cited_dir.mkdir(parents=True)
    (cited_dir / "data.json").write_text("{}\n", encoding="utf-8")

    # 13. UNCERTAIN: unreferenced item in local/archive/
    arch_item = local / "archive" / "historical-snapshot"
    arch_item.mkdir(parents=True)
    (arch_item / "snap.txt").write_text("snap\n", encoding="utf-8")

    return repo, local


def test_inventory_classifications_and_strict_read_only(tmp_path: Path) -> None:
    repo, local = _build_synthetic_repo_and_local(tmp_path)
    before = _snapshot_tree(local)

    report = inventory_local_assets(repo, local)
    md = render_markdown(report)

    # Strictly read-only: filesystem under local/ must be byte-for-byte identical
    after = _snapshot_tree(local)
    assert after == before
    assert report["read_only"] is True

    by_path = {item["local_path"]: item for item in report["items"]}

    # KEEP checks
    assert by_path["local/evidence/e5-kept-run"]["classification"] == "KEEP"
    assert by_path["local/evidence/e5-kept-run"]["hash_kind"] == "manifest_sha256"
    expected_msha = hashlib.sha256((local / "evidence" / "e5-kept-run" / "MANIFEST.sha256").read_bytes()).hexdigest()
    assert by_path["local/evidence/e5-kept-run"]["sha256"] == expected_msha

    assert by_path["local/data/demo-owned-v1"]["classification"] == "KEEP"
    assert by_path["local/data/repro-required"]["classification"] == "KEEP"

    # Protected original assets MUST be KEEP and NEVER deletable
    assert by_path["local/data/scene-original-unreferenced"]["classification"] == "KEEP"
    assert by_path["local/data/scene-original-unreferenced"]["is_obviously_stale_or_broken"] is False
    assert by_path["local/data/gt_private"]["classification"] == "KEEP"
    assert by_path["local/data/gt_private"]["is_obviously_stale_or_broken"] is False

    # OBVIOUSLY_STALE_OR_BROKEN checks (D387)
    for obvious_path in (
        "local/evidence/empty-run",
        "local/evidence/uv-cache",
        "local/evidence/e5-failed-run",
        "local/archive/old-obsolete",
    ):
        assert by_path[obvious_path]["classification"] == "DELETABLE_CANDIDATE"
        assert by_path[obvious_path]["is_obviously_stale_or_broken"] is True
        assert by_path[obvious_path]["obviously_stale_or_broken_reason"]

    # Normal DELETABLE_CANDIDATE (not obviously broken)
    assert by_path["local/evidence/misc-unreferenced"]["classification"] == "DELETABLE_CANDIDATE"
    assert by_path["local/evidence/misc-unreferenced"]["is_obviously_stale_or_broken"] is False

    # UNCERTAIN checks
    assert by_path["local/evidence/archive-only-ref"]["classification"] == "UNCERTAIN"
    assert by_path["local/evidence/cited-no-ref"]["classification"] == "UNCERTAIN"
    assert by_path["local/archive/historical-snapshot"]["classification"] == "UNCERTAIN"

    # Markdown dedicated D387 section + commented-out review checklist
    assert "## 明顯過期或錯誤（Obviously Stale or Broken — D387）" in md
    assert "# rm -rf -- \"local/evidence/uv-cache\"" in md
    assert "local/data/scene-original-unreferenced" not in md.split("## 保留（KEEP）")[0]


def test_inventory_cli_writes_json_and_md(tmp_path: Path) -> None:
    repo, local = _build_synthetic_repo_and_local(tmp_path)
    out_json = tmp_path / "out" / "inv.json"
    out_md = tmp_path / "out" / "inv.md"
    script = Path(__file__).resolve().parents[2] / "scripts" / "inventory_local_assets.py"

    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo",
            str(repo),
            "--local-root",
            str(local),
            "--json-out",
            str(out_json),
            "--md-out",
            str(out_md),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert out_json.is_file()
    assert out_md.is_file()
    parsed = json.loads(out_json.read_text(encoding="utf-8"))
    assert parsed["read_only"] is True
    assert parsed["summary"]["OBVIOUSLY_STALE_OR_BROKEN"]["item_count"] == 4
