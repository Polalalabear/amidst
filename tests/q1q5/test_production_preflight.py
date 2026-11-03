"""Metadata checks cannot authorize rendering, inference or human acceptance."""

import hashlib
import json
from pathlib import Path

import pytest

from amidst.q1q5.production_preflight import (
    inspect_protocol,
    inspect_review_metadata,
    metadata_ref,
    read_pinned,
    strict_json,
)

ROOT = Path(__file__).resolve().parents[2]


def source():
    return json.loads((ROOT / "configs/q1q5/baseline_v1_protocol.json").read_bytes())


def write(tmp_path, value):
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(value))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_current_protocol_is_blocked_and_no_asset_or_model_is_opened(tmp_path):
    path, pin = write(tmp_path, source())
    result = inspect_protocol(path, pin, free_bytes=9 * 1024**3)
    assert result["status"] == "BLOCKED" and not result["production_performed"]
    assert not result["human_approval_verified"] and not result["formal_run_allowed"]
    assert (
        next(row for row in result["checks"] if row["item"] == "run_camera_time_scope")["status"]
        == "UNRESOLVED"
    )


def test_low_disk_even_with_changed_boolean_cannot_allow_formal_production(tmp_path):
    data = source()
    data["formal_run"]["allowed"] = True
    for gate in data["formal_run"]["required_gates"].values():
        gate["status"] = "APPROVED"
    path, pin = write(tmp_path, data)
    result = inspect_protocol(path, pin, free_bytes=8 * 1024**3 - 1)
    assert result["reason"] == "DISK_SPACE_BELOW_8_GIB" and not result["formal_run_allowed"]
    assert all(
        row["status"] == "UNRESOLVED" for row in result["checks"] if row["item"].startswith("gate:")
    )


def test_receipt_bytes_prove_only_integrity_not_human_approval(tmp_path):
    data = source()
    receipt = tmp_path / "approval.json"
    receipt.write_text('{"approved":true}')
    key = next(iter(data["formal_run"]["required_gates"]))
    data["formal_run"]["required_gates"][key].update(
        status="APPROVED",
        receipt_ref=receipt.name,
        receipt_sha256=hashlib.sha256(receipt.read_bytes()).hexdigest(),
    )
    path, pin = write(tmp_path, data)
    result = inspect_protocol(path, pin, data_root=tmp_path, free_bytes=9 * 1024**3)
    assert (
        next(row for row in result["checks"] if row["item"] == "receipt_bytes:" + key)["status"]
        == "VERIFIED"
    )
    assert (
        next(row for row in result["checks"] if row["item"] == "gate:" + key)["status"]
        == "UNRESOLVED"
    )


@pytest.mark.parametrize(
    "relative",
    [
        "../other.json",
        "/tmp/other.json",
        "gt/labels.json",
        "private_evaluation/answers.json",
        "persons.sim.json",
        "event_run.validation.json",
    ],
)
def test_forbidden_refs_are_rejected_without_reading_them(tmp_path, relative):
    with pytest.raises(ValueError):
        metadata_ref(tmp_path, relative)


def test_file_pin_and_symlink_refuse_tampering(tmp_path):
    path, pin = write(tmp_path, source())
    with pytest.raises(ValueError):
        read_pinned(path, "0" * 64)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    with pytest.raises(ValueError):
        read_pinned(link, pin)
    nested = tmp_path / "nested"
    nested.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError):
        read_pinned(nested / "protocol.json", pin)


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":1e999}'])
def test_strict_json_rejects_duplicate_or_nonfinite_values(raw):
    with pytest.raises(ValueError):
        strict_json(raw)


def test_non_json_or_fifo_rejected_without_blocking(tmp_path):
    import os

    fifo = tmp_path / "pipe.json"
    os.mkfifo(fifo)
    with pytest.raises(ValueError):
        read_pinned(fifo, "a" * 64)
    path = tmp_path / "image.png"
    with pytest.raises(ValueError):
        read_pinned(path, "a" * 64)


def test_review_preflight_reads_locked_metadata_and_never_editable_return(tmp_path):
    names = [
        "provenance/build_sources.json",
        "provenance/camera_catalog.json",
        "provenance/region_graph.json",
        "provenance/camera_graph.json",
        "provenance/hsv_config.json",
    ]
    manifest = {"files": {"RETURN.csv": "UNREADABLE_ON_PURPOSE"}}
    for name in names:
        doc = {"gt_read": False, "static_source_sha256": "a" * 64}
        if name == names[1]:
            doc = {"cameras": [{"camera_id": "A", "calibration_sha256": "b" * 64}]}
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(doc))
        manifest["files"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    path = tmp_path / "MANIFEST.json"
    path.write_text(json.dumps(manifest))
    result = inspect_review_metadata(path, hashlib.sha256(path.read_bytes()).hexdigest())
    assert result["camera_ids"] == ["A"] and len(result["locked_metadata_file_hashes"]) == 5
    assert not result["editable_returns_read"] and not result["human_approval_verified"]
    assert result["proposed_production_design"]["runs"][0]["camera_ids"] is None
