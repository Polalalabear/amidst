"""The marker template must agree with the validator's constants and with the design literals."""

from __future__ import annotations

import json
import re

import pytest
from shapely.geometry import Polygon

from amidst.scene_markers import ValidationParams, load_template
from amidst.scene_markers import contract as c


@pytest.fixture(scope="module")
def template() -> dict:
    return load_template()


def test_required_marker_lists_match_the_validator_constants(template: dict) -> None:
    required = template["required_markers"]
    assert tuple(required["scene_static_top_level"]) == c.STATIC_REQUIRED
    assert tuple(required["floors[]"]) == c.FLOOR_REQUIRED
    assert tuple(required["objects[] (all classes)"]) == c.OBJECT_REQUIRED
    assert tuple(required["walkable[]"]) == c.WALK_REQUIRED
    assert tuple(required["walkable[].approval"]) == c.WALK_APPROVAL_REQUIRED
    assert tuple(required["objects[] class WALL/OBSTACLE (additional, §3.5)"]) == c.SOLID_REQUIRED
    assert tuple(required["portals[]"]) == c.PORTAL_REQUIRED
    assert tuple(required["portals[].opening_m"]) == c.OPENING_REQUIRED
    assert tuple(required["cameras[] (optical, no run fields)"]) == c.CAMERA_REQUIRED
    assert tuple(required["run_bindings[]"]) == c.BINDING_REQUIRED
    assert tuple(required["manifest.json (safe)"]) == c.MANIFEST_REQUIRED
    assert tuple(required["manifest.sampling"]) == c.SAMPLING_REQUIRED
    assert tuple(required["rgb_index.records[]"]) == c.RGB_RECORD_REQUIRED
    assert tuple(required["rgb_index.missing[]"]) == c.RGB_MISSING_REQUIRED
    assert not set(c.CAMERA_REQUIRED) & set(c.CAMERA_RUN_FIELDS)  # optics carry no run fields


def test_validator_parameters_match_the_defaults(template: dict) -> None:
    documented = {k: v for k, v in template["validator_parameters"].items() if k != "note"}
    assert documented == ValidationParams().as_dict()


def test_safe_private_split_matches_the_validator(template: dict) -> None:
    split = template["safe_private_split"]
    assert set(split["forbidden_key_names_exact"]) == set(c.FORBIDDEN_KEYS)
    assert set(split["forbidden_key_tokens"]) == set(c.FORBIDDEN_KEY_TOKENS)
    assert set(split["forbidden_path_segments"]) == set(c.FORBIDDEN_PATH_SEGMENTS)
    assert set(split["forbidden_value_fragments"]) == set(c.FORBIDDEN_VALUE_FRAGMENTS)
    assert set(split["validator_input_files"]) == set(c.SAFE_FILENAMES.values())
    assert not set(split["safe_files"]) & set(split["private_files"])


def test_id_rules_match_the_contract(template: dict) -> None:
    rules = template["id_rules"]
    assert rules["pattern"] == c.ID_PATTERN.pattern
    assert rules["prefix_by_class"] == c.PREFIX_BY_CLASS
    for spec in template["design_reference"]["expected_objects"]:
        assert c.ID_PATTERN.match(spec["id"])
        prefix = c.PREFIX_BY_CLASS[spec["class"]]
        assert prefix is None or spec["id"].startswith(prefix)
    ids = [o["id"] for o in template["design_reference"]["expected_objects"]]
    assert len(ids) == len(set(ids))


def test_design_values_are_the_literals_of_the_design_note(template: dict) -> None:
    ref = template["design_reference"]
    cuts = ref["cutouts"]["items"]
    assert len(cuts) == 10
    assert sum(item["area_m2"] for item in cuts) == pytest.approx(2.0705)
    assert ref["cutouts"]["total_area_m2"] == 2.0705
    polys = {k: Polygon(v) for k, v in ref["walkable_precut_polygons_m"]["polygons"].items()}
    assert sum(p.area for p in polys.values()) == pytest.approx(138.88)
    assert 138.88 - 2.0705 == pytest.approx(136.8095)
    assert [i["object_id"] for i in cuts if i["export"] == "HOLE"] == ["OBSTACLE_SCREEN_R102"]
    by_id = {item["camera_id"]: item for item in ref["cameras"]["items"]}
    assert by_id["CAM_W2"]["position_m"] == [14.4, 2.1, 1.8] and by_id["CAM_W2"]["yaw_deg"] == 205
    assert by_id["CAM_W1"]["position_m"] == [-2.6, -1.4, 2.0] and by_id["CAM_N1"]["yaw_deg"] == -65
    assert by_id["CAM_R102_CTRL"]["position_m"] == [21.8, 10.5, 2.8]
    solids = {s["id"]: s["bounds_m"] for s in ref["solids_aabb_m"]["items"]}
    assert solids["OBSTACLE_SCREEN_N"] == [[15, 5.25, 0], [15.8, 5.6, 3.2]]  # D48 deepened
    assert solids["OBSTACLE_SCREEN_CORNER_N"] == [
        [14.5, 1.6, 0],
        [14.65, 2.4, 3.2],
    ]  # moved from 1.55
    assert (
        sum(1 for s in solids if s.startswith("OBSTACLE_")) == 5
        and sum(1 for s in solids if s.startswith("WALL_")) == 22
    )


def test_every_value_group_is_labelled_as_design_value(template: dict) -> None:
    ref = template["design_reference"]
    for key in (
        "walkable_precut_polygons_m",
        "cutouts",
        "solids_aabb_m",
        "clearance_checks",
        "portals",
        "cameras",
        "events",
    ):
        assert ref[key]["value_kind"] == "設計值", key
    assert template["examples"]["value_kind"] == "設計值"


def test_sources_and_unknowns_are_recorded(template: dict) -> None:
    assert template["sources"]["contract"]["v1_1_draft_commit"] == "0e51c53"
    assert template["sources"]["contract"]["approved_v1_commit"].startswith("2643771")
    assert template["sources"]["design"]["commit"].startswith("f2afa3f")
    ids = [u["id"] for u in template["unknowns"]]
    assert ids == [f"U{n:02d}" for n in range(1, len(ids) + 1)]
    assert any("rgb_index" in d["section"] for d in template["contract_delta_v1_0_to_v1_1"])


def test_template_is_plain_json_without_non_finite_numbers() -> None:
    from amidst.scene_markers import DEFAULT_TEMPLATE

    text = DEFAULT_TEMPLATE.read_text(encoding="utf-8")
    assert not re.search(r"\b(NaN|Infinity)\b", text)
    json.loads(text, parse_constant=lambda name: (_ for _ in ()).throw(ValueError(name)))
