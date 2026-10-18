"""S2 cross-camera candidate screen (Office demo task K8c, design D23).

One FRONT endpoint and N candidate REAR appearances: run K1 once per pair and map
each response to *reachable / excluded / undetermined* under the configured speed
range (D2/D12). Pure and deterministic: no file, network, clock or RNG access; K1
is called exactly as shipped and its responses are kept by hash for inspection.

The verdict is an inference about the configured speed range and the supplied map,
not an observation and not a probability. It never ranks candidates and never
names a "most likely" one. Identity stays ``UNCONFIRMED`` and physical navigation
authority stays ``UNKNOWN``. See ``docs/agents/K8_SYNTHETIC_CAPABILITY_DEMO.md``
§4.1 (verdict mapping) and §4.2 (interface).
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from typing import Any

from amidst.blind_hypothesis.engine import (
    REQUEST_SCHEMA,
    HypothesisRequestError,
    canonical_sha256,
    generate_blind_hypotheses,
)
from amidst.blind_hypothesis.floor_map import FloorMap

SCREEN_SCHEMA = "workbench.candidate-screen.v1"
VERDICT_BASIS = "CONFIGURED_SPEED_RANGE_NOT_PROBABILITY"

REACHABLE = "REACHABLE"
UNREACHABLE_UNDER_CONFIG = "UNREACHABLE_UNDER_CONFIG"
UNREACHABLE_UNDER_CONFIG_AND_EVIDENCE = "UNREACHABLE_UNDER_CONFIG_AND_EVIDENCE"
UNDETERMINED = "UNDETERMINED"
VERDICTS = (
    REACHABLE,
    UNREACHABLE_UNDER_CONFIG,
    UNREACHABLE_UNDER_CONFIG_AND_EVIDENCE,
    UNDETERMINED,
)

# Why a verdict was given, beyond the K1 status/reason (which are copied verbatim).
REASON_K1_READY = "K1_READY_HYPOTHESIS_PASSED_CHECKS"
REASON_STRAIGHT_LINE = "STRAIGHT_LINE_EXCEEDS_SPEED_BOUND"
REASON_REACH_EMPTY_BY_SPEED = "REACHABLE_SET_EMPTY_BY_SPEED"
REASON_REACH_EMPTY_BY_EVIDENCE = "REACHABLE_SET_EMPTY_WITH_NEGATIVE_EVIDENCE"
REASON_UNREACHABLE_UNSPECIFIED = "ENDPOINTS_UNREACHABLE_DETAIL_ABSENT"
REASON_SAMPLED_POOL_NOT_PROOF = "SAMPLED_POOL_NOT_EXHAUSTIVE"
REASON_NOT_A_REACHABILITY_RESULT = "K1_UNKNOWN_NOT_A_REACHABILITY_RESULT"
# Not covered by §4.1 (UNKNOWN in the spec): K1 answered READY without a hypothesis,
# or with a status this screen does not know. Fail closed to UNDETERMINED.
REASON_READY_WITHOUT_HYPOTHESES = "K1_READY_WITHOUT_HYPOTHESES"
REASON_STATUS_UNRECOGNISED = "K1_STATUS_UNRECOGNISED"

_BASE_REQUEST_KEYS = frozenset({"session_ref", "scene_id", "top_k", "negative_evidence"})
_CANDIDATE_KEYS = frozenset({"candidate_ref", "end"})


def _fail_closed_detail(response: Mapping[str, Any]) -> Mapping[str, Any]:
    for step in response.get("trace") or ():
        if isinstance(step, Mapping) and step.get("step") == "FAIL_CLOSED":
            return step
    return {}


def _verdict(response: Mapping[str, Any]) -> tuple[str, str, Mapping[str, Any]]:
    """Map one K1 response to (verdict, reason_code, fail-closed trace detail)."""

    status, reason = response.get("status"), response.get("reason")
    if status == "READY":
        if response.get("hypotheses"):
            return REACHABLE, REASON_K1_READY, {}
        return UNDETERMINED, REASON_READY_WITHOUT_HYPOTHESES, {}
    if status != "UNKNOWN":
        return UNDETERMINED, REASON_STATUS_UNRECOGNISED, {}
    detail = _fail_closed_detail(response)
    if reason == "ENDPOINTS_UNREACHABLE":
        if detail.get("straight_line_m") is not None:
            return UNREACHABLE_UNDER_CONFIG, REASON_STRAIGHT_LINE, detail
        if detail.get("empty_at_s"):
            return UNREACHABLE_UNDER_CONFIG, REASON_REACH_EMPTY_BY_SPEED, detail
        return UNREACHABLE_UNDER_CONFIG, REASON_UNREACHABLE_UNSPECIFIED, detail
    if reason == "REACHABLE_SET_EMPTY":
        return UNREACHABLE_UNDER_CONFIG_AND_EVIDENCE, REASON_REACH_EMPTY_BY_EVIDENCE, detail
    if reason == "NO_HYPOTHESIS_PASSED_CHECKS":
        # The candidate pool is a capped sample, not an enumeration of all routes.
        return UNDETERMINED, REASON_SAMPLED_POOL_NOT_PROOF, detail
    return UNDETERMINED, REASON_NOT_A_REACHABILITY_RESULT, detail


def _check_inputs(
    start: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    base_request: Mapping[str, Any],
) -> list[str]:
    if not isinstance(base_request, Mapping) or set(base_request) != _BASE_REQUEST_KEYS:
        raise HypothesisRequestError(
            f"base_request fields must be exactly {sorted(_BASE_REQUEST_KEYS)}"
        )
    negative_evidence = base_request["negative_evidence"]
    if isinstance(negative_evidence, (str, bytes, Mapping)) or not isinstance(
        negative_evidence, Sequence
    ):
        # A malformed container is a request error (like the other structural checks),
        # not evidence trouble: None would otherwise raise a bare TypeError and a
        # string would be split into one-character "intervals".
        raise HypothesisRequestError("base_request.negative_evidence must be a list")
    if not isinstance(start, Mapping):
        raise HypothesisRequestError("start must be a K1 endpoint mapping")
    if isinstance(candidates, (str, bytes)) or not isinstance(candidates, Sequence):
        raise HypothesisRequestError("candidates must be a sequence")
    refs: list[str] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, Mapping) or set(candidate) != _CANDIDATE_KEYS:
            raise HypothesisRequestError(
                f"candidates[{index}] fields must be exactly {sorted(_CANDIDATE_KEYS)}"
            )
        ref = candidate["candidate_ref"]
        if not isinstance(ref, str) or not ref:
            raise HypothesisRequestError(f"candidates[{index}].candidate_ref must be a string")
        if not isinstance(candidate["end"], Mapping):
            raise HypothesisRequestError(f"candidates[{index}].end must be a K1 endpoint mapping")
        refs.append(ref)
    if len(set(refs)) != len(refs):
        raise HypothesisRequestError("candidate_ref values must be unique")
    return refs


def screen_cross_camera_candidates(
    start: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    base_request: Mapping[str, Any],
    config: Mapping[str, Any],
    config_sha256: str,
    floor_map: FloorMap | None,
    source_binding: Mapping[str, Any],
    visibility_index_ref: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run K1 for each (start, candidate end) pair and tabulate the verdicts.

    ``start`` and each ``candidate["end"]`` are K1 request endpoints; ``base_request``
    carries exactly ``session_ref``, ``scene_id``, ``top_k`` and ``negative_evidence``.
    Any other field (for example Ground Truth or a trajectory) raises
    :class:`HypothesisRequestError`, as does a malformed endpoint. Results keep the
    input order; nothing is sorted by plausibility. Evidence problems never raise:
    they come back as ``UNDETERMINED`` with K1's own reason.
    """

    refs = _check_inputs(start, candidates, base_request)
    results: list[dict[str, Any]] = []
    for ref, candidate in zip(refs, candidates, strict=True):
        request = {
            "schema_version": REQUEST_SCHEMA,
            "session_ref": base_request["session_ref"],
            "scene_id": base_request["scene_id"],
            "candidate_ref": ref,
            "start": copy.deepcopy(dict(start)),
            "end": copy.deepcopy(dict(candidate["end"])),
            "top_k": base_request["top_k"],
            "negative_evidence": copy.deepcopy(list(base_request["negative_evidence"])),
            "previous_response_sha256": None,
        }
        try:
            response = generate_blind_hypotheses(
                request,
                config=config,
                config_sha256=config_sha256,
                floor_map=floor_map,
                source_binding=source_binding,
                visibility_index_ref=visibility_index_ref,
            )
        except HypothesisRequestError as error:
            raise HypothesisRequestError(f"candidate {ref}: {error}") from error
        verdict, reason_code, detail = _verdict(response)
        results.append(
            {
                "candidate_ref": ref,
                "verdict": verdict,
                "reason_code": reason_code,
                "k1_status": response["status"],
                "k1_reason": response["reason"],
                "k1_response_sha256": response["output_sha256"],
                "k1_hypothesis_count": len(response.get("hypotheses") or ()),
                "straight_line_m": detail.get("straight_line_m"),
                "empty_at_s": list(detail.get("empty_at_s") or ()) or None,
                "identity_verdict": "UNCONFIRMED",
            }
        )
    output: dict[str, Any] = {
        "schema_version": SCREEN_SCHEMA,
        "results": results,
        "verdict_basis": VERDICT_BASIS,
        "evidence_state": "INFERRED_SCREENING",
        "physical_authority": "UNKNOWN",
        "identity_verdict": "UNCONFIRMED",
        "gt_read": False,
        "config_sha256": config_sha256,
        "output_sha256": None,
    }
    output["output_sha256"] = canonical_sha256(
        {key: value for key, value in output.items() if key != "output_sha256"}
    )
    return output
