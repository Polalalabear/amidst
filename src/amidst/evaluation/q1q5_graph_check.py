"""Read-only, source-pinned r004 engineering pre-review. Never grants authority.

Only static calibration, static RGB, and declared mesh/graph inputs are read.
No renderer, actor state, event scripts, model inference, or GT dependency.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import struct
import zlib
from html import escape
from pathlib import Path


class GraphCheckError(ValueError):
    pass


def canonical_hash(value, *, exclude=()):
    if exclude:
        value = {k: v for k, v in value.items() if k not in exclude}
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    ).hexdigest()


def strict_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise GraphCheckError("Duplicate JSON key")
            result[key] = value
        return result

    def bad(_):
        raise GraphCheckError("Non-finite JSON")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad)
    except (UnicodeError, ValueError) as exc:
        raise GraphCheckError("Invalid JSON input") from exc


def read_pinned(ref):
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise GraphCheckError("Explicit file locator and independent SHA required")
    if not isinstance(ref["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]):
        raise GraphCheckError("Invalid SHA-256")
    path = Path(ref["path"])
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise GraphCheckError("Input must be a bounded regular file")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise GraphCheckError("Input file pin mismatch")
    return raw


def png_info(raw):
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise GraphCheckError("Static frame is not PNG")
    pos = 8
    chunks = []
    width = height = None
    idat = bytearray()
    mode = None
    while pos < len(raw):
        if pos + 12 > len(raw):
            raise GraphCheckError("Truncated PNG")
        size = struct.unpack(">I", raw[pos : pos + 4])[0]
        kind = raw[pos + 4 : pos + 8]
        end = pos + 12 + size
        if end > len(raw):
            raise GraphCheckError("Truncated PNG chunk")
        body = raw[pos + 8 : pos + 8 + size]
        crc = struct.unpack(">I", raw[pos + 8 + size : end])[0]
        if zlib.crc32(kind + body) & 0xFFFFFFFF != crc:
            raise GraphCheckError("Invalid PNG CRC")
        if not chunks and kind != b"IHDR":
            raise GraphCheckError("PNG must start with IHDR")
        if kind == b"IHDR":
            if chunks or size != 13:
                raise GraphCheckError("Invalid PNG IHDR")
            width, height, depth, color, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", body
            )
            if (
                not 0 < width <= 4096
                or not 0 < height <= 4096
                or depth != 8
                or color not in {0, 2, 4, 6}
                or (compression, filtering, interlace) != (0, 0, 0)
            ):
                raise GraphCheckError("Unsupported/bounded PNG mode")
            mode = {0: 1, 2: 3, 4: 2, 6: 4}[color]
        if kind == b"IDAT":
            idat.extend(body)
        chunks.append(kind.decode("ascii"))
        pos = end
        if kind == b"IEND":
            if size or pos != len(raw):
                raise GraphCheckError("PNG trailing data")
            break
    if not chunks or chunks[-1] != "IEND" or not idat or not width or not height:
        raise GraphCheckError("Incomplete PNG")
    expected = height * (1 + width * mode)
    if expected > 64 * 1024 * 1024:
        raise GraphCheckError("Decoded PNG exceeds limit")
    try:
        decoder = zlib.decompressobj()
        decoded = decoder.decompress(bytes(idat), expected + 1)
    except zlib.error as exc:
        raise GraphCheckError("Invalid PNG compression") from exc
    if (
        len(decoded) != expected
        or not decoder.eof
        or decoder.unused_data
        or decoder.unconsumed_tail
        or any(decoded[i] > 4 for i in range(0, expected, width * mode + 1))
    ):
        raise GraphCheckError("Invalid PNG scanlines")
    return {
        "width": width,
        "height": height,
        "idat_sha256": hashlib.sha256(idat).hexdigest(),
        "metadata_chunks": sorted(set(chunks) & {"tEXt", "zTXt", "iTXt", "eXIf"}),
    }


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _unique(rows, field):
    result = {}
    for row in rows:
        key = row[field]
        if not isinstance(key, str) or not key or key in result:
            raise GraphCheckError("Missing/duplicate " + field)
        result[key] = row
    return result


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on(a, b, p):
    return abs(_cross(a, b, p)) < 1e-9 and all(
        min(a[i], b[i]) <= p[i] <= max(a[i], b[i]) for i in (0, 1)
    )


def _intersects(a, b, c, d):
    x, y, u, v = _cross(a, b, c), _cross(a, b, d), _cross(c, d, a), _cross(c, d, b)
    return (x * y < 0 and u * v < 0) or any(
        (_on(a, b, c), _on(a, b, d), _on(c, d, a), _on(c, d, b))
    )


def polygon_area(points, width, height):
    if not isinstance(points, list) or len(points) < 3:
        raise GraphCheckError("Exit polygon needs at least three vertices")
    if any(
        not isinstance(p, list)
        or len(p) != 2
        or not all(_finite(v) for v in p)
        or not 0 <= p[0] < width
        or not 0 <= p[1] < height
        for p in points
    ):
        raise GraphCheckError("Exit polygon outside source image")
    if len({tuple(p) for p in points}) != len(points):
        raise GraphCheckError("Repeated exit vertex")
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if _intersects(points[i], points[(i + 1) % n], points[j], points[(j + 1) % n]):
                raise GraphCheckError("Self-intersecting exit polygon")
    area = (
        abs(
            sum(
                points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1]
                for i in range(n)
            )
        )
        / 2
    )
    if area <= 1e-9:
        raise GraphCheckError("Degenerate exit polygon")
    return area


def plane_projection(calibration, points):
    """Diagnostic z=0 ray intersection; not an occlusion/visibility test."""
    matrix = calibration["camera_to_world"]
    center = [matrix[i][3] for i in range(3)]
    result = []
    for u, v in points:
        ray = [
            (u - calibration["cx"]) / calibration["fx"],
            -(v - calibration["cy"]) / calibration["fy"],
            -1,
        ]
        direction = [sum(matrix[i][j] * ray[j] for j in range(3)) for i in range(3)]
        t = -center[2] / direction[2] if abs(direction[2]) > 1e-12 else -1
        result.append([round(center[i] + t * direction[i], 6) for i in range(3)] if t > 0 else None)
    return result


def _calibration_check(c):
    if (
        c.get("camera_model") != "PINHOLE"
        or c.get("convention") != "BLENDER_NEG_Z_UP_Y"
        or c.get("pixel_origin") != "TOP_LEFT_CONTINUOUS"
        or c.get("meters_per_unit") != 1
        or c.get("distortion") is not None
    ):
        raise GraphCheckError("Unsupported calibration convention/units")
    if any(type(c.get(k)) is not int or not 0 < c[k] <= 4096 for k in ("width", "height")):
        raise GraphCheckError("Invalid image dimensions")
    if any(not _finite(c.get(k)) for k in ("fx", "fy", "cx", "cy")) or min(c["fx"], c["fy"]) <= 0:
        raise GraphCheckError("Invalid intrinsics")
    m = c["camera_to_world"]
    if (
        not isinstance(m, list)
        or len(m) != 4
        or any(not isinstance(r, list) or len(r) != 4 or not all(_finite(x) for x in r) for r in m)
        or m[3] != [0, 0, 0, 1]
    ):
        raise GraphCheckError("Invalid camera transform")
    error = max(
        abs(sum(m[k][i] * m[k][j] for k in range(3)) - (i == j)) for i in range(3) for j in range(3)
    )
    det = (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )
    if error > 1e-5 or abs(det - 1) > 1e-5:
        raise GraphCheckError("Camera rotation is not orthonormal/right-handed")
    if canonical_hash(c, exclude=("calibration_sha256",)) != c["calibration_sha256"]:
        raise GraphCheckError("Calibration content pin mismatch")
    return error


def render_static_map(config_path, config_sha256):
    """Actual mesh-piece XY projection plus camera centers; never a visibility map."""
    config = strict_json(read_pinned({"path": str(config_path), "sha256": config_sha256}))
    check_graphs(config_path, config_sha256)
    meshes = strict_json(read_pinned(config["files"]["region_meshes"]))["meshes"]
    cameras = strict_json(read_pinned(config["files"]["camera_catalog"]))["cameras"]
    vertices = [v for m in meshes.values() for v in m["vertices_world_m"]]
    if not vertices or not cameras:
        raise GraphCheckError("Map requires source mesh vertices and cameras")
    left, right = min(v[0] for v in vertices), max(v[0] for v in vertices)
    bottom, top = min(v[1] for v in vertices), max(v[1] for v in vertices)
    scale = min(850 / max(right - left, 1), 570 / max(top - bottom, 1))

    def xy(v):
        return 35 + (v[0] - left) * scale, 90 + (top - v[1]) * scale

    parts = [
        (
            '<svg xmlns="http://www.w3.org/'
            '2000/svg" viewBox="0 0 1220 76'
            '0" role="img" aria-labelledby='
            '"title desc">'
        ),
        '<title id="title">r004 靜態區域與鏡頭位置提案</title>',
        (
            '<desc id="desc">區域使用來源mesh各片面的'
            "XY投影，保留片段與缺口。未驗可見性、物理通行或鏡頭重疊。<"
            "/desc>"
        ),
        '<rect width="1220" height="760" fill="#f8fafc"/>',
        (
            '<g font-family="sans-serif" fi'
            'll="#172033"><text x="24" y="3'
            '0" font-size="22">r004 STATIC '
            "PROPOSAL — NOT APPROVED</text>"
        ),
        (
            '<text x="24" y="55" font-size='
            '"14">Mesh pieces in world XY; '
            "arrows = optical direction, NO"
            "T field of view / visibility</"
            "text>"
        ),
    ]
    colors = ["#c6e5e0", "#f8d5a3", "#c9d8f4", "#dfc9eb", "#d5e4ba", "#f4c9cd", "#d6d9df"]
    for n, (rid, mesh) in enumerate(sorted(meshes.items())):
        vs = mesh["vertices_world_m"]
        for face in mesh["triangles_or_polygons"]:
            points = [vs[i] for i in face]
            area = (
                abs(
                    sum(
                        points[i][0] * points[(i + 1) % len(points)][1]
                        - points[(i + 1) % len(points)][0] * points[i][1]
                        for i in range(len(points))
                    )
                )
                / 2
            )
            if area < 1e-8:
                continue
            coords = " ".join(f"{x:.2f},{y:.2f}" for x, y in map(xy, points))
            parts.append(
                f'<polygon points="{coords}" fill="{colors[n % len(colors)]}" '
                'fill-opacity="0.7" stroke="#718096" stroke-width="0.7"/>'
            )
        label = xy([sum(v[i] for v in vs) / len(vs) for i in (0, 1)])
        parts.append(
            f'<text x="{label[0]:.2f}" y="{label[1]:.2f}" font-size="12">{escape(rid)}</text>'
        )
    for n, c in enumerate(sorted(cameras, key=lambda c: c["camera_id"]), 1):
        m = c["camera_to_world"]
        world = [m[i][3] for i in range(3)]
        x, y = xy(world)
        dx, dy = -m[0][2], -m[1][2]
        length = math.hypot(dx, dy)
        tx, ty = xy([world[0] + dx / max(length, 1e-9), world[1] + dy / max(length, 1e-9)])
        parts.append(
            f'<path d="M{x:.2f},{y:.2f} L{tx:.2f},{ty:.2f}" '
            'fill="none" stroke="#b13b16" stroke-width="2"/>'
        )
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="#b13b16"/>'
            f'<text x="{x + 8:.2f}" y="{y - 8:.2f}" font-size="13">C{n}</text>'
        )
        line = f"C{n}: {c['camera_id']}  ({world[0]:.2f}, {world[1]:.2f}, {world[2]:.2f}) m"
        parts.append(f'<text x="895" y="{105 + n * 30}" font-size="12">{escape(line)}</text>')
    parts += [
        (
            '<text x="24" y="714" font-size'
            '="14">PROPOSED only. No actor '
            "routes, detections, GT, portal"
            " width, overlap ratio, or coll"
            "ision authority.</text>"
        ),
        (
            '<text x="24" y="740" font-size'
            '="14">來源：已pin靜態mesh與相機校正；沒有把AA'
            "BB當地板，沒有補洞。</text>"
        ),
        "</g></svg>",
    ]
    return "\n".join(parts) + "\n"


def check_graphs(config_path, config_sha256):
    config = strict_json(read_pinned({"path": str(config_path), "sha256": config_sha256}))
    if config.get("schema_version") != "q-demo.r004-prereview-inputs.v1":
        raise GraphCheckError("Explicit pre-review input schema required")
    required = {
        "region_graph",
        "camera_graph",
        "roi_mapping",
        "region_meshes",
        "static_geometry",
        "camera_catalog",
    }
    if not required <= config.get("files", {}).keys():
        raise GraphCheckError("Missing static input role")
    inputs = {k: strict_json(read_pinned(config["files"][k])) for k in sorted(required)}
    try:
        return _check(config, inputs, config_sha256)
    except GraphCheckError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        raise GraphCheckError("Malformed static graph input") from exc


def _check(config, data, config_sha256):
    r, c, roi, meshes, static, catalog = (
        data[k]
        for k in [
            "region_graph",
            "camera_graph",
            "roi_mapping",
            "region_meshes",
            "static_geometry",
            "camera_catalog",
        ]
    )
    checks = []

    def check(key, ok, scope, detail):
        if not ok:
            raise GraphCheckError(key + ": " + detail)
        checks.append({"id": key, "status": "PASS", "scope": scope, "details": detail})

    check(
        "GRAPH_SCHEMAS",
        r.get("schema_version") == "q-demo.region-graph.v1"
        and c.get("schema_version") == "q-demo.camera-transition-graph.v1",
        "graphs",
        "Supported graph schemas only",
    )
    check(
        "PROPOSAL_ONLY",
        all(g.get("approval_status") == "DRAFT" and g.get("approval_ref") is None for g in (r, c))
        and static.get("approval_status") == "DRAFT"
        and static.get("allowed_purposes") == [],
        "authority",
        (
            "Proposal-only checker rejects "
            "any approval promotion; extern"
            "al gates require their own rev"
            "iew"
        ),
    )
    check(
        "REGION_HASH",
        canonical_hash(r, exclude=("graph_id", "content_sha256", "stats")) == r["content_sha256"],
        "region_graph",
        "Canonical region content hash",
    )
    check(
        "CAMERA_HASH",
        canonical_hash(c, exclude=("graph_id", "content_sha256", "stats")) == c["content_sha256"],
        "camera_graph",
        "Canonical camera content hash",
    )
    check(
        "STATIC_PIN",
        r["scene_static_sha256"]
        == roi["scene_static_sha256"]
        == meshes["source_static_sha256"]
        == config["files"]["static_geometry"]["sha256"],
        "static",
        "Independent static file binding",
    )
    check(
        "CATALOG_PIN",
        c["camera_catalog_sha256"]
        == roi["camera_catalog_sha256"]
        == config["files"]["camera_catalog"]["sha256"],
        "cameras",
        "Camera catalog bytes binding",
    )
    check(
        "GRAPH_BINDING",
        c["region_graph_sha256"] == r["content_sha256"],
        "camera_graph",
        "Region graph content pin",
    )
    check(
        "SOURCE_BINDING",
        static["source_sha256"] == roi["source_sha256"],
        "static",
        "Same immutable source revision",
    )
    check(
        "SCENE_REVISION",
        r["scene_revision"] == c["scene_revision"] == static["scene_revision"] == "r004",
        "static",
        "r004 only, no r003 substitution",
    )
    check(
        "SCENE_ID",
        isinstance(r.get("scene_id"), str)
        and bool(r["scene_id"])
        and r["scene_id"] == c.get("scene_id"),
        "graphs",
        "Graphs refer to the same declared scene",
    )
    expected_inputs = {
        "static:r004:proposal": config["files"]["static_geometry"]["sha256"],
        "calibration:r004:catalog": config["files"]["camera_catalog"]["sha256"],
    }
    for graph, prefix, extra in [
        (r, "rgraph", {}),
        (
            c,
            "cgraph",
            {
                "static-image:r004:" + cid: ref["sha256"]
                for cid, ref in config["static_frames"].items()
            },
        ),
    ]:
        refs = _unique(graph["inputs"], "ref")
        check(
            "INPUT_DECLARATIONS:" + prefix,
            {k: v["sha256"] for k, v in refs.items()} == {**expected_inputs, **extra},
            prefix,
            "Every declared input pin agrees with the independent file manifest",
        )
        check(
            "GRAPH_ID:" + prefix,
            graph["graph_id"] == prefix + ":r004:static:" + graph["content_sha256"][:16],
            prefix,
            "Graph identifier derives from content hash",
        )
    regions = _unique(r["regions"], "region_id")
    edges = _unique(r["edges"], "edge_id")
    cameras = _unique(c["cameras"], "camera_id")
    calibration = _unique(catalog["cameras"], "camera_id")
    mappings = _unique(roi["entries"], "camera_id")
    objects = _unique(static["objects"], "object_ref")
    transitions = _unique(c["transitions"], "transition_id")
    check(
        "CAMERA_SET",
        set(cameras)
        == set(calibration)
        == set(mappings)
        == set(config["static_frames"])
        == set(config["overlay_frames"]),
        "cameras",
        "Exact static-frame/calibration/ROI camera scope",
    )
    for rid, region in regions.items():
        mesh = meshes["meshes"][rid]
        check(
            "MESH_PIN:" + rid,
            canonical_hash(mesh) == region["polygon_sha256"]
            and mesh == objects[mesh["object_ref"]],
            rid,
            "Copied mesh matches original vertices/faces",
        )
        vertices = mesh["vertices_world_m"]
        check(
            "MESH_FINITE:" + rid,
            bool(vertices)
            and all(len(v) == 3 and all(_finite(x) for x in v) for v in vertices)
            and all(
                len(face) >= 3 and all(type(i) is int and 0 <= i < len(vertices) for i in face)
                for face in mesh["triangles_or_polygons"]
            ),
            rid,
            "Finite vertices and valid polygon indices; no AABB replacement",
        )
    for eid, edge in edges.items():
        check(
            "EDGE_REFS:" + eid,
            len(edge["regions"]) == 2
            and len(set(edge["regions"])) == 2
            and set(edge["regions"]) <= regions.keys(),
            eid,
            "Distinct declared endpoint regions",
        )
        check(
            "EDGE_STATE:" + eid,
            edge["state"] in {"OPEN", "CLOSED", "UNKNOWN"}
            and edge["traversability"] in {"TOPOLOGICAL_ONLY", "APPROVED_WALKABLE"}
            and edge["direction"] in {"BIDIRECTIONAL", "ONE_WAY"}
            and (
                edge["direction"] != "ONE_WAY"
                or (
                    edge["from"] in edge["regions"]
                    and edge["to"] in edge["regions"]
                    and edge["from"] != edge["to"]
                )
            ),
            eid,
            "Known state/authority and valid direction",
        )
    diagnostics = []
    for cid in sorted(cameras):
        cam, cal, mapping = cameras[cid], calibration[cid], mappings[cid]
        error = _calibration_check(cal)
        frame = png_info(read_pinned(config["static_frames"][cid]))
        overlay = png_info(read_pinned(config["overlay_frames"][cid]))
        check(
            "CALIBRATION:" + cid,
            cam["calibration_sha256"] == mapping["calibration_sha256"] == cal["calibration_sha256"]
            and cal["static_validity"]["source_sha256"] == static["source_sha256"],
            cid,
            "Calibration canonical hash, rotation and source binding",
        )
        check(
            "FRAME_SIZE:" + cid,
            [frame["width"], frame["height"]]
            == [cal["width"], cal["height"]]
            == [overlay["width"], overlay["height"]],
            cid,
            "Source and annotation dimensions agree",
        )
        check(
            "EXIT_REQUIRED:" + cid,
            bool(cam["exit_zones"]),
            cid,
            "Every camera declares at least one exit",
        )
        zone_ids = _unique(cam["exit_zones"], "exit_zone_id")
        for zid, zone in zone_ids.items():
            area = polygon_area(zone["roi_polygon_px"], cal["width"], cal["height"])
            check(
                "ROI_PIN:" + zid,
                mapping["exit_zone"] == zone
                and canonical_hash(zone) == mapping["roi_content_sha256"]
                and zone["static_frame_sha256"]
                == mapping["static_frame_sha256"]
                == config["static_frames"][cid]["sha256"],
                cid,
                "Polygon is simple/in-bounds/nondegenerate and bound to original source PNG",
            )
            check(
                "EXIT_EDGE_REFS:" + zid,
                bool(zone["leads_to_edge_ids"]) and set(zone["leads_to_edge_ids"]) <= edges.keys(),
                cid,
                "Exit points only to declared edges",
            )
            diagnostics.append(
                {
                    "camera_id": cid,
                    "exit_zone_id": zid,
                    "area_px2": area,
                    "calibration_sha256": cal["calibration_sha256"],
                    "static_frame_sha256": zone["static_frame_sha256"],
                    "rotation_max_error": error,
                    "hfov_deg": round(
                        math.degrees(2 * math.atan(cal["width"] / (2 * cal["fx"]))), 6
                    ),
                    "roi_z0_diagnostic_world_m": plane_projection(cal, zone["roi_polygon_px"]),
                    ("projection_limits"): (
                        "z=0 ray intersection only; no occlusion or walkability proof"
                    ),
                    "source_metadata_chunks": frame["metadata_chunks"],
                    "export_metadata_sanitization_required": bool(frame["metadata_chunks"]),
                }
            )
    pairs = set()
    for tid, t in transitions.items():
        a, b = t["from_camera_id"], t["to_camera_id"]
        check(
            "TRANSITION_CAMERA:" + tid,
            a in cameras and b in cameras and a != b and (a, b) not in pairs,
            tid,
            "Unique directed camera pair",
        )
        pairs.add((a, b))
        path = t["region_path"]
        check(
            "TRANSITION_PATH:" + tid,
            bool(path)
            and len(path) == len(t["edge_path"]) + 1
            and t["region_hops"] == len(t["edge_path"])
            and set(path) <= regions.keys(),
            tid,
            "Region/edge/hop shape",
        )
        for i, eid in enumerate(t["edge_path"]):
            check(
                "PATH_EDGE:" + tid + ":" + str(i),
                eid in edges and set(edges[eid]["regions"]) == set(path[i : i + 2]),
                tid,
                "Path edge joins its consecutive regions",
            )
            edge = edges[eid]
            check(
                "PATH_DIRECTION:" + tid + ":" + str(i),
                edge["state"] != "CLOSED"
                and (
                    edge["direction"] != "ONE_WAY"
                    or (edge["from"], edge["to"]) == tuple(path[i : i + 2])
                ),
                tid,
                "Path respects state and direction",
            )
        exits = {z["exit_zone_id"]: z for z in cameras[a]["exit_zones"]}
        entries = {z["entry_zone_id"] for z in cameras[b]["entry_zones"]}
        check(
            "TRANSITION_ZONES:" + tid,
            bool(t["via_exit_zone_ids"])
            and set(t["via_exit_zone_ids"]) <= exits.keys()
            and set(t["to_entry_zone_ids"]) <= entries,
            tid,
            "Source exit and destination entry refs belong to correct cameras",
        )
        walks = [edges[eid] for eid in t["edge_path"]]
        weakest = (
            "TOPOLOGICAL_ONLY"
            if any(e["traversability"] == "TOPOLOGICAL_ONLY" for e in walks)
            else "APPROVED_WALKABLE"
        )
        check(
            "PATH_AUTHORITY:" + tid,
            t["path_traversability"] == weakest
            and type(t["path_has_unknown_state"]) is bool
            and t["path_has_unknown_state"] == any(e["state"] == "UNKNOWN" for e in walks)
            and t["relation"] in {"UNKNOWN", "OVERLAP", "BLIND_GAP"},
            tid,
            "Transition authority/state equals its actual edge path",
        )
        check(
            "PATH_EXIT:" + tid,
            not t["edge_path"]
            or t["edge_path"][0]
            in {eid for zid in t["via_exit_zone_ids"] for eid in exits[zid]["leads_to_edge_ids"]},
            tid,
            "Path follows declared source exit",
        )
    source_authorized = graphs_authorized = False
    promoted = any(e["traversability"] != "TOPOLOGICAL_ONLY" for e in edges.values())
    check(
        "NO_UNSUPPORTED_PROMOTION",
        not promoted or (source_authorized and graphs_authorized),
        "authority",
        "No walkability promotion without source and graph approval evidence",
    )
    # This engineering tool never establishes an approval receipt or runtime eligibility.
    legal = 0
    indegree = {cid: sum(b == cid for a, b in pairs) for cid in sorted(cameras)}
    no_reverse = sorted([list(pair) for pair in pairs if (pair[1], pair[0]) not in pairs])
    portals = [
        e["via"]["ref"]
        for e in edges.values()
        if e["via"]["kind"] == "PORTAL" and e["via"]["ref"] not in objects
    ]
    suspect = sorted(
        o["object_ref"]
        for o in objects.values()
        if o["object_ref"].startswith("WALL_")
        and any(v[2] < -1e-5 for v in o.get("vertices_world_m", []))
    )
    unresolved = []

    def gap(key, scope, summary, refs=(), severity="REVIEW_REQUIRED"):
        unresolved.append(
            {
                "id": key,
                "severity": severity,
                "scope": scope,
                "summary": summary,
                "evidence_refs": list(refs),
            }
        )

    if not source_authorized or not graphs_authorized or not legal:
        gap(
            "G4_AND_PURPOSE_PENDING",
            "all",
            "目前來源用途／圖權限未核定，沒有合法自動切鏡路徑；一般T/F不能授權通行。",
            severity="BLOCKING",
        )
    missing_entries = sorted(cid for cid, cam in cameras.items() if not cam["entry_zones"])
    if missing_entries:
        gap(
            "ENTRY_ROIS_MISSING",
            ",".join(missing_entries),
            "這些鏡頭未定義入口區域；接回入口與反向用途需補靜態證據。",
            severity="BLOCKING",
        )
    if no_reverse:
        gap(
            "REVERSE_SCOPE_INCOMPLETE",
            "camera_graph",
            "存在未配對的反向鏡頭轉移；目前不能聲稱完整雙向候選覆蓋。",
            [a + " -> " + b for a, b in no_reverse],
        )
    for cid, degree in indegree.items():
        if not degree:
            gap(
                "NO_INCOMING:" + cid,
                cid,
                "此鏡頭沒有任何入向轉移，現圖無法支援追入此鏡頭。",
                severity="BLOCKING",
            )
    if any(
        t["relation"] == "UNKNOWN"
        or t["ranking_area_m2"] is None
        or t["nominal_path_length_m"] is None
        for t in transitions.values()
    ):
        gap(
            "COVERAGE_AND_DISTANCE_UNKNOWN",
            "camera_graph",
            "重疊比例、完整可見範圍與路徑距離未量測，不能據此估可靠接回期限。",
        )
    if portals:
        gap(
            "PORTAL_GEOMETRY_NOT_BOUND",
            "region_graph",
            "圖上的portal名稱未綁定可核對的開口尺寸幾何；不是證明場景沒有門。",
            portals,
            "BLOCKING",
        )
    if suspect:
        gap(
            "SOURCE_MEMBERSHIP_UNRESOLVED",
            "static_geometry",
            "部分WALL物件含負Z頂點，safe_static未附有效／隱藏／集合來源。不能逕當碰撞遮擋元件，亦未證明transform錯誤。",
            suspect,
            "BLOCKING",
        )
    for cid, message in {
        "CAM_ENTRY": "出口ROI位於門外前景接近區，門檻未完整可見；須確認是否適合作為出口接近區。",
        "CAM_EXT_CAR": "出口ROI緊鄰車體遮擋，人物腳點能否觸發未驗證。",
        "CAM_W1": "平面診斷顯示ROI偏向提前接近區，不能視為已量測的跨界線。",
        "CAM_W2": "遠端ROI跨很長深度，過早或不穩定觸發風險需看圖確認。",
    }.items():
        if cid in cameras:
            gap("EXIT_SEMANTICS:" + cid, cid, message, [cid + ":EXIT_PROPOSED"])
    if "R102" in regions:
        gap(
            "R102_RESTRICTION_PRESERVED",
            "R102",
            "R102限制維持TOPOLOGICAL_ONLY，不可在本次審查順便解除。",
        )
    result = {
        "schema_version": "q-demo.r004-prereview-check.v1",
        "status": "REVIEW_REQUIRED",
        "gt_read": False,
        "evaluation_eligible": False,
        "checker_scope": "STATIC_ENGINEERING_ONLY",
        "config_sha256": config_sha256,
        "source_heads": config.get("source_heads", {}),
        "source_pins": {k: config["files"][k]["sha256"] for k in sorted(data)},
        "counts": {
            "regions": len(regions),
            "edges": len(edges),
            "cameras": len(cameras),
            "exit_rois": len(diagnostics),
            "transitions": len(transitions),
            "legal_auto_switch_paths": legal,
            "missing_entry_cameras": len(missing_entries),
            "missing_reverse_transitions": len(no_reverse),
            "unbound_portal_refs": len(portals),
            "membership_unresolved_wall_objects": len(suspect),
            "engineering_checks_pass": len(checks),
            "engineering_checks_fail": 0,
        },
        "engineering_checks": checks,
        "unresolved": unresolved,
        "camera_diagnostics": diagnostics,
        "transition_diagnostics": {
            "incoming_counts": indegree,
            "missing_reverse_pairs": no_reverse,
        },
        "approval": {
            "independent_Claude_receipt": "NOT_ASSERTED",
            "G4": "NOT_ASSERTED",
            "new_HSV_G6": "NOT_ASSERTED",
        },
        "limits": [
            "No events, trajectories, visibility/depth, GT or model calls read.",
            (
                "Hash/structure checks do not e"
                "stablish physical traversal, v"
                "isibility, identity or human a"
                "pproval."
            ),
            (
                "Legal auto-switch count is con"
                "servatively zero: this checker"
                " cannot validate external appr"
                "oval receipts."
            ),
        ],
    }
    result["output_sha256"] = canonical_hash(result)
    return result
