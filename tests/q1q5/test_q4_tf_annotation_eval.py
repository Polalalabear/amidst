"""Tests for Issue #426 (W-A8 Q4 formal T/F human annotation pack builder and return scorer)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_q4_tf_annotation_pack import (  # noqa: E402
    PACK_KIND,
    PACK_SCHEMA_VERSION,
    TEMPLATE_KIND,
    TEMPLATE_REL_PATH,
    PackBuildError,
    build_q4_tf_annotation_pack,
    generate_synthetic_samples,
    main as build_main,
    verify_handoff_pack,
)
from score_q4_tf_returns import (  # noqa: E402
    REPORT_SCHEMA_VERSION,
    ReturnScoreError,
    main as score_main,
    score_q4_tf_returns,
)


def _fill_return_from_template(
    pack_dir: Path,
    *,
    annotator_id: str,
    judgments_by_sample_id: dict[str, str],
) -> Path:
    template_path = pack_dir / TEMPLATE_REL_PATH
    doc = json.loads(template_path.read_text(encoding="utf-8"))
    doc["annotator_id"] = annotator_id
    doc["completed_at"] = "2026-11-04T12:00:00+08:00"
    for ans in doc["answers"]:
        sid = ans["sample_id"]
        ans["human_judgment"] = judgments_by_sample_id[sid]
        ans["notes"] = f"annotated by {annotator_id}"
    out_path = pack_dir / "RETURN" / f"q4_tf_answers_{annotator_id}.json"
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out_path


def test_handoff_template_doc_has_required_sections_and_unknown_wc5_status() -> None:
    doc_path = REPO_ROOT / "docs" / "agents" / "team-handoff" / "q4-tf-pack-v1" / "README.md"
    assert doc_path.is_file()
    content = doc_path.read_text(encoding="utf-8")
    assert "## 工作內容" in content
    assert "## 要提交項目" in content
    assert "## 操作步驟" in content
    assert "## RETURN/ 繳交規範" in content
    assert "UNKNOWN" in content
    assert "#416" in content


def test_build_synthetic_q4_tf_pack_and_template_structure(tmp_path: Path) -> None:
    pack_dir_a = tmp_path / "pack_a"
    pack_dir_b = tmp_path / "pack_b"

    receipt_a = build_q4_tf_annotation_pack(pack_dir_a, synthetic=True, seed="unit-seed-1", sample_count=6)
    receipt_b = build_q4_tf_annotation_pack(pack_dir_b, synthetic=True, seed="unit-seed-1", sample_count=6)

    assert receipt_a["status"] == "READY"
    assert receipt_a["schema_version"] == PACK_SCHEMA_VERSION
    assert receipt_a["pack_kind"] == PACK_KIND
    assert receipt_a["source_mode"] == "SYNTHETIC"
    assert receipt_a["real_pack_status"] == "SYNTHETIC_ONLY"
    assert receipt_a["evaluation_eligible"] is False
    assert receipt_a["gt_read"] is False
    assert receipt_a["sample_count"] == 6
    assert receipt_a["manifest_sha256"] == receipt_b["manifest_sha256"]
    assert receipt_a["template_sha256"] == receipt_b["template_sha256"]

    readme_text = (pack_dir_a / "README.md").read_text(encoding="utf-8")
    for section in ("## 工作內容", "## 要提交項目", "## 操作步驟", "## RETURN/ 繳交規範"):
        assert section in readme_text

    template_path = pack_dir_a / TEMPLATE_REL_PATH
    assert template_path.is_file()
    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert template["schema_version"] == PACK_SCHEMA_VERSION
    assert template["template_kind"] == TEMPLATE_KIND
    assert template["allowed_judgments"] == ["T", "F", "UNKNOWN"]
    assert len(template["answers"]) == 6
    for row in template["answers"]:
        assert row["human_judgment"] == ""
        assert "system_judgment" not in row
        assert (pack_dir_a / row["frame_file"]).is_file()

    verified = verify_handoff_pack(pack_dir_a, expected_manifest_sha256=receipt_a["manifest_sha256"])
    assert verified["status"] == "VALID"


@pytest.mark.parametrize(
    "bad_field,bad_value",
    [
        ("gt_private", "gt_private/track.json"),
        ("visibility", 0.95),
        ("depth", [1.2, 3.4]),
        ("renderer_trajectory", [{"x": 0, "y": 1}]),
        ("ground_truth_label", "PRESENT"),
    ],
)
def test_builder_rejects_gt_and_forbidden_fields_in_samples(
    tmp_path: Path,
    bad_field: str,
    bad_value: object,
) -> None:
    samples = generate_synthetic_samples(seed="forbid-seed", count=4)
    samples[0][bad_field] = bad_value
    with pytest.raises(PackBuildError):
        build_q4_tf_annotation_pack(tmp_path / "bad_pack", samples=samples)


def test_builder_rejects_forbidden_files_in_safe_pack_dir(tmp_path: Path) -> None:
    safe_dir = tmp_path / "unsafe_wc5"
    (safe_dir / "gt_private").mkdir(parents=True)
    (safe_dir / "gt_private" / "secret.json").write_text("{}", encoding="utf-8")

    with pytest.raises(PackBuildError):
        build_q4_tf_annotation_pack(tmp_path / "out_pack", safe_pack_dir=safe_dir)


def test_safe_pack_mode_reports_unknown_when_wc5_data_absent(tmp_path: Path) -> None:
    missing_wc5 = tmp_path / "nonexistent_wc5_pack"
    out_dir = tmp_path / "wc5_out"
    receipt_file = tmp_path / "wc5_receipt.json"

    exit_code = build_main(
        [
            "--safe-pack-dir",
            str(missing_wc5),
            "--output-dir",
            str(out_dir),
            "--receipt",
            str(receipt_file),
        ]
    )
    assert exit_code == 0
    receipt = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert receipt["status"] == "UNKNOWN"
    assert receipt["real_pack_status"] == "UNKNOWN"
    assert receipt["source_mode"] == "SAFE_PACK"
    assert receipt["evaluation_eligible"] is False
    assert receipt["gt_read"] is False
    assert (out_dir / "REAL_PACK_STATUS.json").is_file()


def test_score_synthetic_returns_metrics_and_inter_annotator_agreement(tmp_path: Path) -> None:
    # Build deterministic 6-sample pack with known system judgments:
    # S1: PRESENT, S2: ABSENT, S3: PRESENT, S4: ABSENT, S5: UNKNOWN, S6: PRESENT
    samples = generate_synthetic_samples(seed="score-seed", count=6)
    sys_expected = ["PRESENT", "ABSENT", "PRESENT", "ABSENT", "UNKNOWN", "PRESENT"]
    for sample, sys_j in zip(samples, sys_expected):
        sample["system_judgment"] = sys_j

    pack_dir = tmp_path / "score_pack"
    build_receipt = build_q4_tf_annotation_pack(pack_dir, samples=samples, seed="score-seed")

    # Annotator A & Annotator B give high-agreement answers; Annotator C differs on S3 & S6 so
    # consensus (majority across A, B, C) equals Annotator A & B:
    # S1 (sys PRESENT): human T (PRESENT) -> TP
    # S2 (sys ABSENT):  human F (ABSENT)  -> TN
    # S3 (sys PRESENT): human F (ABSENT)  -> FP
    # S4 (sys ABSENT):  human T (PRESENT) -> FN
    # S5 (sys UNKNOWN): human T (PRESENT) -> ABSTAIN_SYSTEM
    # S6 (sys PRESENT): human UNKNOWN     -> ABSTAIN_HUMAN
    ans_a = {
        "Q4_S0001": "T",
        "Q4_S0002": "F",
        "Q4_S0003": "F",
        "Q4_S0004": "T",
        "Q4_S0005": "T",
        "Q4_S0006": "UNKNOWN",
    }
    ans_b = copy.deepcopy(ans_a)
    ans_c = {
        "Q4_S0001": "T",
        "Q4_S0002": "F",
        "Q4_S0003": "T",
        "Q4_S0004": "T",
        "Q4_S0005": "T",
        "Q4_S0006": "T",
    }

    _fill_return_from_template(pack_dir, annotator_id="alice", judgments_by_sample_id=ans_a)
    _fill_return_from_template(pack_dir, annotator_id="bob", judgments_by_sample_id=ans_b)
    _fill_return_from_template(pack_dir, annotator_id="carol", judgments_by_sample_id=ans_c)

    report_out = tmp_path / "score_report.json"
    rc = score_main(
        [
            "--pack-dir",
            str(pack_dir),
            "--manifest-sha256",
            build_receipt["manifest_sha256"],
            "--output",
            str(report_out),
        ]
    )
    assert rc == 0
    report = json.loads(report_out.read_text(encoding="utf-8"))

    assert report["schema_version"] == REPORT_SCHEMA_VERSION
    assert report["status"] == "SCORED"
    assert report["gt_read"] is False
    assert report["sample_count"] == 6
    assert report["annotator_count"] == 3
    assert report["confusion"] == {"TP": 1, "FP": 1, "TN": 1, "FN": 1}
    assert report["decided_count"] == 4
    assert report["accuracy"] == pytest.approx(0.5)
    assert report["precision"] == pytest.approx(0.5)
    assert report["recall"] == pytest.approx(0.5)
    assert report["f1"] == pytest.approx(0.5)

    # S5 has system UNKNOWN and S6 has consensus human UNKNOWN -> 2 of 6 abstained
    assert report["abstention_count"] == 2
    assert report["abstention_rate"] == pytest.approx(2 / 6)
    assert report["human_unknown_count"] == 1
    assert report["human_abstention_rate"] == pytest.approx(1 / 6)
    assert report["system_unknown_count"] == 1
    assert report["system_abstention_rate"] == pytest.approx(1 / 6)

    iaa = report["inter_annotator_agreement"]
    assert iaa["status"] == "MEASURED"
    assert iaa["annotator_count"] == 3
    # All 3 annotators agree on 4 of 6 samples (S1, S2, S4, S5)
    assert iaa["exact_match_count"] == 4
    assert iaa["exact_match_rate"] == pytest.approx(4 / 6)
    # Pairwise agreements: (alice, bob)=1.0, (alice, carol)=4/6, (bob, carol)=4/6 -> mean 7/9
    assert iaa["pairwise_agreement"] == pytest.approx((1.0 + 4 / 6 + 4 / 6) / 3)
    assert iaa["cohens_kappa"] > 0.4
    assert len(iaa["pairs"]) == 3

    assert report["provenance"]["gt_read"] is False
    assert report["provenance"]["pack_manifest_sha256"] == build_receipt["manifest_sha256"]
    assert len(report["provenance"]["return_files_sha256"]) == 3
    assert len(report["receipt_sha256"]) == 64


def test_scorer_rejects_tampered_or_incomplete_returns_fail_closed(tmp_path: Path) -> None:
    pack_dir = tmp_path / "tamper_pack"
    build_q4_tf_annotation_pack(pack_dir, synthetic=True, seed="tamper-seed", sample_count=4)

    # 1. No completed return files yet -> fail closed
    with pytest.raises(ReturnScoreError, match="NO_COMPLETED_RETURN_FILES"):
        score_q4_tf_returns(pack_dir)

    valid_map = {f"Q4_S{i:04d}": "T" for i in range(1, 5)}
    ret_path = _fill_return_from_template(pack_dir, annotator_id="dave", judgments_by_sample_id=valid_map)
    base_doc = json.loads(ret_path.read_text(encoding="utf-8"))

    # 2. Incomplete answer (blank human_judgment)
    incomplete_doc = copy.deepcopy(base_doc)
    incomplete_doc["answers"][0]["human_judgment"] = ""
    ret_path.write_text(json.dumps(incomplete_doc), encoding="utf-8")
    with pytest.raises(ReturnScoreError, match="INVALID_OR_INCOMPLETE_HUMAN_JUDGMENT"):
        score_q4_tf_returns(pack_dir)

    # 3. Tampered locked sample field (e.g. frame_sha256 modified)
    tampered_doc = copy.deepcopy(base_doc)
    tampered_doc["answers"][0]["frame_sha256"] = "0" * 64
    ret_path.write_text(json.dumps(tampered_doc), encoding="utf-8")
    with pytest.raises(ReturnScoreError, match="TAMPERED_LOCKED_FIELD"):
        score_q4_tf_returns(pack_dir)

    # 4. Forbidden GT field injected into return JSON
    gt_doc = copy.deepcopy(base_doc)
    gt_doc["gt_private_leak"] = True
    ret_path.write_text(json.dumps(gt_doc), encoding="utf-8")
    with pytest.raises(ReturnScoreError, match="FORBIDDEN_FIELD_KEY|RETURN_CONTENT_REJECTED"):
        score_q4_tf_returns(pack_dir)

    # 5. Tampered immutable pack file (frame PNG modified after build)
    ret_path.write_text(json.dumps(base_doc), encoding="utf-8")
    frame_file = pack_dir / "frames" / "Q4_S0001.png"
    original_bytes = frame_file.read_bytes()
    frame_file.write_bytes(original_bytes + b"\x00")
    with pytest.raises(ReturnScoreError, match="PACK_VERIFICATION_FAILED"):
        score_q4_tf_returns(pack_dir)
