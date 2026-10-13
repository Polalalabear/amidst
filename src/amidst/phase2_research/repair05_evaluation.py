"""Post-freeze evaluator for one 05 candidate; private truth never reaches adapters."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_evaluation import ResearchTruth, _labels, evaluate_local_pilot
from amidst.engineering.local_pilot import MODES, _save
from amidst.phase2_research.repair05_pipeline import frozen, load
from amidst.phase2_research.repair05_trace import contact_key
from amidst.research_accuracy.baseline import isolated_package
from amidst.research_accuracy.evaluation import pixel_population, supported_behavior
from amidst.research_accuracy.run import FrozenVariant

Json = dict[str, Any]


def continuity_audit(
    state: FrozenVariant, labels: dict[str, str | None], trace: Json
) -> tuple[Json, Counter[str]]:
    """Publish aggregates only; reference actor identifiers stay in this evaluator."""
    multiplicity: Counter[str] = Counter()
    gap_lengths: Counter[int] = Counter()
    missing = 0
    for track in state.perception.tracks:
        multiplicity.update(
            {label for ref in track.observation_ids if (label := labels[ref]) is not None}
        )
        missing += len(track.missing_timestamps)
        sample_times = [
            row.timestamp
            for row in state.perception.frame_statuses
            if row.camera_id == track.camera_id
            and track.timestamps[0] < row.timestamp < track.timestamps[-1]
        ]
        current = 0
        absent = set(track.missing_timestamps)
        for timestamp in sample_times:
            if timestamp in absent:
                current += 1
            elif current:
                gap_lengths[current] += 1
                current = 0
        if current:
            gap_lengths[current] += 1
    first = {
        camera: min(
            row.timestamp for row in state.perception.frame_statuses if row.camera_id == camera
        )
        for camera in {row.camera_id for row in state.perception.frame_statuses}
    }
    reset_rows = [
        row
        for row in trace["decisions"]
        if row["timestamp"] > first[row["camera_id"]] and row["decision"] != "CONTINUATION"
    ]
    return {
        "internal_missing_sample_count": missing,
        "internal_gap_length_samples_distribution": dict(gap_lengths),
        "internal_missing_definition": (
            "Registered sampled timestamps strictly inside each produced track; "
            "not actor identity fragmentation"
        ),
        "known_actor_count": len(multiplicity),
        "actor_track_membership_count": sum(multiplicity.values()),
        "actor_track_multiplicity_distribution": dict(Counter(multiplicity.values())),
        "private_actor_multiplicity_sha256": digest(sorted(multiplicity.items())),
        "noninitial_new_track_decisions": len(reset_rows),
        "noninitial_new_track_decision_reasons": dict(
            Counter(row["decision"] for row in reset_rows)
        ),
        "unlabeled_contact_count": sum(value is None for value in labels.values()),
        "labeled_contact_population_sha256": digest(
            sorted(
                (contact_key(row), labels[row.observation_id])
                for row in state.perception.measurements
            )
        ),
        "quarantined_contact_count": sum(row["quarantined"] for row in trace["decisions"]),
        "alternative_contact_count": sum(
            row.local_alternative_count > 0 for row in state.perception.measurements
        ),
        "ambiguous_frame_count": sum(
            row.status == "AMBIGUOUS_COMPONENT" for row in state.perception.frame_statuses
        ),
        "observed_contacts_invented_or_deleted": False,
    }, multiplicity


def score(row: Json) -> tuple[int, int, int, int]:
    identity, population = row["pixels_and_local_identity"], row["pixel_population"]
    return (
        identity["within_local_track_id_switches"],
        population["mixed_known_identity_tracks"],
        population["fragmented_track_count"],
        population["single_measurement_track_count"],
    )


def gates(
    baseline: Json,
    candidate: Json,
    base_multiplicity: Counter[str],
    candidate_multiplicity: Counter[str],
    *,
    test_caps: Json | None = None,
) -> Json:
    b, c = score(baseline), score(candidate)
    ba, ca = baseline["continuity_audit"], candidate["continuity_audit"]
    checks = {
        "fixed_contacts_identical": baseline["fixed_contact_population_sha256"]
        == candidate["fixed_contact_population_sha256"],
        "labeled_contacts_identical": ba["labeled_contact_population_sha256"]
        == ca["labeled_contact_population_sha256"],
        "switches_nonregression": c[0] <= b[0],
        "mixed_tracks_nonregression": c[1] <= b[1],
        "internal_missing_tracks_nonregression": c[2] <= b[2],
        "singletons_nonregression": c[3] <= b[3],
        "strict_pixel_gain": any(new < old for new, old in zip(c, b, strict=True)),
        "every_actor_track_multiplicity_nonincreasing": set(base_multiplicity)
        == set(candidate_multiplicity)
        and all(
            candidate_multiplicity[actor] <= count for actor, count in base_multiplicity.items()
        ),
        "noninitial_new_track_decisions_nonincreasing": ca["noninitial_new_track_decisions"]
        <= ba["noninitial_new_track_decisions"],
        "internal_missing_samples_nonincreasing": ca["internal_missing_sample_count"]
        <= ba["internal_missing_sample_count"],
    }
    if test_caps is not None:
        checks.update(
            {
                "test_" + key + "_cap": value <= test_caps[key]
                for key, value in zip(
                    ("switches", "mixed_tracks", "internal_missing_tracks", "singletons"),
                    c,
                    strict=True,
                )
            }
        )
    return {
        "checks": checks,
        "accepted": all(checks.values()),
        "outcome": "ACCEPTED_LOCAL_CONTINUITY_GAIN"
        if all(checks.values())
        else "REJECTED_RETAIN_BASELINE",
        "baseline_score": b,
        "candidate_score": c,
        "actor_multiplicity_increase_count": sum(
            candidate_multiplicity[actor] > count for actor, count in base_multiplicity.items()
        ),
        "actor_multiplicity_decrease_count": sum(
            candidate_multiplicity[actor] < count for actor, count in base_multiplicity.items()
        ),
        "standards_fixed_before_test": True,
        "fragmentation_metric_alone_is_insufficient": True,
    }


def evaluate(output: Path, *, test_authorized: bool = False) -> Json:
    if (output / "evaluation.json").exists():
        raise ValueError("REPAIR05_EVALUATION_ALREADY_COMPLETE")
    package, _, manifest, settings = load(output)
    if package.split == "test" and not test_authorized:
        raise ValueError("REPAIR05_TEST_COORDINATION_REQUIRED")
    states = {
        (name, mode): frozen(output, name, mode, manifest)
        for name in manifest["variants"]
        for mode in MODES
    }
    # Every state has been validated and frozen before this first truth read.
    truth = ResearchTruth.model_validate_json(package.simulation_export_path.read_bytes())
    result: Json = {
        "schema_version": "phase2.repair05.evaluation.v1",
        "split": package.split,
        "experiment_id": manifest["experiment_id"],
        "source_run_id": package.run_id,
        "source_sha256": package.source_sha256,
        "dataset_sha256": package.dataset_sha256,
        "manifest_sha256": digest(manifest),
        "config_sha256": manifest["config_sha256"],
        "fixed_contact_population_sha256": manifest["fixed_contact_population_sha256"],
        "gt_only_after_all_inference_freezes": True,
        "test_is_sealed_holdout": False,
        "formal_phase1_acceptance": False,
        "behavior_accuracy_gain_claim": False,
        "variants": {},
        "acceptance": {},
    }
    private: dict[tuple[str, str], Counter[str]] = {}
    for (name, mode), state in states.items():
        summary = evaluate_local_pilot(
            isolated_package(package, output / "evaluation_inputs" / name / mode),
            state.perception,
            state.inference,
            receipt=state.receipt,
            events=state.events.events,
            events_sha256=digest([event.model_dump(mode="json") for event in state.events.events]),
            behavior_bundle=state.events,
        )
        measurement_labels, segment_labels, _, _ = _labels(state.perception, state.inference, truth)
        trace = json.loads((output / name / mode / "trace.json").read_bytes())
        audit, private[(name, mode)] = continuity_audit(state, measurement_labels, trace)
        row = {
            "freeze_ref": state.receipt.receipt_sha256,
            "fixed_contact_population_sha256": manifest["fixed_contact_population_sha256"],
            "track_population_sha256": manifest["variants"][name][mode]["track_population_sha256"],
            "candidate_pool_sha256": state.inference.association_pool_sha256,
            "pixels_and_local_identity": summary["pixels_and_local_identity"],
            "pixel_population": pixel_population(state, measurement_labels),
            "continuity_audit": audit,
            "retrieval": summary["retrieval"],
            "behavior": supported_behavior(state, truth, segment_labels),
            "behavior_unmasked_candidate_diagnostic": summary["behavior"],
            "trace_summary": {key: value for key, value in trace.items() if key != "decisions"},
        }
        result["variants"].setdefault(name, {})[mode] = row
    for mode in MODES:
        result["acceptance"][mode] = gates(
            result["variants"]["baseline"][mode],
            result["variants"]["candidate"][mode],
            private[("baseline", mode)],
            private[("candidate", mode)],
            test_caps=settings["test_caps"] if package.split == "test" else None,
        )
    development_eligible = (
        package.split == "development" or manifest["development_selected_variant"] == "candidate"
    )
    result["active_variant"] = (
        "candidate"
        if development_eligible and all(row["accepted"] for row in result["acceptance"].values())
        else "baseline"
    )
    result["development_selection_required_for_test_activation"] = True
    _save(output / "evaluation.json", result)
    persisted: Json = json.loads((output / "evaluation.json").read_bytes())
    _save(
        output / "evaluation_receipt.json",
        {
            "schema_version": "phase2.repair05.evaluation-certificate.v1",
            "manifest_sha256": digest(manifest),
            "evaluation_sha256": digest(persisted),
            "algorithms": manifest["algorithms"],
            "all_modes_frozen_before_truth": True,
            "single_post_freeze_evaluation": True,
        },
    )
    return persisted


def select_development(output: Path) -> Json:
    package, _, manifest, _ = load(output)
    if package.split != "development":
        raise ValueError("REPAIR05_SELECTION_REQUIRES_DEVELOPMENT")
    result = json.loads((output / "evaluation.json").read_bytes())
    if result["manifest_sha256"] != digest(manifest):
        raise ValueError("REPAIR05_SELECTION_BINDING_MISMATCH")
    return {
        "schema_version": "phase2.repair05.selection.v1",
        "split": "development",
        "manifest_sha256": digest(manifest),
        "evaluation_sha256": digest(result),
        "config_sha256": manifest["config_sha256"],
        "algorithms": manifest["algorithms"],
        "candidate_count": 1,
        "selected_variant": result["active_variant"],
        "acceptance": result["acceptance"],
        "test_consulted_for_selection": False,
    }
