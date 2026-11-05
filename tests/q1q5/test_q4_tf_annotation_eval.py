"""Tests for Issue #426 (W-A8 Q4 formal T/F human annotation pack builder and return scorer)."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import struct
import sys
import zlib

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from build_q4_tf_annotation_pack import (  # noqa: E402
    DEFAULT_ANNOTATION_SEMANTICS,
    PACK_KIND,
    PACK_SCHEMA_VERSION,
    TEMPLATE_KIND,
    TEMPLATE_REL_PATH,
    VALID_ANNOTATION_SEMANTICS,
    PackBuildError,
    _png_chunk,
    build_q4_tf_annotation_pack,
    generate_synthetic_samples,
    main as build_main,
    make_synthetic_png,
    validate_png_bytes,
    verify_handoff_pack,
)
from score_q4_tf_returns import (  # noqa: E402
    AUTO_SEMANTICS,
    REPORT_SCHEMA_VERSION,
    ReturnScoreError,
    adapt_human_judgment,
    adapt_q4_tf_manifest_for_score_reviews,
    export_return_to_q4_tf_reviews,
    import_q4_tf_reviews_to_return,
    main as score_main,
    normalize_return_document,
    score_q4_tf_returns,
)
from amidst.evaluation.q4_presence_eval import canonical, score_reviews, sha


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
    assert receipt_a["annotation_semantics"] == DEFAULT_ANNOTATION_SEMANTICS
    assert receipt_a["sample_count"] == 6
    assert receipt_a["manifest_sha256"] == receipt_b["manifest_sha256"]
    assert receipt_a["template_sha256"] == receipt_b["template_sha256"]
    for sample in generate_synthetic_samples(seed="unit-seed-1", count=6):
        assert (pack_dir_a / "frames" / f"{sample['sample_id']}.png").read_bytes() == sample["frame_bytes"]

    # Verify strict blind pack: no claims or system judgments inside pack_dir
    assert not (pack_dir_a / "claims").exists()
    assert not (pack_dir_b / "claims").exists()

    # System claims are written separately outside pack_dir
    eval_claims_file = Path(receipt_a["system_judgments_file"])
    assert eval_claims_file.is_file()
    assert not eval_claims_file.is_relative_to(pack_dir_a)
    eval_claims_doc = json.loads(eval_claims_file.read_text(encoding="utf-8"))
    assert eval_claims_doc["pack_manifest_sha256"] == receipt_a["manifest_sha256"]
    assert eval_claims_doc["sample_set_sha256"] == receipt_a["sample_set_sha256"]
    assert len(eval_claims_doc["judgments"]) == 6

    readme_text = (pack_dir_a / "README.md").read_text(encoding="utf-8")
    for section in ("## 工作內容", "## 要提交項目", "## 操作步驟", "## RETURN/ 繳交規範"):
        assert section in readme_text

    template_path = pack_dir_a / TEMPLATE_REL_PATH
    assert template_path.is_file()
    template = json.loads(template_path.read_text(encoding="utf-8"))
    assert template["schema_version"] == PACK_SCHEMA_VERSION
    assert template["template_kind"] == TEMPLATE_KIND
    assert template["annotation_semantics"] == DEFAULT_ANNOTATION_SEMANTICS
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
    assert report["evaluation_semantics"] == "TARGET_PRESENCE"
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
    assert iaa["kappa_status"] == "MEASURED"
    assert len(iaa["pairs"]) == 3

    assert report["provenance"]["gt_read"] is False
    assert report["provenance"]["pack_manifest_sha256"] == build_receipt["manifest_sha256"]
    assert report["provenance"]["system_judgments_file"] == build_receipt["system_judgments_file"]
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
    with pytest.raises(ReturnScoreError, match="PACK_VERIFICATION_FAILED|PACK_FILE_SHA256_MISMATCH"):
        score_q4_tf_returns(pack_dir)


def test_blind_pack_strict_separation_and_manifest_binding(tmp_path: Path) -> None:
    pack_dir = tmp_path / "blind_pack"
    receipt = build_q4_tf_annotation_pack(pack_dir, synthetic=True, seed="blind-seed", sample_count=4)

    # 1. Blind pack directory contains NO claims or system judgments
    assert not (pack_dir / "claims").exists()
    manifest = json.loads((pack_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    assert not any("claims" in rel_p.lower() for rel_p in manifest["files"])
    for s in manifest["samples"]:
        assert "system_judgment" not in s
        assert "prediction_sha256" not in s

    # 2. Scorer rejects if claims directory is illegally placed into pack
    (pack_dir / "claims").mkdir(parents=True, exist_ok=True)
    with pytest.raises(ReturnScoreError, match="PACK_NOT_BLIND:CLAIMS_DIR_FOUND"):
        score_q4_tf_returns(pack_dir)
    (pack_dir / "claims").rmdir()

    # 3. Scorer rejects if evaluation claims file has mismatched pack_manifest_sha256
    valid_map = {f"Q4_S{i:04d}": "T" for i in range(1, 5)}
    _fill_return_from_template(pack_dir, annotator_id="eve", judgments_by_sample_id=valid_map)

    eval_file = Path(receipt["system_judgments_file"])
    eval_doc = json.loads(eval_file.read_text(encoding="utf-8"))
    eval_doc["pack_manifest_sha256"] = "f" * 64
    tampered_eval_file = tmp_path / "tampered_eval.json"
    tampered_eval_file.write_text(json.dumps(eval_doc), encoding="utf-8")

    with pytest.raises(ReturnScoreError, match="SYSTEM_JUDGMENTS_MANIFEST_SHA_MISMATCH"):
        score_q4_tf_returns(pack_dir, system_judgments_path=tampered_eval_file)


def test_strict_png_validation() -> None:
    # 1. Valid synthetic PNG passes
    valid_png = make_synthetic_png("test-valid-png")
    meta = validate_png_bytes(valid_png, "test.png")
    assert meta["width"] == 2 and meta["height"] == 2

    # 2. PNG signature + non-image bytes is rejected
    fake_png = b"\x89PNG\r\n\x1a\nnot-an-image-payload-0000"
    with pytest.raises(PackBuildError, match="PNG_CHUNK_DISALLOWED|PNG_CHUNK_DATA_TRUNCATED|INVALID_PNG_HEADER"):
        validate_png_bytes(fake_png, "fake.png")

    # 3. Trailing garbage after IEND is rejected
    trailing_png = valid_png + b"GARBAGE_AFTER_IEND"
    with pytest.raises(PackBuildError, match="PNG_TRAILING_GARBAGE_AFTER_IEND"):
        validate_png_bytes(trailing_png, "trailing.png")

    # 4. Disallowed text metadata chunk (tEXt) is rejected
    text_data = b"Comment\x00synthetic-leak"
    text_chunk = _png_chunk(b"tEXt", text_data)
    # Inject tEXt chunk before IEND
    iend_idx = valid_png.rfind(b"IEND") - 4
    with_text = valid_png[:iend_idx] + text_chunk + valid_png[iend_idx:]
    with pytest.raises(PackBuildError, match="PNG_CHUNK_DISALLOWED"):
        validate_png_bytes(with_text, "text_meta.png")

    # 5. Corrupted CRC is rejected
    corrupted_crc = bytearray(valid_png)
    corrupted_crc[-1] ^= 0xFF
    with pytest.raises(PackBuildError, match="PNG_CRC_INVALID"):
        validate_png_bytes(bytes(corrupted_crc), "bad_crc.png")

    # 6. Corrupted IDAT stream is rejected
    idat_idx = valid_png.find(b"IDAT")
    corrupted_idat = bytearray(valid_png)
    corrupted_idat[idat_idx + 6] ^= 0x55
    # Recalculate CRC for modified IDAT data to isolate decompression failure
    idat_len = struct.unpack(">I", corrupted_idat[idat_idx - 4 : idat_idx])[0]
    new_data = corrupted_idat[idat_idx + 4 : idat_idx + 4 + idat_len]
    new_crc = zlib.crc32(b"IDAT" + new_data) & 0xFFFFFFFF
    corrupted_idat[idat_idx + 4 + idat_len : idat_idx + 8 + idat_len] = struct.pack(">I", new_crc)
    with pytest.raises(PackBuildError, match="PNG_DECOMPRESSION_FAILED"):
        validate_png_bytes(bytes(corrupted_idat), "bad_idat.png")


@pytest.mark.parametrize(
    ("case", "expected_error"),
    [
        ("adam7_empty", "PNG_INVALID_IHDR_PARAMETERS"),
        ("palette_without_plte", "PNG_UNSUPPORTED_COLOR_TYPE"),
        ("phys_canary_invalid_size", "PNG_CHUNK_DISALLOWED"),
    ],
)
def test_unsupported_png_structures_fail_before_pack_creation(
    tmp_path: Path, case: str, expected_error: str,
) -> None:
    color_type = 3 if case == "palette_without_plte" else 2
    interlace = 1 if case == "adam7_empty" else 0
    pixels = b"" if interlace else (b"\x00\x00" if color_type == 3 else b"\x00\x00\x00\x00")
    extra = _png_chunk(b"pHYs", b"D128_CANARY") if case == "phys_canary_invalid_size" else b""
    invalid_png = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, color_type, 0, 0, interlace))
        + extra
        + _png_chunk(b"IDAT", zlib.compress(pixels))
        + _png_chunk(b"IEND", b"")
    )
    with pytest.raises(PackBuildError, match=expected_error):
        validate_png_bytes(invalid_png, f"{case}.png")

    samples = generate_synthetic_samples(seed="unsupported-png", count=3)
    samples[0]["frame_bytes"] = invalid_png
    samples[0].pop("frame_sha256")
    pack_dir = tmp_path / case
    with pytest.raises(PackBuildError, match=expected_error):
        build_q4_tf_annotation_pack(pack_dir, samples=samples, seed="unsupported-png")
    assert not pack_dir.exists()


def test_cohens_kappa_zero_variance_degenerate_handling(tmp_path: Path) -> None:
    """When all annotators choose the exact same category, Cohen's kappa denominator is 0.

    Must gracefully return None/null and kappa_status: DEGENERATE instead of ZeroDivisionError,
    while preserving observed agreement = 1.0.
    """
    pack_dir = tmp_path / "degenerate_pack"
    build_receipt = build_q4_tf_annotation_pack(pack_dir, synthetic=True, seed="degen-seed", sample_count=4)

    # Both Alice and Bob annotate "T" for every single sample (zero variance across categories)
    all_t = {f"Q4_S{i:04d}": "T" for i in range(1, 5)}
    _fill_return_from_template(pack_dir, annotator_id="alice", judgments_by_sample_id=all_t)
    _fill_return_from_template(pack_dir, annotator_id="bob", judgments_by_sample_id=all_t)

    report = score_q4_tf_returns(pack_dir)
    iaa = report["inter_annotator_agreement"]

    assert iaa["status"] == "MEASURED"
    assert iaa["exact_match_count"] == 4
    assert iaa["exact_match_rate"] == 1.0
    assert iaa["pairwise_agreement"] == 1.0
    assert iaa["cohens_kappa"] is None
    assert iaa["kappa_status"] == "DEGENERATE"
    assert iaa["valid_kappa_pairs"] == 0
    assert iaa["degenerate_kappa_pairs"] == 1

    pair = iaa["pairs"][0]
    assert pair["observed_agreement"] == 1.0
    assert pair["expected_agreement"] == 1.0
    assert pair["cohens_kappa"] is None
    assert pair["kappa_status"] == "DEGENERATE"
    assert pair["degenerate_reason"] == "ZERO_VARIANCE_ALL_SAME_CATEGORY"

    # Add a third annotator with variance; IAA handles partially degenerate pairs gracefully
    varied = {"Q4_S0001": "T", "Q4_S0002": "F", "Q4_S0003": "T", "Q4_S0004": "F"}
    _fill_return_from_template(pack_dir, annotator_id="carol", judgments_by_sample_id=varied)

    report_3 = score_q4_tf_returns(pack_dir)
    iaa_3 = report_3["inter_annotator_agreement"]
    assert iaa_3["status"] == "MEASURED"
    assert iaa_3["annotator_count"] == 3
    # Pairs: (alice, bob)=degenerate, (alice, carol)=defined, (bob, carol)=defined
    assert iaa_3["kappa_status"] == "PARTIALLY_DEGENERATE"
    assert iaa_3["valid_kappa_pairs"] == 2
    assert iaa_3["degenerate_kappa_pairs"] == 1
    assert iaa_3["cohens_kappa"] is not None


def test_semantics_presence_vs_claim_veracity_counterexample(tmp_path: Path) -> None:
    """Demonstrate the exact counterexample required by Codex review:

    System statement is 'ABSENT' (system claims target is not present).
    Reviewer answers 'T'.

    - Under TARGET_PRESENCE semantics:
      Reviewer means target is PRESENT -> Human Presence = PRESENT, System = ABSENT -> FN.
    - Under CLAIM_VERACITY semantics (Q4_PRESENCE_EVAL_V1.md):
      Reviewer means system statement (ABSENT) is TRUE -> Human Presence = ABSENT, System = ABSENT -> TN!
    """
    assert adapt_human_judgment("T", system_judgment="ABSENT", semantics="TARGET_PRESENCE") == "PRESENT"
    assert adapt_human_judgment("T", system_judgment="ABSENT", semantics="CLAIM_VERACITY") == "ABSENT"

    samples = generate_synthetic_samples(seed="semantics-seed", count=4)
    # Set all system judgments to ABSENT
    for s in samples:
        s["system_judgment"] = "ABSENT"

    pack_dir = tmp_path / "semantics_pack"
    build_q4_tf_annotation_pack(pack_dir, samples=samples, seed="semantics-seed")

    # Reviewer answers 'T' to all samples
    all_t = {f"Q4_S{i:04d}": "T" for i in range(1, 5)}
    _fill_return_from_template(pack_dir, annotator_id="reviewer", judgments_by_sample_id=all_t)

    # 1. Scored with TARGET_PRESENCE: all 4 are FN
    report_presence = score_q4_tf_returns(pack_dir, semantics="TARGET_PRESENCE")
    assert report_presence["evaluation_semantics"] == "TARGET_PRESENCE"
    assert report_presence["confusion"] == {"TP": 0, "FP": 0, "TN": 0, "FN": 4}

    # 2. Scored with CLAIM_VERACITY: all 4 are TN
    report_veracity = score_q4_tf_returns(pack_dir, semantics="CLAIM_VERACITY")
    assert report_veracity["evaluation_semantics"] == "CLAIM_VERACITY"
    assert report_veracity["confusion"] == {"TP": 0, "FP": 0, "TN": 4, "FN": 0}



def test_pack_and_return_explicit_semantic_binding(tmp_path: Path) -> None:
    """Verify that pack, template, eval_claims, and returns explicitly bind semantics."""
    pack_dir = tmp_path / "presence_pack"
    receipt = build_q4_tf_annotation_pack(
        pack_dir,
        synthetic=True,
        seed="sem-bind-1",
        sample_count=4,
        annotation_semantics="TARGET_PRESENCE",
    )
    assert receipt["annotation_semantics"] == "TARGET_PRESENCE"

    manifest = json.loads((pack_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["annotation_semantics"] == "TARGET_PRESENCE"

    template = json.loads((pack_dir / TEMPLATE_REL_PATH).read_text(encoding="utf-8"))
    assert template["annotation_semantics"] == "TARGET_PRESENCE"

    eval_claims = json.loads(Path(receipt["system_judgments_file"]).read_text(encoding="utf-8"))
    assert eval_claims["annotation_semantics"] == "TARGET_PRESENCE"

    # Fill return; it inherits TARGET_PRESENCE
    judgments = {"Q4_S0001": "T", "Q4_S0002": "F", "Q4_S0003": "T", "Q4_S0004": "UNKNOWN"}
    _fill_return_from_template(pack_dir, annotator_id="alice", judgments_by_sample_id=judgments)

    report = score_q4_tf_returns(pack_dir, semantics="AUTO")
    assert report["evaluation_semantics"] == "TARGET_PRESENCE"
    assert report["declared_annotation_semantics"] == "TARGET_PRESENCE"
    assert report["semantics_adaptation"] == "PASSTHROUGH"
    assert report["counts"]["reviewed"] == 4
    assert report["metrics"]["accuracy"] == report["accuracy"]

    # Unsupported semantics is rejected during pack build
    with pytest.raises(PackBuildError, match="UNSUPPORTED_ANNOTATION_SEMANTICS"):
        build_q4_tf_annotation_pack(
            tmp_path / "bad_sem_pack",
            synthetic=True,
            annotation_semantics="BOGUS_SEMANTICS",
        )


def test_q4_tf_adapter_compatibility_with_issue_147_evaluator(tmp_path: Path) -> None:
    """Verify mathematical equivalence between W-A8 scorer and #123/#147 score_reviews via adapter."""
    pack_dir = tmp_path / "adapter_pack"
    samples = generate_synthetic_samples(seed="adapter-seed-1", count=8)
    # Ensure mixed PRESENT and ABSENT system judgments
    for idx, s in enumerate(samples):
        s["system_judgment"] = "PRESENT" if idx % 2 == 0 else "ABSENT"

    receipt = build_q4_tf_annotation_pack(
        pack_dir,
        samples=samples,
        seed="adapter-seed-1",
        annotation_semantics="TARGET_PRESENCE",
    )

    # Annotator answers: 4 'T', 3 'F', 1 'UNKNOWN'
    judgments = {
        "Q4_S0001": "T",
        "Q4_S0002": "T",
        "Q4_S0003": "F",
        "Q4_S0004": "F",
        "Q4_S0005": "T",
        "Q4_S0006": "F",
        "Q4_S0007": "T",
        "Q4_S0008": "UNKNOWN",
    }
    return_path = _fill_return_from_template(pack_dir, annotator_id="rater_w_a8", judgments_by_sample_id=judgments)

    # 1. Score with W-A8 scorer (AUTO resolves to TARGET_PRESENCE)
    report_w_a8 = score_q4_tf_returns(pack_dir, semantics="AUTO")

    # 2. Adapt return and manifest to #147 format and score with amidst.evaluation.q4_presence_eval.score_reviews
    return_doc = json.loads(return_path.read_text(encoding="utf-8"))
    manifest = json.loads((pack_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    eval_claims = json.loads(Path(receipt["system_judgments_file"]).read_text(encoding="utf-8"))

    adapted_reviews = export_return_to_q4_tf_reviews(
        return_doc,
        manifest,
        eval_claims,
        target_semantics="CLAIM_VERACITY",
    )
    adapted_manifest = adapt_q4_tf_manifest_for_score_reviews(manifest, eval_claims)

    reviews_raw = b"\n".join(canonical(r) for r in adapted_reviews) + b"\n"
    manifest_raw = canonical(adapted_manifest)
    reviews_sha = sha(reviews_raw)
    manifest_sha = sha(manifest_raw)

    report_147 = score_reviews(
        adapted_reviews,
        adapted_manifest,
        reviews_sha256=reviews_sha,
        manifest_sha256=manifest_sha,
    )

    # Verify 100% equivalence on confusion matrix and metrics
    assert report_147["confusion"] == report_w_a8["confusion"]
    assert report_147["accuracy"]["value"] == report_w_a8["accuracy"]
    assert report_147["precision"]["value"] == report_w_a8["precision"]
    assert report_147["recall"]["value"] == report_w_a8["recall"]
    assert report_147["excluded"]["uncertain"] == report_w_a8["counts"]["uncertain_excluded"]


def test_import_q4_tf_reviews_to_return(tmp_path: Path) -> None:
    """Verify bidirectional adapter: #147 reviews rows -> W-A8 return document."""
    pack_dir = tmp_path / "import_pack"
    receipt = build_q4_tf_annotation_pack(pack_dir, synthetic=True, seed="import-seed-1", sample_count=6)
    manifest = json.loads((pack_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    eval_claims = json.loads(Path(receipt["system_judgments_file"]).read_text(encoding="utf-8"))

    # Create dummy #147 review rows
    sys_by_id = {j["sample_id"]: j for j in eval_claims["judgments"]}
    review_rows = []
    for s in manifest["samples"]:
        sid = s["sample_id"]
        pos = (sys_by_id[sid]["system_judgment"] == "PRESENT")
        review_rows.append(
            {
                "schema_version": "q4-tf-review.v1",
                "sample_id": sid,
                "run_id": s["run_id"],
                "camera_id": s["camera_id"],
                "frame_index": s["frame_index"],
                "rgb_file_sha256": s["frame_sha256"],
                "prediction_sha256": sys_by_id[sid]["prediction_sha256"],
                "system_positive": pos,
                "frame_ref": f"frame:{s['run_id']}:{s['camera_id']}:{s['frame_index']}",
                "pilot": False,
                "evaluation_eligible": True,
                "statement": s["statement"],
                "answer": "T",
            }
        )

    imported_return = import_q4_tf_reviews_to_return(
        review_rows,
        manifest,
        annotator_id="imported_agent",
        target_semantics="TARGET_PRESENCE",
    )
    assert imported_return["schema_version"] == PACK_SCHEMA_VERSION
    assert imported_return["template_kind"] == TEMPLATE_KIND
    assert imported_return["annotation_semantics"] == "TARGET_PRESENCE"
    assert len(imported_return["answers"]) == 6

    # Write as return and score
    out_file = pack_dir / "RETURN" / "q4_tf_answers_imported_agent.json"
    out_file.write_text(json.dumps(imported_return, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = score_q4_tf_returns(pack_dir, semantics="AUTO")
    assert report["status"] == "SCORED"
    assert "imported_agent" in report["annotators"]


def test_conflicting_return_semantics_fail_closed(tmp_path: Path) -> None:
    """When multiple raters submit returns with conflicting semantics under AUTO, score fails closed."""
    pack_dir = tmp_path / "conflict_pack"
    build_q4_tf_annotation_pack(pack_dir, synthetic=True, seed="conflict-seed", sample_count=4)

    all_t = {f"Q4_S{i:04d}": "T" for i in range(1, 5)}
    p_alice = _fill_return_from_template(pack_dir, annotator_id="alice", judgments_by_sample_id=all_t)
    p_bob = _fill_return_from_template(pack_dir, annotator_id="bob", judgments_by_sample_id=all_t)

    # Bob's return declares CLAIM_VERACITY while Alice declares TARGET_PRESENCE
    bob_doc = json.loads(p_bob.read_text(encoding="utf-8"))
    bob_doc["annotation_semantics"] = "CLAIM_VERACITY"
    p_bob.write_text(json.dumps(bob_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ReturnScoreError, match="RETURN_MANIFEST_SEMANTICS_MISMATCH|CONFLICTING_RETURN_SEMANTICS"):
        score_q4_tf_returns(pack_dir, semantics="AUTO")


def test_unsupported_return_semantics_rejected(tmp_path: Path) -> None:
    """A return with an unsupported semantics value is rejected fail-closed."""
    pack_dir = tmp_path / "unsupported_sem_pack"
    build_q4_tf_annotation_pack(pack_dir, synthetic=True, seed="unsupported-seed", sample_count=4)

    all_t = {f"Q4_S{i:04d}": "T" for i in range(1, 5)}
    p_alice = _fill_return_from_template(pack_dir, annotator_id="alice", judgments_by_sample_id=all_t)
    alice_doc = json.loads(p_alice.read_text(encoding="utf-8"))
    alice_doc["annotation_semantics"] = "INVENTED_BOGUS_SEMANTICS"
    p_alice.write_text(json.dumps(alice_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with pytest.raises(ReturnScoreError, match="UNSUPPORTED_RETURN_SEMANTICS"):
        score_q4_tf_returns(pack_dir, semantics="AUTO")
