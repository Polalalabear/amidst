"""Source recipe policy failures must stop before simulation or publication."""

import copy
from types import SimpleNamespace
from typing import Any, cast

import pytest

from amidst.finalization.scoped_authority import ScopedUnionPhysicalProvider
from amidst.finalization.scoped_export import validate_recipes


def provider() -> ScopedUnionPhysicalProvider:
    def validate(points: tuple[tuple[float, ...], ...]) -> None:
        if any(not 0 <= p[0] <= 100 or p[1:] != (0., 0.) for p in points):
            raise ValueError("outside approved source geometry")
    return cast(ScopedUnionPhysicalProvider, SimpleNamespace(
        certificate=SimpleNamespace(pins=SimpleNamespace(source_sha256="a" * 64)),
        proposal=SimpleNamespace(camera_landmark_bindings=(
            SimpleNamespace(camera=SimpleNamespace(camera_id="source-camera")),
        )),
        validate_polyline=validate,
    ))


def config() -> dict[str, Any]:
    return {"schema_version": "phase1-scoped-source-export-v1", "sampling_fps": 5,
            "config_locked_before_simulation": True, "metres_per_blender_unit": .0247,
            "source_sha256": "a" * 64, "cases": [{"case_id": "case3",
                "camera_ids": ["source-camera"], "waypoints": [
                    {"timestamp": 0., "position": [0., 0., 0.]},
                    {"timestamp": 10., "position": [0., 0., 0.]},
                    {"timestamp": 14., "position": [100., 0., 0.]},
                ]}]}


def test_approved_departure_dwell_and_all_movement_are_retained() -> None:
    value = config()
    before = copy.deepcopy(value)
    validate_recipes(value, provider())
    assert value == before


@pytest.mark.parametrize("change", ["sampling", "source", "camera", "overspeed",
                                  "interior_dwell", "outside", "off_grid"])
def test_unsupported_recipe_cannot_be_silently_repaired(change: str) -> None:
    value = config()
    case = value["cases"][0]
    if change == "sampling":
        value["sampling_fps"] = 10
    elif change == "source":
        value["source_sha256"] = "b" * 64
    elif change == "camera":
        case["camera_ids"] = ["camera-alias"]
    elif change == "overspeed":
        case["waypoints"][-1]["timestamp"] = 11.
    elif change == "interior_dwell":
        case["waypoints"].append({"timestamp": 16., "position": [100., 0., 0.]})
    elif change == "outside":
        case["waypoints"][-1]["position"][0] = 101.
    else:
        case["waypoints"][-1]["timestamp"] = 14.01
    before = copy.deepcopy(value)
    with pytest.raises(ValueError):
        validate_recipes(value, provider())
    assert value == before
