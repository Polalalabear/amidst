"""Geometry trust-boundary tests for the static review supplements."""

import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[2] / "src/amidst/evaluation/r004_review_v2.py"
spec = importlib.util.spec_from_file_location("r004_review_v2_test", SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


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
