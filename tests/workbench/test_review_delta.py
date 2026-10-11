"""Source-bound, minimal history exports and replay guards."""

from __future__ import annotations

import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from amidst.workbench.reviews import ReviewStore, replay_review_delta
from amidst.workbench.storage_probe import _synthetic_scene

Payload = dict[str, Any]


@pytest.fixture
def store(tmp_path: Path) -> ReviewStore:
    scene = _synthetic_scene()
    return ReviewStore(tmp_path / "reviews.sqlite3", {scene["scene_id"]: scene})


def _publish(store: ReviewStore, object_id: str, changes: Payload, version: int = 0) -> Payload:
    scene_id = _synthetic_scene()["scene_id"]
    draft = store.save_draft(scene_id, object_id, changes, version, "Researcher", "Fixture edit")
    assert store.validate_draft(draft["draft_id"])["valid"]
    return store.publish_draft(draft["draft_id"], "Reviewer", "Synthetic evidence", version)


def _rehash(delta: Payload) -> None:
    payload = {key: value for key, value in delta.items() if key != "document_hash"}
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    delta["document_hash"] = hashlib.sha256(text.encode()).hexdigest()


def _digest(value: object) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def test_export_contains_only_changed_fields_and_replays_without_mutating_source(
    store: ReviewStore,
) -> None:
    scene = _synthetic_scene()
    scene_id = scene["scene_id"]
    published = _publish(store, "probe-region", {"label": "Corrected room"})
    delta = store.export_delta(scene_id, 1)
    state = store.state(scene_id)
    base = copy.deepcopy(state["versions"][0])
    original = copy.deepcopy(base)
    original_delta = copy.deepcopy(delta)
    assert delta["schema_version"] == "workbench.scene-review-delta.v1"
    assert delta["source_hash"] == scene["source_hash"]
    assert delta["base_version"] == 0 and delta["version"] == 1
    assert delta["parent_version_hash"] == delta["base_version_hash"]
    assert delta["reviewer"] == "Reviewer" and delta["reason"] == "Synthetic evidence"
    assert delta["validation_reference"]["validation_id"] == published["validation_id"]
    assert delta["patch"] == [{
        "object_id": "probe-region", "op": "replace", "path": ["label"],
        "old_value": "Synthetic room", "value": "Corrected room",
    }]
    serialized = json.dumps(delta)
    for forbidden in ("probe-portal", "geometry", "properties", "points", "editable_fields",
                      "baseline_objects", '"objects"', '"before"', '"after"', ".blend",
                      '"media"', '"ground_truth"'):
        assert forbidden not in serialized
    assert delta["formal_approval"] is False
    assert replay_review_delta(base, delta) == published["overlay"]
    assert base == original and delta == original_delta
    assert store.state(scene_id)["baseline_objects"] == scene["objects"]
    assert store.export_delta(scene_id, 1) == delta


def test_nested_change_omits_unchanged_properties_and_chain_uses_exact_prior_version(
    store: ReviewStore,
) -> None:
    scene_id = _synthetic_scene()["scene_id"]
    _publish(store, "probe-portal", {"properties": {"width": 1.2, "description": "Measured"}})
    published = _publish(store, "probe-portal",
                         {"properties": {"width": 1.4, "description": "Measured"}}, 1)
    delta = store.export_delta(scene_id, 2)
    assert delta["base_version"] == 1
    assert delta["patch"] == [{
        "object_id": "probe-portal", "op": "replace", "path": ["properties", "width"],
        "old_value": 1.2, "value": 1.4,
    }]
    assert "Measured" not in json.dumps(delta)
    versions = store.state(scene_id)["versions"]
    assert replay_review_delta(versions[1], delta) == published["overlay"]
    with pytest.raises(ValueError, match="DELTA_BASE_MISMATCH"):
        replay_review_delta(versions[0], delta)


def test_geometry_patch_includes_one_coordinate_or_removed_vertex_only(store: ReviewStore) -> None:
    scene = _synthetic_scene()
    scene_id = scene["scene_id"]
    points = copy.deepcopy(scene["objects"][0]["geometry"]["points"])
    points[1][0] = 5
    _publish(store, "probe-region", {"geometry": {"type": "polygon", "points": points}})
    first = store.export_delta(scene_id, 1)
    assert first["patch"] == [{
        "object_id": "probe-region", "op": "replace", "path": ["geometry", "points", 1, 0],
        "old_value": 4, "value": 5,
    }]
    points.pop()
    published = _publish(store, "probe-region",
                         {"geometry": {"type": "polygon", "points": points}}, 1)
    second = store.export_delta(scene_id, 2)
    assert second["patch"] == [{
        "object_id": "probe-region", "op": "remove", "path": ["geometry", "points", 3],
        "old_value": [0, 3, 0],
    }]
    assert replay_review_delta(store.state(scene_id)["versions"][1], second) == published["overlay"]


def test_added_and_removed_properties_replay_as_minimal_operations(store: ReviewStore) -> None:
    scene_id = _synthetic_scene()["scene_id"]
    _publish(store, "probe-portal", {"properties": {"width": 1, "description": "New"}})
    assert store.export_delta(scene_id, 1)["patch"] == [{
        "object_id": "probe-portal", "op": "add", "path": ["properties", "description"],
        "value": "New",
    }]
    published = _publish(store, "probe-portal", {"properties": {"width": 1}}, 1)
    delta = store.export_delta(scene_id, 2)
    assert delta["patch"] == [{
        "object_id": "probe-portal", "op": "remove", "path": ["properties", "description"],
        "old_value": "New",
    }]
    assert replay_review_delta(store.state(scene_id)["versions"][1], delta) == published["overlay"]


@pytest.mark.parametrize("field,value,error", [
    ("schema_version", "unknown", "DELTA_SCHEMA_INVALID"),
    ("media", "fake-image", "DELTA_SCHEMA_INVALID"),
    ("reason", "Altered without rehash", "DELTA_DOCUMENT_HASH_INVALID"),
    ("document_hash", "0" * 64, "DELTA_DOCUMENT_HASH_INVALID"),
])
def test_corrupt_or_expanded_document_rejected(
    store: ReviewStore, field: str, value: object, error: str,
) -> None:
    scene_id = _synthetic_scene()["scene_id"]
    _publish(store, "probe-region", {"label": "Changed"})
    delta = store.export_delta(scene_id, 1)
    delta[field] = value
    with pytest.raises(ValueError, match=error):
        replay_review_delta(store.state(scene_id)["versions"][0], delta)


@pytest.mark.parametrize("field,value,error", [
    ("old_value", "Wrong room", "DELTA_PATCH_BASE_MISMATCH"),
    ("path", ["authority"], "DELTA_PATCH_INVALID"),
    ("path", ["geometry", "points", True], "DELTA_PATCH_INVALID"),
    ("path", ["properties", "missing", "width"], "DELTA_PATCH_INVALID"),
    ("op", {}, "DELTA_PATCH_INVALID"),
    ("value", "Synthetic room", "DELTA_PATCH_NOT_CANONICAL"),
])
def test_rehashed_but_invalid_patch_cannot_bypass_replay(
    store: ReviewStore, field: str, value: object, error: str,
) -> None:
    scene_id = _synthetic_scene()["scene_id"]
    _publish(store, "probe-region", {"label": "Changed"})
    delta = store.export_delta(scene_id, 1)
    delta["patch"][0][field] = value
    _rehash(delta)
    with pytest.raises(ValueError, match=error):
        replay_review_delta(store.state(scene_id)["versions"][0], delta)


def test_wrong_source_wrong_parent_authority_and_validation_references_rejected(
    store: ReviewStore,
) -> None:
    scene_id = _synthetic_scene()["scene_id"]
    _publish(store, "probe-region", {"label": "Changed"})
    base = store.state(scene_id)["versions"][0]
    valid = store.export_delta(scene_id, 1)
    with pytest.raises(ValueError, match="DELTA_BASE_MISMATCH"):
        replay_review_delta({**base, "source_hash": "f" * 64}, valid)
    for field, value, error in (
        ("parent_version_hash", "f" * 64, "DELTA_BASE_MISMATCH"),
        ("formal_approval", True, "DELTA_AUTHORITY_INVALID"),
        ("validation_reference", {}, "DELTA_VALIDATION_REFERENCE_INVALID"),
        ("result_objects_hash", "f" * 64, "DELTA_RESULT_MISMATCH"),
    ):
        delta = copy.deepcopy(valid)
        delta[field] = value
        _rehash(delta)
        with pytest.raises(ValueError, match=error):
            replay_review_delta(base, delta)


def test_baseline_missing_version_and_scene_cannot_be_exported(store: ReviewStore) -> None:
    scene_id = _synthetic_scene()["scene_id"]
    for version, error in ((0, "DELTA_VERSION_REQUIRED"), (1, "VERSION_NOT_FOUND"),
                           (True, "VERSION_INVALID")):
        with pytest.raises(ValueError, match=error):
            store.export_delta(scene_id, version)
    with pytest.raises(ValueError, match="SCENE_NOT_FOUND"):
        store.export_delta("another-scene", 1)


def test_new_published_rows_persist_delta_only_and_reconstruct_existing_state(
    store: ReviewStore,
) -> None:
    scene = _synthetic_scene()
    scene_id = scene["scene_id"]
    published = _publish(store, "probe-region", {"label": "Changed"})
    with sqlite3.connect(store.db_path) as db:
        raw, row_hash = db.execute("SELECT payload, hash FROM versions WHERE version=1").fetchone()
    stored = json.loads(raw)
    assert set(stored) == {"storage_schema", "scene_id", "version", "delta"}
    assert stored["storage_schema"] == "workbench.scene-publication-delta.v1"
    assert row_hash == _digest(stored)
    assert stored["delta"] == store.export_delta(scene_id, 1)
    assert "probe-portal" not in raw and '"objects"' not in raw
    assert '"before"' not in raw and '"after"' not in raw and '"overlay"' not in raw
    reopened = ReviewStore(store.db_path, {scene_id: scene})
    assert reopened.state(scene_id)["versions"][1] == published
    assert reopened.state(scene_id)["objects"] == published["objects"]


def test_legacy_full_history_reads_without_migration_and_new_rows_are_compact(
    store: ReviewStore,
) -> None:
    scene = _synthetic_scene()
    scene_id = scene["scene_id"]
    published = _publish(store, "probe-region", {"label": "Legacy room"})
    # Only this disposable test database is altered to reproduce the historical
    # v1 storage representation. Existing user histories are never migrated.
    legacy_payload = json.dumps(published, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False)
    with sqlite3.connect(store.db_path) as db:
        db.execute("DROP TRIGGER versions_no_update")
        db.execute("UPDATE versions SET payload=?, hash=? WHERE version=1",
                   (legacy_payload, _digest(published)))
    reopened = ReviewStore(store.db_path, {scene_id: scene})
    assert reopened.state(scene_id)["versions"][1] == published
    assert replay_review_delta(reopened.state(scene_id)["versions"][0],
                               reopened.export_delta(scene_id, 1)) == published["overlay"]
    second = _publish(reopened, "probe-portal", {"label": "New door"}, 1)
    again = ReviewStore(store.db_path, {scene_id: scene})
    assert again.state(scene_id)["versions"][2] == second
    with sqlite3.connect(store.db_path) as db:
        rows = db.execute("SELECT payload FROM versions ORDER BY version").fetchall()
    assert rows[1][0] == legacy_payload
    assert json.loads(rows[2][0])["storage_schema"] == "workbench.scene-publication-delta.v1"
    assert "probe-region" not in rows[2][0]
