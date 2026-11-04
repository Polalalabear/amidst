#!/usr/bin/env python3
"""Validate and score completed Q4 True/False human annotation returns (#426, W-A8).

Validates `RETURN/*.json` against the pack `MANIFEST.json` and a cryptographically
bound external system judgments file fail-closed, then computes:
- TP / FP / TN / FN, accuracy, precision, recall, F1
- Human, system, and combined abstention (`UNKNOWN`) rates
- Inter-annotator agreement (exact match rate, pairwise agreement, Cohen's kappa)
  with graceful handling of zero-variance / constant marginal degeneracy (avoids ZeroDivisionError)
- Provenance and SHA-256 receipt (`gt_read: false`)

Codex REVISE fixes (#436):
1. Strict blind pack separation: requires system judgments to reside outside the blind pack,
   verifying SHA-256 binding against `pack_manifest_sha256` and `sample_set_sha256`.
2. Cohen's Kappa degeneracy fix: when all raters select the same category, Cohen's kappa
   denominator is 0 (undefined). Gracefully reports `null` / `DEGENERATE` with reason,
   while preserving observed pairwise agreement = 1.0.
3. Semantics support and adapter: supports both `TARGET_PRESENCE` (T=target present, F=absent)
   and `CLAIM_VERACITY` (T=system claim correct, F=claim incorrect, per Q4_PRESENCE_EVAL_V1.md).
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_q4_tf_annotation_pack import (  # noqa: E402
    ALLOWED_HUMAN_JUDGMENTS,
    ALLOWED_SYSTEM_JUDGMENTS,
    PACK_SCHEMA_VERSION,
    SHA256_RE,
    TEMPLATE_KIND,
    TEMPLATE_REL_PATH,
    PackBuildError,
    canonical_json_bytes,
    parse_json_strict,
    pretty_json_bytes,
    scan_bytes_for_forbidden_content,
    scan_object_for_forbidden_fields,
    sha256_bytes,
    validate_png_bytes,
    verify_handoff_pack,
)

REPORT_SCHEMA_VERSION = "q4-presence-eval-report.v1"
REPORT_KIND = "q4-tf-returns-score-v1"
VALID_SEMANTICS = ("TARGET_PRESENCE", "CLAIM_VERACITY")

LOCKED_SAMPLE_FIELDS = (
    "sample_id",
    "run_id",
    "clock_id",
    "camera_id",
    "frame_index",
    "timestamp_us",
    "frame_file",
    "frame_sha256",
    "target_query",
    "statement",
)


class ReturnScoreError(ValueError):
    """Raised when return validation or scoring fails closed."""


def require_score(condition: bool, code: str) -> None:
    if not condition:
        raise ReturnScoreError(code)


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return (numerator / denominator) if denominator > 0 else None


def adapt_human_judgment(
    human_judgment: str,
    *,
    system_judgment: str,
    semantics: str = "TARGET_PRESENCE",
) -> str:
    """Map human T/F/UNKNOWN to effective presence ('PRESENT', 'ABSENT', 'UNKNOWN').

    Under TARGET_PRESENCE semantics:
    - 'T' -> Target is present ('PRESENT')
    - 'F' -> Target is absent ('ABSENT')
    - 'UNKNOWN' -> Unclear / abstained ('UNKNOWN')

    Under CLAIM_VERACITY semantics (Q4_PRESENCE_EVAL_V1.md):
    - System claim is 'PRESENT': 'T' (true) -> 'PRESENT', 'F' (false) -> 'ABSENT'
    - System claim is 'ABSENT':  'T' (true) -> 'ABSENT',  'F' (false) -> 'PRESENT'
    - 'UNKNOWN' -> 'UNKNOWN'
    """
    require_score(human_judgment in ALLOWED_HUMAN_JUDGMENTS, f"INVALID_HUMAN_JUDGMENT:{human_judgment}")
    require_score(system_judgment in ALLOWED_SYSTEM_JUDGMENTS, f"INVALID_SYSTEM_JUDGMENT:{system_judgment}")
    require_score(semantics in VALID_SEMANTICS, f"UNSUPPORTED_SEMANTICS:{semantics}")

    if human_judgment == "UNKNOWN":
        return "UNKNOWN"

    if semantics == "TARGET_PRESENCE":
        if human_judgment == "T":
            return "PRESENT"
        elif human_judgment == "F":
            return "ABSENT"
    elif semantics == "CLAIM_VERACITY":
        if system_judgment == "PRESENT":
            return "PRESENT" if human_judgment == "T" else "ABSENT"
        elif system_judgment == "ABSENT":
            return "ABSENT" if human_judgment == "T" else "PRESENT"
        else:
            return "UNKNOWN"

    return "UNKNOWN"


def _compute_binary_and_abstention_metrics(
    pairs: list[tuple[str, str]],
) -> dict[str, Any]:
    """Compute confusion matrix, P/R/F1/Accuracy, and abstention rates for (human_presence, system_judgment) pairs."""
    total = len(pairs)
    require_score(total > 0, "EMPTY_EVALUATION_PAIRS")

    tp = fp = tn = fn = 0
    human_unknown = 0
    system_unknown = 0
    combined_unknown = 0
    human_present = 0
    human_absent = 0
    system_present = 0
    system_absent = 0

    for human_label, system_label in pairs:
        if human_label == "PRESENT":
            human_present += 1
        elif human_label == "ABSENT":
            human_absent += 1
        else:
            human_unknown += 1

        if system_label == "PRESENT":
            system_present += 1
        elif system_label == "ABSENT":
            system_absent += 1
        else:
            system_unknown += 1

        if human_label == "UNKNOWN" or system_label == "UNKNOWN":
            combined_unknown += 1
            continue

        if human_label == "PRESENT" and system_label == "PRESENT":
            tp += 1
        elif human_label == "ABSENT" and system_label == "PRESENT":
            fp += 1
        elif human_label == "ABSENT" and system_label == "ABSENT":
            tn += 1
        elif human_label == "PRESENT" and system_label == "ABSENT":
            fn += 1

    decided = tp + fp + tn + fn
    accuracy = _safe_ratio(tp + tn, decided)
    precision = _safe_ratio(tp, tp + fp)
    recall = _safe_ratio(tp, tp + fn)
    f1_denom = 2 * tp + fp + fn
    f1 = (2 * tp / f1_denom) if f1_denom > 0 else None

    abstention_rate = _safe_ratio(combined_unknown, total)
    human_abstention_rate = _safe_ratio(human_unknown, total)
    system_abstention_rate = _safe_ratio(system_unknown, total)

    return {
        "sample_count": total,
        "decided_count": decided,
        "confusion": {"TP": tp, "FP": fp, "TN": tn, "FN": fn},
        "TP": tp,
        "FP": fp,
        "TN": tn,
        "FN": fn,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "abstention_count": combined_unknown,
        "abstention_rate": abstention_rate,
        "unknown_rate": abstention_rate,
        "human_counts": {
            "PRESENT": human_present,
            "ABSENT": human_absent,
            "UNKNOWN": human_unknown,
        },
        "system_counts": {
            "PRESENT": system_present,
            "ABSENT": system_absent,
            "UNKNOWN": system_unknown,
        },
        "human_unknown_count": human_unknown,
        "human_abstention_rate": human_abstention_rate,
        "system_unknown_count": system_unknown,
        "system_abstention_rate": system_abstention_rate,
    }


def _compute_cohens_kappa(labels_a: list[str], labels_b: list[str], categories: tuple[str, ...]) -> dict[str, Any]:
    """Compute Cohen's Kappa with graceful handling of zero-variance / constant marginal degeneracy."""
    n = len(labels_a)
    require_score(n == len(labels_b) and n > 0, "KAPPA_LENGTH_MISMATCH")
    agree = sum(1 for a, b in zip(labels_a, labels_b) if a == b)
    p_o = agree / n
    counts_a = Counter(labels_a)
    counts_b = Counter(labels_b)
    p_e = sum((counts_a[c] / n) * (counts_b[c] / n) for c in categories)

    if abs(1.0 - p_e) < 1e-12:
        # Denominator (1 - p_e) is 0 because all ratings fall into the same single category.
        # Kappa is statistically undefined (zero variance). Return null/None and record reason.
        return {
            "observed_agreement": p_o,
            "expected_agreement": p_e,
            "cohens_kappa": None,
            "kappa_status": "DEGENERATE",
            "degenerate_reason": "ZERO_VARIANCE_ALL_SAME_CATEGORY",
            "agree_count": agree,
            "sample_count": n,
        }

    kappa = (p_o - p_e) / (1.0 - p_e)
    return {
        "observed_agreement": p_o,
        "expected_agreement": p_e,
        "cohens_kappa": kappa,
        "kappa_status": "MEASURED",
        "degenerate_reason": None,
        "agree_count": agree,
        "sample_count": n,
    }


def _compute_inter_annotator_agreement(
    annotator_order: list[str],
    sample_ids: list[str],
    by_annotator_answers: dict[str, dict[str, str]],
) -> dict[str, Any]:
    k = len(annotator_order)
    n = len(sample_ids)
    require_score(k >= 1 and n >= 1, "EMPTY_ANNOTATORS_OR_SAMPLES")
    if k == 1:
        return {
            "annotator_count": 1,
            "status": "SINGLE_ANNOTATOR",
            "exact_match_count": n,
            "exact_match_rate": None,
            "pairwise_agreement": None,
            "cohens_kappa": None,
            "kappa_status": "NOT_APPLICABLE",
            "valid_kappa_pairs": 0,
            "degenerate_kappa_pairs": 0,
            "pairs": [],
        }

    exact_matches = 0
    for sid in sample_ids:
        distinct = {by_annotator_answers[ann][sid] for ann in annotator_order}
        if len(distinct) == 1:
            exact_matches += 1
    exact_match_rate = exact_matches / n

    pair_records: list[dict[str, Any]] = []
    for i in range(k):
        for j in range(i + 1, k):
            ann_a = annotator_order[i]
            ann_b = annotator_order[j]
            seq_a = [by_annotator_answers[ann_a][sid] for sid in sample_ids]
            seq_b = [by_annotator_answers[ann_b][sid] for sid in sample_ids]
            stats = _compute_cohens_kappa(seq_a, seq_b, ALLOWED_HUMAN_JUDGMENTS)
            pair_records.append(
                {
                    "annotator_a": ann_a,
                    "annotator_b": ann_b,
                    **stats,
                }
            )

    mean_pairwise = sum(p["observed_agreement"] for p in pair_records) / len(pair_records)

    # Average only defined (non-degenerate) kappa values
    valid_kappas = [p["cohens_kappa"] for p in pair_records if p["cohens_kappa"] is not None]
    if valid_kappas:
        mean_kappa: float | None = sum(valid_kappas) / len(valid_kappas)
        kappa_status = "MEASURED" if len(valid_kappas) == len(pair_records) else "PARTIALLY_DEGENERATE"
    else:
        mean_kappa = None
        kappa_status = "DEGENERATE"

    return {
        "annotator_count": k,
        "status": "MEASURED",
        "exact_match_count": exact_matches,
        "exact_match_rate": exact_match_rate,
        "pairwise_agreement": mean_pairwise,
        "cohens_kappa": mean_kappa,
        "kappa_status": kappa_status,
        "valid_kappa_pairs": len(valid_kappas),
        "degenerate_kappa_pairs": len(pair_records) - len(valid_kappas),
        "pairs": pair_records,
    }


def _consensus_human_judgment(judgments: list[str]) -> str:
    """Majority vote over T/F; ties or majority UNKNOWN resolve to UNKNOWN."""
    counts = Counter(judgments)
    t_count = counts.get("T", 0)
    f_count = counts.get("F", 0)
    u_count = counts.get("UNKNOWN", 0)
    if t_count > f_count and t_count > u_count:
        return "T"
    if f_count > t_count and f_count > u_count:
        return "F"
    return "UNKNOWN"


def _discover_return_files(pack_root: Path, explicit_files: list[Path | str] | None) -> list[Path]:
    if explicit_files is not None:
        resolved = [Path(p).resolve() for p in explicit_files]
        require_score(len(resolved) > 0, "NO_RETURN_FILES")
        return resolved

    return_dir = pack_root / "RETURN"
    require_score(return_dir.is_dir() and not return_dir.is_symlink(), "RETURN_DIR_MISSING")
    template_path = (pack_root / TEMPLATE_REL_PATH).resolve()
    candidates = [
        p.resolve()
        for p in sorted(return_dir.glob("*.json"))
        if p.resolve() != template_path
    ]
    require_score(len(candidates) > 0, "NO_COMPLETED_RETURN_FILES")
    return candidates


def _resolve_system_judgments_file(pack_root: Path, explicit_path: Path | str | None) -> Path:
    if explicit_path is not None:
        p = Path(explicit_path).resolve()
        require_score(p.is_file(), f"SYSTEM_JUDGMENTS_FILE_MISSING:{p}")
        return p

    candidates = [
        pack_root.parent / f"{pack_root.name}.eval_claims.json",
        pack_root.parent / f"{pack_root.name}_eval_claims.json",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand.resolve()

    raise ReturnScoreError(
        f"SYSTEM_JUDGMENTS_FILE_MISSING: checked {[str(c) for c in candidates]}"
    )


def score_q4_tf_returns(
    pack_dir: Path | str,
    *,
    system_judgments_path: Path | str | None = None,
    return_files: list[Path | str] | None = None,
    expected_manifest_sha256: str | None = None,
    semantics: str = "TARGET_PRESENCE",
) -> dict[str, Any]:
    """Validate and score completed Q4 T/F return JSON files fail-closed."""
    require_score(semantics in VALID_SEMANTICS, f"UNSUPPORTED_SEMANTICS:{semantics}")
    pack_root = Path(pack_dir).resolve()

    # Enforce strict blind pack isolation: claims cannot reside in the annotator pack
    require_score(not (pack_root / "claims").exists(), "PACK_NOT_BLIND:CLAIMS_DIR_FOUND")

    try:
        verified = verify_handoff_pack(pack_root, expected_manifest_sha256=expected_manifest_sha256)
    except PackBuildError as exc:
        raise ReturnScoreError(f"PACK_VERIFICATION_FAILED:{exc}") from exc

    manifest = verified["manifest"]
    manifest_sha256 = verified["manifest_sha256"]

    # Verify each frame file is a strictly valid PNG
    manifest_files = manifest.get("files", {})
    for rel_path in manifest_files:
        if rel_path.endswith(".png"):
            frame_bytes = (pack_root / rel_path).read_bytes()
            try:
                validate_png_bytes(frame_bytes, rel_path)
            except PackBuildError as exc:
                raise ReturnScoreError(f"FRAME_PNG_INVALID:{rel_path}:{exc}") from exc

    # Load and verify separate external system judgments file
    sys_file = _resolve_system_judgments_file(pack_root, system_judgments_path)
    require_score(not sys_file.is_relative_to(pack_root), "SYSTEM_CLAIMS_CANNOT_BE_INSIDE_BLIND_PACK")

    sys_raw = sys_file.read_bytes()
    sys_file_sha = sha256_bytes(sys_raw)

    try:
        scan_bytes_for_forbidden_content(sys_raw, sys_file.name)
        sys_doc = parse_json_strict(sys_raw)
        scan_object_for_forbidden_fields(sys_doc, sys_file.name)
    except PackBuildError as exc:
        raise ReturnScoreError(f"SYSTEM_JUDGMENTS_INVALID:{exc}") from exc

    require_score(
        isinstance(sys_doc, dict)
        and sys_doc.get("gt_read") is False,
        "SYSTEM_JUDGMENTS_GT_READ_FALSE_REQUIRED",
    )
    require_score(
        sys_doc.get("sample_set_sha256") == manifest.get("sample_set_sha256"),
        "SYSTEM_JUDGMENTS_SAMPLE_SET_SHA_MISMATCH",
    )
    require_score(
        sys_doc.get("pack_manifest_sha256") == manifest_sha256,
        "SYSTEM_JUDGMENTS_MANIFEST_SHA_MISMATCH",
    )

    manifest_samples = manifest.get("samples")
    require_score(isinstance(manifest_samples, list) and len(manifest_samples) > 0, "MANIFEST_SAMPLES_EMPTY")
    sample_by_id: dict[str, dict[str, Any]] = {}
    sample_ids_ordered: list[str] = []
    for sample in manifest_samples:
        sid = sample["sample_id"]
        sample_by_id[sid] = sample
        sample_ids_ordered.append(sid)

    sys_judgments_list = sys_doc.get("judgments")
    require_score(
        isinstance(sys_judgments_list, list) and len(sys_judgments_list) == len(sample_ids_ordered),
        "SYSTEM_JUDGMENTS_COUNT_MISMATCH",
    )
    system_by_id: dict[str, dict[str, Any]] = {}
    for row in sys_judgments_list:
        require_score(isinstance(row, dict), "SYSTEM_JUDGMENT_ROW_INVALID")
        sid = row.get("sample_id")
        require_score(
            isinstance(sid, str) and sid in sample_by_id and sid not in system_by_id,
            f"SYSTEM_JUDGMENT_SAMPLE_ID_INVALID:{sid}",
        )
        judgment = row.get("system_judgment")
        require_score(judgment in ALLOWED_SYSTEM_JUDGMENTS, f"SYSTEM_JUDGMENT_VALUE_INVALID:{sid}")
        require_score(
            row.get("frame_sha256") == sample_by_id[sid]["frame_sha256"],
            f"SYSTEM_JUDGMENT_FRAME_SHA_MISMATCH:{sid}",
        )
        system_by_id[sid] = row

    discovered_files = _discover_return_files(pack_root, return_files)

    by_annotator_answers: dict[str, dict[str, str]] = {}
    by_annotator_metrics: dict[str, dict[str, Any]] = {}
    return_files_sha256: dict[str, str] = {}
    annotator_order: list[str] = []

    for ret_path in discovered_files:
        require_score(ret_path.is_file() and not ret_path.is_symlink(), f"RETURN_FILE_INVALID:{ret_path}")
        raw = ret_path.read_bytes()
        rel_key = (
            ret_path.relative_to(pack_root).as_posix()
            if ret_path.is_relative_to(pack_root)
            else ret_path.name
        )
        try:
            scan_bytes_for_forbidden_content(raw, f"RETURN/{ret_path.name}")
            doc = parse_json_strict(raw)
            scan_object_for_forbidden_fields(doc, rel_key)
        except PackBuildError as exc:
            raise ReturnScoreError(f"RETURN_CONTENT_REJECTED:{rel_key}:{exc}") from exc

        require_score(isinstance(doc, dict), f"RETURN_NOT_OBJECT:{rel_key}")
        require_score(
            doc.get("schema_version") == PACK_SCHEMA_VERSION and doc.get("template_kind") == TEMPLATE_KIND,
            f"RETURN_SCHEMA_MISMATCH:{rel_key}",
        )
        require_score(doc.get("pack_id") == manifest.get("pack_id"), f"RETURN_PACK_ID_MISMATCH:{rel_key}")
        require_score(
            doc.get("sample_set_sha256") == manifest.get("sample_set_sha256"),
            f"RETURN_SAMPLE_SET_SHA_MISMATCH:{rel_key}",
        )
        if "pack_manifest_sha256" in doc and doc["pack_manifest_sha256"] != "":
            require_score(
                doc["pack_manifest_sha256"] == manifest_sha256,
                f"RETURN_MANIFEST_SHA_MISMATCH:{rel_key}",
            )

        annotator_id = doc.get("annotator_id")
        require_score(
            isinstance(annotator_id, str) and bool(annotator_id.strip()),
            f"ANNOTATOR_ID_MISSING:{rel_key}",
        )
        annotator_id = annotator_id.strip()
        require_score(annotator_id not in by_annotator_answers, f"DUPLICATE_ANNOTATOR_ID:{annotator_id}")

        answers = doc.get("answers")
        require_score(
            isinstance(answers, list) and len(answers) == len(sample_ids_ordered),
            f"RETURN_ANSWERS_COUNT_MISMATCH:{rel_key}",
        )

        seen_samples: set[str] = set()
        annotator_map: dict[str, str] = {}
        for ans in answers:
            require_score(isinstance(ans, dict), f"ANSWER_ROW_NOT_OBJECT:{rel_key}")
            sid = ans.get("sample_id")
            require_score(
                isinstance(sid, str) and sid in sample_by_id and sid not in seen_samples,
                f"ANSWER_SAMPLE_ID_INVALID_OR_DUPLICATE:{rel_key}:{sid}",
            )
            seen_samples.add(sid)
            expected_sample = sample_by_id[sid]
            for field in LOCKED_SAMPLE_FIELDS:
                require_score(
                    ans.get(field) == expected_sample.get(field),
                    f"TAMPERED_LOCKED_FIELD:{rel_key}:{sid}:{field}",
                )
            human_judgment = ans.get("human_judgment")
            require_score(
                isinstance(human_judgment, str) and human_judgment in ALLOWED_HUMAN_JUDGMENTS,
                f"INVALID_OR_INCOMPLETE_HUMAN_JUDGMENT:{rel_key}:{sid}",
            )
            notes = ans.get("notes", "")
            require_score(isinstance(notes, str), f"INVALID_NOTES_FIELD:{rel_key}:{sid}")
            annotator_map[sid] = human_judgment

        require_score(set(annotator_map.keys()) == set(sample_ids_ordered), f"MISSING_SAMPLES:{rel_key}")

        annotator_order.append(annotator_id)
        by_annotator_answers[annotator_id] = annotator_map
        return_files_sha256[rel_key] = sha256_bytes(raw)

        annotator_pairs = [
            (
                adapt_human_judgment(
                    annotator_map[sid],
                    system_judgment=system_by_id[sid]["system_judgment"],
                    semantics=semantics,
                ),
                system_by_id[sid]["system_judgment"],
            )
            for sid in sample_ids_ordered
        ]
        by_annotator_metrics[annotator_id] = _compute_binary_and_abstention_metrics(annotator_pairs)

    consensus_pairs: list[tuple[str, str]] = []
    pooled_pairs: list[tuple[str, str]] = []
    per_sample_records: list[dict[str, Any]] = []

    for sid in sample_ids_ordered:
        sys_label = system_by_id[sid]["system_judgment"]
        human_judgments_for_sid = [by_annotator_answers[ann][sid] for ann in annotator_order]
        consensus_tf = _consensus_human_judgment(human_judgments_for_sid)
        consensus_presence = adapt_human_judgment(
            consensus_tf,
            system_judgment=sys_label,
            semantics=semantics,
        )
        consensus_pairs.append((consensus_presence, sys_label))

        for ann in annotator_order:
            pooled_presence = adapt_human_judgment(
                by_annotator_answers[ann][sid],
                system_judgment=sys_label,
                semantics=semantics,
            )
            pooled_pairs.append((pooled_presence, sys_label))

        if consensus_presence == "UNKNOWN" and sys_label == "UNKNOWN":
            outcome = "ABSTAIN_BOTH"
        elif consensus_presence == "UNKNOWN":
            outcome = "ABSTAIN_HUMAN"
        elif sys_label == "UNKNOWN":
            outcome = "ABSTAIN_SYSTEM"
        elif consensus_presence == "PRESENT" and sys_label == "PRESENT":
            outcome = "TP"
        elif consensus_presence == "ABSENT" and sys_label == "PRESENT":
            outcome = "FP"
        elif consensus_presence == "ABSENT" and sys_label == "ABSENT":
            outcome = "TN"
        else:
            outcome = "FN"

        per_sample_records.append(
            {
                "sample_id": sid,
                "camera_id": sample_by_id[sid]["camera_id"],
                "frame_index": sample_by_id[sid]["frame_index"],
                "frame_sha256": sample_by_id[sid]["frame_sha256"],
                "system_judgment": sys_label,
                "prediction_sha256": system_by_id[sid]["prediction_sha256"],
                "human_judgments": {ann: by_annotator_answers[ann][sid] for ann in annotator_order},
                "consensus_human_judgment": consensus_tf,
                "consensus_presence": consensus_presence,
                "outcome": outcome,
            }
        )

    summary_metrics = _compute_binary_and_abstention_metrics(consensus_pairs)
    pooled_metrics = _compute_binary_and_abstention_metrics(pooled_pairs)
    agreement = _compute_inter_annotator_agreement(
        annotator_order,
        sample_ids_ordered,
        by_annotator_answers,
    )

    provenance = {
        "gt_read": False,
        "pack_manifest_sha256": manifest_sha256,
        "sample_set_sha256": manifest["sample_set_sha256"],
        "system_judgments_file": str(sys_file),
        "system_judgments_sha256": sys_file_sha,
        "template_sha256": manifest["template_sha256"],
        "semantics": semantics,
        "return_files_sha256": dict(sorted(return_files_sha256.items())),
    }

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "status": "SCORED",
        "pack_id": manifest["pack_id"],
        "source_mode": manifest["source_mode"],
        "real_pack_status": manifest["real_pack_status"],
        "evaluation_eligible": manifest["evaluation_eligible"],
        "evaluation_semantics": semantics,
        "gt_read": False,
        "annotator_count": len(annotator_order),
        "annotators": annotator_order,
        **summary_metrics,
        "inter_annotator_agreement": agreement,
        "by_annotator": by_annotator_metrics,
        "pooled_metrics": pooled_metrics,
        "per_sample": per_sample_records,
        "provenance": provenance,
    }
    digest = sha256_bytes(canonical_json_bytes(report))
    report["receipt_sha256"] = digest
    report["output_sha256"] = digest
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack-dir", "--pack", dest="pack_dir", required=True, type=Path)
    parser.add_argument(
        "--system-judgments",
        "--claims-file",
        dest="system_judgments_path",
        type=Path,
        default=None,
        help="Optional external system judgments / evaluation claims JSON file (defaults to <pack_dir>.eval_claims.json).",
    )
    parser.add_argument(
        "--semantics",
        choices=list(VALID_SEMANTICS),
        default="TARGET_PRESENCE",
        help="Evaluation semantics for human T/F: TARGET_PRESENCE (default) or CLAIM_VERACITY.",
    )
    parser.add_argument(
        "--return-file",
        dest="return_files",
        action="append",
        type=Path,
        help="Optional explicit completed return JSON path(s). Defaults to all RETURN/*.json except template.",
    )
    parser.add_argument("--manifest-sha256", help="Optional expected SHA-256 of MANIFEST.json.")
    parser.add_argument("--output", type=Path, help="Optional path to write the scored JSON report.")
    args = parser.parse_args(argv)

    try:
        report = score_q4_tf_returns(
            args.pack_dir,
            system_judgments_path=args.system_judgments_path,
            return_files=args.return_files,
            expected_manifest_sha256=args.manifest_sha256,
            semantics=args.semantics,
        )
        if args.output is not None:
            require_score(not args.output.exists(), "OUTPUT_ALREADY_EXISTS")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(pretty_json_bytes(report))
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 0
    except (ReturnScoreError, OSError, ValueError, TypeError) as exc:
        err = {
            "status": "INVALID",
            "reason": str(exc) if isinstance(exc, ReturnScoreError) else "SCORE_FAILED",
        }
        print(json.dumps(err, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
