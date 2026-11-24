"""Display-only ground estimates from selected, pinned detection observations."""

from __future__ import annotations

import math
from collections import defaultdict

from amidst.live_mode.tracker import Projector
from amidst.q1q5.physical_prediction import DEFAULT_PARAMS

FOOT_EDGE_MARGIN_PX = 4
DISPLAY_ESTIMATE_SCHEMA = "q-core.display-estimate.v1"

DEFAULT_MAX_SPEED_M_S = DEFAULT_PARAMS.speed_range_m_s[-1]


def estimate_track(
    records,
    response,
    catalog,
    *,
    catalog_sha256,
    index_sha256,
    clock_id,
    max_speed_m_s=DEFAULT_MAX_SPEED_M_S,
):
    def unknown(reason):
        return {
            "schema_version": DISPLAY_ESTIMATE_SCHEMA,
            "est_xy": "UNKNOWN",
            "uncertainty_m": "UNKNOWN",
            "reason": reason,
        }

    if catalog is None:
        return unknown("CALIBRATION_MISSING")
    as_of = response["as_of_us"]
    cameras = {c["camera_id"]: c for c in catalog["cameras"]}
    projector = Projector(list(cameras.values()))
    wanted = {
        (s["camera_id"], oid)
        for s in response["sightings"]
        if s.get("selected_for_single_view", True)
        for oid in s["observation_ids"]
    }
    selected = response["single_view"]
    points = defaultdict(dict)
    for row in records:
        stamp, camera = row["timestamp_us"], row["camera_id"]
        if stamp > as_of:
            continue
        if not any(
            s["kind"] == "ON_CAMERA"
            and s["camera_id"] == camera
            and s["range_us"][0] <= stamp < s["range_us"][1]
            for s in selected
        ):
            continue
        calibration = cameras.get(camera)
        for det in row["detections"] or []:
            oid = det["observation_id"]
            if (camera, oid) not in wanted:
                continue
            key = (camera, oid)
            if calibration is None:
                points[stamp][key] = "CALIBRATION_MISSING"
                continue
            x1, y1, x2, y2 = det["bbox_xyxy_px"]
            if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                points[stamp][key] = "GROUND_PROJECTION_UNDEFINED"
                continue
            if y2 >= calibration["height"] - FOOT_EDGE_MARGIN_PX:
                points[stamp][key] = "FOOT_TRUNCATED_AT_FRAME_BOTTOM"
                continue
            xy = projector.ground(
                camera, (x1 + x2) / 2, y2, calibration["width"], calibration["height"]
            )
            points[stamp][key] = (
                xy
                if xy is not None and all(math.isfinite(v) for v in xy)
                else "GROUND_PROJECTION_UNDEFINED"
            )
    if not points:
        return unknown("NO_PROJECTABLE_SELECTED_OBSERVATION")
    latest = max(points)
    reasons = {value for value in points[latest].values() if isinstance(value, str)}
    for reason in (
        "FOOT_TRUNCATED_AT_FRAME_BOTTOM",
        "GROUND_PROJECTION_UNDEFINED",
        "CALIBRATION_MISSING",
    ):
        if reason in reasons:
            return unknown(reason)
    if len(points[latest]) != 1:
        return unknown("AMBIGUOUS_SELECTED_OBSERVATIONS")
    xy = next(iter(points[latest].values()))
    elapsed_s = (as_of - latest) / 1_000_000
    return {
        "schema_version": DISPLAY_ESTIMATE_SCHEMA,
        "est_xy": xy,
        "uncertainty_m": max_speed_m_s * elapsed_s,
        "last_observed_us": latest,
        "method": "BOX_FOOT_TO_Z0_LAST_POSITION",
        "uncertainty_basis": "SPEED_ONLY_REACHABLE_RADIUS",
        "max_speed_m_s": max_speed_m_s,
        "source_clock_id": clock_id,
        "source_index_sha256": index_sha256,
        "calibration_sha256": catalog_sha256,
    }
