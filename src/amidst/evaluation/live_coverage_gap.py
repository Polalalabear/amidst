"""#630 LIVE outdoor coverage-gap analysis (geometry only, no rendering).

Ground coverage of every r004 camera is computed from the committed scene geometry
(`docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json`: pinhole intrinsics, Blender camera_to_world,
full-height occluder segments). A floor point (x, y) counts as seen by a camera when at least two of
three body points (z = 0.15, 0.9, 1.6 m) project inside the frame in front of the camera and the 2-D
sight line does not cross an occluder segment; this mirrors `groundTruthVisible` in
`frontend/live-mode/src/world.mjs` (2-of-3 points, ray blocked by walls).

GT isolation: recorded tick positions and `gt_visible` lists are read here only to SCORE a coverage
model offline. Nothing in this module feeds inference, ranking or scheduling.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

HEIGHTS = (0.15, 0.9, 1.6)
GRAPH_V3_CAMERAS = (
    "CAM_BRANCH", "CAM_EXT_CAR", "CAM_EXT_CLEAR", "CAM_R101_IN", "CAM_W1", "CAM_W2", "CAM_WIDE",
)
YARD = (-15.2, -3.2, -6.0, 8.0)  # x0, x1, y0, y1 of R004_EXTERIOR_FLOOR
HARD_CASES = ("H1-1", "H1-2", "H1-3", "H4-1", "H4-2", "H4-3", "H5-1", "H5-2", "H5-3")


class Camera:
    """Pinhole camera; `c2w` is a Blender-convention 4x4 (camera looks along -Z, +Y up)."""

    def __init__(self, camera_id, c2w, fx, fy, width, height, near=0.05, far=100.0):
        self.camera_id = camera_id
        self.fx, self.fy = fx, fy
        self.cx, self.cy = width / 2.0, height / 2.0
        self.width, self.height = width, height
        self.near, self.far = near, far
        self.pos = tuple(c2w[i][3] for i in range(3))
        self.rot = [[c2w[r][c] for c in range(3)] for r in range(3)]  # columns = camera axes in world

    def to_camera(self, x, y, z):
        d = (x - self.pos[0], y - self.pos[1], z - self.pos[2])
        return tuple(sum(self.rot[r][c] * d[r] for r in range(3)) for c in range(3))  # R^T d

    def sees_point(self, x, y, z):
        px, py, pz = self.to_camera(x, y, z)
        depth = -pz
        if depth <= self.near or depth > self.far:
            return False
        u = self.cx + self.fx * px / depth
        v = self.cy - self.fy * py / depth
        return 0 <= u <= self.width and 0 <= v <= self.height


def make_camera(camera_id, pos, yaw_deg, pitch_deg, fx, fy, width=960, height=540):
    """Camera at `pos` (Blender x, y, z) looking along heading `yaw_deg` (0 = +x, 90 = +y), pitched down."""
    yaw, pit = math.radians(yaw_deg), math.radians(pitch_deg)
    fwd = (math.cos(yaw) * math.cos(pit), math.sin(yaw) * math.cos(pit), -math.sin(pit))
    right = (math.sin(yaw), -math.cos(yaw), 0.0)
    up = (right[1] * fwd[2] - right[2] * fwd[1], right[2] * fwd[0] - right[0] * fwd[2], right[0] * fwd[1] - right[1] * fwd[0])
    back = tuple(-v for v in fwd)
    c2w = [[right[i], up[i], back[i], pos[i]] for i in range(3)] + [[0, 0, 0, 1]]
    return Camera(camera_id, c2w, fx, fy, width, height)


def load_geometry(path):
    g = json.loads(Path(path).read_text())
    cams = {}
    for c in g["cameras"]:
        cams[c["camera_id"]] = Camera(c["camera_id"], c["camera_to_world"], c["fx"], c["fy"], c["width"], c["height"],
                                      c.get("clip_start", 0.05), c.get("clip_end", 100.0))
    occ = [(tuple(o["a"]), tuple(o["b"])) for o in g["occluders_full_height"]]
    return cams, occ, g


def _ccw(a, b, c):
    return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])


def segments_cross(p, q, a, b):
    d1, d2 = _ccw(p, q, a), _ccw(p, q, b)
    d3, d4 = _ccw(a, b, p), _ccw(a, b, q)
    return d1 * d2 < 0 and d3 * d4 < 0


def sees_floor_point(cam, occluders, x, y, min_seen=2, max_dist=None):
    if max_dist is not None and math.hypot(x - cam.pos[0], y - cam.pos[1]) > max_dist:
        return False
    if sum(cam.sees_point(x, y, z) for z in HEIGHTS) < min_seen:
        return False
    p, q = cam.pos[:2], (x, y)
    return not any(segments_cross(p, q, a, b) for a, b in occluders)


def visible_cameras(cams, occluders, x, y, ids=None, max_dist=None):
    return [cid for cid, c in cams.items()
            if (ids is None or cid in ids) and sees_floor_point(c, occluders, x, y, max_dist=max_dist)]


def grid(region=YARD, step=0.25):
    x0, x1, y0, y1 = region
    nx, ny = int(round((x1 - x0) / step)), int(round((y1 - y0) / step))
    return [(x0 + (i + 0.5) * step, y0 + (j + 0.5) * step) for j in range(ny) for i in range(nx)], step


def coverage_map(cams, occluders, ids, region=YARD, step=0.25):
    pts, step = grid(region, step)
    return {p: [cid for cid in ids if sees_floor_point(cams[cid], occluders, *p)] for p in pts}, step


def uncovered_stats(cov, step):
    unc = [p for p, v in cov.items() if not v]
    area = len(unc) * step * step
    if not unc:
        return {"area_m2": 0.0, "total_m2": len(cov) * step * step, "bbox": None}
    xs, ys = [p[0] for p in unc], [p[1] for p in unc]
    return {"area_m2": round(area, 1), "total_m2": round(len(cov) * step * step, 1),
            "fraction": round(len(unc) / len(cov), 3),
            "bbox": [round(min(xs), 2), round(max(xs), 2), round(min(ys), 2), round(max(ys), 2)]}


def ascii_map(cov, step, region=YARD, scale=2):
    """North (+y) at the top; '#' = no camera, digit = number of cameras seeing the cell."""
    x0, x1, y0, y1 = region
    pts = cov
    rows = []
    cell = step * scale
    ny, nx = int(round((y1 - y0) / cell)), int(round((x1 - x0) / cell))
    for j in range(ny - 1, -1, -1):
        row = ""
        for i in range(nx):
            x, y = x0 + (i + 0.5) * cell, y0 + (j + 0.5) * cell
            key = min(pts, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
            n = len(pts[key])
            row += "#" if n == 0 else str(min(n, 9))
        rows.append(f"y={y0 + (j + 0.5) * cell:5.1f} {row}")
    return "\n".join(rows)


def load_ticks(log_path):
    """Target ticks from a smoke A log (xy, t_sim, recorded GT-visible cameras). Evaluation only."""
    a = json.loads(Path(log_path).read_text())
    out = []
    for t in a["ticks"]:
        T = next((x for x in t["actors"] if x["id"] == "T"), None)
        if T and T.get("present") and T.get("xy"):
            out.append({"tick": t["tick"], "t_sim": t["t_sim"], "xy": tuple(T["xy"]), "gt_visible": list(T["gt_visible"])})
    return out


def gap_segments(ticks, covered):
    """Maximal runs of consecutive ticks whose `covered(tick)` is False."""
    segs, cur = [], []
    for t in ticks:
        if covered(t):
            if cur:
                segs.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        segs.append(cur)
    return [{"start_tick": s[0]["tick"], "end_tick": s[-1]["tick"], "t_start": round(s[0]["t_sim"], 1),
             "duration_s": round(s[-1]["t_sim"] - s[0]["t_sim"], 1), "n": len(s),
             "from_xy": [round(v, 1) for v in s[0]["xy"]], "to_xy": [round(v, 1) for v in s[-1]["xy"]]} for s in segs]


def ticks_report(ticks, cams, occluders, ids):
    """Per-tick: GT-recorded graph visibility and the geometric model's; agreement of the two."""
    n = len(ticks)
    gt_none = sum(1 for t in ticks if not [c for c in t["gt_visible"] if c in ids])
    gt_entry_only = sum(1 for t in ticks if not [c for c in t["gt_visible"] if c in ids] and "CAM_ENTRY" in t["gt_visible"])
    model_none = 0
    agree = 0
    for t in ticks:
        m = visible_cameras(cams, occluders, *t["xy"], ids=ids)
        model_none += not m
        agree += (not m) == (not [c for c in t["gt_visible"] if c in ids])
    return {"ticks": n, "gt_no_graph_cam": gt_none, "gt_entry_only": gt_entry_only,
            "model_no_graph_cam": model_none, "model_gt_agree_no_cam": agree}


def best_added_camera(cams, occluders, ids, points, region=YARD, step=1.0, fx=685.5, fy=685.5, pitch=20.0, height=3.0, top=5, max_dist=None):
    """Greedy single-camera search on the yard boundary: which new camera covers most currently-uncovered points.
    `points` are (x, y) target positions (e.g. all hard-set ticks); the search never sees GT visibility."""
    x0, x1, y0, y1 = region
    cands = []
    for i in range(int((x1 - x0) / step) + 1):
        x = x0 + i * step
        cands += [(x, y0), (x, y1)]
    for j in range(int((y1 - y0) / step) + 1):
        y = y0 + j * step
        cands += [(x0, y), (x1, y)]
    base_uncov = [p for p in points if not visible_cameras(cams, occluders, *p, ids=ids, max_dist=max_dist)]
    pts, st = grid(region, 0.5)
    base_area_unc = [p for p in pts if not visible_cameras(cams, occluders, *p, ids=ids)]
    rows = []
    for (cx, cy) in cands:
        for yaw in range(0, 360, 45):
            cam = make_camera("CAND", (cx, cy, height), yaw, pitch, fx, fy)
            gain_ticks = sum(sees_floor_point(cam, occluders, *p, max_dist=max_dist) for p in base_uncov)
            gain_area = sum(sees_floor_point(cam, occluders, *p) for p in base_area_unc) * st * st
            rows.append({"pos": [round(cx, 1), round(cy, 1), height], "yaw_deg": yaw, "gain_ticks": gain_ticks,
                         "gain_area_m2": round(gain_area, 1)})
    rows.sort(key=lambda r: (-r["gain_ticks"], -r["gain_area_m2"]))
    return {"base_uncovered_ticks": len(base_uncov), "base_uncovered_area_m2": round(len(base_area_unc) * st * st, 1),
            "top": rows[:top]}


def uncovered_count(points, cams, occluders, ids, extra=(), max_dist=None):
    """How many target positions no camera of `ids` (plus `extra` Camera objects) sees (optionally within `max_dist` m)."""
    return sum(1 for p in points
               if not visible_cameras(cams, occluders, *p, ids=ids, max_dist=max_dist)
               and not any(sees_floor_point(c, occluders, *p, max_dist=max_dist) for c in extra))


def pre_window_points(ticks, hard_t, window_s=3.0):
    """Target positions in the `window_s` seconds before the hard point (OCCLUSION_START, graph reading)."""
    return [t for t in ticks if hard_t - window_s <= t["t_sim"] < hard_t]


def hard_points_from_check(check_path):
    """case_id -> graph-reading hard point time, from hardset_check.json (offline scoring output, GT-derived)."""
    out = {}
    for it in json.loads(Path(check_path).read_text()):
        gaps = it["graph"]["gaps"]
        if gaps:
            out[it["case_id"]] = {"t": gaps[0]["t_start"], "last_cams": gaps[0]["last_cams"], "last_xy": gaps[0]["last_xy"],
                                  "unseen_s": gaps[0]["unseen_s"]}
    return out


def reaim_search(cams, occluders, ids, camera_id, points, step=15, pitches=(15.0, 20.0, 30.0), region=YARD):
    """Re-aim one existing camera (same position and intrinsics): union coverage of `ids` over `points` and yard area."""
    base = cams[camera_id]
    others = [i for i in ids if i != camera_id]
    pts, st = grid(region, 0.5)
    rows = []
    for yaw in range(0, 360, step):
        for pitch in pitches:
            c = make_camera(camera_id, base.pos, yaw, pitch, base.fx, base.fy, base.width, base.height)
            unc_t = uncovered_count(points, cams, occluders, others, extra=[c])
            unc_a = sum(1 for p in pts if not visible_cameras(cams, occluders, *p, ids=others) and not sees_floor_point(c, occluders, *p)) * st * st
            rows.append({"yaw_deg": yaw, "pitch_deg": pitch, "uncovered_ticks": unc_t, "uncovered_area_m2": round(unc_a, 1)})
    rows.sort(key=lambda r: (r["uncovered_ticks"], r["uncovered_area_m2"]))
    cur_t = uncovered_count(points, cams, occluders, ids)
    cur_a = sum(1 for p in pts if not visible_cameras(cams, occluders, *p, ids=ids)) * st * st
    return {"camera_id": camera_id, "current_uncovered_ticks": cur_t, "current_uncovered_area_m2": round(cur_a, 1), "top": rows[:3]}


def walk_polyline(poly, step=0.2):
    out = []
    for a, b in zip(poly, poly[1:]):
        n = max(1, int(math.dist(a, b) / step))
        out += [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n)]
    out.append(tuple(poly[-1]))
    return out


def route_profile(poly, cams, occluders, ids, step=0.2, near_m=14.0):
    """Where along a polyline the coverage class changes: 'near' (a graph camera within near_m), 'far' (only farther
    cameras), 'blind' (none). Used to see where a scripted hide starts (the hard point, graph reading)."""
    rows, prev = [], None
    for p in walk_polyline(poly, step):
        vis = visible_cameras(cams, occluders, *p, ids=ids)
        dists = {c: math.dist(p, cams[c].pos[:2]) for c in vis}
        cls = "blind" if not vis else ("near" if min(dists.values()) <= near_m else "far")
        if cls != prev:
            rows.append({"xy": [round(p[0], 1), round(p[1], 1)], "class": cls, "cameras": sorted(vis),
                         "nearest_m": round(min(dists.values()), 1) if dists else None})
            prev = cls
    return rows


def option_table(cams, occluders, ids, all_pts, pre_pts, options, region=YARD):
    """options: name -> (cameras dict to use, extra Camera list). Uniform metrics for every counterfactual."""
    pts, st = grid(region, 0.5)
    rows = {}
    for name, (use, extra) in options.items():
        area = sum(1 for p in pts if not visible_cameras(use, occluders, *p, ids=ids)
                   and not any(sees_floor_point(c, occluders, *p) for c in extra)) * st * st
        rows[name] = {
            "yard_uncovered_m2": round(area, 1),
            "ticks_uncovered": uncovered_count(all_pts, use, occluders, ids, extra),
            "ticks_uncovered_14m": uncovered_count(all_pts, use, occluders, ids, extra, max_dist=14.0),
            "pre_window_uncovered_14m": uncovered_count(pre_pts, use, occluders, ids, extra, max_dist=14.0),
        }
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--geometry", default="docs/evaluation/R004_SCENE_GEOMETRY_2D_V1.json")
    ap.add_argument("--evidence", required=True, help="far-target-619 LOCAL directory (reads <set>/<case>.a-log.json)")
    ap.add_argument("--set", default="after")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    cams, occ, _ = load_geometry(args.geometry)
    graph = set(GRAPH_V3_CAMERAS)
    report = {"graph_cameras": sorted(graph), "yard": YARD}
    per_cam = {}
    for cid, cam in cams.items():
        cov, st = coverage_map(cams, occ, [cid])
        per_cam[cid] = {"area_m2": round(sum(1 for v in cov.values() if v) * st * st, 1)}
    report["per_camera_yard_area_m2"] = per_cam
    cov_g, st = coverage_map(cams, occ, sorted(graph))
    cov_a, _ = coverage_map(cams, occ, sorted(graph | {"CAM_ENTRY"}))
    report["yard_uncovered_graph"] = uncovered_stats(cov_g, st)
    report["yard_uncovered_graph_plus_entry"] = uncovered_stats(cov_a, st)
    report["ascii_graph"] = ascii_map(cov_g, st)
    report["ascii_graph_plus_entry"] = ascii_map(cov_a, st)
    all_ticks = []
    cases = {}
    for c in HARD_CASES:
        p = Path(args.evidence) / args.set / f"{c}.a-log.json"
        ticks = load_ticks(p)
        all_ticks += ticks
        g = ticks_report(ticks, cams, occ, graph)
        g["segments_no_graph_cam_gt"] = gap_segments(ticks, lambda t: any(x in graph for x in t["gt_visible"]))
        g["segments_no_graph_cam_with_entry_gt"] = gap_segments(ticks, lambda t: any(x in graph or x == "CAM_ENTRY" for x in t["gt_visible"]))
        cases[c] = g
    report["cases"] = cases
    pts = [t["xy"] for t in all_ticks]
    report["best_added_camera"] = best_added_camera(cams, occ, graph, pts)
    best = report["best_added_camera"]["top"][0]
    new_cam = make_camera("NEW", tuple(best["pos"]), best["yaw_deg"], 20.0, 685.5, 685.5)
    entry = [cams["CAM_ENTRY"]]
    report["counterfactual_ticks_uncovered"] = {
        "total_ticks": len(pts),
        "graph_v3": uncovered_count(pts, cams, occ, graph),
        "graph_v3_plus_entry": uncovered_count(pts, cams, occ, graph, entry),
        "graph_v3_plus_best_new": uncovered_count(pts, cams, occ, graph, [new_cam]),
        "graph_v3_plus_entry_and_best_new": uncovered_count(pts, cams, occ, graph, entry + [new_cam]),
    }
    report["counterfactual_by_case"] = {
        c: {"ticks": len(ts), "graph_v3": uncovered_count([t["xy"] for t in ts], cams, occ, graph),
            "plus_entry": uncovered_count([t["xy"] for t in ts], cams, occ, graph, entry),
            "plus_best_new": uncovered_count([t["xy"] for t in ts], cams, occ, graph, [new_cam]),
            "plus_both": uncovered_count([t["xy"] for t in ts], cams, occ, graph, entry + [new_cam])}
        for c, ts in ((c, load_ticks(Path(args.evidence) / args.set / f"{c}.a-log.json")) for c in HARD_CASES)}
    hp = hard_points_from_check(Path(args.evidence) / args.set / "hardset_check.json")
    pre = {}
    pre_pts = []
    for c in HARD_CASES:
        if c not in hp:
            continue
        ts = load_ticks(Path(args.evidence) / args.set / f"{c}.a-log.json")
        w = pre_window_points(ts, hp[c]["t"])
        pre_pts += [t["xy"] for t in w]
        pre[c] = {"hard_point_t": round(hp[c]["t"], 1), "last_cams_gt": hp[c]["last_cams"], "last_xy": [round(v, 1) for v in hp[c]["last_xy"]],
                  "window_ticks": len(w),
                  "model_cams_by_tick": [visible_cameras(cams, occ, *t["xy"], ids=graph) for t in w],
                  "nearest_graph_cam_m_by_tick": [round(min([math.hypot(t["xy"][0] - cams[i].pos[0], t["xy"][1] - cams[i].pos[1])
                                                           for i in visible_cameras(cams, occ, *t["xy"], ids=graph)] or [-1]), 1) for t in w]}
    report["pre_window_3s"] = pre
    report["pre_window_points"] = len(pre_pts)
    report["pre_window_uncovered_14m"] = {
        "graph_v3": uncovered_count(pre_pts, cams, occ, graph, max_dist=14.0),
        "plus_entry": uncovered_count(pre_pts, cams, occ, graph, entry, max_dist=14.0),
        "plus_best_new": uncovered_count(pre_pts, cams, occ, graph, [new_cam], max_dist=14.0),
        "plus_both": uncovered_count(pre_pts, cams, occ, graph, entry + [new_cam], max_dist=14.0)}
    report["pre_window_best_added_camera"] = best_added_camera(cams, occ, graph, pre_pts, max_dist=14.0)
    report["all_ticks_uncovered_14m"] = {
        "graph_v3": uncovered_count(pts, cams, occ, graph, max_dist=14.0),
        "plus_entry": uncovered_count(pts, cams, occ, graph, entry, max_dist=14.0),
        "plus_best_new": uncovered_count(pts, cams, occ, graph, [new_cam], max_dist=14.0)}
    routes = {
        "H1-1 as scripted": [(-10, -0.4), (-13, -1), (-13, 3), (-12.75, 6), (-10.5, 7.8), (-9, 7.8)],
        "H1-2 as scripted (reverse)": [(-10, -0.4), (-9, 7.8), (-10.5, 7.8), (-12.75, 6), (-13, 3), (-13, -1)],
    }
    report["route_profiles"] = {k: route_profile(v, cams, occ, graph) for k, v in routes.items()}
    ext_car = cams["CAM_EXT_CAR"]
    reaim_car = reaim_search(cams, occ, graph, "CAM_EXT_CAR", pts)["top"][0]
    reaimed = dict(cams, CAM_EXT_CAR=make_camera("CAM_EXT_CAR", ext_car.pos, reaim_car["yaw_deg"], reaim_car["pitch_deg"], ext_car.fx, ext_car.fy))
    area_best = report["best_added_camera"]["top"][0]  # tick-best
    pre_best = report["pre_window_best_added_camera"]["top"][0]  # pre-window/area-best
    cam_t = make_camera("NEW_T", tuple(area_best["pos"]), area_best["yaw_deg"], 20.0, 685.5, 685.5)
    cam_p = make_camera("NEW_P", tuple(pre_best["pos"]), pre_best["yaw_deg"], 20.0, 685.5, 685.5)
    report["option_table"] = option_table(cams, occ, graph, pts, pre_pts, {
        "baseline graph v3": (cams, []),
        "a: add CAM_ENTRY": (cams, entry),
        "c1: new camera, tick-best": (cams, [cam_t]),
        "c2: new camera, area-best": (cams, [cam_p]),
        "c3: re-aim CAM_EXT_CAR": (reaimed, []),
        "a+c2": (cams, entry + [cam_p]),
    })
    report["option_cameras"] = {"c1": area_best, "c2": pre_best, "c3_reaim_ext_car": reaim_car}
    G = graph
    split = {"yard_x_lt_-3.2": 0, "indoor": 0}
    split_after_c2 = {"yard_x_lt_-3.2": 0, "indoor": 0}
    for t in all_ticks:
        if not visible_cameras(cams, occ, *t["xy"], ids=G):
            split["yard_x_lt_-3.2" if t["xy"][0] < -3.2 else "indoor"] += 1
            if not sees_floor_point(cam_p, occ, *t["xy"]):
                split_after_c2["yard_x_lt_-3.2" if t["xy"][0] < -3.2 else "indoor"] += 1
    report["uncovered_ticks_by_region"] = {"baseline": split, "after_c2": split_after_c2}
    report["reaim"] = {cid: reaim_search(cams, occ, graph, cid, pts) for cid in ("CAM_EXT_CLEAR", "CAM_EXT_CAR")}
    sets = {}
    for name in ("before", "after", "before_rep", "after_rep"):
        per = {}
        for c in HARD_CASES:
            p = Path(args.evidence) / name / f"{c}.a-log.json"
            if p.exists():
                tk = load_ticks(p)
                per[c] = [len(tk), sum(1 for t in tk if not any(x in graph for x in t["gt_visible"]))]
        sets[name] = per
    report["no_graph_cam_ticks_by_set"] = sets
    Path(args.out).write_text(json.dumps(report, indent=1, default=list))
    return report


if __name__ == "__main__":
    main()
