"""Independent controlled cases for the single-factor 05 candidate and frozen gates."""

from __future__ import annotations

import copy
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from amidst.engineering import perception as detector
from amidst.engineering.perception import FrameStatus, Measurement, PerceptionResult
from amidst.phase2_research import repair05_adapter, repair05_evaluation, repair05_pipeline
from amidst.phase2_research.pipeline import _contacts
from amidst.phase2_research.repair05_trace import trace_assignment
from amidst.phase2_research.repair05_tracker import (
    Strategy,
    clean_window,
    local_functions,
    reassociate,
    robust_prediction,
)
from amidst.research_accuracy import pixel

Json = dict[str, Any]


def detected(points: list[float], *, timestamps: list[float] | None = None) -> PerceptionResult:
    times = timestamps or [index * 0.4 for index in range(len(points))]
    measurements = tuple(
        Measurement(
            observation_id=f"pixel:model:run:C:{index:04d}:00",
            local_track_id=f"old:{index}",
            camera_id="C",
            model_id="model",
            run_id="run",
            timestamp=timestamp,
            frame_ref=f"frame:{index}",
            bbox_xyxy=(x - 3, 10, x + 4, 41),
            contact_pixel=(x, 40),
            appearance=(20, 40, 200),
            uncertainty=0.25,
            input_sha256="a" * 64,
            status="DETECTED",
            local_alternative_count=0,
            evidence_refs=(f"frame:{index}",),
        )
        for index, (timestamp, x) in enumerate(zip(times, points, strict=True))
    )
    return PerceptionResult(
        model_id="model",
        run_id="run",
        measurements=measurements,
        tracks=(),
        frame_statuses=tuple(
            FrameStatus(
                frame_ref=f"frame:{index}",
                camera_id="C",
                timestamp=timestamp,
                status="MEASURED",
                measurement_count=1,
            )
            for index, timestamp in enumerate(times)
        ),
        input_manifest_sha256="b" * 64,
        producer_sha256=sha256(Path(detector.__file__).read_bytes()).hexdigest(),
        complete=True,
    )


def test_robust_history_recovers_prediction_mismatch_without_changing_contacts() -> None:
    fixed = detected([10, 14, 38, 36])
    before = fixed.model_dump_json()
    baseline = reassociate(fixed, pixel.PixelContinuityConfig(), strategy="BASELINE")
    candidate = reassociate(fixed, pixel.PixelContinuityConfig())
    assert len(baseline.tracks) == 2 and len(candidate.tracks) == 1
    assert candidate.tracks[0].missing_timestamps == ()
    assert _contacts(candidate) == _contacts(fixed)
    assert fixed.model_dump_json() == before
    _, base_trace = trace_assignment(fixed, pixel.PixelContinuityConfig())
    _, new_trace = trace_assignment(
        fixed, pixel.PixelContinuityConfig(), strategy="ROBUST_THREE_CLEAN"
    )
    assert base_trace["decisions"][-1]["decision"] == "NO_ELIGIBLE_CONTINUATION"
    assert new_trace["decisions"][-1]["decision"] == "CONTINUATION"
    assert new_trace["decisions"][-1]["histories"][0]["prediction_residual_px"] == pytest.approx(16)


def test_constant_velocity_and_short_history_match_inherited_tracker_exactly() -> None:
    fixed = detected([10, 14, 18, 22, 26])
    assert reassociate(fixed, pixel.PixelContinuityConfig()) == pixel.reassociate_perception_v2(
        fixed
    )
    two = detected([10, 14])
    assert reassociate(two, pixel.PixelContinuityConfig()) == pixel.reassociate_perception_v2(two)


@pytest.mark.parametrize(
    "mutation",
    ["partial", "alternative", "uncertainty", "long_gap", "duplicate", "short", "velocity_off"],
)
def test_robust_history_requires_three_clean_contacts(mutation: str) -> None:
    config = pixel.PixelContinuityConfig()
    rows = list(detected([10, 14, 38]).measurements)
    if mutation == "partial":
        rows[1] = rows[1].model_copy(update={"status": "MERGED_OR_PARTIAL"})
    elif mutation == "alternative":
        rows[1] = rows[1].model_copy(update={"local_alternative_count": 1})
    elif mutation == "uncertainty":
        rows[1] = rows[1].model_copy(update={"uncertainty": 0.75})
    elif mutation == "long_gap":
        rows[2] = rows[2].model_copy(update={"timestamp": 2.0})
    elif mutation == "duplicate":
        rows[1] = rows[1].model_copy(update={"timestamp": 0.0})
    elif mutation == "short":
        rows = rows[:2]
    else:
        config = config.model_copy(update={"use_velocity": False})
    assert robust_prediction(rows, 2.4, config) is None
    if mutation != "velocity_off":
        assert not clean_window(rows, config)


def test_quarantined_contact_and_alternatives_remain_explicit() -> None:
    fixed = detected([10, 14, 18, 22])
    partial = fixed.measurements[2].model_copy(
        update={"status": "MERGED_OR_PARTIAL", "local_alternative_count": 2, "uncertainty": 0.75}
    )
    fixed = fixed.model_copy(
        update={"measurements": (*fixed.measurements[:2], partial, fixed.measurements[3])}
    )
    result, trace = trace_assignment(
        fixed, pixel.PixelContinuityConfig(), strategy="ROBUST_THREE_CLEAN"
    )
    assert len(result.measurements) == 4
    assert result.measurements[2].status == "MERGED_OR_PARTIAL"
    assert result.measurements[2].uncertainty >= 0.75
    assert result.measurements[2].local_alternative_count >= 2
    assert trace["decision_counts"]["QUARANTINED_MERGE"] == 1
    assert trace["continuations_from_partial_prediction_anchor"] == 0


def test_concurrent_traces_and_trackers_never_mutate_original_module() -> None:
    identities = (
        pixel._prediction,
        pixel._candidates,
        pixel._assign,
        pixel.reassociate_perception_v2,
    )
    fixed = detected([10, 14, 38, 36])
    expected = pixel.reassociate_perception_v2(fixed)

    def run(index: int) -> int:
        strategy: Strategy = "BASELINE" if index % 2 else "ROBUST_THREE_CLEAN"
        result, _ = trace_assignment(fixed, pixel.PixelContinuityConfig(), strategy=strategy)
        assert identities == (
            pixel._prediction,
            pixel._candidates,
            pixel._assign,
            pixel.reassociate_perception_v2,
        )
        assert pixel.reassociate_perception_v2(fixed) == expected
        return len(result.tracks)

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(run, range(32))) == [1, 2] * 16
    assert identities == (
        pixel._prediction,
        pixel._candidates,
        pixel._assign,
        pixel.reassociate_perception_v2,
    )


def test_exception_and_local_dependency_injection_preserve_module_identity() -> None:
    identities = (pixel._prediction, pixel._candidates, pixel._assign)
    fixed = detected([10, 14, 38, 36])
    functions = local_functions("ROBUST_THREE_CLEAN")

    def deny(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("private injected failure")

    functions["_prediction"] = deny
    with pytest.raises(RuntimeError, match="private injected failure"):
        functions["reassociate_perception_v2"](fixed)
    with pytest.raises(ValueError, match="bound v1 RGB detector"):
        trace_assignment(
            fixed.model_copy(update={"producer_sha256": "0" * 64}), pixel.PixelContinuityConfig()
        )
    assert identities == (pixel._prediction, pixel._candidates, pixel._assign)


def test_unknown_strategy_is_rejected() -> None:
    with pytest.raises(ValueError, match="STRATEGY_DENIED"):
        reassociate(detected([10]), pixel.PixelContinuityConfig(), strategy="oracle")  # type: ignore[arg-type]


def metric(value: tuple[int, int, int, int], *, resets: int = 6, missing: int = 6) -> Json:
    return {
        "fixed_contact_population_sha256": "a" * 64,
        "pixels_and_local_identity": {"within_local_track_id_switches": value[0]},
        "pixel_population": {
            "mixed_known_identity_tracks": value[1],
            "fragmented_track_count": value[2],
            "single_measurement_track_count": value[3],
        },
        "continuity_audit": {
            "labeled_contact_population_sha256": "b" * 64,
            "noninitial_new_track_decisions": resets,
            "internal_missing_sample_count": missing,
        },
    }


@pytest.mark.parametrize(
    "failure",
    [
        "multiplicity",
        "reset",
        "missing",
        "contacts",
        "labels",
        "switches",
        "mixed",
        "singleton",
        "no_gain",
    ],
)
def test_gate_rejects_reset_or_population_gaming_despite_fragmentation_reduction(
    failure: str,
) -> None:
    baseline, candidate = metric((4, 3, 7, 6)), metric((4, 3, 6, 6))
    base, new = Counter({"A": 2, "B": 1}), Counter({"A": 2, "B": 1})
    if failure == "multiplicity":
        new["A"] = 3
    elif failure == "reset":
        candidate["continuity_audit"]["noninitial_new_track_decisions"] = 7
    elif failure == "missing":
        candidate["continuity_audit"]["internal_missing_sample_count"] = 7
    elif failure == "contacts":
        candidate["fixed_contact_population_sha256"] = "c" * 64
    elif failure == "labels":
        candidate["continuity_audit"]["labeled_contact_population_sha256"] = "c" * 64
    elif failure == "no_gain":
        candidate = copy.deepcopy(baseline)
    else:
        index = {"switches": 0, "mixed": 1, "singleton": 3}[failure]
        values = [4, 3, 6, 6]
        values[index] += 1
        candidate = metric(tuple(values))  # type: ignore[arg-type]
    result = repair05_evaluation.gates(
        baseline, candidate, base, new, test_caps=repair05_pipeline.policy()["test_caps"]
    )
    assert not result["accepted"]
    assert result["fragmentation_metric_alone_is_insufficient"]


def test_gate_accepts_nonresetting_gain_and_test_caps_are_predeclared() -> None:
    result = repair05_evaluation.gates(
        metric((4, 3, 7, 6)),
        metric((4, 3, 6, 6)),
        Counter({"A": 2}),
        Counter({"A": 1}),
        test_caps=repair05_pipeline.policy()["test_caps"],
    )
    assert result["accepted"] and result["actor_multiplicity_decrease_count"] == 1
    assert repair05_pipeline.policy()["test_caps"] == {
        "switches": 4,
        "mixed_tracks": 3,
        "internal_missing_tracks": 6,
        "singletons": 6,
    }


def test_test_build_requires_coordinated_authorization_before_loading_rgb(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "package.json").write_text('{"split":"test"}')

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("source RGB must not be loaded")

    monkeypatch.setattr(repair05_pipeline, "_load", denied)
    with pytest.raises(ValueError, match="TEST_COORDINATION_REQUIRED"):
        repair05_pipeline.build(source, tmp_path / "out", experiment_id="one")
    with pytest.raises(ValueError, match="FROZEN_DEVELOPMENT_SELECTION_REQUIRED"):
        repair05_pipeline.build(source, tmp_path / "out", experiment_id="one", test_authorized=True)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("condition", ["occupied", "inside_source", "bad_id"])
def test_build_refuses_unsafe_output_before_source_reads(tmp_path: Path, condition: str) -> None:
    source, output, experiment = tmp_path / "source", tmp_path / "out", "one"
    if condition == "occupied":
        output.mkdir()
        (output / "old.json").write_text("frozen")
    elif condition == "inside_source":
        output = source / "out"
    else:
        experiment = "../escape"
    with pytest.raises(ValueError, match="NEW_EMPTY_OUTPUT_REQUIRED"):
        repair05_pipeline.build(source, output, experiment_id=experiment)


def test_aggregate_is_unavailable_without_independent_registered_digest() -> None:
    service = object.__new__(repair05_adapter.Repair05Service)
    service.binding = {"scene_id": "scene", "source_run_id": "run"}
    service.manifest = {"algorithms": repair05_pipeline.algorithms()}
    service.integrity_checks = {}
    service.expected_evaluation_sha256 = None
    assert service.diagnostics()["reason"] == "AGGREGATE_NOT_REGISTERED"


@pytest.mark.parametrize(
    "start,end", [(-1, 4), (0, 25), (4, 3), (True, 4), (0, float("nan")), (0, float("inf"))]
)
def test_query_rejects_out_of_source_or_nonfinite_windows(start: float, end: float) -> None:
    service = object.__new__(repair05_adapter.Repair05Service)
    service.binding = {"scene_id": "scene", "source_run_id": "run"}
    service.manifest = {"algorithms": repair05_pipeline.algorithms()}
    service.integrity_checks = {}
    service.cameras, service.time_range = {"C"}, [0, 24]
    with pytest.raises(ValueError, match="TIME_SCOPE_DENIED"):
        service.query("scene", "run", "C", start, end)


def test_runtime_adapter_has_no_evaluator_import_or_reference_fields() -> None:
    source = Path(repair05_adapter.__file__).read_text()
    assert "from amidst.phase2_research.repair05_evaluation" not in source
    assert "ResearchTruth" not in source and "simulation_export_path" not in source
    _, trace = trace_assignment(detected([10, 14, 38, 36]), pixel.PixelContinuityConfig())
    assert "actor_identity" not in json.dumps(trace)
    assert trace["input_contact_count"] == 4 and not trace["gt_or_reference_content_read"]
