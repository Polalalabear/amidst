"""Pure C6 pre-render policies. Source raycasts are injected by the Blender caller."""

from __future__ import annotations

import collections
import hashlib
import math


def probe_visibility(ndc, clip_start, clip_end, raycast):
    """Call a zero-argument raycast only for an in-frustum point.

    raycast returns an occluder id, or None for a clear ray. No Blender import,
    renderer visibility, target truth, or depth image is used here.
    """
    x, y, axial_depth = ndc
    if not all(math.isfinite(v) for v in (*ndc, clip_start, clip_end)):
        raise ValueError("NONFINITE_VISIBILITY_INPUT")
    if not 0 < clip_start < clip_end:
        raise ValueError("INVALID_CLIP_RANGE")
    if not clip_start <= axial_depth <= clip_end:
        return {"status": "CLIPPED", "occluder": None}
    if not (0 <= x < 1 and 0 <= y < 1):
        return {"status": "OUTSIDE_FOV", "occluder": None}
    blocker = raycast()
    return {"status": "VISIBLE" if blocker is None else "OCCLUDED", "occluder": blocker}


def is_visible(camera_probes):
    """Shared C6/C5 acceptance semantics: ANY probe visible means not blind."""
    return any(p["status"] == "VISIBLE" for probes in camera_probes for p in probes)


def simplified_indices(points, tolerance):
    """RDP merges collinear/staircase excursions within a declared tolerance.

    This simplifies *turn measurement only*. It never moves a rendered route or
    substitutes an unchecked chord for the source-checked original path.
    """
    if len(points) <= 2:
        return list(range(len(points)))

    def distance(p, a, b):
        delta = [b[i] - a[i] for i in (0, 1)]
        denom = sum(v * v for v in delta)
        t = max(0, min(1, sum((p[i] - a[i]) * delta[i] for i in (0, 1)) / denom)) if denom else 0
        return math.hypot(*(p[i] - a[i] - t * delta[i] for i in (0, 1)))

    def recurse(lo, hi):
        if hi <= lo + 1:
            return [lo, hi] if hi != lo else [lo]
        index = max(range(lo + 1, hi), key=lambda i: distance(points[i], points[lo], points[hi]))
        if distance(points[index], points[lo], points[hi]) <= tolerance:
            return [lo, hi]
        return recurse(lo, index)[:-1] + recurse(index, hi)

    return recurse(0, len(points) - 1)


def classify_route(record, policy, min_incidence=0.25):
    """No endpoint substitution: evaluate the supplied route exactly as sampled."""
    samples = record["samples"]
    lower, upper = policy["speed_band_m_s"]
    nominal = policy["nominal_speed_m_s"]
    if not 0 < lower <= nominal <= upper <= 2:
        raise ValueError("INVALID_FROZEN_SPEED_BAND")
    flags = [is_visible(s["rays"]) for s in samples]
    blind = [i for i, v in enumerate(flags) if not v]
    runs = []
    for index in blind:
        if not runs or index != runs[-1][-1] + 1:
            runs.append([index])
        else:
            runs[-1].append(index)
    reasons = []
    qualifying = []
    for sample in samples:
        actual = [
            i
            for i, probes in enumerate(sample["rays"])
            if probes[0]["status"] == "VISIBLE" and probes[0]["incidence"] >= min_incidence
        ]
        # Reject inconsistent claimed eligibility instead of trusting a nonempty list.
        claimed = sample["v2_bottom_eligible_cameras"]
        qualifying.append(bool(actual) and len(actual) == len(claimed))
    result = {
        "endpoint_ground_qualified": {"start": qualifying[0], "end": qualifying[-1]},
        "both_endpoints_ground_qualified": qualifying[0] and qualifying[-1],
        "duration_s_at_nominal_speed": record["length_m"] / nominal,
        "duration_s_at_speed_band_lower": record["length_m"] / lower,
        "max_window_s": policy["max_window_s"],
        "turns_in_blind": 0,
        "turn_events_in_blind": [],
        "cross_camera": not bool(
            set(samples[0]["v2_bottom_eligible_cameras"])
            & set(samples[-1]["v2_bottom_eligible_cameras"])
        ),
        "source_blind_intervals_distance_m": [
            [samples[run[0]]["distance_m"], samples[run[-1]]["distance_m"]] for run in runs
        ],
    }
    if not result["both_endpoints_ground_qualified"]:
        reasons.append("ENDPOINT_GROUND_UNQUALIFIED")
    window_duration = (
        result["duration_s_at_nominal_speed"]
        if policy.get("window_basis") == "FIXED_NOMINAL_RENDER_SCHEDULE"
        else result["duration_s_at_speed_band_lower"]
    )
    result["configured_render_speed_m_s"] = nominal
    result["configured_render_duration_s"] = result["duration_s_at_nominal_speed"]
    result["window_check_basis"] = policy.get("window_basis", "SPEED_BAND_LOWER")
    if window_duration > policy["max_window_s"] + 1e-9:
        reasons.append("MAX_WINDOW_EXCEEDED_AT_SPEED_BAND_LOWER")
    if not blind or not flags[0] or not flags[-1] or blind != list(range(blind[0], blind[-1] + 1)):
        reasons.append("NOT_SINGLE_INTERIOR_BLIND_INTERVAL")
        return {**result, "qualified": False, "reasons": reasons}
    first, last = blind[0], blind[-1]
    blind_length = samples[last]["distance_m"] - samples[first]["distance_m"]
    if blind_length + 1e-9 < policy["min_blind_length_m"]:
        reasons.append("BLIND_INTERVAL_TOO_SHORT")
    distances = [s["distance_m"] for s in samples]
    visible_lengths = [distances[first - 1], distances[-1] - distances[last + 1]]
    minimum_visible = policy["min_visible_duration_s"] * lower
    for side, length in zip(("approach", "departure"), visible_lengths, strict=True):
        if length + 1e-9 < minimum_visible:
            reasons.append(f"{side.upper()}_TOO_SHORT")
    adjacent = []
    for index, direction in ((first - 1, -1), (last + 1, 1)):
        boundary = index
        while 0 <= index < len(samples) and qualifying[index] and flags[index]:
            index += direction
        outer = index - direction
        length = abs(distances[boundary] - distances[outer]) if qualifying[boundary] else 0
        adjacent.append(
            {
                "length_m": length,
                "minimum_duration_s_at_speed_upper": length / upper,
                "boundary_sample_index": boundary,
                "outer_sample_index": outer,
                "qualified": length / upper + 1e-9 >= policy["min_endpoint_qualified_duration_s"],
            }
        )
    if not all(a["qualified"] for a in adjacent):
        reasons.append("BLIND_ADJACENT_QUALIFIED_SEGMENT_TOO_SHORT")
    points = [s["foot_position_m"] for s in samples]
    indices = simplified_indices(points, policy["simplification_tolerance_m"])
    events = []
    for a, b, c in zip(indices, indices[1:], indices[2:], strict=False):
        v = [points[b][k] - points[a][k] for k in (0, 1)]
        w = [points[c][k] - points[b][k] for k in (0, 1)]
        denom = math.hypot(*v) * math.hypot(*w)
        if not denom:
            continue
        angle = math.degrees(
            math.acos(max(-1, min(1, sum(x * y for x, y in zip(v, w, strict=True)) / denom)))
        )
        if first <= b <= last and angle > policy["min_turn_angle_degrees"]:
            events.append({"sample_index": b, "distance_m": distances[b], "angle_degrees": angle})
    return {
        **result,
        "qualified": not reasons,
        "reasons": reasons,
        "approach_length_m": visible_lengths[0],
        "departure_length_m": visible_lengths[1],
        "minimum_visible_length_m": minimum_visible,
        "blind_length_m": blind_length,
        "blind_sample_indices": [first, last],
        "blind_adjacent_ground_segments": dict(
            zip(("approach", "departure"), adjacent, strict=True)
        ),
        "turns_in_blind": len(events),
        "turn_events_in_blind": events,
        "simplified_turn_measurement_indices": indices,
        "simplified_path_used_for_motion": False,
        "cross_camera": not bool(
            set(samples[0]["v2_bottom_eligible_cameras"])
            & set(samples[-1]["v2_bottom_eligible_cameras"])
        ),
    }


def search_paths(graph, seen, eligible, spacing, policy):
    """Search new paths with two-sided bottom-eligible visible approaches."""
    side_steps = math.ceil(
        max(
            policy["min_visible_duration_s"] * policy["speed_band_m_s"][0],
            policy["min_endpoint_qualified_duration_s"] * policy["speed_band_m_s"][1],
        )
        / spacing
    )
    window_speed = (
        policy["nominal_speed_m_s"]
        if policy.get("window_basis") == "FIXED_NOMINAL_RENDER_SCHEDULE"
        else policy["speed_band_m_s"][0]
    )
    limit = math.floor(policy["max_window_s"] * window_speed / spacing)
    boundary = sorted(
        n for n in graph if seen[n] and eligible[n] and any(not seen[m] for m in graph[n])
    )

    def extension(start, forbidden, camera):
        queue = collections.deque([[start]])
        visited = {start}
        while queue:
            path = queue.popleft()
            if len(path) == side_steps + 1:
                return path
            for n in sorted(graph[path[-1]]):
                if n not in visited and n not in forbidden and camera in eligible[n]:
                    visited.add(n)
                    queue.append(path + [n])
        return None

    paths, unique = [], set()
    cap = policy["max_boundary_entries"]
    stride = max(1, math.ceil(len(boundary) / cap))
    for start in boundary[::stride]:
        queue = collections.deque([[start]])
        visited = {start}
        exits = 0
        while queue and exits < policy["max_exits_per_entry"]:
            path = queue.popleft()
            if len(path) + 2 * side_steps > limit:
                continue
            for n in sorted(graph[path[-1]]):
                if n in visited:
                    continue
                visited.add(n)
                middle = path + [n]
                if seen[n]:
                    if not eligible[n] or len(middle) < 3:
                        continue
                    for ca in eligible[start]:
                        before = extension(start, set(middle[1:]), ca)
                        if before is None:
                            continue
                        for cb in eligible[n]:
                            after = extension(n, set(middle[:-1]) | set(before), cb)
                            if after is None:
                                continue
                            candidate = before[:0:-1] + middle + after[1:]
                            key = min(tuple(candidate), tuple(reversed(candidate)))
                            if key not in unique and len(candidate) - 1 <= limit:
                                unique.add(key)
                                paths.append(candidate)
                                exits += 1
                                if len(paths) >= policy["max_candidate_records"]:
                                    return paths, len(boundary), True
                else:
                    queue.append(middle)
    if policy.get("blind_waypoint_search"):
        # Diverse source-side paths through blind waypoints, rather than only
        # shortest paths. Revisiting cells is explicit and never an identity claim.
        max_middle = limit - 2 * side_steps

        def tree(start):
            parents = {start: None}
            distance = {start: 0}
            queue = collections.deque([start])
            while queue:
                n = queue.popleft()
                if distance[n] >= max_middle:
                    continue
                for m in sorted(graph[n]):
                    if m not in parents and not seen[m]:
                        parents[m] = n
                        distance[m] = distance[n] + 1
                        queue.append(m)
            return parents, distance

        trees = {n: tree(n) for n in boundary[::stride]}

        def branch(parents, node):
            path = []
            while node is not None:
                path.append(node)
                node = parents[node]
            return path[::-1]

        for start in boundary[::stride]:
            for end in boundary[::stride]:
                if start >= end or set(eligible[start]) & set(eligible[end]):
                    continue
                before = next(
                    (
                        p
                        for camera in eligible[start]
                        if (p := extension(start, {end}, camera)) is not None
                    ),
                    None,
                )
                after = next(
                    (
                        p
                        for camera in eligible[end]
                        if (p := extension(end, set(before or []) | {start}, camera)) is not None
                    ),
                    None,
                )
                if before is None or after is None:
                    continue
                pa, da = trees[start]
                pb, db = trees[end]
                waypoints = sorted(
                    n for n in da.keys() & db.keys() if not seen[n] and da[n] + db[n] <= max_middle
                )
                # Spatially sample, not by a prediction/GT score.
                skip = max(1, math.ceil(len(waypoints) / policy["max_waypoints_per_pair"]))
                for waypoint in waypoints[::skip]:
                    middle = branch(pa, waypoint) + branch(pb, waypoint)[-2::-1]
                    candidate = before[:0:-1] + middle + after[1:]
                    key = min(tuple(candidate), tuple(reversed(candidate)))
                    if key in unique or len(candidate) - 1 > limit:
                        continue
                    unique.add(key)
                    paths.append(candidate)
                    if len(paths) >= policy["max_candidate_records"]:
                        return paths, len(boundary), True
    return paths, len(boundary), False


def select_benchmarks(records, policy):
    """Qualified records only; never fill a shortfall with degraded samples."""
    pool = [r for r in records if r["prescreen"]["qualified"]]
    selected = []
    pairs = collections.Counter()
    same_long = 0
    while pool and len(selected) < policy["max_selected"]:

        def key(r):
            p = r["prescreen"]
            pair = (
                tuple(r["samples"][0]["v2_bottom_eligible_cameras"]),
                tuple(r["samples"][-1]["v2_bottom_eligible_cameras"]),
            )
            return p["cross_camera"], -pairs[pair], bool(p["turns_in_blind"]), p["blind_length_m"]

        record = max(pool, key=key)
        pool.remove(record)
        p = record["prescreen"]
        pair = (
            tuple(record["samples"][0]["v2_bottom_eligible_cameras"]),
            tuple(record["samples"][-1]["v2_bottom_eligible_cameras"]),
        )
        long_same = (
            not p["cross_camera"] and p["blind_length_m"] >= policy["long_blind_threshold_m"]
        )
        if pairs[pair] >= policy["max_per_camera_pair"] or (
            long_same and same_long >= policy["max_long_same_camera_routes"]
        ):
            continue
        positions = {tuple(s["foot_position_m"][:2]) for s in record["samples"]}
        if any(
            len(positions & other) / min(len(positions), len(other))
            > policy["max_path_overlap_fraction"]
            for other in ({tuple(s["foot_position_m"][:2]) for s in r["samples"]} for r in selected)
        ):
            continue
        selected.append(record)
        pairs[pair] += 1
        same_long += long_same
    cross = sum(r["prescreen"]["cross_camera"] for r in selected)
    # Remove same-camera tails if they would violate the required majority.
    while selected and cross / len(selected) < policy["min_cross_camera_fraction"]:
        index = max(i for i, r in enumerate(selected) if not r["prescreen"]["cross_camera"])
        selected.pop(index)
    for i, record in enumerate(selected, 1):
        record["benchmark_id"] = f"c6-benchmark-{i:03}"
    return selected


def adjacent_exits(graph, seen, blind_path, spacing):
    """Geometric visibility-boundary clusters, explicitly not semantic portals."""
    queue = collections.deque(blind_path)
    visited = set(blind_path)
    boundary = set()
    while queue:
        n = queue.popleft()
        for m in graph[n]:
            if seen[m]:
                boundary.add(m)
            elif m not in visited:
                visited.add(m)
                queue.append(m)
    groups = []
    while boundary:
        start = min(boundary)
        boundary.remove(start)
        group, todo = [start], [start]
        while todo:
            n = todo.pop()
            for m in graph[n]:
                if m in boundary:
                    boundary.remove(m)
                    group.append(m)
                    todo.append(m)
        cameras = sorted({c for n in group for c in seen[n]})
        token = hashlib.sha256(str(sorted(group)).encode()).hexdigest()[:12]
        groups.append(
            {
                "exit_ref": f"c6-geometric-exit:{token}",
                "camera_indices": cameras,
                "sample_count": len(group),
                "xy_bounds_m": [
                    [min(n[a] for n in group) * spacing for a in (0, 1)],
                    [max(n[a] for n in group) * spacing for a in (0, 1)],
                ],
                "authority": "VISIBILITY_BOUNDARY_NOT_A_CERTIFIED_PORTAL",
                "exclusion_status": "CONDITIONAL_ON_C5_AND_VALID_NO_DETECTION_NOT_APPLIED",
            }
        )
    return groups
