"""Independent single-track examples exercise occurrence, alert lifecycle and missing evidence."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from amidst.domain.observation import ProjectedPoint
from amidst.engineering.association import ConfiguredRegion, InferenceScope, ProjectedMeasurement
from amidst.engineering.local_association import InferenceBundle
from amidst.engineering.local_behavior import BehaviorConfig
from amidst.phase2_research.pipeline import candidate_policies
from amidst.phase2_research.rules import compose_rules


def case(
    positions: list[float], *, gap_after: int | None = None, missing: int | None = None
) -> tuple[InferenceBundle, BehaviorConfig]:
    scope = InferenceScope(
        place_id="lab",
        model_id="model",
        model_revision="1",
        run_id="run",
        clock_id="seconds",
        source_ref="source:fixture",
        source_sha256="a" * 64,
        spatial_context_id="ground",
        context_sha256="b" * 64,
    )
    config = BehaviorConfig(
        scope=scope,
        config_version="test-source",
        regions=(ConfiguredRegion(region_id="room", floor_id="floor", bounds_xy_m=(0, -1, 4, 1)),),
    )
    rows = []
    for index, x in enumerate(positions):
        timestamp = index * 0.4 + (2 if gap_after is not None and index > gap_after else 0)
        point = (
            None
            if index == missing
            else ProjectedPoint(
                point_id=f"point:{index}",
                camera_id="C",
                plane_id="floor",
                timestamp=timestamp,
                world_position=(x, 0, 0),
                observation_id=f"pixel:{index}",
            )
        )
        rows.append(
            ProjectedMeasurement(
                observation_id=f"pixel:{index}",
                local_track_id="track",
                camera_id="C",
                timestamp=timestamp,
                frame_ref=f"frame:{index}",
                point=point,
                status="PROJECTED" if point else "PROJECTION_MISSING",
                uncertainty_m=0.1,
            )
        )
    # This composer receives typed projections only; no image producer or truth read.
    inference = InferenceBundle.model_construct(scope=scope, projected_measurements=tuple(rows))
    return inference, config


def run(positions: list[float], **options: Any) -> dict[str, Any]:
    inference, config = case(positions, **options)
    return compose_rules(inference, config, candidate_policies()["region_rules"])


def test_confirmed_region_entry_exit_and_sustained_dwell_keep_trigger_retract_history() -> None:
    report = run([-1, -1, 1, 1, 1, 1, 1, 1, -1, -1])
    events = {row["kind"]: row for row in report["events"]}
    assert set(events) == {"REGION_ENTRY", "REGION_EXIT", "SUSTAINED_DWELL"}
    assert all(row["support_state"] == "SUPPORTED" for row in events.values())
    assert events["REGION_ENTRY"]["state"] == "RETRACTED"
    assert events["REGION_ENTRY"]["lifecycle"][0]["at"] == pytest.approx(1.2)
    assert events["REGION_ENTRY"]["lifecycle"][1]["at"] == pytest.approx(3.6)
    assert events["SUSTAINED_DWELL"]["lifecycle"][0]["at"] == pytest.approx(2.8)
    assert events["SUSTAINED_DWELL"]["lifecycle"][1]["at"] == pytest.approx(3.2)
    assert events["REGION_EXIT"]["state"] == "TRIGGERED"
    assert events["SUSTAINED_DWELL"]["active"] is False
    assert all(len(row["source_frames"]) <= 3 for row in events.values())


def test_starting_inside_never_invents_a_confirmed_entry() -> None:
    report = run([1, 1, 1, 1, 1, 1, 1])
    entry = next(row for row in report["events"] if row["kind"] == "REGION_ENTRY")
    assert entry["support_state"] == "UNKNOWN"
    assert entry["missing_evidence"] == ["NO_VISIBLE_PRIOR_OUTSIDE_SAMPLES"]
    assert entry["lifecycle"][0]["transition"] == "UNKNOWN"


@pytest.mark.parametrize("options", [{"gap_after": 3}, {"missing": 3}])
def test_sample_or_projection_gap_breaks_sustained_evidence(options: dict[str, int]) -> None:
    report = run([1, 1, 1, 1, 1, 1, 1], **options)
    assert not any(row["kind"] == "SUSTAINED_DWELL" for row in report["events"])
    assert all(row["support_state"] == "UNKNOWN" for row in report["events"])


@pytest.mark.parametrize("positions", [[-1, -1, 1, -1, -1], [1, 1.2, 1.4, 1.6, 1.8, 2, 2.2]])
def test_short_region_touch_and_moving_transit_do_not_become_dwell(positions: list[float]) -> None:
    assert not any(row["kind"] == "SUSTAINED_DWELL" for row in run(positions)["events"])


def test_revisit_events_have_stable_distinct_dedupe_keys_and_input_not_mutated() -> None:
    inference, config = case([-1, -1, 1, 1, -1, -1, 1, 1, -1, -1])
    before = copy.deepcopy(inference.projected_measurements)
    policy = candidate_policies()["region_rules"]
    first = compose_rules(inference, config, policy)
    assert first == compose_rules(inference, config, policy)
    entries = [row for row in first["events"] if row["kind"] == "REGION_ENTRY"]
    assert len(entries) == 2 and len({row["dedupe_key"] for row in entries}) == 2
    assert inference.projected_measurements == before


@pytest.mark.parametrize(
    "mutation",
    [
        {"side_samples": True},
        {"max_gap_s": float("nan")},
        {"dwell_radius_m": -1},
        {"command": "override"},
    ],
)
def test_rule_policy_rejects_spoofed_or_unbounded_values(mutation: dict[str, Any]) -> None:
    inference, config = case([1, 1])
    with pytest.raises(ValueError, match="REGION_RULE"):
        compose_rules(inference, config, {**candidate_policies()["region_rules"], **mutation})


def test_cross_source_rule_scope_denied() -> None:
    inference, config = case([1, 1])
    other = config.model_copy(
        update={"scope": config.scope.model_copy(update={"run_id": "foreign"})}
    )
    with pytest.raises(ValueError, match="SCOPE_DENIED"):
        compose_rules(inference, other, candidate_policies()["region_rules"])
