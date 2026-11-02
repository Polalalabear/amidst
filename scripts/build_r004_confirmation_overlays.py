"""Build CQ-22's three blinded, static-only A/B/C confirmation sheets.

The output is review material, not a graph, a human answer, or authority.
Reads are limited to pinned graph/static documents and two sanitized stills.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import shutil
import struct
import zlib
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_PINS = {
    "build_plan_v3_1.json": "277d0e9376f8d0bcb055d11aac7e856a4ae50b541bf7519c719a998c2f1b3d51",
    "camera_graph_v3_1.json": "e250413a0d0a2aeb61bd98bb1763236b1e39127f919cee1ee3ca3bd906b78409",
    "region_graph_v3_1.json": "a2f737805cf5446c6ba01fa4bebfddd2186d040cbd94314cf573c082191b24e1",
    "static_patches_v3_1.json": "fb4141b5e50267982f0e566268e565a584b1bd9fe80a6bacbe895a45b8498547",
}
STILL_PINS = {
    "CAM_BRANCH": "bcef1c4d56ec65a3788335eb5fae1fabdb57fa93e7694ae38614e5a668b69fc6",
    "CAM_WIDE": "eb2e31bf0eb78696f84309b53d629e5f377756678016dae260e5d8ccb0b6b42b",
}
HELPER_PIN = "d0b601565ba02ae54a1169927643c2863da326281579d4cdfaca977071b955b9"
PORTALS_PIN = "72e8ebb844e4c78235bfff5451639fe9e8fa3e7ef8f9eed1596679891cd1e64f"
COLORS = ["#00d5ff", "#ff79d1", "#ffd45e"]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixed_file(root, name, expected):
    root = Path(root).absolute()
    path = root / name
    if root.resolve() != root or path.resolve() != path or not path.is_relative_to(root):
        raise ValueError("Canonical nonsymlink input required")
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError(f"Input pin mismatch: {name}")
    return raw


def png_pixels(raw):
    """Reject metadata and validate the curated PNG without altering pixels."""
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("PNG signature required")
    offset, chunks, idat = 8, [], []
    while offset < len(raw):
        n = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        payload = raw[offset + 8:offset + 8 + n]
        crc = raw[offset + 8 + n:offset + 12 + n]
        if len(crc) != 4 or zlib.crc32(kind + payload) & 0xffffffff != int.from_bytes(crc, "big"):
            raise ValueError("PNG CRC mismatch")
        if kind not in {b"IHDR", b"IDAT", b"IEND", b"sRGB", b"gAMA", b"cHRM", b"pHYs", b"oFFs"}:
            raise ValueError("Only sanitized static PNG chunks are allowed")
        if kind == b"IHDR":
            width, height = struct.unpack(">II", payload[:8])
            if (width, height) != (960, 540):
                raise ValueError("Pinned camera image size required")
        if kind == b"IDAT":
            idat.append(payload)
        chunks.append(kind.decode("ascii"))
        offset += 12 + n
    if offset != len(raw) or chunks[-1] != "IEND" or not idat:
        raise ValueError("Complete PNG required")
    return {"file_sha256": sha(raw), "idat_sha256": sha(b"".join(idat)), "chunks": chunks}


def ground_at_v(module, cal, x, v):
    """Intersect a calibrated image row with fixed x on the z=0 support plane."""
    matrix = cal["camera_to_world"]
    delta = [x - matrix[0][3], -matrix[1][3], -matrix[2][3]]
    local = [sum(matrix[i][j] * delta[i] for i in range(3)) for j in range(3)]
    ratio = (v - cal["cy"]) / cal["fy"]
    denominator = matrix[1][1] - ratio * matrix[1][2]
    if abs(denominator) < 1e-10:
        raise ValueError("No bounded ground intersection")
    y = (ratio * local[2] - local[1]) / denominator
    point = [x, y, 0.0]
    pixel = module.project(cal, point)
    if pixel is None or abs(pixel[1] - v) > 1e-7:
        raise ValueError("Ground projection mismatch")
    return point


def band(module, cal, support, triangles, x0, x1):
    points = [ground_at_v(module, cal, x, v)
              for x, v in [(x0, 518), (x1, 518), (x1, 536), (x0, 536)]]
    witnesses = points + [
        [(a[i] + b[i]) / 2 for i in range(3)]
        for a, b in zip(points, points[1:] + points[:1], strict=True)
    ] + [[sum(p[i] for p in points) / 4 for i in range(3)]]
    if not all(module.on_support(p, support) and module.static_witness(cal, p, triangles)
               for p in witnesses):
        raise ValueError("Boundary proposal lacks nine static support witnesses")
    return {"polygon_world_m": points, "roi_polygon_px": [module.project(cal, p) for p in points],
            "static_witness_count": 9, "status": "PROPOSED"}


def polygon(points, color, width=5, opacity=".18", dash=""):
    coords = " ".join(f"{x:.6f},{y:.6f}" for x, y in points)
    return (f'<polygon points="{coords}" fill="{color}" fill-opacity="{opacity}" '
            f'stroke="{color}" stroke-width="{width}" stroke-dasharray="{dash}"/>')


def sheet(question, camera, raw, candidates, reference_rois):
    uri = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 2110">',
             '<rect width="1000" height="2110" fill="#111827"/>',
             '<style>text{font-family:system-ui,-apple-system,"Noto Sans CJK TC",sans-serif;fill:#f8fafc}</style>',
             f'<title>{escape(question)}</title>',
             f'<text x="20" y="36" font-size="25">{escape(question)}</text>',
             f'<text x="20" y="72" font-size="18">{camera} · r004 · 無人物靜態畫面；位置待確認</text>',
             f'<defs><image id="still" href="{uri}" width="960" height="540"/></defs>']
    for i, row in enumerate(candidates):
        y = 130 + i * 640
        parts += [f'<text x="20" y="{y-20}" font-size="23">{chr(65+i)}　{escape(row["label"])}</text>',
                  f'<g transform="translate(20,{y})">', '<use href="#still"/>']
        for roi in reference_rois:
            parts.append(polygon(roi, "#d1d5db", 2, "0", "8,7"))
        parts += [polygon(row["roi_polygon_px"], COLORS[i]), '</g>']
    parts += ['<text x="20" y="2048" font-size="22">請選 A／B／C／都不是／看不出來；也可圈選補充。</text>',
              '<text x="20" y="2084" font-size="17">灰色虛線為 v3_1 已有區域；彩色為本題候選，尚未核定。</text>', '</svg>']
    return ("\n".join(parts) + "\n").encode("utf-8")


def build(args):
    output = Path(args.output).absolute()
    if output.resolve() != output or output.exists():
        raise ValueError("New canonical output directory required")
    if shutil.disk_usage(output.parent).free < 8 * 1024**3:
        raise ValueError("DISK_BELOW_8_GIB")
    graphs = {n: json.loads(fixed_file(args.graphs, n, pin)) for n, pin in GRAPH_PINS.items()}
    plan = graphs["build_plan_v3_1.json"]
    helper = ROOT / "src/amidst/evaluation/r004_review_v2.py"
    fixed_file(helper.parent, helper.name, HELPER_PIN)
    spec = importlib.util.spec_from_file_location("static_review", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    names = ["source_static_geometry", "static_membership", "region_meshes", "camera_catalog"]
    static = {n: json.loads(fixed_file(args.provenance, n + ".json", plan["static_source_pins"][n + ".json"]))
              for n in names}
    portals = json.loads(fixed_file(args.provenance, "portals.json", PORTALS_PIN))
    images = {c: fixed_file(args.static_images, c + ".png", pin) for c, pin in STILL_PINS.items()}
    image_receipts = {c: png_pixels(raw) for c, raw in images.items()}
    cals = {c["camera_id"]: c for c in static["camera_catalog"]["cameras"]}
    meshes = static["region_meshes"]["meshes"]
    scope = module.membership(static["source_static_geometry"], static["static_membership"])
    triangles = module.triangles_for(scope["render_enabled_objects"])
    patches = graphs["static_patches_v3_1.json"]
    original = patches["CAM_BRANCH:EXIT_V3:E_CORNER_N"]
    if not all(module.on_support(p, meshes["CORR_N"])
               and module.static_witness(cals["CAM_BRANCH"], p, triangles)
               for p in original["witness_world_m"]):
        raise ValueError("Pinned BRANCH patch static witnesses do not reproduce")
    extended = module.rectangle_patch(cals["CAM_BRANCH"], meshes["CORR_N"],
        [15, plan["branch_bounds"]["CORR_N"][1], plan["branch_bounds"]["CORR_N"][2], 3.75], triangles)
    # A 0.4 m marker at the pinned corridor center identifies the lower image
    # location. It does not claim the whole corridor width is visible there.
    center = (15 + plan["branch_bounds"]["CORR_N"][1]) / 2
    lower = band(module, cals["CAM_BRANCH"], meshes["CORR_N"], triangles, center - .2, center + .2)
    branch = [{**original, "label": "目前加深加寬的範圍"},
              {**extended, "label": "同寬，再向畫面下緣延伸"},
              {**lower, "label": "畫面下緣中央條帶（只指位置；v4 提案）"}]
    portal = next(p for p in portals if p["portal_id"] == "PORTAL_R102")
    door = [
        {"label": "左側斜窄開口（PORTAL_R102 候選）", "polygon_world_m": portal["opening_polygon_world_m"],
         "roi_polygon_px": [module.project(cals["CAM_WIDE"], p) for p in portal["opening_polygon_world_m"]],
         "basis": "PINNED_STATIC_PORTAL_PROJECTION", "status": "UNKNOWN"},
        {"label": "右側大開口", "roi_polygon_px": [[570,160],[958,84],[958,538],[723,355],[571,327]],
         "basis": "MANUAL_LOCATION_ON_PINNED_STATIC_IMAGE_ONLY", "status": "UNKNOWN"},
        {"label": "畫面遠端位置（若是其他處，請圈選）", "roi_polygon_px": [[410,164],[493,159],[493,269],[410,273]],
         "basis": "MANUAL_LOCATION_ON_PINNED_STATIC_IMAGE_ONLY", "status": "UNKNOWN"},
    ]
    x0, x1 = 15.01, plan["branch_bounds"]["CORR_N"][1] - .01
    sections = [band(module, cals["CAM_WIDE"], meshes["CORR_N"], triangles,
                     x0 + (x1-x0)*i/3, x0 + (x1-x0)*(i+1)/3) for i in range(3)]
    sections.sort(key=lambda r: sum(p[0] for p in r["roi_polygon_px"]) / 4)
    bottom = [{**r, "label": label} for r, label in zip(sections, ["畫面下緣左段", "畫面下緣中段", "畫面下緣右段"], strict=True)]
    questions = [
        ("s1-1-wide-door.svg", "s1-1｜你提到沒標的門是哪一處？", "CAM_WIDE", door),
        ("s1-2-branch-depth.svg", "s1-2｜哪個範圍符合「到轉角處、涵蓋走道」？", "CAM_BRANCH", branch),
        ("s1-3-wide-bottom.svg", "s1-3｜你說的「圖片最下緣」是左、中、右哪一段？", "CAM_WIDE", bottom),
    ]
    receipt = {"status": "PROPOSED_REVIEW_MATERIAL_NOT_AUTHORITY", "graph_source_commit": "0c34287b0b0c21c672f863fd281934f37e8aa24b",
               "source_sha256": static["source_static_geometry"]["source_sha256"],
               "graph_file_sha256": GRAPH_PINS, "static_source_pins": plan["static_source_pins"],
               "portals_sha256": PORTALS_PIN, "helper_sha256": HELPER_PIN,
               "source_images": image_receipts, "questions": [], "files": {},
               "boundary_marker_rule": "Calibrated ground rows v=518..536 px; BRANCH 0.4 m marker at CORR_N center (not full width); WIDE 0.01 m inside side boundaries, thirds ordered by image u",
               "limits": ["No human answers supplied", "Manual location boxes do not identify or certify a doorway",
                          "Nine static foot witnesses are not whole-person visibility or physical authority",
                          "WIDE next region/camera remains MISSING; reviewer door identity UNKNOWN",
                          "No graph mutation, G4, freeze, rendering, inference or distribution"],
               "gt_read": False, "events_read": False, "source_blend_read": False, "rendered": False}
    # Recheck the exact named inputs after geometry work; never modify them.
    for name, pin in GRAPH_PINS.items():
        fixed_file(args.graphs, name, pin)
    for name in names:
        fixed_file(args.provenance, name + ".json", plan["static_source_pins"][name + ".json"])
    fixed_file(args.provenance, "portals.json", PORTALS_PIN)
    for camera, pin in STILL_PINS.items():
        fixed_file(args.static_images, camera + ".png", pin)
    output.mkdir()
    for name, question, camera, candidates in questions:
        rois = [p["roi_polygon_px"] for p in patches.values() if p["camera_id"] == camera]
        raw = sheet(question, camera, images[camera], candidates, rois)
        (output / name).write_bytes(raw)
        receipt["files"][name] = sha(raw)
        receipt["questions"].append({"file": name, "camera_id": camera, "candidates": candidates,
                                     "allowed_answers": ["A", "B", "C", "都不是", "看不出來"]})
    (output / "RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"output": str(output), "files": receipt["files"], "status": receipt["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graphs", default=ROOT / "configs/q1q5/graphs/r004", type=Path)
    parser.add_argument("--provenance", required=True, type=Path)
    parser.add_argument("--static-images", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    build(parser.parse_args())
