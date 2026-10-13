"""Certified views of existing accuracy-v2 aggregates; no evaluator or producer runs.

The published comparison digest is an independent content certificate.  A hash
found inside the requested file is never a certificate.  Every read rechecks the
manifest and frozen artifacts, so a previously displayed result cannot bless a
changed run.  Only fixed scalar aggregates leave this module.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn, cast

from amidst.engineering.access import digest

Json = dict[str, Any]
SCHEMA = "workbench.accuracy-evaluation.v1"
MODES = ("photos_only", "photos_plus_observations")
VARIANTS = (
    "baseline",
    "appearance_only",
    "prior_only",
    "features_full",
    "motion_diagnostic",
    "pixel_only",
    "behavior_only",
    "end_to_end",
)
KINDS = ("ENTER", "EXIT", "CORNER", "DWELL", "POSSIBLE_WANDERING")
ABLATIONS = (
    "full",
    "without_space",
    "without_time",
    "without_appearance",
    "only_space",
    "only_time",
    "only_appearance",
)
MAX_COMPARISON_BYTES = 1024 * 1024
MAX_PUBLIC_BYTES = 128 * 1024
_HASH = re.compile(r"[0-9a-f]{64}")
_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]{1,100}")
_PRIVATE = re.compile(r"(?:^|[\s\"'=:(])(?:/|[A-Za-z]:[\\/]|file://)|\.\./")
_RAW_KEYS = frozenset(
    {
        "actor_id",
        "actor_ids",
        "actor_identity",
        "target_id",
        "target_ids",
        "ground_truth",
        "ground_truth.json",
        "labels",
        "positive_refs",
        "truth",
        "source_locator",
        "private_path",
    }
)
_ROW_FIELDS = frozenset(
    {
        "association_all_provisional_hypotheses",
        "association_by_kind",
        "behavior",
        "behavior_bundle_binding_verified",
        "behavior_unmasked_candidate_diagnostic",
        "config_sha256",
        "dataset_sha256",
        "evaluation_truth_sha256",
        "evaluator_policy",
        "evaluator_policy_sha256",
        "evaluator_sha256",
        "experiment_id",
        "external_model_calls",
        "fixed_pool_feature_ablations",
        "formal_phase1_acceptance",
        "freeze_sha256",
        "geometry",
        "inference_sha256",
        "limitations",
        "mode",
        "model_id",
        "origin",
        "pixel_population",
        "pixels_and_local_identity",
        "retrieval",
        "run_id",
        "runtime_config_sha256",
        "schema_version",
        "split",
        "status",
        "variant",
        "weighted_fixed_pool_feature_ablations",
    }
)


@dataclass(frozen=True)
class AccuracyEvaluationCertificate:
    """Server-owned, independently recorded hashes; never supplied by a query."""

    manifest_sha256: str
    comparison_sha256: str

    def __post_init__(self) -> None:
        if not all(
            _HASH.fullmatch(value)
            for value in (
                self.manifest_sha256,
                self.comparison_sha256,
            )
        ):
            raise ValueError("INVALID_ACCURACY_EVALUATION_CERTIFICATE")


# accuracy_20261010/validation.json experiments.{development,test}.  These are
# the original completed evaluations, not newly executed evaluation receipts.
_CERTIFICATES = {
    "accuracy-development-v2-final": AccuracyEvaluationCertificate(
        "60b64ec9c070e8bf6cfbd25a3526c1616520c683902421e2afb158d482bce260",
        "c179428f351956c59ec04a305bb3f3f6fe7120b1b74309f7f3b01afa018083c6",
    ),
    "accuracy-test-v2-final": AccuracyEvaluationCertificate(
        "ccea43fea99cc070004e285acd5e11ed1fc78a35f74630ac45892a9757cfe963",
        "5fefafbf3e75536921cf2b82fca93317e174f00eff0e9d835cb4f90bf1123133",
    ),
}


class AccuracyEvaluationError(ValueError):
    def __init__(self, reason: str, *, stale: bool = False) -> None:
        super().__init__(reason)
        self.reason, self.stale = reason, stale


def _reject(reason: str, *, stale: bool = False) -> NoReturn:
    raise AccuracyEvaluationError(reason, stale=stale)


def _pairs(pairs: list[tuple[str, Any]]) -> Json:
    result: Json = {}
    for key, value in pairs:
        if key in result:
            _reject("DUPLICATE_ACCURACY_AGGREGATE_FIELD")
        result[key] = value
    return result


def _constant(_: str) -> None:
    _reject("NONFINITE_ACCURACY_AGGREGATE")


def _safe_path(root: Path, path: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError:
        _reject("ACCURACY_EVALUATION_REFERENCE_DENIED")
    if root.is_symlink() or any(
        (root / Path(*relative.parts[:i])).is_symlink() for i in range(1, len(relative.parts) + 1)
    ):
        _reject("ACCURACY_EVALUATION_REFERENCE_DENIED")
    if path.exists() and not stat.S_ISREG(path.stat().st_mode):
        _reject("ACCURACY_EVALUATION_REFERENCE_DENIED")


def _read(root: Path, name: str, limit: int) -> Json:
    path = root / name
    _safe_path(root, path)
    flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            _reject("ACCURACY_EVALUATION_REFERENCE_DENIED")
        payload = stream.read(limit + 1)
    if len(payload) > limit:
        _reject("ACCURACY_EVALUATION_PAYLOAD_TOO_LARGE")
    value = json.loads(payload, object_pairs_hook=_pairs, parse_constant=_constant)
    if not isinstance(value, dict):
        _reject("INVALID_ACCURACY_AGGREGATE")
    return cast(Json, value)


def _bounded_aggregate(value: object, depth: int = 0, nodes: list[int] | None = None) -> None:
    nodes = [0] if nodes is None else nodes
    nodes[0] += 1
    if depth > 12 or nodes[0] > 50000:
        _reject("ACCURACY_AGGREGATE_COMPLEXITY_LIMIT")
    if isinstance(value, dict):
        if len(value) > 128:
            _reject("ACCURACY_AGGREGATE_COMPLEXITY_LIMIT")
        for key, child in value.items():
            if not isinstance(key, str) or len(key) > 128 or key in _RAW_KEYS:
                _reject("ACCURACY_AGGREGATE_PRIVATE_FIELD")
            _bounded_aggregate(child, depth + 1, nodes)
    elif isinstance(value, list):
        if len(value) > 128:
            _reject("ACCURACY_AGGREGATE_COMPLEXITY_LIMIT")
        for child in value:
            _bounded_aggregate(child, depth + 1, nodes)
    elif isinstance(value, str):
        if len(value) > 1024 or _PRIVATE.search(value) or any(ord(c) < 32 for c in value):
            _reject("ACCURACY_AGGREGATE_PRIVATE_TEXT")
    elif isinstance(value, float) and not math.isfinite(value):
        _reject("NONFINITE_ACCURACY_AGGREGATE")


def _count(value: object) -> int:
    if type(value) is not int or not 0 <= value <= 10**12:
        _reject("INVALID_ACCURACY_AGGREGATE_COUNT")
    return value


def _metric(value: object, *, ratio: bool = False) -> float | int | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or (not math.isfinite(value) or value < 0 or ratio and value > 1)
    ):
        _reject("INVALID_ACCURACY_AGGREGATE_METRIC")
    return value


def _hash(value: object) -> str:
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        _reject("INVALID_ACCURACY_AGGREGATE_HASH")
    return value


def _recall(value: Json) -> Json:
    if set(value) != {"1", "3", "5"}:
        _reject("INVALID_ACCURACY_RECALL_KEYS")
    return {key: _metric(value[key], ratio=True) for key in ("1", "3", "5")}


def _behavior(value: Json) -> Json:
    if set(value) != set(KINDS):
        _reject("INVALID_ACCURACY_BEHAVIOR_KINDS")
    result: Json = {}
    for kind in KINDS:
        row = value[kind]
        if set(row) != {
            "true_positive",
            "false_positive",
            "false_negative",
            "unresolved",
            "precision",
            "recall",
        }:
            _reject("INVALID_ACCURACY_BEHAVIOR_FIELDS")
        counts = {
            key: _count(row[key])
            for key in (
                "true_positive",
                "false_positive",
                "false_negative",
                "unresolved",
            )
        }
        for key, denominator in (
            ("precision", counts["true_positive"] + counts["false_positive"]),
            ("recall", counts["true_positive"] + counts["false_negative"]),
        ):
            actual = _metric(row[key], ratio=True)
            expected = counts["true_positive"] / denominator if denominator else None
            if actual != expected:
                _reject("ACCURACY_BEHAVIOR_DENOMINATOR_MISMATCH", stale=True)
        result[kind] = {
            **counts,
            "precision": row["precision"],
            "recall": row["recall"],
            "reference_count": counts["true_positive"] + counts["false_negative"],
        }
    return result


def _appearance(value: Json) -> Json:
    robust, legacy = value["robust_crop"], value["p8_reference_same_tracks_and_pool"]
    if value["pool_equality_proven"] is not True or (
        value["same_pool_sha256"] != value["p8_same_pool_sha256"]
        or value["same_pool_sha256"] != legacy["same_pool_sha256"]
        or robust["eligible_queries"] != value["eligible_queries"]
        or legacy["handcrafted"]["eligible_queries"] != value["eligible_queries"]
    ):
        _reject("ACCURACY_APPEARANCE_POPULATION_MISMATCH", stale=True)
    return {
        "pool_sha256": _hash(value["same_pool_sha256"]),
        "eligible_queries": _count(value["eligible_queries"]),
        "pool_query_count": _count(value["pool_query_count"]),
        "robust_recall_at_k": _recall(robust["tie_aware_recall_at_k"]),
        "handcrafted_recall_at_k": _recall(legacy["handcrafted"]["tie_aware_recall_at_k"]),
        "false_negative_queries_at_k": {
            k: _count(robust["false_negative_queries_at_k"][k]) for k in ("1", "3", "5")
        },
        "missing_query_descriptors": _count(robust["missing_query_descriptor_count"]),
        "query_exclusions": {
            k: _count(value["query_exclusion_counts"].get(k, 0))
            for k in (
                "NO_ELIGIBLE_SAME_IDENTITY_PRODUCED_TARGET",
                "UNRESOLVED_OR_IMPURE_QUERY",
            )
        },
    }


def project_accuracy_evaluation(
    value: Json,
    manifest: Json,
    freeze_bindings: Mapping[tuple[str, str], Json],
    certificate: AccuracyEvaluationCertificate,
) -> Json:
    """Certify a fixed aggregate and project a bounded public DTO, without GT."""
    _bounded_aggregate(value)
    if digest(manifest) != certificate.manifest_sha256:
        _reject("ACCURACY_EVALUATION_BINDING_MISMATCH", stale=True)
    if digest(value) != certificate.comparison_sha256:
        _reject("ACCURACY_EVALUATION_CONTENT_HASH_MISMATCH", stale=True)
    root_fields = {
        "schema_version",
        "experiment_id",
        "source_run_id",
        "split",
        "manifest_sha256",
        "config_sha256",
        "dataset_sha256",
        "evaluator_sha256",
        "evaluator_policy",
        "formal_phase1_acceptance",
        "test_is_sealed_holdout",
        "variants",
        "comparison",
    }
    if (
        set(value) != root_fields
        or value["schema_version"] != "accuracy.comparison.v2"
        or (
            value["formal_phase1_acceptance"] is not False
            or value["test_is_sealed_holdout"] is not False
            or set(value["variants"]) != set(VARIANTS)
            or set(value["comparison"]) != set(VARIANTS)
        )
    ):
        _reject("INVALID_ACCURACY_AGGREGATE_SCHEMA")
    for key in ("experiment_id", "source_run_id", "split", "config_sha256", "dataset_sha256"):
        if value[key] != manifest[key]:
            _reject("ACCURACY_EVALUATION_BINDING_MISMATCH", stale=True)
    if value["manifest_sha256"] != certificate.manifest_sha256 or (
        value["evaluator_sha256"] != manifest["algorithms"]["research_accuracy/evaluation.py"]
    ):
        _reject("ACCURACY_EVALUATION_BINDING_MISMATCH", stale=True)
    for key in ("experiment_id", "source_run_id"):
        if not isinstance(value[key], str) or not _IDENTIFIER.fullmatch(value[key]):
            _reject("INVALID_ACCURACY_AGGREGATE_IDENTIFIER")
    rows = []
    for variant in VARIANTS:
        if set(value["variants"][variant]) != set(MODES):
            _reject("INVALID_ACCURACY_AGGREGATE_MODES")
        for mode in MODES:
            original = value["variants"][variant][mode]
            if set(original) not in (
                _ROW_FIELDS,
                _ROW_FIELDS | {"pure_track_appearance_comparison"},
            ):
                _reject("INVALID_ACCURACY_AGGREGATE_FIELDS")
            bound = freeze_bindings[variant, mode]
            expected = manifest["variants"][variant][mode]
            for key, actual in {
                "run_id": manifest["source_run_id"],
                "experiment_id": manifest["experiment_id"],
                "variant": variant,
                "mode": mode,
                "dataset_sha256": manifest["dataset_sha256"],
                "runtime_config_sha256": manifest["config_sha256"],
                "freeze_sha256": expected["receipt_sha256"],
                "inference_sha256": bound["inference_sha256"],
                "config_sha256": bound["source_config_sha256"],
                "model_id": bound["model_id"],
            }.items():
                if original.get(key) != actual:
                    _reject("ACCURACY_VARIANT_FREEZE_MISMATCH", stale=True)
            if original["formal_phase1_acceptance"] is not False or (
                original["external_model_calls"] is not False
                or original["origin"] != "SYNTHETIC"
                or original["behavior_bundle_binding_verified"] is not True
                or original["schema_version"] != "local.camera.evaluation.v1"
                or original["status"] != "E1_SYNTHETIC_PILOT_MEASURED"
                or original["split"] != manifest["split"]
            ):
                _reject("INVALID_ACCURACY_AGGREGATE_SCHEMA")
            pixels, population = original["pixels_and_local_identity"], original["pixel_population"]
            retrieval, association = (
                original["retrieval"],
                original["association_all_provisional_hypotheses"],
            )
            ablations, behavior = (
                original["weighted_fixed_pool_feature_ablations"],
                original["behavior"],
            )
            if set(ablations) != set(ABLATIONS) or any(
                a["candidate_pool_sha256"] != expected["candidate_pool_sha256"]
                or a["eligible_query_count"] != ablations["full"]["eligible_query_count"]
                or a["true_link_count"] != retrieval["same_identity_eligible_pair_count"]
                or a["hard_physics_preserved"] is not True
                or a["scores_are_probabilities"] is not False
                for a in ablations.values()
            ):
                _reject("ACCURACY_CANDIDATE_POPULATION_MISMATCH", stale=True)
            if pixels["measurement_count"] != bound["measurement_count"] or (
                population["track_count"] != bound["track_count"]
                or retrieval["same_identity_eligible_pair_count"] != association["true_link_count"]
                or retrieval["retrieved_pair_count"] != bound["pair_count"]
            ):
                _reject("ACCURACY_POPULATION_DENOMINATOR_MISMATCH", stale=True)
            tp = _count(association["true_positive"])
            resolved = _count(association["resolved_link_count"])
            positives = _count(association["true_link_count"])
            if association["same_identity_eligible_pair_precision"] != (
                tp / resolved if resolved else None
            ) or association["same_identity_eligible_pair_recall"] != (
                tp / positives if positives else None
            ):
                _reject("ACCURACY_ASSOCIATION_DENOMINATOR_MISMATCH", stale=True)
            row = {
                "variant": variant,
                "mode": mode,
                "freeze_sha256": _hash(original["freeze_sha256"]),
                "population": {
                    "track_population_sha256": _hash(bound["track_population_sha256"]),
                    "candidate_pool_sha256": _hash(expected["candidate_pool_sha256"]),
                    "measurement_count": _count(pixels["measurement_count"]),
                    "eligible_contacts": _count(pixels["eligible_visible_actor_contacts"]),
                    "track_count": _count(population["track_count"]),
                    "segment_count": _count(bound["segment_count"]),
                    "pair_count": _count(retrieval["retrieved_pair_count"]),
                    "eligible_pair_positives": _count(
                        retrieval["same_identity_eligible_pair_count"]
                    ),
                    "eligible_queries": _count(ablations["full"]["eligible_query_count"]),
                },
                "pixels": {
                    "id_switches": _count(pixels["within_local_track_id_switches"]),
                    "fragmented_tracks": _count(population["fragmented_track_count"]),
                    "mixed_tracks": _count(population["mixed_known_identity_tracks"]),
                    "single_measurement_tracks": _count(
                        population["single_measurement_track_count"]
                    ),
                    "contact_recall": _metric(
                        pixels["one_to_one_visible_contact_recall"], ratio=True
                    ),
                    "ground_rms_m": _metric(pixels["ground_contact_error_m"]["rms"]),
                },
                "association": {
                    "ablation_population": {
                        "candidate_pool_sha256": _hash(expected["candidate_pool_sha256"]),
                        "eligible_queries": _count(ablations["full"]["eligible_query_count"]),
                        "eligible_pair_positives": positives,
                        "relative_to_selected_variant": True,
                    },
                    "true_positive": tp,
                    "false_positive": _count(association["pair_level_false_merge_count"]),
                    "false_negative": _count(association["pair_level_missed_link_count"]),
                    "unresolved_links": _count(association["unresolved_link_count"]),
                    "predicted_links": _count(association["predicted_link_count"]),
                    "resolved_links": resolved,
                    "pair_precision": _metric(
                        association["same_identity_eligible_pair_precision"], ratio=True
                    ),
                    "pair_recall": _metric(
                        association["same_identity_eligible_pair_recall"], ratio=True
                    ),
                    "rank_recall_at_k": _recall(
                        ablations["full"]["identity_candidate_recall_at_k"]
                    ),
                    "ablation_recall_at_k": {
                        k: _recall(ablations[k]["identity_candidate_recall_at_k"])
                        for k in ABLATIONS
                    },
                    "records_read": _count(retrieval["records_read"]),
                    "index_entries_touched": _count(retrieval["index_entries_touched"]),
                },
                "behavior": {
                    "unknown_count": _count(behavior["evidence_unknown_count"]),
                    "candidate_count": _count(behavior["visible_candidate_count"]),
                    "per_kind": _behavior(behavior["groups"]["visible_supported"]["per_kind"]),
                },
            }
            if "pure_track_appearance_comparison" in original:
                row["appearance"] = _appearance(original["pure_track_appearance_comparison"])
            rows.append(row)
    comparisons, regressions = _comparisons(rows)
    result = {
        "schema_version": SCHEMA,
        "status": "CERTIFIED_LOCAL_SYNTHETIC",
        "binding": {
            **{
                k: manifest[k]
                for k in (
                    "source_run_id",
                    "experiment_id",
                    "source_sha256",
                    "dataset_sha256",
                    "config_sha256",
                    "split",
                )
            },
            "manifest_sha256": certificate.manifest_sha256,
            "comparison_sha256": certificate.comparison_sha256,
        },
        "modes": list(MODES),
        "variants": rows,
        "comparisons": comparisons,
        "regressions": regressions,
        "formal_phase1_acceptance": False,
        "test_is_sealed_holdout": False,
        "limitations": [
            "Historical frozen local synthetic evaluation; no new inference or evaluation run.",
            "Changed producer pools have separate hashes and denominators; "
            "ranking gains are not directly comparable.",
            "UNKNOWN preserves all reference false negatives; "
            "no confirmed global identity or blind-gap behavior.",
            "No sealed holdout, real-camera, trained ReID, cross-place "
            "or formal acceptance evidence.",
        ],
    }
    _bounded_aggregate(result)
    if len(json.dumps(result).encode()) > MAX_PUBLIC_BYTES:
        _reject("ACCURACY_PUBLIC_PAYLOAD_TOO_LARGE")
    return result


def _comparisons(rows: list[Json]) -> tuple[list[Json], list[Json]]:
    comparisons, regressions = [], []
    for mode in MODES:
        baseline = next(r for r in rows if r["mode"] == mode and r["variant"] == "baseline")
        for row in (r for r in rows if r["mode"] == mode and r["variant"] != "baseline"):
            population, base = row["population"], baseline["population"]
            comparable = all(
                population[key] == base[key]
                for key in (
                    "candidate_pool_sha256",
                    "track_population_sha256",
                    "measurement_count",
                    "eligible_contacts",
                    "eligible_queries",
                    "eligible_pair_positives",
                )
            )
            comparisons.append(
                {
                    "mode": mode,
                    "baseline_variant": "baseline",
                    "variant": row["variant"],
                    "population_comparable": comparable,
                    "baseline_pool_sha256": base["candidate_pool_sha256"],
                    "candidate_pool_sha256": population["candidate_pool_sha256"],
                    "baseline_queries": base["eligible_queries"],
                    "eligible_queries": population["eligible_queries"],
                    "baseline_positive_pairs": base["eligible_pair_positives"],
                    "eligible_pair_positives": population["eligible_pair_positives"],
                }
            )
            for section, metric in (
                ("pixels", "fragmented_tracks"),
                ("pixels", "mixed_tracks"),
                ("association", "records_read"),
                ("association", "index_entries_touched"),
            ):
                if row[section][metric] > baseline[section][metric]:
                    regressions.append(
                        {
                            "mode": mode,
                            "variant": row["variant"],
                            "metric": metric,
                            "baseline": baseline[section][metric],
                            "value": row[section][metric],
                            "population_comparable": comparable,
                        }
                    )
            for kind in KINDS:
                selected, reference = (
                    row["behavior"]["per_kind"][kind],
                    baseline["behavior"]["per_kind"][kind],
                )
                if selected["reference_count"] != reference["reference_count"]:
                    _reject("ACCURACY_BEHAVIOR_REFERENCE_POPULATION_MISMATCH", stale=True)
                if selected["false_positive"] > reference["false_positive"]:
                    regressions.append(
                        {
                            "mode": mode,
                            "variant": row["variant"],
                            "metric": kind + "_false_positive",
                            "baseline": reference["false_positive"],
                            "value": selected["false_positive"],
                            "population_comparable": True,
                        }
                    )
                if (
                    selected["recall"] is not None
                    and reference["recall"] is not None
                    and (selected["recall"] < reference["recall"])
                ):
                    regressions.append(
                        {
                            "mode": mode,
                            "variant": row["variant"],
                            "metric": kind + "_recall",
                            "baseline": reference["recall"],
                            "value": selected["recall"],
                            "population_comparable": True,
                        }
                    )
            full = row["association"]["rank_recall_at_k"]["1"]
            for name, recall in row["association"]["ablation_recall_at_k"].items():
                if full is not None and recall["1"] is not None and full < recall["1"]:
                    regressions.append(
                        {
                            "mode": mode,
                            "variant": row["variant"],
                            "metric": "rank_at_1_vs_" + name,
                            "baseline": recall["1"],
                            "value": full,
                            "population_comparable": True,
                        }
                    )
            if "appearance" in row:
                appearance = row["appearance"]
                for k in ("1", "3", "5"):
                    actual = appearance["robust_recall_at_k"][k]
                    reference_recall = appearance["handcrafted_recall_at_k"][k]
                    if (
                        actual is not None
                        and reference_recall is not None
                        and (actual < reference_recall)
                    ):
                        regressions.append(
                            {
                                "mode": mode,
                                "variant": row["variant"],
                                "metric": "appearance_at_" + k + "_vs_handcrafted",
                                "baseline": reference_recall,
                                "value": actual,
                                "population_comparable": True,
                            }
                        )
    return comparisons, regressions


def certify_accuracy_evaluation(
    root: Path,
    manifest: Json,
    *,
    certificate: AccuracyEvaluationCertificate | None = None,
) -> Json:
    """Read/verify existing frozen aggregates; never imports the GT evaluator."""
    certificate = certificate or _CERTIFICATES.get(manifest.get("experiment_id", ""))
    if certificate is None:
        _reject("ACCURACY_EVALUATION_CONTENT_CERTIFICATE_MISSING")
    current = _read(root, "manifest.json", MAX_COMPARISON_BYTES)
    if digest(current) != digest(manifest) or digest(current) != certificate.manifest_sha256:
        _reject("ACCURACY_EVALUATION_BINDING_MISMATCH", stale=True)
    value = _read(root, "comparison.json", MAX_COMPARISON_BYTES)
    # Validate the independent certificate before any additional artifact read.
    _bounded_aggregate(value)
    if digest(value) != certificate.comparison_sha256:
        _reject("ACCURACY_EVALUATION_CONTENT_HASH_MISMATCH", stale=True)
    for variant in VARIANTS:
        for mode in MODES:
            names = ["perception.json", "inference.json", "events.json", "receipt.json"]
            if manifest["variants"][variant][mode]["appearance_sha256"] is not None:
                names.append("appearance.json")
            for name in names:
                _safe_path(root, root / variant / mode / name)
    from amidst.engineering.access import Mode
    from amidst.research_accuracy.run import Variant, frozen, load

    package, registry, verified, _ = load(root)
    if digest(verified) != certificate.manifest_sha256:
        _reject("ACCURACY_EVALUATION_BINDING_MISMATCH", stale=True)
    bindings = {}
    for variant in VARIANTS:
        for mode in MODES:
            state = frozen(
                root, cast(Variant, variant), cast(Mode, mode), verified, package, registry
            )
            bindings[variant, mode] = {
                "inference_sha256": state.receipt.inference_sha256,
                "track_population_sha256": state.receipt.measurement_sha256,
                "measurement_count": len(state.perception.measurements),
                "track_count": len(state.perception.tracks),
                "segment_count": len(state.inference.local_record_maps),
                "pair_count": state.inference.pair_count,
                "source_config_sha256": package.config_sha256,
                "model_id": package.model_id,
            }
    return project_accuracy_evaluation(value, verified, bindings, certificate)


class AccuracyEvaluationReader:
    """An importer-owned reference, with fresh validation on every query."""

    def __init__(self, root: Path, manifest: Json) -> None:
        self.root, self.manifest = root, json.loads(json.dumps(manifest))

    def evaluation(self) -> Json:
        try:
            _safe_path(self.root, self.root / "comparison.json")
            if not (self.root / "comparison.json").exists():
                return {"status": "UNAVAILABLE", "reason": "NO_PREEXISTING_EVALUATION"}
            return certify_accuracy_evaluation(self.root, self.manifest)
        except AccuracyEvaluationError as exc:
            return {"status": "STALE" if exc.stale else "UNAVAILABLE", "reason": exc.reason}
        except (OSError, ValueError, KeyError, TypeError, RecursionError):
            return {"status": "UNAVAILABLE", "reason": "INVALID_ACCURACY_EVALUATION"}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify existing certified accuracy aggregates; no rerun."
    )
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    manifest = _read(args.root, "manifest.json", MAX_COMPARISON_BYTES)
    print(json.dumps(AccuracyEvaluationReader(args.root, manifest).evaluation(), indent=2))


if __name__ == "__main__":
    main()
