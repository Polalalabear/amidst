"""Static source ray-test policy; no renderer/target visibility or trajectories."""

import math


def probe_status(calibration, point, raycast):
    matrix = calibration["camera_to_world"]
    delta = [point[i] - matrix[i][3] for i in range(3)]
    local = [sum(matrix[i][j] * delta[i] for i in range(3)) for j in range(3)]
    depth = -local[2]
    if not all(math.isfinite(v) for v in (*local, depth)):
        return "UNKNOWN"
    if not calibration["clip_start"] <= depth <= calibration["clip_end"]:
        return "CLIPPED"
    u = calibration["cx"] + calibration["fx"] * local[0] / depth
    v = calibration["cy"] - calibration["fy"] * local[1] / depth
    if not (0 <= u < calibration["width"] and 0 <= v < calibration["height"]):
        return "OUTSIDE_FOV"
    return raycast()


def union_status(statuses):
    if "VISIBLE" in statuses:
        return "VISIBLE"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "NOT_VISIBLE"


def cell_status(statuses):
    if all(s == "VISIBLE" for s in statuses):
        return "SAMPLED_VISIBLE"
    if any(s in {"VISIBLE", "UNKNOWN"} for s in statuses):
        return "UNKNOWN_MIXED"
    return "SAMPLED_NOT_VISIBLE_NOT_CONTINUOUS_BLIND_PROOF"
