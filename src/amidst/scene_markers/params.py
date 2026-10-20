"""Tolerances and thresholds of the controlled-scene marker validator.

Every number a rule compares against is a field here, so a tolerance is never buried in a rule.
Defaults mirror ``validator_parameters`` in ``configs/controlled_scene_v1_marker_template.json``
(a test keeps the two in sync).  The design document states most values as exact literals; the
tolerances only absorb floating-point error.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import Any

VERIFIER_VERSION = "controlled-scene-marker-validator.v2"
PARAMS_VERSION = "validation-params.v2"  # v2: OBS-002 judged by penetration width (D58)


@dataclass(frozen=True)
class ValidationParams:
    # Geometry tolerances (m / m²).
    bounds_tol_m: float = 1e-4
    geometry_tol_m: float = 1e-6
    floor_z_tol_m: float = 1e-9
    overlap_area_tol_m2: float = 1e-6  # walkable-vs-walkable overlap (WLK-003)
    # D58: solid-vs-walkable overlap is judged by penetration width, not area.  float32 spacing
    # below 32 m is <= 3.8e-6 m, so a sliver up to 1e-5 m wide is precision noise (INFO).
    overlap_penetration_max_m: float = 1e-5
    # Cut-out list (design §1.1.1): per item, exported total (2.0705 m²) and post-cut area.
    cut_item_area_tol_m2: float = 1e-3
    cut_total_area_tol_m2: float = 1e-3
    walk_total_area_tol_m2: float = 1e-3
    walk_shape_tol_m2: float = 1e-3
    # Screen clearance (D38): envelope r = 0.30 m, clear distance >= 0.10 m.
    min_clearance_m: float = 0.10
    envelope_radius_m: float = 0.30
    clearance_tol_m: float = 1e-6
    # A solid blocks the floor when it starts below this height (D42 envelope height 1.80 m).
    blocking_height_m: float = 1.80
    # Camera pose / optics (D48, D50).
    camera_pos_tol_m: float = 1e-3
    camera_angle_tol_deg: float = 0.1
    camera_k_tol_px: float = 1e-3
    camera_rot_tol: float = 1e-6
    camera_min_gap_m: float = 0.10
    # Policy switches.
    allow_extra_ids: bool = False

    @classmethod
    def from_overrides(cls, overrides: dict[str, Any] | None) -> ValidationParams:
        if not overrides:
            return cls()
        known = {f.name: f.type for f in fields(cls)}
        clean: dict[str, Any] = {}
        for key, value in overrides.items():
            if key not in known:
                raise ValueError(f"unknown parameter: {key}")
            if isinstance(getattr(cls, key), bool):
                clean[key] = (
                    value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes")
                )
            else:
                clean[key] = float(value)
        return replace(cls(), **clean)

    def as_dict(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self)}
