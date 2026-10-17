"""Pruning re-run by new negative evidence (task K5, blind-hypothesis contract §6).

Pure helpers used by :func:`amidst.blind_hypothesis.engine.generate_blind_hypotheses`
when the request carries ``previous_response_sha256``. Pruning is a deterministic
re-run, never an in-place edit of the previous response:

1. The caller sends the same request, the evidence list extended at its end, the
   previous response's ``output_sha256`` and (because the module looks nothing up)
   the previous response object itself. :func:`check_previous` recomputes that
   object's canonical hash, compares it with the request, and requires that the
   old evidence list (refs and entry hashes) is a prefix of the new one.
2. The engine recomputes regions and paths with all evidence.
3. :func:`apply_pruning` lists previously ACTIVE paths that now conflict with the
   *new* evidence in ``pruned_hypotheses`` (status ``PRUNED``) and appends one
   ``pruning_log`` entry per new evidence entry.

Nothing here reads files, clocks or GT; the previous response is data, and its
paths are re-checked against the evidence with the same ``unseen`` rule the engine
applies to its own paths.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from amidst.blind_hypothesis.engine import (
    RESPONSE_SCHEMA,
    _Evidence,
    _Unknown,
    canonical_sha256,
    verify_output_sha256,
)
from amidst.blind_hypothesis.restricted import RestrictedLayer

NOT_APPEND_ONLY = "NEGATIVE_EVIDENCE_NOT_APPEND_ONLY"
FINGERPRINT_STEP = "NEGATIVE_EVIDENCE_FINGERPRINT"
REQUEST_STEP = "REQUEST_FINGERPRINT"
# Fields that may differ between a run and its re-run; every other request field
# (endpoints, scene, session, candidate) must repeat unchanged.
_RERUN_VARIABLE_FIELDS = frozenset({"negative_evidence", "previous_response_sha256", "top_k"})
PRUNING_REF_PREFIX = "pruning:"


def evidence_fingerprint_step(entries: Sequence[Any]) -> dict[str, Any]:
    """Trace step recording ``{ref, sha256}`` per applied entry, in application order.

    The response lists only evidence refs (contract §5); the entry hashes in the
    trace let a re-run detect that an old entry was edited while keeping its ref.
    """

    return {
        "step": FINGERPRINT_STEP,
        "entries": [
            {"negative_evidence_ref": e.get("negative_evidence_ref"), "sha256": e.get("sha256")}
            for e in entries
            if isinstance(e, Mapping)
        ],
    }


def request_fingerprint_step(
    request: Mapping[str, Any],
    restricted: RestrictedLayer | None = None,
    restricted_regions_sha256: str | None = None,
) -> dict[str, Any]:
    """Trace step with the hash of the request minus the fields a re-run may change.

    The restricted-policy layer (D15) is part of the request's meaning although it is
    not a request field: with a layer, the hash covers the request, the layer's
    ``restricted_ref`` and the hash of its regions, so a re-run under another layer is
    not "the same request". Without a layer the hash is that of the request alone.
    """

    fixed: Any = {k: v for k, v in request.items() if k not in _RERUN_VARIABLE_FIELDS}
    if restricted is not None:
        fixed = {
            "request": fixed,
            "restricted_ref": dict(restricted.ref),
            "restricted_regions_sha256": restricted_regions_sha256,
        }
    try:
        digest: str | None = canonical_sha256(fixed)
    except (TypeError, ValueError):
        digest = None  # not canonical JSON (e.g. NaN); a re-run then never matches
    return {"step": REQUEST_STEP, "request_sha256": digest}


def check_previous(
    request: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    response: Mapping[str, Any],
    restricted: RestrictedLayer | None = None,
    restricted_regions_sha256: str | None = None,
) -> None:
    """Raise ``_Unknown`` unless ``previous`` is a verified, append-only predecessor.

    ``response`` is the not yet computed new response (its echo of the interval,
    configuration and provenance is already filled and must equal the previous one:
    the caller re-sends the *same* request).
    """

    def fail(problem: str, reason: str = NOT_APPEND_ONLY, **detail: Any) -> _Unknown:
        return _Unknown(reason, problem=problem, **detail)

    if not isinstance(previous, Mapping):
        raise fail("PREVIOUS_RESPONSE_MISSING")
    if previous.get("schema_version") != RESPONSE_SCHEMA:
        raise fail("PREVIOUS_RESPONSE_SCHEMA")
    claimed = request["previous_response_sha256"]
    if (
        not isinstance(claimed, str)
        or previous.get("output_sha256") != claimed
        or not verify_output_sha256(previous)
    ):
        raise fail("PREVIOUS_RESPONSE_HASH_MISMATCH")
    if previous.get("status") != "READY":
        raise fail("PREVIOUS_RESPONSE_NOT_READY", previous_reason=previous.get("reason"))

    new_entries = [e for e in request["negative_evidence"] if isinstance(e, Mapping)]
    old_refs = previous.get("negative_evidence_applied")
    fingerprint = next(
        (s for s in previous.get("trace", []) if s.get("step") == FINGERPRINT_STEP), None
    )
    if not isinstance(old_refs, list) or fingerprint is None:
        raise fail("PREVIOUS_EVIDENCE_LIST_MISSING")
    old = [(e["negative_evidence_ref"], e["sha256"]) for e in fingerprint["entries"]]
    if [ref for ref, _ in old] != old_refs:
        raise fail("PREVIOUS_EVIDENCE_LIST_INCONSISTENT")
    new = [(e.get("negative_evidence_ref"), e.get("sha256")) for e in new_entries]
    if new[: len(old)] != old:
        raise fail("EVIDENCE_NOT_A_PREFIX_EXTENSION", previous_count=len(old))

    request_step = next(
        (s for s in previous.get("trace", []) if s.get("step") == REQUEST_STEP), None
    )
    if request_step is None:
        raise fail("PREVIOUS_REQUEST_FINGERPRINT_MISSING")
    current = request_fingerprint_step(request, restricted, restricted_regions_sha256)[
        "request_sha256"
    ]
    if current is None or request_step.get("request_sha256") != current:
        raise fail("REQUEST_CHANGED")

    for key in ("interval", "configuration", "provenance"):
        if previous.get(key) != response[key]:
            raise _Unknown("PROVENANCE_MISMATCH", problem=f"PREVIOUS_RESPONSE_{key.upper()}")


def apply_pruning(
    previous: Mapping[str, Any],
    response: dict[str, Any],
    raw_entries: Sequence[Mapping[str, Any]],
    evidence: Sequence[_Evidence],
    times: Sequence[float],
    areas: Sequence[tuple[float, float]],
    first_new: int,
    unseen_check: Callable[..., dict[str, Any]],
) -> None:
    """Fill ``pruned_hypotheses``, ``pruning_log`` and a trace step of the new response.

    ``areas[n]`` is the ``(before, after)`` mean region area of new entry
    ``first_new + n``. A previously ACTIVE path is PRUNED when it now fails
    ``unseen`` against a new entry and is not itself re-selected; it is attributed
    to the first (in application order) new entry it conflicts with.
    """

    if previous.get("endpoint_substitutions") != response["endpoint_substitutions"]:
        raise _Unknown("PROVENANCE_MISMATCH", problem="PREVIOUS_RESPONSE_ENDPOINT_SUBSTITUTIONS")
    previous_hash = previous["output_sha256"]
    refs = {
        j: PRUNING_REF_PREFIX
        + canonical_sha256(
            {
                "previous_response_sha256": previous_hash,
                "order": j + 1,
                "negative_evidence_ref": evidence[j].ref,
                "negative_evidence_sha256": raw_entries[j].get("sha256"),
            }
        )[:24]
        for j in range(first_new, len(evidence))
    }

    selected_refs = {h["hypothesis_ref"] for h in response["hypotheses"]}
    pruned: list[dict[str, Any]] = []
    pruned_by_entry: dict[int, list[str]] = {j: [] for j in refs}
    previous_active = [h for h in previous["hypotheses"] if h.get("status") == "ACTIVE"]
    for old in previous_active:
        samples = old["samples"]
        if [s["timestamp_s"] for s in samples] != list(times):
            raise _Unknown("PROVENANCE_MISMATCH", problem="PREVIOUS_HYPOTHESIS_SAMPLE_TIMES")
        check = unseen_check(evidence, [s["position_m"] for s in samples], times)
        if check["result"] != "FAIL" or old["hypothesis_ref"] in selected_refs:
            continue
        conflicting = {c["negative_evidence_ref"] for c in check["conflicts"]}
        owner = next((j for j in refs if evidence[j].ref in conflicting), None)
        if owner is None:
            # The old path was ACTIVE yet conflicts with old evidence only: the previous
            # response or its evidence is not what this re-run extends.
            raise _Unknown(
                NOT_APPEND_ONLY,
                problem="PREVIOUS_HYPOTHESIS_CONFLICTS_WITH_PRIOR_EVIDENCE",
                hypothesis_ref=old["hypothesis_ref"],
            )
        record = copy.deepcopy(dict(old))
        record["status"] = "PRUNED"
        record["pruned_by"] = refs[owner]
        record["rank"] = None
        record["checks"]["unseen"] = check
        pruned.append(record)
        pruned_by_entry[owner].append(old["hypothesis_ref"])

    log = [copy.deepcopy(dict(item)) for item in previous["pruning_log"]]
    for n, j in enumerate(refs):
        indices = evidence[j].step_indices
        before, after = areas[n]
        log.append(
            {
                "pruning_ref": refs[j],
                "order": j + 1,
                "negative_evidence_ref": evidence[j].ref,
                "camera_id": evidence[j].camera_id,
                "time_window_s": [times[min(indices)], times[max(indices)]] if indices else None,
                "hypotheses_pruned": sorted(pruned_by_entry[j]),
                "region_area_before_m2": before,
                "region_area_after_m2": after,
                "previous_response_sha256": previous_hash,
            }
        )
    response["pruned_hypotheses"] = pruned
    response["pruning_log"] = log
    response["trace"].append(
        {
            "step": "PRUNING_RERUN",
            "previous_response_sha256": previous_hash,
            "new_negative_evidence": [evidence[j].ref for j in refs],
            "previous_active": len(previous_active),
            "hypotheses_pruned": len(pruned),
            "hypotheses_surviving": sum(
                1 for h in previous_active if h["hypothesis_ref"] in selected_refs
            ),
        }
    )
