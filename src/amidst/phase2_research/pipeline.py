"""Freeze independently configured continuities and visible behaviors before evaluation."""

from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from amidst.engineering.access import FreezeReceipt, RunBinding, digest
from amidst.engineering.local_association import AssociationPolicy, InferenceBundle, build_inference
from amidst.engineering.local_behavior import BehaviorConfig, LocalBehaviorBundle
from amidst.engineering.local_index import RetrievalPolicy
from amidst.engineering.local_pilot import MODES, _load, _save, algorithm_hashes
from amidst.engineering.perception import PerceptionResult, produce_perception
from amidst.phase2_research.continuity import reassociate
from amidst.research_accuracy.association import (
    AssociationConfig,
    build_appearance_bundle,
    improve_association,
)
from amidst.research_accuracy.behavior import BehaviorEvidencePolicy, compose_behaviors_v2
from amidst.research_accuracy.pixel import PixelContinuityConfig
from amidst.research_accuracy.run import FrozenVariant

Json = dict[str, Any]
VERSION = "phase2-synthetic-research-abc-v1"


def algorithms() -> dict[str, str]:
    from amidst.research_accuracy.run import research_algorithms

    return (
        algorithm_hashes()
        | research_algorithms()
        | {
            "phase2_research/" + name: sha256(
                Path(__file__).with_name(name).read_bytes()
            ).hexdigest()
            for name in ("pipeline.py", "rules.py", "continuity.py", "evaluation.py", "adapter.py")
        }
    )


def candidate_policies() -> Json:
    base: Json = {
        "pixel": PixelContinuityConfig().model_dump(mode="json"),
        "behavior": BehaviorEvidencePolicy().model_dump(mode="json"),
        "dwell_min_duration_s": 1.2,
    }
    variants: Json = {"baseline": base}
    changes_by_name: Json = {
        "short_memory": {"max_gap_s": 0.81},
        "long_memory": {"max_gap_s": 1.61},
        "no_velocity": {"use_velocity": False},
        "strict_prediction": {"max_prediction_error_px": 16.0},
        "relaxed_prediction": {"max_prediction_error_px": 32.0},
        "no_quarantine": {"merge_quarantine": False},
        "lower_unmatched": {"unmatched_cost": 0.75},
    }
    for name, changes in changes_by_name.items():
        variants[name] = {**base, "pixel": {**base["pixel"], **changes}}
    variants["sustained_behavior"] = {
        **base,
        "behavior": {
            **base["behavior"],
            "portal_clearance_m": 0.08,
            "portal_context_window_s": 1.6,
            "corner_context_window_s": 3.2,
            "corner_min_arm_displacement_m": 0.25,
        },
        "dwell_min_duration_s": 2.0,
    }
    variants["unambiguous_partial"] = {**base, "partial_mode": "UNAMBIGUOUS_PARTIAL"}
    variants["reliable_dwell"] = {**base, "reliable_dwell": True}
    return {
        "version": VERSION,
        "variants": variants,
        "selection": "DEVELOPMENT_ONLY; test is previously used synthetic regression",
        "region_rules": {
            "version": "single-region-rules-v1",
            "side_samples": 2,
            "max_gap_s": 0.6,
            "dwell_duration_s": 2.0,
            "dwell_radius_m": 0.3,
            "dwell_speed_m_s": 0.25,
        },
    }


def _contacts(perception: PerceptionResult) -> str:
    return digest(
        sorted(
            (
                row.camera_id,
                row.timestamp,
                row.frame_ref,
                row.input_sha256,
                row.bbox_xyxy,
                row.contact_pixel,
                row.appearance,
            )
            for row in perception.measurements
        )
    )


def _namespace(perception: PerceptionResult, policy: Json) -> PerceptionResult:
    producer = digest(
        {
            "algorithms": algorithms(),
            "pixel": policy["pixel"],
            "inherited_producer_sha256": perception.producer_sha256,
            "partial_mode": policy.get("partial_mode", "STRICT"),
        }
    )
    namespace = {
        track.local_track_id: "abc-track:"
        + digest([producer, perception.model_id, perception.run_id, track.local_track_id])[:24]
        for track in perception.tracks
    }
    observations = {
        row.observation_id: "abc-pixel:" + digest([producer, row.observation_id])[:24]
        for row in perception.measurements
    }
    rows = tuple(
        row.model_copy(
            update={
                "local_track_id": namespace[row.local_track_id],
                "observation_id": observations[row.observation_id],
                "producer_version": VERSION,
            }
        )
        for row in perception.measurements
    )
    tracks = tuple(
        track.model_copy(
            update={
                "local_track_id": namespace[track.local_track_id],
                "observation_ids": tuple(observations[ref] for ref in track.observation_ids),
            }
        )
        for track in perception.tracks
    )
    return perception.model_copy(
        update={
            "measurements": rows,
            "tracks": tracks,
            "producer_version": VERSION,
            "producer_sha256": producer,
        }
    )


def build(source: Path, output: Path, policy: Json, *, experiment_id: str) -> Json:
    from amidst.phase2_research.rules import compose_rules

    source, output = source.resolve(), output.resolve()
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", experiment_id)
        or policy.get("version") != VERSION
        or not policy.get("variants")
        or len(policy["variants"]) > 12
        or output.is_relative_to(source)
        or (output.exists() and any(output.iterdir()))
    ):
        raise ValueError("RESEARCH_REQUIRES_NEW_EMPTY_BOUND_OUTPUT")
    package, registry, topology, original = _load(source)
    if package.split not in ("development", "test"):
        raise ValueError("RESEARCH_SPLIT_DENIED")
    behavior = BehaviorConfig.model_validate_json((source / "behavior_config.json").read_bytes())
    detector = produce_perception(package.frames, model_id=package.model_id, run_id=package.run_id)
    manifest: Json = {
        "schema_version": "phase2.research.freeze.v1",
        "version": VERSION,
        "experiment_id": experiment_id,
        "source_locator": str(source),
        "source_run_id": package.run_id,
        "split": package.split,
        "source_sha256": package.source_sha256,
        "dataset_sha256": package.dataset_sha256,
        "context_sha256": package.context_sha256,
        "clock_id": package.scope.clock_id,
        "source_manifest_sha256": digest(original),
        "algorithms": algorithms(),
        "config_sha256": digest(
            {
                "policy": policy,
                "algorithms": algorithms(),
                "source_config_sha256": original["config_sha256"],
            }
        ),
        "policy_sha256": digest(policy),
        "fixed_contact_population_sha256": _contacts(detector),
        "variants": {},
        "formal_phase1_acceptance": False,
        "external_model_calls": False,
        "test_is_sealed_holdout": False,
        "raw_copied": False,
    }
    _save(output / "policy.json", policy)
    for name, variant in policy["variants"].items():
        if not re.fullmatch(r"[a-z_]{1,40}", name):
            raise ValueError("RESEARCH_VARIANT_DENIED")
        PixelContinuityConfig.model_validate(variant["pixel"])
        BehaviorEvidencePolicy.model_validate(variant["behavior"])
        manifest["variants"][name] = {}
        for mode in MODES:
            # Recompute each mode independently from the same fixed detector population.
            perception = _namespace(
                reassociate(
                    detector,
                    config=PixelContinuityConfig.model_validate(variant["pixel"]),
                    partial_mode=variant.get("partial_mode", "STRICT"),
                ),
                variant,
            )
            if _contacts(perception) != manifest["fixed_contact_population_sha256"]:
                raise ValueError("RESEARCH_CONTACT_POPULATION_CHANGED")
            inference = build_inference(
                perception,
                scope=package.scope,
                context=package.context,
                policy=AssociationPolicy.model_validate(original["association_policy"]),
                topology=topology,
                retrieval_policy=RetrievalPolicy.model_validate(original["retrieval_policy"]),
            )
            canonical = digest(inference.snapshot)
            appearance = build_appearance_bundle(perception, inference, package.frames)
            inference = improve_association(
                perception, inference, package.frames, AssociationConfig()
            )
            if digest(inference.snapshot) != canonical:
                raise ValueError("RESEARCH_CANONICAL_GRAPH_CHANGED")
            config = behavior.model_copy(
                update={
                    "config_version": behavior.config_version + ":abc-v1",
                    "thresholds": behavior.thresholds.model_copy(
                        update={"dwell_min_duration_s": variant["dwell_min_duration_s"]}
                    ),
                }
            )
            events = compose_behaviors_v2(
                inference,
                config,
                tracks=perception.tracks,
                policy=BehaviorEvidencePolicy.model_validate(variant["behavior"]),
            )
            if variant.get("reliable_dwell"):
                from amidst.research_accuracy.behavior import SUPPORT_PREFIX, event_support_state

                tracks = {track.local_track_id: track for track in perception.tracks}
                rows = {row.observation_id: row for row in perception.measurements}
                conservative = []
                behavior_hash = digest(
                    {
                        "inherited_config_sha256": events.config_sha256,
                        "reliable_dwell": True,
                        "version": VERSION,
                    }
                )
                for event in events.events:
                    unreliable = (
                        event.kind == "DWELL"
                        and event_support_state(event) == "SUPPORTED"
                        and any(
                            tracks[ref].status == "FRAGMENTED"
                            or any(
                                rows[oid].status == "MERGED_OR_PARTIAL"
                                for oid in tracks[ref].observation_ids
                            )
                            for ref in event.local_track_ids
                        )
                    )
                    if unreliable:
                        event = event.model_copy(
                            update={
                                "supports": tuple(
                                    support
                                    for support in event.supports
                                    if not support.startswith(SUPPORT_PREFIX)
                                )
                                + (SUPPORT_PREFIX + "UNKNOWN",),
                                "conflicts": (
                                    *event.conflicts,
                                    "UNRELIABLE_LOCAL_TRACK_DWELL_CONTEXT",
                                ),
                            }
                        )
                        event = event.model_copy(
                            update={"uncertainty": "UNKNOWN dwell; unreliable local-track context."}
                        )
                    event_id = "abc-behavior:" + digest([behavior_hash, event.event_id])[:24]
                    event = event.model_copy(
                        update={
                            "config_sha256": behavior_hash,
                            "event_id": event_id,
                            "detail_ref": event_id,
                        }
                    )
                    conservative.append(event)
                events = events.model_copy(
                    update={"events": tuple(conservative), "config_sha256": behavior_hash}
                )
            binding = RunBinding(
                place_id=package.scope.place_id,
                model_id=package.model_id,
                model_revision=package.revision,
                source_ref=package.scope.source_ref,
                spatial_context_id=package.scope.spatial_context_id,
                run_id=package.run_id,
                clock_id=package.scope.clock_id,
                observation_mode=mode,
                registry_version=VERSION,
                dataset_sha256=package.dataset_sha256,
                config_sha256=digest(
                    {
                        "config": manifest["config_sha256"],
                        "experiment": experiment_id,
                        "variant": name,
                    }
                ),
                producer_sha256=perception.producer_sha256,
                registry_sha256=registry.sha256,
                media_sha256=digest([(frame.media_ref, frame.sha256) for frame in registry.frames]),
            )
            receipt = FreezeReceipt.create(binding, inference, perception.model_dump(mode="json"))
            rules = compose_rules(inference, config, policy["region_rules"])
            docs = {
                "perception": perception,
                "inference": inference,
                "events": events,
                "receipt": receipt,
                "appearance": appearance,
                "rules": rules,
            }
            hashes = {}
            for key, value in docs.items():
                _save(output / name / mode / (key + ".json"), value)
                hashes[key] = digest(value)
            manifest["variants"][name][mode] = {
                "hashes": hashes,
                "freeze_ref": receipt.receipt_sha256,
                "candidate_pool_sha256": inference.association_pool_sha256,
                "track_population_sha256": digest(
                    [track.local_track_id for track in perception.tracks]
                ),
                "producer_sha256": perception.producer_sha256,
                "behavior_config_sha256": events.config_sha256,
            }
    _save(output / "manifest.json", manifest)
    return manifest


def load(output: Path) -> tuple[Any, Any, Json, Json]:
    manifest = json.loads((output / "manifest.json").read_bytes())
    policy = json.loads((output / "policy.json").read_bytes())
    if (
        manifest["schema_version"] != "phase2.research.freeze.v1"
        or manifest["version"] != VERSION
        or manifest["algorithms"] != algorithms()
        or manifest["policy_sha256"] != digest(policy)
    ):
        raise ValueError("RESEARCH_FREEZE_SOURCE_CHANGED")
    package, registry, _, original = _load(Path(manifest["source_locator"]))
    if (
        manifest["source_manifest_sha256"] != digest(original)
        or manifest["source_run_id"] != package.run_id
        or manifest["dataset_sha256"] != package.dataset_sha256
        or manifest["source_sha256"] != package.source_sha256
        or manifest["config_sha256"]
        != digest(
            {
                "policy": policy,
                "algorithms": algorithms(),
                "source_config_sha256": original["config_sha256"],
            }
        )
    ):
        raise ValueError("RESEARCH_SOURCE_BINDING_MISMATCH")
    return package, registry, manifest, policy


def frozen(output: Path, variant: str, mode: str, manifest: Json) -> FrozenVariant:
    package, registry, current, _ = load(output)
    if current != manifest or variant not in manifest["variants"] or mode not in MODES:
        raise ValueError("RESEARCH_VARIANT_MODE_DENIED")
    root = output / variant / mode
    expected = manifest["variants"][variant][mode]
    for key, expected_hash in expected["hashes"].items():
        path = root / (key + ".json")
        if path.is_symlink() or not path.resolve().is_relative_to(output.resolve()):
            raise ValueError("RESEARCH_ARTIFACT_PATH_DENIED")
        if digest(json.loads(path.read_bytes())) != expected_hash:
            raise ValueError("RESEARCH_ARTIFACT_HASH_MISMATCH")
    perception = PerceptionResult.model_validate_json((root / "perception.json").read_bytes())
    inference = InferenceBundle.model_validate_json((root / "inference.json").read_bytes())
    events = LocalBehaviorBundle.model_validate_json((root / "events.json").read_bytes())
    receipt = FreezeReceipt.model_validate_json((root / "receipt.json").read_bytes())
    binding = receipt.binding
    if (
        not receipt.verify(binding, inference, perception.model_dump(mode="json"))
        or receipt.receipt_sha256 != expected["freeze_ref"]
        or binding.registry_sha256 != registry.sha256
        or binding.observation_mode != mode
        or binding.run_id != package.run_id
        or binding.config_sha256
        != digest(
            {
                "config": manifest["config_sha256"],
                "experiment": manifest["experiment_id"],
                "variant": variant,
            }
        )
        or binding.producer_sha256 != perception.producer_sha256
        or inference.association_pool_sha256 != expected["candidate_pool_sha256"]
        or inference.scope != package.scope
        or events.scope != package.scope
        or events.inference_sha256 != receipt.inference_sha256
        or events.config_sha256 != expected["behavior_config_sha256"]
        or perception.input_manifest_sha256 != package.dataset_sha256
        or _contacts(perception) != manifest["fixed_contact_population_sha256"]
    ):
        raise ValueError("RESEARCH_RECEIPT_SCOPE_MISMATCH")
    return FrozenVariant(perception, inference, events, receipt)
