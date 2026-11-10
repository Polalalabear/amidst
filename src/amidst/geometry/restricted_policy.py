"""D15 user-confirmed policy polygons, separate from physical source geometry."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from shapely.geometry import Polygon, mapping, shape
from shapely.ops import unary_union


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def build_restricted_policy(
    physical, annotations, *, annotation_file_sha256, physical_file_sha256, confirmations
):
    if physical["source_sha256"] != annotations["source_sha256"]:
        raise ValueError("POLICY_SOURCE_MISMATCH")
    if not confirmations or len({c["annotation_ref"] for c in confirmations}) != len(confirmations):
        raise ValueError("POLICY_CONFIRMATION_REQUIRED_OR_DUPLICATE")
    surfaces = {r["surface_id"]: r for r in annotations["surfaces"]}
    scale = physical["config"]["metres_per_blender_unit"]
    rows = []
    for confirmation in confirmations:
        if confirmation.get("decision") != "D15" or not confirmation.get("confirmation_ref"):
            raise ValueError("POLICY_CONFIRMATION_REQUIRED")
        ref = confirmation["annotation_ref"]
        row = surfaces[ref]
        polygon = unary_union(
            [
                Polygon([(row["vertices"][i][0] * scale, row["vertices"][i][1] * scale) for i in t])
                for t in row["triangles"]
            ]
        )
        if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
            raise ValueError("POLICY_GEOMETRY_INVALID")
        rows.append(
            {
                "region_id": "restricted:" + ref,
                "tier": "RESTRICTED_POLICY",
                "source": "USER_CONFIRMED_ANNOTATION",
                "geometry": mapping(polygon),
                "source_annotation_ref": ref,
                "source_annotation_record_sha256": digest(row),
                "source_annotation_file_sha256": annotation_file_sha256,
                "confirmation_ref": confirmation["confirmation_ref"],
                "decision": "D15",
                "physical_obstacle": False,
                "affects_walkability": False,
                "affects_ranking": False,
            }
        )
    result = {
        "schema_version": "office-demo.restricted-policy.v1",
        "source_sha256": physical["source_sha256"],
        "physical_map_sha256": physical_file_sha256,
        "physical_output_sha256": physical["output_sha256"],
        "annotation_file_sha256": annotation_file_sha256,
        "metres_per_blender_unit": scale,
        "authority": "USER_CONFIRMED_POLICY_ONLY_NOT_PHYSICAL_GEOMETRY",
        "gt_read": False,
        "variants": {},
    }
    for name, variant in physical["variants"].items():
        result["variants"][name] = {
            "floor_z_m": variant["floor_z_m"],
            "parameters": copy.deepcopy(variant["parameters"]),
            "physical_sections_sha256": digest(
                {k: variant[k] for k in ("regions", "unknown_regions", "portals")}
            ),
            "restricted_regions": copy.deepcopy(rows),
        }
    result["output_sha256"] = digest(result)
    return result


def load_restricted_policy(
    path, *, variant, expected_sha256, expected_source_sha256, expected_physical_sha256
):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("POLICY_FILE_HASH_MISMATCH")
    bundle = json.loads(raw)
    if bundle["output_sha256"] != digest({k: v for k, v in bundle.items() if k != "output_sha256"}):
        raise ValueError("POLICY_OUTPUT_HASH_MISMATCH")
    if (
        bundle["source_sha256"] != expected_source_sha256
        or bundle["physical_map_sha256"] != expected_physical_sha256
        or bundle["gt_read"] is not False
    ):
        raise ValueError("POLICY_SOURCE_MISMATCH")
    rows = bundle["variants"][variant]["restricted_regions"]
    for row in rows:
        if (
            row["tier"] != "RESTRICTED_POLICY"
            or not row["confirmation_ref"]
            or row["physical_obstacle"] is not False
            or row["affects_walkability"] is not False
            or row["affects_ranking"] is not False
        ):
            raise ValueError("POLICY_AUTHORITY_INVALID")
        polygon = shape(row["geometry"])
        if polygon.is_empty or not polygon.is_valid:
            raise ValueError("POLICY_GEOMETRY_INVALID")
    return {
        "restricted_ref": {
            "map_ref": "restricted-policy:" + expected_sha256[:24],
            "sha256": expected_sha256,
            "source": "USER_CONFIRMED_ANNOTATION",
            "tier": "RESTRICTED_POLICY",
        },
        "restricted_regions": copy.deepcopy(rows),
        "physical_sections_sha256": bundle["variants"][variant]["physical_sections_sha256"],
    }
