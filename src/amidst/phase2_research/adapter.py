"""Bounded read-only research DTOs; no runtime inference or evaluator sidecar reads."""

from __future__ import annotations

import copy
import json
import math
from bisect import bisect_left, bisect_right
from hashlib import sha256
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_pilot import _load
from amidst.engineering.registry import opaque_ref
from amidst.phase2_research.pipeline import frozen, load
from amidst.research_accuracy.association import rank_association_hypotheses

Json = dict[str, Any]


class ResearchService:
    def __init__(
        self,
        output: Path,
        *,
        scene_id: str,
        variant: str,
        mode: str,
        expected_manifest_sha256: str | None = None,
        expected_evaluation_sha256: str | None = None,
    ):
        package, registry, manifest, _ = load(output)
        if expected_manifest_sha256 is not None and digest(manifest) != expected_manifest_sha256:
            raise ValueError("RESEARCH_MANIFEST_CERTIFICATE_MISMATCH")
        state = frozen(output, variant, mode, manifest)
        self.output, self.manifest = output, manifest
        self.expected_evaluation_sha256 = expected_evaluation_sha256
        if self.expected_evaluation_sha256 is None:
            certificate = Path(__file__).parents[3] / (
                "data/engineering/phase2_abc_20261013/research_release.json"
            )
            if certificate.is_file():
                registered = json.loads(certificate.read_bytes())
                if registered.get("manifest_sha256") == digest(manifest):
                    self.expected_evaluation_sha256 = registered.get("evaluation_sha256")
        source = Path(manifest["source_locator"])
        checks = [output / "manifest.json", output / "policy.json"]
        checks.extend(
            source / name
            for name in (
                "manifest.json",
                "package.json",
                "registry.json",
                "topology.json",
                "runtime_config.json",
                "behavior_config.json",
            )
        )
        checks.extend(
            output / variant / mode / (name + ".json")
            for name in manifest["variants"][variant][mode]["hashes"]
        )
        self.integrity_checks = {path: sha256(path.read_bytes()).hexdigest() for path in checks}
        self.integrity_metadata_bytes_read = 0
        self.binding = {
            "scene_id": scene_id,
            "source_run_id": package.run_id,
            "experiment_id": manifest["experiment_id"],
            "source_sha256": package.source_sha256,
            "dataset_sha256": package.dataset_sha256,
            "config_sha256": manifest["config_sha256"],
            "freeze_ref": state.receipt.receipt_sha256,
            "clock_id": package.scope.clock_id,
            "variant": variant,
            "mode": mode,
        }
        self.cameras = {camera.camera_id for camera in registry.cameras}
        _, _, _, source_manifest = _load(Path(manifest["source_locator"]))
        links = source_manifest["frame_links"]
        rules = json.loads((output / variant / mode / "rules.json").read_bytes())
        self.events: dict[str, Json] = {}
        for original in rules["events"]:
            row = {
                key: copy.deepcopy(original[key])
                for key in (
                    "kind",
                    "region_id",
                    "camera_id",
                    "time_range",
                    "support_state",
                    "state",
                    "active",
                    "lifecycle",
                    "rule_version",
                    "config_sha256",
                    "evidence_count",
                    "all_evidence_sha256",
                    "missing_evidence",
                    "uncertainty",
                )
            }
            row["event_ref"] = opaque_ref(
                "researchevent", digest(self.binding), original["event_id"]
            )
            row["detail_ref"] = row["event_ref"]
            row["local_track_ref"] = opaque_ref(
                "researchtrack", digest(self.binding), original["local_track_id"]
            )
            row["dedupe_key"] = original["dedupe_key"]
            row["source_frames"] = [
                frame
                | {"frame_ref": links[frame["frame_ref"]], "media_ref": links[frame["frame_ref"]]}
                for frame in original["source_frames"]
            ]
            row["media_refs"] = [frame["media_ref"] for frame in row["source_frames"]]
            self.events[row["event_ref"]] = row
        self.rules_denominators = rules["denominators"]
        measurements = {row.observation_id: row for row in state.perception.measurements}
        self.associations = []
        ranked = rank_association_hypotheses(state.inference)
        ranks = {row.hypothesis_id: index + 1 for index, row in enumerate(ranked)}
        for hypothesis in state.inference.association_hypotheses:
            samples = [measurements[ref] for ref in hypothesis.pixel_observation_ids]
            if not samples:
                continue
            ref = opaque_ref("researchassociation", digest(self.binding), hypothesis.hypothesis_id)
            self.associations.append(
                {
                    "association_ref": ref,
                    "kind": hypothesis.kind,
                    "status": hypothesis.status,
                    "reason": hypothesis.reason,
                    "rank": ranks.get(hypothesis.hypothesis_id),
                    "camera_ids": list(dict.fromkeys(row.camera_id for row in samples)),
                    "time_range": [
                        min(row.timestamp for row in samples),
                        max(row.timestamp for row in samples),
                    ],
                    "local_track_refs": [
                        opaque_ref("researchtrack", digest(self.binding), ref)
                        for ref in hypothesis.local_track_ids
                    ],
                    "scores_are_probabilities": False,
                    "identity_confirmed": False,
                    "uncertainty": hypothesis.uncertainty,
                }
            )
        self._event_index = self._index(list(self.events.values()), key="camera_id")
        self._association_index = self._index(self.associations, key="camera_ids")

    @staticmethod
    def _index(
        rows: list[Json], *, key: str
    ) -> dict[str, tuple[list[Json], list[float], list[float]]]:
        buckets: dict[str, list[Json]] = {}
        for row in rows:
            cameras = row[key] if isinstance(row[key], list) else [row[key]]
            for camera in cameras:
                buckets.setdefault(camera, []).append(row)
        result = {}
        for camera, bucket in buckets.items():
            bucket.sort(key=lambda row: (row["time_range"][0], row["time_range"][1]))
            ends: list[float] = []
            for row in bucket:
                ends.append(max(row["time_range"][1], ends[-1] if ends else 0))
            result[camera] = (bucket, [row["time_range"][0] for row in bucket], ends)
        return result

    def _scope(self, scene_id: str, run_id: str) -> None:
        if scene_id != self.binding["scene_id"] or run_id != self.binding["source_run_id"]:
            raise ValueError("RESEARCH_SCOPE_DENIED")
        from amidst.phase2_research.pipeline import algorithms

        if algorithms() != self.manifest["algorithms"]:
            raise ValueError("RESEARCH_FREEZE_SOURCE_CHANGED")
        self.integrity_metadata_bytes_read = 0
        for path, expected in self.integrity_checks.items():
            if path.is_symlink():
                raise ValueError("RESEARCH_ARTIFACT_PATH_DENIED")
            payload = path.read_bytes()
            self.integrity_metadata_bytes_read += len(payload)
            if sha256(payload).hexdigest() != expected:
                raise ValueError("RESEARCH_MANIFEST_OR_ARTIFACT_CHANGED")

    def context(self) -> Json:
        self._scope(self.binding["scene_id"], self.binding["source_run_id"])
        return {
            "schema_version": "phase2.research.context.v1",
            "binding": copy.deepcopy(self.binding),
            "available": True,
            "origin": "SYNTHETIC",
            "authority": "SYNTHETIC_CONFIG",
            "formal_phase1_acceptance": False,
            "external_model_calls": False,
            "capabilities": {
                "diagnostics": True,
                "region_events": True,
                "association_hypotheses": True,
                "trained_reid": False,
            },
            "camera_ids": sorted(self.cameras),
            "event_kinds": ["REGION_ENTRY", "REGION_EXIT", "SUSTAINED_DWELL"],
            "rule_denominators": copy.deepcopy(self.rules_denominators),
        }

    def diagnostics(self) -> Json:
        self._scope(self.binding["scene_id"], self.binding["source_run_id"])
        path, receipt_path = (
            self.output / "evaluation.json",
            self.output / "evaluation_receipt.json",
        )
        if not path.is_file() or not receipt_path.is_file():
            return {
                "schema_version": "phase2.research.diagnostics.v1",
                "status": "UNAVAILABLE",
                "binding": copy.deepcopy(self.binding),
            }
        if self.expected_evaluation_sha256 is None:
            return {
                "schema_version": "phase2.research.diagnostics.v1",
                "status": "UNAVAILABLE",
                "reason": "AGGREGATE_NOT_REGISTERED",
                "binding": copy.deepcopy(self.binding),
            }
        if path.is_symlink() or receipt_path.is_symlink():
            raise ValueError("RESEARCH_EVALUATION_PATH_DENIED")
        evaluation = json.loads(path.read_bytes())
        receipt = json.loads(receipt_path.read_bytes())
        if (
            receipt["manifest_sha256"] != digest(self.manifest)
            or digest(evaluation) != self.expected_evaluation_sha256
            or receipt["evaluation_sha256"] != digest(evaluation)
            or evaluation["manifest_sha256"] != digest(self.manifest)
            or evaluation["config_sha256"] != self.binding["config_sha256"]
            or evaluation["dataset_sha256"] != self.binding["dataset_sha256"]
            or receipt["algorithms"] != self.manifest["algorithms"]
        ):
            raise ValueError("RESEARCH_EVALUATION_CERTIFICATE_MISMATCH")
        return {
            "schema_version": "phase2.research.diagnostics.v1",
            "status": "CERTIFIED_AGGREGATE",
            "binding": copy.deepcopy(self.binding),
            "evaluation": evaluation,
            "formal_phase1_acceptance": False,
            "trained_reid": False,
        }

    @staticmethod
    def _lookup(
        index: dict[str, tuple[list[Json], list[float], list[float]]],
        camera: str,
        start: float,
        end: float,
    ) -> tuple[list[Json], int, bool]:
        bucket, starts, ends = index.get(camera, ([], [], []))
        left, right = bisect_left(ends, start), bisect_right(starts, end)
        selected: list[Json] = []
        read = 0
        for row in bucket[left:right]:
            read += 1
            if row["time_range"][1] < start:
                continue
            if len(selected) == 64:
                return selected, read, True
            selected.append(row)
        return selected, read, False

    def query(self, scene_id: str, run_id: str, camera_id: str, start: float, end: float) -> Json:
        self._scope(scene_id, run_id)
        if camera_id not in self.cameras:
            raise ValueError("RESEARCH_CAMERA_SCOPE_DENIED")
        if (
            any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in (start, end)
            )
            or start < 0
            or end < start
            or end - start > 120
        ):
            raise ValueError("RESEARCH_TIME_SCOPE_DENIED")
        events, event_reads, event_truncated = self._lookup(
            self._event_index, camera_id, start, end
        )
        associations, pair_reads, pair_truncated = self._lookup(
            self._association_index, camera_id, start, end
        )
        return {
            "schema_version": "phase2.research.query.v1",
            "binding": copy.deepcopy(self.binding),
            "camera_id": camera_id,
            "time_range": [start, end],
            "events": copy.deepcopy(events),
            "association_hypotheses": copy.deepcopy(associations),
            "retrieval": {
                "records_read": event_reads + pair_reads,
                "event_records_read": event_reads,
                "association_records_read": pair_reads,
                "global_scan": False,
                "truncated": event_truncated or pair_truncated,
                "query_limit_per_kind": 64,
                "integrity_metadata_bytes_read": self.integrity_metadata_bytes_read,
                "frames_read": 0,
                "rgb_bytes_read": 0,
            },
            "formal_phase1_acceptance": False,
        }

    def event(self, scene_id: str, run_id: str, event_ref: str) -> Json:
        self._scope(scene_id, run_id)
        if event_ref not in self.events:
            raise ValueError("RESEARCH_EVENT_SCOPE_DENIED")
        return {
            "schema_version": "phase2.research.event.v1",
            "binding": copy.deepcopy(self.binding),
            "event": copy.deepcopy(self.events[event_ref]),
            "formal_phase1_acceptance": False,
        }


def load_service(
    output: Path,
    *,
    scene_id: str = "local-camera-accuracy-v2",
    variant: str = "selected",
    mode: str = "photos_plus_observations",
    expected_manifest_sha256: str | None = None,
    expected_evaluation_sha256: str | None = None,
) -> ResearchService:
    return ResearchService(
        output,
        scene_id=scene_id,
        variant=variant,
        mode=mode,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_evaluation_sha256=expected_evaluation_sha256,
    )
