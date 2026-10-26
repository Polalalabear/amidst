# ruff: noqa: E501  (violation descriptions and fixture prose are single-line strings)
"""Builds the SYNTHETIC conformance fixtures (valid set + violation patches).

Everything here is invented: ids, hashes, cameras and timings carry no demo storyline, no Ground
Truth and no production route. ``python build_fixtures.py`` rewrites ``SYNTHETIC/valid/`` and
``SYNTHETIC/violations.json``; the unit test regenerates them and fails if they drifted.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from amidst.evaluation.q1q5_conformance import canonical_sha256

HERE = Path(__file__).resolve().parent
OUT = HERE / "SYNTHETIC"
RUN, CLOCK, SCENE, REV = "RUN_X", "CLOCK_X", "SCENE_SYN", "rSYN"
OBS_SEG = (
    "0123456789abcdef"  # placeholder: finalize() swaps in the index-key segment (contract §2.2)
)
WALL0 = "2026-11-01T13:00:00+08:00"
SRC_US = 200_000  # source_frame_interval_us (5 fps)
STRIDE = 2  # stride_samples: the index grid is every second source frame
IV = STRIDE * SRC_US  # index_interval_us = 400000
GAP_US = (
    1_200_000  # link_max_gap_us: 3 x IV, so link_max_gap_samples = 2 (all SYNTHETIC, not proposals)
)
DT_US = 9_200_000  # decision_time_us: last linked A:40 (8.0 s) + link_max_gap_us
ENTRY_US = 13_600_000  # entry_timestamp_us of the evidence that is switched to
WINDOW = [8_400_000, 14_400_000]  # candidate window: first unlinked cell + search window (6 s)


def H(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# tracking_scope_sha256 of a SYNTHETIC tracking-scope file (section 5.1 D81: raw file bytes; the file
# itself is not part of the fixture set, so only the pin's equality across response / journal is judged)
TS_SHA = H("SYNTHETIC-tracking-scope")


RECORD_ORDER = [
    ("CAM_A", 0),
    ("CAM_A", 2),
    ("CAM_A", 3),
    ("CAM_A", 4),
    ("CAM_A", 6),
    ("CAM_A", 40),
    ("CAM_B", 0),
    ("CAM_B", 2),
    ("CAM_B", 68),
    ("CAM_C", 0),
]


def ri(camera: str, frame: int) -> str:
    """JSON path of a record in detection_index.records.jsonl."""

    return f"$[{RECORD_ORDER.index((camera, frame))}]"


def wall(seconds: int) -> str:
    return f"2026-11-01T13:{seconds // 60:02d}:{seconds % 60:02d}+08:00"


# ----------------------------------------------------------------------------- common pieces

PROV = {
    "producer": "SYNTHETIC-producer",
    "producer_version": "0",
    "gt_read": False,
    "input_refs": ["index:SYNTHETIC"],
}


def scope(
    requested: dict[str, Any] | None,
    ranges: list[dict[str, Any]] | None,
    coverage: dict[str, Any] | None,
    cameras: list[str] | None,
    full: bool = True,
    tracking: str | None = None,
) -> dict[str, Any]:
    s: dict[str, Any] = {
        "scene_id": SCENE,
        "scene_revision": REV,
        "run_ids": [RUN],
        "clock_ids": [CLOCK],
        "clock_mapping_sha256": "@clock_sha",
        "requested_time": requested,
        "resolved_source_ranges_us": ranges,
        "time_coverage": coverage,
        "camera_ids": cameras,
        "detection_index_id": "@index_id" if full else None,
        "detection_index_sha256": "@index_sha" if full else None,
        "region_graph_sha256": "@rg_sha" if full else None,
        "camera_graph_sha256": "@cg_sha" if full else None,
        "tracking_scope_sha256": tracking,  # section 2.3: null when unused, never omitted
        "class_map_sha256": "@classmap_sha" if full else None,
        "color_method_version": "@color_ver" if full else None,
        "parameter_set_id": "@param_id",
        "parameter_set_sha256": "@param_sha",
    }
    return s


def envelope(
    kind: str, status: str, reason: str | None, sc: dict[str, Any], **kw: Any
) -> dict[str, Any]:
    base = {
        "schema_version": f"q-demo.{kind}.v1",
        "status": status,
        "reason": reason,
        "reasons": [reason] if reason else [],
        "resolved_scope": sc,
        "identity_verdict": "UNCONFIRMED",
        "llm_parse_used": False,
        "agent_attempted": False,
        "agent_used": False,
        "decision_source": None,
        "fallback_used": False,
        "fallback_reason": None,
        "provenance": copy.deepcopy(PROV),
        "stats": {"latency_ms": {"total": 12}},
    }
    base.update(kw)
    return base


def wall_req(a: int, b: int) -> dict[str, Any]:
    return {"kind": "WALL", "wall_range": [wall(a), wall(b)]}


def complete(a: int, b: int) -> tuple[dict, list, dict]:
    return (
        wall_req(a, b),
        [{"run_id": RUN, "range_us": [a * 1_000_000, b * 1_000_000]}],
        {"coverage_complete": True, "uncovered_wall_ranges": []},
    )


# ----------------------------------------------------------------------------- static documents


def graphs() -> dict[str, Any]:
    regions = [
        ("REG_1", "CORRIDOR_SEGMENT"),
        ("REG_2", "CORNER"),
        ("REG_3", "CORRIDOR_SEGMENT"),
        ("REG_4", "ROOM"),
        ("REG_5", "ROOM"),
    ]
    rg = {
        "schema_version": "q-demo.region-graph.v1",
        "graph_id": "@",
        "scene_id": SCENE,
        "scene_revision": REV,
        "scene_static_sha256": H("scene-static"),
        "approval_status": "APPROVED",
        "approval_ref": "SYNTHETIC-APPROVAL",
        "regions": [
            {
                "region_id": r,
                "kind": k,
                "floor_id": "FLOOR_1F",
                "walk_ids": [f"WALK_{r}"],
                "polygon_ref": f"poly:{r}",
                "polygon_sha256": H(r),
            }
            for r, k in regions
        ],
        "edges": [
            {
                "edge_id": "E_1_2",
                "regions": ["REG_1", "REG_2"],
                "via": {"kind": "ADJACENT", "ref": "boundary:1-2"},
                "direction": "BIDIRECTIONAL",
                "state": "OPEN",
                "traversability": "APPROVED_WALKABLE",
                "basis_refs": ["basis:1"],
            },
            {
                "edge_id": "E_2_3",
                "regions": ["REG_2", "REG_3"],
                "via": {"kind": "ADJACENT", "ref": "boundary:2-3"},
                "direction": "BIDIRECTIONAL",
                "state": "OPEN",
                "traversability": "APPROVED_WALKABLE",
                "basis_refs": ["basis:2"],
            },
            {
                "edge_id": "E_3_4",
                "regions": ["REG_3", "REG_4"],
                "via": {"kind": "PORTAL", "ref": "PORTAL_SYN"},
                "direction": "BIDIRECTIONAL",
                "state": "OPEN",
                "traversability": "TOPOLOGICAL_ONLY",
                "basis_refs": ["basis:3"],
            },
            {
                "edge_id": "E_2_5",
                "regions": ["REG_2", "REG_5"],
                "via": {"kind": "ADJACENT", "ref": "boundary:2-5"},
                "direction": "BIDIRECTIONAL",
                "state": "OPEN",
                "traversability": "APPROVED_WALKABLE",
                "basis_refs": ["basis:4"],
            },
        ],
        "inputs": [{"ref": "scene_static:SYNTHETIC", "sha256": H("scene-static")}],
        "content_sha256": "@",
    }
    roi = [[0, 300], [80, 300], [80, 540], [0, 540]]
    exits = {
        "CAM_A": "E_1_2",
        "CAM_B": "E_2_3",
        "CAM_C": "E_3_4",
        "CAM_D": "E_1_2",
        "CAM_E": "E_2_5",
    }
    covers = {
        "CAM_A": ("REG_1", None),
        "CAM_B": ("REG_3", 6.0),
        "CAM_C": ("REG_4", 4.0),
        "CAM_D": ("REG_1", 3.5),
        "CAM_E": ("REG_5", None),
    }
    cams = []
    for cam, (reg, area) in covers.items():
        cams.append(
            {
                "camera_id": cam,
                "calibration_sha256": H(f"calib-{cam}"),
                "covered_regions": [
                    {
                        "region_id": reg,
                        "basis": "STATIC_VISIBILITY_INDEX",
                        "visibility_ref": f"vis:{cam}",
                        "visible_area_m2": area,
                    }
                ],
                "exit_zones": [  # D71: every camera has at least one exit zone
                    {
                        "exit_zone_id": f"{cam}:EXIT_1",
                        "roi_polygon_px": roi,
                        "leads_to_edge_ids": [exits[cam]],
                        "mapping_basis": "MANUAL_ON_STATIC_FRAME",
                        "static_frame_ref": f"static:{cam}",
                        "static_frame_sha256": H(f"static-{cam[-1]}"),
                    }
                ],
                "entry_zones": (
                    [{"entry_zone_id": f"{cam}:ENTRY_1", "roi_polygon_px": roi}]
                    if cam in ("CAM_B", "CAM_C", "CAM_E")
                    else []
                ),
            }
        )

    def tr(tid, to, entry, regs, edges, relation, trav, area=None):
        return {
            "transition_id": tid,
            "from_camera_id": "CAM_A",
            "to_camera_id": to,
            "via_exit_zone_ids": ["CAM_A:EXIT_1"],
            "to_entry_zone_ids": entry,
            "region_path": regs,
            "edge_path": edges,
            "relation": relation,
            "region_hops": len(regs) - 1,
            "path_traversability": trav,
            "path_has_unknown_state": False,
            "ranking_area_m2": area,
            "ranking_area_refs": [f"area:{tid}"] if area is not None else [],
            "nominal_path_length_m": None,
            "basis_refs": ["basis:t"],
        }

    cg = {
        "schema_version": "q-demo.camera-transition-graph.v1",
        "graph_id": "@",
        "scene_id": SCENE,
        "scene_revision": REV,
        "region_graph_sha256": "@",
        "camera_catalog_sha256": H("catalog"),
        "approval_status": "APPROVED",
        "approval_ref": "SYNTHETIC-APPROVAL",
        "cameras": cams,
        "transitions": [
            tr("T_A_D", "CAM_D", [], ["REG_1"], [], "OVERLAP", "APPROVED_WALKABLE", 3.5),
            tr(
                "T_A_B",
                "CAM_B",
                ["CAM_B:ENTRY_1"],
                ["REG_1", "REG_2", "REG_3"],
                ["E_1_2", "E_2_3"],
                "BLIND_GAP",
                "APPROVED_WALKABLE",
                6.0,
            ),
            tr(
                "T_A_E",
                "CAM_E",
                ["CAM_E:ENTRY_1"],
                ["REG_1", "REG_2", "REG_5"],
                ["E_1_2", "E_2_5"],
                "BLIND_GAP",
                "APPROVED_WALKABLE",
            ),
            tr(
                "T_A_C",
                "CAM_C",
                ["CAM_C:ENTRY_1"],
                ["REG_1", "REG_2", "REG_3", "REG_4"],
                ["E_1_2", "E_2_3", "E_3_4"],
                "BLIND_GAP",
                "TOPOLOGICAL_ONLY",
                4.0,
            ),
        ],
        "inputs": [{"ref": "scene_static:SYNTHETIC", "sha256": H("scene-static")}],
        "content_sha256": "@",
    }
    return {"region_graph.json": rg, "camera_graph.json": cg}


def index_files() -> dict[str, Any]:
    full = [[0, 60_000_000]]
    per = [
        {
            "camera_id": c,
            "sampled_ranges_us": full,
            "inferred_ranges_us": [] if c == "CAM_C" else full,
            "not_inferred": [{"range_us": [0, 60_000_000], "reason": "MODEL_NOT_RUN"}]
            if c == "CAM_C"
            else [],
            "source_frame_interval_us": SRC_US,
            "stride_samples": STRIDE,
            "index_interval_us": IV,
            "index_grid_origin_frame": 0,
        }
        for c in ("CAM_A", "CAM_B", "CAM_C", "CAM_D", "CAM_E")
    ]
    manifest = {
        "schema_version": "q-demo.detection-index.v1",
        "index_id": "@",
        "scene_id": SCENE,
        "scene_revision": REV,
        "run_id": RUN,
        "clock_id": CLOCK,
        "rgb_index_sha256": H("rgb-index"),
        "detector": {
            "family": "SYNTHETIC-DETECTOR",
            "variant": "synthetic-v0",
            "framework": "synthetic",
            "framework_version": "0",
            "code_source": {"repo": "synthetic/none", "commit": "0" * 40},
            "weights_file": "synthetic.weights",
            "weights_file_bytes": 1234,
            "weights_file_sha256": H("weights"),
            "weights_source": "synthetic://none",
            "weights_license": {"code": "SYNTHETIC", "training_data_terms": "UNKNOWN"},
            "load": {"strict": True, "num_classes": 80},
            "config_sha256": H("config"),
            "class_map": {
                "version": "synthetic-classes-v1",
                "num_classes": 80,
                "source_file_sha256": H("class-map-source"),
                "content_sha256": H("class-map"),
            },
            "input_preprocess": {
                "resize_policy": "synthetic",
                "input_size_px": [640, 640],
                "color": "RGB",
                "scale": "1/255",
                "dtype": "FP32",
            },
            "postprocess": {"top_k_queries": 300},
            "index_score_floor": 0.11,
            "nms": {"applied": False, "iou": None},
            "device": "cpu",
        },
        "color_method": {
            "version": "synthetic-hsv-v0",
            "content_sha256": H("color-method"),
            "applies_to_classes": ["person"],
            "color_vocabulary": {
                "version": "colors-syn",
                "labels": ["red", "blue"],
                "content_sha256": H("colors"),
            },
        },
        "sampling": {"policy": "EVERY_NTH_SAMPLE", "stride_samples": STRIDE, "per_camera": per},
        "records_ref": "detection_index.records.jsonl",
        "records_file_sha256": "@",
        "content_sha256": "@",
        "provenance": {"producer": "SYNTHETIC-indexer", "producer_version": "0", "gt_read": False},
    }

    def color(red: str, blue: str, reason: str | None = None) -> dict[str, Any]:
        return {
            "method_version": "synthetic-hsv-v0",
            "crop_box_xyxy_px": [412.0, 180.5, 470.2, 240.0],
            "crop_pixels": 3500,
            "hsv_stats": {"hue_hist": [0.0, 0.1], "sat_mean": 0.7, "val_mean": 0.6},
            "verdicts": {"red": red, "blue": blue},
            "unknown_reason": reason,
        }

    def obs(cam: str, f: int, n: int) -> str:
        return f"obs:{OBS_SEG}:{cam}:{f}:{n}"

    def rec(cam, f, state, dets, reason=None, rgb=True):
        return {
            "frame_ref": f"frame:{RUN}:{cam}:{f}",
            "camera_id": cam,
            "frame_index": f,
            "timestamp_us": f * 200_000,
            "rgb_file_sha256": H(f"rgb-{cam}-{f}") if rgb else None,
            "frame_state": state,
            "state_reason": reason,
            "detections": dets,
        }

    def person(
        cam: str, f: int, box: list[float], score: float, clr: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "observation_id": obs(cam, f, 0),
            "class_id": 0,
            "class_label": "person",
            "bbox_xyxy_px": box,
            "score": score,
            "color": clr,
        }

    # Grid = every second frame from 0 (stride 2). Odd frames are off the grid -> NOT_SAMPLED;
    # grid frames are INFERRED / NOT_INFERRED / MISSING, never NOT_SAMPLED (contract section 4.4).
    records = [
        rec(
            "CAM_A",
            0,
            "INFERRED",
            [
                person("CAM_A", 0, [412.0, 180.5, 470.2, 355.0], 0.91, color("STRONG", "NONE")),
                {
                    "observation_id": obs("CAM_A", 0, 1),
                    "class_id": 2,
                    "class_label": "car",
                    "bbox_xyxy_px": [10.0, 20.0, 200.0, 120.0],
                    "score": 0.55,
                    "color": None,
                },
            ],
        ),
        rec("CAM_A", 2, "INFERRED", []),
        rec("CAM_A", 3, "NOT_SAMPLED", None),
        rec("CAM_A", 4, "MISSING", None, rgb=False),
        rec(
            "CAM_A",
            6,
            "INFERRED",
            [person("CAM_A", 6, [420.0, 182.0, 478.0, 357.0], 0.9, color("STRONG", "NONE"))],
        ),
        rec(
            "CAM_A",
            40,
            "INFERRED",
            [person("CAM_A", 40, [600.0, 190.0, 660.0, 360.0], 0.88, color("STRONG", "NONE"))],
        ),
        rec(
            "CAM_B",
            0,
            "INFERRED",
            [person("CAM_B", 0, [300.0, 100.0, 360.0, 260.0], 0.8, color("NONE", "STRONG"))],
        ),
        rec(
            "CAM_B",
            2,
            "INFERRED",
            [
                person(
                    "CAM_B",
                    2,
                    [300.0, 100.0, 360.0, 260.0],
                    0.3,
                    color("UNKNOWN", "UNKNOWN", "LOW_LIGHT_OR_SATURATION"),
                )
            ],
        ),
        rec(
            "CAM_B",
            68,
            "INFERRED",
            [person("CAM_B", 68, [310.0, 110.0, 372.0, 270.0], 0.84, color("STRONG", "NONE"))],
        ),
        rec("CAM_C", 0, "NOT_INFERRED", None, reason="MODEL_NOT_RUN"),
    ]
    return {"detection_index.json": manifest, "detection_index.records.jsonl": records}


PARAM_ORDER = [  # index in parameters[]; violation cases patch by position
    "index_score_floor",
    "top_k",
    "switch_min_presence",
    "agent_max_rounds",
    "agent_total_budget_ms",
    "q3_max_llm_attempts",
    "link_max_gap_us",
    "link_max_gap_samples",
    "session_max_agent_rounds",
    "research_interval_us",
]


def pi(name: str) -> str:
    return f"$.parameters[{PARAM_ORDER.index(name)}].value"


def parameter_set() -> dict[str, Any]:
    """q-demo.parameter-set.v1 (contract section 11). Values are arbitrary SYNTHETIC numbers."""

    values = {
        "index_score_floor": (0.11, "score"),
        "top_k": (4, "count"),
        "switch_min_presence": ("MATCH_STRONG", None),
        "agent_max_rounds": (6, "count"),
        "agent_total_budget_ms": (9000, "ms"),
        "q3_max_llm_attempts": (2, "count"),
        "link_max_gap_us": (GAP_US, "us"),
        "link_max_gap_samples": (GAP_US // IV - 1, "index_cells"),  # derived: gap_us / interval - 1
        "session_max_agent_rounds": (12, "count"),
        "research_interval_us": (IV, "us"),
    }
    return {
        "schema_version": "q-demo.parameter-set.v1",
        "parameter_set_id": "@",
        "applies_to": {
            "scene_revision": REV,
            "run_ids": [RUN],
            "detection_index_ids": ["@index_id"],
            "index_interval_us": IV,
        },
        "parameters": [
            {
                "name": name,
                "value": values[name][0],
                "unit": values[name][1],
                "status": "APPROVED",
                "proposed_by": "SYNTHETIC-NOT-A-PROPOSAL",
                "proposal_ref": None,
            }
            for name in PARAM_ORDER
        ],
        "approval": {
            "status": "APPROVED",
            "approved_by": "SYNTHETIC",
            "approval_ref": "SYNTHETIC-APPROVAL",
        },
        "content_sha256": "@",
    }


def static_docs() -> dict[str, Any]:
    files = {
        "clock_mapping.json": {
            "schema_version": "q-demo.clock-mapping.v1",
            "run_id": RUN,
            "clock_id": CLOCK,
            "mapping_kind": "DECLARED_DEMO_CLOCK",
            "timezone": "Asia/Taipei",
            "wall_origin": WALL0,
            "t0_us": 0,
            "mapping_version": "syn-1",
            "declaration_source": "SYNTHETIC fixture config",
            "rate": 1,
            "source_duration_us": 60_000_000,
            "declared_by": "SYNTHETIC",
            "declared_at": "2026-10-20T00:00:00+08:00",
            "content_sha256": "@",
        },
        "parameter_set.json": parameter_set(),
        "supported_classes.json": {
            "schema_version": "q1q5-conformance.supported-classes.v1",
            "class_labels": ["person", "car", "bicycle"],
            "aliases": {"車": "car", "汽車": "car", "人": "person"},
            "color_labels": ["red", "blue"],
        },
    }
    files.update(graphs())
    files.update(index_files())
    return files


# ----------------------------------------------------------------------------- Q1


def q1_request(cls="car", color=None, score=0.2, time=None, cams=("CAM_A", "CAM_B")):
    return {
        "schema_version": "q-demo.q1-request.v1",
        "session_ref": "sess-syn",
        "scene_id": SCENE,
        "run_ids": [RUN],
        "time": time or wall_req(0, 10),
        "condition": {
            "class_label": cls,
            "min_count_per_frame": 1,
            "color": color,
            "query_min_score": score,
        },
        "camera_ids": list(cams),
        "region_ids": None,
        "page_size": 12,
        "cursor": None,
        "origin": "MANUAL",
    }


def cov(n=4):
    return {
        "evaluated_frames": n,
        "not_sampled_frames": 0,
        "not_inferred_frames": 0,
        "missing_frames": 0,
    }


def q1_results():
    def result(cam, rank, start, end):
        return {
            "camera_id": cam,
            "rank": rank,
            "matched_segments": [
                {
                    "range_us": [start, end],
                    "matched_frames": 2,
                    "evaluated_frames": 2,
                    "representative": {
                        "frame_ref": f"frame:{RUN}:{cam}:{start // 200000}",
                        "observation_ids": [f"obs:{OBS_SEG}:{cam}:{start // 200000}:0"],
                        "media_token": f"media-SYN-{cam}",
                    },
                }
            ],
            "coverage": cov(),
        }

    return [result("CAM_A", 1, 0, 400_000), result("CAM_B", 2, 400_000, 800_000)]


def q1_response(
    cls="car",
    color=None,
    score=0.2,
    status="READY",
    reason=None,
    results=None,
    no_match=None,
    not_eval=None,
    time=None,
    supported_ref=None,
):
    req, ranges, cv = time or complete(0, 10)
    cond = {"class_label": cls, "min_count_per_frame": 1, "color": color, "query_min_score": score}
    results = [] if results is None else results
    return envelope(
        "q1-response".replace("-response", "-response"),
        status,
        reason,
        scope(req, ranges, cv, ["CAM_A", "CAM_B"]),
        query_id="q1-" + H(f"{cls}{color}{status}")[:16],
        query_sha256=H(f"q1:{cls}:{color}:{status}"),
        normalized_condition=cond,
        results=results,
        no_match_cameras=no_match or [],
        not_evaluated_cameras=not_eval or [],
        results_total=len(results),
        returned_count=len(results),
        next_cursor=None,
        ranking_basis=["first_match_us_asc", "camera_id"],
        supported_classes_ref=supported_ref,
    )


def q1_files() -> dict[str, Any]:
    nm = [
        {
            "camera_id": c,
            "coverage": {
                "evaluated_frames": 4,
                "not_sampled_frames": 0,
                "not_inferred_frames": 0,
                "missing_frames": 0,
            },
        }
        for c in ("CAM_A", "CAM_B")
    ]
    partial_time = (
        wall_req(0, 1800),
        [{"run_id": RUN, "range_us": [0, 60_000_000]}],
        {"coverage_complete": False, "uncovered_wall_ranges": [[wall(60), wall(1800)]]},
    )
    oor_req = {
        "kind": "WALL",
        "wall_range": ["2026-11-01T14:00:00+08:00", "2026-11-01T14:10:00+08:00"],
    }
    oor_time = (
        oor_req,
        [],
        {"coverage_complete": False, "uncovered_wall_ranges": [list(oor_req["wall_range"])]},
    )
    red = {"label": "red", "min_verdict": "STRONG"}
    f: dict[str, Any] = {
        "q1_ready.request.json": q1_request(),
        "q1_ready.response.json": q1_response(results=q1_results()),
        "q1_nomatch.request.json": q1_request("bicycle"),
        "q1_nomatch.response.json": q1_response("bicycle", status="NO_MATCH", no_match=nm),
        "q1_partial.request.json": q1_request(time=wall_req(0, 1800)),
        "q1_partial.response.json": q1_response(
            status="PARTIAL", reason="TIME_SCOPE_PARTIAL", results=q1_results(), time=partial_time
        ),
        "q1_oor.request.json": q1_request(time=oor_req),
        "q1_oor.response.json": q1_response(
            status="OUT_OF_RANGE", reason="TIME_SCOPE_OUT_OF_RANGE", time=oor_time
        ),
        "q1_unsupported.request.json": q1_request("tree"),
        "q1_unsupported.response.json": q1_response(
            "tree",
            status="UNSUPPORTED_CLASS",
            reason="CLASS_NOT_IN_CLASS_MAP",
            supported_ref="supported-classes:syn-v1",
        ),
        "q1_color_car.request.json": q1_request("car", red),
        "q1_color_car.response.json": q1_response(
            "car", red, status="UNSUPPORTED_CONDITION", reason="COLOR_ONLY_FOR_PERSON"
        ),
        "q1_belowfloor.request.json": q1_request(score=0.05),
        "q1_belowfloor.response.json": {
            "error_code": "FORBIDDEN_INFERENCE_INPUT",
            "http_status": 422,
            "message": "query_min_score is below index_score_floor",
        },
    }
    f["q1_ready.explanation.json"] = {
        "schema_version": "q-demo.explanation.v1",
        "explains_output_sha256": "@q1_ready_out",
        "text": "CAM_A 與 CAM_B 在查詢時段內有取樣影格符合條件；這只是條件相符的候選。",
        "cited_refs": ["CAM_A", "CAM_B", "READY"],
        "fallback_reason": None,
        "content_sha256": "@",
    }
    return f


# ----------------------------------------------------------------------------- Q3


def q3_files() -> dict[str, Any]:
    text = "穿紅衣服的人在下午 1 點到 1:30 經過哪裡？"

    def req() -> dict[str, Any]:
        return {
            "schema_version": "q-demo.q3-parse-request.v1",
            "session_ref": "sess-syn",
            "text": text,
            "locale": "zh-TW",
            "context": {"scene_id": SCENE, "run_ids": [RUN], "clock_mapping_sha256": "@clock_sha"},
            "parser_mode": "LLM_WITH_RULE_FALLBACK",
        }

    q2 = q2_request("RULE_ONLY")

    def call(attempts: int) -> dict[str, Any]:
        return {
            "model": "synthetic-llm",
            "model_digest": H("digest"),
            "prompt_sha256": H("prompt"),
            "prompt_ref": "prompt:syn-1",
            "raw_output_sha256": H("raw"),
            "attempts": attempts,
            "validation_errors": [],
        }

    def sc() -> dict[str, Any]:
        return scope(None, None, None, None, full=False)

    return {
        "q3_llm.request.json": req(),
        "q3_llm.llm_output.json": {
            "schema_version": "q-demo.q3-llm-output.v1",
            "intent": "FIND_PERSON",
            "class_term": "人",
            "color_term": "紅",
            "time_literal": {"start": "下午 1 點", "end": "1:30", "date": None},
            "camera_terms": [],
            "region_terms": [],
            "needs_clarification": False,
            "clarification_question": None,
        },
        "q3_llm.response.json": envelope(
            "q3-parse-response",
            "PARSED",
            None,
            sc(),
            llm_parse_used=True,
            parsed_by="LLM",
            structured_query=q2,
            unresolved_terms=[],
            clarification=None,
            llm_call=call(1),
        ),
        "q3_fallback.request.json": {**req(), "session_ref": "sess-syn-2"},
        "q3_fallback.response.json": envelope(
            "q3-parse-response",
            "PARSED",
            None,
            sc(),
            fallback_used=True,
            fallback_reason="PROVIDER_TIMEOUT",
            parsed_by="RULE",
            structured_query=q2,
            unresolved_terms=[],
            clarification=None,
            llm_call={**call(2), "raw_output_sha256": None},
        ),
        "q3_noclock.request.json": {
            **req(),
            "text": "下午 1 點到 1:30 的人在哪裡？",
            "context": {"scene_id": SCENE, "run_ids": [RUN], "clock_mapping_sha256": None},
            "parser_mode": "RULE_ONLY",
        },
        "q3_noclock.llm_output.json": {  # the rule parser's intermediate result has the LLM's shape
            "schema_version": "q-demo.q3-llm-output.v1",
            "intent": "FIND_PERSON",
            "class_term": "人",
            "color_term": None,
            "time_literal": {"start": "下午 1 點", "end": "1:30", "date": None},
            "camera_terms": [],
            "region_terms": [],
            "needs_clarification": True,
            "clarification_question": "沒有時鐘對照，要用哪個時間基準？",
        },
        "q3_noclock.response.json": envelope(
            "q3-parse-response",
            "NEEDS_CLARIFICATION",
            "CLOCK_MAPPING_MISSING",
            {**sc(), "clock_ids": None, "clock_mapping_sha256": None},
            parsed_by="RULE",
            structured_query=None,
            unresolved_terms=[],
            clarification={"question": "沒有時鐘對照，要用哪個時間基準？", "options": ["source"]},
            llm_call=None,
        ),
        "q3_clarify.request.json": {**req(), "text": "那個人去哪了？"},
        "q3_clarify.response.json": envelope(
            "q3-parse-response",
            "NEEDS_CLARIFICATION",
            None,
            sc(),
            llm_parse_used=True,
            parsed_by="LLM",
            structured_query=None,
            unresolved_terms=["那個人"],
            clarification={"question": "要找哪一種外觀的人？", "options": ["red", "blue"]},
            llm_call=call(1),
        ),
    }


# ----------------------------------------------------------------------------- Q2 / Q5


def q2_request(mode: str) -> dict[str, Any]:
    return {
        "schema_version": "q-demo.q2-request.v1",
        "session_ref": "sess-syn",
        "scene_id": SCENE,
        "run_ids": [RUN],
        "time": wall_req(0, 21),
        "seed": {
            "kind": "APPEARANCE",
            "class_label": "person",
            "color": {"label": "red", "min_verdict": "STRONG"},
        },
        "switch_mode": mode,
        "parameter_set_id": "@param_id",
    }


def snapshot(session: str) -> dict[str, Any]:
    def cand(rank, cam, tid, relation, regs, tier, area):
        return {
            "candidate_ref": f"cand:{'0' * 16}:{rank}",
            "camera_id": cam,
            "rank": rank,
            "relation": relation,
            "transition_id": tid,
            "region_path": regs,
            "window_us": list(WINDOW),
            "window_truncated_us": [],
            "path_traversability": "APPROVED_WALKABLE",
            "path_has_unknown_state": False,
            "ranking_basis": {"relation_tier": tier, "overlap_area_m2": area, "camera_id": cam},
            "alternative_transition_ids": [],
        }

    return {
        "schema_version": "q-demo.candidate-snapshot.v1",
        "candidate_snapshot_sha256": "@",
        "session_id": session,
        "exit_resolution": "UNIQUE",
        "candidates": [
            cand(1, "CAM_D", "T_A_D", "OVERLAP", ["REG_1"], 1, 3.5),
            cand(2, "CAM_B", "T_A_B", "BLIND_GAP", ["REG_1", "REG_2", "REG_3"], 2, 6.0),
            cand(3, "CAM_E", "T_A_E", "BLIND_GAP", ["REG_1", "REG_2", "REG_5"], 2, None),
        ],
        "excluded_transitions": [{"transition_id": "T_A_C", "reason": "TOPOLOGICAL_ONLY_EDGE"}],
        "candidate_set_complete": True,
        "truncated": False,
        "truncated_count": 0,
    }


def decision(
    session,
    step,
    before,
    after,
    t,
    mode,
    by,
    *,
    considered=(),
    llm=(),
    submitted=None,
    accepted=True,
    code=None,
    action=None,
    ref=None,
    fb=None,
    rounds=0,
    budget=0,
    snap=True,
    dtime=DT_US,
    entry=None,
    agent_rounds=0,
):
    return {
        "schema_version": "q-demo.decision-record.v1",
        "decision_id": f"{session}-dec-{step}",
        "session_id": session,
        "step_index": step,
        "state_before": before,
        "state_after": after,
        "source_time_us": t,
        "decision_time_us": dtime if snap else None,
        "switch_mode": mode,
        "candidate_snapshot_sha256": "@" if snap else None,
        "exit_resolution": "UNIQUE" if snap else None,
        "candidates_considered": list(considered),
        "tool_calls": [
            {
                "tool": "get_candidate_evidence",
                "request_sha256": H(f"{session}{step}rq"),
                "response_sha256": H(f"{session}{step}rs"),
            }
        ]
        if considered
        else [],
        "llm_calls": list(llm),
        "submitted": submitted,
        "accepted": accepted,
        "rejection_code": code,
        "executed_action": action,
        "executed_candidate_ref": ref,
        "entry_observation_id": entry,
        "input_pins": {"tracking_scope_sha256": TS_SHA},  # section 5.1 (D81)
        "decided_by": by,
        "fallback_reason": fb,
        "rounds_used": rounds,
        "budget_used_ms": budget,
        "searching_index": 1 if snap else 0,  # D69: one SEARCHING per session in these fixtures
        "session_agent_rounds_used": agent_rounds,
        "content_sha256": "@",
        **({} if mode == "RULE_ONLY" else {"stats": {"latency_ms": {"agent": 5, "evidence": 1}}}),
    }


def ev_hash(stem: str, rank: int) -> str:
    """Placeholder; finalize() replaces it with the #135 C8 hash and updates the citing records."""

    return H(f"evidence-{stem}-{rank}")


def considered(stem, rank, presence, action, by, reason=None, evidence=True):
    return {
        "candidate_ref": f"cand:{'0' * 16}:{rank}",
        "rank": rank,
        "evidence_sha256": ev_hash(stem, rank) if evidence else None,
        "target_presence": presence,
        "exclusion_reason": reason,
        "action": action,
        "decided_by": by,
    }


def llm_call(n):
    return {
        "model": "synthetic-llm",
        "model_digest": H("digest"),
        "prompt_sha256": H(f"prompt{n}"),
        "prompt_ref": f"prompt:syn-{n}",
        "raw_output_sha256": H(f"raw{n}"),
        "validation": "PASS",
    }


ENTRY_OBS = f"obs:{OBS_SEG}:CAM_B:68:0"
EMPTY_SHA = hashlib.sha256(b"").hexdigest()


def evidence(
    stem: str,
    rank: int,
    presence: str,
    camera: str,
    *,
    evaluated: int = 15,
    not_inferred: int = 0,
    missing: int = 0,
    not_sampled: int = 0,
    complete: bool | None = None,
    partial: str | None = None,
    best: tuple = (),
    entry: tuple | None = None,
    ref: str | None = None,
) -> dict[str, Any]:
    """q-demo.candidate-evidence.v1 (#135 C8); ``best`` = (frame, ts, verdict, score) items."""

    n = evaluated + not_inferred + missing
    return {
        "schema_version": "q-demo.candidate-evidence.v1",
        "candidate_ref": ref or f"cand:{'0' * 16}:{rank}",
        "camera_id": camera,
        "window_us": list(WINDOW),
        "target_presence": presence,
        "frames": {
            "evaluated": evaluated,
            "not_sampled": not_sampled,
            "not_inferred": not_inferred,
            "missing": missing,
        },
        "coverage_complete": (n > 0 and evaluated == n) if complete is None else complete,
        "partial_basis": partial,
        "decision_time_us": DT_US,
        "entry_observation_id": f"obs:{OBS_SEG}:{camera}:{entry[0]}:0" if entry else None,
        "entry_timestamp_us": entry[1] if entry else None,
        "best_observations": [
            {
                "observation_id": f"obs:{OBS_SEG}:{camera}:{frame}:0",
                "frame_ref": f"frame:{RUN}:{camera}:{frame}",
                "timestamp_us": ts,
                "score": score,
                "color_verdict": verdict,
                "bbox_xyxy_px": [300.0, 100.0, 360.0, 260.0],
            }
            for frame, ts, verdict, score in best
        ],
        "matching_observation_count": sum(1 for b in best if b[2] in ("STRONG", "WEAK")),
        "first_match_us": next((b[1] for b in best if b[2] in ("STRONG", "WEAK")), None),
        "evidence_sha256": ev_hash(stem, rank),
    }


def session_evidence(stem: str) -> dict[str, Any]:
    return {
        f"{stem}.evidence_1.json": evidence(
            stem,
            1,
            "PERSON_NO_COLOR_MATCH",
            "CAM_D",
            best=[(50, 10_000_000, "NONE", 0.7)],
        ),
        f"{stem}.evidence_2.json": evidence(
            stem,
            2,
            "MATCH_STRONG",
            "CAM_B",
            best=[(68, ENTRY_US, "STRONG", 0.84)],
            entry=(68, ENTRY_US),
        ),
    }


def evidence_cases() -> dict[str, Any]:
    """One standalone summary per §8.3 branch (candidate refs point at no supplied snapshot)."""

    def ref(n: int) -> str:
        return f"cand:{'e' * 16}:{n}"

    def case(name: str, rank: int, presence: str, **kw: Any) -> tuple[str, dict[str, Any]]:
        stem = f"evidence_case_{name}"
        return f"{stem}.json", evidence(stem, 1, presence, "CAM_X", ref=ref(rank), **kw)

    pairs = [
        case("not_evaluated", 1, "NOT_EVALUATED", evaluated=0, not_inferred=15),
        case("empty_window", 2, "NOT_EVALUATED", evaluated=0),
        case(
            "partial",
            3,
            "PARTIAL_EVIDENCE",
            evaluated=6,
            not_inferred=9,
            partial="NO_PERSON_DETECTED",
        ),
        case(
            "partial_nocolor",
            4,
            "PARTIAL_EVIDENCE",
            evaluated=6,
            missing=9,
            partial="PERSON_NO_COLOR_MATCH",
            best=[(50, 10_000_000, "NONE", 0.7)],
        ),
        case(
            "color_unknown_mixed",
            5,
            "PERSON_COLOR_UNKNOWN",
            best=[(50, 10_000_000, "UNKNOWN", 0.7), (52, 10_400_000, "NONE", 0.6)],
        ),
        case(
            "weak_partial",
            6,
            "MATCH_WEAK",
            evaluated=6,
            not_inferred=9,
            best=[(60, 12_000_000, "WEAK", 0.6)],
        ),
        case("no_person", 7, "NO_PERSON_DETECTED", not_sampled=15),
        case("nocolor_strong", 9, "MATCH_STRONG", best=[(60, 12_000_000, None, 0.8)]),
        case(
            "nocolor_partial",
            10,
            "PARTIAL_EVIDENCE",
            evaluated=6,
            not_inferred=9,
            partial="NO_PERSON_DETECTED",
        ),
        case(
            "after_decision_only",
            8,
            "MATCH_STRONG",
            best=[(45, 9_000_000, "STRONG", 0.8)],
        ),
    ]
    return dict(pairs)


def links(session: str) -> list[dict[str, Any]]:
    """§8.2 link journal (D69/D78 q-demo.link-record.v2): one chain that is linked exactly at link_max_gap_us, one that triggers SEARCHING."""

    rows: list[dict[str, Any]] = []

    def audit(prev, iou, elapsed, gap, decision):
        # D78: null while the last real box is tried for the first unlinked cell; an object once
        # earlier cells were left unlinked (SYNTHETIC boxes; reference = last real box)
        if gap <= (0 if decision == "LINKED" else 1):
            return None
        linked = decision == "LINKED"
        return {
            "method": "LAST_OBSERVATION_V1",
            "reference_bbox_xyxy_px": [100.0, 100.0, 200.0, 300.0],
            "source_observations": [
                {
                    "observation_id": f"obs:{OBS_SEG}:CAM_A:{prev}:0",
                    "timestamp_us": prev * SRC_US,
                    "bbox_xyxy_px": [100.0, 100.0, 200.0, 300.0],
                }
            ],
            "elapsed_us": elapsed,
            "actual_pair_iou": iou if linked else None,
            "reference_iou": iou if linked else None,
            "event": "REACQUIRED" if linked else "NO_MATCH",
            "identity_verdict": "UNCONFIRMED",
        }

    def link(prev, nxt, iou, elapsed, gap, decision):
        frame = prev + elapsed // SRC_US
        rows.append(
            {
                "schema_version": "q-demo.link-record.v2",
                "session_id": session,
                "link_index": len(rows),
                "run_id": RUN,
                "camera_id": "CAM_A",
                "frame_ref": f"frame:{RUN}:CAM_A:{frame}",
                "local_segment_id": f"local:{session}:{0 if prev < 40 else 1}",
                "prev_observation_id": f"obs:{OBS_SEG}:CAM_A:{prev}:0",
                "next_observation_id": f"obs:{OBS_SEG}:CAM_A:{nxt}:0" if nxt is not None else None,
                "iou": iou,
                "elapsed_us": elapsed,
                "gap_samples": gap,
                "decision": decision,
                "ambiguous_candidates": None,
                "matching_audit": audit(prev, iou, elapsed, gap, decision),
            }
        )
        return rows[-1]

    return [
        link(0, None, None, IV, 1, "NO_CANDIDATE"),
        link(0, None, None, 2 * IV, 2, "FRAME_MISSING"),
        link(0, 6, 0.55, 3 * IV, 2, "LINKED"),  # elapsed == link_max_gap_us and still linked
        link(40, None, None, IV, 1, "NO_CANDIDATE"),
        link(40, None, None, 2 * IV, 2, "NO_CANDIDATE"),
        link(40, None, None, 3 * IV, 3, "NO_CANDIDATE"),  # 3 > link_max_gap_samples 2 -> SEARCHING
    ]


def switch_done(record: dict[str, Any], step: int) -> dict[str, Any]:
    """Section 8.6 D78: the SWITCHING -> PLAYING record that completes an accepted SWITCH.

    It binds the SWITCH by cause_decision_id, keeps its snapshot / entry / candidate / counters and
    adds no tool or model call.
    """

    done = copy.deepcopy(record)
    done.update(
        decision_id=f"{record['session_id']}-dec-{step}",
        step_index=step,
        state_before="SWITCHING",
        state_after="PLAYING",
        candidates_considered=[],
        tool_calls=[],
        llm_calls=[],
        submitted=None,
        executed_action=None,
        cause_decision_id=record["decision_id"],
        content_sha256="@",
    )
    return done


def q2_response(
    session: str, by: str, tracking: str | None = TS_SHA, **over: Any
) -> dict[str, Any]:
    req, ranges, cv = complete(0, 21)
    tl = [
        {
            "segment_id": "seg-0",
            "kind": "ON_CAMERA",
            "camera_id": "CAM_A",
            "range_us": [0, 8_400_000],
            "entered_by": "SEED",
            "decided_by": "USER",
            "observation_ids": [f"obs:{OBS_SEG}:CAM_A:0:0", f"obs:{OBS_SEG}:CAM_A:40:0"],
            "presence_at_entry": "MATCH_STRONG",
        },
        {
            "segment_id": "seg-1",
            "kind": "GAP",
            "range_us": [8_400_000, ENTRY_US],
            "gap_states": ["TEMP_LOST", "SEARCHING"],
            "camera_shown": "CAM_A",
            "position": None,
        },
        {
            "segment_id": "seg-2",
            "kind": "ON_CAMERA",
            "camera_id": "CAM_B",
            "range_us": [ENTRY_US, 21_000_000],
            "entered_by": "SWITCH",
            "decided_by": by,
            "decision_id": f"{session}-dec-{6 if session == 'sess_agent' else 4}",
            "observation_ids": [ENTRY_OBS],
            "presence_at_entry": "MATCH_STRONG",
        },
    ]
    body = dict(
        status="COMPLETE",
        reason=None,
        session_id=session,
        timeline=tl,
        decisions_ref=f"{session}.decisions.jsonl",
        decisions_sha256="@",
        links_ref=f"{session}.links.jsonl",  # a controlled logical ref (D69), not a local path
        links_sha256="@",
    )
    body.update(over)
    sc = scope(req, ranges, cv, ["CAM_A", "CAM_B", "CAM_D", "CAM_E"], tracking=tracking)
    return envelope("q2-response", body.pop("status"), body.pop("reason"), sc, **body)


def q2_files() -> dict[str, Any]:
    f: dict[str, Any] = {}
    # --- rule-only session
    s = "sess_rule"
    f["q2_rule.request.json"] = q2_request("RULE_ONLY")
    f["q2_rule.snapshot.json"] = snapshot(s)
    f.update(session_evidence("q2_rule"))
    f["q2_rule.links.jsonl"] = links(s)
    f["q2_rule.decisions.jsonl"] = [
        decision(s, 0, None, "PLAYING", 0, "RULE_ONLY", "USER", snap=False),
        decision(
            s,
            4,
            "SEARCHING",
            "SWITCHING",  # D78: PLAYING follows in its own record
            ENTRY_US,
            "RULE_ONLY",
            "RULE_ONLY",
            considered=[
                considered(
                    "q2_rule",
                    1,
                    "PERSON_NO_COLOR_MATCH",
                    "NEXT_CANDIDATE",
                    "RULE_ONLY",
                    "CONDITION_MISMATCH",
                ),
                considered("q2_rule", 2, "MATCH_STRONG", "SWITCH", "RULE_ONLY"),
            ],
            submitted={"action": "SWITCH", "candidate_ref": f"cand:{'0' * 16}:2"},
            action="SWITCH",
            ref=f"cand:{'0' * 16}:2",
            entry=ENTRY_OBS,
        ),
    ]
    f["q2_rule.decisions.jsonl"].append(switch_done(f["q2_rule.decisions.jsonl"][-1], 5))
    f["q2_rule.response.json"] = q2_response(s, "RULE_ONLY", decision_source="RULE_ONLY")
    # --- agent session: rejected unknown ref, accepted NEXT_CANDIDATE, then ROUND_LIMIT fallback
    s = "sess_agent"
    f["q2_agent.request.json"] = q2_request("AGENT_SEQUENTIAL")
    f["q2_agent.snapshot.json"] = snapshot(s)
    f["q2_agent.agent_decision.json"] = {
        "schema_version": "q-demo.agent-decision.v1",
        "session_id": s,
        "decision_id": f"{s}-dec-4",
        "candidate_snapshot_sha256": "@",
        "action": "SWITCH",
        "candidate_ref": f"cand:{'0' * 16}:9",
        "cited_observation_ids": [f"obs:{OBS_SEG}:CAM_B:0:0"],
        "rationale": "synthetic rationale",
    }
    f.update(session_evidence("q2_agent"))
    f["q2_agent.links.jsonl"] = links(s)
    f["q2_agent.decisions.jsonl"] = [
        decision(s, 0, None, "PLAYING", 0, "AGENT_SEQUENTIAL", "USER", snap=False),
        decision(
            s,
            4,
            "SEARCHING",
            "SEARCHING",
            DT_US,
            "AGENT_SEQUENTIAL",
            "AGENT",
            llm=[llm_call(1)],
            submitted={"action": "SWITCH", "candidate_ref": f"cand:{'0' * 16}:9"},
            accepted=False,
            code="UNKNOWN_REF",
            rounds=1,
            budget=900,
            agent_rounds=1,
        ),
        decision(
            s,
            5,
            "SEARCHING",
            "SEARCHING",
            DT_US,
            "AGENT_SEQUENTIAL",
            "AGENT",
            llm=[llm_call(2)],
            considered=[
                considered(
                    "q2_agent",
                    1,
                    "PERSON_NO_COLOR_MATCH",
                    "NEXT_CANDIDATE",
                    "AGENT",
                    "CONDITION_MISMATCH",
                )
            ],
            submitted={"action": "NEXT_CANDIDATE", "candidate_ref": f"cand:{'0' * 16}:1"},
            action="NEXT_CANDIDATE",
            ref=f"cand:{'0' * 16}:1",
            rounds=2,
            budget=1800,
            agent_rounds=2,
        ),
        decision(
            s,
            6,
            "SEARCHING",
            "SWITCHING",  # D78: PLAYING follows in its own record
            ENTRY_US,
            "AGENT_SEQUENTIAL",
            "RULE_FALLBACK",
            fb="ROUND_LIMIT",
            rounds=6,
            budget=2400,
            agent_rounds=2,
            considered=[considered("q2_agent", 2, "MATCH_STRONG", "SWITCH", "RULE_FALLBACK")],
            submitted={"action": "SWITCH", "candidate_ref": f"cand:{'0' * 16}:2"},
            action="SWITCH",
            ref=f"cand:{'0' * 16}:2",
            entry=ENTRY_OBS,
        ),
    ]
    f["q2_agent.decisions.jsonl"].append(switch_done(f["q2_agent.decisions.jsonl"][-1], 7))
    f["q2_agent.response.json"] = q2_response(
        s,
        "RULE_FALLBACK",
        decision_source="RULE_FALLBACK",
        agent_attempted=True,
        agent_used=True,
        fallback_used=True,
        fallback_reason="ROUND_LIMIT",
    )
    # --- exhausted Agent session (D73 §14-21): NEXT_CANDIDATE on all three candidates (the first one
    # has an evidence hash but no observation, §14-26), then the Controller returns to origin
    s = "sess_exhaust"
    stem = "q2_exhaust"
    f[f"{stem}.request.json"] = q2_request("AGENT_SEQUENTIAL")
    f[f"{stem}.snapshot.json"] = snapshot(s)
    f[f"{stem}.evidence_1.json"] = evidence(stem, 1, "NO_PERSON_DETECTED", "CAM_D", not_sampled=15)
    f[f"{stem}.evidence_2.json"] = evidence(
        stem, 2, "NOT_EVALUATED", "CAM_B", evaluated=0, not_inferred=15
    )
    f[f"{stem}.evidence_3.json"] = evidence(
        stem, 3, "NOT_EVALUATED", "CAM_E", evaluated=0, not_inferred=15
    )
    f[f"{stem}.links.jsonl"] = links(s)
    f[f"{stem}.decisions.jsonl"] = [
        decision(s, 0, None, "PLAYING", 0, "AGENT_SEQUENTIAL", "USER", snap=False),
        decision(
            s,
            4,
            "SEARCHING",
            "RETURNED_TO_ORIGIN",
            DT_US,
            "AGENT_SEQUENTIAL",
            "RULE_ONLY",
            considered=[
                considered(
                    stem, 1, "NO_PERSON_DETECTED", "NEXT_CANDIDATE", "AGENT", "CONDITION_MISMATCH"
                ),
                considered(
                    stem, 2, "NOT_EVALUATED", "NEXT_CANDIDATE", "AGENT", "INSUFFICIENT_COVERAGE"
                ),
                considered(
                    stem, 3, "NOT_EVALUATED", "NEXT_CANDIDATE", "AGENT", "INSUFFICIENT_COVERAGE"
                ),
            ],
            llm=[llm_call(11), llm_call(12), llm_call(13)],
            action="RETURN_TO_ORIGIN",
            rounds=3,
            budget=2700,
            agent_rounds=3,
        ),
    ]
    f[f"{stem}.response.json"] = q2_response(
        s,
        "RULE_ONLY",
        decision_source="RULE_ONLY",  # D73 §14-21: the return is the Controller's, agent_used stays true
        agent_attempted=True,
        agent_used=True,
        timeline=[
            {
                "segment_id": "seg-0",
                "kind": "ON_CAMERA",
                "camera_id": "CAM_A",
                "range_us": [0, 8_400_000],
                "entered_by": "SEED",
                "decided_by": "USER",
                "observation_ids": [f"obs:{OBS_SEG}:CAM_A:0:0", f"obs:{OBS_SEG}:CAM_A:40:0"],
                "presence_at_entry": "MATCH_STRONG",
            },
            {
                "segment_id": "seg-1",
                "kind": "GAP",
                "range_us": [8_400_000, 21_000_000],
                "gap_states": ["TEMP_LOST", "SEARCHING", "RETURNED_TO_ORIGIN"],
                "camera_shown": "CAM_A",
                "position": None,
            },
        ],
    )
    # --- NO_SEED session: nothing was decided or linked, so both journals are empty (D69, #178);
    # the seed has no colour condition (§8.3 "起始條件沒有顏色時", #211)
    s = "sess_noseed"
    f["q2_noseed.request.json"] = {
        **q2_request("RULE_ONLY"),
        "seed": {"kind": "APPEARANCE", "class_label": "person", "color": None},
    }
    f[f"{s}.decisions.jsonl"] = ""
    f[f"{s}.links.jsonl"] = ""
    f["q2_noseed.response.json"] = q2_response(
        s,
        "RULE_ONLY",
        status="NO_SEED",
        timeline=[],
        decision_source=None,
        decisions_sha256=EMPTY_SHA,
        links_sha256=EMPTY_SHA,
    )
    # --- tracking scope missing (section 5.4 step 0, D81): blocked before any seed or session
    s = "sess_noscope"
    f["q2_noscope.request.json"] = f["q2_noseed.request.json"]
    f[f"{s}.decisions.jsonl"] = ""
    f[f"{s}.links.jsonl"] = ""
    f["q2_noscope.response.json"] = q2_response(
        s,
        "RULE_ONLY",
        tracking=None,  # section 2.3: the scope pin is null, the key stays
        status="UNKNOWN",
        reason="TRACKING_SCOPE_MISSING",
        reasons=["TRACKING_SCOPE_MISSING"],
        timeline=[],
        decision_source=None,
        decisions_sha256=EMPTY_SHA,
        links_sha256=EMPTY_SHA,
    )
    return f


def valid_files() -> dict[str, Any]:
    files = static_docs()
    files.update(q1_files())
    files.update(q3_files())
    files.update(q2_files())
    files.update(evidence_cases())
    return files


# ----------------------------------------------------------------------------- finalisation

REF_PREFIX = re.compile(r"cand:[0-9a-f]{16}:")
EVIDENCE = "q-demo.candidate-evidence.v1"


def _replace(node: Any, table: dict[str, str]) -> Any:
    if isinstance(node, dict):
        return {k: _replace(v, table) for k, v in node.items()}
    if isinstance(node, list):
        return [_replace(v, table) for v in node]
    if isinstance(node, str) and node.startswith("@") and node in table:
        return table[node]
    return node


def _replace_text(node: Any, old: str, new: str) -> Any:
    if isinstance(node, dict):
        return {k: _replace_text(v, old, new) for k, v in node.items()}
    if isinstance(node, list):
        return [_replace_text(v, old, new) for v in node]
    if isinstance(node, str):
        return node.replace(old, new)
    return node


def index_key16(manifest: dict[str, Any]) -> str:
    """Contract section 2.2: index key = manifest without index_id, content_sha256, records_ref, records_file_sha256."""

    return canonical_sha256(
        manifest, ("index_id", "content_sha256", "records_ref", "records_file_sha256", "stats")
    )[:16]


def serialise(name: str, data: Any) -> bytes:
    if name.endswith(".jsonl"):
        return "".join(
            json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n" for r in data
        ).encode()
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode()


def finalize(files: dict[str, Any]) -> dict[str, Any]:
    """Recompute every derived hash / id / link so a patched set stays consistent."""

    f = files
    t: dict[str, str] = {}
    # D78: a SWITCHING -> PLAYING record is derived from the SWITCH it completes, so a case that
    # patches the SWITCH keeps the pair bound (binding violations are tested in the unit tests)
    for name in [n for n in f if n.endswith(".decisions.jsonl") and isinstance(f[n], list)]:
        by_id = {r.get("decision_id"): r for r in f[name] if isinstance(r, dict)}
        for i, r in enumerate(f[name]):
            cause = by_id.get(r.get("cause_decision_id")) if isinstance(r, dict) else None
            if cause is not None:
                done = switch_done(cause, r["step_index"])
                done["source_time_us"] = max(r["source_time_us"], cause["source_time_us"])
                f[name][i] = done
    if "clock_mapping.json" in f:
        f["clock_mapping.json"]["content_sha256"] = t["@clock_sha"] = canonical_sha256(
            f["clock_mapping.json"], ("content_sha256",)
        )
    if "region_graph.json" in f:
        g = f["region_graph.json"]
        g["content_sha256"] = t["@rg_sha"] = canonical_sha256(g, ("content_sha256", "graph_id"))
        g["graph_id"] = f"rgraph:{REV}:static:{g['content_sha256'][:16]}"
    if "camera_graph.json" in f:
        g = f["camera_graph.json"]
        g["region_graph_sha256"] = t.get("@rg_sha", g["region_graph_sha256"])
        g["content_sha256"] = t["@cg_sha"] = canonical_sha256(g, ("content_sha256", "graph_id"))
        g["graph_id"] = f"cgraph:{REV}:static:{g['content_sha256'][:16]}"
    if "detection_index.json" in f:
        m = f["detection_index.json"]
        # index_id and every observation_id carry the index-key segment; records_file_sha256 and
        # content_sha256 are computed afterwards and do not feed back into it (section 2.2)
        segment = index_key16(m)
        for name in list(f):
            if not isinstance(f[name], str):
                f[name] = _replace_text(f[name], OBS_SEG, segment)
        m = f["detection_index.json"]
        if "detection_index.records.jsonl" in f:
            m["records_file_sha256"] = hashlib.sha256(
                serialise("detection_index.records.jsonl", f["detection_index.records.jsonl"])
            ).hexdigest()
        m["content_sha256"] = t["@index_sha"] = canonical_sha256(m, ("content_sha256", "index_id"))
        m["index_id"] = t["@index_id"] = f"detidx:{REV}:{RUN}:{segment}"
        t["@classmap_sha"] = m["detector"]["class_map"]["content_sha256"]
        t["@color_ver"] = m["color_method"]["version"]
    if "parameter_set.json" in f:
        f["parameter_set.json"] = _replace(f["parameter_set.json"], t)
        p = f["parameter_set.json"]
        p["content_sha256"] = t["@param_sha"] = canonical_sha256(
            p, ("content_sha256", "parameter_set_id")
        )
        p["parameter_set_id"] = t["@param_id"] = f"pset:q-demo:{p['content_sha256'][:16]}"
    for name in list(f):
        f[name] = _replace(f[name], t)
    # snapshots and the decisions / agent submissions that cite them
    for name in sorted(n for n in f if n.endswith(".snapshot.json")):
        snap = f[name]
        body = copy.deepcopy(snap)
        for c in body["candidates"]:
            c.pop("candidate_ref", None)
        digest = canonical_sha256(body, ("candidate_snapshot_sha256",))
        snap["candidate_snapshot_sha256"] = digest
        prefix = f"cand:{digest[:16]}:"
        for c in snap["candidates"]:
            c["candidate_ref"] = REF_PREFIX.sub(prefix, c["candidate_ref"])
        stem = name.split(".")[0]
        for other in list(f):
            if (
                other.split(".")[0] != stem
                or other == name
                or other.endswith((".request.json", ".response.json"))
            ):
                continue
            text = json.dumps(f[other], ensure_ascii=False)
            text = REF_PREFIX.sub(prefix, text)
            f[other] = json.loads(text)
            items = f[other] if isinstance(f[other], list) else [f[other]]
            for it in items:
                if it.get("candidate_snapshot_sha256") not in (None,):
                    it["candidate_snapshot_sha256"] = digest
    evidence_names = sorted(
        n for n in f if isinstance(f[n], dict) and f[n].get("schema_version") == EVIDENCE
    )
    for name in evidence_names:
        e = f[name]
        old = e["evidence_sha256"]
        e["evidence_sha256"] = canonical_sha256(e, ("evidence_sha256", "stats"))
        for other in list(f):
            if other != name and not isinstance(f[other], str):
                f[other] = _replace_text(f[other], old, e["evidence_sha256"])
    for name in [n for n in f if n.endswith(".decisions.jsonl")]:
        for r in f[name]:
            r["content_sha256"] = canonical_sha256(r, ("content_sha256", "stats"))
        t["@dec_sha:" + name.split(".")[0]] = hashlib.sha256(serialise(name, f[name])).hexdigest()
    for name in [
        n
        for n in f
        if n.endswith(".response.json") and isinstance(f[n], dict) and "decisions_sha256" in f[n]
    ]:
        if "@dec_sha:" + name.split(".")[0] in t:
            f[name]["decisions_sha256"] = t["@dec_sha:" + name.split(".")[0]]
        links_name = name.split(".")[0] + ".links.jsonl"
        if links_name in f and f[name].get("links_sha256") == "@":
            raw = f[links_name]
            raw = raw.encode() if isinstance(raw, str) else serialise(links_name, raw)
            f[name]["links_sha256"] = hashlib.sha256(raw).hexdigest()
    for name in sorted(
        n
        for n in f
        if n.endswith(".response.json") and isinstance(f[n], dict) and "schema_version" in f[n]
    ):
        f[name]["output_sha256"] = canonical_sha256(f[name], ("output_sha256", "stats"))
    if "q1_ready.response.json" in f:
        out = f["q1_ready.response.json"]["output_sha256"]
        for name in [n for n in f if n.endswith(".explanation.json")]:
            e = f[name]
            e["explains_output_sha256"] = out
            e["content_sha256"] = canonical_sha256(e, ("content_sha256",))
    return f


# ----------------------------------------------------------------------------- patching

_TOKEN = re.compile(r"\.([A-Za-z_][\w-]*)|\[(\d+)\]")


def _walk_path(root: Any, path: str) -> tuple[Any, Any]:
    tokens = [
        (m.group(1), m.group(2))
        for m in _TOKEN.finditer(path[1:] if path.startswith("$") else path)
    ]
    node = root
    for key, idx in tokens[:-1]:
        node = node[key] if key is not None else node[int(idx)]
    key, idx = tokens[-1]
    return node, (key if key is not None else int(idx))


def apply_op(files: dict[str, Any], op: dict[str, Any]) -> None:
    kind = op["op"]
    if kind == "add_file":
        files[op["file"]] = copy.deepcopy(op["data"])
    elif kind == "append_record":  # one more record in a JSONL journal
        files[op["file"]].append(copy.deepcopy(op["value"]))
    elif kind == "add_raw":
        files[op["file"]] = op["text"]
    elif kind == "remove_file":
        del files[op["file"]]
    elif kind == "rehash_decisions":
        for r in files[op["file"]]:
            r["content_sha256"] = canonical_sha256(r, ("content_sha256", "stats"))
    elif kind == "copy_file":
        files[op["to"]] = copy.deepcopy(files[op["from"]])
    elif kind == "rehash_manifest":  # content_sha256 of a (copied) detection-index manifest
        m = files[op["file"]]
        m["content_sha256"] = canonical_sha256(m, ("content_sha256", "index_id", "stats"))
    else:
        parent, key = _walk_path(files[op["file"]], op["path"])
        if kind == "set":
            parent[key] = copy.deepcopy(op["value"])
            if op["path"] == "$.reason" and "reasons" in parent:
                # D73 §14-12: reasons[] follows reason unless a case sets it itself
                parent["reasons"] = [op["value"]] if op["value"] else []
        elif kind == "del":
            del parent[key]
        elif kind == "append":
            parent[key].append(copy.deepcopy(op["value"]))
        elif kind == "swap":
            parent[key][op["i"]], parent[key][op["j"]] = parent[key][op["j"]], parent[key][op["i"]]
        else:
            raise ValueError(kind)


def materialize(case: dict[str, Any] | None, target: Path) -> None:
    files = valid_files()
    stage = (case or {}).get("stage", "pre")
    ops = (case or {}).get("ops", [])
    if stage == "pre":
        for op in ops:
            apply_op(files, op)
    if case is None or stage == "pre":
        finalize(files)
    else:
        finalize(files)
        for op in ops:
            apply_op(files, op)
    target.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        raw = data.encode() if isinstance(data, str) else serialise(name, data)
        (target / name).write_bytes(raw)


# ----------------------------------------------------------------------------- violations


def S(file, path, value, stage="pre"):
    return {"op": "set", "file": file, "path": path, "value": value, "_stage": stage}


def case(cid, description, ops, expect, stage="pre", text=None):
    out = {
        "id": cid,
        "description": description,
        "ops": [{k: v for k, v in o.items() if k != "_stage"} for o in ops],
        "stage": stage,
        "expect_fail": sorted(expect),
    }
    if text:
        out["expect_message_contains"] = (
            text  # substring that must appear in a finding of the expected checks
        )
    return out


def grid_reply(file: str) -> list[dict[str, Any]]:
    """D69 (§2.3): grid mismatch is status UNKNOWN, reason PARAMETER_GRID_MISMATCH, nothing executed."""

    return [
        S(file, "$.status", "UNKNOWN"),
        S(file, "$.reason", "PARAMETER_GRID_MISMATCH"),
        S(file, "$.timeline", []),
    ]


def with_results(file: str) -> list[dict[str, Any]]:
    return [
        S(file, "$.results", q1_results()),
        S(file, "$.results_total", 2),
        S(file, "$.returned_count", 2),
    ]


RP_REASONS = ["TIME_SCOPE_PARTIAL"]  # the reason of q1_partial in the valid set


def agent_after_fallback() -> dict[str, Any]:
    """An Agent step recorded after the session's RULE_FALLBACK, with no USER decision in between."""

    r = decision(
        "sess_agent",
        8,  # after the D78 SWITCHING -> PLAYING record (step 7)
        "PLAYING",
        "TEMP_LOST",
        14_000_000,
        "AGENT_SEQUENTIAL",
        "AGENT",
        llm=[llm_call(9)],
        snap=False,
        agent_rounds=3,
    )
    r["searching_index"] = 1
    return r


def agent_after_user_restart() -> list[dict[str, Any]]:
    """RETURNED... -> a USER re-pick, then an Agent step: the user restarts the Agent (D73 X2)."""

    user = decision(
        "sess_agent",
        8,
        "PLAYING",
        "PLAYING",
        14_000_000,
        "AGENT_SEQUENTIAL",
        "USER",
        snap=False,
        agent_rounds=2,
    )
    user["searching_index"] = 1
    again = agent_after_fallback()
    again["step_index"], again["decision_id"] = 9, "sess_agent-dec-9"
    again["state_before"] = "PLAYING"
    again["source_time_us"] = 14_400_000
    return [user, again]


def violations() -> list[dict[str, Any]]:
    R1 = "q1_ready.response.json"
    C: list[dict[str, Any]] = []
    a = C.append
    # ---- shared response fields
    a(
        case(
            "gt_read_true",
            "provenance.gt_read is true",
            [S(R1, "$.provenance.gt_read", True)],
            ["COMMON_GT_READ_FALSE", "SCHEMA_VALID"],
        )
    )
    a(
        case(
            "identity_confirmed",
            "identity_verdict is CONFIRMED",
            [S(R1, "$.identity_verdict", "CONFIRMED")],
            ["COMMON_IDENTITY_UNCONFIRMED", "SCHEMA_VALID"],
        )
    )
    a(
        case(
            "same_person_text",
            "a reason claims 'same person'",
            [S("q2_rule.response.json", "$.reason", "same person as before")],
            ["COMMON_IDENTITY_UNCONFIRMED"],
        )
    )
    a(
        case(
            "q1_agent_used",
            "Q1 response claims agent_used",
            [S(R1, "$.agent_used", True), S(R1, "$.agent_attempted", True)],
            ["COMMON_AGENT_FIELDS"],
        )
    )
    a(
        case(
            "fallback_flag_without_reason",
            "fallback_used true, reason null",
            [S(R1, "$.fallback_used", True)],
            ["COMMON_AGENT_FIELDS"],
        )
    )
    a(
        case(
            "source_agent_without_agent",
            "decision_source AGENT on a rule-only session",
            [S("q2_rule.response.json", "$.decision_source", "AGENT")],
            ["COMMON_AGENT_FIELDS", "Q2_RESPONSE_VS_DECISIONS"],
        )
    )
    a(
        case(
            "fallback_reason_unknown",
            "fallback_reason outside the closed list",
            [S("q2_agent.response.json", "$.fallback_reason", "SLOW")],
            ["COMMON_AGENT_FIELDS", "SCHEMA_VALID", "Q2_RESPONSE_VS_DECISIONS"],
        )
    )
    a(
        case(
            "local_path_in_refs",
            "absolute local path in provenance.input_refs",
            [S(R1, "$.provenance.input_refs[0]", "/Users/someone/data/index.json")],
            ["NO_FORBIDDEN_CONTENT"],
        )
    )
    a(
        case(
            "forbidden_field",
            "GT-style actor_id field in a response",
            [S(R1, "$.actor_id", "A1")],
            ["NO_FORBIDDEN_CONTENT", "SCHEMA_VALID"],
        )
    )
    a(
        case(
            "forbidden_token",
            "response cites persons.sim.json",
            [S(R1, "$.provenance.input_refs[0]", "persons.sim.json")],
            ["NO_FORBIDDEN_CONTENT"],
        )
    )
    # ---- time coverage / status
    a(
        case(
            "ready_with_reason",
            "READY carrying a reason",
            [S(R1, "$.reason", "SOMETHING")],
            ["COMMON_STATUS_REASON"],
        )
    )
    a(
        case(
            "partial_without_reason",
            "PARTIAL without its main reason",
            [S("q1_partial.response.json", "$.reason", None)],
            ["COMMON_STATUS_REASON"],
        )
    )
    a(
        case(
            "status_outside_list",
            "status outside the endpoint's closed list",
            [S("q1_nomatch.response.json", "$.status", "DONE")],
            ["COMMON_STATUS_REASON", "SCHEMA_VALID"],
        )
    )
    P = "q1_partial.response.json"
    a(
        case(
            "partial_but_ready",
            "incomplete wall coverage reported as READY",
            [S(P, "$.status", "READY"), S(P, "$.reason", None)],
            ["TIME_COVERAGE_INTERNAL"],
        )
    )
    a(
        case(
            "nomatch_over_gaps",
            "NO_MATCH although frames were not inferred",
            [
                S(
                    "q1_nomatch.response.json",
                    "$.no_match_cameras[0].coverage.not_inferred_frames",
                    3,
                )
            ],
            ["Q1_STATUS_VS_COVERAGE"],
        )
    )
    a(
        case(
            "nomatch_partial_time",
            "NO_MATCH although only part of the time was covered",
            [
                S(
                    "q1_nomatch.response.json",
                    "$.resolved_scope.time_coverage",
                    {"coverage_complete": False, "uncovered_wall_ranges": [[wall(10), wall(20)]]},
                )
            ],
            ["TIME_COVERAGE_INTERNAL", "TIME_COVERAGE_RECOMPUTE"],
        )
    )
    a(
        case(
            "ready_with_not_evaluated",
            "READY while a camera was not evaluated",
            [S(R1, "$.not_evaluated_cameras", [{"camera_id": "CAM_C", "reason": "NOT_INFERRED"}])],
            ["Q1_STATUS_VS_COVERAGE"],
        )
    )
    a(
        case(
            "out_of_range_as_nomatch",
            "no overlap with the data but status NO_MATCH",
            [
                S("q1_oor.response.json", "$.status", "NO_MATCH"),
                S("q1_oor.response.json", "$.reason", None),
            ],
            ["TIME_COVERAGE_INTERNAL", "TIME_COVERAGE_RECOMPUTE", "Q1_STATUS_VS_COVERAGE"],
        )
    )
    a(
        case(
            "uncovered_range_wrong",
            "uncovered_wall_ranges disagrees with the clock mapping",
            [
                S(
                    P,
                    "$.resolved_scope.time_coverage.uncovered_wall_ranges",
                    [[wall(90), wall(1800)]],
                )
            ],
            ["TIME_COVERAGE_RECOMPUTE"],
        )
    )
    a(
        case(
            "resolved_range_wrong",
            "resolved source range disagrees with the clock mapping",
            [S(R1, "$.resolved_scope.resolved_source_ranges_us[0].range_us", [0, 9_000_000])],
            ["TIME_COVERAGE_RECOMPUTE"],
        )
    )
    a(
        case(
            "draft_graph_ready",
            "camera graph is DRAFT but responses are READY/COMPLETE",
            [
                S("camera_graph.json", "$.approval_status", "DRAFT"),
                S("camera_graph.json", "$.approval_ref", None),
            ],
            ["GRAPH_APPROVAL_GATES_STATUS"],
        )
    )
    # ---- unsupported handling
    U = "q1_unsupported.response.json"
    a(
        case(
            "unsupported_with_results",
            "UNSUPPORTED_CLASS still returns results",
            with_results(U),
            ["Q1_UNSUPPORTED_HANDLING"],
        )
    )
    a(
        case(
            "unsupported_class_ready",
            "unsupported class answered as READY",
            [S(U, "$.status", "READY"), S(U, "$.reason", None)] + with_results(U),
            ["Q1_SUPPORTED_SET_CONSISTENCY"],
        )
    )
    CC = "q1_color_car.response.json"
    a(
        case(
            "color_on_car_ready",
            "colour condition on car answered as READY",
            [S(CC, "$.status", "READY"), S(CC, "$.reason", None)] + with_results(CC),
            ["Q1_UNSUPPORTED_HANDLING", "Q1_SUPPORTED_SET_CONSISTENCY"],
        )
    )
    a(
        case(
            "supported_class_rejected",
            "supported class answered UNSUPPORTED_CLASS",
            [
                S(R1, "$.status", "UNSUPPORTED_CLASS"),
                S(R1, "$.results", []),
                S(R1, "$.results_total", 0),
                S(R1, "$.returned_count", 0),
                S(R1, "$.supported_classes_ref", "supported-classes:syn-v1"),
            ],
            ["Q1_SUPPORTED_SET_CONSISTENCY", "EXPLANATION_CITED_REFS"],
        )
    )
    a(
        case(
            "below_floor_accepted",
            "request below index_score_floor answered normally instead of 422",
            [
                {"op": "copy_file", "from": R1, "to": "q1_belowfloor.response.json"},
                S("q1_belowfloor.response.json", "$.normalized_condition.query_min_score", 0.05),
            ],
            ["Q1_MIN_SCORE_FLOOR"],
        )
    )
    # ---- Q1 ordering
    a(
        case(
            "q1_order_swapped",
            "results not ordered by first match / camera_id",
            [{"op": "swap", "file": R1, "path": "$.results", "i": 0, "j": 1}],
            ["Q1_RESULT_ORDER"],
        )
    )
    a(
        case(
            "q1_segments_overlap",
            "matched segments overlap",
            [
                {
                    "op": "append",
                    "file": R1,
                    "path": "$.results[0].matched_segments",
                    "value": {
                        "range_us": [100_000, 300_000],
                        "matched_frames": 1,
                        "evaluated_frames": 1,
                        "representative": {
                            "frame_ref": "frame:RUN_X:CAM_A:0",
                            "observation_ids": ["obs:0123456789abcdef:CAM_A:0:0"],
                            "media_token": "m",
                        },
                    },
                }
            ],
            ["Q1_RESULT_ORDER"],
        )
    )
    a(
        case(
            "q1_camera_in_two_lists",
            "a camera is both a result and a no-match",
            [
                S(
                    R1,
                    "$.no_match_cameras",
                    [
                        {
                            "camera_id": "CAM_A",
                            "coverage": {
                                "evaluated_frames": 4,
                                "not_inferred_frames": 0,
                                "missing_frames": 0,
                            },
                        }
                    ],
                )
            ],
            ["Q1_NONE_CATEGORIES_DISJOINT"],
        )
    )
    a(
        case(
            "q1_matched_gt_evaluated",
            "matched_frames exceeds evaluated_frames",
            [S(R1, "$.results[0].matched_segments[0].matched_frames", 5)],
            ["Q1_STATUS_VS_COVERAGE"],
        )
    )
    a(
        case(
            "q1_count_mismatch",
            "returned_count differs from results",
            [S(R1, "$.returned_count", 5), S(R1, "$.results_total", 5)],
            ["Q1_RESULT_ORDER"],
        )
    )
    # ---- hashes
    a(
        case(
            "output_hash_bad",
            "output_sha256 does not recompute",
            [S(R1, "$.output_sha256", "0" * 64)],
            ["OUTPUT_HASH_RECOMPUTE"],
            stage="post",
        )
    )
    a(
        case(
            "timing_in_body",
            "latency_ms inside the hashed body",
            [S(R1, "$.latency_ms", 12)],
            ["OUTPUT_HASH_RECOMPUTE", "SCHEMA_VALID"],
        )
    )
    a(
        case(
            "explanation_in_body",
            "explanation text inside the hashed response",
            [S(R1, "$.explanation_text", "synthetic")],
            ["OUTPUT_HASH_RECOMPUTE", "SCHEMA_VALID"],
        )
    )
    a(
        case(
            "content_hash_bad",
            "region graph content_sha256 does not recompute",
            [S("region_graph.json", "$.content_sha256", "0" * 64)],
            [
                "CONTENT_HASH_RECOMPUTE",
                "ID_DERIVED_FROM_HASH",
                "GRAPH_CROSS_REFERENCES",
                "SCOPE_HASH_LINKS",
            ],
            stage="post",
        )
    )
    a(
        case(
            "graph_id_not_from_hash",
            "graph_id hash segment differs from content_sha256",
            [S("region_graph.json", "$.graph_id", "rgraph:rSYN:static:0000000000000000")],
            ["ID_DERIVED_FROM_HASH"],
            stage="post",
        )
    )
    a(
        case(
            "scope_link_broken",
            "resolved_scope points at a different index hash",
            [S(R1, "$.resolved_scope.detection_index_sha256", "1" * 64)],
            ["SCOPE_HASH_LINKS"],
        )
    )
    a(
        case(
            "params_hash_bad",
            "parameter set content_sha256 wrong",
            [S("parameter_set.json", "$.content_sha256", "0" * 64)],
            ["CONTENT_HASH_RECOMPUTE", "PARAMSET_INTEGRITY", "SCOPE_HASH_LINKS"],
            stage="post",
        )
    )
    # ---- Q3
    L, LR = "q3_llm.llm_output.json", "q3_llm.response.json"
    a(
        case(
            "q3_llm_extra_field",
            "LLM output has an extra field",
            [S(L, "$.confidence", 0.9)],
            ["SCHEMA_VALID"],
        )
    )
    a(
        case(
            "q3_llm_bad_intent",
            "intent outside the closed list",
            [S(L, "$.intent", "FIND_ALL")],
            ["SCHEMA_VALID"],
        )
    )
    a(
        case(
            "q3_term_rephrased",
            "class_term is not a fragment of the user text",
            [S(L, "$.class_term", "車輛")],
            ["Q3_LLM_TERMS_LITERAL"],
        )
    )
    a(
        case(
            "q3_time_converted",
            "LLM converted the time to microseconds",
            [S(L, "$.time_literal.start", "1604000000000")],
            ["Q3_LLM_OUTPUT_STRICT", "Q3_LLM_TERMS_LITERAL"],
        )
    )
    a(
        case(
            "q3_clarify_without_question",
            "needs_clarification without a question",
            [S(L, "$.needs_clarification", True)],
            ["Q3_LLM_OUTPUT_STRICT"],
        )
    )
    a(
        case(
            "q3_clarify_executed",
            "NEEDS_CLARIFICATION still carries a query",
            [S("q3_clarify.response.json", "$.structured_query", q2_request("RULE_ONLY"))],
            ["Q3_RESPONSE_RULES"],
        )
    )
    a(
        case(
            "q3_parsed_without_call",
            "llm_parse_used true but no llm_call",
            [S(LR, "$.llm_call", None)],
            ["Q3_RESPONSE_RULES"],
        )
    )
    a(
        case(
            "q3_fallback_unrecorded",
            "rule parse after an LLM attempt without fallback",
            [
                S("q3_fallback.response.json", "$.fallback_used", False),
                S("q3_fallback.response.json", "$.fallback_reason", None),
            ],
            ["Q3_FALLBACK_CONSISTENCY"],
        )
    )
    a(
        case(
            "q3_rule_with_llm_flag",
            "parsed_by RULE but llm_parse_used true",
            [S("q3_fallback.response.json", "$.llm_parse_used", True)],
            ["COMMON_AGENT_FIELDS"],
        )
    )
    a(
        case(
            "q3_attempts_over_limit",
            "attempts exceed q3_max_llm_attempts",
            [S(LR, "$.llm_call.attempts", 5)],
            ["Q3_ATTEMPTS_WITHIN_PARAM"],
        )
    )
    a(
        case(
            "q3_query_bad_schema",
            "assembled query lacks required fields",
            [S(LR, "$.structured_query.time", None), S(LR, "$.structured_query.seed", None)],
            ["Q3_STRUCTURED_QUERY_SCHEMA"],
        )
    )
    a(
        case(
            "q3_agent_used",
            "Q3 response claims agent_used",
            [S(LR, "$.agent_used", True), S(LR, "$.agent_attempted", True)],
            ["COMMON_AGENT_FIELDS"],
        )
    )
    E = "q1_ready.explanation.json"
    a(
        case(
            "explanation_foreign_ref",
            "explanation cites a ref absent from the response",
            [{"op": "append", "file": E, "path": "$.cited_refs", "value": "CAM_Z"}],
            ["EXPLANATION_CITED_REFS"],
        )
    )
    a(
        case(
            "explanation_no_refs",
            "explanation cites nothing",
            [S(E, "$.cited_refs", [])],
            ["EXPLANATION_CITED_REFS"],
        )
    )
    a(
        case(
            "explanation_identity",
            "explanation claims the same person",
            [S(E, "$.text", "這就是同一個人。")],
            ["EXPLANATION_CITED_REFS"],
        )
    )
    # ---- candidates
    SN = "q2_rule.snapshot.json"
    a(
        case(
            "cand_order_swapped",
            "candidate list not in D28 order",
            [{"op": "swap", "file": SN, "path": "$.candidates", "i": 0, "j": 1}],
            ["CANDIDATE_ORDER_D28", "CANDIDATE_SNAPSHOT_HASH"],
            stage="post",
        )
    )
    a(
        case(
            "cand_topological",
            "a TOPOLOGICAL_ONLY path listed as candidate",
            [S(SN, "$.candidates[0].path_traversability", "TOPOLOGICAL_ONLY")],
            ["CANDIDATE_TOPOLOGICAL_EXCLUDED"],
        )
    )
    a(
        case(
            "cand_excluded_wrong_reason",
            "TOPOLOGICAL_ONLY exclusion recorded with another reason",
            [S(SN, "$.excluded_transitions[0].reason", "CLOSED_EDGE")],
            ["CANDIDATE_TOPOLOGICAL_EXCLUDED"],
        )
    )
    a(
        case(
            "cand_detection_in_ranking",
            "detection count in ranking_basis",
            [S(SN, "$.candidates[0].ranking_basis.detection_count", 3)],
            ["CANDIDATE_ORDER_D28"],
        )
    )
    a(
        case(
            "cand_tier_wrong",
            "relation_tier inconsistent with relation",
            [S(SN, "$.candidates[1].ranking_basis.relation_tier", 1)],
            ["CANDIDATE_ORDER_D28"],
        )
    )
    a(
        case(
            "cand_duplicate_camera",
            "one camera listed twice",
            [
                S(SN, "$.candidates[2].camera_id", "CAM_B"),
                S(SN, "$.candidates[2].ranking_basis.camera_id", "CAM_B"),
            ],
            ["CANDIDATE_ORDER_D28", "CANDIDATE_TOPOLOGICAL_EXCLUDED"],
        )
    )
    a(
        case(
            "cand_over_top_k",
            "more candidates than top_k",
            [S("parameter_set.json", pi("top_k"), 2)],
            ["CANDIDATE_REFS_AND_LIMITS"],
        )
    )
    a(
        case(
            "cand_ref_prefix_wrong",
            "candidate_ref does not embed the snapshot hash",
            [S(SN, "$.candidates[0].candidate_ref", "cand:ffffffffffffffff:1")],
            ["CANDIDATE_REFS_AND_LIMITS", "DECISION_CANDIDATE_LEGALITY"],
            stage="post",
        )
    )
    # ---- decisions
    D = "q2_rule.decisions.jsonl"
    bad_ref = "cand:0000000000000000:9"
    a(
        case(
            "dec_switch_outside_snapshot",
            "accepted switch to a candidate that is not in the snapshot",
            [
                S(D, "$[1].executed_candidate_ref", bad_ref),
                S(D, "$[1].submitted.candidate_ref", bad_ref),
                S(D, "$[1].candidates_considered[1].candidate_ref", bad_ref),
            ],
            [
                "DECISION_CANDIDATE_LEGALITY",
                "DECISION_EVIDENCE_AND_ENTRY",
                "DECISION_REJECTION_CORRECTNESS",
                "Q2_SWITCH_CAMERA_LEGAL",
            ],
        )
    )
    a(
        case(
            "dec_topological_switch",
            "accepted switch along a TOPOLOGICAL_ONLY path",
            [S(SN, "$.candidates[1].path_traversability", "TOPOLOGICAL_ONLY")],
            ["DECISION_CANDIDATE_LEGALITY", "CANDIDATE_TOPOLOGICAL_EXCLUDED"],
        )
    )
    a(
        case(
            "dec_skipped_rank",
            "candidate evidence taken out of order",
            [S(D, "$[1].candidates_considered[1].rank", 3)],
            ["DECISION_SEQUENTIAL_ORDER", "DECISION_CANDIDATE_LEGALITY"],
        )
    )
    a(
        case(
            "dec_no_evidence",
            "switch without fetched evidence",
            [S(D, "$[1].candidates_considered[1].evidence_sha256", None)],
            ["DECISION_SEQUENTIAL_ORDER", "DECISION_REJECTION_CORRECTNESS"],
        )
    )
    a(
        case(
            "dec_below_guard",
            "switch to MATCH_WEAK accepted (record and evidence agree on WEAK)",
            [
                S(D, "$[1].candidates_considered[1].target_presence", "MATCH_WEAK"),
                S("q2_rule.evidence_2.json", "$.target_presence", "MATCH_WEAK"),
                S("q2_rule.evidence_2.json", "$.best_observations[0].color_verdict", "WEAK"),
            ],
            ["DECISION_SWITCH_GUARD"],
        )
    )
    a(
        case(
            "dec_exclusion_reason_wrong",
            "rule fallback records the wrong exclusion reason",
            [S(D, "$[1].candidates_considered[0].exclusion_reason", "BELOW_SWITCH_GUARD")],
            ["DECISION_SEQUENTIAL_ORDER"],
        )
    )
    a(
        case(
            "dec_accepted_with_code",
            "accepted but rejection_code set",
            [S(D, "$[1].rejection_code", "UNKNOWN_REF")],
            ["DECISION_FIELD_CONSISTENCY"],
        )
    )
    a(
        case(
            "dec_rule_with_llm",
            "RULE_ONLY decision calls an LLM",
            [
                {"op": "append", "file": D, "path": "$[1].llm_calls", "value": llm_call(9)},
                S(D, "$[1].session_agent_rounds_used", 1),  # keep the D69 counter consistent
            ],
            ["DECISION_FIELD_CONSISTENCY", "Q2_RESPONSE_VS_DECISIONS"],
        )
    )
    A = "q2_agent.decisions.jsonl"
    a(
        case(
            "dec_agent_without_llm",
            "Agent decision with no recorded LLM call",
            [S(A, "$[2].llm_calls", [])],
            ["DECISION_FIELD_CONSISTENCY"],
        )
    )
    a(
        case(
            "dec_rounds_over",
            "rounds_used above the limit without ROUND_LIMIT",
            [S(A, "$[2].rounds_used", 9)],
            ["DECISION_BUDGET_LIMITS"],
        )
    )
    a(
        case(
            "dec_budget_over",
            "budget exceeded without TIME_BUDGET",
            [S(A, "$[2].budget_used_ms", 99999)],
            ["DECISION_BUDGET_LIMITS"],
        )
    )
    a(
        case(
            "dec_state_illegal",
            "SEARCHING record claims PLAYING -> PLAYING",
            [S(D, "$[1].state_before", "PLAYING")],
            ["SESSION_STATE_MACHINE"],
        )
    )
    a(
        case(
            "dec_time_backwards",
            "source time goes backwards",
            [S(D, "$[0].source_time_us", 20_000_000)],
            ["SESSION_STATE_MACHINE"],
        )
    )
    a(
        case(
            "dec_step_duplicate",
            "duplicate step_index",
            [S(D, "$[1].step_index", 0)],
            ["SESSION_STATE_MACHINE"],
        )
    )
    a(
        case(
            "dec_unknown_ref_accepted",
            "controller accepted an unknown candidate_ref",
            [S(A, "$[1].accepted", True), S(A, "$[1].rejection_code", None)],
            ["DECISION_REJECTION_CORRECTNESS", "DECISION_FIELD_CONSISTENCY"],
        )
    )
    a(
        case(
            "dec_stale_snapshot_accepted",
            "stale snapshot submission accepted",
            [
                S("q2_agent.agent_decision.json", "$.candidate_snapshot_sha256", "2" * 64),
                S("q2_agent.agent_decision.json", "$.candidate_ref", "cand:0000000000000000:2"),
                S(A, "$[1].accepted", True),
                S(A, "$[1].rejection_code", None),
                {"op": "rehash_decisions", "file": A},
            ],
            [
                "DECISION_REJECTION_CORRECTNESS",
                "DECISION_FIELD_CONSISTENCY",
                "Q2_DECISIONS_FILE_HASH",  # the journal changed after the response hashed its bytes
            ],
            stage="post",
            text="STALE_SNAPSHOT",
        )
    )
    a(
        case(
            "dec_content_hash_bad",
            "decision content_sha256 wrong",
            [S(D, "$[1].content_sha256", "0" * 64)],
            ["CONTENT_HASH_RECOMPUTE", "Q2_DECISIONS_FILE_HASH"],
            stage="post",
        )
    )
    a(
        case(
            "agent_decision_empty_rationale",
            "NEXT_CANDIDATE without a reason",
            [
                S("q2_agent.agent_decision.json", "$.action", "NEXT_CANDIDATE"),
                S("q2_agent.agent_decision.json", "$.rationale", " "),
            ],
            ["AGENT_DECISION_FORMAT"],
        )
    )
    # ---- Q2 response
    QA, QR = "q2_agent.response.json", "q2_rule.response.json"
    a(
        case(
            "q2_first_fallback_wrong",
            "first fallback reason differs from records",
            [S(QA, "$.fallback_reason", "TIME_BUDGET")],
            ["Q2_RESPONSE_VS_DECISIONS"],
        )
    )
    a(
        case(
            "q2_agent_attempted_false",
            "records show LLM calls but agent_attempted false",
            [S(QA, "$.agent_attempted", False)],
            ["Q2_RESPONSE_VS_DECISIONS", "COMMON_AGENT_FIELDS"],
        )
    )
    a(
        case(
            "q2_agent_used_false",
            "accepted Agent decision but agent_used false",
            [S(QA, "$.agent_used", False)],
            ["Q2_RESPONSE_VS_DECISIONS"],
        )
    )
    a(
        case(
            "q2_mode_not_authorized",
            "AGENT_SEQUENTIAL requested but ran RULE_ONLY without MODE_NOT_AUTHORIZED",
            [S("q2_rule.request.json", "$.switch_mode", "AGENT_SEQUENTIAL")],
            ["Q2_RESPONSE_VS_DECISIONS"],
        )
    )
    a(
        case(
            "q2_wrong_camera",
            "switch segment shows a camera that is not the accepted candidate",
            [S(QR, "$.timeline[2].camera_id", "CAM_E")],
            ["Q2_SWITCH_CAMERA_LEGAL"],
        )
    )
    a(
        case(
            "q2_gap_position",
            "a position is drawn inside a blind gap",
            [S(QR, "$.timeline[1].position", [1.0, 2.0])],
            ["SCHEMA_VALID", "Q2_TIMELINE_STRUCTURE"],
        )
    )
    a(
        case(
            "q2_segments_overlap",
            "timeline segments overlap",
            [S(QR, "$.timeline[1].range_us", [8_400_000, 14_000_000])],
            ["Q2_TIMELINE_STRUCTURE"],
        )
    )
    a(
        case(
            "q2_switch_without_decision",
            "SWITCH entry without decision_id",
            [{"op": "del", "file": QR, "path": "$.timeline[2].decision_id"}],
            ["Q2_TIMELINE_STRUCTURE", "Q2_SWITCH_CAMERA_LEGAL"],
        )
    )
    a(
        case(
            "q2_complete_partial_time",
            "COMPLETE although part of the time is uncovered",
            [
                S(
                    QR,
                    "$.resolved_scope.time_coverage",
                    {"coverage_complete": False, "uncovered_wall_ranges": [[wall(30), wall(40)]]},
                )
            ],
            ["TIME_COVERAGE_INTERNAL", "TIME_COVERAGE_RECOMPUTE"],
        )
    )
    a(
        case(
            "q2_no_seed_with_timeline",
            "NO_SEED but a timeline is returned",
            [S(QR, "$.status", "NO_SEED")],
            ["Q2_TIMELINE_STRUCTURE"],
        )
    )
    a(
        case(
            "q2_timeline_short",
            "COMPLETE timeline does not reach the end of the range",
            [S(QR, "$.timeline[2].range_us", [ENTRY_US, 18_000_000])],
            ["Q2_TIMELINE_STRUCTURE"],
        )
    )
    # ---- index / records
    M, RC = "detection_index.json", "detection_index.records.jsonl"
    a(
        case(
            "index_ranges_overlap",
            "sampled ranges overlap",
            [
                S(
                    M,
                    "$.sampling.per_camera[0].sampled_ranges_us",
                    [[0, 30_000_000], [20_000_000, 60_000_000]],
                )
            ],
            ["INDEX_MANIFEST_RULES"],
        )
    )
    a(
        case(
            "index_inferred_outside_sampled",
            "inferred range outside the sampled range",
            [S(M, "$.sampling.per_camera[0].sampled_ranges_us", [[0, 30_000_000]])],
            ["INDEX_MANIFEST_RULES"],
        )
    )
    a(
        case(
            "records_inferred_null",
            "INFERRED frame with detections null",
            [S(RC, "$[1].detections", None)],
            ["RECORDS_FRAME_STATE"],
        )
    )
    a(
        case(
            "records_missing_empty_array",
            "MISSING frame reads as 'no detection'",
            [S(RC, "$[3].detections", [])],
            ["RECORDS_FRAME_STATE"],
        )
    )
    a(
        case(
            "records_not_inferred_no_reason",
            "NOT_INFERRED without a reason",
            [S(RC, f"{ri('CAM_C', 0)}.state_reason", None)],
            ["RECORDS_FRAME_STATE"],
        )
    )
    a(
        case(
            "records_unsorted",
            "records not sorted by (camera, frame)",
            [
                S(RC, f"{ri('CAM_B', 0)}.camera_id", "CAM_A"),
                S(RC, f"{ri('CAM_B', 0)}.frame_ref", "frame:RUN_X:CAM_A:0"),
            ],
            ["RECORDS_FRAME_STATE", "RECORDS_OBSERVATION_IDS"],
        )
    )
    a(
        case(
            "records_obs_ordinal_wrong",
            "observation ordinal is not the position",
            [S(RC, "$[0].detections[1].observation_id", "obs:0123456789abcdef:CAM_A:0:5")],
            ["RECORDS_OBSERVATION_IDS"],
        )
    )
    a(
        case(
            "records_color_on_car",
            "colour computed for a class outside applies_to_classes",
            [
                S(
                    RC,
                    "$[0].detections[1].color",
                    {
                        "method_version": "synthetic-hsv-v0",
                        "crop_box_xyxy_px": [0, 0, 10, 10],
                        "crop_pixels": 100,
                        "hsv_stats": {"hue_hist": [], "sat_mean": 0.1, "val_mean": 0.1},
                        "verdicts": {"red": "NONE", "blue": "NONE"},
                        "unknown_reason": None,
                    },
                )
            ],
            ["RECORDS_COLOR_RULES"],
        )
    )
    a(
        case(
            "records_verdict_label_missing",
            "verdicts miss a vocabulary colour",
            [{"op": "del", "file": RC, "path": "$[0].detections[0].color.verdicts.blue"}],
            ["RECORDS_COLOR_RULES"],
        )
    )
    a(
        case(
            "records_unknown_no_reason",
            "UNKNOWN verdict without unknown_reason",
            [S(RC, f"{ri('CAM_B', 2)}.detections[0].color.unknown_reason", None)],
            ["RECORDS_COLOR_RULES"],
        )
    )
    a(
        case(
            "records_below_floor",
            "stored score below index_score_floor",
            [S(RC, f"{ri('CAM_B', 2)}.detections[0].score", 0.05)],
            ["RECORDS_SCORE_FLOOR"],
        )
    )
    a(
        case(
            "records_file_hash_wrong",
            "manifest records_file_sha256 differs from the file",
            [S(M, "$.records_file_sha256", "3" * 64)],
            ["INDEX_RECORDS_FILE_HASH", "CONTENT_HASH_RECOMPUTE"],
            stage="post",
        )
    )
    a(
        case(
            "records_inferred_outside_range",
            "INFERRED frame on a camera that has no inferred range",
            [
                S(RC, f"{ri('CAM_C', 0)}.frame_state", "INFERRED"),
                S(RC, f"{ri('CAM_C', 0)}.state_reason", None),
                S(RC, f"{ri('CAM_C', 0)}.detections", []),
            ],
            ["RECORDS_MATCH_MANIFEST"],
        )
    )
    # ---- graphs
    RG, CG = "region_graph.json", "camera_graph.json"
    a(
        case(
            "graph_stair_edge",
            "STAIR edge in v1",
            [S(RG, "$.edges[0].via.kind", "STAIR")],
            ["GRAPH_STRUCTURE"],
        )
    )
    a(
        case(
            "graph_one_way_without_ends",
            "ONE_WAY edge without from/to",
            [S(RG, "$.edges[0].direction", "ONE_WAY")],
            ["GRAPH_STRUCTURE"],
        )
    )
    a(
        case(
            "graph_approved_without_ref",
            "APPROVED graph without approval_ref",
            [S(RG, "$.approval_ref", None)],
            ["GRAPH_STRUCTURE"],
        )
    )
    a(
        case(
            "graph_stores_actual_route",
            "camera graph stores a person's actual next camera",
            [S(CG, "$.transitions[0].actual_next_camera", "CAM_B")],
            ["NO_FORBIDDEN_CONTENT", "SCHEMA_VALID"],
        )
    )
    a(
        case(
            "graph_input_event_script",
            "graph built from an event file",
            [S(CG, "$.inputs[0].ref", "event_a1.query.json")],
            ["NO_FORBIDDEN_CONTENT"],
        )
    )
    a(
        case(
            "graph_input_detection_index",
            "graph built from the detection index",
            [S(CG, "$.inputs[0].ref", "detidx:rSYN:RUN_X:0000000000000000")],
            ["NO_FORBIDDEN_CONTENT"],
        )
    )
    a(
        case(
            "graph_traversability_not_propagated",
            "TOPOLOGICAL_ONLY edge but transition says APPROVED_WALKABLE",
            [S(CG, "$.transitions[3].path_traversability", "APPROVED_WALKABLE")],
            ["GRAPH_CROSS_REFERENCES", "CANDIDATE_TOPOLOGICAL_EXCLUDED"],
        )
    )
    a(
        case(
            "graph_bad_edge_path",
            "edge_path does not follow region_path",
            [S(CG, "$.transitions[1].edge_path", ["E_1_2", "E_2_5"])],
            ["GRAPH_CROSS_REFERENCES"],
        )
    )
    a(
        case(
            "graph_hops_wrong",
            "region_hops differs from the path",
            [S(CG, "$.transitions[1].region_hops", 5)],
            ["GRAPH_STRUCTURE"],
        )
    )
    a(
        case(
            "graph_manual_roi_without_frame",
            "manual ROI without a static frame",
            [{"op": "del", "file": CG, "path": "$.cameras[0].exit_zones[0].static_frame_sha256"}],
            ["GRAPH_STRUCTURE"],
        )
    )
    a(
        case(
            "graph_unknown_state_not_flagged",
            "edge state UNKNOWN but path_has_unknown_state false",
            [S(RG, "$.edges[0].state", "UNKNOWN")],
            ["GRAPH_CROSS_REFERENCES"],
        )
    )
    # ---- clock mapping, schema, misc
    CM = "clock_mapping.json"
    a(
        case(
            "clock_offset_wrong",
            "wall_origin offset does not match Asia/Taipei",
            [S(CM, "$.wall_origin", "2026-11-01T13:00:00+09:00")],
            ["CLOCK_MAPPING_RULES", "TIME_COVERAGE_RECOMPUTE"],
        )
    )
    a(case("clock_rate_two", "rate other than 1", [S(CM, "$.rate", 2)], ["SCHEMA_VALID"]))
    a(
        case(
            "error_wrong_http_status",
            "FORBIDDEN_INFERENCE_INPUT with HTTP 200",
            [S("q1_belowfloor.response.json", "$.http_status", 200)],
            ["ERROR_RESPONSE_RULES"],
        )
    )
    a(
        case(
            "unclassified_file",
            "JSON file with no known schema_version",
            [{"op": "add_file", "file": "junk.json", "data": {"x": 1}}],
            ["DOCUMENT_LOADABLE"],
        )
    )
    a(
        case(
            "nan_in_file",
            "NaN in a JSON file",
            [
                {
                    "op": "add_raw",
                    "file": "nan.json",
                    "text": '{"schema_version": "q-demo.q1-request.v1", "x": NaN}',
                }
            ],
            ["DOCUMENT_LOADABLE"],
        )
    )
    a(
        case(
            "float_microseconds",
            "a _us field written as a float",
            [S(R1, "$.results[0].matched_segments[0].range_us", [0.5, 400000])],
            ["SCHEMA_VALID", "Q1_RESULT_ORDER"],
        )
    )
    # ================================================================ contract 3873ff2 additions
    PS = "parameter_set.json"
    A, QA = "q2_agent.decisions.jsonl", "q2_agent.response.json"
    # ---- section 2.2: hash preimages of self-derived ids (U21 / U22 / U24)
    valid = finalize(valid_files())
    index_content_hash = valid[M]["content_sha256"]
    a(
        case(
            "index_id_from_content_hash",
            "index_id hash segment taken from content_sha256 instead of the index key",
            [S(M, "$.index_id", f"detidx:{REV}:{RUN}:{index_content_hash[:16]}")],
            ["ID_DERIVED_FROM_HASH", "SCOPE_HASH_LINKS", "RECORDS_OBSERVATION_IDS"],
            stage="post",
        )
    )
    a(
        case(
            "obs_segment_not_index_key",
            "an observation_id embeds another hash segment than the manifest's index key",
            [S(RC, "$[0].detections[0].observation_id", "obs:ffffffffffffffff:CAM_A:0:0")],
            ["RECORDS_OBSERVATION_IDS"],
        )
    )
    a(
        case(
            "index_id_two_contents",
            "a second manifest with the same index_id but another content_sha256",
            [
                {"op": "copy_file", "from": M, "to": "detection_index_dup.json"},
                S("detection_index_dup.json", "$.records_file_sha256", "4" * 64),
                {"op": "rehash_manifest", "file": "detection_index_dup.json"},
            ],
            ["INDEX_MANIFEST_RULES", "INDEX_RECORDS_FILE_HASH"],
            stage="post",
        )
    )
    a(
        case(
            "snapshot_hash_wrong",
            "candidate snapshot changed without recomputing candidate_snapshot_sha256",
            [S(SN, "$.candidate_set_complete", False)],
            ["CANDIDATE_SNAPSHOT_HASH"],
            stage="post",
        )
    )
    a(
        case(
            "paramset_id_not_from_hash",
            "parameter_set_id hash segment differs from content_sha256",
            [S(PS, "$.parameter_set_id", "pset:q-demo:0000000000000000")],
            ["PARAMSET_INTEGRITY", "SCOPE_HASH_LINKS"],
            stage="post",
        )
    )
    # ---- section 4.2 / 4.4: detector record, index grid
    a(
        case(
            "index_load_not_strict",
            "detector.load.strict is false",
            [S(M, "$.detector.load.strict", False)],
            ["SCHEMA_VALID"],
        )
    )
    a(
        case(
            "index_class_map_source_hash",
            "class_map.content_sha256 replaced by the source-file hash",
            [S(M, "$.detector.class_map.content_sha256", H("class-map-source"))],
            ["INDEX_MANIFEST_RULES"],
        )
    )
    a(
        case(
            "index_num_classes_differ",
            "load.num_classes differs from class_map.num_classes",
            [S(M, "$.detector.load.num_classes", 81)],
            ["INDEX_MANIFEST_RULES"],
        )
    )
    a(
        case(
            "index_nms_iou_without_nms",
            "nms.applied false but iou set",
            [S(M, "$.detector.nms.iou", 0.7)],
            ["INDEX_MANIFEST_RULES"],
        )
    )
    a(
        case(
            "index_interval_not_stride_product",
            "index_interval_us differs from stride_samples x source_frame_interval_us",
            [S(M, "$.sampling.per_camera[4].index_interval_us", 600_000)],
            ["INDEX_MANIFEST_RULES", "Q2_FAIL_CLOSED_ON_GRID_MISMATCH"],
        )
    )
    a(
        case(
            "records_not_sampled_on_grid",
            "a frame on the index grid is NOT_SAMPLED",
            [
                S(RC, f"{ri('CAM_A', 2)}.frame_state", "NOT_SAMPLED"),
                S(RC, f"{ri('CAM_A', 2)}.detections", None),
            ],
            ["RECORDS_INDEX_GRID"],
        )
    )
    a(
        case(
            "records_inferred_off_grid",
            "a frame off the index grid is INFERRED",
            [
                S(RC, f"{ri('CAM_A', 3)}.frame_state", "INFERRED"),
                S(RC, f"{ri('CAM_A', 3)}.detections", []),
            ],
            ["RECORDS_INDEX_GRID"],
        )
    )
    # ---- section 5.3 / 5.4: ranking area, tier order, no secondary keys
    a(
        case(
            "cand_overlap_with_unknown_edge_tier1",
            "an OVERLAP whose path has an UNKNOWN edge keeps tier 1 (must be 3)",
            [S(SN, "$.candidates[0].path_has_unknown_state", True)],
            ["CANDIDATE_ORDER_D28"],
        )
    )
    a(
        case(
            "cand_secondary_key",
            "region_hops added to ranking_basis as a secondary key",
            [S(SN, "$.candidates[0].ranking_basis.region_hops", 0)],
            ["CANDIDATE_ORDER_D28"],
        )
    )
    a(
        case(
            "cand_area_differs_from_graph",
            "overlap_area_m2 differs from the transition's ranking_area_m2",
            [S(CG, "$.transitions[1].ranking_area_m2", 7.0)],
            ["CANDIDATE_RANKING_AREA"],
        )
    )
    a(
        case(
            "graph_area_without_refs",
            "ranking_area_m2 given without ranking_area_refs",
            [S(CG, "$.transitions[1].ranking_area_refs", [])],
            ["GRAPH_STRUCTURE"],
        )
    )
    # ---- section 8.2: gap threshold, link records, grid mismatch
    LK = "q2_rule.links.jsonl"
    a(
        case(
            "link_gap_not_counting_failed_cell",
            "gap_samples of a failing cell forgets to count the current cell (2 instead of 3)",
            [S(LK, "$[5].gap_samples", 2)],
            ["LINK_RECORD_GAP_RULES", "SEARCHING_TRIGGER_TIME"],
        )
    )
    a(
        case(
            "link_gap_counting_linked_cell",
            "a LINKED record counts the linked cell (3 instead of 2)",
            [S(LK, "$[2].gap_samples", 3)],
            ["LINK_RECORD_GAP_RULES"],
        )
    )
    a(
        case(
            "link_elapsed_off_grid",
            "elapsed_us is not a multiple of index_interval_us",
            [S(LK, "$[0].elapsed_us", 300_000)],
            ["LINK_RECORD_GAP_RULES"],
        )
    )
    early = [
        S(D, "$[1].decision_time_us", 8_800_000),
        S("q2_rule.evidence_1.json", "$.decision_time_us", 8_800_000),
        S("q2_rule.evidence_2.json", "$.decision_time_us", 8_800_000),
    ]
    a(
        case(
            "searching_one_cell_early",
            "SEARCHING starts at gap_samples 2 (not beyond link_max_gap_samples 2)",
            early,
            ["SEARCHING_TRIGGER_TIME"],
        )
    )
    late = [
        S(D, "$[1].decision_time_us", 9_600_000),
        S("q2_rule.evidence_1.json", "$.decision_time_us", 9_600_000),
        S("q2_rule.evidence_2.json", "$.decision_time_us", 9_600_000),
    ]
    a(
        case(
            "searching_one_cell_late",
            "SEARCHING starts one cell after the threshold was exceeded",
            late,
            ["SEARCHING_TRIGGER_TIME"],
        )
    )
    mismatch_interval = [S(PS, "$.applies_to.index_interval_us", SRC_US)]
    a(
        case(
            "grid_applies_to_interval_differs",
            "parameter set built for another index_interval_us, responses served normally",
            mismatch_interval,
            ["Q2_FAIL_CLOSED_ON_GRID_MISMATCH"],
        )
    )
    a(
        case(
            "grid_gap_not_a_multiple",
            "link_max_gap_us is not a multiple of index_interval_us, responses served normally",
            [S(PS, pi("link_max_gap_us"), 1_000_000), S(PS, pi("link_max_gap_samples"), None)],
            ["Q2_FAIL_CLOSED_ON_GRID_MISMATCH"],
        )
    )
    a(
        case(
            "grid_gap_below_interval",
            "link_max_gap_us is smaller than one index cell",
            [S(PS, pi("link_max_gap_us"), SRC_US), S(PS, pi("link_max_gap_samples"), None)],
            ["Q2_FAIL_CLOSED_ON_GRID_MISMATCH"],
        )
    )
    a(
        case(
            "grid_listed_samples_not_derived",
            "listed link_max_gap_samples differs from link_max_gap_us / index_interval_us - 1",
            [S(PS, pi("link_max_gap_samples"), 3)],
            ["Q2_FAIL_CLOSED_ON_GRID_MISMATCH"],
        )
    )
    a(
        case(
            "grid_camera_interval_differs",
            "a used camera has another index_interval_us than the parameter set (other source frame interval, same stride)",
            [
                S(M, "$.sampling.per_camera[3].source_frame_interval_us", 3 * SRC_US),
                S(M, "$.sampling.per_camera[3].index_interval_us", STRIDE * 3 * SRC_US),
            ],
            ["Q2_FAIL_CLOSED_ON_GRID_MISMATCH"],
        )
    )
    a(
        case(
            "grid_ok_but_rejected",
            "PARAMETER_GRID_MISMATCH answered although the grid matches",
            grid_reply("q2_rule.response.json"),
            ["Q2_FAIL_CLOSED_ON_GRID_MISMATCH"],
        )
    )
    a(
        case(
            "grid_mismatch_as_error_code",
            "grid mismatch answered with the v0.2.1 error response instead of the D69 reason",
            mismatch_interval
            + [
                {
                    "op": "add_file",
                    "file": "q2_rule.response.json",
                    "data": {"error_code": "PARAMETER_GRID_MISMATCH", "message": "synthetic"},
                }
            ],
            ["Q2_FAIL_CLOSED_ON_GRID_MISMATCH", "ERROR_RESPONSE_RULES"],
            text="not an error code",
        )
    )
    a(
        case(
            "grid_mismatch_still_executed",
            "grid mismatch gives the reason but still runs the session (status PARTIAL, timeline kept)",
            mismatch_interval
            + [
                S("q2_rule.response.json", "$.status", "PARTIAL"),
                S("q2_rule.response.json", "$.reason", "PARAMETER_GRID_MISMATCH"),
            ],
            ["Q2_FAIL_CLOSED_ON_GRID_MISMATCH", "Q2_REASON_STATUS"],
        )
    )
    # ---- section 11: parameter approval
    a(
        case(
            "params_not_approved_ready",
            "parameter set is only PROPOSED but responses are READY / COMPLETE",
            [
                S(PS, "$.approval.status", "PROPOSED"),
                S(PS, "$.approval.approved_by", None),
                S(PS, "$.approval.approval_ref", None),
            ],
            ["PARAMS_APPROVAL_GATES_STATUS"],
        )
    )
    # ---- section 8.3: presence judging order and entry observation
    EC = "evidence_case_{}.json"
    a(
        case(
            "ev_unknown_mixed_as_no_color_match",
            "NONE mixed with UNKNOWN reported as PERSON_NO_COLOR_MATCH",
            [S(EC.format("color_unknown_mixed"), "$.target_presence", "PERSON_NO_COLOR_MATCH")],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "ev_partial_with_nothing_evaluated",
            "PARTIAL_EVIDENCE although evaluated == 0",
            [
                S(EC.format("not_evaluated"), "$.target_presence", "PARTIAL_EVIDENCE"),
                S(EC.format("not_evaluated"), "$.partial_basis", "NO_PERSON_DETECTED"),
            ],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "ev_empty_window_is_covered",
            "an empty window (N == 0) reported as NO_PERSON_DETECTED with complete coverage",
            [
                S(EC.format("empty_window"), "$.target_presence", "NO_PERSON_DETECTED"),
                S(EC.format("empty_window"), "$.coverage_complete", True),
            ],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "ev_negative_over_gaps",
            "NO_PERSON_DETECTED although 9 of 15 index cells were not inferred",
            [
                S(EC.format("partial"), "$.target_presence", "NO_PERSON_DETECTED"),
                S(EC.format("partial"), "$.partial_basis", None),
            ],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "ev_all_evaluated_not_evaluated",
            "NOT_EVALUATED although all cells were evaluated",
            [S(EC.format("no_person"), "$.target_presence", "NOT_EVALUATED")],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "ev_not_sampled_counted_in_n",
            "coverage_complete false because not_sampled cells were counted into N",
            [S(EC.format("no_person"), "$.coverage_complete", False)],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "ev_strong_without_strong_box",
            "MATCH_STRONG whose best observation is only WEAK",
            [S(EC.format("after_decision_only"), "$.best_observations[0].color_verdict", "WEAK")],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "ev_entry_before_decision_time",
            "entry observation earlier than decision_time_us",
            [
                S(
                    EC.format("after_decision_only"),
                    "$.entry_observation_id",
                    "obs:0123456789abcdef:CAM_X:45:0",
                ),
                S(EC.format("after_decision_only"), "$.entry_timestamp_us", 9_000_000),
            ],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "dec_switch_without_entry",
            "accepted SWITCH without entry_observation_id",
            [S(D, "$[1].entry_observation_id", None)],
            ["DECISION_EVIDENCE_AND_ENTRY"],
        )
    )
    a(
        case(
            "dec_source_time_before_decision_time",
            "source_time_us earlier than decision_time_us",
            [S(D, "$[1].source_time_us", 9_000_000)],
            ["DECISION_EVIDENCE_AND_ENTRY"],
        )
    )
    a(
        case(
            "q2_switch_before_entry",
            "the SWITCH segment starts before the evidence's entry_timestamp_us (time goes back)",
            [
                S(QR, "$.timeline[1].range_us", [8_400_000, 12_800_000]),
                S(QR, "$.timeline[2].range_us", [12_800_000, 21_000_000]),
            ],
            ["Q2_SWITCH_CAMERA_LEGAL"],
        )
    )
    skipped_candidate = [
        S(D, "$[1].candidates_considered[0].target_presence", "MATCH_STRONG"),
        S("q2_rule.evidence_1.json", "$.target_presence", "MATCH_STRONG"),
        S("q2_rule.evidence_1.json", "$.best_observations[0].color_verdict", "STRONG"),
        S("q2_rule.evidence_1.json", "$.entry_observation_id", "obs:0123456789abcdef:CAM_D:50:0"),
        S("q2_rule.evidence_1.json", "$.entry_timestamp_us", 10_000_000),
    ]
    a(
        case(
            "rule_skips_candidate_with_entry",
            "the rule steps past a guard-reaching candidate that has an entry observation",
            skipped_candidate,
            ["DECISION_SWITCH_GUARD"],
        )
    )
    a(
        case(
            "n6_agent_used_after_rejections_only",
            "agent_used true although no Agent step was accepted (only tool use / rejections)",
            [
                S(A, "$[2].accepted", False),
                S(A, "$[2].rejection_code", "ILLEGAL_ORDER"),
                S(A, "$[2].executed_action", None),
                S(A, "$[2].executed_candidate_ref", None),
            ],
            ["Q2_RESPONSE_VS_DECISIONS"],
        )
    )
    # ---- v0.3.0-rc1: D69 / D71 / #135 clarifications on the staging contract
    QN = "q2_noseed.response.json"
    LA = "q2_agent.links.jsonl"
    a(
        case(
            "dec_missing_d69_counters",
            "decision record without searching_index (D69)",
            [{"op": "del", "file": D, "path": "$[1].searching_index"}],
            ["SCHEMA_VALID", "DECISION_SESSION_COUNTERS"],
        )
    )
    a(
        case(
            "dec_searching_index_not_counted",
            "a record inside a SEARCHING keeps searching_index 0",
            [S(D, "$[1].searching_index", 0)],
            ["DECISION_SESSION_COUNTERS"],
        )
    )
    a(
        case(
            "dec_searching_index_changes_within_snapshot",
            "two records of the same snapshot carry different searching_index values",
            [S(A, "$[2].searching_index", 2)],
            ["DECISION_SESSION_COUNTERS"],
        )
    )
    a(
        case(
            "dec_agent_rounds_below_calls",
            "session_agent_rounds_used is 1 although two LLM calls are recorded so far",
            [S(A, "$[2].session_agent_rounds_used", 1)],
            ["DECISION_SESSION_COUNTERS"],
        )
    )
    a(
        case(
            "dec_agent_rounds_reset",
            "the session total goes back from 2 to 0 (reset by the fallback)",
            [S(A, "$[3].session_agent_rounds_used", 0)],
            ["DECISION_SESSION_COUNTERS"],
        )
    )
    a(
        case(
            "q2_links_hash_wrong",
            "links_sha256 is not the hash of the link journal's bytes",
            [S(QR, "$.links_sha256", "5" * 64)],
            ["Q2_LINKS_FILE_HASH"],
        )
    )
    a(
        case(
            "q2_links_ref_missing",
            "Q2 response without links_ref (D69)",
            [{"op": "del", "file": QR, "path": "$.links_ref"}],
            ["SCHEMA_VALID"],
        )
    )
    a(
        case(
            "link_without_schema_version",
            "a link record without schema_version q-demo.link-record.v2",
            [{"op": "del", "file": LK, "path": "$[0].schema_version"}],
            ["SCHEMA_VALID"],
        )
    )
    a(
        case(
            "link_index_gap",
            "link_index skips a number",
            [S(LK, "$[3].link_index", 5)],
            ["LINK_RECORD_FIELDS"],
        )
    )
    a(
        case(
            "link_unlinked_with_next",
            "a NO_CANDIDATE cell names a next observation",
            [S(LK, "$[0].next_observation_id", f"obs:{OBS_SEG}:CAM_A:2:0")],
            ["LINK_RECORD_FIELDS"],
        )
    )
    a(
        case(
            "link_ambiguous_without_candidates",
            "AMBIGUOUS_LINK without its ambiguous_candidates list",
            [S(LK, "$[0].decision", "AMBIGUOUS_LINK")],
            ["LINK_RECORD_FIELDS"],
        )
    )
    a(
        case(
            "link_candidates_on_linked_cell",
            "a LINKED cell carries ambiguous_candidates",
            [
                S(
                    LK,
                    "$[2].ambiguous_candidates",
                    [{"observation_id": f"obs:{OBS_SEG}:CAM_A:6:0", "iou": 0.55}],
                )
            ],
            ["LINK_RECORD_FIELDS"],
        )
    )
    a(
        case(
            "link_two_sessions_in_one_journal",
            "one link journal mixes two sessions",
            [S(LA, "$[4].session_id", "sess_other")],
            ["LINK_RECORD_FIELDS"],
        )
    )
    a(
        case(
            "empty_journal_but_agent_attempted",
            "the NO_SEED session has empty journals but claims an Agent attempt",
            [S(QN, "$.agent_attempted", True)],
            ["Q2_RESPONSE_VS_DECISIONS"],
        )
    )
    a(
        case(
            "empty_file_without_journal_name",
            "a 0-byte JSONL that is not <session>.decisions / .links is still an unknown document",
            [{"op": "add_raw", "file": "stray.jsonl", "text": ""}],
            ["DOCUMENT_LOADABLE"],
        )
    )
    a(
        case(
            "ev_nocolor_verdict_strong",
            "a colour-less summary marks one person box STRONG",
            [
                {
                    "op": "append",
                    "file": EC.format("nocolor_strong"),
                    "path": "$.best_observations",
                    "value": {
                        "observation_id": f"obs:{OBS_SEG}:CAM_X:62:0",
                        "frame_ref": f"frame:{RUN}:CAM_X:62",
                        "timestamp_us": 12_400_000,
                        "score": 0.7,
                        "color_verdict": "STRONG",
                        "bbox_xyxy_px": [300.0, 100.0, 360.0, 260.0],
                    },
                }
            ],
            ["EVIDENCE_PRESENCE_RULES"],
            text="never STRONG",
        )
    )
    a(
        case(
            "ev_nocolor_weak",
            "a colour-less summary reports MATCH_WEAK",
            [S(EC.format("nocolor_strong"), "$.target_presence", "MATCH_WEAK")],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "ev_colour_query_null_verdict",
            "the query has a colour condition but a person box has no verdict",
            [S("q2_rule.evidence_2.json", "$.best_observations[0].color_verdict", None)],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "ev_colour_verdicts_for_colourless_seed",
            "the Q2 seed has no colour condition but the evidence summaries carry colour verdicts",
            [S("q2_rule.request.json", "$.seed.color", None)],
            ["EVIDENCE_PRESENCE_RULES"],
        )
    )
    a(
        case(
            "ev_hash_wrong",
            "evidence_sha256 is not the canonical hash of the summary (#135 C8)",
            [S(EC.format("no_person"), "$.evidence_sha256", "6" * 64)],
            ["CONTENT_HASH_RECOMPUTE"],
            stage="post",
        )
    )
    a(
        case(
            "graph_camera_without_exit",
            "a camera has no exit zone (D71: fail closed, no whole-frame stand-in)",
            [S("camera_graph.json", "$.cameras[1].exit_zones", [])],
            [
                "SCHEMA_VALID",
                "Q2_EXIT_ZONES_PRECHECK",
            ],  # D73 X1: no exit zone is UNKNOWN, never answered
        )
    )
    a(
        case(
            "graph_traversability_unknown",
            "an edge uses traversability UNKNOWN, which is not in the closed list (#135 C2)",
            [S("region_graph.json", "$.edges[3].traversability", "UNKNOWN")],
            ["SCHEMA_VALID", "GRAPH_CROSS_REFERENCES"],
        )
    )
    a(
        case(
            "cand_truncation_outside_window",
            "a window_truncated_us cut lies outside window_us",
            [S(SN, "$.candidates[0].window_truncated_us", [[14_000_000, 15_000_000]])],
            ["CANDIDATE_WINDOW_TRUNCATION"],
        )
    )
    a(
        case(
            "cand_truncation_overlapping",
            "window_truncated_us cuts overlap",
            [
                S(
                    SN,
                    "$.candidates[0].window_truncated_us",
                    [[9_000_000, 10_000_000], [9_600_000, 11_000_000]],
                )
            ],
            ["CANDIDATE_WINDOW_TRUNCATION"],
        )
    )
    a(
        case(
            "cand_truncation_missing",
            "a candidate without window_truncated_us (C4: [] when nothing is cut)",
            [{"op": "del", "file": SN, "path": "$.candidates[2].window_truncated_us"}],
            ["SCHEMA_VALID", "CANDIDATE_WINDOW_TRUNCATION"],
        )
    )
    a(
        case(
            "index_per_camera_stride_override",
            "one camera overrides stride_samples (D69: must equal sampling.stride_samples)",
            [
                S(M, "$.sampling.per_camera[3].stride_samples", 3),
                S(M, "$.sampling.per_camera[3].index_interval_us", 3 * SRC_US),
            ],
            ["INDEX_MANIFEST_RULES", "Q2_FAIL_CLOSED_ON_GRID_MISMATCH"],
        )
    )
    QP, QPR = "q1_partial.response.json", "q1_partial.request.json"
    a(
        case(
            "q1_last_page_total_mismatch",
            "a last page (next_cursor null) whose last rank is not results_total",
            [
                S(QPR, "$.cursor", "cursor:syn-2"),
                S(QP, "$.results", q1_results()[1:]),
                S(QP, "$.results_total", 3),
                S(QP, "$.returned_count", 1),
            ],
            ["Q1_RESULT_ORDER"],
        )
    )
    a(
        case(
            "q1_first_page_not_rank_1",
            "the first page (request cursor null) does not start at rank 1",
            [
                S(QP, "$.results", [{**r, "rank": r["rank"] + 1} for r in q1_results()]),
                S(QP, "$.results_total", 3),
                S(QP, "$.returned_count", 2),
            ],
            ["Q1_RESULT_ORDER"],
        )
    )
    # ---- D73 (2026-10-25): decisions on contract section 14, kit 0.3.0-rc2
    RP = "q1_partial.response.json"
    QA, QR, QE = "q2_agent", "q2_rule", "q2_exhaust"
    a(
        case(
            "reasons_missing",
            "no reasons[] next to reason (D73 section 14 item 12)",
            [{"op": "del", "file": R1, "path": "$.reasons"}],
            ["COMMON_REASONS_LIST"],
        )
    )
    a(
        case(
            "reasons_first_is_not_reason",
            "reasons[0] differs from reason",
            [S(RP, "$.reasons", ["PARAMETERS_NOT_APPROVED"])],
            ["COMMON_REASONS_LIST"],
        )
    )
    a(
        case(
            "reasons_not_empty_without_reason",
            "reason is null but reasons[] lists one",
            [S(R1, "$.reasons", ["TIME_SCOPE_PARTIAL"])],
            ["COMMON_REASONS_LIST"],
        )
    )
    a(
        case(
            "reasons_duplicate",
            "a reason listed twice",
            [S(RP, "$.reasons", [*RP_REASONS, *RP_REASONS])],
            ["COMMON_REASONS_LIST"],
        )
    )
    a(
        case(
            "reasons_wrong_priority",
            "GRAPH_NOT_APPROVED listed before the grid mismatch (missing data ranks first)",
            [
                S(RP, "$.reason", "GRAPH_NOT_APPROVED"),
                S(RP, "$.reasons", ["GRAPH_NOT_APPROVED", "PARAMETER_GRID_MISMATCH"]),
            ],
            ["COMMON_REASONS_LIST"],
        )
    )
    # ---- contract merged by #237 (kit 0.3.0-rc3): reason total order, link-record.v2, USER_STOPPED
    NS = "q2_noscope.response.json"
    a(
        case(
            "reasons_new_codes_wrong_order",
            "SEED_CAMERA_NOT_TRACKED listed before TRACKING_SCOPE_MISSING (section 14-12 total order)",
            [
                S(NS, "$.reason", "SEED_CAMERA_NOT_TRACKED"),
                S(NS, "$.reasons", ["SEED_CAMERA_NOT_TRACKED", "TRACKING_SCOPE_MISSING"]),
            ],
            ["COMMON_REASONS_LIST"],
        )
    )
    a(
        case(
            "reasons_tail_before_other_code",
            "an unranked code listed after the degradation tail (INCOMPLETE_EVIDENCE is last)",
            [
                S(NS, "$.reason", "INCOMPLETE_EVIDENCE"),
                S(NS, "$.reasons", ["INCOMPLETE_EVIDENCE", "TRACKING_SCOPE_MISSING"]),
            ],
            ["COMMON_REASONS_LIST"],
        )
    )
    a(
        case(
            "q2_scope_missing_not_unknown",
            "TRACKING_SCOPE_MISSING with status PARTIAL",
            [S(NS, "$.status", "PARTIAL")],
            # rc4: a non-UNKNOWN answer under a null scope pin is also a section 5.4 step 0 breach
            ["Q2_REASON_STATUS", "Q2_RESPONSE_VS_DECISIONS"],
        )
    )
    a(
        case(
            "q2_user_stopped_complete",
            "USER_STOPPED on a COMPLETE Q2 response (D82 says PARTIAL)",
            [
                S("q2_rule.response.json", "$.reason", "USER_STOPPED"),
                S("q2_rule.response.json", "$.reasons", ["USER_STOPPED"]),
            ],
            ["Q2_REASON_STATUS"],
        )
    )
    a(
        case(
            "link_matching_audit_missing",
            "a link-record.v2 without the matching_audit key",
            [{"op": "del", "file": LK, "path": "$[1].matching_audit"}],
            ["SCHEMA_VALID"],
        )
    )
    a(
        case(
            "link_matching_audit_null_after_gap",
            "matching_audit null although earlier cells were already unlinked (gap_samples 2)",
            [S(LK, "$[1].matching_audit", None)],
            ["LINK_RECORD_MATCHING_AUDIT"],
        )
    )
    a(
        case(
            "link_audit_pair_iou_differs",
            "actual_pair_iou differs from the main iou of the LINKED cell",
            [S(LK, "$[2].matching_audit.actual_pair_iou", 0.4)],
            ["LINK_RECORD_MATCHING_AUDIT"],
        )
    )
    a(
        case(
            "link_audit_event_on_unlinked",
            "event REACQUIRED on a cell that did not link",
            [S(LK, "$[1].matching_audit.event", "REACQUIRED")],
            ["LINK_RECORD_MATCHING_AUDIT"],
        )
    )
    a(
        case(
            "llm_digest_null_on_pass",
            "a PASS call without an observed digest",
            [S(f"{QA}.decisions.jsonl", "$[1].llm_calls[0].model_digest", None)],
            ["DECISION_LLM_CALL_RULES"],
        )
    )
    a(
        case(
            "llm_digest_null_with_raw_output",
            "a timed-out call that still has a raw output hash and no digest",
            [
                S(f"{QA}.decisions.jsonl", "$[1].llm_calls[0].model_digest", None),
                S(f"{QA}.decisions.jsonl", "$[1].llm_calls[0].validation", "PROVIDER_TIMEOUT"),
            ],
            ["DECISION_LLM_CALL_RULES"],
        )
    )
    a(
        case(
            "llm_digest_null_on_schema_invalid",
            "SCHEMA_INVALID means the model answered, so its digest was observed",
            [
                S(f"{QA}.decisions.jsonl", "$[1].llm_calls[0].model_digest", None),
                S(f"{QA}.decisions.jsonl", "$[1].llm_calls[0].raw_output_sha256", None),
                S(f"{QA}.decisions.jsonl", "$[1].llm_calls[0].validation", "SCHEMA_INVALID"),
            ],
            ["DECISION_LLM_CALL_RULES"],
        )
    )
    a(
        case(
            "wall_clock_budget_in_rule_journal",
            "a RULE_ONLY journal record with measured budget_used_ms",
            [S(f"{QR}.decisions.jsonl", "$[1].budget_used_ms", 5)],
            ["DECISION_NO_WALL_CLOCK"],
        )
    )
    a(
        case(
            "wall_clock_latency_in_rule_journal",
            "a RULE_ONLY journal record with latency_ms",
            [S(f"{QR}.decisions.jsonl", "$[1].stats", {"latency_ms": {"rule": 3}})],
            ["DECISION_NO_WALL_CLOCK"],
        )
    )
    a(
        case(
            "decisions_hash_is_record_hashes",
            "decisions_sha256 hashes the record hashes instead of the journal bytes",
            [S(f"{QR}.response.json", "$.decisions_sha256", H("record-hashes"))],
            ["Q2_DECISIONS_FILE_HASH", "OUTPUT_HASH_RECOMPUTE"],
            stage="post",
        )
    )
    a(
        case(
            "exhausted_return_with_fallback_reason",
            "the Controller return after the Agent's NEXT steps invents a fallback_reason",
            [S(f"{QE}.decisions.jsonl", "$[1].fallback_reason", "TIME_BUDGET")],
            [
                "DECISION_AGENT_EXHAUSTED_RETURN",
                "DECISION_BUDGET_LIMITS",
                "Q2_RESPONSE_VS_DECISIONS",
            ],
        )
    )
    a(
        case(
            "exhausted_return_with_candidate_left",
            "the Controller returns although the Agent has not taken NEXT on the last candidate",
            [
                {
                    "op": "del",
                    "file": f"{QE}.decisions.jsonl",
                    "path": "$[1].candidates_considered[2]",
                }
            ],
            ["DECISION_AGENT_EXHAUSTED_RETURN"],
        )
    )
    a(
        case(
            "exhausted_return_after_rule_next",
            "a rule NEXT_CANDIDATE inside a Controller return of an Agent session",
            [S(f"{QE}.decisions.jsonl", "$[1].candidates_considered[1].decided_by", "RULE_ONLY")],
            ["DECISION_AGENT_EXHAUSTED_RETURN"],
            text="NEXT_CANDIDATE steps only",
        )
    )
    a(
        case(
            "exhausted_return_response_not_used",
            "the response says agent_used false although the Agent's NEXT steps were accepted",
            [S(f"{QE}.response.json", "$.agent_used", False)],
            ["Q2_RESPONSE_VS_DECISIONS"],
        )
    )
    a(
        case(
            "agent_restarted_after_fallback",
            "an Agent step after RULE_FALLBACK without a USER decision (no automatic restart)",
            [
                {
                    "op": "append_record",
                    "file": f"{QA}.decisions.jsonl",
                    "value": agent_after_fallback(),
                }
            ],
            ["DECISION_NO_AUTO_AGENT_RESTART"],
        )
    )
    a(
        case(
            "session_round_cap_without_round_limit",
            "session_agent_rounds_used passes session_max_agent_rounds without ROUND_LIMIT",
            [
                S(f"{QA}.decisions.jsonl", "$[2].session_agent_rounds_used", 13),
                S(f"{QA}.decisions.jsonl", "$[3].session_agent_rounds_used", 13),
            ],
            ["DECISION_BUDGET_LIMITS"],
        )
    )
    a(
        case(
            "exit_zones_missing_without_cause",
            "UNKNOWN / EXIT_ZONES_MISSING although every camera has exit zones",
            [
                S("q2_noseed.response.json", "$.status", "UNKNOWN"),
                S("q2_noseed.response.json", "$.reason", "EXIT_ZONES_MISSING"),
            ],
            ["Q2_EXIT_ZONES_PRECHECK"],
        )
    )
    a(
        case(
            "q3_missing_clock_parsed_to_wall_query",
            "no clock mapping in the request context but the answer is PARSED into a wall-clock query",
            [S("q3_llm.request.json", "$.context.clock_mapping_sha256", None)],
            ["Q3_MISSING_CLOCK_CLARIFIES"],
        )
    )
    a(
        case(
            "q3_missing_clock_error_reason",
            "no clock mapping and the answer is PARSE_FAILED / CLOCK_MAPPING_MISSING instead of a clarification",
            [
                S("q3_noclock.response.json", "$.status", "PARSE_FAILED"),
                S("q3_noclock.response.json", "$.clarification", None),
            ],
            ["Q3_MISSING_CLOCK_CLARIFIES"],
        )
    )
    a(
        case(
            "q1_two_runs_ready",
            "a Q1 request over two runs is answered READY in the first version",
            [S("q1_ready.request.json", "$.run_ids", [RUN, "RUN_Y"])],
            ["Q1_Q3_SINGLE_RUN_ONLY"],
        )
    )
    a(
        case(
            "q1_response_spans_two_runs",
            "a Q1 response whose scope spans two runs is READY",
            [S(R1, "$.resolved_scope.run_ids", [RUN, "RUN_Y"])],
            ["Q1_Q3_SINGLE_RUN_ONLY"],
        )
    )
    a(
        case(
            "q3_parsed_over_two_runs",
            "a Q3 request that spans two runs is PARSED instead of asking which run",
            [S("q3_llm.request.json", "$.context.run_ids", [RUN, "RUN_Y"])],
            ["Q1_Q3_SINGLE_RUN_ONLY"],
        )
    )
    return C


POSITIVE_CASES = [
    {
        "id": "records_change_keeps_index_id",
        "description": "changing the per-frame records changes records_file_sha256 and content_sha256 but not the index key / index_id",
        "ops": [S("detection_index.records.jsonl", "$[6].detections[0].score", 0.81)],
        "stage": "pre",
        "expect_fail": [],
    },
    {
        "id": "rule_no_alignable_observation",
        "description": "a guard-reaching candidate without an entry observation is recorded as NO_ALIGNABLE_OBSERVATION",
        "ops": [
            S(
                "q2_rule.decisions.jsonl",
                "$[1].candidates_considered[0].target_presence",
                "MATCH_STRONG",
            ),
            S(
                "q2_rule.decisions.jsonl",
                "$[1].candidates_considered[0].exclusion_reason",
                "NO_ALIGNABLE_OBSERVATION",
            ),
            S("q2_rule.evidence_1.json", "$.target_presence", "MATCH_STRONG"),
            S("q2_rule.evidence_1.json", "$.best_observations[0].color_verdict", "STRONG"),
        ],
        "stage": "pre",
        "expect_fail": [],
    },
    {
        "id": "n6_tool_use_only_is_not_agent_used",
        "description": "the Agent called tools but no Agent step was accepted: agent_attempted true, agent_used false, fallback recorded",
        "ops": [
            S("q2_agent.decisions.jsonl", "$[2].accepted", False),
            S("q2_agent.decisions.jsonl", "$[2].rejection_code", "ILLEGAL_ORDER"),
            S("q2_agent.decisions.jsonl", "$[2].executed_action", None),
            S("q2_agent.decisions.jsonl", "$[2].executed_candidate_ref", None),
            S("q2_agent.response.json", "$.agent_used", False),
        ],
        "stage": "pre",
        "expect_fail": [],
    },
    {
        "id": "grid_mismatch_fails_closed",
        "description": "the parameter set does not fit the index grid and every Q2 request is answered UNKNOWN / PARAMETER_GRID_MISMATCH with an empty timeline (D69)",
        "ops": [
            S("parameter_set.json", "$.applies_to.index_interval_us", SRC_US),
            *grid_reply("q2_rule.response.json"),
            *grid_reply("q2_agent.response.json"),
            *grid_reply("q2_noseed.response.json"),
            *grid_reply("q2_noscope.response.json"),
            *grid_reply("q2_exhaust.response.json"),
        ],
        "stage": "pre",
        "expect_fail": [],
    },
    {
        "id": "link_at_threshold_stays_linked",
        "description": "elapsed_us == link_max_gap_us on a LINKED cell is valid (gap_samples 2, equal to link_max_gap_samples)",
        "ops": [
            S("q2_rule.links.jsonl", "$[2].iou", 0.56),
            S("q2_rule.links.jsonl", "$[2].matching_audit.actual_pair_iou", 0.56),
            S("q2_rule.links.jsonl", "$[2].matching_audit.reference_iou", 0.56),
        ],
        "stage": "pre",
        "expect_fail": [],
    },
    {
        "id": "q1_last_page_of_two",
        "description": "the second page of a two-result query: one result of rank 2, results_total 2, next_cursor null (#156)",
        "ops": [
            S("q1_partial.request.json", "$.cursor", "cursor:syn-2"),
            S("q1_partial.response.json", "$.results", q1_results()[1:]),
            S("q1_partial.response.json", "$.returned_count", 1),
        ],
        "stage": "pre",
        "expect_fail": [],
    },
    {
        "id": "q3_q2_query_without_colour",
        "description": "a Q3 rule parse assembles a Q2 request whose APPEARANCE seed has no colour condition (#211)",
        "ops": [S("q3_fallback.response.json", "$.structured_query.seed.color", None)],
        "stage": "pre",
        "expect_fail": [],
    },
    {
        "id": "failed_call_has_no_digest",
        "description": "a call that timed out before the model reported a digest keeps its failure code and a null digest (D73 section 14 item 20)",
        "ops": [
            S("q2_agent.decisions.jsonl", "$[1].llm_calls[0].model_digest", None),
            S("q2_agent.decisions.jsonl", "$[1].llm_calls[0].raw_output_sha256", None),
            S("q2_agent.decisions.jsonl", "$[1].llm_calls[0].validation", "PROVIDER_UNAVAILABLE"),
        ],
        "stage": "pre",
        "expect_fail": [],
    },
    {
        "id": "round_limit_from_session_cap",
        "description": "ROUND_LIMIT is recorded when session_max_agent_rounds is reached even though agent_max_rounds is not (D73 X3)",
        "ops": [
            S("q2_agent.decisions.jsonl", "$[3].rounds_used", 2),
            S("q2_agent.decisions.jsonl", "$[3].session_agent_rounds_used", 12),
        ],
        "stage": "pre",
        "expect_fail": [],
    },
    {
        "id": "agent_restarted_by_user",
        "description": "the Agent runs again after a fallback because the user restarted it (a USER decision in between, D73 X2)",
        "ops": [
            {"op": "append_record", "file": "q2_agent.decisions.jsonl", "value": r}
            for r in agent_after_user_restart()
        ],
        "stage": "pre",
        "expect_fail": [],
    },
    {
        "id": "latency_change_keeps_hash",
        "description": "stats.latency_ms may change without touching output_sha256",
        "ops": [S("q1_ready.response.json", "$.stats.latency_ms.total", 999)],
        "stage": "post",
        "expect_fail": [],
    },
]


def all_cases() -> list[dict[str, Any]]:
    out = violations() + [
        {**c, "ops": [{k: v for k, v in o.items() if k != "_stage"} for o in c["ops"]]}
        for c in POSITIVE_CASES
    ]
    return out


def main() -> None:
    valid = OUT / "valid"
    if valid.exists():
        shutil.rmtree(valid)
    materialize(None, valid)
    (OUT / "violations.json").write_text(
        json.dumps(all_cases(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(list(valid.iterdir()))} files and {len(all_cases())} cases")


if __name__ == "__main__":
    sys.exit(main())
