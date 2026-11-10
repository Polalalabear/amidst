"""Blind-interval hypothesis module (Office demo task K1).

Pure functions only; Codex wires them into the backend (C4b). See
``docs/contracts/OFFICE_BLIND_HYPOTHESIS_V1.md`` (K0 draft, PR #10).

K5 adds the pruning re-run (``pruning``), the retrieval-to-negative-evidence
conversion (``retrieval_evidence``) and the convergence summary (``convergence``).
The restricted-policy layer of D15 (``restricted``) adds labels only.
"""

from amidst.blind_hypothesis.convergence import pruning_convergence_summary
from amidst.blind_hypothesis.engine import (
    CONFIG_SCHEMA,
    REQUEST_SCHEMA,
    RESPONSE_SCHEMA,
    HypothesisConfig,
    HypothesisRequestError,
    canonical_sha256,
    generate_blind_hypotheses,
    parse_config,
    verify_output_sha256,
)
from amidst.blind_hypothesis.floor_map import (
    ANNOTATION_MAP_KIND,
    FloorMap,
    FloorMapDescriptor,
    FloorMapError,
    PolygonFloorMap,
    floor_map_from_scene_geometry,
    polygon_floor_map,
)
from amidst.blind_hypothesis.restricted import (
    RESTRICTED_INVALID_REASON,
    RESTRICTED_TIER,
    RestrictedLayer,
    RestrictedLayerError,
    parse_restricted_layer,
)
from amidst.blind_hypothesis.retrieval_evidence import (
    applied_frame_keys_from_request,
    negative_evidence_from_retrieval,
)

__all__ = [
    "ANNOTATION_MAP_KIND",
    "CONFIG_SCHEMA",
    "REQUEST_SCHEMA",
    "RESPONSE_SCHEMA",
    "RESTRICTED_INVALID_REASON",
    "RESTRICTED_TIER",
    "FloorMap",
    "FloorMapDescriptor",
    "FloorMapError",
    "HypothesisConfig",
    "HypothesisRequestError",
    "PolygonFloorMap",
    "RestrictedLayer",
    "RestrictedLayerError",
    "applied_frame_keys_from_request",
    "canonical_sha256",
    "floor_map_from_scene_geometry",
    "generate_blind_hypotheses",
    "negative_evidence_from_retrieval",
    "parse_config",
    "parse_restricted_layer",
    "polygon_floor_map",
    "pruning_convergence_summary",
    "verify_output_sha256",
]
