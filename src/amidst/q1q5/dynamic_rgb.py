"""Bounded, RGB-only animated engineering run. Producer metadata is never read."""

from pathlib import Path
from types import SimpleNamespace

from amidst.q1q5.production_preflight import metadata_ref, read_pinned, strict_json


def load_dynamic_rgb(path, pin, doc, *, binary, require):
    path = Path(path)
    require(
        set(doc)
        == {
            "schema_version",
            "source_kind",
            "scene_id",
            "run_id",
            "clock_id",
            "sampling",
            "motion_kind",
            "static_ref",
            "static_file_sha256",
            "records",
            "identity_verdict",
            "gt_read",
        },
        "DYNAMIC_FIELDS",
    )
    require(
        doc["source_kind"] == "SYNTHETIC"
        and doc["gt_read"] is False
        and doc["identity_verdict"] == "UNCONFIRMED"
        and doc["motion_kind"] == "ARTICULATED_RENDERED_MOTION",
        "DYNAMIC_SCOPE",
    )
    require(
        (doc["scene_id"], doc["run_id"], doc["clock_id"])
        == (
            "ENGINEERING_DYNAMIC_SCENE",
            "ENGINEERING_DYNAMIC_RUN_20261025",
            "ENGINEERING_DYNAMIC_CLOCK",
        ),
        "DYNAMIC_SOURCE",
    )
    sampling = doc["sampling"]
    require(
        sampling
        == dict(fps=20, duration_s=8, sample_count_per_camera=160, image_size_px=[960, 540]),
        "DYNAMIC_SAMPLING",
    )
    static = strict_json(
        read_pinned(metadata_ref(path.parent, doc["static_ref"]), doc["static_file_sha256"])
    )
    require(
        set(static)
        == {
            "schema_version",
            "scene_id",
            "revision",
            "engineering_only",
            "cameras",
            "image_size_px",
            "source_blend_file_sha256",
            "gt_read",
        }
        and static["schema_version"] == "q-demo.dynamic-static.v1"
        and static["scene_id"] == doc["scene_id"]
        and static["engineering_only"] is True
        and static["gt_read"] is False
        and set(static["cameras"]) == {"A", "B"},
        "DYNAMIC_STATIC",
    )
    rows = {(r["camera_id"], r["frame_index"]): r for r in doc["records"]}
    require(
        len(rows) == len(doc["records"]) == 320
        and set(rows) == {(c, i) for c in ["A", "B"] for i in range(160)},
        "DYNAMIC_GRID",
    )
    for (_, frame), row in rows.items():
        require(
            set(row) == {"camera_id", "frame_index", "timestamp_s", "rgb_ref", "file_sha256"}
            and row["timestamp_s"] == frame / 20
            and len(row["file_sha256"]) == 64,
            "DYNAMIC_CLOCK_OR_FIELDS",
        )
        metadata_ref(path.parent, row["rgb_ref"])
    manifest = {k: doc[k] for k in ["scene_id", "run_id", "clock_id", "sampling"]}
    manifest.update(
        allowlist=[dict(role="rgb_index", file_sha256=pin)],
        static_file_sha256=doc["static_file_sha256"],
    )
    return SimpleNamespace(
        manifest=manifest,
        files={"rgb_index": {"missing": []}},
        camera_ids={"A", "B"},
        rgb_record=lambda c, i: rows.get((c, i)),
        read_rgb=lambda c, i: binary(
            metadata_ref(path.parent, rows[(c, i)]["rgb_ref"]), rows[(c, i)]["file_sha256"]
        ),
    )
