"""Geometry trust-boundary tests for the static review supplements."""

import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "src/amidst/evaluation/r004_review_v2.py"
spec = importlib.util.spec_from_file_location("r004_review_v2_test", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def v3_documents():
    root = Path(__file__).resolve().parents[2] / "configs/q1q5/graphs/r004"
    return {name: json.loads((root / (name + ".json")).read_text())
            for name in ["camera_graph_v3", "region_graph_v3", "tracking_scope_v3",
                         "static_patches_v3", "roi_report_v3"]}


def test_v3_production_loader_and_query_only_camera_scope():
    from amidst.q1q5.graphs import load_graphs
    docs = v3_documents(); region, camera = docs["region_graph_v3"], docs["camera_graph_v3"]
    bundle = load_graphs(region, camera, region_sha256=region["content_sha256"],
                         camera_sha256=camera["content_sha256"],
                         tracking_scope=docs["tracking_scope_v3"],
                         tracking_scope_sha256=hashlib.sha256((Path(__file__).resolve().parents[2] /
                             "configs/q1q5/graphs/r004/tracking_scope_v3.json").read_bytes()).hexdigest())
    assert bundle.approval_status == "DRAFT"
    scope = docs["tracking_scope_v3"]
    assert len(scope["query_camera_ids"]) == 8 and len(scope["tracking_camera_ids"]) == 7
    assert scope["query_only_camera_ids"] == ["CAM_ENTRY"]
    assert all(c["camera_id"] != "CAM_ENTRY" for c in camera["cameras"])
    assert all(e["traversability"] == "TOPOLOGICAL_ONLY" for e in region["edges"])


def test_v3_1_loader_preserves_pins_authority_and_transition_semantics():
    from amidst.q1q5.graphs import load_graphs
    root = Path(__file__).resolve().parents[2] / "configs/q1q5/graphs/r004"
    plan = json.loads((root / "build_plan_v3_1.json").read_bytes())
    for name, pin in plan["base_files"].items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == pin
    old = v3_documents()
    new = {n: json.loads((root / (n + "_v3_1.json")).read_bytes())
           for n in ["camera_graph", "region_graph", "tracking_scope", "static_patches", "roi_report"]}
    region, camera = new["region_graph"], new["camera_graph"]
    bundle = load_graphs(region, camera, region_sha256=region["content_sha256"],
                         camera_sha256=camera["content_sha256"],
                         tracking_scope=new["tracking_scope"],
                         tracking_scope_sha256=hashlib.sha256(
                             (root / "tracking_scope_v3_1.json").read_bytes()).hexdigest())
    assert bundle.approval_status == "DRAFT"
    assert camera["transitions"] == old["camera_graph_v3"]["transitions"]
    assert region["edges"] == old["region_graph_v3"]["edges"]
    assert new["tracking_scope"] == old["tracking_scope_v3"]
    changed = {k for k, v in new["static_patches"].items() if v != old["static_patches_v3"][k]}
    assert changed == {"CAM_BRANCH:ENTRY_V3:E_W_CORNER", "CAM_BRANCH:EXIT_V3:E_W_CORNER",
                       "CAM_BRANCH:EXIT_V3:E_CORNER_N"}
    for zid in changed:
        patch = new["static_patches"][zid]
        xs = [p[0] for p in patch["polygon_world_m"]]
        assert max(xs) - min(xs) == pytest.approx(2.4, abs=1e-6)
        assert patch["static_witness_count"] == 9
        assert new["roi_report"][zid]["reprojection_consistency_max_px"] == 0
        assert new["roi_report"][zid]["independent_calibration_error_px"] is None
    for before, after in zip(old["camera_graph_v3"]["cameras"], camera["cameras"], strict=True):
        assert before["calibration_sha256"] == after["calibration_sha256"]


def test_v3_1_recipe_tampering_fails_before_static_reads(tmp_path):
    root = Path(__file__).resolve().parents[2] / "configs/q1q5/graphs/r004"
    recipe = root / "build_plan_v3_1.json"
    with pytest.raises(m.ReviewError, match="Input pin mismatch"):
        m.build_graph_v3_1(recipe, "0" * 64, root, tmp_path / "missing", tmp_path / "out")


def test_v3_all_56_pairs_accounted_and_d77_pairs_excluded():
    docs = v3_documents(); scope = docs["tracking_scope_v3"]
    rows = scope["directed_pairs"]
    assert len(rows) == len({(r["from_camera_id"], r["to_camera_id"]) for r in rows}) == 56
    for row in rows:
        if row["disposition"] == "EXCLUDED":
            assert row["reason"]
        if {row["from_camera_id"], row["to_camera_id"]} in [
                {"CAM_BRANCH", "CAM_WIDE"}, {"CAM_EXT_CAR", "CAM_EXT_CLEAR"}]:
            assert row["reason"].startswith("D77_")


@pytest.mark.parametrize("cid", ["CAM_BRANCH", "CAM_EXT_CAR", "CAM_EXT_CLEAR", "CAM_R101_IN",
                                "CAM_W1", "CAM_W2", "CAM_WIDE", "CAM_ENTRY"])
def test_v3_eight_missing_exit_negative_probes(cid):
    from amidst.q1q5.graphs import GraphError, load_graphs
    docs = v3_documents(); region, camera = docs["region_graph_v3"], deepcopy(docs["camera_graph_v3"])
    if cid == "CAM_ENTRY":
        # D74 excludes it from tracking. Deliberately re-including it without
        # a real exit must fail, rather than fabricating an ROI for the probe.
        camera["cameras"].append({**deepcopy(camera["cameras"][0]), "camera_id": cid,
                                  "exit_zones": [], "entry_zones": []})
    else:
        next(c for c in camera["cameras"] if c["camera_id"] == cid)["exit_zones"] = []
    m.seal_graph(camera, "cgraph")
    with pytest.raises(GraphError) as error:
        load_graphs(region, camera, region_sha256=region["content_sha256"],
                    camera_sha256=camera["content_sha256"])
    assert error.value.code == "EXIT_ZONES_MISSING"


def test_v3_per_edge_entries_and_north_south_vehicle_approaches():
    docs = v3_documents(); patches = docs["static_patches_v3"]
    for cid in ["CAM_W1", "CAM_W2"]:
        assert all(cid + ":ENTRY_V3:" + edge in patches
                   for edge in (["E_PORTAL_R101","E_VEST_CORR","E_W_CORNER"] if cid=="CAM_W1" else ["E_PORTAL_R101","E_OUT_VEST","E_W_CORNER"]))
    for side in ["NORTH_APPROACH", "SOUTH_APPROACH"]:
        for role in ["ENTRY", "EXIT"]:
            p = patches["CAM_EXT_CAR:" + role + "_V3:" + side]
            assert p["edge_id"] == "E_OUT_VEST" and p["static_witness_count"] == 9
    assert "CAM_WIDE:EXIT_V3:E_PORTAL_R102" in patches
    assert all("CAM_ENTRY" not in key for key in patches)


def test_v3_rectangle_union_cannot_hide_a_floor_hole():
    mesh = {"vertices_world_m": [[0,0,0],[1,0,0],[1,2,0],[0,2,0],
                                 [1.1,0,0],[2,0,0],[2,2,0],[1.1,2,0]],
            "triangles_or_polygons": [[0,1,2,3],[4,5,6,7]]}
    assert not m.rectangle_supported([0,2,0,2], 0, mesh)
    assert m.rectangle_supported([0,1,0,2], 0, mesh)


def test_concave_face_does_not_fill_missing_corner():
    points = [[0, 0, 0], [2, 0, 0], [2, 1, 0], [1, 1, 0], [1, 2, 0], [0, 2, 0]]
    triangles = m.triangulate_face(points)
    assert len(triangles) == 4
    assert not any(m.segment_triangle([1.5, 1.5, 1], [1.5, 1.5, -1], t) for t in triangles)
    assert any(m.segment_triangle([0.5, 1.5, 1], [0.5, 1.5, -1], t) for t in triangles)


def test_nonplanar_face_is_rejected():
    with pytest.raises(m.ReviewError, match="Non-planar"):
        m.triangulate_face([[0, 0, 0], [2, 0, 0], [2, 2, 0.3], [0, 2, 0]])


@pytest.mark.parametrize(
    "a,b,blocked",
    [
        ([0.2, 0.2, 1], [0.2, 0.2, -1], True),
        ([0.2, 0.2, 1], [0.2, 0.2, 0], False),
        ([2, 2, 1], [2, 2, -1], False),
        ([0.2, 0.2, -1], [0.2, 0.2, 1], True),
    ],
)
def test_occlusion_is_two_sided_and_endpoint_safe(a, b, blocked):
    assert m.segment_triangle(a, b, [[0, 0, 0], [1, 0, 0], [0, 1, 0]]) is blocked


def test_support_gap_is_not_an_aabb():
    mesh = {
        "vertices_world_m": [
            [0, 0, 0],
            [1, 0, 0],
            [1, 1, 0],
            [0, 1, 0],
            [2, 0, 0],
            [3, 0, 0],
            [3, 1, 0],
            [2, 1, 0],
        ],
        "triangles_or_polygons": [[0, 1, 2, 3], [4, 5, 6, 7]],
    }
    assert m.on_support([0.5, 0.5, 0], mesh)
    assert not m.on_support([1.5, 0.5, 0], mesh)
    assert not m.on_support([0.5, 0.5, 0.1], mesh)
    assert m.square_supported([0.5, 0.5, 0], 0.4, mesh)
    assert not m.square_supported([1.5, 0.5, 0], 0.4, mesh)


def test_small_interior_hole_cannot_hide_between_nine_witnesses():
    vs, faces = [], []
    for left, r, b, t in [
        (-1, 0.1, -1, 1),
        (0.15, 1, -1, 1),
        (0.1, 0.15, -1, 0.1),
        (0.1, 0.15, 0.15, 1),
    ]:
        n = len(vs)
        vs += [[left, b, 0], [r, b, 0], [r, t, 0], [left, t, 0]]
        faces.append(list(range(n, n + 4)))
    mesh = {"vertices_world_m": vs, "triangles_or_polygons": faces}
    assert all(m.on_support([x * 0.4, y * 0.4, 0], mesh) for x in [-1, 0, 1] for y in [-1, 0, 1])
    assert not m.square_supported([0, 0, 0], 0.4, mesh)


def wall():
    vertices, faces = [], []
    for lo, hi, bottom, top in [(-2, -0.5, 0, 3), (0.5, 2, 0, 3), (-0.5, 0.5, 2, 3)]:
        start = len(vertices)
        vertices += [[lo, 0, bottom], [hi, 0, bottom], [hi, 0, top], [lo, 0, top]]
        faces.append(list(range(start, start + 4)))
    return {"object_ref": "SHELL", "vertices_world_m": vertices, "triangles_or_polygons": faces}


def test_aperture_has_source_faces_and_actual_dimensions():
    result = m.aperture(wall(), 1, 0, 0, [-2, 2], "PORTAL")
    assert result["width_m"] == 1 and result["height_m"] == 2
    assert result["source_face_indices"] == [0, 1, 2]
    assert result["mesh_sha256"] == m.digest(wall())
    assert result["status"] == "PROPOSED" and result["approval_granted"] is False


def test_unbounded_aperture_is_rejected():
    with pytest.raises(m.ReviewError):
        m.aperture(wall(), 1, 0, 0, [-0.4, 2], "PORTAL")


def test_off_plane_or_unsupported_aperture_cannot_be_invented():
    with pytest.raises(m.ReviewError):
        m.aperture(wall(), 1, 5, 0, [-2, 2], "PORTAL")


def test_hidden_templates_and_support_annotations_stay_separate():
    static = {
        "source_sha256": "a",
        "objects": [{"object_ref": x} for x in ["WALL", "TEMPLATE", "WALK_A"]],
    }
    record = {
        "source_sha256": "a",
        "objects": [
            {"object_ref": "WALL", "hide_render": False, "render_collection_enabled": True},
            {"object_ref": "TEMPLATE", "hide_render": True, "render_collection_enabled": True},
            {"object_ref": "WALK_A", "hide_render": True, "render_collection_enabled": True},
        ],
    }
    result = m.membership(static, record)
    assert result["excluded_source_only_objects"] == ["TEMPLATE"]
    assert result["support_annotation_meshes"] == [{"object_ref": "WALK_A"}]
    assert result["render_enabled_objects"] == [{"object_ref": "WALL"}]
    assert result["approval_granted"] is False


def test_membership_cannot_mix_sources_or_omit_members():
    with pytest.raises(m.ReviewError):
        m.membership({"source_sha256": "a", "objects": []}, {"source_sha256": "b", "objects": []})
    with pytest.raises(m.ReviewError):
        m.membership(
            {"source_sha256": "a", "objects": [{"object_ref": "A"}]},
            {"source_sha256": "a", "objects": []},
        )


def test_project_never_uses_points_behind_camera():
    cal = {
        "camera_to_world": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 2], [0, 0, 0, 1]],
        "fx": 100,
        "fy": 100,
        "cx": 100,
        "cy": 100,
    }
    assert m.project(cal, [0, 0, 0]) == [100, 100]
    assert m.project(cal, [0, 0, 3]) is None


def test_shared_entry_exit_svg_keeps_both_roles_and_portable_image():
    import xml.etree.ElementTree as ET

    common = {
        "camera_id": "CAM_A",
        "roi_polygon_px": [[10, 10], [30, 10], [30, 30], [10, 30]],
        "center_to_locator_m": 0.5,
    }
    rows = {
        "ENTRY": {**common, "role": "ENTRY"},
        "EXIT": {**common, "role": "EXIT", "edge_id": "EDGE_A"},
    }
    root = ET.fromstring(m.zone_svg("CAM_A", b"encoded_pixels", rows))
    ns = {"s": "http://www.w3.org/2000/svg"}
    assert len(root.findall("s:polygon", ns)) == 2
    assert root.find("s:image", ns).attrib["href"].startswith("data:image/png;base64,")
    texts = [e.text for e in root.findall("s:text", ns)]
    assert "E1" in texts and "X1" in texts
    assert any("ENTRY (blue dashed)" in x for x in texts)
    assert any("EXIT EDGE_A" in x for x in texts)


def test_d81_w2_vestibule_patch_and_four_paths_are_consistent():
    docs=v3_documents();patches=docs["static_patches_v3"];camera=docs["camera_graph_v3"]
    for role in ["ENTRY","EXIT"]:
        patch=patches[f"CAM_W2:{role}_V3:E_OUT_VEST"]
        assert patch["region_id"]=="VEST_W" and patch["edge_id"]=="E_OUT_VEST"
        assert f"CAM_W2:{role}_V3:E_VEST_CORR" not in patches
    for row in camera["transitions"]:
        if {row["from_camera_id"],row["to_camera_id"]} in [{"CAM_W2","CAM_EXT_CAR"},{"CAM_W2","CAM_EXT_CLEAR"}]:
            assert row["edge_path"]==["E_OUT_VEST"] and row["region_hops"]==1
            assert row["region_path"]==(["VEST_W","OUT_W"] if row["from_camera_id"]=="CAM_W2" else ["OUT_W","VEST_W"])


def test_d81_same_region_pairs_do_not_grant_g4_or_invent_an_edge():
    docs=v3_documents();camera=docs["camera_graph_v3"];scope=docs["tracking_scope_v3"]
    assert len(camera["transitions"])==22
    assert sum(row["disposition"]=="TRANSITION" for row in scope["directed_pairs"])==22
    for source,target in [("CAM_W1","CAM_W2"),("CAM_W2","CAM_W1")]:
        row=next(t for t in camera["transitions"] if t["from_camera_id"]==source and t["to_camera_id"]==target)
        assert row["region_path"]==["CORR_W"] and row["edge_path"]==[] and row["region_hops"]==0
        assert row["via_exit_zone_ids"] and row["to_entry_zone_ids"]
        assert row["relation"]=="UNKNOWN" and row["ranking_area_m2"] is None
        assert row["path_traversability"]=="APPROVED_WALKABLE" and not row["path_has_unknown_state"]
    assert camera["approval_status"]=="DRAFT" and scope["G4_approved"] is False


def test_source_locator_rebases_without_embedding_private_root(tmp_path, monkeypatch):
    monkeypatch.setenv("AMIDST_ARTIFACTS", str(tmp_path))
    assert m.source_blend_locator("source/file.blend") == tmp_path / "source/file.blend"
    with pytest.raises(m.ReviewError, match="within AMIDST_ARTIFACTS"):
        m.source_blend_locator("../outside.blend")


def test_source_locator_rejects_symlink_escape(tmp_path, monkeypatch):
    monkeypatch.setenv("AMIDST_ARTIFACTS", str(tmp_path))
    (tmp_path / "source").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(m.ReviewError, match="within AMIDST_ARTIFACTS"):
        m.source_blend_locator("source/file.blend")
