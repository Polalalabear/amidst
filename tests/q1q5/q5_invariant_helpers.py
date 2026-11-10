"""Independent offline journal checks, not a runtime policy or contract replacement.

Structural/trace checks are finite evidence. Missing context is INCOMPLETE, not
PASS. AS_IS reports the collapsed SWITCH as a known gap; CONTRACT rejects it.
No assets, GT, provider, product imports or mutations of supplied documents.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

STATES = {"PLAYING", "TEMP_LOST", "SEARCHING", "RETURNED_TO_ORIGIN", "ENDED"}
ACTIVE = STATES - {"ENDED"}
# Observed trace arcs, not approval of their agreement with the wire contract.
AS_IS_ARCS = {
    (None, "PLAYING"),
    ("PLAYING", "PLAYING"),
    ("PLAYING", "TEMP_LOST"),
    ("TEMP_LOST", "PLAYING"),
    ("TEMP_LOST", "SEARCHING"),
    ("SEARCHING", "SEARCHING"),
    ("SEARCHING", "PLAYING"),
    ("SEARCHING", "RETURNED_TO_ORIGIN"),
    ("RETURNED_TO_ORIGIN", "PLAYING"),
    ("RETURNED_TO_ORIGIN", "SEARCHING"),
    ("PLAYING", "SEARCHING"),
} | {(s, "ENDED") for s in ACTIVE}


def digest(value, exclude=()):
    pre = {k: v for k, v in value.items() if k not in exclude} if exclude else value
    return hashlib.sha256(
        json.dumps(
            pre,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()


def wire_hash(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True)
class Finding:
    code: str
    path: str


@dataclass
class JournalReport:
    violations: list[Finding] = field(default_factory=list)
    unchecked: list[Finding] = field(default_factory=list)
    known_gaps: list[Finding] = field(default_factory=list)

    @property
    def status(self):
        if self.violations:
            return "FAIL"
        if self.unchecked:
            return "INCOMPLETE"
        return "KNOWN_GAPS" if self.known_gaps else "PASS"


def check_journal(bundle, *, profile="AS_IS") -> JournalReport:
    """Check supplied evidence. trusted_scope must come from external trusted pins.

    index_records is the pinned index context, not GT. This verifier does not
    authenticate metadata approval, redo image inference or prove GT isolation.
    """
    if profile not in {"AS_IS", "CONTRACT"}:
        raise ValueError("Explicit AS_IS or CONTRACT profile required")
    report = JournalReport()

    def require(ok, code, path):
        if not ok:
            report.violations.append(Finding(code, path))

    def integer(value):
        return type(value) is int and value >= 0

    def inside(value, interval):
        return integer(value) and interval[0] <= value < interval[1]

    try:
        response = bundle["response"]
        require(
            response["output_sha256"] == digest(response, ("output_sha256", "stats")),
            "RESPONSE_HASH",
            "response",
        )
        require(
            response["decisions_sha256"] == wire_hash(bundle["decisions"]),
            "DECISIONS_FILE_HASH",
            "decisions",
        )
        require(response["links_sha256"] == wire_hash(bundle["links"]), "LINKS_FILE_HASH", "links")
        decisions = [json.loads(line) for line in bundle["decisions"].splitlines()]
        links = [json.loads(line) for line in bundle["links"].splitlines()]
        require(
            response["identity_verdict"] == "UNCONFIRMED"
            and response["provenance"]["gt_read"] is False,
            "EVIDENCE_BOUNDARY",
            "response",
        )
        scope = response["resolved_scope"]
        if "trusted_scope" not in bundle:
            report.unchecked.append(Finding("TRUSTED_SCOPE_MISSING", "resolved_scope"))
        else:
            require(scope == bundle["trusted_scope"], "SOURCE_SCOPE", "resolved_scope")
        windows = [r["range_us"] for r in scope["resolved_source_ranges_us"] or []]
        sid = response["session_id"]
        previous_state = None
        source_time = -1
        counters = {"searching_index": 0, "session_agent_rounds_used": 0}
        fallback = False
        by_id = {}
        episode = (-1, 0)
        for i, row in enumerate(decisions):
            path = f"decisions[{i}]"
            require(
                row["content_sha256"] == digest(row, ("content_sha256", "stats")),
                "DECISION_HASH",
                path,
            )
            require(
                row["session_id"] == sid
                and row["step_index"] == i
                and row["decision_id"] not in by_id,
                "DECISION_ID_ORDER",
                path,
            )
            by_id[row["decision_id"]] = row
            before, after = row["state_before"], row["state_after"]
            require(
                (before, after) in AS_IS_ARCS and before == previous_state, "STATE_TRANSITION", path
            )
            previous_state = after
            require(
                integer(row["source_time_us"]) and row["source_time_us"] >= source_time,
                "SOURCE_TIME",
                path,
            )
            source_time = row["source_time_us"]
            require(
                any(
                    a <= source_time <= b if after == "ENDED" else a <= source_time < b
                    for a, b in windows
                ),
                "DECISION_QUERY_BOUNDS",
                path,
            )
            decision_time = row["decision_time_us"]
            require(
                decision_time is None or integer(decision_time) and decision_time <= source_time,
                "DECISION_TIME",
                path,
            )
            for name in counters:
                require(integer(row[name]) and row[name] >= counters[name], "COUNTER_RESET", path)
                counters[name] = row[name]
            require(
                integer(row["rounds_used"])
                and (row["searching_index"] != episode[0] or row["rounds_used"] >= episode[1]),
                "EPISODE_COUNTER_RESET",
                path,
            )
            episode = (row["searching_index"], row["rounds_used"])
            require(type(row["accepted"]) is bool, "ACCEPTED_TYPE", path)
            action = row["executed_action"]
            require(
                action in {None, "SWITCH", "NEXT_CANDIDATE", "RETURN_TO_ORIGIN"},
                "ACTION_VOCABULARY",
                path,
            )
            require(row["accepted"] or action is None, "REJECTED_ACTION_EXECUTED", path)
            require(not fallback or not row["llm_calls"], "AGENT_AFTER_FALLBACK", path)
            fallback |= row["decided_by"] == "RULE_FALLBACK"
            considered = row["candidates_considered"]
            ranks = [c["rank"] for c in considered]
            require(
                all(type(r) is int and r > 0 for r in ranks) and ranks == sorted(set(ranks)),
                "CANDIDATE_ORDER",
                path,
            )
            if action == "SWITCH":
                require(
                    before == "SEARCHING" and after == "PLAYING" and row["accepted"],
                    "SWITCH_STATE",
                    path,
                )
                gap = Finding("SWITCHING_NOT_RECORDED", path)
                (report.known_gaps if profile == "AS_IS" else report.violations).append(gap)
            if action == "NEXT_CANDIDATE" and row["decided_by"] == "AGENT":
                submitted = row["submitted"]
                require(
                    submitted["candidate_ref"] == row["executed_candidate_ref"]
                    and bool(submitted["cited_observation_ids"]),
                    "NEXT_CITATION",
                    path,
                )
                if "evidence" not in bundle:
                    report.unchecked.append(Finding("NEXT_CONTEXT_MISSING", path))
                else:
                    evidence = next(
                        (
                            e
                            for e in bundle["evidence"]
                            if e["candidate_ref"] == row["executed_candidate_ref"]
                            and e["decision_time_us"] == row["decision_time_us"]
                        ),
                        None,
                    )
                    require(evidence is not None, "NEXT_EVIDENCE_NOT_FETCHED", path)
                    if evidence is not None:
                        allowed = {o["observation_id"] for o in evidence["best_observations"]}
                        if evidence["entry_observation_id"] is not None:
                            allowed.add(evidence["entry_observation_id"])
                        require(
                            set(submitted["cited_observation_ids"]) <= allowed,
                            "NEXT_FOREIGN_CITATION",
                            path,
                        )
                require(
                    submitted["decision_id"] == row["decision_id"]
                    and submitted["candidate_snapshot_sha256"] == row["candidate_snapshot_sha256"],
                    "NEXT_DECISION_BINDING",
                    path,
                )
        if decisions:
            require(decisions[-1]["state_after"] == "ENDED", "MISSING_TERMINAL", "decisions")

        segments = response["timeline"]
        require(not segments or bool(decisions), "MISSING_INITIAL_JOURNAL", "decisions")
        cursor = None
        switch_segments = {}
        for i, segment in enumerate(segments):
            path = f"timeline[{i}]"
            left, right = segment["range_us"]
            require(
                integer(left)
                and integer(right)
                and left < right
                and (cursor is None or left == cursor),
                "TIMELINE_INTERVAL",
                path,
            )
            require(any(a <= left < right <= b for a, b in windows), "QUERY_BOUNDS", path)
            cursor = right
            if segment["kind"] == "GAP":
                require(segment["position"] is None, "GAP_POSITION", path)
            else:
                require(
                    segment["kind"] == "ON_CAMERA" and bool(segment["observation_ids"]),
                    "TIMELINE_KIND",
                    path,
                )
                if segment.get("entered_by") == "SWITCH":
                    key = segment["decision_id"]
                    require(key not in switch_segments, "DUPLICATE_SWITCH_SEGMENT", path)
                    switch_segments[key] = segment
        for row in decisions:
            if row["executed_action"] != "SWITCH":
                continue
            path = row["decision_id"]
            segment = switch_segments.pop(path, None)
            require(segment is not None, "SWITCH_TIMELINE_BINDING", path)
            if segment is None:
                continue
            require(
                segment["observation_ids"][0] == row["entry_observation_id"]
                and segment["range_us"][0] == row["source_time_us"],
                "SWITCH_ENTRY",
                path,
            )
            snapshots = bundle.get("snapshots")
            evidence = bundle.get("evidence")
            if snapshots is None or evidence is None:
                report.unchecked.append(Finding("SWITCH_CONTEXT_MISSING", path))
                continue
            snapshot = next(
                (
                    s
                    for s in snapshots
                    if s["candidate_snapshot_sha256"] == row["candidate_snapshot_sha256"]
                ),
                None,
            )
            require(snapshot is not None, "SNAPSHOT_REF", path)
            if snapshot is None:
                continue
            pre = {
                k: v for k, v in snapshot.items() if k not in {"candidate_snapshot_sha256", "stats"}
            }
            pre = json.loads(json.dumps(pre))
            for candidate in pre["candidates"]:
                candidate.pop("candidate_ref", None)
            require(
                snapshot["candidate_snapshot_sha256"] == digest(pre)
                and snapshot["session_id"] == sid,
                "SNAPSHOT_HASH_SCOPE",
                path,
            )
            candidate = next(
                (
                    c
                    for c in snapshot["candidates"]
                    if c["candidate_ref"] == row["executed_candidate_ref"]
                ),
                None,
            )
            require(candidate is not None, "CANDIDATE_REF", path)
            if candidate is None:
                continue
            e = next(
                (
                    e
                    for e in evidence
                    if e["candidate_ref"] == candidate["candidate_ref"]
                    and e["decision_time_us"] == row["decision_time_us"]
                ),
                None,
            )
            require(e is not None, "EVIDENCE_NOT_FETCHED", path)
            if e is None:
                continue
            require(
                e["evidence_sha256"] == digest(e, ("evidence_sha256", "stats")),
                "EVIDENCE_HASH",
                path,
            )
            require(
                e["target_presence"] == "MATCH_STRONG"
                and e["entry_observation_id"] == row["entry_observation_id"]
                and e["entry_timestamp_us"] == row["source_time_us"]
                and inside(e["entry_timestamp_us"], candidate["window_us"])
                and e["window_us"] == candidate["window_us"]
                and e["camera_id"] == candidate["camera_id"] == segment["camera_id"],
                "SWITCH_GUARD",
                path,
            )
            require(
                any(
                    c["evidence_sha256"] == e["evidence_sha256"]
                    and c["candidate_ref"] == e["candidate_ref"]
                    and c["rank"] == candidate["rank"]
                    for c in row["candidates_considered"]
                ),
                "EVIDENCE_CITATION",
                path,
            )
            if "index_records" not in bundle:
                report.unchecked.append(Finding("INDEX_CONTEXT_MISSING", path))
            else:
                observed = [
                    (r, o)
                    for r in bundle["index_records"]
                    for o in r["detections"] or []
                    if o["observation_id"] == e["entry_observation_id"]
                ]
                require(
                    len(observed) == 1
                    and observed[0][0]["frame_state"] == "INFERRED"
                    and observed[0][0]["camera_id"] == e["camera_id"]
                    and observed[0][0]["timestamp_us"] == e["entry_timestamp_us"],
                    "ENTRY_INDEX_BINDING",
                    path,
                )
        require(not switch_segments, "ORPHAN_SWITCH_SEGMENT", "timeline")
        for i, e in enumerate(bundle.get("evidence", [])):
            path = f"evidence[{i}]"
            require(
                e["evidence_sha256"] == digest(e, ("evidence_sha256", "stats")),
                "EVIDENCE_HASH",
                path,
            )
            counts = e["frames"]
            require(
                e["target_presence"]
                in {
                    "MATCH_STRONG",
                    "MATCH_WEAK",
                    "PERSON_COLOR_UNKNOWN",
                    "PERSON_NO_COLOR_MATCH",
                    "NO_PERSON_DETECTED",
                    "PARTIAL_EVIDENCE",
                    "NOT_EVALUATED",
                },
                "PRESENCE_VOCABULARY",
                path,
            )
            require(
                set(counts) == {"evaluated", "not_sampled", "not_inferred", "missing"}
                and all(integer(v) for v in counts.values()),
                "EVIDENCE_COUNTS",
                path,
            )
            evaluated = counts["evaluated"]
            expected = evaluated + counts["not_inferred"] + counts["missing"]
            complete = expected > 0 and evaluated == expected
            require(
                type(e["coverage_complete"]) is bool and e["coverage_complete"] == complete,
                "EVIDENCE_COVERAGE",
                path,
            )
            require(
                (e["target_presence"] == "NOT_EVALUATED") == (evaluated == 0)
                and (e["target_presence"] != "PARTIAL_EVIDENCE" or 0 < evaluated < expected)
                and (
                    e["target_presence"] not in {"NO_PERSON_DETECTED", "PERSON_NO_COLOR_MATCH"}
                    or complete
                ),
                "NEGATIVE_WITHOUT_COVERAGE",
                path,
            )
        for i, row in enumerate(links):
            linked = row["decision"] == "LINKED"
            require(
                row["decision"]
                in {
                    "LINKED",
                    "NO_CANDIDATE",
                    "AMBIGUOUS_LINK",
                    "FRAME_MISSING",
                    "FRAME_NOT_INFERRED",
                },
                "LINK_DECISION",
                f"links[{i}]",
            )
            require(
                row["session_id"] == sid and row["link_index"] == i,
                "LINK_ORDER_SCOPE",
                f"links[{i}]",
            )
            require(
                integer(row["elapsed_us"]) and integer(row["gap_samples"]),
                "LINK_GRID",
                f"links[{i}]",
            )
            require(
                (row["next_observation_id"] is not None) == linked
                and (row["iou"] is not None) == linked,
                "LINK_ATTACHMENT",
                f"links[{i}]",
            )
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OverflowError):
        report.violations.append(Finding("MALFORMED_JOURNAL", "bundle"))
    return report
