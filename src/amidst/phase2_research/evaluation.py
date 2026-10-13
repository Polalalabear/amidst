"""Independent post-freeze synthetic evaluation; never imported by runtime adapters."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_evaluation import (
    ResearchTruth,
    _inventory,
    _labels,
    _link_metrics,
    evaluate_local_pilot,
)
from amidst.engineering.local_pilot import MODES, _save
from amidst.phase2_research.pipeline import frozen, load
from amidst.research_accuracy.appearance_evaluation import evaluate_appearance
from amidst.research_accuracy.association import AssociationConfig, RGBDescriptorBundle
from amidst.research_accuracy.baseline import isolated_package
from amidst.research_accuracy.evaluation import (
    feature_ablations,
    pixel_population,
    supported_behavior,
)

Json = dict[str, Any]


def _persist_evaluation(output: Path, result: Json, manifest: Json) -> Json:
    _save(output / "evaluation.json", result)
    # Integer histogram keys become strings in JSON; certify the saved public
    # representation, whose sorted canonical digest may differ from memory.
    persisted: Json = json.loads((output / "evaluation.json").read_bytes())
    _save(
        output / "evaluation_receipt.json",
        {
            "manifest_sha256": digest(manifest),
            "evaluation_sha256": digest(persisted),
            "algorithms": manifest["algorithms"],
            "all_modes_frozen_before_truth": True,
        },
    )
    return persisted


def evaluate(output: Path) -> Json:
    if (output / "evaluation.json").exists():
        raise ValueError("RESEARCH_EVALUATION_ALREADY_COMPLETE")
    package, registry, manifest, _ = load(output)
    # Certify every saved variant/mode before the first independent truth read.
    states = {
        (name, mode): frozen(output, name, mode, manifest)
        for name in manifest["variants"]
        for mode in MODES
    }
    result: Json = {
        "schema_version": "phase2.research.evaluation.v1",
        "experiment_id": manifest["experiment_id"],
        "source_run_id": package.run_id,
        "split": package.split,
        "manifest_sha256": digest(manifest),
        "config_sha256": manifest["config_sha256"],
        "dataset_sha256": package.dataset_sha256,
        "fixed_contact_population_sha256": manifest["fixed_contact_population_sha256"],
        "formal_phase1_acceptance": False,
        "test_is_sealed_holdout": False,
        "gt_only_after_all_inference_freezes": True,
        "variants": {},
    }
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
        truth = ResearchTruth.model_validate_json(package.simulation_export_path.read_bytes())
        measurements, labels, _, _ = _labels(state.perception, state.inference, truth)
        _, pool, _ = _inventory(package, state.inference)
        positives = {
            pair
            for pair in pool
            if labels[pair[0]] is not None and labels[pair[0]] == labels[pair[1]]
        }
        behavior = supported_behavior(state, truth, labels)
        feature = feature_ablations(state.inference, labels, positives, AssociationConfig())

        from amidst.engineering.local_pilot import _load

        _, _, _, source_manifest = _load(Path(manifest["source_locator"]))
        appearance = RGBDescriptorBundle.model_validate_json(
            (output / name / mode / "appearance.json").read_bytes()
        )
        appearance_report, _ = evaluate_appearance(
            package,
            state.perception,
            state.inference,
            appearance,
            measurements,
            registry,
            source_manifest,
        )
        groups: Json = {}
        for group in ("same_camera", "cross_camera", "overlap"):
            kind = {
                "same_camera": "SAME_CAMERA_RECOVERY",
                "cross_camera": "CROSS_CAMERA_GAP",
                "overlap": "OVERLAPPING_VISIBILITY",
            }[group]
            rows = [
                row
                for row in state.inference.association_hypotheses
                if len(row.segment_ids) == 2 and row.kind == kind
            ]
            pairs = {(row.segment_ids[0], row.segment_ids[1]) for row in rows}
            accepted = {
                (row.segment_ids[0], row.segment_ids[1])
                for row in rows
                if row.status == "PROVISIONAL"
            }
            local_positives = positives & pairs
            groups[group] = {
                "candidate_pairs": len(rows),
                "candidate_population_sha256": digest(sorted(pairs)),
                "statuses": dict(Counter(row.status for row in rows)),
                "link_metrics": _link_metrics(accepted, local_positives, labels),
                "reference_positive_pairs": len(local_positives),
                "conditional_reference": "Retrieved produced segments only; not full person recall",
            }
        pixel = summary["pixels_and_local_identity"]
        assert isinstance(pixel, dict)
        row: Json = {
            "freeze_ref": state.receipt.receipt_sha256,
            "fixed_contact_population_sha256": manifest["fixed_contact_population_sha256"],
            "track_population_sha256": manifest["variants"][name][mode]["track_population_sha256"],
            "candidate_pool_sha256": state.inference.association_pool_sha256,
            "pixels_and_local_identity": pixel,
            "pixel_population": pixel_population(state, measurements),
            "behavior": behavior,
            "behavior_unmasked_candidate_diagnostic": summary["behavior"],
            "retrieval": summary["retrieval"],
            "association_feature_ablations": feature,
            "association_groups": groups,
            "pure_track_appearance_comparison": appearance_report,
            "region_rule_accuracy": {
                "status": "N/A_NO_INDEPENDENT_EVENT_REFERENCE",
                "rule_logic_checked_on_controlled_synthetic_unit_cases": True,
            },
        }
        result["variants"].setdefault(name, {})[mode] = row
    if "selected" in result["variants"]:
        baseline = result["variants"]["baseline"]["photos_only"]
        selected = result["variants"]["selected"]["photos_only"]
        bp, sp = baseline["pixel_population"], selected["pixel_population"]
        b_id, s_id = baseline["pixels_and_local_identity"], selected["pixels_and_local_identity"]
        gates = {
            "fixed_contacts_comparable": baseline["fixed_contact_population_sha256"]
            == selected["fixed_contact_population_sha256"],
            "switches_nonregression": s_id["within_local_track_id_switches"]
            <= b_id["within_local_track_id_switches"],
            "mixed_tracks_nonregression": sp["mixed_known_identity_tracks"]
            <= bp["mixed_known_identity_tracks"],
            "fragmented_tracks_reduced": sp["fragmented_track_count"]
            < bp["fragmented_track_count"],
            "singletons_nonregression": sp["single_measurement_track_count"]
            <= bp["single_measurement_track_count"],
        }
        result["acceptance_gates"] = {
            "continuity": gates,
            "continuity_outcome": "MEASURED_LOCAL_CONTINUITY_GAIN"
            if all(gates.values())
            else "NO_ACCEPTED_CONTINUITY_GAIN",
            "association_population_comparable": baseline["candidate_pool_sha256"]
            == selected["candidate_pool_sha256"],
            "global_identity_metrics": "N/A_NO_GLOBAL_ASSIGNMENT",
            "behavior_accuracy_gain_claim": False,
            "region_rule_accuracy": "N/A_NO_INDEPENDENT_EVENT_REFERENCE",
        }
    return _persist_evaluation(output, result, manifest)


def select_development(output: Path) -> Json:
    """Use development only; accept a pixel Pareto gain before choosing a policy."""
    package, _, _, policy = load(output)
    if package.split != "development":
        raise ValueError("RESEARCH_SELECTION_REQUIRES_DEVELOPMENT")
    evaluation = json.loads((output / "evaluation.json").read_bytes())
    baseline = evaluation["variants"]["baseline"]["photos_only"]

    def pixel_score(row: Json) -> tuple[int, int, int, int]:
        metrics, population = row["pixels_and_local_identity"], row["pixel_population"]
        return (
            metrics["within_local_track_id_switches"],
            population["mixed_known_identity_tracks"],
            population["fragmented_track_count"],
            population["single_measurement_track_count"],
        )

    eligible = []
    base_score = pixel_score(baseline)
    for name, modes in evaluation["variants"].items():
        row = modes["photos_only"]
        score = pixel_score(row)
        if (
            name not in {"sustained_behavior", "reliable_dwell"}
            and all(a <= b for a, b in zip(score, base_score, strict=True))
            and any(a < b for a, b in zip(score, base_score, strict=True))
        ):
            eligible.append((sum(score), score, name))
    chosen = min(eligible)[2] if eligible else "baseline"
    behavior_base = baseline["behavior"]["groups"]["visible_supported"]["per_kind"]
    behavior_new = evaluation["variants"]["reliable_dwell"]["photos_only"]["behavior"]["groups"][
        "visible_supported"
    ]["per_kind"]
    base_fp = sum(row["false_positive"] for row in behavior_base.values())
    new_fp = sum(row["false_positive"] for row in behavior_new.values())
    base_tp = sum(row["true_positive"] for row in behavior_base.values())
    new_tp = sum(row["true_positive"] for row in behavior_new.values())
    use_behavior = (
        new_fp <= base_fp and new_tp >= base_tp and (new_fp < base_fp or new_tp > base_tp)
    )
    selected = dict(policy["variants"][chosen])
    if use_behavior:
        selected.update(reliable_dwell=True)
    return {
        "schema_version": "phase2.research.selection.v1",
        "split": "development",
        "evaluation_sha256": digest(evaluation),
        "pixel_variant": chosen,
        "pixel_gate": "PARETO_GAIN" if eligible else "NO_GAIN_RETAIN_BASELINE",
        "behavior_gate": "TP_NONREGRESSION_FP_GAIN" if use_behavior else "NO_GAIN_RETAIN_BASELINE",
        "baseline_pixel_score": base_score,
        "selected_pixel_score": pixel_score(evaluation["variants"][chosen]["photos_only"]),
        "behavior_totals": {
            "baseline_tp": base_tp,
            "selected_tp": new_tp,
            "baseline_fp": base_fp,
            "selected_fp": new_fp,
        },
        "policy": {
            **policy,
            "variants": {"baseline": policy["variants"]["baseline"], "selected": selected},
        },
    }
