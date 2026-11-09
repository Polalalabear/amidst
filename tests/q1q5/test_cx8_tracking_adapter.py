"""Synthetic selected-observation diagnostic regression tests; no model or media."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("cx8", ROOT / "scripts/run_cx8_rule_tracking.py")
cx8 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cx8)


def row(camera="C1", index=0, label="person", state="INFERRED"):
    return {"frame_ref": f"frame:R:{camera}:{index}", "camera_id": camera,
            "frame_index": index, "timestamp_us": index * 200_000,
            "rgb_file_sha256": "a" * 64, "frame_state": state,
            "detections": [{"observation_id": f"obs:{camera}:{index}",
                            "score": 0.9, "class_label": label}] if state == "INFERRED" else None}


def inputs(rows):
    raw = b"".join((json.dumps(r, sort_keys=True) + "\n").encode() for r in rows)
    binding = {"scene_id": "SYN_SCENE", "run_id": "R", "clock_id": "SYN_CLOCK",
               "rgb_index_sha256": "b" * 64}
    manifest = {"schema_version": "q-demo.detection-index.v1", **binding,
                "records_file_sha256": cx8.digest(raw), "provenance": {"gt_read": False},
                "detector": {"index_score_floor": 0.2},
                "sampling": {"per_camera": [{"camera_id": c, "source_frame_interval_us": 200_000,
                                              "sampled_ranges_us": [[0, 10_000_000]]}
                                             for c in sorted({r["camera_id"] for r in rows})]}}
    manifest["content_sha256"] = cx8.content_hash(manifest)
    mraw = json.dumps(manifest, sort_keys=True).encode()
    params = {"approval": {"status": "APPROVED", "ref": "SYNTHETIC_TEST_ONLY"},
              "parameters": [{"name": "query_min_score", "value": 0.5, "status": "APPROVED"}]}
    params["content_sha256"] = cx8.content_hash(params)
    target = {"class_label": "person", "selection_ref": "synthetic-selection:1",
              "source_records_sha256": cx8.digest(raw),
              "observation_ids": [d["observation_id"] for r in rows for d in r["detections"] or []]}
    return raw, {"manifest_bytes": mraw, "manifest_sha256": cx8.digest(mraw),
                 "expected_binding": binding, "selected_target": target, "parameter_set": params}


def test_missing_inputs_fail_closed_without_handoffs():
    raw, kwargs = inputs([row()])
    for missing in ("manifest_bytes", "expected_binding", "selected_target", "parameter_set"):
        result = cx8.build_receipt(raw, **{**kwargs, missing: None})
        assert result["status"] == "UNKNOWN"
        assert result["segments"] == result["switches"] == []


def test_explicit_samples_preserve_gaps_and_do_not_infer_handoffs():
    raw, kwargs = inputs([row(index=0), row(index=5), row(camera="C2", index=10)])
    result = cx8.build_receipt(raw, **kwargs)
    assert result["status"] == "AVAILABLE"
    assert result["scope"] == "SELECTED_OBSERVATIONS_DIAGNOSTIC"
    assert result["identity"] == "UNCONFIRMED"
    assert result["cross_camera_association"] == "NOT_EVALUATED"
    assert [(s["start_us"], s["end_us"]) for s in result["segments"]] == [
        (0, 200_000), (1_000_000, 1_200_000), (2_000_000, 2_200_000)]
    assert result["switches"] == []


@pytest.mark.parametrize("field", ["scene_id", "run_id", "clock_id", "rgb_index_sha256"])
def test_foreign_source_binding_is_rejected(field):
    raw, kwargs = inputs([row()])
    kwargs["expected_binding"][field] = "foreign"
    result = cx8.build_receipt(raw, **kwargs)
    assert result["reason"] == "SOURCE_BINDING_MISMATCH" and result["segments"] == []


def test_manifest_and_records_pins_are_checked():
    raw, kwargs = inputs([row()])
    assert cx8.build_receipt(raw, **{**kwargs, "manifest_bytes": kwargs["manifest_bytes"] + b" "})["reason"] == "MANIFEST_HASH_MISMATCH"
    assert cx8.build_receipt(raw + b"\n", **kwargs)["reason"] == "RECORDS_HASH_MISMATCH"


def test_mixed_run_rows_and_unselected_classes_cannot_become_tracking():
    foreign = row()
    foreign["frame_ref"] = "frame:OTHER_RUN:C1:0"
    raw, kwargs = inputs([foreign])
    assert cx8.build_receipt(raw, **kwargs)["reason"] == "SOURCE_BINDING_MISMATCH"
    raw, kwargs = inputs([row(label="clock")])
    result = cx8.build_receipt(raw, **kwargs)
    assert result["reason"] == "SELECTED_OBSERVATIONS_UNAVAILABLE"
    assert result["segments"] == result["switches"] == []


def test_only_explicitly_selected_observations_are_returned():
    raw, kwargs = inputs([row(index=0), row(index=1)])
    kwargs["selected_target"]["observation_ids"] = ["obs:C1:1"]
    result = cx8.build_receipt(raw, **kwargs)
    assert [s["observation_id"] for s in result["segments"]] == ["obs:C1:1"]


def test_unapproved_or_modified_parameter_sets_fail_closed():
    raw, kwargs = inputs([row()])
    for patch in ({"approval": {"status": "PROPOSED"}}, {"content_sha256": "0" * 64}):
        params = {**kwargs["parameter_set"], **patch}
        result = cx8.build_receipt(raw, **{**kwargs, "parameter_set": params})
        assert result["reason"] == "PARAMETERS_NOT_APPROVED" and result["segments"] == []


@pytest.mark.parametrize("state", ["MISSING", "NOT_INFERRED", "NOT_SAMPLED"])
def test_nonobserved_samples_never_supply_selected_evidence(state):
    raw, kwargs = inputs([row(state=state)])
    kwargs["selected_target"]["observation_ids"] = ["obs:C1:0"]
    result = cx8.build_receipt(raw, **kwargs)
    assert result["status"] == "UNKNOWN" and result["segments"] == []


def test_invalid_and_duplicate_evidence_is_rejected():
    for rows in ([row(), row()], [{**row(), "timestamp_us": -1}], [{**row(), "frame_state": "SAMPLED"}]):
        raw, kwargs = inputs(rows)
        # Keep the selection itself valid, to exercise record validation.
        kwargs["selected_target"]["observation_ids"] = ["obs:C1:0"]
        result = cx8.build_receipt(raw, **kwargs)
        assert result["status"] == "UNKNOWN" and result["segments"] == []


def test_disk_guard(monkeypatch):
    monkeypatch.setattr(cx8.shutil, "disk_usage", lambda p: SimpleNamespace(free=8 * 1024 ** 3 - 1))
    with pytest.raises(SystemExit):
        cx8.require_free_space(ROOT)
    monkeypatch.setattr(cx8.shutil, "disk_usage", lambda p: SimpleNamespace(free=8 * 1024 ** 3))
    assert cx8.require_free_space(ROOT) == 8 * 1024 ** 3


def test_pinned_inputs_refuse_symlinks(tmp_path):
    source = tmp_path / "synthetic.json"
    source.write_bytes(b"{}")
    link = tmp_path / "link.json"
    try:
        link.symlink_to(source)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"Host filesystem does not permit symlinks: {exc}")
    assert cx8.read_pinned(source, cx8.digest(b"{}")) == b"{}"
    with pytest.raises(ValueError, match="canonical"):
        cx8.read_pinned(link, cx8.digest(b"{}"))


def test_cli_rejects_output_inside_repo_before_reading_inputs():
    args = ["--repo", str(ROOT), "--records", "none", "--manifest", "none",
            "--manifest-sha256", "0" * 64, "--run-id", "R", "--scene-id", "SYN_SCENE",
            "--clock-id", "SYN_CLOCK", "--rgb-index-sha256", "b" * 64,
            "--output", str(ROOT / "out.json")]
    with pytest.raises(SystemExit):
        cx8.main(args)
