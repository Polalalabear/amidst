"""Independent 05 namespace over immutable E1 measured contacts; no detector/render runs."""

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
from amidst.engineering.local_pilot import MODES, _load, _save, frozen_mode
from amidst.engineering.perception import PerceptionResult
from amidst.phase2_research.pipeline import _contacts
from amidst.phase2_research.pipeline import algorithms as inherited_algorithms
from amidst.phase2_research.repair05_trace import trace_assignment
from amidst.phase2_research.repair05_tracker import Strategy
from amidst.research_accuracy.behavior import BehaviorEvidencePolicy, compose_behaviors_v2
from amidst.research_accuracy.pixel import PixelContinuityConfig
from amidst.research_accuracy.run import FrozenVariant

Json = dict[str, Any]
VERSION = "phase2-repair05-v1"
FILES = (
    "repair05_trace.py",
    "repair05_attribution.py",
    "repair05_tracker.py",
    "repair05_pipeline.py",
    "repair05_evaluation.py",
    "repair05_verify.py",
    "repair05_adapter.py",
)


def algorithms() -> dict[str, str]:
    return inherited_algorithms() | {
        "phase2_research/" + name: sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in FILES
    }


def policy() -> Json:
    return {
        "version": VERSION,
        "pixel": PixelContinuityConfig().model_dump(mode="json"),
        "strategies": {"baseline": "BASELINE", "candidate": "ROBUST_THREE_CLEAN"},
        "single_factor": "median pairwise velocity from exactly three clean measured contacts",
        "behavior": BehaviorEvidencePolicy().model_dump(mode="json"),
        "behavior_changes": False,
        "appearance_or_reid_changes": False,
        "test_is_sealed_holdout": False,
        "test_caps": {
            "switches": 4,
            "mixed_tracks": 3,
            "internal_missing_tracks": 6,
            "singletons": 6,
        },
        "anti_reset_gates": {
            "fixed_and_labeled_contacts_identical": True,
            "every_reference_actor_track_multiplicity_nonincreasing": True,
            "noninitial_new_track_decisions_nonincreasing": True,
            "report_all_missing_samples_and_gap_distribution": True,
            "missing_samples_never_invented": True,
        },
    }


def _namespace(perception: PerceptionResult, strategy: Strategy) -> PerceptionResult:
    producer = digest({"algorithms": algorithms(), "policy": policy(), "strategy": strategy})
    tracks = {
        row.local_track_id: "repair05-track:" + digest([producer, row.local_track_id])[:24]
        for row in perception.tracks
    }
    observations = {
        row.observation_id: "repair05-pixel:" + digest([producer, row.observation_id])[:24]
        for row in perception.measurements
    }
    return perception.model_copy(
        update={
            "measurements": tuple(
                row.model_copy(
                    update={
                        "observation_id": observations[row.observation_id],
                        "local_track_id": tracks[row.local_track_id],
                        "producer_version": VERSION,
                    }
                )
                for row in perception.measurements
            ),
            "tracks": tuple(
                row.model_copy(
                    update={
                        "local_track_id": tracks[row.local_track_id],
                        "observation_ids": tuple(observations[ref] for ref in row.observation_ids),
                    }
                )
                for row in perception.tracks
            ),
            "producer_version": VERSION,
            "producer_sha256": producer,
        }
    )


def build(
    source: Path,
    output: Path,
    *,
    experiment_id: str,
    test_authorized: bool = False,
    development_selection: Json | None = None,
) -> Json:
    source, output = source.resolve(), output.resolve()
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", experiment_id)
        or output.is_relative_to(source)
        or (output.exists() and any(output.iterdir()))
    ):
        raise ValueError("REPAIR05_NEW_EMPTY_OUTPUT_REQUIRED")
    metadata = json.loads((source / "package.json").read_bytes())
    if metadata["split"] == "test" and not test_authorized:
        raise ValueError("REPAIR05_TEST_COORDINATION_REQUIRED")
    if metadata["split"] not in {"development", "test"}:
        raise ValueError("REPAIR05_SPLIT_DENIED")
    if metadata["split"] == "test" and (
        development_selection is None
        or development_selection.get("split") != "development"
        or development_selection.get("algorithms") != algorithms()
        or development_selection.get("selected_variant") not in {"baseline", "candidate"}
        or development_selection.get("test_consulted_for_selection") is not False
    ):
        raise ValueError("REPAIR05_FROZEN_DEVELOPMENT_SELECTION_REQUIRED")
    package, registry, topology, original = _load(source)
    source_behavior = BehaviorConfig.model_validate_json(
        (source / "behavior_config.json").read_bytes()
    )
    fixed, _, _, _ = frozen_mode(source, "photos_only", original)
    settings = policy()
    manifest: Json = {
        "schema_version": "phase2.repair05.freeze.v1",
        "version": VERSION,
        "experiment_id": experiment_id,
        "source_locator": str(source),
        "split": package.split,
        "source_run_id": package.run_id,
        "source_sha256": package.source_sha256,
        "dataset_sha256": package.dataset_sha256,
        "source_manifest_sha256": digest(original),
        "original_detector_sha256": digest(fixed),
        "fixed_contact_population_sha256": _contacts(fixed),
        "algorithms": algorithms(),
        "policy_sha256": digest(settings),
        "config_sha256": digest(
            {
                "policy": settings,
                "algorithms": algorithms(),
                "source_config_sha256": original["config_sha256"],
            }
        ),
        "variants": {},
        "formal_phase1_acceptance": False,
        "raw_rgb_copied": False,
        "new_detector_or_render_run": False,
        "test_is_sealed_holdout": False,
        "development_selection_sha256": digest(development_selection)
        if development_selection
        else None,
        "development_selected_variant": development_selection["selected_variant"]
        if development_selection
        else None,
    }
    if development_selection:
        _save(output / "development_selection.json", development_selection)
    _save(output / "policy.json", settings)
    for name, strategy in (("baseline", "BASELINE"), ("candidate", "ROBUST_THREE_CLEAN")):
        typed_strategy: Strategy = "BASELINE" if strategy == "BASELINE" else "ROBUST_THREE_CLEAN"
        manifest["variants"][name] = {}
        for mode in MODES:
            mode_fixed, _, _, _ = frozen_mode(source, mode, original)
            if digest(mode_fixed) != digest(fixed):
                raise ValueError("REPAIR05_ORIGINAL_MODE_CONTACTS_DIFFER")
            raw, trace = trace_assignment(
                mode_fixed,
                PixelContinuityConfig(),
                strategy=typed_strategy,
            )
            perception = _namespace(raw, typed_strategy)
            if _contacts(perception) != _contacts(fixed):
                raise ValueError("REPAIR05_CONTACT_POPULATION_CHANGED")
            inference = build_inference(
                perception,
                scope=package.scope,
                context=package.context,
                policy=AssociationPolicy.model_validate(original["association_policy"]),
                topology=topology,
                retrieval_policy=RetrievalPolicy.model_validate(original["retrieval_policy"]),
            )
            # Existing composer is unchanged and retained only for downstream regression.
            events = compose_behaviors_v2(
                inference,
                source_behavior,
                tracks=perception.tracks,
                policy=BehaviorEvidencePolicy(),
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
            documents = {
                "perception": perception,
                "inference": inference,
                "events": events,
                "receipt": receipt,
                "trace": trace,
            }
            hashes = {}
            for key, value in documents.items():
                _save(output / name / mode / (key + ".json"), value)
                hashes[key] = digest(value)
            manifest["variants"][name][mode] = {
                "hashes": hashes,
                "strategy": strategy,
                "freeze_ref": receipt.receipt_sha256,
                "producer_sha256": perception.producer_sha256,
                "candidate_pool_sha256": inference.association_pool_sha256,
                "track_population_sha256": digest(
                    [track.local_track_id for track in perception.tracks]
                ),
                "behavior_config_sha256": events.config_sha256,
            }
    _save(output / "manifest.json", manifest)
    return manifest


def load(output: Path) -> tuple[Any, Any, Json, Json]:
    manifest = json.loads((output / "manifest.json").read_bytes())
    settings = json.loads((output / "policy.json").read_bytes())
    if (
        manifest["schema_version"] != "phase2.repair05.freeze.v1"
        or manifest["version"] != VERSION
        or manifest["algorithms"] != algorithms()
        or settings != policy()
        or manifest["policy_sha256"] != digest(settings)
    ):
        raise ValueError("REPAIR05_FREEZE_SOURCE_CHANGED")
    package, registry, _, original = _load(Path(manifest["source_locator"]))
    if (
        manifest["source_manifest_sha256"] != digest(original)
        or manifest["source_run_id"] != package.run_id
        or manifest["source_sha256"] != package.source_sha256
        or manifest["dataset_sha256"] != package.dataset_sha256
        or manifest["config_sha256"]
        != digest(
            {
                "policy": settings,
                "algorithms": algorithms(),
                "source_config_sha256": original["config_sha256"],
            }
        )
    ):
        raise ValueError("REPAIR05_SOURCE_BINDING_MISMATCH")
    if package.split == "test":
        selection = json.loads((output / "development_selection.json").read_bytes())
        if (
            digest(selection) != manifest["development_selection_sha256"]
            or selection["selected_variant"] != manifest["development_selected_variant"]
            or selection["algorithms"] != manifest["algorithms"]
        ):
            raise ValueError("REPAIR05_DEVELOPMENT_SELECTION_CHANGED")
    return package, registry, manifest, settings


def frozen(output: Path, variant: str, mode: str, manifest: Json) -> FrozenVariant:
    package, registry, current, _ = load(output)
    if current != manifest or variant not in manifest["variants"] or mode not in MODES:
        raise ValueError("REPAIR05_VARIANT_MODE_DENIED")
    root, expected = output / variant / mode, manifest["variants"][variant][mode]
    for key, expected_hash in expected["hashes"].items():
        path = root / (key + ".json")
        if path.is_symlink() or not path.resolve().is_relative_to(output.resolve()):
            raise ValueError("REPAIR05_ARTIFACT_PATH_DENIED")
        if digest(json.loads(path.read_bytes())) != expected_hash:
            raise ValueError("REPAIR05_ARTIFACT_HASH_MISMATCH")
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
        or binding.registry_version != VERSION
        or binding.run_id != package.run_id
        or binding.dataset_sha256 != package.dataset_sha256
        or binding.media_sha256
        != digest([(frame.media_ref, frame.sha256) for frame in registry.frames])
        or binding.config_sha256
        != digest(
            {
                "config": manifest["config_sha256"],
                "experiment": manifest["experiment_id"],
                "variant": variant,
            }
        )
        or binding.producer_sha256 != perception.producer_sha256
        or perception.producer_sha256 != expected["producer_sha256"]
        or perception.producer_version != VERSION
        or perception.input_manifest_sha256 != package.dataset_sha256
        or _contacts(perception) != manifest["fixed_contact_population_sha256"]
        or inference.scope != package.scope
        or events.scope != package.scope
        or inference.association_pool_sha256 != expected["candidate_pool_sha256"]
        or events.inference_sha256 != receipt.inference_sha256
        or events.config_sha256 != expected["behavior_config_sha256"]
    ):
        raise ValueError("REPAIR05_RECEIPT_SCOPE_MISMATCH")
    trace = json.loads((root / "trace.json").read_bytes())
    if (
        trace["input_contact_count"] != len(perception.measurements)
        or trace["gt_or_reference_content_read"]
    ):
        raise ValueError("REPAIR05_TRACE_POPULATION_OR_GT_MISMATCH")
    return FrozenVariant(perception, inference, events, receipt)
