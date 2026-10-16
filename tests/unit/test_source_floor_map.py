"""Source-only geometry, body-radius conditioning, portals and K1 handoff guards."""

import copy
import hashlib
import json
from dataclasses import dataclass

import numpy as np
import pytest
from shapely.geometry import Point, shape
from shapely.ops import unary_union

from amidst.geometry.source_floor_map import derive_source_map, digest, load_polygon_floor_map


def cuboid(x0, y0, z0, x1, y1, z1):
    vertices = [[x, y, z] for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    triangles = [
        [0, 1, 3],
        [0, 3, 2],
        [4, 6, 7],
        [4, 7, 5],
        [0, 4, 5],
        [0, 5, 1],
        [2, 3, 7],
        [2, 7, 6],
        [0, 2, 6],
        [0, 6, 4],
        [1, 5, 7],
        [1, 7, 3],
    ]
    return {"vertices": vertices, "triangles": triangles}


@pytest.fixture
def extract():
    config = {
        "source_sha256": "a" * 64,
        "metres_per_blender_unit": 1,
        "floor_top_search_z_m": [0.35, 0.8],
        "floor_mode_bin_m": 0.001,
        "minimum_floor_patch_area_m2": 4.0,
        "floor_height_tolerance_m": 0.002,
        "floor_normal_min_abs_z": 0.999,
        "body_floor_exclusion_m": 0.005,
        "precision_grid_m": 0.00001,
        "buffer_quadrant_segments": 16,
        "furniture_assembly_prefixes": ["Theatre Chair"],
        "portal": {
            "axis_tolerance_m": 0.005,
            "min_flank_length_m": 0.4,
            "min_width_m": 0.55,
            "max_width_m": 3.5,
            "half_depth_m": 0.3,
        },
        "run_parameters": {
            "person": {"body_radius_m": 0.25, "body_height_m": 1.7},
            "legacy_office": {"body_radius_m": 0.1482, "body_height_m": 2.9393},
        },
    }
    geometries = {}
    objects = []

    def add(name, g, parent=None):
        h = digest(g)
        geometries[h] = g
        objects.append(
            {
                "instance_ref": "mesh:" + name,
                "object_id": name,
                "parent": parent,
                "geometry_sha256": h,
                "matrix_world_bu": np.eye(4).tolist(),
            }
        )

    add("floor", cuboid(0, 0, 0, 10, 10, 0.5))
    add("wall-south", cuboid(4.9, 0, 0.5, 5.1, 4, 3.5))
    add("wall-north", cuboid(4.9, 6, 0.5, 5.1, 10, 3.5))
    add("lintel", cuboid(4.9, 4, 2.5, 5.1, 6, 3.5))
    add("chair-a", cuboid(2, 2, 0.5, 3, 3, 1.5), "Theatre Chair.A")
    add("chair-b", cuboid(7, 7, 0.5, 8, 8, 1.5), "Theatre Chair.B")
    return {
        "schema_version": "office-demo.source-mesh-extract.v1",
        "config": config,
        "source_sha256": "a" * 64,
        "source_size": 123,
        "source_mtime_ns": 1,
        "source_identity_unchanged": True,
        "source_saved": False,
        "render_executed": False,
        "annotations_as_inputs": False,
        "gt_read": False,
        "config_sha256": "b" * 64,
        "producer_sha256": "c" * 64,
        "evaluated_scene": {"frame": 220},
        "roi_m": [[0, 0, 0.35], [10, 10, 3.75]],
        "objects": objects,
        "geometry_definitions": geometries,
    }


def build(extract):
    return derive_source_map(extract, extract_sha256="d" * 64)


def free(result, variant="person"):
    return unary_union([shape(r["geometry"]) for r in result["variants"][variant]["regions"]])


def test_floor_height_from_support_and_per_chair_footprints(extract):
    saved = copy.deepcopy(extract)
    result = build(extract)
    assert result["floor"]["evidence"]["height_m"] == pytest.approx(0.5)
    assert result["floor"]["evidence"]["level_anchor_instance_refs"] == ["mesh:floor"]
    furniture = result["variants"]["person"]["furniture"]
    assert len(furniture) == 2
    assert all(f["area_m2"] == pytest.approx(1) for f in furniture)
    assert not free(result).covers(Point(2.5, 2.5))
    assert free(result).covers(Point(3.5, 3.5))
    assert extract == saved
    assert result["output_sha256"] == digest(
        {k: v for k, v in result.items() if k != "output_sha256"}
    )


def test_body_height_blocks_legacy_at_person_passable_source_door(extract):
    result = build(extract)
    assert len(result["variants"]["person"]["portals"]) == 1
    assert result["variants"]["person"]["portals"][0]["opening_width_m"] == pytest.approx(2)
    assert not result["variants"]["legacy_office"]["portals"]
    assert free(result).covers(Point(5, 5))
    assert not free(result, "legacy_office").covers(Point(5, 5))


def test_radius_is_conditioned_once_and_buffer_is_conservative(extract):
    extract["config"]["run_parameters"]["small"] = {"body_radius_m": 0.1, "body_height_m": 1.7}
    result = build(extract)
    assert result["variants"]["person"]["effective_conservative_buffer_radius_m"] > 0.25
    assert free(result, "small").area > free(result).area
    assert free(result, "small").covers(Point(3.15, 2.5))
    assert not free(result).covers(Point(3.15, 2.5))


def test_zero_thickness_source_wall_remains_a_body_barrier(extract):
    geom = {
        "vertices": [[1, 0, 0.5], [1, 10, 0.5], [1, 10, 3.5], [1, 0, 3.5]],
        "triangles": [[0, 1, 2], [0, 2, 3]],
    }
    h = digest(geom)
    extract["geometry_definitions"][h] = geom
    extract["objects"].append(
        {
            "instance_ref": "mesh:thin-wall",
            "object_id": "thin-wall",
            "parent": None,
            "geometry_sha256": h,
            "matrix_world_bu": np.eye(4).tolist(),
        }
    )
    result = build(extract)
    assert not free(result).covers(Point(1, 5))
    assert free(result).covers(Point(1.5, 5))


@pytest.mark.parametrize(
    "field", ["annotations_as_inputs", "gt_read", "source_saved", "render_executed"]
)
def test_non_source_inputs_and_mutated_geometry_are_rejected(extract, field):
    extract[field] = True
    with pytest.raises(ValueError, match="SOURCE_ONLY_EVIDENCE_REQUIRED"):
        build(extract)


def test_tampered_geometry_and_no_floor_fail_closed(extract):
    extract["geometry_definitions"][extract["objects"][0]["geometry_sha256"]]["vertices"][0][0] = 99
    with pytest.raises(ValueError, match="EVALUATED_GEOMETRY_HASH_MISMATCH"):
        build(extract)


def test_no_floor_support_is_not_replaced_by_annotation(extract):
    extract["objects"] = [o for o in extract["objects"] if o["object_id"] != "floor"]
    # Chair tops are outside the declared floor search band; no floor is invented.
    with pytest.raises(ValueError, match="SOURCE_FLOOR_SUPPORT_UNAVAILABLE"):
        build(extract)


@dataclass
class Descriptor:
    kind: str
    map_ref: str
    sha256: str
    walkable_ref: str
    portal_ref: str
    floor_id: str


@dataclass
class Map:
    descriptor: Descriptor
    floor_z_m: float
    regions: dict
    portals: dict
    unknown_regions: dict
    region_tiers: dict


def test_k1_shape_adapter_checks_pins_and_preserves_holes(extract, tmp_path):
    result = build(extract)
    path = tmp_path / "map.json"
    path.write_text(json.dumps(result))
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    loaded = load_polygon_floor_map(
        path,
        variant="person",
        expected_sha256=h,
        expected_source_sha256="a" * 64,
        map_class=Map,
        descriptor_class=Descriptor,
    )
    assert loaded.descriptor.kind == "SOURCE_DERIVED_MESH"
    assert loaded.floor_z_m == pytest.approx(0.5)
    assert loaded.region_tiers and set(loaded.region_tiers.values()) == {"SOURCE_DERIVED"}
    assert not unary_union(list(loaded.regions.values())).covers(Point(2.5, 2.5))
    with pytest.raises(ValueError, match="MAP_BUNDLE_HASH_MISMATCH"):
        load_polygon_floor_map(
            path, variant="person", expected_sha256="0" * 64, expected_source_sha256="a" * 64
        )
    with pytest.raises(ValueError, match="MAP_SOURCE_AUTHORITY_MISMATCH"):
        load_polygon_floor_map(
            path, variant="person", expected_sha256=h, expected_source_sha256="e" * 64
        )


def test_small_coplanar_threshold_is_kept_when_connected_to_floor_anchors(extract):
    extract["objects"] = [o for o in extract["objects"] if o["object_id"] == "floor"]
    extract["objects"] = []
    for name, geometry in (
        ("left", cuboid(0, 0, 0, 4.9, 10, 0.5)),
        ("right", cuboid(5.1, 0, 0, 10, 10, 0.5)),
        ("threshold", cuboid(4.9, 4, 0, 5.1, 6, 0.5)),
    ):
        h = digest(geometry)
        extract["geometry_definitions"][h] = geometry
        extract["objects"].append(
            {
                "instance_ref": "mesh:" + name,
                "object_id": name,
                "parent": None,
                "geometry_sha256": h,
                "matrix_world_bu": np.eye(4).tolist(),
            }
        )
    result = build(extract)
    assert shape(result["floor"]["geometry"]).covers(Point(5, 5))
    assert "mesh:threshold" in result["floor"]["evidence"]["source_instance_refs"]
    assert "mesh:threshold" not in result["floor"]["evidence"]["level_anchor_instance_refs"]
