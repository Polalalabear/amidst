"""D57 (rgb_index key names, pinned frames[] adapter) and D58 (OBS-002 penetration width).

SYNTHETIC: documents come from ``scene_marker_fixtures``.  The pinned-hash case builds a file whose
SHA-256 is monkeypatched into the pin list, because the real pinned files are not in the repo.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from scene_marker_fixtures import build_bundle, write_bundle

from amidst.scene_markers import ValidationParams, rgb_index_adapter, validate_documents
from amidst.scene_markers.validate import validate_safe_bundle

Bundle = dict[str, Any]


def run(bundle: Bundle, **kwargs: Any) -> dict[str, Any]:
    return validate_documents(**bundle, **kwargs)


def rule(report: dict[str, Any], rule_id: str) -> dict[str, Any]:
    return next(r for r in report["rules"] if r["rule_id"] == rule_id)


def codes(report: dict[str, Any], rule_id: str, severity: str = "ERROR") -> set[str]:
    return {
        i["code"] for i in report["issues"] if i["rule_id"] == rule_id and i["severity"] == severity
    }


# ---------------------------------------------------------------- D57


def _legacy_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pin: bool = True) -> Path:
    """A bundle on disk whose rgb_index.json uses frames[] (the legacy r003 layout)."""
    bundle = build_bundle("b1")
    bundle["rgb_index"]["frames"] = bundle["rgb_index"].pop("records")
    directory = tmp_path / "safe_bundle"
    hashes = write_bundle(directory, bundle)
    if pin:
        monkeypatch.setitem(
            rgb_index_adapter.PINNED_LEGACY_FILE_SHA256,
            hashes["rgb_index"],
            "ctrl-lcorr-s1-b1-5fps-v1-r001",
        )
    return directory


def test_records_is_the_native_key_and_needs_no_adapter() -> None:
    report = run(build_bundle("b1"))
    assert report["status"] == "PASS" and report["adapters"] == []


def test_pinned_legacy_frames_file_is_adapted_and_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _legacy_dir(tmp_path, monkeypatch)
    before = (directory / "rgb_index.json").read_bytes()
    report = validate_safe_bundle(directory)
    assert report["status"] == "PASS", [i for i in report["issues"] if i["severity"] == "ERROR"]
    assert report["adapters"] == [
        {
            "name": "rgb-index-frames-to-records",
            "version": "1",
            "role": "rgb_index",
            "mapping": "frames[] -> records[]",
            "source_file_sha256": report["input_file_sha256"]["rgb_index"],
            "source_schema_version": "controlled-scene.rgb-index.v1",
            "pinned_run_id": "ctrl-lcorr-s1-b1-5fps-v1-r001",
        }
    ]
    assert (
        rule(report, "RUN-004")["result"] == "PASS" and rule(report, "RUN-003")["result"] == "PASS"
    )
    assert (directory / "rgb_index.json").read_bytes() == before  # the file is never rewritten


def test_frames_file_that_is_not_pinned_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = _legacy_dir(tmp_path, monkeypatch, pin=False)
    report = validate_safe_bundle(directory)
    assert report["status"] == "FAIL" and report["adapters"] == []
    assert codes(report, "SCH-010") == {"RGB_INDEX_FRAMES_NOT_PINNED"}


def test_pinned_hash_with_other_schema_version_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = build_bundle("b1")
    bundle["rgb_index"]["frames"] = bundle["rgb_index"].pop("records")
    bundle["rgb_index"]["schema_version"] = "controlled-scene.rgb-index.v2"
    directory = tmp_path / "safe_bundle"
    hashes = write_bundle(directory, bundle)
    monkeypatch.setitem(rgb_index_adapter.PINNED_LEGACY_FILE_SHA256, hashes["rgb_index"], "x")
    assert "RGB_INDEX_FRAMES_NOT_PINNED" in codes(validate_safe_bundle(directory), "SCH-010")


def test_frames_in_memory_has_no_file_hash_so_it_is_not_pinned() -> None:
    bundle = build_bundle("b1")
    bundle["rgb_index"]["frames"] = bundle["rgb_index"].pop("records")
    assert "RGB_INDEX_FRAMES_NOT_PINNED" in codes(run(bundle), "SCH-010")


def test_both_keys_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bundle = build_bundle("b1")
    bundle["rgb_index"]["frames"] = copy.deepcopy(bundle["rgb_index"]["records"])
    report = run(bundle)
    assert report["status"] == "FAIL" and codes(report, "SCH-010") == {"RGB_INDEX_KEYS_AMBIGUOUS"}
    directory = tmp_path / "safe_bundle"
    hashes = write_bundle(directory, bundle)  # even a pinned hash cannot rescue two keys
    monkeypatch.setitem(rgb_index_adapter.PINNED_LEGACY_FILE_SHA256, hashes["rgb_index"], "x")
    assert codes(validate_safe_bundle(directory), "SCH-010") == {"RGB_INDEX_KEYS_AMBIGUOUS"}


def test_neither_key_fails_closed() -> None:
    bundle = build_bundle("b1")
    bundle["rgb_index"].pop("records")
    report = run(bundle)
    assert report["status"] == "FAIL" and codes(report, "SCH-010") == {"RGB_INDEX_KEYS_MISSING"}


def test_failed_resolution_does_not_cascade_into_grid_errors() -> None:
    bundle = build_bundle("b1")
    bundle["rgb_index"].pop("records")
    assert codes(run(bundle), "RUN-004") == set()


def test_real_pin_list_is_the_two_d57_hashes() -> None:
    assert set(rgb_index_adapter.PINNED_LEGACY_FILE_SHA256) == {
        "9e43237e9c9ac9ea4f2bc97f65e49103a0ec3946b1b555b9d7fbf59850e97d47",
        "a5392a6fc5b51257adb82827df376f42290690cbdb52160888eb241f256ecc39",
    }
    assert rgb_index_adapter.LEGACY_SCHEMA_VERSION == "controlled-scene.rgb-index.v1"


def test_missing_and_incomplete_rules_are_unchanged_after_adaptation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = build_bundle("b1")
    bundle["rgb_index"]["frames"] = bundle["rgb_index"].pop("records")
    bundle["rgb_index"]["frames"].pop(11)  # sample vanishes from the index: RGB_INDEX_INCOMPLETE
    directory = tmp_path / "safe_bundle"
    hashes = write_bundle(directory, bundle)
    monkeypatch.setitem(rgb_index_adapter.PINNED_LEGACY_FILE_SHA256, hashes["rgb_index"], "x")
    assert "RGB_INDEX_INCOMPLETE" in codes(validate_safe_bundle(directory), "RUN-004")


# ---------------------------------------------------------------- D58


def _overlap_bundle(depth_m: float) -> Bundle:
    """OBSTACLE_SCREEN_R102's hole is made smaller than the footprint by ``depth_m`` on one side."""
    bundle = build_bundle("a")
    walk = next(w for w in bundle["static"]["walkable"] if w["id"] == "WALK_R102")
    walk["holes_m"] = [[[18.0 + depth_m, 7.8], [18.0 + depth_m, 10.2], [18.15, 10.2], [18.15, 7.8]]]
    return bundle


def test_float32_scale_overlap_is_info_with_area_and_width() -> None:
    report = run(_overlap_bundle(1.9073e-6))  # the r003 R102 case: 1.9073e-6 m x 2.4 m
    assert report["status"] == "PASS"
    assert rule(report, "OBS-002")["result"] == "PASS"
    info = [i for i in report["issues"] if i["rule_id"] == "OBS-002" and i["severity"] == "INFO"]
    assert [i["code"] for i in info] == ["SOLID_OVERLAP_WITHIN_FLOAT_PRECISION"]
    assert info[0]["id"] == "OBSTACLE_SCREEN_R102"
    assert "4.5775e-06" in info[0]["message"] or "4.5776e-06" in info[0]["message"]
    assert "1.9073e-06" in info[0]["message"]
    assert report["summary"]["infos"] == 1


def test_one_millimetre_overlap_is_an_error() -> None:
    report = run(_overlap_bundle(1e-3))
    assert report["status"] == "FAIL"
    assert codes(report, "OBS-002") == {"SOLID_OVERLAPS_WALKABLE"}
    assert not codes(report, "OBS-002", "INFO")


@pytest.mark.parametrize(("depth", "expected"), [(9.9e-6, "PASS"), (1.01e-5, "FAIL")])
def test_penetration_threshold_is_the_boundary(depth: float, expected: str) -> None:
    assert rule(run(_overlap_bundle(depth)), "OBS-002")["result"] == expected


def test_threshold_is_a_parameter_and_area_alone_no_longer_decides() -> None:
    bundle = _overlap_bundle(1.9073e-6)
    strict = ValidationParams(overlap_penetration_max_m=1e-6)
    assert rule(run(bundle, params=strict), "OBS-002")["result"] == "FAIL"
    # the old area tolerance (1e-6 m²) is exceeded by 4.58e-6 m² yet the rule passes (D58)
    assert ValidationParams().overlap_area_tol_m2 == 1e-6
    assert rule(run(bundle), "OBS-002")["result"] == "PASS"


def test_long_thin_sliver_is_judged_by_width_not_length() -> None:
    bundle = _overlap_bundle(5e-6)  # 2.4 m long, 5 um wide
    assert rule(run(bundle), "OBS-002")["result"] == "PASS"


def test_version_markers_are_updated() -> None:
    report = run(build_bundle("a"))
    assert report["verifier_version"].endswith(".v2")
    assert report["parameters_version"] == "validation-params.v2"
    assert report["parameters"]["overlap_penetration_max_m"] == 1e-5
    json.dumps(report)
