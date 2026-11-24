"""Focused tests for E6 data separation and SHA manifest checker (#718)."""

from __future__ import annotations

import copy
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


def test_committed_e6_spec_passes():
    spec, e3_base, e3_ext = _load_all()
    errors = checker.validate_e6_spec(spec, e3_base, e3_ext)
    assert errors == [], f"Unexpected errors: {errors}"


def test_rejects_diagnostic_case_in_formal():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    bad["formal_cases"][0]["case_id"] = bad["diagnostic_cases"][0]["case_id"]
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext)
    assert any("LEAK_DIAG_IN_FORMAL_ID" in e for e in errors)


def test_rejects_old_e3_family_in_formal():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    bad["formal_cases"][0]["family_id"] = "E3_OLD_FAMILY_A4"
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext)
    assert any("LEAK_OLD_FAMILY_IN_FORMAL" in e for e in errors)


def test_rejects_old_e3_opening_coord_in_formal():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    bad["formal_cases"][0]["start_xy"] = [-10.0, -0.4]
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext)
    assert any("FORMAL_REUSES_OLD_OPENING" in e for e in errors)


def test_rejects_too_few_effective_units():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    for i in range(6):
        bad["formal_cases"][i]["family_id"] = "E6-F01"
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext)
    assert any("FORMAL_UNITS_BELOW_MIN" in e for e in errors)


def test_rejects_too_few_decision_points():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    for c in bad["formal_cases"]:
        c["planned_decision_points"] = c["planned_decision_points"][:3]
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext)
    assert any("FORMAL_DP_BELOW_MIN" in e for e in errors)


def test_rejects_formal_sha_collision_with_old_e3():
    spec, e3_base, e3_ext = _load_all()
    bad = copy.deepcopy(spec)
    bad["formal_cases"][0]["case_sha256"] = bad["old_e3_cases"][0]["case_sha256"]
    errors = checker.validate_e6_spec(bad, e3_base, e3_ext)
    assert any("FORMAL_SHA_COLLIDES_OLD_E3" in e for e in errors)
