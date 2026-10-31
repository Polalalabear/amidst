"""評分端；與推論隔離。Synthetic numbers only, never adopted wire/approval."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PARAMETERS = {"index_interval_us": 200000, "link_max_gap_us": 600000,
              "research_interval_us": 1000000, "search_window_us": 6000000,
              "session_max_research_rounds": 6}
OPTIONS = {
    "U-D1": "M1", "U-D2": "TEST_ONLY:REPORT_EXCESS_ONLY", "U-D4": "E2",
    "U-D5": "TEST_ONLY:RECOMPUTE_AND_REJECT", "U-D6": "TEST_ONLY:REJECT_EARLY_BLIND",
    "U-D7": "TEST_ONLY:MAIN_STANDARD_AND_CLASS_RATIOS", "U-D8": "TEST_ONLY:NEW_V2_MODULE",
    "U-D9": "TEST_ONLY:CLAMPED_WINDOW_START", "U-D10": "TEST_ONLY:N_MAX_MINUS_TWO",
    "UK-8": "TEST_ONLY:EXPLICIT_SYNTHETIC_TIMESTAMPS_NOT_A_REAL_METHOD_SELECTION"}


def canonical(doc):
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def seal(doc, field):
    doc[field] = sha(canonical({k: v for k, v in doc.items() if k not in {field, "stats"}}))
    return doc


def row(i, source, decision=None, action=None, searching=0, *, state_before="SEARCHING", state_after="SEARCHING"):
    record = dict(schema_version="q-demo.decision-record.v1", session_id="SYNTHETIC_SESSION",
        decision_id=f"SYNTHETIC_D{i}", step_index=i, source_time_us=source,
        decision_time_us=decision, executed_action=action, accepted=True, decided_by="RULE_ONLY",
        executed_candidate_ref="SYNTHETIC_CANDIDATE" if action == "SWITCH" else None,
        entry_observation_id="SYNTHETIC_OBSERVATION" if action == "SWITCH" else None,
        searching_index=searching, state_before=state_before, state_after=state_after)
    return seal(record, "content_sha256")


def build(output=ROOT):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    generated = {}
    def put(name, doc=None, raw=None):
        raw = raw if raw is not None else canonical(doc) + b"\n"
        (output / name).write_bytes(raw); generated[name] = sha(raw)
    parameters = dict(schema_version="q-demo.parameter-set.v1",
        applies_to={"run_ids": ["SYNTHETIC_RUN"], "scene_revision": "SYNTHETIC_ONLY", "detection_index_ids": []},
        parameters=[{"name": name, "value": value, "unit": "count" if name.endswith("rounds") else "us",
                     "status": "APPROVED", "proposed_by": "SYNTHETIC_ONLY", "proposal_ref": "SYNTHETIC_ONLY"}
                    for name, value in PARAMETERS.items()],
        approval={"status": "APPROVED", "approved_by": "SYNTHETIC_CONTROL_ONLY", "approval_ref": "SYNTHETIC_ONLY"})
    seal(parameters, "content_sha256")
    parameters["parameter_set_id"] = "pset:q-demo:" + parameters["content_sha256"][:16]
    put("parameter_set.SYNTHETIC.json", parameters)
    pending = {key: "PENDING_USER" for key in OPTIONS}
    put("decisions.PENDING.SYNTHETIC.json", pending)
    for key, option in OPTIONS.items():
        put(f"decisions.{key}.SYNTHETIC.json", {**pending, key: option})
    metadata = {"fixture_role": "SYNTHETIC_ONLY", "schema_adoption": "NONE",
        "decision_adoption": "NONE", "fixed_not_configurable": {"U-D3": "D93 O1"},
        "test_only_selections": OPTIONS,
        "golden": {"G1_us": 5200000, "phase_returns_us": [600000, 1600000],
            "phase_switch_us": 2600000, "phase_entry_us": 7600000,
            "phase_search_windows_us": [[200000, 6200000], [1600000, 7600000], [2600000, 8600000]],
            "phase_searching_count": 3, "prefix_cutoff_us": 6800000, "padding_end_us": 12000000,
            "searching_window_us": [700000, 3000000], "searching_window_count": 2}}
    put("CASES.SYNTHETIC.json", metadata)
    plan = {"fixture_role": "SYNTHETIC_ONLY", "not_a_production_plan_schema": True,
            "t_X_us": 0, "t_N_us": 6800000, "scenario": "PHASE_CONTROL"}
    put("plan.SYNTHETIC.json", plan)
    binding = {**PARAMETERS, "parameter_set_id": parameters["parameter_set_id"],
               "parameter_set_sha256": parameters["content_sha256"]}
    def script(events):
        return dict(schema_version="q5-evaluation-script.v2", status="PROPOSED", approval_ref=None,
            approval_content_sha256=None, run_id="SYNTHETIC_RUN", clock_id="SYNTHETIC_CLOCK",
            session_query_range_us=[0, 12000000], parameter_binding=binding,
            plan_ref={"path": "plan.SYNTHETIC.json", "sha256": generated["plan.SYNTHETIC.json"]}, events=events)
    phase_event = dict(event_id="SYNTHETIC_LONG_GAP", action="SWITCH", event_class="LONG_GAP",
        plan_anchor_us={"t_X": 0, "t_N_by_camera": {"SYNTHETIC_C": 6800000}},
        decision_window_us=[0, 7800000], entry_windows_us={"SYNTHETIC_C": {"kind": "BLIND", "range_us": [6200000, 7800000]}},
        return_count_max=2)
    put("phase.script.SYNTHETIC.json", script([phase_event]))
    phase_rows = [row(0, 600000, searching=1, state_before="PLAYING"),
        row(1, 600000, 600000, "RETURN_TO_ORIGIN", 1), row(2, 1600000, searching=2, state_before="RETURNING"),
        row(3, 1600000, 1600000, "RETURN_TO_ORIGIN", 2), row(4, 2600000, searching=3, state_before="RETURNING"),
        row(5, 7600000, 2600000, "SWITCH", 3, state_after="SWITCHING"),
        row(6, 12000000, searching=3, state_before="PLAYING", state_after="ENDED")]
    standard_event = dict(event_id="SYNTHETIC_STANDARD", action="SWITCH", event_class="STANDARD",
        plan_anchor_us={"t_X": 1000000, "t_N_by_camera": {"SYNTHETIC_C": 3000000}},
        decision_window_us=[0, 4000000], entry_windows_us={"SYNTHETIC_C": {"kind": "BLIND", "range_us": [2400000, 4000000]}})
    put("standard.script.SYNTHETIC.json", script([standard_event]))
    standard_rows = [row(0, 1600000, searching=1, state_before="PLAYING"),
        row(1, 3000000, 1600000, "SWITCH", 1, state_after="SWITCHING"),
        row(2, 12000000, searching=1, state_before="PLAYING", state_after="ENDED")]
    limit_events = [dict(event_id="SYNTHETIC_PREFIX", action="RETURN_TO_ORIGIN", event_class="STANDARD",
        plan_anchor_us={"t_X": 0, "t_N": 600000}, decision_window_us=[0, 1600000]),
        dict(event_id="SYNTHETIC_SUFFIX", action="RETURN_TO_ORIGIN", event_class="STANDARD",
        plan_anchor_us={"t_X": 8000000, "t_N": 9000000}, decision_window_us=[3000000, 10000000])]
    put("limit.script.SYNTHETIC.json", script(limit_events))
    limit_rows = []
    for index in range(1, 7):
        time = 600000 + (index - 1) * 1000000
        limit_rows.append(row(len(limit_rows), time, searching=index,
                              state_before="PLAYING" if index == 1 else "RETURNING"))
        limit_rows.append(row(len(limit_rows), time, time, "RETURN_TO_ORIGIN", index))
    limit_rows.append(row(len(limit_rows), 6800000, searching=6, state_before="RETURNING", state_after="ENDED"))
    searching_rows = [row(0, 0, searching=0, state_before=None, state_after="PLAYING"),
        row(1, 600000, searching=1, state_before="PLAYING"),
        row(2, 800000, 600000, "RETURN_TO_ORIGIN", 1), row(3, 1600000, searching=2, state_before="RETURNING"),
        row(4, 1700000, 1600000, "RETURN_TO_ORIGIN", 2),
        row(5, 2600000, searching=3, state_before="SEARCHING", state_after="SEARCHING"),
        row(6, 2800000, 2600000, "RETURN_TO_ORIGIN", 3), row(7, 12000000, searching=3, state_after="ENDED")]
    searching_rows[0]["decided_by"] = "USER"; seal(searching_rows[0], "content_sha256")
    searching_rows[5]["decided_by"] = "USER"; seal(searching_rows[5], "content_sha256")
    def response(kind, rows):
        journal = b"".join(canonical(r) + b"\n" for r in rows)
        timeline = [{"kind": "GAP", "range_us": [0, 12000000]}]
        if kind in {"phase", "standard"}:
            entry = 7600000 if kind == "phase" else 3000000
            decision_id = "SYNTHETIC_D5" if kind == "phase" else "SYNTHETIC_D1"
            timeline = [{"segment_id": "SYNTHETIC_SEG", "kind": "ON_CAMERA", "range_us": [entry, 12000000],
                "entered_by": "SWITCH", "decision_id": decision_id, "camera_id": "SYNTHETIC_C",
                "observation_ids": ["SYNTHETIC_OBSERVATION"]}]
        doc = dict(schema_version="q-demo.q2-response.v1", session_id="SYNTHETIC_SESSION",
            status="ENDED_BY_LIMIT" if kind == "limit" else "COMPLETE", agent_used=False, fallback_used=False,
            resolved_scope={"run_ids": ["SYNTHETIC_RUN"], "clock_ids": ["SYNTHETIC_CLOCK"],
                "parameter_set_sha256": parameters["content_sha256"],
                "resolved_source_ranges_us": [{"run_id": "SYNTHETIC_RUN", "range_us": [0, 12000000]}]},
            decisions_sha256=sha(journal), timeline=timeline)
        seal(doc, "output_sha256")
        put(f"{kind}.response.SYNTHETIC.json", doc)
        put(f"{kind}.decisions.SYNTHETIC.jsonl", raw=journal)
    for kind, rows in [("phase", phase_rows), ("standard", standard_rows), ("limit", limit_rows), ("searching", searching_rows)]:
        response(kind, rows)
    put("MANIFEST.SYNTHETIC.json", {"fixture_role": "SYNTHETIC_ONLY", "files": generated.copy()})


if __name__ == "__main__":
    build()
