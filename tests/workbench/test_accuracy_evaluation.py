"""Aggregate-only accuracy certification, independent of producers and truth."""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from amidst.engineering.access import digest
from amidst.research_accuracy import run
from amidst.workbench import accuracy_evaluation as evaluation

Json = dict[str, Any]


@pytest.fixture
def aggregates() -> tuple[Json, Json, dict[tuple[str, str], Json]]:
    """A small pre-existing aggregate: changed pool, UNKNOWN and a regression."""
    manifest: Json = {
        "experiment_id": "aggregate-test-v2",
        "source_run_id": "source-test-v1",
        "split": "test",
        "source_sha256": "1" * 64,
        "dataset_sha256": "2" * 64,
        "config_sha256": "3" * 64,
        "algorithms": {"research_accuracy/evaluation.py": "4" * 64},
        "variants": {},
    }
    bindings: dict[tuple[str, str], Json] = {}
    variants: Json = {}
    for variant in evaluation.VARIANTS:
        manifest["variants"][variant], variants[variant] = {}, {}
        changed = variant in {"pixel_only", "end_to_end"}
        pool, pair_count, positives, queries = (
            ("b" * 64, 8, 4, 2)
            if changed
            else (
                "a" * 64,
                3,
                2,
                1,
            )
        )
        for mode in evaluation.MODES:
            manifest["variants"][variant][mode] = {
                "candidate_pool_sha256": pool,
                "receipt_sha256": "5" * 64,
                "appearance_sha256": None,
            }
            bindings[variant, mode] = {
                "inference_sha256": "6" * 64,
                "track_population_sha256": "7" * 64,
                "measurement_count": 10,
                "track_count": 4 if changed else 2,
                "segment_count": 5 if changed else 2,
                "pair_count": pair_count,
                "source_config_sha256": "8" * 64,
                "model_id": "synthetic-model",
            }
            row = dict.fromkeys(evaluation._ROW_FIELDS, {})
            row.update(
                {
                    "run_id": manifest["source_run_id"],
                    "experiment_id": manifest["experiment_id"],
                    "variant": variant,
                    "mode": mode,
                    "model_id": "synthetic-model",
                    "dataset_sha256": manifest["dataset_sha256"],
                    "config_sha256": "8" * 64,
                    "runtime_config_sha256": manifest["config_sha256"],
                    "freeze_sha256": "5" * 64,
                    "inference_sha256": "6" * 64,
                    "origin": "SYNTHETIC",
                    "formal_phase1_acceptance": False,
                    "external_model_calls": False,
                    "behavior_bundle_binding_verified": True,
                    "schema_version": "local.camera.evaluation.v1",
                    "status": "E1_SYNTHETIC_PILOT_MEASURED",
                    "split": "test",
                    "pixel_population": {
                        "track_count": 4 if changed else 2,
                        "fragmented_track_count": 2 if changed else 0,
                        "mixed_known_identity_tracks": 0,
                        "single_measurement_track_count": 0,
                    },
                    "pixels_and_local_identity": {
                        "measurement_count": 10,
                        "eligible_visible_actor_contacts": 12,
                        "within_local_track_id_switches": 1 if changed else 2,
                        "one_to_one_visible_contact_recall": 0.75,
                        "ground_contact_error_m": {"rms": 0.25},
                    },
                    "retrieval": {
                        "same_identity_eligible_pair_count": positives,
                        "retrieved_pair_count": pair_count,
                        "records_read": 8,
                        "index_entries_touched": 6,
                    },
                    "association_all_provisional_hypotheses": {
                        "true_link_count": positives,
                        "true_positive": 1,
                        "resolved_link_count": 2,
                        "predicted_link_count": 3,
                        "pair_level_false_merge_count": 1,
                        "pair_level_missed_link_count": positives - 1,
                        "unresolved_link_count": 1,
                        "same_identity_eligible_pair_precision": 0.5,
                        "same_identity_eligible_pair_recall": 1 / positives,
                    },
                    "weighted_fixed_pool_feature_ablations": {
                        name: {
                            "candidate_pool_sha256": pool,
                            "eligible_query_count": queries,
                            "true_link_count": positives,
                            "hard_physics_preserved": True,
                            "scores_are_probabilities": False,
                            "identity_candidate_recall_at_k": {"1": 0.5, "3": 1.0, "5": 1.0},
                        }
                        for name in evaluation.ABLATIONS
                    },
                    "behavior": {
                        "evidence_unknown_count": 1,
                        "visible_candidate_count": 5,
                        "groups": {
                            "visible_supported": {
                                "per_kind": {
                                    kind: {
                                        "true_positive": 0,
                                        "false_positive": 0,
                                        "false_negative": 1,
                                        "unresolved": 1,
                                        "precision": None,
                                        "recall": 0.0,
                                    }
                                    for kind in evaluation.KINDS
                                }
                            }
                        },
                    },
                }
            )
            variants[variant][mode] = row
    value: Json = {
        "schema_version": "accuracy.comparison.v2",
        "experiment_id": manifest["experiment_id"],
        "source_run_id": manifest["source_run_id"],
        "split": "test",
        "manifest_sha256": digest(manifest),
        "config_sha256": manifest["config_sha256"],
        "dataset_sha256": manifest["dataset_sha256"],
        "evaluator_sha256": "4" * 64,
        "evaluator_policy": {},
        "formal_phase1_acceptance": False,
        "test_is_sealed_holdout": False,
        "variants": variants,
        "comparison": dict.fromkeys(evaluation.VARIANTS, {}),
    }
    return value, manifest, bindings


def _certificate(value: Json, manifest: Json) -> evaluation.AccuracyEvaluationCertificate:
    return evaluation.AccuracyEvaluationCertificate(digest(manifest), digest(value))


def test_certified_comparison_preserves_populations_false_negatives_and_regressions(
    aggregates: tuple[Json, Json, dict[tuple[str, str], Json]],
) -> None:
    value, manifest, bindings = aggregates
    result = evaluation.project_accuracy_evaluation(
        value, manifest, bindings, _certificate(value, manifest)
    )
    selected = next(
        row
        for row in result["variants"]
        if row["variant"] == "end_to_end" and row["mode"] == "photos_only"
    )
    assert selected["behavior"]["unknown_count"] == 1
    assert selected["behavior"]["per_kind"]["CORNER"]["false_negative"] == 1
    assert selected["behavior"]["per_kind"]["CORNER"]["reference_count"] == 1
    assert selected["population"]["eligible_pair_positives"] == 4
    assert selected["population"]["eligible_queries"] == 2
    assert len(result["variants"]) == 16
    comparison = next(
        row
        for row in result["comparisons"]
        if row["variant"] == "end_to_end" and row["mode"] == "photos_only"
    )
    assert comparison["population_comparable"] is False
    assert comparison["baseline_pool_sha256"] != comparison["candidate_pool_sha256"]
    assert any(
        row["metric"] == "fragmented_tracks" and row["value"] == 2 for row in result["regressions"]
    )
    assert not result["formal_phase1_acceptance"] and not result["test_is_sealed_holdout"]
    assert "evaluation_truth_sha256" not in json.dumps(result)


@pytest.mark.parametrize(
    "mutation",
    [
        "experiment",
        "freeze",
        "denominator",
        "ground_truth",
        "private_path",
        "unknown_field",
        "nonfinite",
    ],
)
def test_even_server_pinned_aggregate_refuses_invalid_binding_or_private_content(
    aggregates: tuple[Json, Json, dict[tuple[str, str], Json]],
    mutation: str,
) -> None:
    value, manifest, bindings = aggregates
    original_certificate = _certificate(value, manifest)
    row = value["variants"]["end_to_end"]["photos_only"]
    if mutation == "experiment":
        value["experiment_id"] = "another-experiment"
    elif mutation == "freeze":
        row["freeze_sha256"] = "f" * 64
    elif mutation == "denominator":
        row["behavior"]["groups"]["visible_supported"]["per_kind"]["CORNER"]["recall"] = 1
    elif mutation == "ground_truth":
        row["pixel_population"]["actor_id"] = "actor-1"
    elif mutation == "private_path":
        row["limitations"] = ["file:///private/truth.json"]
    elif mutation == "unknown_field":
        row["extra_metadata"] = {"message": "not an approved aggregate field"}
    else:
        row["pixels_and_local_identity"]["ground_contact_error_m"]["rms"] = float("inf")
    with pytest.raises(evaluation.AccuracyEvaluationError):
        evaluation.project_accuracy_evaluation(
            value,
            manifest,
            bindings,
            original_certificate if mutation == "nonfinite" else _certificate(value, manifest),
        )


def test_same_pool_digest_with_changed_query_denominator_is_not_comparable(
    aggregates: tuple[Json, Json, dict[tuple[str, str], Json]],
) -> None:
    value, manifest, bindings = aggregates
    for mode in evaluation.MODES:
        for ablation in value["variants"]["prior_only"][mode][
            "weighted_fixed_pool_feature_ablations"
        ].values():
            ablation["eligible_query_count"] = 2
    result = evaluation.project_accuracy_evaluation(
        value, manifest, bindings, _certificate(value, manifest)
    )
    comparison = next(row for row in result["comparisons"] if row["variant"] == "prior_only")
    assert comparison["candidate_pool_sha256"] == comparison["baseline_pool_sha256"]
    assert comparison["eligible_queries"] != comparison["baseline_queries"]
    assert comparison["population_comparable"] is False


def test_content_certificate_is_independent_of_requested_metrics(
    aggregates: tuple[Json, Json, dict[tuple[str, str], Json]],
) -> None:
    value, manifest, bindings = aggregates
    certificate = _certificate(value, manifest)
    value["variants"]["baseline"]["photos_only"]["pixels_and_local_identity"][
        "within_local_track_id_switches"
    ] = 999
    with pytest.raises(evaluation.AccuracyEvaluationError, match="CONTENT_HASH_MISMATCH"):
        evaluation.project_accuracy_evaluation(value, manifest, bindings, certificate)


@pytest.fixture
def reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    aggregates: tuple[Json, Json, dict[tuple[str, str], Json]],
) -> evaluation.AccuracyEvaluationReader:
    value, manifest, bindings = aggregates
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    (tmp_path / "comparison.json").write_text(json.dumps(value))
    monkeypatch.setitem(
        evaluation._CERTIFICATES, manifest["experiment_id"], _certificate(value, manifest)
    )
    package = SimpleNamespace(config_sha256="8" * 64, model_id="synthetic-model")
    monkeypatch.setattr(run, "load", lambda _: (package, None, manifest, {}))

    def frozen(_: Path, variant: str, mode: str, *_args: Any) -> Any:
        row = bindings[variant, mode]
        return SimpleNamespace(
            receipt=SimpleNamespace(
                inference_sha256=row["inference_sha256"],
                measurement_sha256=row["track_population_sha256"],
            ),
            perception=SimpleNamespace(
                measurements=[None] * row["measurement_count"], tracks=[None] * row["track_count"]
            ),
            inference=SimpleNamespace(
                local_record_maps=[None] * row["segment_count"], pair_count=row["pair_count"]
            ),
        )

    monkeypatch.setattr(run, "frozen", frozen)
    return evaluation.AccuracyEvaluationReader(tmp_path, manifest)


def test_reader_rejects_stale_previous_result_after_content_or_manifest_change(
    reader: evaluation.AccuracyEvaluationReader,
) -> None:
    assert reader.evaluation()["status"] == "CERTIFIED_LOCAL_SYNTHETIC"
    path = reader.root / "comparison.json"
    value = json.loads(path.read_bytes())
    value["variants"]["baseline"]["photos_only"]["pixels_and_local_identity"][
        "within_local_track_id_switches"
    ] = 999
    path.write_text(json.dumps(value))
    assert reader.evaluation() == {
        "status": "STALE",
        "reason": "ACCURACY_EVALUATION_CONTENT_HASH_MISMATCH",
    }
    path = reader.root / "manifest.json"
    value = json.loads(path.read_bytes())
    value["dataset_sha256"] = "f" * 64
    path.write_text(json.dumps(value))
    assert reader.evaluation()["reason"] == "ACCURACY_EVALUATION_BINDING_MISMATCH"


@pytest.mark.parametrize("name", ["comparison.json", "baseline", "manifest.json"])
def test_symlink_refusal_happens_before_truth_can_be_opened(
    reader: evaluation.AccuracyEvaluationReader,
    tmp_path: Path,
    name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    truth = tmp_path / "ground_truth.json"
    truth.write_text('{"target_id":"must-never-read"}')
    path = reader.root / name
    if path.exists():
        path.unlink()
    path.symlink_to(truth)
    original_open = evaluation.os.open

    def audited_open(path: str | bytes | Path, *args: Any, **kwargs: Any) -> int:
        assert Path(path).resolve() != truth.resolve()
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(evaluation.os, "open", audited_open)
    assert reader.evaluation()["reason"] == "ACCURACY_EVALUATION_REFERENCE_DENIED"


def test_bounded_reads_duplicates_and_missing_certificate_fail_closed(
    reader: evaluation.AccuracyEvaluationReader,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = reader.root / "comparison.json"
    original = path.read_bytes()
    path.write_bytes(b" " * (evaluation.MAX_COMPARISON_BYTES + 1))
    assert reader.evaluation()["reason"] == "ACCURACY_EVALUATION_PAYLOAD_TOO_LARGE"
    path.write_text('{"schema_version":"accuracy.comparison.v2","schema_version":"duplicate"}')
    assert reader.evaluation()["reason"] == "DUPLICATE_ACCURACY_AGGREGATE_FIELD"
    path.write_bytes(original)
    monkeypatch.delitem(evaluation._CERTIFICATES, reader.manifest["experiment_id"])
    assert reader.evaluation()["reason"] == "ACCURACY_EVALUATION_CONTENT_CERTIFICATE_MISSING"


def test_fifo_is_refused_without_blocking_a_query(
    reader: evaluation.AccuracyEvaluationReader,
) -> None:
    path = reader.root / "comparison.json"
    path.unlink()
    os.mkfifo(path)
    assert reader.evaluation()["reason"] == "ACCURACY_EVALUATION_REFERENCE_DENIED"


def test_reader_never_calls_producer_evaluator_or_opens_truth(
    reader: evaluation.AccuracyEvaluationReader,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from amidst.research_accuracy import evaluation as truth_evaluator

    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("query cannot execute a producer or truth evaluator")

    for name in ("produce_perception", "produce_perception_v2", "build"):
        monkeypatch.setattr(run, name, forbidden)
    monkeypatch.setattr(truth_evaluator, "evaluate", forbidden)
    before = copy.deepcopy(reader.manifest)
    assert reader.evaluation()["status"] == "CERTIFIED_LOCAL_SYNTHETIC"
    assert reader.manifest == before
