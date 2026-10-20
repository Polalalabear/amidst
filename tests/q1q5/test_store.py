"""SYNTHETIC store integrity tests; no real assets or service dependencies."""
import hashlib
import json

import pytest

from amidst.q1q5.store import DocumentPin, JsonRunStore, StoreError, canonical_hash


def write(root, path, doc, schema="q-demo.clock-mapping.v1"):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = doc if isinstance(doc, bytes) else json.dumps(doc).encode()
    target.write_bytes(raw)
    return DocumentPin(path, hashlib.sha256(raw).hexdigest(), schema)


def document(**changes):
    doc = {"schema_version": "q-demo.clock-mapping.v1", "declaration_source": "SYNTHETIC"}
    doc.update(changes)
    doc["content_sha256"] = canonical_hash(doc, exclude=("content_sha256",))
    return doc


def index(root, state="INFERRED"):
    manifest = {
        "schema_version": "q-demo.detection-index.v1", "scene_revision": "rSYN",
        "scene_id": "SYNTHETIC", "run_id": "RUN_SYN", "clock_id": "CLOCK_SYN",
        "sampling": {"per_camera": [{"camera_id": "CAM_SYN"}]},
        "records_ref": "records.jsonl",
    }
    key = canonical_hash(manifest, exclude=("records_ref",))[:16]
    record = {"frame_ref": "frame:RUN_SYN:CAM_SYN:0", "camera_id": "CAM_SYN",
              "frame_index": 0, "timestamp_us": 0, "frame_state": state,
              "state_reason": "SYNTHETIC" if state == "NOT_INFERRED" else None,
              "detections": [{"observation_id": f"obs:{key}:CAM_SYN:0:0"}]
              if state == "INFERRED" else None}
    raw = json.dumps(record).encode() + b"\n"
    records = write(root, "run/records.jsonl", raw, "q-demo.detection-record.v1")
    manifest["records_file_sha256"] = records.file_sha256
    manifest["index_id"] = f"detidx:rSYN:RUN_SYN:{key}"
    manifest["content_sha256"] = canonical_hash(manifest, exclude=("index_id",))
    pin = write(root, "run/index.json", manifest, manifest["schema_version"])
    return JsonRunStore(root, {"index": pin, "records": records}), manifest, record


def test_json_and_index_load_without_mutating_declared_approval(tmp_path):
    doc = document(approval_status="DRAFT")
    pin = write(tmp_path, "clock.json", doc)
    store = JsonRunStore(tmp_path, {"clock": pin})
    loaded = store.load_document("clock")
    assert loaded == doc and loaded["approval_status"] == "DRAFT"
    loaded["approval_status"] = "APPROVED"
    assert store.load_document("clock")["approval_status"] == "DRAFT"
    store, manifest, record = index(tmp_path)
    result = store.load_detection_index("index")
    assert result.manifest == manifest and result.records == (record,)


@pytest.mark.parametrize("state", ["MISSING", "NOT_INFERRED", "NOT_SAMPLED"])
def test_absent_observation_states_remain_distinct(tmp_path, state):
    store, _, _ = index(tmp_path, state)
    assert store.load_detection_index("index").records[0]["frame_state"] == state


def test_pinned_missing_or_tampered_files_fail_closed(tmp_path):
    pin = write(tmp_path, "clock.json", document())
    store = JsonRunStore(tmp_path, {"clock": pin})
    (tmp_path / "clock.json").write_text("{}")
    with pytest.raises(StoreError, match="file hash"):
        store.load_document("clock")
    (tmp_path / "clock.json").unlink()
    with pytest.raises(StoreError, match="missing"):
        store.load_document("clock")


@pytest.mark.parametrize("path", [
    "../escape.json", "/absolute.json", "a/../escape.json", "a//x.json", "gt/data.json",
    "private_evaluation/x.json", "human_review/x.json", "source.blend", "image.png",
    "persons.sim.json", "event_x.validation.json", "a\\x.json",
])
def test_forbidden_paths_are_rejected_before_access(path):
    with pytest.raises(StoreError) as error:
        DocumentPin(path, "0" * 64, "SYNTHETIC")
    assert error.value.code == "FORBIDDEN_DATA_SCOPE"


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}',
                                  b'[]', b'not-json', b'{"actor_id":"SYNTHETIC"}'])
def test_invalid_json_and_forbidden_keys_are_not_exposed(tmp_path, raw):
    pin = write(tmp_path, "bad.json", raw)
    with pytest.raises(StoreError):
        JsonRunStore(tmp_path, {"bad": pin}).load_document("bad")


def test_content_hash_schema_and_external_content_pin_are_checked(tmp_path):
    doc = document()
    doc["declaration_source"] = "CHANGED"
    pin = write(tmp_path, "bad.json", doc)
    with pytest.raises(StoreError, match="Content hash"):
        JsonRunStore(tmp_path, {"x": pin}).load_document("x")
    pin = write(tmp_path, "good.json", document())
    wrong = DocumentPin(pin.path, pin.file_sha256, "wrong")
    with pytest.raises(StoreError, match="Schema"):
        JsonRunStore(tmp_path, {"x": wrong}).load_document("x")
    wrong = DocumentPin(pin.path, pin.file_sha256, pin.schema_version, "0" * 64)
    with pytest.raises(StoreError, match="Pinned content"):
        JsonRunStore(tmp_path, {"x": wrong}).load_document("x")


@pytest.mark.parametrize("parent", [False, True])
def test_leaf_and_parent_symlinks_are_never_followed(tmp_path, parent):
    pin = write(tmp_path, "safe/clock.json", document())
    if parent:
        (tmp_path / "safe").rename(tmp_path / "original")
        (tmp_path / "safe").symlink_to(tmp_path / "original", target_is_directory=True)
    else:
        (tmp_path / "safe/clock.json").rename(tmp_path / "safe/original.json")
        (tmp_path / "safe/clock.json").symlink_to(tmp_path / "safe/original.json")
    with pytest.raises(StoreError, match="symlinked"):
        JsonRunStore(tmp_path, {"x": pin}).load_document("x")


def test_unknown_reference_and_records_pin_cannot_be_substituted(tmp_path):
    store, _, _ = index(tmp_path)
    with pytest.raises(StoreError) as error:
        store.load_document("../index.json")
    assert error.value.code == "FORBIDDEN_DATA_SCOPE"
    store._pins.pop("records")
    with pytest.raises(StoreError, match="allowlisted"):
        store.load_detection_index("index")
