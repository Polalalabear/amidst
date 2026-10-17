"""Scene-local contact measurements and response-only quality flags.

The Office index and all its certificates remain unchanged. Mask membership uses
RGB only, at the exact camera/frame, and never associates through time or GT.
"""

from __future__ import annotations

import copy
import hashlib
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from amidst.engineering.perception import _components
from amidst.engineering.perception_v2 import VERSION, ContactConfig, components8, produce_contact_v2
from amidst.engineering.registry import content_hash, opaque_ref
from amidst.workbench.blender_scene import BlenderSceneAdapter
from amidst.workbench.frame_baseline import BaselineFrameIndex, _Inputs
from amidst.workbench.scene_errors import DataIntegrityError, integrity_error, public_reason

Json = dict[str, Any]
AUTHORITY = "QUALITY_FLAG_ONLY_POSITION_UNCHANGED"


def quality(component: Json | None, *, merged: bool = False) -> Json:
    reasons = list(component["reasons"]) if component else []
    if merged and "AMBIGUOUS_MERGE" not in reasons:
        reasons.append("AMBIGUOUS_MERGE")
    sensitivity = (component.get("pixel_sensitivity") or {}) if component else {}
    return {
        "version": VERSION,
        "status": "NOT_EVALUATED" if component is None else "FLAGGED" if reasons else "PASS",
        "reasons": reasons,
        "pixel_sensitivity_m": sensitivity.get("max_displacement_m"),
        "authority": AUTHORITY,
    }


def component_mapping(v1_pixels, masks, point, components):
    """Prefer exact 4-connected mask ownership; bbox is only a fallback."""
    if v1_pixels is not None:
        hits = []
        old = {tuple(pixel) for pixel in v1_pixels.tolist()}
        for index, mask in enumerate(masks):
            if old and old.issubset({tuple(pixel) for pixel in mask.tolist()}):
                hits.append(index)
    else:
        x, y = point
        hits = [
            i
            for i, component in enumerate(components)
            if component["bbox_xyxy"][0] <= x < component["bbox_xyxy"][2]
            and component["bbox_xyxy"][1] <= y < component["bbox_xyxy"][3]
        ]
    return (
        (hits[0], []) if len(hits) == 1 else (None, ["AMBIGUOUS_MAPPING"] if len(hits) > 1 else [])
    )


def match_quality(
    inputs: Json,
    observations: list[Json],
    prediction: Json,
    config: ContactConfig,
    component_matches: dict[str, Json] | None = None,
) -> dict[str, Json]:
    """Map each v1 mask to its unique v2 owner at the same camera/frame.

    v1 uses the original >30 difference and 4-connected components. A v1
    component's pixels belong to one 8-connected v2 component. Only when the
    original component cannot be recovered do we fall back to bbox membership.
    """
    predicted = {r["frame_ref"]: r for r in prediction["frames"]}
    result = {r["observation_ref"]: quality(None) for r in observations}
    for camera_id in sorted({r["camera_id"] for r in inputs["frames"]}):
        frames = [r for r in inputs["frames"] if r["camera_id"] == camera_id]
        images = {}
        for frame in frames:
            raw = Path(frame["local_path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != frame["sha256"]:
                raise ValueError("QUALITY_RGB_HASH_MISMATCH")
            with Image.open(frame["local_path"]) as image:
                images[frame["frame_ref"]] = np.asarray(image).copy()
        background = np.median(np.stack(list(images.values())), axis=0).astype(np.int16)
        for frame in frames:
            ref = frame["frame_ref"]
            difference = np.max(abs(images[ref].astype(np.int16) - background), axis=2)
            masks = components8(difference > config.difference_threshold, config.min_pixels)
            old_components = _components(difference > 30)
            measured = predicted[ref]["components"]
            if len(masks) != len(measured):
                raise ValueError("QUALITY_COMPONENT_MISMATCH")
            memberships = []
            for observation in observations:
                if observation["camera_id"] != camera_id or observation["frame_ref"] != ref:
                    continue
                candidates = [
                    c[4] for c in old_components if list(c[:4]) == observation["bbox_xyxy"]
                ]
                pixels = candidates[0] if len(candidates) == 1 else None
                index, reasons = component_mapping(
                    pixels, masks, observation["contact_pixel"], measured
                )
                if index is not None:
                    memberships.append((observation["observation_ref"], index))
                elif reasons:
                    result[observation["observation_ref"]]["reasons"] = reasons
            counts = Counter(i for _, i in memberships)
            for observation_ref, i in memberships:
                result[observation_ref] = quality(measured[i], merged=counts[i] > 1)
                if component_matches is not None:
                    component_matches[observation_ref] = copy.deepcopy(measured[i])
    return result


class ContactFrameIndex(BaselineFrameIndex):
    """Reuse bounded camera/time retrieval with exclusively v2 pixel positions.

    No temporal association or interpolation has been materialized for this run.
    Local tracks are deliberately absent, rather than copied from v1 or Office.
    """

    def __init__(self, inputs: Json, prediction: Json) -> None:
        value = _Inputs.model_validate(inputs)
        self._binding = value.source_binding.model_dump(mode="json")
        self._camera_ids = frozenset(c.camera_id for c in value.cameras)
        self._plane_binding = value.floor_plane.model_dump(mode="json")
        self._calibration_sha256 = prediction["calibration_sha256"]
        self._baseline_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self._local_tracks = ()
        observations, records = [], {}
        frames = {r.frame_ref: r for r in value.frames}
        for frame in prediction["frames"]:
            source = frames[frame["frame_ref"]]
            found = []
            for component in frame["components"]:
                valid = component["world_position"] is not None
                row = {
                    "observation_ref": opaque_ref(
                        "observation", self._binding["run_id"], component["component_ref"]
                    ),
                    "track_ref": opaque_ref(
                        "track", self._binding["run_id"], component["component_ref"]
                    ),
                    "frame_ref": source.frame_ref,
                    "camera_id": source.camera_id,
                    "timestamp": float(source.timestamp),
                    "bbox_xyxy": component["bbox_xyxy"],
                    "contact_pixel": component["contact_pixel"],
                    "uncertainty": 0.0 if valid else 1.0,
                    "measurement_status": "DETECTED" if valid else "MERGED_OR_PARTIAL",
                    "local_alternative_count": len(frame["components"]),
                    "projection_status": "PROJECTED" if valid else "PROJECTION_MISSING",
                    "projection_reason": component["reasons"][0] if component["reasons"] else None,
                    "world_position": component["world_position"],
                    "projection_quality": component.get("incidence"),
                    "source_image_sha256": source.sha256,
                    "measurement_basis": "RGB_PIXELS",
                    "geometry_authority": "SOURCE_BOUND_FLOOR_INTERSECTION_ONLY",
                    "identity_verdict": "UNCONFIRMED",
                    "behavior_verdict": "UNKNOWN",
                    "state": "PROJECTED_OBSERVATION" if valid else "MISSING",
                    "missing_reason": None if valid else list(component["reasons"]),
                }
                observations.append(row)
                found.append(row)
            best = (
                min(found, key=lambda r: (r["world_position"] is None, r["observation_ref"]))
                if found
                else {}
            )
            records[source.frame_ref] = {
                "frame_ref": source.frame_ref,
                "media_ref": source.frame_ref,
                "camera_id": source.camera_id,
                "timestamp": float(source.timestamp),
                "width": source.width,
                "height": source.height,
                "source_image_sha256": source.sha256,
                "byte_count": source.byte_count,
                "frame_status": frame["status"],
                "measurement_count": len(found),
                "image_measurement": bool(found),
                **{
                    key: best.get(key)
                    for key in (
                        "observation_ref",
                        "track_ref",
                        "bbox_xyxy",
                        "contact_pixel",
                        "uncertainty",
                        "projection_quality",
                        "world_position",
                    )
                },
                "measurement_status": best.get("measurement_status", "NO_MEASUREMENT"),
                "projection_status": best.get("projection_status", "NOT_ATTEMPTED"),
                "projection_reason": best.get("projection_reason"),
                "state": best.get("state", "MISSING"),
                "missing_reason": best.get("missing_reason", frame["reasons"]),
                "measurement_basis": "RGB_PIXELS",
                "geometry_authority": "SOURCE_BOUND_FLOOR_INTERSECTION_ONLY",
                "identity_verdict": "UNCONFIRMED",
                "behavior_verdict": "UNKNOWN",
            }
        self._observations = tuple(observations)
        self._records = records
        self._buckets = {
            c: tuple(
                sorted(
                    (r for r in records.values() if r["camera_id"] == c),
                    key=lambda r: r["timestamp"],
                )
            )
            for c in self._camera_ids
        }
        self._times = {c: tuple(r["timestamp"] for r in rows) for c, rows in self._buckets.items()}
        self._steps = {
            c: min((b - a for a, b in zip(t, t[1:], strict=False) if b > a), default=0)
            for c, t in self._times.items()
        }
        self.source_features = content_hash(
            {"prediction": prediction, "index_sha256": self._baseline_sha256}
        )
        self._telemetry = {
            "gt_used": False,
            "agent_calls": 0,
            "external_model_calls": 0,
            "producer_sha256": prediction["producer_sha256"],
            "pixel_measurements": len(observations),
            "local_tracks": 0,
            "projected_measurements": sum(r["world_position"] is not None for r in observations),
            "complete": prediction["complete"],
        }

    def snapshot(self) -> Json:
        result = super().snapshot()
        result["baseline_version"] = VERSION
        return result


class ContactQualityScene(BlenderSceneAdapter):
    """Add flags at response boundaries, leaving the frozen index untouched."""

    def __init__(
        self,
        root: Path,
        *,
        contact_config: ContactConfig,
        perception_version: str = "rgb-mask-contact-v1",
        validation_pin=None,
        hybrid_config: Json | None = None,
        hybrid_config_sha256: str | None = None,
    ):
        self._qualities: dict[str, Json] = {}
        self._ground_estimates: dict[str, Json] = {}
        component_matches: dict[str, Json] = {}
        self._v2 = perception_version == VERSION
        if perception_version not in {"rgb-mask-contact-v1", VERSION}:
            raise ValueError("UNSUPPORTED_PERCEPTION_VERSION")
        prediction = None

        def check_declared_target(inputs):
            if hybrid_config is None:
                return
            if hybrid_config_sha256 is None or len(hybrid_config_sha256) != 64:
                raise ValueError("HYBRID_CONFIG_HASH_REQUIRED")
            declaration = hybrid_config["runs"].get(inputs["source_binding"]["run_id"])
            if declaration and (
                contact_config.assumed_target_height_m != declaration["target_proxy"]["height_m"]
                or contact_config.assumed_target_radius_m != declaration["body_radius_m"]
            ):
                raise ValueError("CONTACT_TARGET_DECLARATION_MISMATCH")

        def factory(inputs):
            nonlocal prediction
            check_declared_target(inputs)
            prediction = produce_contact_v2(inputs, contact_config)
            self._verify_prediction(prediction)
            return ContactFrameIndex(inputs, prediction)

        super().__init__(
            root,
            validation_pin=validation_pin,
            index_factory=factory if self._v2 else None,
            enable_reconstruction=not self._v2,
        )
        if self.index.telemetry.get("frame_status_counts", {}).get("HASH_MISMATCH", 0):
            raise DataIntegrityError("RGB_HASH_MISMATCH")
        check_declared_target(self._inputs)
        if self._v2:
            self._snapshot["layer_availability"] = {
                "perception": {"status": "AVAILABLE", "version": VERSION},
                **{
                    layer: {"status": "UNAVAILABLE", "reason": "NOT_MATERIALIZED_FOR_RUN"}
                    for layer in ("motion", "association", "physical_source", "physical")
                },
            }
            self._snapshot["capabilities"].update(physical_review=False, camera_frame_wall=True)
        prediction, component_matches = self._set_qualities(prediction, contact_config)

        if hybrid_config is not None:
            from amidst.domain.camera import Camera
            from amidst.domain.geometry import Plane
            from amidst.engineering.hybrid_contact import estimate_contact

            floor = self._inputs["floor_plane"]
            plane = Plane(
                plane_id="hybrid-floor",
                point=floor["point"],
                normal=floor["normal"],
                floor_id=floor["floor_id"],
            )
            cameras = {
                r["camera_id"]: Camera.model_validate(r["calibration"])
                for r in self._inputs["cameras"]
            }
            binding = self._inputs["source_binding"]
            provenance = {
                "scene_id": self.scene_id,
                "run_ref": self.run_id,
                "clock_id": binding["clock_id"],
                "source_sha256": self.source_hash,
                "safe_inputs_sha256": hashlib.sha256(self._inputs_raw).hexdigest(),
                "producer": "hybrid-ground-estimator",
                "producer_version": "v1",
                "config_sha256": hybrid_config_sha256,
                "annotation_sha256": {"occluders": None, "walkable": None},
                "gt_read": False,
            }
            hybrid_qualities = dict(self._qualities)
            for ref, component in component_matches.items():
                if ref not in hybrid_qualities:
                    hybrid_qualities[ref] = quality(component)
            self._ground_estimates = {
                r["observation_ref"]: estimate_contact(
                    r,
                    component_matches.get(r["observation_ref"]),
                    hybrid_qualities.get(r["observation_ref"]),
                    cameras[r["camera_id"]],
                    plane,
                    provenance,
                    hybrid_config,
                )
                for r in self.index.observations
            }

    @staticmethod
    def _verify_prediction(prediction):
        if any("RGB_HASH_MISMATCH" in frame["reasons"] for frame in prediction["frames"]):
            raise DataIntegrityError("RGB_HASH_MISMATCH")

    def _set_qualities(self, prediction, config):
        matches = {}
        try:
            if prediction is None:
                prediction = produce_contact_v2(self._inputs, config)
                self._verify_prediction(prediction)
            if self._v2:
                matches = {
                    opaque_ref("observation", self.run_id, c["component_ref"]): c
                    for f in prediction["frames"]
                    for c in f["components"]
                }
                self._qualities = {
                    ref: quality(c) for ref, c in matches.items() if c["world_position"] is not None
                }
            else:
                self._qualities = match_quality(
                    self._inputs, self.index.observations, prediction, config, matches
                )
            return prediction, matches
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
            if integrity_error(error):
                raise
            reason = public_reason(error, "QUALITY_MAPPING_FAILED")
            unevaluated = quality(None) | {"reasons": [reason]}
            self._qualities = {
                r["observation_ref"]: copy.deepcopy(unevaluated)
                for r in self.index.observations
                if not self._v2 or r["world_position"] is not None
            }
            self._snapshot["contact_quality_status"] = {"status": "NOT_EVALUATED", "reason": reason}
            return None, {}

    def with_display_identity(self, scene_id, label, description):
        scene = super().with_display_identity(scene_id, label, description)
        scene._ground_estimates = copy.deepcopy(self._ground_estimates)
        for estimate in scene._ground_estimates.values():
            estimate["provenance"]["scene_id"] = scene_id
            estimate.pop("output_sha256", None)
            estimate["output_sha256"] = content_hash(estimate)
        return scene

    def _annotate(self, value):
        if isinstance(value, list):
            return [self._annotate(item) for item in value]
        if isinstance(value, dict):
            result = {
                key: item
                if key
                in {
                    "presentation",
                    "objects",
                    "cameras",
                    "contact_quality",
                    "ground_estimate",
                    "blind_hypotheses",
                    "review_evidence",
                    "pruning_convergence",
                }
                else self._annotate(item)
                for key, item in value.items()
            }
            ref = value.get("observation_ref")
            if ref and ref in self._qualities:
                result["contact_quality"] = copy.deepcopy(self._qualities[ref])
            if ref and ref in self._ground_estimates:
                result["ground_estimate"] = copy.deepcopy(self._ground_estimates[ref])
            return result
        return value

    def annotate_contact_quality(self, value):
        return self._annotate(value)

    def snapshot(self):
        return self._annotate(super().snapshot())

    def query(self, *args, **kwargs):
        return self._annotate(super().query(*args, **kwargs))

    def frame_query(self, *args, **kwargs):
        return self._annotate(super().frame_query(*args, **kwargs))

    def motion_reconstruction(self, *args, **kwargs):
        return self._annotate(super().motion_reconstruction(*args, **kwargs))

    def cross_camera_reconstruction(self, *args, **kwargs):
        return self._annotate(super().cross_camera_reconstruction(*args, **kwargs))

    def physical_cross_camera_reconstruction(self, *args, **kwargs):
        return self._annotate(super().physical_cross_camera_reconstruction(*args, **kwargs))

    def physical_review(self, *args, **kwargs):
        return self._annotate(super().physical_review(*args, **kwargs))
