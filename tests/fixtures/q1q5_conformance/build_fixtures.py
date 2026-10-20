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
OBS_SEG = "0123456789abcdef"
WALL0 = "2026-11-01T13:00:00+08:00"


def H(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


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
                "exit_zones": (
                    [
                        {
                            "exit_zone_id": "CAM_A:EXIT_1",
                            "roi_polygon_px": roi,
                            "leads_to_edge_ids": ["E_1_2"],
                            "mapping_basis": "MANUAL_ON_STATIC_FRAME",
                            "static_frame_ref": "static:CAM_A",
                            "static_frame_sha256": H("static-A"),
                        }
                    ]
                    if cam == "CAM_A"
                    else []
                ),
                "entry_zones": (
                    [{"entry_zone_id": f"{cam}:ENTRY_1", "roi_polygon_px": roi}]
                    if cam in ("CAM_B", "CAM_C", "CAM_E")
                    else []
                ),
            }
        )

    def tr(tid, to, entry, regs, edges, relation, trav):
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
            tr("T_A_D", "CAM_D", [], ["REG_1"], [], "OVERLAP", "APPROVED_WALKABLE"),
            tr(
                "T_A_B",
                "CAM_B",
                ["CAM_B:ENTRY_1"],
                ["REG_1", "REG_2", "REG_3"],
                ["E_1_2", "E_2_3"],
                "BLIND_GAP",
                "APPROVED_WALKABLE",
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
            "weights_file_sha256": H("weights"),
            "weights_source": "synthetic://none",
            "config_sha256": H("config"),
            "class_map": {"version": "synthetic-classes-v1", "content_sha256": H("class-map")},
            "input_preprocess": {"resize_policy": "synthetic", "input_size_px": [640, 640]},
            "index_score_floor": 0.11,
            "nms": {"applied": True, "iou": 0.7},
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
        "sampling": {"policy": "EVERY_NTH_SAMPLE", "stride_samples": 1, "per_camera": per},
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

    records = [
        rec(
            "CAM_A",
            0,
            "INFERRED",
            [
                {
                    "observation_id": obs("CAM_A", 0, 0),
                    "class_id": 0,
                    "class_label": "person",
                    "bbox_xyxy_px": [412.0, 180.5, 470.2, 355.0],
                    "score": 0.91,
                    "color": color("STRONG", "NONE"),
                },
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
        rec("CAM_A", 1, "INFERRED", []),
        rec("CAM_A", 2, "NOT_SAMPLED", None),
        rec("CAM_A", 3, "MISSING", None, rgb=False),
        rec(
            "CAM_B",
            0,
            "INFERRED",
            [
                {
                    "observation_id": obs("CAM_B", 0, 0),
                    "class_id": 0,
                    "class_label": "person",
                    "bbox_xyxy_px": [300.0, 100.0, 360.0, 260.0],
                    "score": 0.8,
                    "color": color("NONE", "STRONG"),
                }
            ],
        ),
        rec(
            "CAM_B",
            1,
            "INFERRED",
            [
                {
                    "observation_id": obs("CAM_B", 1, 0),
                    "class_id": 0,
                    "class_label": "person",
                    "bbox_xyxy_px": [300.0, 100.0, 360.0, 260.0],
                    "score": 0.3,
                    "color": color("UNKNOWN", "UNKNOWN", "LOW_LIGHT_OR_SATURATION"),
                }
            ],
        ),
        rec("CAM_C", 0, "NOT_INFERRED", None, reason="MODEL_NOT_RUN"),
    ]
    return {"detection_index.json": manifest, "detection_index.records.jsonl": records}


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
        "parameter_set.json": {
            "parameter_set_id": "SYNTHETIC-PARAMS-NOT-PROPOSALS",
            "content_sha256": "@",
            "index_score_floor": 0.11,
            "top_k": 4,
            "switch_min_presence": "MATCH_STRONG",
            "agent_max_rounds": 6,
            "agent_total_budget_ms": 9000,
            "q3_max_llm_attempts": 2,
        },
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

    return [result("CAM_A", 1, 0, 400_000), result("CAM_B", 2, 200_000, 600_000)]


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
            "window_us": [8_200_000, 14_200_000],
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
):
    return {
        "schema_version": "q-demo.decision-record.v1",
        "decision_id": f"{session}-dec-{step}",
        "session_id": session,
        "step_index": step,
        "state_before": before,
        "state_after": after,
        "source_time_us": t,
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
        "decided_by": by,
        "fallback_reason": fb,
        "rounds_used": rounds,
        "budget_used_ms": budget,
        "content_sha256": "@",
        "stats": {"latency_ms": {"agent": 5, "evidence": 1}},
    }


def considered(n, rank, presence, action, by, reason=None, evidence=True):
    return {
        "candidate_ref": f"cand:{'0' * 16}:{rank}",
        "rank": rank,
        "evidence_sha256": H(f"ev-{n}-{rank}") if evidence else None,
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


def q2_response(session: str, by: str, **over: Any) -> dict[str, Any]:
    req, ranges, cv = complete(0, 21)
    tl = [
        {
            "segment_id": "seg-0",
            "kind": "ON_CAMERA",
            "camera_id": "CAM_A",
            "range_us": [0, 8_200_000],
            "entered_by": "SEED",
            "decided_by": "USER",
            "observation_ids": [f"obs:{OBS_SEG}:CAM_A:0:0"],
            "presence_at_entry": "MATCH_STRONG",
        },
        {
            "segment_id": "seg-1",
            "kind": "GAP",
            "range_us": [8_200_000, 13_400_000],
            "gap_states": ["TEMP_LOST", "SEARCHING"],
            "camera_shown": "CAM_A",
            "position": None,
        },
        {
            "segment_id": "seg-2",
            "kind": "ON_CAMERA",
            "camera_id": "CAM_B",
            "range_us": [13_400_000, 21_000_000],
            "entered_by": "SWITCH",
            "decided_by": by,
            "decision_id": f"{session}-dec-{6 if session == 'sess_agent' else 4}",
            "observation_ids": [f"obs:{OBS_SEG}:CAM_B:0:0"],
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
    )
    body.update(over)
    sc = scope(req, ranges, cv, ["CAM_A", "CAM_B", "CAM_D", "CAM_E"])
    return envelope("q2-response", body.pop("status"), body.pop("reason"), sc, **body)


def q2_files() -> dict[str, Any]:
    f: dict[str, Any] = {}
    # --- rule-only session
    s = "sess_rule"
    f["q2_rule.request.json"] = q2_request("RULE_ONLY")
    f["q2_rule.snapshot.json"] = snapshot(s)
    f["q2_rule.decisions.jsonl"] = [
        decision(s, 0, None, "PLAYING", 0, "RULE_ONLY", "USER", snap=False),
        decision(
            s,
            4,
            "SEARCHING",
            "PLAYING",
            13_400_000,
            "RULE_ONLY",
            "RULE_ONLY",
            considered=[
                considered(
                    1,
                    1,
                    "PERSON_NO_COLOR_MATCH",
                    "NEXT_CANDIDATE",
                    "RULE_ONLY",
                    "CONDITION_MISMATCH",
                ),
                considered(1, 2, "MATCH_STRONG", "SWITCH", "RULE_ONLY"),
            ],
            submitted={"action": "SWITCH", "candidate_ref": f"cand:{'0' * 16}:2"},
            action="SWITCH",
            ref=f"cand:{'0' * 16}:2",
        ),
    ]
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
    f["q2_agent.decisions.jsonl"] = [
        decision(s, 0, None, "PLAYING", 0, "AGENT_SEQUENTIAL", "USER", snap=False),
        decision(
            s,
            4,
            "SEARCHING",
            "SEARCHING",
            8_200_000,
            "AGENT_SEQUENTIAL",
            "AGENT",
            llm=[llm_call(1)],
            submitted={"action": "SWITCH", "candidate_ref": f"cand:{'0' * 16}:9"},
            accepted=False,
            code="UNKNOWN_REF",
            rounds=1,
            budget=900,
        ),
        decision(
            s,
            5,
            "SEARCHING",
            "SEARCHING",
            8_200_000,
            "AGENT_SEQUENTIAL",
            "AGENT",
            llm=[llm_call(2)],
            considered=[
                considered(
                    2, 1, "PERSON_NO_COLOR_MATCH", "NEXT_CANDIDATE", "AGENT", "CONDITION_MISMATCH"
                )
            ],
            submitted={"action": "NEXT_CANDIDATE", "candidate_ref": f"cand:{'0' * 16}:1"},
            action="NEXT_CANDIDATE",
            ref=f"cand:{'0' * 16}:1",
            rounds=2,
            budget=1800,
        ),
        decision(
            s,
            6,
            "SEARCHING",
            "PLAYING",
            13_400_000,
            "AGENT_SEQUENTIAL",
            "RULE_FALLBACK",
            fb="ROUND_LIMIT",
            rounds=6,
            budget=2400,
            considered=[considered(3, 2, "MATCH_STRONG", "SWITCH", "RULE_FALLBACK")],
            submitted={"action": "SWITCH", "candidate_ref": f"cand:{'0' * 16}:2"},
            action="SWITCH",
            ref=f"cand:{'0' * 16}:2",
        ),
    ]
    f["q2_agent.response.json"] = q2_response(
        s,
        "RULE_FALLBACK",
        decision_source="RULE_FALLBACK",
        agent_attempted=True,
        agent_used=True,
        fallback_used=True,
        fallback_reason="ROUND_LIMIT",
    )
    return f


def valid_files() -> dict[str, Any]:
    files = static_docs()
    files.update(q1_files())
    files.update(q3_files())
    files.update(q2_files())
    return files


# ----------------------------------------------------------------------------- finalisation

REF_PREFIX = re.compile(r"cand:[0-9a-f]{16}:")


def _replace(node: Any, table: dict[str, str]) -> Any:
    if isinstance(node, dict):
        return {k: _replace(v, table) for k, v in node.items()}
    if isinstance(node, list):
        return [_replace(v, table) for v in node]
    if isinstance(node, str) and node.startswith("@") and node in table:
        return table[node]
    return node


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
    if "clock_mapping.json" in f:
        f["clock_mapping.json"]["content_sha256"] = t["@clock_sha"] = canonical_sha256(
            f["clock_mapping.json"], ("content_sha256",)
        )
    if "parameter_set.json" in f:
        p = f["parameter_set.json"]
        p["content_sha256"] = t["@param_sha"] = canonical_sha256(p, ("content_sha256",))
        t["@param_id"] = p["parameter_set_id"]
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
        if "detection_index.records.jsonl" in f:
            m["records_file_sha256"] = hashlib.sha256(
                serialise("detection_index.records.jsonl", f["detection_index.records.jsonl"])
            ).hexdigest()
        m["content_sha256"] = t["@index_sha"] = canonical_sha256(m, ("content_sha256", "index_id"))
        m["index_id"] = t["@index_id"] = f"detidx:{REV}:{RUN}:{m['content_sha256'][:16]}"
        t["@classmap_sha"] = m["detector"]["class_map"]["content_sha256"]
        t["@color_ver"] = m["color_method"]["version"]
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
    for name in [n for n in f if n.endswith(".decisions.jsonl")]:
        for r in f[name]:
            r["content_sha256"] = canonical_sha256(r, ("content_sha256", "stats"))
        t["@dec_sha:" + name.split(".")[0]] = canonical_sha256(
            [r["content_sha256"] for r in f[name]]
        )
    for name in [
        n
        for n in f
        if n.endswith(".response.json") and isinstance(f[n], dict) and "decisions_sha256" in f[n]
    ]:
        f[name]["decisions_sha256"] = t["@dec_sha:" + name.split(".")[0]]
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
    elif kind == "add_raw":
        files[op["file"]] = op["text"]
    elif kind == "remove_file":
        del files[op["file"]]
    elif kind == "rehash_decisions":
        for r in files[op["file"]]:
            r["content_sha256"] = canonical_sha256(r, ("content_sha256", "stats"))
    elif kind == "copy_file":
        files[op["to"]] = copy.deepcopy(files[op["from"]])
    else:
        parent, key = _walk_path(files[op["file"]], op["path"])
        if kind == "set":
            parent[key] = copy.deepcopy(op["value"])
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


def with_results(file: str) -> list[dict[str, Any]]:
    return [
        S(file, "$.results", q1_results()),
        S(file, "$.results_total", 2),
        S(file, "$.returned_count", 2),
    ]


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
            ["PARAMSET_INTEGRITY", "SCOPE_HASH_LINKS"],
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
            ["CANDIDATE_ORDER_D28"],
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
            [S("parameter_set.json", "$.top_k", 2)],
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
            "switch to MATCH_WEAK accepted",
            [S(D, "$[1].candidates_considered[1].target_presence", "MATCH_WEAK")],
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
            [{"op": "append", "file": D, "path": "$[1].llm_calls", "value": llm_call(9)}],
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
            ["DECISION_REJECTION_CORRECTNESS", "DECISION_FIELD_CONSISTENCY"],
            stage="post",
            text="STALE_SNAPSHOT",
        )
    )
    a(
        case(
            "dec_content_hash_bad",
            "decision content_sha256 wrong",
            [S(D, "$[1].content_sha256", "0" * 64)],
            ["CONTENT_HASH_RECOMPUTE"],
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
            [S(QR, "$.timeline[2].range_us", [12_000_000, 21_000_000])],
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
            [S(QR, "$.timeline[2].range_us", [13_400_000, 18_000_000])],
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
            [S(RC, "$[6].state_reason", None)],
            ["RECORDS_FRAME_STATE"],
        )
    )
    a(
        case(
            "records_unsorted",
            "records not sorted by (camera, frame)",
            [S(RC, "$[4].camera_id", "CAM_A"), S(RC, "$[4].frame_ref", "frame:RUN_X:CAM_A:0")],
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
            [S(RC, "$[5].detections[0].color.unknown_reason", None)],
            ["RECORDS_COLOR_RULES"],
        )
    )
    a(
        case(
            "records_below_floor",
            "stored score below index_score_floor",
            [S(RC, "$[5].detections[0].score", 0.05)],
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
                S(RC, "$[6].frame_state", "INFERRED"),
                S(RC, "$[6].state_reason", None),
                S(RC, "$[6].detections", []),
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
    return C


POSITIVE_CASES = [
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
