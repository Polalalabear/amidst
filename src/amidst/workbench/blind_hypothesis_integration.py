"""Server-resolved D18 endpoints and source map; K1/K5 remain pure modules."""

from __future__ import annotations

import copy
import hashlib
import json
import time

from amidst.blind_hypothesis import generate_blind_hypotheses, pruning_convergence_summary
from amidst.engineering.hybrid_contact import k1_endpoint_eligibility
from amidst.engineering.registry import content_hash
from amidst.geometry.source_floor_map import load_polygon_floor_map
from amidst.workbench.scene_errors import DataIntegrityError


def _pinned(repo, relative, expected):
    path = repo / relative
    if path.is_symlink() or not path.resolve().is_relative_to(repo.resolve()):
        raise DataIntegrityError("HYPOTHESIS_PATH_REJECTED")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise DataIntegrityError("HYPOTHESIS_FILE_HASH_MISMATCH")
    return json.loads(raw)


def bind_hypotheses(scene, fixture_path, repo, binding_path):
    """Only trusted preset registration calls this; no client paths or overrides."""
    binding = json.loads((repo / binding_path).read_bytes())
    fixture = _pinned(repo, str(fixture_path.relative_to(repo)), binding["fixture_sha256"])
    scope = scene.live_scope()
    if any(scope.get(k) != binding[k] for k in ("run_id", "clock_id", "source_sha256")) or (
        scene.scene_id != binding["scene_id"]
        or hashlib.sha256(scene._inputs_raw).hexdigest() != binding["safe_inputs_sha256"]
    ):
        raise DataIntegrityError("HYPOTHESIS_SOURCE_BINDING_MISMATCH")
    try:
        config = _pinned(repo, binding["config"], binding["config_sha256"])
    except FileNotFoundError:
        config = {}  # K1 emits SPEED_CONFIG_UNAVAILABLE; never borrow another run.
    try:
        map_bundle = _pinned(repo, binding["map"], binding["map_sha256"])
        variant = map_bundle["variants"][binding["map_variant"]]
        declared = fixture["run_configuration"]
        if (
            variant["parameters"]["run_id"] != scene.run_id
            or variant["parameters"]["body_height_m"] != declared["height_m"]
            or variant["parameters"]["body_radius_m"] != declared["body_radius_m"]
            or abs(variant["floor_z_m"] - scene._inputs["floor_plane"]["point"][2]) > 1e-9
        ):
            raise DataIntegrityError("HYPOTHESIS_MAP_RUN_PARAMETERS_MISMATCH")
        floor_map = load_polygon_floor_map(
            repo / binding["map"],
            variant=binding["map_variant"],
            expected_sha256=binding["map_sha256"],
            expected_source_sha256=scene.source_hash,
        )
    except FileNotFoundError:
        floor_map = None
    except ValueError as error:
        raise DataIntegrityError("HYPOTHESIS_MAP_INTEGRITY_MISMATCH") from error
    if config:
        parameters = config["scenes"].get(scene.scene_id, {})
        if parameters.get("body_radius_m") != fixture["run_configuration"]["body_radius_m"] or (
            parameters.get("time_step_s") != 1 / fixture["sampling_hz"]
        ):
            raise DataIntegrityError("HYPOTHESIS_CONFIG_RUN_PARAMETERS_MISMATCH")
    scene._blind_hypothesis = BlindHypothesisIntegration(scene, fixture, binding, config, floor_map)
    scene._snapshot["capabilities"]["blind_hypotheses"] = True
    if binding.get("visibility_index"):
        from amidst.workbench.frame_retrieval import FrameRetrievalIndex

        try:
            visibility = _pinned(
                repo, binding["visibility_index"], binding["visibility_index_sha256"]
            )
        except FileNotFoundError:
            visibility = None
            scene._blind_hypothesis.negative_evidence_status = (
                "UNAVAILABLE_VISIBILITY_INDEX_MISSING"
            )
        if visibility is not None:
            interval = fixture["blind_interval"]
            retrieval = FrameRetrievalIndex.from_scene(
                scene,
                visibility,
                binding["visibility_index_sha256"],
                [interval["start_s"], interval["end_s"]],
            )
            scene._frame_retrieval = retrieval
            context = scene._blind_hypothesis
            context.evidence_validator = retrieval.verify_evidence_frames
            baseline = retrieval.baseline_entries()
            context.baseline_refs = [e["negative_evidence_ref"] for e in baseline]
            context.negative_evidence.update({e["negative_evidence_ref"]: e for e in baseline})
            context.visibility_index_ref = {
                "index_ref": "visindex:" + binding["visibility_index_sha256"][:24],
                "sha256": binding["visibility_index_sha256"],
                "method": "SOURCE_MESH_RAYCAST",
            }
            scene._snapshot["capabilities"]["frame_retrieval"] = True
    if binding.get("restricted_policy"):
        from amidst.geometry.restricted_policy import load_restricted_policy

        scene._blind_hypothesis.restricted_policy_input = load_restricted_policy(
            repo / binding["restricted_policy"],
            variant=binding["map_variant"],
            expected_sha256=binding["restricted_policy_sha256"],
            expected_source_sha256=scene.source_hash,
            expected_physical_sha256=binding["map_sha256"],
        )


class BlindHypothesisIntegration:
    def __init__(self, scene, fixture, binding, config, floor_map):
        self.scene, self.fixture, self.binding = scene, fixture, binding
        self.config, self.floor_map = config, floor_map
        # C5 may register validated entries server-side; clients only resolve refs.
        # No RGB absence -> visible-floor claim; no renderer visibility is read.
        self.negative_evidence = {}
        self.baseline_refs = []
        self.visibility_index_ref = None
        self.evidence_validator = None
        self.restricted_policy_input = None
        self.negative_evidence_status = binding["negative_evidence_status"]

    def reconstruct(self, request, previous=None):
        interval = self.fixture["blind_interval"]
        observations = {r["observation_ref"]: r for r in self.scene.index.observations}
        endpoints, guards = [], []
        for side in ("start", "end"):
            ref = interval[side + "_observation_ref"]
            row = observations.get(ref)
            estimate = copy.deepcopy(self.scene._ground_estimates.get(ref))
            guard = None if estimate is None else k1_endpoint_eligibility(estimate)
            if estimate is not None and (
                row is None
                or row["timestamp"] != interval[side + "_s"]
                or row["camera_id"] != interval[side + "_camera_id"]
                or estimate["provenance"].get("run_ref") != self.scene.run_id
                or estimate["provenance"].get("clock_id") != self.binding["clock_id"]
                or estimate["provenance"].get("source_sha256") != self.binding["source_sha256"]
                or estimate["provenance"].get("safe_inputs_sha256")
                != self.binding["safe_inputs_sha256"]
                or content_hash({k: v for k, v in estimate.items() if k != "output_sha256"})
                != estimate.get("output_sha256")
            ):
                guard = {"eligible": False, "reasons": ["PROVENANCE_MISMATCH"]}
            if estimate is not None and guard and not guard["eligible"]:
                estimate = None  # Preserve the original sealed estimate; do not forge a new one.
            guards.append({"endpoint": side, "observation_ref": ref, "eligibility": guard})
            endpoints.append(
                {
                    "observation_ref": ref,
                    "camera_id": interval[side + "_camera_id"],
                    "timestamp_s": interval[side + "_s"],
                    "evidence_state": "PROJECTED_OBSERVATION",
                    "ground_estimate": estimate,
                    "substitution": None,
                }
            )
        mode = request.negative_evidence_mode
        refs = ([] if mode == "NONE" else self.baseline_refs) + (
            request.negative_evidence_refs if mode == "BASELINE_AND_FEEDBACK" else []
        )
        evidence = [
            copy.deepcopy(self.negative_evidence[r]) for r in refs if r in self.negative_evidence
        ]
        evidence_fresh = (
            self.evidence_validator(evidence) if evidence and self.evidence_validator else True
        )
        problem = None
        if (
            request.observation_ref != interval["start_observation_ref"]
            or not request.start <= interval["start_s"] < interval["end_s"] <= request.end
            or set(request.camera_ids) != {interval["start_camera_id"], interval["end_camera_id"]}
            or len(request.camera_ids) != 2
        ):
            problem = "D18_ENDPOINT_SCOPE_MISMATCH"
        elif any(
            interval["start_s"] < r["timestamp"] < interval["end_s"] for r in observations.values()
        ):
            problem = "D18_INTERVAL_CONTAINS_OBSERVATION"
        elif request.negative_evidence_refs and mode != "BASELINE_AND_FEEDBACK":
            problem = "NEGATIVE_EVIDENCE_MODE_CONFLICT"
        elif not evidence_fresh or len(evidence) != len(refs):
            problem = "NEGATIVE_EVIDENCE_UNAVAILABLE"
        engine_request = {
            "schema_version": "office-demo.blind-hypothesis-request.v1",
            "session_ref": request.session_ref,
            "scene_id": self.scene.scene_id,
            "candidate_ref": None,
            "start": endpoints[0],
            "end": endpoints[1],
            "top_k": request.top_k,
            "negative_evidence": evidence,
            "previous_response_sha256": request.previous_response_sha256,
        }
        deadline = time.monotonic() + self.binding["cooperative_deadline_s"]
        response = (
            self._unavailable(interval, problem)
            if problem
            else generate_blind_hypotheses(
                engine_request,
                config=self.config,
                config_sha256=self.binding["config_sha256"],
                floor_map=self.floor_map,
                source_binding={
                    "run_ref": self.scene.run_id,
                    "clock_id": self.binding["clock_id"],
                    "source_sha256": self.scene.source_hash,
                    "safe_inputs_sha256": self.binding["safe_inputs_sha256"],
                },
                previous_response=previous,
                visibility_index_ref=self.visibility_index_ref,
                should_stop=lambda: time.monotonic() >= deadline,
            )
        )
        # Integration metadata is sealed after K1 and before review/cache/K5 consumers.
        # K1/K5 source modules and their request fingerprint remain unchanged.
        response["negative_evidence_mode"] = mode
        response["output_sha256"] = content_hash(
            {k: v for k, v in response.items() if k != "output_sha256"}
        )
        original_rows = [
            copy.deepcopy(observations[e["observation_ref"]])
            for e in endpoints
            if e["observation_ref"] in observations
        ]
        review = {
            "schema_version": "workbench.blind-hypothesis-review-evidence.v1",
            "hypothesis_response_sha256": response["output_sha256"],
            "endpoints": endpoints,
            "endpoint_usage_checks": guards,
            "run_parameters": copy.deepcopy(
                (endpoints[0]["ground_estimate"] or {}).get("provenance", {}).get("run_parameters")
            ),
            "endpoint_substitution": "NOT_PERFORMED",
            "negative_evidence_status": self.negative_evidence_status,
            "negative_evidence_mode": mode,
            "restricted_policy_input": self.restricted_policy_input,
            "restricted_policy_engine_status": "AWAITING_CLAUDE_K1_NATIVE_SUPPORT"
            if self.restricted_policy_input
            else "NOT_REGISTERED",
            "source_observations": original_rows,
            "blind_frame_time_range_s": interval["interior_time_range_s"],
            "missing_positions_filled": False,
            "negative_evidence_refs": refs,
            "applied_frame_keys": self.applied_frame_keys(response),
            "frame_deduplication_status": "AWAITING_REVIEWED_K5_APPLIED_FRAME_KEYS_SYNC",
            "physical_authority": "UNKNOWN",
            "identity_verdict": "UNCONFIRMED",
            "gt_read": False,
        }
        review["output_sha256"] = content_hash(review)
        # Convergence consumes the returned sealed objects, without modifying K1/K5 payloads.
        convergence = pruning_convergence_summary(([previous] if previous else []) + [response])
        return {
            "blind_hypotheses": response,
            "review_evidence": review,
            "pruning_convergence": convergence,
        }

    def applied_frame_keys(self, response):
        """Collect server-held applied frames for the upcoming K5 interface sync."""
        keys = set()
        for ref in response.get("negative_evidence_applied", []):
            entry = self.negative_evidence.get(ref)
            if entry is None:
                continue
            producer = entry["detection_producer"]
            for frame in entry["frame_refs"]:
                keys.add(
                    (
                        entry["camera_id"],
                        frame["frame_ref"],
                        entry["visibility_ref"],
                        producer["producer"],
                        producer.get("version"),
                    )
                )
        return [list(key) for key in sorted(keys)]

    def _unavailable(self, interval, problem):
        """Integration rejection before K1: no geometry search or reused result."""
        return {
            "schema_version": "workbench.blind-hypothesis.v1",
            "status": "UNKNOWN",
            "reason": problem,
            "interval": {
                "start_s": interval["start_s"],
                "end_s": interval["end_s"],
                "duration_s": interval["end_s"] - interval["start_s"],
                "start_observation_ref": interval["start_observation_ref"],
                "end_observation_ref": interval["end_observation_ref"],
            },
            "endpoint_substitutions": [],
            "configuration": {},
            "hypotheses": [],
            "pruned_hypotheses": [],
            "reachable_regions": [],
            "rejected_counts": {"speed": 0, "walkable": 0, "unseen": 0, "diversity": 0},
            "negative_evidence_applied": [],
            "pruning_log": [],
            "limits": {"hit": []},
            "trace": [{"step": "FAIL_CLOSED", "reason": problem, "stage": "INTEGRATION_PREFLIGHT"}],
            "evidence_state": "INFERRED_HYPOTHESIS",
            "ranking_basis": "NOT_COMPUTED",
            "physical_authority": "UNKNOWN",
            "identity_verdict": "UNCONFIRMED",
            "agent_used": False,
            "reconstruction_rng": "NOT_USED",
            "provenance": {
                "scene_id": self.scene.scene_id,
                "run_ref": self.scene.run_id,
                "clock_id": self.binding["clock_id"],
                "source_sha256": self.scene.source_hash,
                "safe_inputs_sha256": self.binding["safe_inputs_sha256"],
                "producer": "blind-hypothesis-integration-preflight",
                "gt_read": False,
            },
        }
