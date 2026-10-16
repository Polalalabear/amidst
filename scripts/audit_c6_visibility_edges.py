"""Audit grid aliasing from recorded source-ray profiles, without Blender or GT."""

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path

from c6_prescreen import search_paths


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    data = json.loads(args.input.read_text())
    spacing = data["config"]["grid_spacing_m"]
    scale = data["config"]["metres_per_blender_unit"]
    nodes = {tuple(r["grid_xy"]): r for r in data["grid_evidence"]}
    graph = {
        n: [
            m
            for m in ((n[0] - 1, n[1]), (n[0] + 1, n[1]), (n[0], n[1] - 1), (n[0], n[1] + 1))
            if m in nodes
        ]
        for n in nodes
    }
    if (
        data["search"]["edge_rejections"]
        or sum(map(len, graph.values())) // 2 != data["search"]["edges"]
    ):
        raise ValueError("CANNOT_RECONSTRUCT_PHYSICAL_GRAPH")
    seen = {
        n: sorted({i for probe in r["visible_camera_indices_by_probe"] for i in probe})
        for n, r in nodes.items()
    }
    eligible = {}
    for n, row in nodes.items():
        point = [
            n[0] * spacing,
            n[1] * spacing,
            row["floor_z_m"] + data["config"]["foot_clearance_m"],
        ]
        eligible[n] = []
        for i in row["visible_camera_indices_by_probe"][0]:
            origin = [
                data["calibrations_scene_units"][i]["camera_to_world"][k][3] * scale
                for k in (0, 1, 2)
            ]
            incidence = round(abs(point[2] - origin[2]) / math.dist(point, origin), 6)
            if incidence >= data["config"]["min_bottom_incidence"]:
                eligible[n].append(i)
    paths, _, _ = search_paths(graph, seen, eligible, spacing, data["prescreen"]["policy"])
    records = data["prescreen"]["rejected_records"]
    if len(paths) != data["prescreen"]["raw_records_evaluated"] or len(records) != len(paths):
        raise ValueError("AUDIT_REQUIRES_ALL_REJECTED_PROFILES_AND_ZERO_SELECTED")
    observed = {}
    failures = collections.Counter()
    cross_profiles = 0
    for record in records:
        index = int(record["raw_gap_id"].rsplit("-", 1)[-1]) - 1
        path = paths[index]
        profile = record["prescreen"]
        if not math.isclose(
            (len(path) - 1) * spacing,
            profile["configured_render_duration_s"]
            * data["prescreen"]["policy"]["nominal_speed_m_s"],
        ):
            raise ValueError("PROFILE_PATH_LENGTH_MISMATCH")
        intervals = profile["source_blind_intervals_distance_m"]
        for j, node in enumerate(path):
            is_blind = any(lo - 1e-8 <= j * spacing <= hi + 1e-8 for lo, hi in intervals)
            if is_blind == bool(seen[node]):
                raise ValueError("PROFILE_NODE_VISIBILITY_MISMATCH")
        cross_profiles += profile["cross_camera"]
        failures.update(profile["reasons"])
        for j, (a, b) in enumerate(zip(path, path[1:], strict=False)):
            distance = (j + 0.5) * spacing
            midpoint_visible = not any(lo - 1e-8 <= distance <= hi + 1e-8 for lo, hi in intervals)
            edge = tuple(sorted((a, b)))
            if edge in observed and observed[edge] != midpoint_visible:
                raise ValueError("STATIC_SOURCE_PROFILE_CONFLICT")
            observed[edge] = midpoint_visible
    cuts = {
        edge
        for edge, visible in observed.items()
        if visible and not seen[edge[0]] and not seen[edge[1]]
    }
    pruned = {n: [m for m in graph[n] if tuple(sorted((n, m))) not in cuts] for n in graph}

    def components(g):
        blind = {n for n in g if not seen[n]}
        multiple = []
        count = 0
        while blind:
            start = min(blind)
            blind.remove(start)
            todo, group, boundary = [start], {start}, set()
            while todo:
                n = todo.pop()
                for m in g[n]:
                    if seen[m]:
                        boundary.add(m)
                    elif m in blind:
                        blind.remove(m)
                        group.add(m)
                        todo.append(m)
            count += 1
            cameras = sorted({i for n in boundary for i in eligible[n]})
            if len(cameras) > 1:
                multiple.append(
                    {
                        "blind_nodes": len(group),
                        "boundary_nodes": len(boundary),
                        "bottom_eligible_camera_indices": cameras,
                    }
                )
        return {"blind_components": count, "multi_camera_ground_boundary_components": multiple}

    result = {
        "schema_version": "c6-source-visibility-edge-audit.v1",
        "input_sha256": sha(args.input),
        "producer_sha256": sha(__file__),
        "source_sha256": data["source_sha256"],
        "profiles_checked": len(records),
        "cross_camera_profiles_rejected": cross_profiles,
        "failure_reasons": dict(failures),
        "midpoint_edges_measured": len(observed),
        "blind_node_edges_with_visible_midpoint": [
            [[v * spacing for v in n] for n in edge] for edge in sorted(cuts)
        ],
        "before": components(graph),
        "after_known_visible_midpoint_cuts": components(pruned),
        "unmeasured_midpoints": "OPTIMISTICALLY_RETAINED_NOT_VERIFIED_BLIND",
        "authority": "BOUNDED_GRID_DIAGNOSIS_NOT_CONTINUOUS_SPACE_OR_NAVIGATION_PROOF",
        "gt_read": False,
    }
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "profiles_checked",
                    "cross_camera_profiles_rejected",
                    "failure_reasons",
                    "before",
                    "after_known_visible_midpoint_cuts",
                )
            }
        )
    )


if __name__ == "__main__":
    main()
