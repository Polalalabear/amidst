"""Fixed render-frame admission and clock checks, with no Blender or GT input."""

import math

from c6_prescreen import classify_route, is_visible


def frame_times(duration_s, clock):
    if clock["fps"] != 5 or clock["speed_m_s"] != 1.5:
        raise ValueError("UNEXPECTED_FROZEN_CLOCK")
    origin = clock["origin_s"] + clock["phase_s"]
    start = clock["route_start_s"]
    first = math.ceil((start - origin) * clock["fps"] - 1e-9)
    last = math.floor((start + duration_s - origin) * clock["fps"] + 1e-9)
    return [round(origin + i / clock["fps"], 9) for i in range(first, last + 1)]


def check_k1_alignment(times, clock, time_step_s):
    if not math.isclose(time_step_s, 0.2, abs_tol=1e-12):
        raise ValueError("K1_TIME_STEP_MUST_BE_0_2")
    origin = clock["origin_s"] + clock["phase_s"]
    if any(
        abs((t - origin) / time_step_s - round((t - origin) / time_step_s)) > 1e-7 for t in times
    ):
        raise ValueError("K1_TIME_NOT_ON_RENDER_FRAME")
    return True


def classify_frames(record, dense_samples, config):
    policy = dict(config["prescreen"])
    speed = config["render_clock"]["speed_m_s"]
    # Historical classifier is reused with actual speed for D7. Visible prefix/
    # suffix lengths are measured on the denser source diagnostic below.
    policy["speed_band_m_s"] = [policy["speed_band_m_s"][0], speed]
    policy["min_visible_duration_s"] = 0
    result = classify_route(record, policy, config["min_bottom_incidence"])
    frames = record["samples"]
    check_k1_alignment([s["timestamp_s"] for s in frames], config["render_clock"], 0.2)
    result["single_gap_basis"] = "ACTUAL_FIXED_5HZ_FRAME_TIMES"
    result["ground_duration_basis"] = "ACTUAL_RENDER_SPEED_FRAME_SPAN"
    result["render_duration_s"] = record["length_m"] / speed
    result["last_frame_s"] = frames[-1]["timestamp_s"]
    # Do not truncate the physical route to its last integer frame: source rays
    # also cover the declared physical endpoint, used only for length screening.
    flags = [is_visible(s["rays"]) for s in dense_samples]
    prefix = next((i for i, v in enumerate(flags) if not v), None)
    suffix = next((i for i in range(len(flags) - 1, -1, -1) if not flags[i]), None)
    visible = (
        [0, 0]
        if prefix is None
        else [
            dense_samples[max(0, prefix - 1)]["distance_m"],
            record["length_m"] - dense_samples[min(len(flags) - 1, suffix + 1)]["distance_m"],
        ]
    )
    result["minimum_visible_length_m"] = (
        config["prescreen"]["min_visible_duration_s"] * config["prescreen"]["speed_band_m_s"][0]
    )
    result["approach_length_m"], result["departure_length_m"] = visible
    for side, length in zip(("APPROACH", "DEPARTURE"), visible, strict=True):
        if length + 1e-9 < result["minimum_visible_length_m"]:
            result["reasons"].append(side + "_TOO_SHORT")
    for side in result.get("blind_adjacent_ground_segments", {}).values():
        side["duration_s_at_render_speed"] = side.pop("minimum_duration_s_at_speed_upper")
    result["qualified"] = not result["reasons"]
    return result
