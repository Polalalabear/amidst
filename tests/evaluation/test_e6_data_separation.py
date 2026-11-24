"""Focused tests for E6 data separation and SHA manifest checker (#718)."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts" / "evaluation"))

import check_e6_data_separation as checker  # noqa: E402

SPEC_PATH = REPO_ROOT / "configs" / "evaluation" / "e6_scenarios_spec_v1.json"
E3_BASE_PATH = REPO_ROOT / "configs" / "evaluation" / "e3_live_cases_v1.json"
E3_EXT_PATH = REPO_ROOT / "configs" / "evaluation" / "e3_reappearances_v1.json"


def _load_all():
    return (
        json.loads(SPEC_PATH.read_text(encoding="utf-8")),
        json.loads(E3_BASE_PATH.read_text(encoding="utf-8")),
        json.loads(E3_EXT_PATH.read_text(encoding="utf-8")),
    )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_committed_e6_spec_passes_draft_mode():
    spec, e3_base, e3_ext = _load_all()
    errors = checker.validate_e6_spec(spec, e3_base, e3_ext, mode="draft")
    assert errors == [], f"Unexpected errors: {errors}"


def test_rejects_diagnostic_case_in_formal():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    bad["formal_cases"][0]["case_id"] = bad["diagnostic_cases"][0]["case_id"]
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext, mode="draft")
    assert any("LEAK_DIAG_IN_FORMAL_ID" in e for e in errors)


def test_rejects_old_e3_family_in_formal():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    bad["formal_cases"][0]["family_id"] = "E3_OLD_FAMILY_A4"
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext, mode="draft")
    assert any("LEAK_OLD_FAMILY_IN_FORMAL" in e for e in errors)


def test_rejects_old_e3_opening_coord_in_formal():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    bad["formal_cases"][0]["start_xy"] = [-10.0, -0.4]
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext, mode="draft")
    assert any("FORMAL_REUSES_OLD_OPENING" in e for e in errors)


def test_rejects_too_few_effective_units():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    for i in range(6):
        bad["formal_cases"][i]["family_id"] = "E6-F01"
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext, mode="draft")
    assert any("FORMAL_UNITS_BELOW_MIN" in e for e in errors)


def test_rejects_too_few_decision_points():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    for c in bad["formal_cases"]:
        c["planned_decision_points"] = c["planned_decision_points"][:3]
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext, mode="draft")
    assert any("FORMAL_DP_BELOW_MIN" in e for e in errors)


def test_rejects_formal_sha_collision_with_old_e3():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    bad["formal_cases"][0]["case_sha256"] = bad["old_e3_cases"][0]["case_sha256"]
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext, mode="draft")
    assert any("FORMAL_SHA_COLLIDES_OLD_E3" in e for e in errors)


def test_rejects_duplicate_dp_id_and_duplicate_timestamp():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    for c in bad["formal_cases"]:
        first = copy.deepcopy(c["planned_decision_points"][0])
        c["planned_decision_points"] = [copy.deepcopy(first) for _ in range(4)]
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext, mode="draft")
    assert any("FORMAL_DP_DUPLICATE_ID" in e for e in errors)
    assert any("FORMAL_DP_BELOW_MIN" in e for e in errors)


def test_rejects_duplicate_timestamp_even_with_distinct_ids():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    c0 = bad["formal_cases"][0]
    c0["planned_decision_points"][1]["t_plan_s"] = c0["planned_decision_points"][0]["t_plan_s"]
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext, mode="draft")
    assert any("FORMAL_DP_DUPLICATE_TIME" in e for e in errors)


def test_rejects_out_of_range_and_nonfinite_dp_timestamp():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    bad["formal_cases"][0]["planned_decision_points"][0]["t_plan_s"] = 999.0
    bad["formal_cases"][1]["planned_decision_points"][0]["t_plan_s"] = float("nan")
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext, mode="draft")
    assert any("FORMAL_DP_TIME_OUT_OF_RANGE" in e for e in errors)
    assert any("FORMAL_DP_INVALID_TIME" in e for e in errors)


def test_rejects_frozen_status_with_null_sha_even_in_draft_mode():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    for c in bad["formal_cases"]:
        c["actual_gt_status"] = "FROZEN"
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext, mode="draft")
    assert any("FORMAL_MISSING_SHA" in e for e in errors)


def test_formal_mode_rejects_pending_spec():
    spec, e3_base, e3_ext = _load_all()
    errors = checker.validate_e6_spec(spec, e3_base, e3_ext, mode="formal")
    assert any("FORMAL_NOT_FROZEN" in e for e in errors)
    assert any("FORMAL_MISSING_SHA" in e for e in errors)


def test_formal_mode_passes_and_verifies_artifact_root_shas(tmp_path: Path):
    spec, e3_base, e3_ext = _load_all()
    frozen = copy.deepcopy(spec)
    (tmp_path / "gt-boxes").mkdir()
    for i, c in enumerate(frozen["formal_cases"]):
        cid = c["case_id"]
        case_rel = f"{cid}.case.json"
        gt_rel = f"gt-boxes/{cid}.a-log.json"
        case_bytes = f'{{"case_id":"{cid}","seq":{i}}}\n'.encode("utf-8")
        gt_bytes = f'{{"gt_case":"{cid}","seq":{i}}}\n'.encode("utf-8")
        (tmp_path / case_rel).write_bytes(case_bytes)
        (tmp_path / gt_rel).write_bytes(gt_bytes)

        c["actual_gt_status"] = "FROZEN"
        c["actual_duration_s"] = c["planned_duration_s"]
        c["case_path"] = case_rel
        c["gt_path"] = gt_rel
        c["case_sha256"] = _sha256_bytes(case_bytes)
        c["gt_sha256"] = _sha256_bytes(gt_bytes)
        c["actual_decision_points"] = [
            {
                "dp_id": dp["dp_id"],
                "tick": int(round(dp["t_plan_s"] * 5)),
                "t_actual_s": dp["t_plan_s"],
                "gt_regime": dp.get("gt_regime", "VISIBLE"),
            }
            for dp in c["planned_decision_points"]
        ]

    errors = checker.validate_e6_spec(frozen, e3_base, e3_ext, mode="formal", artifact_root=tmp_path)
    assert errors == [], f"Unexpected errors: {errors}"

    # Mutate one byte on disk -> formal artifact verification MUST fail
    (tmp_path / "E6-S01.case.json").write_bytes(b'{"tampered":true}\n')
    errors_tampered = checker.validate_e6_spec(frozen, e3_base, e3_ext, mode="formal", artifact_root=tmp_path)
    assert any("FORMAL_ARTIFACT_SHA_MISMATCH" in e for e in errors_tampered)
