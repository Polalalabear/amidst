"""Bounded source-bound 05 diagnostics; never import the independent truth evaluator."""

from __future__ import annotations

import copy
import json
import math
from hashlib import sha256
from pathlib import Path
from typing import Any

from amidst.engineering.access import digest
from amidst.engineering.local_pilot import _load
from amidst.engineering.registry import opaque_ref
from amidst.phase2_research.repair05_pipeline import algorithms, frozen, load

Json = dict[str, Any]


class Repair05Service:
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
            raise ValueError("REPAIR05_MANIFEST_CERTIFICATE_MISMATCH")
        state = frozen(output, variant, mode, manifest)
        self.output, self.manifest = output, manifest
        self.expected_evaluation_sha256 = expected_evaluation_sha256
        self.binding = {
            "scene_id": scene_id,
            "source_run_id": package.run_id,
            "experiment_id": manifest["experiment_id"],
            "source_sha256": package.source_sha256,
            "dataset_sha256": package.dataset_sha256,
            "config_sha256": manifest["config_sha256"],
            "freeze_ref": state.receipt.receipt_sha256,
            "mode": mode,
            "variant": variant,
            "clock_id": package.scope.clock_id,
        }
        self.cameras = {camera.camera_id for camera in registry.cameras}
        self.time_range = [
            min(frame.timestamp for frame in registry.frames),
            max(frame.timestamp for frame in registry.frames),
        ]
        _, _, _, original = _load(Path(manifest["source_locator"]))
        links = original["frame_links"]
        measured = {row.observation_id: row for row in state.perception.measurements}
        self.tracks: list[Json] = []
        for track in state.perception.tracks:
            rows = [measured[ref] for ref in track.observation_ids]
            self.tracks.append(
                {
                    "track_ref": opaque_ref(
                        "repair05track", digest(self.binding), track.local_track_id
                    ),
                    "camera_id": track.camera_id,
                    "time_range": [track.timestamps[0], track.timestamps[-1]],
                    "status": track.status,
                    "sample_count": len(rows),
                    "internal_missing_sample_count": len(track.missing_timestamps),
                    "missing_timestamps": list(track.missing_timestamps),
                    "alternative_contact_count": sum(
                        row.local_alternative_count > 0 for row in rows
                    ),
                    "uncertainty": max(row.uncertainty for row in rows),
                    "identity_confirmed": False,
                    "source_frames": [
                        {
                            "frame_ref": links[row.frame_ref],
                            "media_ref": links[row.frame_ref],
                            "camera_id": row.camera_id,
                            "timestamp": row.timestamp,
                        }
                        for row in rows[:8]
                    ],
                    "source_frames_truncated": len(rows) > 8,
                }
            )
        checks = [output / "manifest.json", output / "policy.json"]
        source = Path(manifest["source_locator"])
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
        if package.split == "test":
            checks.append(output / "development_selection.json")
        self.integrity_checks = {path: sha256(path.read_bytes()).hexdigest() for path in checks}

    def _scope(self, scene_id: str, run_id: str) -> None:
        if scene_id != self.binding["scene_id"] or run_id != self.binding["source_run_id"]:
            raise ValueError("REPAIR05_SCOPE_DENIED")
        if algorithms() != self.manifest["algorithms"]:
            raise ValueError("REPAIR05_FREEZE_SOURCE_CHANGED")
        for path, expected in self.integrity_checks.items():
            if path.is_symlink() or sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("REPAIR05_ARTIFACT_CHANGED")

    def context(self) -> Json:
        self._scope(self.binding["scene_id"], self.binding["source_run_id"])
        return {
            "schema_version": "phase2.repair05.context.v1",
            "available": True,
            "binding": copy.deepcopy(self.binding),
            "origin": "SYNTHETIC",
            "formal_phase1_acceptance": False,
            "test_is_sealed_holdout": False,
            "camera_ids": sorted(self.cameras),
            "time_range": self.time_range[:],
            "capabilities": {"diagnostics": True, "local_tracks": True, "trained_reid": False},
            "metric_definition": (
                "FRAGMENTED counts tracks with internally missing registered sampled timestamps"
            ),
        }

    def diagnostics(self) -> Json:
        self._scope(self.binding["scene_id"], self.binding["source_run_id"])
        if self.expected_evaluation_sha256 is None:
            return {
                "schema_version": "phase2.repair05.diagnostics.v1",
                "status": "UNAVAILABLE",
                "reason": "AGGREGATE_NOT_REGISTERED",
                "binding": copy.deepcopy(self.binding),
            }
        paths = [self.output / "evaluation.json", self.output / "evaluation_receipt.json"]
        if any(path.is_symlink() for path in paths):
            raise ValueError("REPAIR05_EVALUATION_PATH_DENIED")
        evaluation, receipt = (json.loads(path.read_bytes()) for path in paths)
        if (
            digest(evaluation) != self.expected_evaluation_sha256
            or receipt["evaluation_sha256"] != digest(evaluation)
            or evaluation["manifest_sha256"] != digest(self.manifest)
            or receipt["manifest_sha256"] != digest(self.manifest)
            or receipt["algorithms"] != self.manifest["algorithms"]
            or evaluation["dataset_sha256"] != self.binding["dataset_sha256"]
            or evaluation["config_sha256"] != self.binding["config_sha256"]
            or evaluation["source_run_id"] != self.binding["source_run_id"]
        ):
            raise ValueError("REPAIR05_EVALUATION_CERTIFICATE_MISMATCH")
        return {
            "schema_version": "phase2.repair05.diagnostics.v1",
            "status": "CERTIFIED_AGGREGATE",
            "binding": copy.deepcopy(self.binding),
            "evaluation": evaluation,
            "formal_phase1_acceptance": False,
        }

    def query(self, scene_id: str, run_id: str, camera_id: str, start: float, end: float) -> Json:
        self._scope(scene_id, run_id)
        if camera_id not in self.cameras:
            raise ValueError("REPAIR05_CAMERA_SCOPE_DENIED")
        if (
            any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                for value in (start, end)
            )
            or start < self.time_range[0]
            or end > self.time_range[1]
            or end < start
            or end - start > 120
        ):
            raise ValueError("REPAIR05_TIME_SCOPE_DENIED")
        rows = [
            row
            for row in self.tracks
            if row["camera_id"] == camera_id
            and row["time_range"][0] <= end
            and row["time_range"][1] >= start
        ]
        return {
            "schema_version": "phase2.repair05.query.v1",
            "binding": copy.deepcopy(self.binding),
            "camera_id": camera_id,
            "time_range": [start, end],
            "tracks": copy.deepcopy(rows[:64]),
            "truncated": len(rows) > 64,
            "total_matching_tracks": len(rows),
            "identity_confirmed": False,
            "source_frames_are_original_registered_media": True,
        }


def load_service(
    output: Path,
    *,
    scene_id: str = "local-camera-accuracy-v2",
    variant: str = "baseline",
    mode: str = "photos_only",
    expected_manifest_sha256: str | None = None,
    expected_evaluation_sha256: str | None = None,
) -> Repair05Service:
    return Repair05Service(
        output,
        scene_id=scene_id,
        variant=variant,
        mode=mode,
        expected_manifest_sha256=expected_manifest_sha256,
        expected_evaluation_sha256=expected_evaluation_sha256,
    )
