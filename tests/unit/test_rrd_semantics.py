"""Full recording comparison checks, using small synthetic Arrow/RRD fixtures."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pyarrow as pa
import pytest
import rerun as rr
from rerun.archetypes.recording_info import RecordingInfo
from rerun.chunk import Chunk

PATH = Path(__file__).resolve().parents[2] / "scripts/verify_rrd_semantics.py"
SPEC = importlib.util.spec_from_file_location("rrd_semantics_test_module", PATH)
assert SPEC is not None and SPEC.loader is not None
semantics = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = semantics
SPEC.loader.exec_module(semantics)


def _points(
    positions: list[list[float]],
    times: list[float] | None = None,
    *,
    entity: str = "/world/source",
    frames: list[int] | None = None,
) -> Chunk:
    indexes: list[Any] = []
    if times is not None:
        indexes.append(rr.TimeColumn("event_time", duration=times))
    if frames is not None:
        indexes.append(rr.TimeColumn("source_frame", sequence=frames))
    return Chunk.from_columns(entity, indexes, rr.Points3D.columns(positions=positions))


def _snapshot(chunks: list[Any], application: str = "semantic-fixture") -> dict[str, Any]:
    return semantics.canonicalize_chunks(chunks, application_id=application)


def _compare(left: list[Any], right: list[Any]) -> dict[str, Any]:
    return semantics.compare_canonical_recordings(_snapshot(left), _snapshot(right))


def test_batch_segmentation_and_stream_chunk_order_keep_all_rows_equal() -> None:
    left = [_points([[1, 2, 3], [4, 5, 6]], [0.0, 0.2])]
    first, second = _points([[1, 2, 3]], [0.0]), _points([[4, 5, 6]], [0.2])
    result = _compare(left, [second, first])
    assert result["status"] == "PASS"
    assert result["primary"]["canonical_log_row_count"] == 2
    assert result["primary"]["raw_stream_chunk_count"] == 1
    assert result["clean"]["raw_stream_chunk_count"] == 2
    assert result["different_log_row_count"] == 0


def test_tampered_position_fails() -> None:
    result = _compare([_points([[1, 2, 3]], [1.0])], [_points([[1, 2, 3.001]], [1.0])])
    assert result["status"] == "FAIL"
    assert "component_updates_sha256" in result["mismatched_fields"]


def test_tampered_source_time_one_nanosecond_fails() -> None:
    result = _compare([_points([[1, 2, 3]], [1.0])], [_points([[1, 2, 3]], [1.000000001])])
    assert result["status"] == "FAIL"
    assert "timeline_updates_sha256" in result["mismatched_fields"]


def test_missing_entity_fails() -> None:
    first = [_points([[1, 2, 3]], [1.0]), _points([[4, 5, 6]], [2.0], entity="/world/second")]
    result = _compare(first, [_points([[1, 2, 3]], [1.0])])
    assert result["status"] == "FAIL"
    assert "entity_paths_sha256" in result["mismatched_fields"]


def test_clear_updates_are_preserved() -> None:
    clear = Chunk.from_columns("/world/source", [], rr.Clear.columns(is_recursive=[True]))
    result = _compare([_points([[1, 2, 3]]), clear], [_points([[1, 2, 3]])])
    assert result["status"] == "FAIL"
    assert result["primary"]["component_update_count"] > result["clean"]["component_update_count"]


def test_equal_source_timestamp_logging_order_is_preserved() -> None:
    left = [_points([[1, 2, 3], [4, 5, 6]], [1.0, 1.0])]
    right = [_points([[4, 5, 6], [1, 2, 3]], [1.0, 1.0])]
    assert _compare(left, right)["status"] == "FAIL"


def test_static_overwrite_order_is_preserved() -> None:
    assert (
        _compare([_points([[1, 2, 3], [4, 5, 6]])], [_points([[4, 5, 6], [1, 2, 3]])])["status"]
        == "FAIL"
    )


def test_source_frame_sequence_fails_when_modified() -> None:
    result = _compare(
        [_points([[1, 2, 3]], [1.0], frames=[17])], [_points([[1, 2, 3]], [1.0], frames=[18])]
    )
    assert result["status"] == "FAIL"
    assert "timeline_updates_sha256" in result["mismatched_fields"]


def test_application_id_is_part_of_semantics() -> None:
    left, right = _snapshot([_points([[1, 2, 3]])], "a"), _snapshot([_points([[1, 2, 3]])], "b")
    assert semantics.compare_canonical_recordings(left, right)["status"] == "FAIL"


def _rewritten(chunk: Chunk, *, field_index: int, field: Any) -> Any:
    batch = chunk.to_record_batch()
    batch = batch.set_column(field_index, field, batch.column(field_index))
    return SimpleNamespace(
        entity_path=chunk.entity_path, is_static=chunk.is_static, to_record_batch=lambda: batch
    )


def test_unknown_control_is_rejected_instead_of_silently_ignored() -> None:
    chunk = _points([[1, 2, 3]])
    field = chunk.to_record_batch().schema.field(0)
    changed = pa.field("unreviewed.control", field.type, metadata=field.metadata)
    with pytest.raises(ValueError, match="unknown control"):
        _snapshot([_rewritten(chunk, field_index=0, field=changed)])


def test_unknown_column_kind_is_rejected() -> None:
    chunk = _points([[1, 2, 3]])
    batch = chunk.to_record_batch()
    field = batch.schema.field(1)
    changed = pa.field(
        field.name, field.type, metadata={**field.metadata, b"rerun:kind": b"UNKNOWN"}
    )
    with pytest.raises(ValueError, match="unknown Arrow column kind"):
        _snapshot([_rewritten(chunk, field_index=1, field=changed)])


def test_descriptor_type_metadata_changes_fail() -> None:
    left = _points([[1, 2, 3]])
    right = _points([[1, 2, 3]])
    field = right.to_record_batch().schema.field(1)
    changed = pa.field(
        field.name,
        field.type,
        metadata={**field.metadata, b"rerun:component_type": b"unreviewed.Position3D"},
    )
    assert _compare([left], [_rewritten(right, field_index=1, field=changed)])["status"] == "FAIL"


def test_negative_zero_and_nan_payloads_keep_exact_float_bits() -> None:
    assert semantics._scalar(pa.scalar(-0.0, type=pa.float32())) != semantics._scalar(
        pa.scalar(0.0, type=pa.float32())
    )
    a = pa.Array.from_buffers(
        pa.float64(), 1, [None, pa.py_buffer(bytes.fromhex("010000000000f87f"))]
    )
    b = pa.Array.from_buffers(
        pa.float64(), 1, [None, pa.py_buffer(bytes.fromhex("020000000000f87f"))]
    )
    assert semantics._scalar(a[0]) != semantics._scalar(b[0])


def test_only_known_recording_creation_property_is_excluded_and_raw_values_bound() -> None:
    a = Chunk.from_columns("/__properties", [], RecordingInfo.columns(start_time=[100]))
    b = Chunk.from_columns("/__properties", [], RecordingInfo.columns(start_time=[200]))
    result = _compare([a], [b])
    assert result["status"] == "PASS"
    assert result["primary"]["excluded_container_values"]["recording_creation_start_time_ns"] == [
        [100]
    ]
    assert result["clean"]["excluded_container_values"]["recording_creation_start_time_ns"] == [
        [200]
    ]
    c = Chunk.from_columns("/world/source_time", [], RecordingInfo.columns(start_time=[100]))
    d = Chunk.from_columns("/world/source_time", [], RecordingInfo.columns(start_time=[200]))
    assert _compare([c], [d])["status"] == "FAIL"


def test_component_empty_list_clear_is_distinct_from_missing_sparse_update() -> None:
    chunk = _points([[1, 2, 3]])
    batch = chunk.to_record_batch()
    field = batch.schema.field(1)
    empty = batch.set_column(1, field, pa.array([[]], type=field.type))
    absent = batch.set_column(1, field, pa.array([None], type=field.type))

    def wrapper(b: Any) -> Any:
        return SimpleNamespace(
            entity_path=chunk.entity_path, is_static=True, to_record_batch=lambda: b
        )

    result = _compare([wrapper(empty)], [wrapper(absent)])
    assert result["status"] == "FAIL"
    assert result["primary"]["component_update_count"] == 1
    assert result["clean"]["component_update_count"] == 0


def test_real_rrd_files_equal_with_creation_metadata_different(tmp_path: Path) -> None:
    paths = [tmp_path / "a.rrd", tmp_path / "b.rrd"]
    for path in paths:
        recording = rr.RecordingStream("semantic-file-fixture")
        recording.save(path)
        recording.set_time("event_time", duration=1.000000001)
        recording.log("world/source", rr.Points3D([[1, 2, 3]]))
        recording.flush()
        recording.disconnect()
    result = semantics.compare_rrd_semantics(*paths)
    assert result["status"] == "PASS"
    assert result["primary"]["rrd_file_sha256"] != result["clean"]["rrd_file_sha256"]
    assert result["full_recording_component_timeline_coverage"] is True
