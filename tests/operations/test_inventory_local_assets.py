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
    assert parsed["external_ref_scan"]["github_issues_prs_scanned"] is False
    assert parsed["external_ref_scan"]["open_pr_branches_scanned"] is False
    assert parsed["external_ref_scan"]["warning"]


def test_ancestor_prefix_propagation_and_non_area_local_paths(tmp_path: Path) -> None:
    """PR #738 P1-1: docs referencing local/X/child (e.g. local/runtime/live-main)
    MUST classify local/X (local/runtime) as KEEP with active_reference_count >= 1,
    along with local/manifests, local/logs, and local/.migration-d169.
    """
    repo = tmp_path / "repo"
    local = tmp_path / "local"
    (repo / "docs" / "agents").mkdir(parents=True)
    (repo / "docs" / "operations").mkdir(parents=True)

    # Doc under docs/agents/ references child paths under local/runtime, local/manifests, local/logs, local/.migration-d169
    (repo / "docs" / "agents" / "COORDINATOR_HANDOFF_20261117.md").write_text(
        "\n".join(
            [
                "- Live 8791 runtime lives at `local/runtime/live-main`.",
                "- Manifests live under `~/amidst/local/manifests/run-01.json`.",
                "- Logs written to `./local/logs/server.log`.",
                "- Migration marker: `local/.migration-d169`.",
                "- System path `/usr/local/bin/python3` is a system binary, not a repo asset.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    # Create top-level entries in local/
    (local / "runtime" / "live-main").mkdir(parents=True)
    (local / "runtime" / "live-main" / "state.json").write_text("{}\n", encoding="utf-8")

    (local / "manifests").mkdir(parents=True)
    (local / "manifests" / "run-01.json").write_text("{}\n", encoding="utf-8")

    (local / "logs").mkdir(parents=True)
    (local / "logs" / "server.log").write_text("ok\n", encoding="utf-8")

    (local / ".migration-d169").write_text("done\n", encoding="utf-8")

    # Unreferenced sibling should still be DELETABLE_CANDIDATE
    (local / "bin").mkdir(parents=True)
    (local / "bin" / "unused.txt").write_text("nope\n", encoding="utf-8")

    report = inventory_local_assets(repo, local)
    by_path = {item["local_path"]: item for item in report["items"]}

    for expected_keep in ("local/runtime", "local/manifests", "local/logs", "local/.migration-d169"):
        assert by_path[expected_keep]["classification"] == "KEEP", expected_keep
        assert by_path[expected_keep]["active_reference_count"] >= 1, expected_keep

    # /usr/local/bin must NOT have falsely kept local/bin
    assert by_path["local/bin"]["classification"] == "DELETABLE_CANDIDATE"
    assert by_path["local/bin"]["active_reference_count"] == 0


def test_github_refs_json_keeps_issue_and_pr_branch_referenced_items(tmp_path: Path) -> None:
    """PR #738 P1-2: an item referenced ONLY in a GitHub issue/PR or open PR branch
    via --github-refs-json MUST be classified as KEEP.
    """
    repo = tmp_path / "repo"
    local = tmp_path / "local"
    (repo / "docs").mkdir(parents=True)

    # Item referenced ONLY in a GitHub issue (nowhere in repo checkout)
    gh_only = local / "evidence" / "coordinator-20261109"
    gh_only.mkdir(parents=True)
    (gh_only / "audit.json").write_text('{"ok": true}\n', encoding="utf-8")

    # Item referenced ONLY in an open PR branch
    pr_only = local / "evidence" / "open-pr-experiment"
    pr_only.mkdir(parents=True)
    (pr_only / "metrics.json").write_text('{"ok": true}\n', encoding="utf-8")

    # Truly unreferenced item
    unref = local / "evidence" / "truly-unreferenced"
    unref.mkdir(parents=True)
    (unref / "x.txt").write_text("x\n", encoding="utf-8")

    # Without GitHub refs: coordinator-20261109 is DELETABLE_CANDIDATE and warning is emitted
    base_report = inventory_local_assets(repo, local)
    base_by_path = {item["local_path"]: item for item in base_report["items"]}
    assert base_by_path["local/evidence/coordinator-20261109"]["classification"] == "DELETABLE_CANDIDATE"
    assert base_report["external_ref_scan"]["github_issues_prs_scanned"] is False
    assert base_report["external_ref_scan"]["open_pr_branches_scanned"] is False
    base_md = render_markdown(base_report)
    assert "外部引用掃描未完整警示" in base_md
    assert "刪除前必讀" in base_md

    # With --github-refs-json: both issue-referenced and open-PR-referenced items become KEEP
    gh_json = tmp_path / "gh_refs.json"
    gh_json.write_text(
        json.dumps(
            {
                "issues_and_prs": [
                    {
                        "source": "github:issue#729",
                        "text": "Please keep local/evidence/coordinator-20261109/audit.json for audit.",
                    }
                ],
                "open_pr_branches": [
                    {
                        "branch": "origin/codex/feat-exp",
                        "source": "github:pr#740:docs/notes.md",
                        "text": "Depends on local/evidence/open-pr-experiment/metrics.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    out_json = tmp_path / "inv_gh.json"
    out_md = tmp_path / "inv_gh.md"
    script = Path(__file__).resolve().parents[2] / "scripts" / "inventory_local_assets.py"
    proc = subprocess.run(
        [
            sys.executable,
            str(script),
            "--repo",
            str(repo),
            "--local-root",
            str(local),
            "--github-refs-json",
            str(gh_json),
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
    gh_report = json.loads(out_json.read_text(encoding="utf-8"))
    gh_by_path = {item["local_path"]: item for item in gh_report["items"]}

    assert gh_report["external_ref_scan"]["github_issues_prs_scanned"] is True
    assert gh_report["external_ref_scan"]["open_pr_branches_scanned"] is True
    assert gh_report["external_ref_scan"]["warning"] == ""

    assert gh_by_path["local/evidence/coordinator-20261109"]["classification"] == "KEEP"
    assert gh_by_path["local/evidence/coordinator-20261109"]["active_reference_count"] >= 1
    assert gh_by_path["local/evidence/open-pr-experiment"]["classification"] == "KEEP"
    assert gh_by_path["local/evidence/open-pr-experiment"]["active_reference_count"] >= 1
    assert gh_by_path["local/evidence/truly-unreferenced"]["classification"] == "DELETABLE_CANDIDATE"
