"""Focused negative/source-binding tests; synthetic static fixtures only."""

import copy
import hashlib
import importlib.util
import json
import struct
import zlib
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "src/amidst/evaluation/q1q5_graph_check.py"
spec = importlib.util.spec_from_file_location("static_checker_under_test", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def png(width=8, height=6):
    def chunk(kind, data):
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\0" + bytes(width * 3)) * height))
        + chunk(b"IEND", b"")
    )


def fixture(
    tmp_path, *, polygon=None, rotation=None, promote=False, duplicate=False, missing_exit=False
):
    def save(name, value):
        path = tmp_path / name
        raw = value if isinstance(value, bytes) else json.dumps(value).encode()
        path.write_bytes(raw)
        return {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}

    h = module.canonical_hash

    def mesh(name, x):
        return {
            "object_ref": name,
            "vertices_world_m": [[x, 0, 0], [x + 1, 0, 0], [x + 1, 1, 0], [x, 1, 0]],
            "triangles_or_polygons": [[0, 1, 2, 3]],
        }

    ma, mb = mesh("WALK_A", 0), mesh("WALK_B", 1)
    static = {
        "source_sha256": "a" * 64,
        "scene_revision": "r004",
        "approval_status": "DRAFT",
        "allowed_purposes": [],
        "objects": [ma, mb],
    }
    static_ref = save("static.json", static)
    meshes = {"source_static_sha256": static_ref["sha256"], "meshes": {"A": ma, "B": mb}}
    r = {
        "schema_version": "q-demo.region-graph.v1",
        "scene_revision": "r004",
        "scene_id": "fixture",
        "scene_static_sha256": static_ref["sha256"],
        "approval_status": "DRAFT",
        "approval_ref": None,
        "regions": [{"region_id": k, "polygon_sha256": h(m)} for k, m in [("A", ma), ("B", mb)]],
        "edges": [
            {
                "edge_id": "AB",
                "regions": ["A", "B"],
                "traversability": "APPROVED_WALKABLE" if promote else "TOPOLOGICAL_ONLY",
                "state": "UNKNOWN",
                "direction": "BIDIRECTIONAL",
                "via": {"kind": "PORTAL", "ref": "OPENING_UNBOUND"},
            }
        ],
    }
    cals, cams, mappings, frames, overlays = [], [], [], {}, {}
    for cid in ["CA", "CB"]:
        frame = save(cid + ".png", png())
        frames[cid] = frame
        overlays[cid] = frame
        cal = {
            "camera_id": cid,
            "camera_model": "PINHOLE",
            "convention": "BLENDER_NEG_Z_UP_Y",
            "pixel_origin": "TOP_LEFT_CONTINUOUS",
            "meters_per_unit": 1,
            "distortion": None,
            "fx": 4,
            "fy": 4,
            "cx": 4,
            "cy": 3,
            "width": 8,
            "height": 6,
            "camera_to_world": rotation or [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2], [0, 0, 0, 1]],
            "static_validity": {"source_sha256": "a" * 64},
        }
        cal["calibration_sha256"] = h(cal)
        cals.append(cal)
        zone = {
            "exit_zone_id": cid + ":EXIT",
            "roi_polygon_px": polygon if polygon is not None else [[1, 1], [5, 1], [5, 4], [1, 4]],
            "leads_to_edge_ids": ["AB"],
            "static_frame_sha256": frame["sha256"],
        }
        cams.append(
            {
                "camera_id": cid,
                "calibration_sha256": cal["calibration_sha256"],
                "exit_zones": [] if missing_exit else [zone],
                "entry_zones": [],
            }
        )
        mappings.append(
            {
                "camera_id": cid,
                "calibration_sha256": cal["calibration_sha256"],
                "exit_zone": zone,
                "roi_content_sha256": h(zone),
                "static_frame_sha256": frame["sha256"],
            }
        )
    catalog = {"cameras": cals}
    catalog_ref = save("cameras.json", catalog)
    r["inputs"] = [
        {"ref": "static:r004:proposal", "sha256": static_ref["sha256"]},
        {"ref": "calibration:r004:catalog", "sha256": catalog_ref["sha256"]},
    ]
    r["content_sha256"] = h(r)
    r["graph_id"] = "rgraph:r004:static:" + r["content_sha256"][:16]
    c = {
        "schema_version": "q-demo.camera-transition-graph.v1",
        "scene_revision": "r004",
        "scene_id": "fixture",
        "approval_status": "DRAFT",
        "approval_ref": None,
        "camera_catalog_sha256": catalog_ref["sha256"],
        "region_graph_sha256": r["content_sha256"],
        "cameras": cams,
        "transitions": [
            {
                "transition_id": "CA_CB",
                "from_camera_id": "CA",
                "to_camera_id": "CB",
                "region_path": ["A", "B"],
                "edge_path": ["AB"],
                "region_hops": 1,
                "via_exit_zone_ids": ["CA:EXIT"],
                "to_entry_zone_ids": [],
                "path_traversability": "TOPOLOGICAL_ONLY",
                "path_has_unknown_state": True,
                "relation": "UNKNOWN",
                "ranking_area_m2": None,
                "nominal_path_length_m": None,
            }
        ],
    }
    if duplicate:
        c["cameras"].append(copy.deepcopy(cams[0]))
    c["inputs"] = r["inputs"] + [
        {"ref": "static-image:r004:" + cid, "sha256": ref["sha256"]} for cid, ref in frames.items()
    ]
    c["content_sha256"] = h(c)
    c["graph_id"] = "cgraph:r004:static:" + c["content_sha256"][:16]
    roi = {
        "source_sha256": "a" * 64,
        "scene_static_sha256": static_ref["sha256"],
        "camera_catalog_sha256": catalog_ref["sha256"],
        "entries": mappings,
    }
    files = {
        "static_geometry": static_ref,
        "camera_catalog": catalog_ref,
        **{
            key: save(key + ".json", value)
            for key, value in [
                ("region_graph", r),
                ("camera_graph", c),
                ("roi_mapping", roi),
                ("region_meshes", meshes),
            ]
        },
    }
    config = {
        "schema_version": "q-demo.r004-prereview-inputs.v1",
        "files": files,
        "static_frames": frames,
        "overlay_frames": overlays,
    }
    config_ref = save("config.json", config)
    return Path(config_ref["path"]), config_ref["sha256"], config


def test_pinned_report_is_reproducible_but_never_approval(tmp_path):
    path, sha, _ = fixture(tmp_path)
    first = module.check_graphs(path, sha)
    assert first == module.check_graphs(path, sha)
    assert first["output_sha256"] == module.canonical_hash(first, exclude=("output_sha256",))
    assert first["counts"]["legal_auto_switch_paths"] == 0
    assert first["approval"]["G4"] == "NOT_ASSERTED"
    assert any(x["id"] == "PORTAL_GEOMETRY_NOT_BOUND" for x in first["unresolved"])
    assert first["status"] == "REVIEW_REQUIRED" and first["gt_read"] is False


def test_file_tamper_fails_before_semantic_claims(tmp_path):
    path, sha, config = fixture(tmp_path)
    Path(config["files"]["region_graph"]["path"]).write_text("{}")
    with pytest.raises(module.GraphCheckError, match="pin mismatch"):
        module.check_graphs(path, sha)


@pytest.mark.parametrize(
    "poly",
    [
        [],
        [[0, 0], [1, 1], [2, 2]],
        [[1, 1], [5, 4], [5, 1], [1, 4]],
        [[1, 1], [8, 1], [5, 4]],
        [[1, 1], [5, 1], [5, 1]],
    ],
)
def test_invalid_source_polygons_rejected_even_when_resealed(tmp_path, poly):
    path, sha, _ = fixture(tmp_path, polygon=poly)
    with pytest.raises(module.GraphCheckError):
        module.check_graphs(path, sha)


@pytest.mark.parametrize(
    "options",
    [
        {"missing_exit": True},
        {"duplicate": True},
        {"promote": True},
        {"rotation": [[2, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2], [0, 0, 0, 1]]},
    ],
)
def test_camera_and_authority_fail_closed(tmp_path, options):
    path, sha, _ = fixture(tmp_path, **options)
    with pytest.raises(module.GraphCheckError):
        module.check_graphs(path, sha)


def test_png_crc_and_trailing_bytes_rejected():
    assert module.png_info(png())["width"] == 8
    for bad in [png() + b"extra", png()[:-1], png()[:40] + b"X" + png()[41:]]:
        with pytest.raises(module.GraphCheckError):
            module.png_info(bad)


def test_duplicate_json_and_nonfinite_values_rejected():
    for value in ['{"a":1,"a":2}', '{"v":NaN}']:
        with pytest.raises(module.GraphCheckError):
            module.strict_json(value)


def test_map_uses_actual_polygons_and_labels_limits(tmp_path):
    path, sha, _ = fixture(tmp_path)
    svg = module.render_static_map(path, sha)
    assert "<polygon" in svg and "WALK_A" not in svg and "CA" in svg
    assert "NOT APPROVED" in svg and "NOT field of view" in svg


@pytest.mark.parametrize(
    "compressed",
    [
        b"not zlib",
        zlib.compress(b"\x05" + bytes(24)) * 6,
        zlib.compress((b"\0" + bytes(24)) * 6) + b"extra",
    ],
)
def test_crc_correct_but_undecodable_png_rejected(compressed):
    raw = png()
    start = raw.index(b"IDAT") - 4
    old_size = struct.unpack(">I", raw[start : start + 4])[0]
    chunk = (
        struct.pack(">I", len(compressed))
        + b"IDAT"
        + compressed
        + struct.pack(">I", zlib.crc32(b"IDAT" + compressed) & 0xFFFFFFFF)
    )
    malformed = raw[:start] + chunk + raw[start + old_size + 12 :]
    with pytest.raises(module.GraphCheckError):
        module.png_info(malformed)


def test_resealed_path_cannot_exceed_edge_authority(tmp_path):
    path, _, config = fixture(tmp_path)
    ref = config["files"]["camera_graph"]
    camera = json.loads(Path(ref["path"]).read_bytes())
    camera["transitions"][0]["path_traversability"] = "APPROVED_WALKABLE"
    camera["content_sha256"] = module.canonical_hash(
        camera, exclude=("graph_id", "content_sha256", "stats")
    )
    camera["graph_id"] = "cgraph:r004:static:" + camera["content_sha256"][:16]
    raw = json.dumps(camera).encode()
    Path(ref["path"]).write_bytes(raw)
    ref["sha256"] = hashlib.sha256(raw).hexdigest()
    raw = json.dumps(config).encode()
    path.write_bytes(raw)
    with pytest.raises(module.GraphCheckError, match="PATH_AUTHORITY"):
        module.check_graphs(path, hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize(
    "change",
    [
        {"schema_version": "invalid"},
        {"approval_status": "APPROVED", "approval_ref": "invented"},
        {"scene_id": "another"},
        {"inputs": []},
    ],
)
def test_resealed_schema_or_approval_rejected(tmp_path, change):
    path, _, config = fixture(tmp_path)
    ref = config["files"]["camera_graph"]
    camera = json.loads(Path(ref["path"]).read_bytes())
    camera.update(change)
    camera["content_sha256"] = module.canonical_hash(
        camera, exclude=("graph_id", "content_sha256", "stats")
    )
    camera["graph_id"] = "cgraph:r004:static:" + camera["content_sha256"][:16]
    raw = json.dumps(camera).encode()
    Path(ref["path"]).write_bytes(raw)
    ref["sha256"] = hashlib.sha256(raw).hexdigest()
    raw = json.dumps(config).encode()
    path.write_bytes(raw)
    with pytest.raises(module.GraphCheckError):
        module.check_graphs(path, hashlib.sha256(raw).hexdigest())


@pytest.mark.parametrize("change", [{"camera_model": "FISHEYE"}, {"width": True}, {"height": 6.0}])
def test_calibration_projection_model_is_explicit(tmp_path, change):
    _, _, config = fixture(tmp_path)
    cal = json.loads(Path(config["files"]["camera_catalog"]["path"]).read_text())["cameras"][0]
    cal.update(change)
    cal["calibration_sha256"] = module.canonical_hash(cal, exclude=("calibration_sha256",))
    with pytest.raises(module.GraphCheckError):
        module._calibration_check(cal)
