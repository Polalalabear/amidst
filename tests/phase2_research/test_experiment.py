"""Development selection, immutable outputs and fixed detector populations."""

from __future__ import annotations

import copy
import json
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from amidst.engineering import perception as detector
from amidst.engineering.perception import FrameStatus, Measurement, PerceptionResult
from amidst.phase2_research import evaluation, pipeline
from amidst.phase2_research.continuity import reassociate
from amidst.research_accuracy.pixel import PixelContinuityConfig


def detected() -> PerceptionResult:
    rows = tuple(
        Measurement(
            observation_id=f"sample:{i}",
            local_track_id=f"old:{i}",
            camera_id="C",
            model_id="model",
            run_id="run",
            timestamp=i * 0.4,
            frame_ref=f"frame:{i}",
            bbox_xyxy=(10 + i, 10, 17 + i, 41),
            contact_pixel=(13 + i, 40),
            appearance=(20, 40, 200),
            uncertainty=0.75 if i == 1 else 0.25,
            input_sha256="a" * 64,
            status="MERGED_OR_PARTIAL" if i == 1 else "DETECTED",
            local_alternative_count=1 if i == 1 else 0,
            evidence_refs=(f"frame:{i}",),
        )
        for i in range(3)
    )
    return PerceptionResult(
        model_id="model",
        run_id="run",
        measurements=rows,
        tracks=(),
        frame_statuses=tuple(
            FrameStatus(
                frame_ref=f"frame:{i}",
                camera_id="C",
                timestamp=i * 0.4,
                status="MEASURED",
                measurement_count=1,
            )
            for i in range(3)
        ),
        input_manifest_sha256="b" * 64,
        producer_sha256=sha256(Path(detector.__file__).read_bytes()).hexdigest(),
        complete=True,
    )


def test_partial_continuation_preserves_contacts_uncertainty_and_source_immutability() -> None:
    fixed = detected()
    before = fixed.model_dump_json()
    result = reassociate(fixed, PixelContinuityConfig(), partial_mode="UNAMBIGUOUS_PARTIAL")
    assert fixed.model_dump_json() == before
    assert pipeline._contacts(result) == pipeline._contacts(fixed)
    assert result.measurements[0].local_track_id == result.measurements[1].local_track_id
    assert result.measurements[1].status == "MERGED_OR_PARTIAL"
    assert result.measurements[1].uncertainty >= 0.75
    assert result.measurements[1].local_alternative_count >= 1
    assert len(result.measurements) == 3
    assert result == reassociate(fixed, PixelContinuityConfig(), partial_mode="UNAMBIGUOUS_PARTIAL")


def test_partial_policy_refuses_spoofed_detector_and_unsupported_policy() -> None:
    with pytest.raises(ValueError, match="bound v1 RGB detector"):
        reassociate(
            detected().model_copy(update={"producer_sha256": "0" * 64}),
            PixelContinuityConfig(),
            partial_mode="UNAMBIGUOUS_PARTIAL",
        )
    with pytest.raises(ValueError, match="POLICY_DENIED"):
        reassociate(detected(), PixelContinuityConfig(), partial_mode="oracle")


@pytest.mark.parametrize("mutation", ["occupied", "inside_source", "bad_id", "wrong_version"])
def test_build_refuses_existing_or_unbound_outputs_before_loading_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "out"
    policy = pipeline.candidate_policies()
    experiment = "experiment"
    if mutation == "occupied":
        output.mkdir()
        (output / "existing.json").write_text("immutable")
    elif mutation == "inside_source":
        output = source / "out"
    elif mutation == "bad_id":
        experiment = "../escape"
    else:
        policy["version"] = "old"

    def denied(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("invalid output should fail before source reads")

    monkeypatch.setattr(pipeline, "_load", denied)
    with pytest.raises(ValueError, match="NEW_EMPTY_BOUND_OUTPUT"):
        pipeline.build(source, output, policy, experiment_id=experiment)


def metric(score: tuple[int, int, int, int], *, tp: int = 1, fp: int = 1) -> dict[str, Any]:
    return {
        "photos_only": {
            "pixels_and_local_identity": {"within_local_track_id_switches": score[0]},
            "pixel_population": {
                "mixed_known_identity_tracks": score[1],
                "fragmented_track_count": score[2],
                "single_measurement_track_count": score[3],
            },
            "behavior": {
                "groups": {
                    "visible_supported": {
                        "per_kind": {
                            "DWELL": {"true_positive": tp, "false_positive": fp},
                        }
                    }
                }
            },
        },
    }


def selection_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    policy = pipeline.candidate_policies()
    policy["variants"]["pareto"] = copy.deepcopy(policy["variants"]["baseline"])
    monkeypatch.setattr(
        evaluation, "load", lambda _: (SimpleNamespace(split="development"), None, {}, policy)
    )
    rows = {
        "baseline": metric((3, 2, 2, 2)),
        "pareto": metric((3, 2, 1, 1)),
        "strict_prediction": metric((2, 2, 2, 3)),
        "reliable_dwell": metric((3, 2, 2, 2), tp=0, fp=0),
    }
    (tmp_path / "evaluation.json").write_text(json.dumps({"variants": rows}))
    return rows


def test_development_selection_rejects_switch_singleton_and_fp_tp_tradeoffs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selection_fixture(tmp_path, monkeypatch)
    selected = evaluation.select_development(tmp_path)
    assert selected["pixel_variant"] == "pareto"
    assert selected["behavior_gate"] == "NO_GAIN_RETAIN_BASELINE"
    assert "reliable_dwell" not in selected["policy"]["variants"]["selected"]
    assert set(selected["policy"]["variants"]) == {"baseline", "selected"}


def test_no_pareto_gain_retains_baseline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = selection_fixture(tmp_path, monkeypatch)
    rows["pareto"] = metric((4, 2, 1, 1))
    (tmp_path / "evaluation.json").write_text(json.dumps({"variants": rows}))
    selected = evaluation.select_development(tmp_path)
    assert selected["pixel_variant"] == "baseline"
    assert selected["pixel_gate"] == "NO_GAIN_RETAIN_BASELINE"


def test_test_split_is_never_used_for_parameter_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(evaluation, "load", lambda _: (SimpleNamespace(split="test"), None, {}, {}))
    with pytest.raises(ValueError, match="REQUIRES_DEVELOPMENT"):
        evaluation.select_development(tmp_path)
    assert not (tmp_path / "evaluation.json").exists()
