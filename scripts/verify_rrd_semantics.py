"""Compare complete data-recording rows independently of RRD chunk batching.

The original RowIds reconstruct logging order, then their absolute values are
removed. Every non-container timeline and component update remains exact.
Blueprints are bound as raw artifacts/presence, outside this recording gate.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
from rerun.chunk import Chunk, RrdReader

SCHEMA = "phase1-full-data-recording-semantic-comparison-v1"
EXCLUSIONS = (
    "ABSOLUTE_CONTAINER_ROW_IDS_AND_CHUNK_IDS_LOG_ORDER_RETAINED",
    "SDK_LOG_TIME_WALLCLOCK_INDEX_ONLY",
    "SDK_PROPERTIES_RECORDINGINFO_START_TIME_CREATION_WALLCLOCK_ONLY",
    "STORE_UUID_CONTAINER_IDENTIFIERS_ONLY_APPLICATION_ID_RETAINED",
    "CHUNK_BATCH_SEGMENTATION_AND_DERIVED_IS_SORTED_FLAGS_ONLY",
)
CASES = {
    "case1": "office/evaluation/demos/case1/reviewed.rrd",
    "case2": "scoped/evaluation/demos/case2/scoped.rrd",
    "case3": "scoped/evaluation/demos/case3/scoped.rrd",
}


def _encoded(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _hash(value: Any) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require(condition: Any, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def _metadata(value: Any, *, excluded: tuple[bytes, ...] = ()) -> list[list[str]]:
    return [
        [key.hex(), data.hex()]
        for key, data in sorted((value or {}).items())
        if key not in excluded
    ]


def _field(field: Any) -> dict[str, Any]:
    return {
        "name": field.name,
        "type": str(field.type),
        "nullable": field.nullable,
        "metadata": _metadata(field.metadata, excluded=(b"rerun:is_sorted",)),
        "children": [_field(field.type.field(index)) for index in range(field.type.num_fields)],
    }


def _scalar(value: Any) -> Any:
    """Retain typed Arrow values, including every float bit and nested null."""
    if not value.is_valid:
        return {"null": True}
    dtype = value.type
    if pa.types.is_floating(dtype):
        array = pa.array([value], type=dtype)
        return {"ieee754_little_endian": array.buffers()[1].to_pybytes().hex()}
    if pa.types.is_integer(dtype) or pa.types.is_boolean(dtype) or pa.types.is_string(dtype):
        return value.as_py()
    if pa.types.is_large_string(dtype):
        return value.as_py()
    if (
        pa.types.is_binary(dtype)
        or pa.types.is_large_binary(dtype)
        or pa.types.is_fixed_size_binary(dtype)
    ):
        return {"binary_hex": value.as_py().hex()}
    if (
        pa.types.is_list(dtype)
        or pa.types.is_large_list(dtype)
        or pa.types.is_fixed_size_list(dtype)
    ):
        return [_scalar(item) for item in value.values]
    if pa.types.is_struct(dtype):
        return [[field.name, _scalar(value[field.name])] for field in dtype]
    if pa.types.is_map(dtype):
        return [_scalar(item) for item in value.values]
    if pa.types.is_dictionary(dtype):
        return _scalar(value.value)
    if pa.types.is_timestamp(dtype) or pa.types.is_duration(dtype) or pa.types.is_time64(dtype):
        return {"exact_storage_integer": value.cast(pa.int64()).as_py()}
    if pa.types.is_date32(dtype) or pa.types.is_time32(dtype):
        return {"exact_storage_integer": value.cast(pa.int32()).as_py()}
    if pa.types.is_date64(dtype):
        return {"exact_storage_integer": value.cast(pa.int64()).as_py()}
    raise ValueError(
        "unsupported Arrow value type; complete coverage cannot be claimed: " + str(dtype)
    )


def canonicalize_chunks(chunks: Iterable[Chunk], *, application_id: str) -> dict[str, Any]:
    """Canonicalize all recording rows; reject unknown controls or lossy types.

    Splitting chunks or sparse component columns does not alter a logging row.
    RowId order is preserved for static overwrite/clear and equal-time updates.
    """
    assembled: dict[bytes, dict[str, Any]] = {}
    descriptors: dict[str, Any] = {}
    timelines: dict[str, Any] = {}
    schema_metadata: dict[str, Any] = {}
    raw_row_ids: list[str] = []
    log_times: list[int] = []
    creation_times: list[Any] = []
    chunks_seen = raw_rows = null_component_cells = retained_cells = 0
    for chunk in chunks:
        chunks_seen += 1
        batch = chunk.to_record_batch()
        raw_rows += batch.num_rows
        meta = batch.schema.metadata or {}
        _require(
            meta.get(b"rerun:entity_path", chunk.entity_path.encode()).decode()
            == chunk.entity_path,
            "chunk entity path and Arrow metadata disagree",
        )
        normalized_meta = _metadata(meta, excluded=(b"rerun:id", b"rerun:entity_path"))
        schema_metadata[_hash(normalized_meta)] = normalized_meta
        controls: list[int] = []
        index_columns: list[tuple[int, dict[str, Any]]] = []
        data_columns: list[tuple[int, dict[str, Any], bool]] = []
        for index, field in enumerate(batch.schema):
            field_meta = field.metadata or {}
            kind = field_meta.get(b"rerun:kind")
            if kind == b"control":
                _require(
                    field.name == "rerun.controls.RowId"
                    and pa.types.is_fixed_size_binary(field.type)
                    and field.type.byte_width == 16
                    and field_meta.get(b"ARROW:extension:name") == b"rerun.datatypes.TUID"
                    and json.loads(field_meta[b"ARROW:extension:metadata"]) == {"namespace": "row"},
                    "unknown control column cannot be silently excluded",
                )
                controls.append(index)
            elif kind == b"index":
                _require(
                    field_meta.get(b"rerun:index_name") == field.name.encode(),
                    "timeline name metadata disagrees",
                )
                if field.name == "log_time":
                    _require(
                        pa.types.is_timestamp(field.type) and field.type.unit == "ns",
                        "log_time exclusion requires SDK wall-clock timestamp(ns)",
                    )
                    log_times.extend(batch.column(index).cast(pa.int64()).to_pylist())
                else:
                    description = _field(field)
                    timelines[_hash(description)] = description
                    index_columns.append((index, description))
            elif kind == b"data":
                _require(
                    b"rerun:component" in field_meta and b"rerun:component_type" in field_meta,
                    "component descriptor is missing",
                )
                creation = (
                    chunk.entity_path == "/__properties"
                    and field.name == "RecordingInfo:start_time"
                )
                if creation:
                    _require(
                        chunk.is_static
                        and field_meta.get(b"rerun:component") == b"RecordingInfo:start_time"
                        and field_meta.get(b"rerun:component_type") == b"rerun.components.Timestamp"
                        and pa.types.is_list(field.type)
                        and pa.types.is_int64(field.type.value_type),
                        "creation wall-clock exclusion has an unexpected schema",
                    )
                description = _field(field)
                if not creation:
                    descriptors[_hash(description)] = description
                data_columns.append((index, description, creation))
            else:
                raise ValueError(
                    "unknown Arrow column kind; full coverage cannot be claimed: " + str(kind)
                )
        _require(len(controls) == 1, "exactly one original RowId is required to retain log order")
        _require(bool(data_columns), "recording chunk contains no component columns")
        for row in range(batch.num_rows):
            rid = batch.column(controls[0])[row].as_py()
            _require(isinstance(rid, bytes) and len(rid) == 16, "invalid original RowId")
            raw_row_ids.append(rid.hex())
            retained_times = [
                {"field": field, "value": _scalar(batch.column(index)[row])}
                for index, field in index_columns
            ]
            retained_times.sort(key=lambda item: _encoded(item["field"]))
            row_base = {
                "entity_path": chunk.entity_path,
                "static": chunk.is_static,
                "timelines": retained_times,
            }
            if rid not in assembled:
                assembled[rid] = {**row_base, "components": {}}
            else:
                _require(
                    all(assembled[rid][key] == value for key, value in row_base.items()),
                    "split original RowId changes entity/static/timeline values",
                )
            for index, field, creation in data_columns:
                value = batch.column(index)[row]
                if not value.is_valid:
                    null_component_cells += 1
                    # A null sparse cell means no update; an empty list clear remains retained.
                    continue
                if creation:
                    creation_times.append(value.as_py())
                    continue
                key = _hash(field)
                _require(
                    key not in assembled[rid]["components"],
                    "duplicate component update for one RowId",
                )
                assembled[rid]["components"][key] = {"field": field, "value": _scalar(value)}
                retained_cells += 1
    _require(bool(assembled), "recording has no canonical rows")
    rows = []
    for rid in sorted(assembled):
        row_value = assembled[rid]
        rows.append(
            {
                **row_value,
                "components": sorted(
                    row_value["components"].values(), key=lambda item: _encoded(item["field"])
                ),
            }
        )
    entity_paths = sorted({row["entity_path"] for row in rows})
    component_updates = [
        {
            "log_row_ordinal": ordinal,
            "entity_path": row["entity_path"],
            "static": row["static"],
            "timelines": row["timelines"],
            **component,
        }
        for ordinal, row in enumerate(rows)
        for component in row["components"]
    ]
    timeline_updates = [
        {"log_row_ordinal": ordinal, "entity_path": row["entity_path"], **timeline}
        for ordinal, row in enumerate(rows)
        for timeline in row["timelines"]
    ]
    canonical_schema = {
        "component_descriptors": sorted(descriptors.values(), key=_encoded),
        "timeline_descriptors": sorted(timelines.values(), key=_encoded),
        "non_container_schema_metadata": sorted(schema_metadata.values(), key=_encoded),
    }
    payload = {"application_id": application_id, "rows": rows, "schema": canonical_schema}
    return {
        "semantic_rows": rows,
        "semantic_payload_sha256": _hash(payload),
        "canonical_log_row_count": len(rows),
        "canonical_log_rows_sha256": _hash(rows),
        "component_update_count": retained_cells,
        "component_updates_sha256": _hash(component_updates),
        "timeline_update_count": len(timeline_updates),
        "timeline_updates_sha256": _hash(timeline_updates),
        "semantic_schema_sha256": _hash(canonical_schema),
        "entity_count": len(entity_paths),
        "entity_paths_sha256": _hash(entity_paths),
        "timeline_descriptors": canonical_schema["timeline_descriptors"],
        "component_descriptor_count": len(descriptors),
        "application_id": application_id,
        "raw_stream_chunk_count": chunks_seen,
        "raw_stream_row_count": raw_rows,
        "excluded_container_values": {
            "original_row_id_cell_count": len(raw_row_ids),
            "original_row_ids_sha256": _hash(raw_row_ids),
            "sdk_log_time_cell_count": len(log_times),
            "sdk_log_time_values_sha256": _hash(log_times),
            "sdk_log_time_min_ns": min(log_times, default=None),
            "sdk_log_time_max_ns": max(log_times, default=None),
            "recording_creation_start_time_ns": creation_times,
        },
        "sparse_absent_component_cell_count": null_component_cells,
        "full_recording_component_timeline_coverage": True,
        "log_order_static_clears_equal_source_time_update_order_retained": True,
        "declared_metadata_exclusions": list(EXCLUSIONS),
    }


def canonicalize_recording(path: Path) -> dict[str, Any]:
    before = _digest(path)
    reader = RrdReader(path)
    recordings = reader.recordings()
    _require(len(recordings) == 1, "original acceptance requires exactly one data recording")
    entry = recordings[0]
    snapshot = canonicalize_chunks(reader.stream(store=entry), application_id=entry.application_id)
    _require(_digest(path) == before, "RRD file changed during independent semantic read")
    snapshot.update(
        {
            "path": str(path.resolve()),
            "rrd_file_sha256": before,
            "recording_count": len(recordings),
            "raw_reader_store_count": len(reader.store(store=entry)),
            "raw_recording_store_uuid": entry.recording_id,
            "blueprint_store_count": len(reader.blueprints()),
            "raw_blueprint_stores": [
                {
                    "kind": row.kind,
                    "application_id": row.application_id,
                    "store_uuid": row.recording_id,
                }
                for row in reader.blueprints()
            ],
            "blueprint_presence_and_entire_rrd_bytes_bound": True,
            "blueprint_semantics_claimed": False,
        }
    )
    return snapshot


def compare_canonical_recordings(primary: dict[str, Any], clean: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "semantic_payload_sha256",
        "canonical_log_row_count",
        "canonical_log_rows_sha256",
        "component_update_count",
        "component_updates_sha256",
        "timeline_update_count",
        "timeline_updates_sha256",
        "semantic_schema_sha256",
        "entity_count",
        "entity_paths_sha256",
        "component_descriptor_count",
        "application_id",
        "timeline_descriptors",
    )
    mismatched = [field for field in fields if primary[field] != clean[field]]
    a, b = primary["semantic_rows"], clean["semantic_rows"]
    different_rows = [
        index
        for index in range(max(len(a), len(b)))
        if index >= len(a) or index >= len(b) or a[index] != b[index]
    ]
    _require(
        primary["full_recording_component_timeline_coverage"] is True
        and clean["full_recording_component_timeline_coverage"] is True,
        "complete recording coverage is absent",
    )
    return {
        "schema_version": SCHEMA,
        "status": "PASS" if not mismatched and not different_rows else "FAIL",
        "comparison_scope": (
            "COMPLETE_SINGLE_DATA_RECORDING_ALL_LOG_ROWS_COMPONENTS_SOURCE_TIMELINES"
        ),
        "full_recording_component_timeline_coverage": True,
        "source_event_time_and_sequence_values_exact": True,
        "static_clear_and_equal_time_update_order_retained": True,
        "declared_metadata_exclusions": list(EXCLUSIONS),
        "mismatched_fields": mismatched,
        "different_log_row_count": len(different_rows),
        "first_different_rows": [
            {
                "log_row_ordinal": index,
                "primary_entity_path": a[index]["entity_path"] if index < len(a) else None,
                "clean_entity_path": b[index]["entity_path"] if index < len(b) else None,
                "primary_row_sha256": _hash(a[index]) if index < len(a) else None,
                "clean_row_sha256": _hash(b[index]) if index < len(b) else None,
            }
            for index in different_rows[:10]
        ],
        "primary": {key: value for key, value in primary.items() if key != "semantic_rows"},
        "clean": {key: value for key, value in clean.items() if key != "semantic_rows"},
        "blueprint_semantics_claimed": False,
    }


def compare_rrd_semantics(primary_rrd: Path, clean_rrd: Path) -> dict[str, Any]:
    return compare_canonical_recordings(
        canonicalize_recording(primary_rrd), canonicalize_recording(clean_rrd)
    )


def verify_joint_rrd_semantics(
    primary_release: Path, clean_release: Path, master_path: Path
) -> dict[str, Any]:
    master_sha = _digest(master_path)
    master = json.loads(master_path.read_bytes())
    cases = [
        {
            "case_id": case_id,
            "relative_rrd_path": relative,
            **compare_rrd_semantics(primary_release / relative, clean_release / relative),
        }
        for case_id, relative in CASES.items()
    ]
    _require(_digest(master_path) == master_sha, "master changed during independent recording read")
    return {
        "schema_version": SCHEMA,
        "status": "PASS" if all(case["status"] == "PASS" for case in cases) else "FAIL",
        "master_file_sha256": master_sha,
        "source_asset_sha256": master["source_sha256"],
        "verifier_file_sha256": _digest(Path(__file__)),
        "all_case_ids": list(CASES),
        "cases": cases,
        "full_recording_component_timeline_coverage": True,
        "declared_metadata_exclusions": list(EXCLUSIONS),
        "sdk_versions": {
            "rerun_sdk": importlib.metadata.version("rerun-sdk"),
            "pyarrow": pa.__version__,
        },
        "all_source_and_original_failure_receipts_preserved": True,
        "rrd_files_modified": False,
        "inference_or_render_executed": False,
        "ground_truth_read": False,
        "blueprint_semantics_claimed": False,
        "formal_acceptance_granted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("primary-release", "clean-release", "master", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    _require(not args.output.exists(), "fresh independent semantic receipt required")
    receipt = verify_joint_rrd_semantics(args.primary_release, args.clean_release, args.master)
    args.output.write_text(json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(receipt["status"])
    if receipt["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
