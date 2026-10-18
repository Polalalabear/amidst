"""Fixture-only consumer skeletons; never substitute fixtures for registered real runs."""

from __future__ import annotations

import copy
import math
import secrets
from fractions import Fraction
from typing import Any

from amidst.engineering.registry import content_hash
from amidst.workbench.controlled_scene_data import RequiredInputUnavailable, no_private
from amidst.workbench.scene_errors import DataIntegrityError

ACTIONS = frozenset({"candidate_cameras", "synced_frames", "person_layer", "curve_layer",
                     "evidence_lookup"})
SCENE = "controlled-l-corridor"
RUN = "fixture-controlled-5fps-v1-r001"
CAMERAS = ("FIX_CAM_01", "FIX_CAM_02", "FIX_CAM_03", "FIX_CAM_04")
INFERRED_STATES = frozenset({"PROJECTED_OBSERVATION", "INFERRED_INTERPOLATION",
                             "INFERRED_HYPOTHESIS"})


def uncertainty() -> dict[str, Any]:
    return {"status": "UNKNOWN", "method": "SYNTHETIC_FIXTURE_ONLY", "units": "m",
            "bounds": None, "reason": "NO_MEASURED_ERROR_BOUND",
            "limitations": ["Not measured accuracy, probability or physical acceptance"]}


def validate_uncertainty(value: Any) -> None:
    if isinstance(value, dict):
        if (value.get("evidence_state") in INFERRED_STATES
                or value.get("kind") in {"OBSERVED", "INFERRED_CONNECTOR", "BLIND_HYPOTHESIS",
                                         "PREDICTION"}
                or "estimate_ref" in value):
            u = value.get("uncertainty")
            if (not isinstance(u, dict) or not {"status", "method", "units", "bounds",
                                               "reason", "limitations"}.issubset(u)
                    or not u["method"] or not u["limitations"]
                    or u["status"] not in {"UNKNOWN", "BOUNDED_HEURISTIC"}
                    or (u["status"] == "UNKNOWN" and (u["bounds"] is not None or not u["reason"]))
                    or (u["status"] == "BOUNDED_HEURISTIC" and u["bounds"] is None)):
                raise DataIntegrityError("INFERENCE_UNCERTAINTY_MISSING_OR_INVALID")
        for child in value.values():
            validate_uncertainty(child)
    elif isinstance(value, list):
        for child in value:
            validate_uncertainty(child)


def fixture_layers() -> dict[str, Any]:
    """Hand-authored synthetic geometry, not derived from a renderer or actor script."""
    estimate = {
        "estimate_ref": "fixture-estimate-1", "observation_ref": "fixture-obs-1",
        "camera_id": CAMERAS[0], "frame_ref": "fixture-frame-62", "timestamp_s": 12.4,
        "rgb_file_sha256": "1" * 64, "calibration_sha256": "2" * 64,
        "floor_id": "FLOOR_FIXTURE", "local_track_ref": None,
        "evidence_state": "PROJECTED_OBSERVATION", "uncertainty": uncertainty(),
        "ground_estimate": {"status": "UNKNOWN", "estimate_kind": "UNKNOWN",
                            "basis": "SYNTHETIC_FIXTURE", "segment": None,
                            "reason": "C4A_ADAPTER_NOT_IMPLEMENTED"},
        "bbox_height_px": 180, "heading": {"state": "UNKNOWN", "direction_xy": None,
                                           "reason": "LOCAL_TRACK_UNAVAILABLE"},
        "display": {"humanoid_range_allowed": False,
                    "display_config_sha256": "3" * 64},
        "identity_verdict": "UNCONFIRMED", "physical_verdict": "UNKNOWN",
    }
    segment = {"kind": "BLIND_HYPOTHESIS", "evidence_state": "INFERRED_HYPOTHESIS",
               "t_s": [12, 13], "hypothesis_refs": ["fixture-hypothesis-1"],
               "hypothesis_response_sha256": "4" * 64, "support_refs": [],
               "unassociated_baseline": True, "region_band": True,
               "uncertainty": uncertainty()}
    return {"estimates": [estimate], "curves": [{
        "curve_ref": "fixture-curve-1", "candidate_ref": None, "local_track_refs": [],
        "segments": [segment], "result_sha256": content_hash(segment), "map_sha256": "5" * 64,
        "policy_pins": {"body_policy_sha256": "6" * 64, "speed_config_sha256": "7" * 64},
        "association": {"state": "UNKNOWN", "identity_verdict": "UNCONFIRMED"},
    }]}


class ControlledSceneAPI:
    def __init__(self, *, fixture_mode: bool = False,
                 layers: dict[str, Any] | None = None) -> None:
        self.fixture_mode = fixture_mode
        self._layers = copy.deepcopy(layers if layers is not None else fixture_layers())
        no_private(self._layers)
        validate_uncertainty(self._layers)
        for estimate in self._layers["estimates"]:
            if "uncertainty" not in estimate:
                raise DataIntegrityError("INFERENCE_UNCERTAINTY_MISSING_OR_INVALID")
        self._fixture_pin = content_hash(self._layers)
        self._cursors: dict[str, tuple[str, int]] = {}

    @property
    def scene_ids(self) -> frozenset[str]:
        return frozenset({SCENE}) if self.fixture_mode else frozenset()

    def bootstrap(self) -> dict[str, Any]:
        return {"schema_version": "controlled-scene.bootstrap.v1",
                "data_origin": "SYNTHETIC_FIXTURE" if self.fixture_mode else "UNCONFIGURED",
                "fixture_marker": "FIXTURE" if self.fixture_mode else None,
                "scenes": [{"scene_id": SCENE, "run_ids": [RUN], "camera_ids": list(CAMERAS),
                            "sampling": {"fps": 5, "duration_s": 20,
                                         "sampling_version": "5fps-v1"}}]
                if self.fixture_mode else [],
                "real_run_support": "NOT_IMPLEMENTED", "gt_read": False,
                "requires_session": True}

    def call(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if action not in ACTIONS:
            raise ValueError("UNKNOWN_CONTROLLED_ACTION")
        no_private(payload)
        self._validate_request(action, payload)
        if not self.fixture_mode:
            raise RequiredInputUnavailable("CONTROLLED_RUN_NOT_CONFIGURED")
        if payload["scene_id"] != SCENE or payload["run_id"] != RUN:
            raise DataIntegrityError("SOURCE_RUN_PIN_MISMATCH")
        if content_hash(self._layers) != self._fixture_pin:
            raise DataIntegrityError("FIXTURE_HASH_MISMATCH")
        validate_uncertainty(self._layers)
        scope = {"scene_id": SCENE, "scene_version": 1, "run_id": RUN, "clock_id": "clock:" + RUN,
                 "source_sha256": self._fixture_pin, "sampling_version": "5fps-v1",
                 "time_range_s": payload.get("time_range_s", [0, 20]),
                 "length_unit": "m", "data_origin": "SYNTHETIC_FIXTURE"}
        result = {"schema_version": "controlled-scene." + action.replace("_", "-") + ".v1",
                  "resolved_scope": scope, "data_origin": "SYNTHETIC_FIXTURE",
                  "fixture_marker": "FIXTURE", "SYNTHETIC": True,
                  "identity_verdict": "UNCONFIRMED", "agent_used": False,
                  "provenance": {"producer": "controlled-scene-fixture-skeleton-v1",
                                 "gt_read": False, "input_sha256": self._fixture_pin},
                  "status": "READY"}
        if action == "candidate_cameras":
            result.update(self._candidates(payload))
        elif action == "synced_frames":
            result.update(self._frames(payload))
        elif action == "person_layer":
            result.update(time_range_s=payload["time_range_s"],
                          estimates=[copy.deepcopy(v) for v in self._layers["estimates"]
                                     if payload["time_range_s"][0] <= v["timestamp_s"]
                                     < payload["time_range_s"][1]])
        elif action == "curve_layer":
            curves = copy.deepcopy(self._layers["curves"])
            # Immutable result refs describe full fixture scope; filter without changing refs.
            for curve in curves:
                curve["segments"] = [s for s in curve["segments"]
                                     if s["t_s"][0] < payload["time_range_s"][1]
                                     and s["t_s"][1] > payload["time_range_s"][0]]
            result.update(curves=curves, time_range_s=payload["time_range_s"],
                          time_highlight={"t_s": payload.get("t_s"), "window_s": 1},
                          kinds_reserved=["PREDICTION"])
        else:
            result.update(self._evidence(payload))
        validate_uncertainty(result)
        result["output_sha256"] = content_hash(result)
        return result

    @staticmethod
    def _validate_request(action: str, p: dict[str, Any]) -> None:
        base = {"schema_version", "session_ref", "scene_id", "run_id"}
        fields = {
            "candidate_cameras": {"target_region_ref", "target_polygon", "time_range_s",
                                  "query_intent", "surrounding_policy_ref", "camera_ids",
                                  "page_size", "cursor", "layout_capacity"},
            "synced_frames": {"t_s", "camera_ids"},
            "person_layer": {"time_range_s"},
            "curve_layer": {"time_range_s", "t_s"},
            "evidence_lookup": {"pick"},
        }[action]
        if (not base.issubset(p) or set(p) - base - fields
                or p["schema_version"] != (
                    "controlled-scene." + action.replace("_", "-") + "-request.v1")
                or any(not isinstance(p[k], str) or not p[k]
                       for k in ("session_ref", "scene_id", "run_id"))):
            raise ValueError("INVALID_CONTROLLED_REQUEST")
        if action in {"candidate_cameras", "person_layer", "curve_layer"}:
            span = p.get("time_range_s")
            if (not isinstance(span, list) or len(span) != 2
                    or any(type(v) not in {int, float} or not math.isfinite(v) for v in span)
                    or not 0 <= span[0] < span[1] <= 20):
                raise ValueError("INVALID_TIME_RANGE")
        if action == "synced_frames" or "t_s" in p:
            if type(p.get("t_s")) not in {int, float} or not math.isfinite(p["t_s"]):
                raise ValueError("INVALID_TIME")
        if action == "synced_frames" or p.get("camera_ids") is not None:
            cameras = p.get("camera_ids")
            if (not isinstance(cameras, list) or not 1 <= len(cameras) <= 8
                    or any(not isinstance(c, str) for c in cameras)
                    or len(set(cameras)) != len(cameras) or not set(cameras).issubset(CAMERAS)):
                raise ValueError("INVALID_CAMERA_SCOPE")
        if action == "candidate_cameras":
            if (bool(p.get("target_region_ref")) == bool(p.get("target_polygon"))
                    or p.get("query_intent") not in {"PASS_THROUGH", "ENTER_EXIT"}
                    or p.get("surrounding_policy_ref") != "fixture-surround-policy-v1"
                    or type(p.get("page_size")) is not int or not 1 <= p["page_size"] <= 8
                    or type(p.get("layout_capacity")) is not int
                    or p["layout_capacity"] not in {1, 2, 4, 8}):
                raise ValueError("INVALID_CANDIDATE_QUERY")
            if p.get("target_region_ref") not in {None, "AREA_FIXTURE"}:
                raise ValueError("UNREGISTERED_REGION")
            if p.get("target_polygon") is not None:
                polygon = p["target_polygon"]
                if (not isinstance(polygon, dict) or set(polygon) != {
                    "floor_id", "frame_id", "length_unit", "polygon_m"
                } or polygon["floor_id"] != "FLOOR_FIXTURE"
                        or polygon["frame_id"] != "fixture-world"
                        or polygon["length_unit"] != "m"
                        or not isinstance(polygon["polygon_m"], list)
                        or not 3 <= len(polygon["polygon_m"]) <= 64
                        or any(not isinstance(v, list) or len(v) != 2
                               or any(type(n) not in {int, float} or not math.isfinite(n)
                                      for n in v)
                               for v in polygon["polygon_m"])):
                    raise ValueError("INVALID_POLYGON")

    def _candidates(self, p: dict[str, Any]) -> dict[str, Any]:
        query = {k: v for k, v in p.items() if k not in {"session_ref", "cursor"}}
        query_hash = content_hash({"query": query, "fixture_pin": self._fixture_pin})
        selected = [c for c in CAMERAS if p.get("camera_ids") is None or c in p["camera_ids"]]
        start = 0
        if p.get("cursor") is not None:
            if not isinstance(p["cursor"], str) or p["cursor"] not in self._cursors:
                raise DataIntegrityError("CURSOR_PIN_MISMATCH")
            bound, start = self._cursors[p["cursor"]]
            if bound != content_hash([query_hash, p["session_ref"]]):
                raise DataIntegrityError("CURSOR_PIN_MISMATCH")
        end = start + p["page_size"]
        cursor = None
        if end < len(selected):
            cursor = secrets.token_urlsafe(24)
            if len(self._cursors) >= 256:
                self._cursors.clear()
            self._cursors[cursor] = (content_hash([query_hash, p["session_ref"]]), end)
        candidates = [{"camera_id": c, "rank": i + 1, "relation": "UNKNOWN",
                       "reason_codes": ["SYNTHETIC_FIXTURE_NO_VISIBILITY_INDEX"],
                       "related_region_refs": [], "suggested_time_windows_s": [],
                       "geometry_basis": None, "image_evidence": {
                           "perception_status": "NOT_EVALUATED", "evaluated_frames": 0,
                           "frame_records_read": 0, "frames_with_detection": None,
                           "count_complete": False, "sample_frame_refs": []},
                       "availability": "PARTIAL", "unavailable_reason": "FIXTURE_ONLY"}
                      for i, c in enumerate(selected)]
        return {"status": "UNKNOWN", "reason": "VISIBILITY_INDEX_UNAVAILABLE",
                "query_id": "cq-" + query_hash, "query_sha256": query_hash,
                "candidate_snapshot_sha256": content_hash(candidates),
                "candidates": candidates[start:end], "candidates_total": len(selected),
                "returned_count": len(candidates[start:end]), "next_cursor": cursor,
                "candidate_set_complete": False, "truncated": False,
                "unknown_camera_ids": selected, "recommended_camera_ids": selected,
                "ranking_basis": ["relation_tier", "overlap_area_m2_desc", "camera_id"],
                "stats": {"catalog_records_read": len(selected), "index_records_read": 0,
                          "frame_records_read": 0}}

    @staticmethod
    def _frames(p: dict[str, Any]) -> dict[str, Any]:
        t = Fraction(str(p["t_s"]))
        inside = 0 <= t < 20
        index = int(t * 5) if inside else None
        timestamp = Fraction(index, 5) if index is not None else None
        tiles = []
        for camera in p["camera_ids"]:
            if not inside:
                tile = {"camera_id": camera, "status": "OUT_OF_RANGE", "frame_ref": None,
                        "reason": "TIME_OUTSIDE_RUN"}
            else:
                # No image is materialized or served by this metadata-only fixture.
                tile = {"camera_id": camera, "status": "MISSING", "frame_ref": None,
                        "reason": "RGB_RECORD_ABSENT"}
            tiles.append(tile)
        return {"t_s": p["t_s"], "clock_id": "clock:" + RUN, "sampling_version": "5fps-v1",
                "frame_rule": "LATEST_AT_OR_BEFORE_EXPECTED_GRID", "tiles": tiles,
                "expected_frame_index": index,
                "expected_timestamp_s": float(timestamp) if timestamp is not None else None,
                "sample_age_s": float(t - timestamp) if timestamp is not None else None,
                "media_tokens_issued": 0}

    def _evidence(self, p: dict[str, Any]) -> dict[str, Any]:
        pick = p.get("pick")
        if (not isinstance(pick, dict) or set(pick) != {
            "layer", "ref", "result_sha256", "segment_index", "t_click_s"
        } or pick["layer"] != "curve" or pick["ref"] != "fixture-curve-1"
                or type(pick["segment_index"]) is not int or pick["segment_index"] != 0
                or type(pick["t_click_s"]) not in {int, float}
                or not math.isfinite(pick["t_click_s"]) or not 0 <= pick["t_click_s"] < 20):
            raise ValueError("INVALID_EVIDENCE_PICK")
        if pick["result_sha256"] != self._layers["curves"][0]["result_sha256"]:
            raise DataIntegrityError("RESULT_PIN_MISMATCH")
        return {"status": "UNKNOWN", "reason": "FIXTURE_SUPPORT_NOT_MATERIALIZED",
                "relation": "HYPOTHESIS_ENDPOINTS_AND_NEGATIVE_EVIDENCE",
                "nearest_support": None, "other_supports": [], "negative_evidence_frames": [],
                "jump": None}
