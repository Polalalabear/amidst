"""Policy format and preservation checks; no K1 algorithm modification."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from shapely.geometry import LineString, shape
from shapely.ops import unary_union

from amidst.geometry.restricted_policy import (
    build_restricted_policy,
    digest,
    load_restricted_policy,
)

ROOT = Path(__file__).resolve().parents[2]


def test_actual_policy_is_two_confirmed_annotations_without_physical_changes():
    physical_path = ROOT / "docs/engineering/C7_OFFICE_SOURCE_MAP_20261017.json"
    annotations_path = ROOT / "data/scene_audit/school_v3_approved_scale_20261006/geometry.json"
    config = json.loads((ROOT / "configs/c7_office_restricted_policy_v1.json").read_text())
    physical, annotations = (json.loads(p.read_text()) for p in (physical_path, annotations_path))
    before = copy.deepcopy(physical)
    layer = build_restricted_policy(
        physical,
        annotations,
        annotation_file_sha256=config["annotation_file_sha256"],
        physical_file_sha256=config["physical_map_sha256"],
        confirmations=config["confirmations"],
    )
    assert physical == before
    for name, variant in layer["variants"].items():
        assert [r["source_annotation_ref"] for r in variant["restricted_regions"]] == [
            "OBSTACLE_1F_OFFICE_01",
            "OBSTACLE_1F_OFFICE_02",
        ]
        assert all(
            r["tier"] == "RESTRICTED_POLICY" and r["confirmation_ref"]
            for r in variant["restricted_regions"]
        )
        assert variant["physical_sections_sha256"] == digest(
            {k: physical["variants"][name][k] for k in ("regions", "unknown_regions", "portals")}
        )
    assert layer["output_sha256"] == digest(
        {k: v for k, v in layer.items() if k != "output_sha256"}
    )
    for confirmation in config["confirmations"]:
        bad = copy.deepcopy(confirmation)
        bad["confirmation_ref"] = None
        with pytest.raises(ValueError, match="CONFIRMATION"):
            build_restricted_policy(
                physical,
                annotations,
                annotation_file_sha256=config["annotation_file_sha256"],
                physical_file_sha256=config["physical_map_sha256"],
                confirmations=[bad],
            )


def test_policy_pin_and_source_rejection():
    p = ROOT / "docs/engineering/C7_OFFICE_RESTRICTED_POLICY_20261017.json"
    d = json.loads(p.read_text())
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    result = load_restricted_policy(
        p,
        variant="person",
        expected_sha256=sha,
        expected_source_sha256=d["source_sha256"],
        expected_physical_sha256=d["physical_map_sha256"],
    )
    assert result["restricted_ref"]["tier"] == "RESTRICTED_POLICY"
    with pytest.raises(ValueError, match="FILE_HASH"):
        load_restricted_policy(
            p,
            variant="person",
            expected_sha256="0" * 64,
            expected_source_sha256=d["source_sha256"],
            expected_physical_sha256=d["physical_map_sha256"],
        )
    with pytest.raises(ValueError, match="SOURCE"):
        load_restricted_policy(
            p,
            variant="person",
            expected_sha256=sha,
            expected_source_sha256="0" * 64,
            expected_physical_sha256=d["physical_map_sha256"],
        )


def test_small_k1_input_policy_is_separate_and_cannot_create_walkability():
    fixture = json.loads(
        (ROOT / "tests/fixtures/c7_restricted_policy_small_map_v1.json").read_text()
    )
    physical = unary_union([shape(r["geometry"]) for r in fixture["regions"]])
    route = LineString([p[:2] for p in fixture["test_route_m"]])
    assert physical.covers(route)
    policy = [shape(r["geometry"]) for r in fixture["restricted_regions"]]
    assert route.intersects(policy[0]) and not physical.intersects(policy[1])
    # K1 must retain physical domain/hash and label crossings, not union/subtract policy.
    assert fixture["unknown_regions"] == []
    assert fixture["expected"]["geometry_and_ranking_unchanged"] is True
