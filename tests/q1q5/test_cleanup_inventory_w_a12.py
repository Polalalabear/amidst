"""Tests for W-A12 (#430) cleanup inventory, remote branches, open issues, and merge conflicts."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

REPO_ROOT = Path(__file__).resolve().parents[2]
MD_PATH = REPO_ROOT / "docs" / "operations" / "CLEANUP_INVENTORY_AND_CANDIDATES_20261104.md"
JSON_PATH = REPO_ROOT / "docs" / "operations" / "CLEANUP_INVENTORY_20261104.json"
REGISTRY_PATH = REPO_ROOT / "configs" / "architecture" / "schema_registry_v1.json"

NON_DELETION_STATEMENT = (
    "本文件只做盤點與建議，不執行任何刪除、分支移除或 issue 關閉；"
    "實際動作屬 #431（cleanup:delete），需 Claude 審查通過＋使用者授權。"
)

VALID_BRANCH_CATEGORIES = {
    "KEEP_ACTIVE",
    "KEEP_EVIDENCE",
    "ARCHIVE_TAG_CANDIDATE",
    "DELETE_CANDIDATE_AFTER_W_A13_AUTH",
}

VALID_ISSUE_CATEGORIES = {
    "KEEP_OPEN_ACTIVE",
    "DEFERRED_QUEUE",
    "CLOSE_CANDIDATE_AFTER_W_A13_AUTH",
}

VALID_DOC_CATEGORIES = {
    "KEEP_CURRENT",
    "ARCHIVE_WITH_POINTER_CANDIDATE",
}


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(REPO_ROOT), *args],
        text=True,
        encoding="utf-8",
        errors="replace",
    ).strip()


def test_both_inventory_files_exist() -> None:
    assert MD_PATH.is_file(), f"Markdown inventory file missing: {MD_PATH}"
    assert JSON_PATH.is_file(), f"JSON inventory file missing: {JSON_PATH}"
    assert MD_PATH.stat().st_size > 0, "Markdown file is empty"
    assert JSON_PATH.stat().st_size > 0, "JSON file is empty"


def test_non_deletion_statement_present() -> None:
    md_content = MD_PATH.read_text(encoding="utf-8")
    # Verify the non-deletion statement is prominent at the top of the Markdown document
    first_1000_chars = md_content[:1000]
    assert NON_DELETION_STATEMENT in first_1000_chars, (
        f"Non-deletion guard statement missing at top of {MD_PATH.name}"
    )

    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    assert data.get("non_deletion_guard") == NON_DELETION_STATEMENT
    exec_guard = data.get("execution_guard", {})
    assert exec_guard.get("deletions_executed") is False
    assert exec_guard.get("branches_removed") == 0
    assert exec_guard.get("issues_closed") == 0
    assert exec_guard.get("files_deleted") == 0
    assert exec_guard.get("requires_claude_review") is True
    assert exec_guard.get("requires_explicit_user_authorization") is True
    assert exec_guard.get("execution_deferred_to_issue") == "#431"


def test_json_valid_and_schema_safe() -> None:
    raw_json = JSON_PATH.read_text(encoding="utf-8")
    data = json.loads(raw_json)
    assert isinstance(data, dict)
    assert data.get("document_id") == "W-A12-CLEANUP-INVENTORY-20261104"
    assert data.get("issue_ref") == "#430"

    # Verify no unregistered *.v1 schema literals in JSON
    schema_reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    registered = {s["value"] for s in schema_reg["schemas"]}
    schema_literals = re.findall(
        r'''\b(?:["']?schema_version["']?)\s*[:=]\s*["']([^"'\r\n]+)["']''',
        raw_json,
        re.I,
    )
    for literal in schema_literals:
        assert literal in registered, f"Unregistered schema literal found in JSON: {literal}"


def test_every_remote_branch_present_and_categorized() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    branches_inv = data["section_2_remote_branches_inventory"]
    all_branches = branches_inv["remote_branches"]
    branch_map = {b["branch"]: b for b in all_branches}

    # Inspect git remote branches directly
    raw_git_branches = [
        line.strip()
        for line in git("branch", "-r").splitlines()
        if line.strip() and "->" not in line
    ]

    missing = [b for b in raw_git_branches if b not in branch_map]
    assert not missing, f"Missing remote branches in inventory: {missing[:10]} (total missing: {len(missing)})"

    seen_categories: set[str] = set()
    for b in all_branches:
        cat = b.get("category")
        assert cat in VALID_BRANCH_CATEGORIES, f"Invalid category {cat} on branch {b['branch']}"
        seen_categories.add(cat)
        assert b.get("head_sha"), f"Missing head_sha for branch {b['branch']}"
        assert b.get("rationale"), f"Missing rationale for branch {b['branch']}"
        assert b.get("superseded_by"), f"Missing superseded_by for branch {b['branch']}"

    assert seen_categories == VALID_BRANCH_CATEGORIES, (
        f"Missing branch categories: {VALID_BRANCH_CATEGORIES - seen_categories}"
    )


def test_open_issues_inventory_categories() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    issues = data["section_3_open_issues_inventory"]
    assert len(issues) >= 100, f"Expected full issue inventory, found {len(issues)}"

    issue_map = {item["issue_number"]: item for item in issues}
    assert 93 in issue_map, "Issue #93 missing from inventory"
    assert 430 in issue_map, "Issue #430 missing from inventory"
    assert 431 in issue_map, "Issue #431 missing from inventory"
    assert 434 in issue_map, "Issue #434 missing from inventory"

    seen_categories: set[str] = set()
    for item in issues:
        cat = item.get("category")
        assert cat in VALID_ISSUE_CATEGORIES, f"Invalid category {cat} for issue #{item['issue_number']}"
        seen_categories.add(cat)
        assert item.get("title"), f"Missing title for issue #{item['issue_number']}"
        assert item.get("rationale"), f"Missing rationale for issue #{item['issue_number']}"

    assert seen_categories == VALID_ISSUE_CATEGORIES, (
        f"Missing issue categories: {VALID_ISSUE_CATEGORIES - seen_categories}"
    )


def test_superseded_docs_inventory_categories() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    docs_section = data["section_4_superseded_docs_inventory"]
    docs = docs_section["documents"]
    assert len(docs) >= 100, f"Expected full doc inventory, found {len(docs)}"

    seen_categories: set[str] = set()
    for d in docs:
        cat = d.get("recommendation")
        assert cat in VALID_DOC_CATEGORIES, f"Invalid doc category {cat} for {d['path']}"
        seen_categories.add(cat)
        assert d.get("preserve_full_content") is True
        assert d.get("rationale"), f"Missing rationale for doc {d['path']}"
        if cat == "ARCHIVE_WITH_POINTER_CANDIDATE":
            assert d.get("target_archive_path", "").startswith("docs/archive/"), (
                f"Expected docs/archive/ target for {d['path']}, got {d.get('target_archive_path')}"
            )

    assert seen_categories == VALID_DOC_CATEGORIES, (
        f"Missing doc categories: {VALID_DOC_CATEGORIES - seen_categories}"
    )


def test_main_merge_conflict_analysis_integrity() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    conflict_data = data["section_5_main_merge_conflict_analysis"]

    expected_mb = git("merge-base", "origin/main", "origin/mainline/q1q5")
    assert conflict_data.get("merge_base_sha") == expected_mb
    assert conflict_data.get("merge_tree_conflict_count") == 1

    diverged = conflict_data.get("diverged_and_conflict_files", [])
    diverged_paths = {df["path"] for df in diverged}
    assert "README.md" in diverged_paths, "README.md conflict missing from analysis"
    assert "docs/history/STATUS.md" in diverged_paths, "docs/history/STATUS.md missing from analysis"

    for df in diverged:
        assert df.get("resolution_strategy"), f"Missing resolution strategy for {df['path']}"

    protocol = conflict_data.get("w_a13_merge_protocol", [])
    assert len(protocol) >= 4, "W-A13 merge protocol incomplete"


def test_active_pr_branches_strictly_keep_active() -> None:
    data = json.loads(JSON_PATH.read_text(encoding="utf-8"))
    branches = data["section_2_remote_branches_inventory"]["remote_branches"]
    bmap = {b["branch"]: b for b in branches}

    active_named_branches = [
        "origin/argon/419-windows-clean-clone-baseline",
        "origin/argon/421-physical-prediction-blind-curve",
        "origin/argon/422-non-person-track-o3",
        "origin/argon/424-colab-oneclick-notebook",
        "origin/argon/426-q4-tf-eval-tool",
        "origin/argon/427-research-report-figures",
        "origin/argon/430-cleanup-inventory-candidates",
        "origin/claude/core-search-track-contract",
        "origin/claude/demo-all-events",
        "origin/claude/l2-3-long-timeline",
        "origin/claude/project-docs-pack",
        "origin/codex/412-review-argon-411",
        "origin/codex/413-review-speed-increment",
        "origin/codex/414-r004-d124-rerender",
        "origin/codex/415-local-build-scripts",
        "origin/codex/416-safe-packs",
        "origin/codex/418-expanded-office-parameters",
        "origin/codex/448-local-cleanup-inventory",
        "origin/codex/d126-core-search-track",
    ]
    for b in active_named_branches:
        assert b in bmap, f"Active branch {b} missing from inventory"
        assert bmap[b]["category"] == "KEEP_ACTIVE", f"Active branch {b} must be KEEP_ACTIVE"

    active_pr_nums = [255, 435, 436, 437, 438, 439, 440, 441, 442, 443, 444, 446, 447, 449, 450]
    for pnum in active_pr_nums:
        ref = f"origin/pr/{pnum}"
        assert ref in bmap, f"Active PR ref {ref} missing from inventory"
        assert bmap[ref]["category"] == "KEEP_ACTIVE", f"Active PR ref {ref} must be KEEP_ACTIVE"
