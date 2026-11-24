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


def _build_valid_formal_fixture(spec: dict, root: Path) -> dict:
    """Materialize a complete synthetic frozen corpus with valid 5 Hz GT ticks and SHAs."""
    frozen = copy.deepcopy(spec)
    (root / "gt-boxes").mkdir(exist_ok=True)
    fps_hz = 5
    window_ticks = 15

    for i, c in enumerate(frozen["formal_cases"]):
        cid = c["case_id"]
        duration_s = float(c["planned_duration_s"])
        n_ticks = int(round(duration_s * fps_hz))

        # Build per-tick GT matching each DP's declared gt_regime across its 15-tick window
        regime_by_tick: dict[int, str] = {}
        actual_dps = []
        for dp in c["planned_decision_points"]:
            tk = int(round(float(dp["t_plan_s"]) * fps_hz))
            regime = dp.get("gt_regime", "VISIBLE")
            for w in range(tk, tk + window_ticks):
                regime_by_tick[w] = regime
            actual_dps.append(
                {
                    "dp_id": dp["dp_id"],
                    "tick": tk,
                    "t_actual_s": round(tk / float(fps_hz), 3),
                    "gt_regime": regime,
                }
            )

        ticks = []
        for tk in range(n_ticks):
            reg = regime_by_tick.get(tk, "VISIBLE")
            if reg == "TRUE_DEPARTURE":
                actor = {"id": "T", "present": False, "xy": [0.0, 0.0], "gt_visible": []}
            elif reg == "FULL_BLIND":
                actor = {"id": "T", "present": True, "xy": [0.0, 0.0], "gt_visible": []}
            else:
                actor = {"id": "T", "present": True, "xy": [0.0, 0.0], "gt_visible": ["CAM_W1"]}
            ticks.append({"tick": tk, "actors": [actor]})

        case_rel = f"{cid}.case.json"
        gt_rel = f"gt-boxes/{cid}.a-log.json"
        case_bytes = (json.dumps({"case_id": cid, "seq": i}) + "\n").encode("utf-8")
        gt_bytes = (json.dumps({"case_id": cid, "ticks": ticks}) + "\n").encode("utf-8")
        (root / case_rel).write_bytes(case_bytes)
        (root / gt_rel).write_bytes(gt_bytes)

        c["actual_gt_status"] = "FROZEN"
        c["actual_duration_s"] = duration_s
        c["case_path"] = case_rel
        c["gt_path"] = gt_rel
        c["case_sha256"] = _sha256_bytes(case_bytes)
        c["gt_sha256"] = _sha256_bytes(gt_bytes)
        c["actual_decision_points"] = actual_dps

    return frozen


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


def test_formal_mode_requires_artifact_root(tmp_path: Path):
    spec, e3_base, e3_ext = _load_all()
    frozen = _build_valid_formal_fixture(spec, tmp_path)
    errors = checker.validate_e6_spec(frozen, e3_base, e3_ext, mode="formal", artifact_root=None)
    assert any("FORMAL_ARTIFACT_ROOT_REQUIRED" in e for e in errors)


def test_formal_mode_passes_and_rejects_tampered_file(tmp_path: Path):
    spec, e3_base, e3_ext = _load_all()
    frozen = _build_valid_formal_fixture(spec, tmp_path)
    errors = checker.validate_e6_spec(frozen, e3_base, e3_ext, mode="formal", artifact_root=tmp_path)
    assert errors == [], f"Unexpected errors: {errors}"

    # Mutate one byte on disk -> formal artifact verification MUST fail
    (tmp_path / "E6-S01.case.json").write_bytes(b'{"tampered":true}\n')
    errors_tampered = checker.validate_e6_spec(frozen, e3_base, e3_ext, mode="formal", artifact_root=tmp_path)
    assert any("FORMAL_ARTIFACT_SHA_MISMATCH" in e for e in errors_tampered)


def test_formal_mode_rejects_out_of_range_tick_and_tick_time_mismatch(tmp_path: Path):
    spec, e3_base, e3_ext = _load_all()
    frozen = _build_valid_formal_fixture(spec, tmp_path)
    frozen["formal_cases"][0]["actual_decision_points"][0]["tick"] = 1_000_000
    frozen["formal_cases"][1]["actual_decision_points"][0]["tick"] += 2  # breaks 5 Hz match with t_actual_s
    errors = checker.validate_e6_spec(frozen, e3_base, e3_ext, mode="formal", artifact_root=tmp_path)
    assert any("FORMAL_DP_TICK_OUT_OF_RANGE" in e for e in errors)
    assert any("FORMAL_DP_TICK_TIME_MISMATCH" in e for e in errors)


def test_formal_mode_rejects_empty_gt_ticks_and_wrong_gt_regime(tmp_path: Path):
    spec, e3_base, e3_ext = _load_all()
    frozen = _build_valid_formal_fixture(spec, tmp_path)

    # Case 0: overwrite GT with empty ticks and update SHA so hash matches -> MUST still FAIL
    empty_gt_bytes = b'{"case_id":"E6-S01","ticks":[]}\n'
    (tmp_path / "gt-boxes/E6-S01.a-log.json").write_bytes(empty_gt_bytes)
    frozen["formal_cases"][0]["gt_sha256"] = _sha256_bytes(empty_gt_bytes)

    # Case 1: flip declared gt_regime so it disagrees with GT ticks -> MUST FAIL
    frozen["formal_cases"][1]["actual_decision_points"][0]["gt_regime"] = "TRUE_DEPARTURE"

    errors = checker.validate_e6_spec(frozen, e3_base, e3_ext, mode="formal", artifact_root=tmp_path)
    assert any("FORMAL_GT_MISSING_TICKS" in e for e in errors)
    assert any("FORMAL_DP_REGIME_MISMATCH" in e for e in errors)
