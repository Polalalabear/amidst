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


def sample_status(probes, rule):
    if len(probes) != 3:
        raise ValueError("VISIBILITY_PROBE_COUNT_MISMATCH")
    if rule == "ANY_PROBE_VISIBLE":
        return union_status(probes)
    if rule != "FOOT_AND_TORSO_PROBES_VISIBLE":
        raise ValueError("VISIBILITY_RULE_UNSUPPORTED")
    if probes[0] == probes[1] == "VISIBLE":
        return "VISIBLE"
    if "UNKNOWN" in probes:
        return "UNKNOWN"
    return "NOT_VISIBLE"


def predicted_leg_area_px(calibration, xy, floor_z_m, foot_offset_m, waist_offset_m, radius_m):
    """Project a vertical, camera-facing 2r-wide foot-to-waist rectangle.

    Pinhole quadrilateral area, not a bounding box or a claim of detector recall.
    All four corners must be in front and within calibrated clipping distances.
    """
    matrix = calibration["camera_to_world"]
    dx, dy = xy[0] - matrix[0][3], xy[1] - matrix[1][3]
    distance = math.hypot(dx, dy)
    if distance == 0 or not math.isfinite(distance):
        return 0.0
    tangent = [-dy / distance, dx / distance]
    pixels = []
    for side, height in (
        (-1, foot_offset_m),
        (1, foot_offset_m),
        (1, waist_offset_m),
        (-1, waist_offset_m),
    ):
        point = [
            xy[0] + side * radius_m * tangent[0],
            xy[1] + side * radius_m * tangent[1],
            floor_z_m + height,
        ]
        delta = [point[i] - matrix[i][3] for i in range(3)]
        local = [sum(matrix[i][j] * delta[i] for i in range(3)) for j in range(3)]
        depth = -local[2]
        if not calibration["clip_start"] <= depth <= calibration["clip_end"] or depth <= 0:
            return 0.0
        pixels.append(
            (
                calibration["cx"] + calibration["fx"] * local[0] / depth,
                calibration["cy"] - calibration["fy"] * local[1] / depth,
            )
        )
    area = (
        abs(
            sum(
                a[0] * b[1] - b[0] * a[1]
                for a, b in zip(pixels, pixels[1:] + pixels[:1], strict=True)
            )
        )
        / 2
    )
    return area if math.isfinite(area) else 0.0


def cell_status(statuses):
    if all(s == "VISIBLE" for s in statuses):
        return "SAMPLED_VISIBLE"
    if any(s in {"VISIBLE", "UNKNOWN"} for s in statuses):
        return "UNKNOWN_MIXED"
    return "SAMPLED_NOT_VISIBLE_NOT_CONTINUOUS_BLIND_PROOF"
