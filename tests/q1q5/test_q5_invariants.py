"""Independent checker positives and adversarial, rehashed negative journals."""

import json
from copy import deepcopy
from functools import lru_cache

import pytest
from q5_audit_source import run_pinned
from q5_invariant_helpers import check_journal, digest, wire_hash


@lru_cache(maxsize=2)
def example(switch=True):
    pattern = "None" if switch else "{'A': {i: 'STRONG' for i in range(10)}}"
    return run_pinned(f"b = fixture({pattern})\nr, _ = run(b)\nresult = bundle(r, b)")


def rows(bundle):
    return [json.loads(s) for s in bundle["decisions"].splitlines()]


def reseal(bundle, decisions=None):
    """Rehash tampering so semantic checks cannot pass on hash rejection alone."""
    if decisions is not None:
        for row in decisions:
            row["content_sha256"] = digest(row, ("content_sha256", "stats"))
        bundle["decisions"] = "".join(
            json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in decisions
        )
    r = bundle["response"]
    r["decisions_sha256"] = wire_hash(bundle["decisions"])
    r["links_sha256"] = wire_hash(bundle["links"])
    r["output_sha256"] = digest(r, ("output_sha256", "stats"))


def codes(report):
    return {finding.code for finding in report.violations}


def test_normal_no_switch_journal_passes_and_inputs_are_immutable():
    bundle = deepcopy(example(False))
    before = deepcopy(bundle)
    report = check_journal(bundle)
    assert report.status == "PASS" and bundle == before


def test_as_is_switch_is_explicit_known_gap_and_contract_is_not_passed():
    report = check_journal(example())
    assert report.status == "KNOWN_GAPS" and not report.violations
    assert {x.code for x in report.known_gaps} == {"SWITCHING_NOT_RECORDED"}
    contract = check_journal(example(), profile="CONTRACT")
    assert contract.status == "FAIL" and "SWITCHING_NOT_RECORDED" in codes(contract)


@pytest.mark.parametrize(
    "missing,code",
    [
        ("trusted_scope", "TRUSTED_SCOPE_MISSING"),
        ("snapshots", "SWITCH_CONTEXT_MISSING"),
        ("evidence", "SWITCH_CONTEXT_MISSING"),
        ("index_records", "INDEX_CONTEXT_MISSING"),
    ],
)
def test_missing_context_is_incomplete_never_pass(missing, code):
    bundle = deepcopy(example())
    del bundle[missing]
    report = check_journal(bundle)
    assert report.status == "INCOMPLETE" and code in {x.code for x in report.unchecked}


@pytest.mark.parametrize(
    "case,code",
    [
        ("hash", "RESPONSE_HASH"),
        ("bytes", "DECISIONS_FILE_HASH"),
        ("link_bytes", "LINKS_FILE_HASH"),
        ("scope", "SOURCE_SCOPE"),
        ("identity", "EVIDENCE_BOUNDARY"),
        ("gt", "EVIDENCE_BOUNDARY"),
        ("gap_position", "GAP_POSITION"),
        ("interval", "TIMELINE_INTERVAL"),
        ("query_end", "QUERY_BOUNDS"),
        ("entry", "SWITCH_ENTRY"),
        ("foreign_entry", "ENTRY_INDEX_BINDING"),
        ("orphan", "ORPHAN_SWITCH_SEGMENT"),
        ("state", "STATE_TRANSITION"),
        ("terminal", "MISSING_TERMINAL"),
        ("step", "DECISION_ID_ORDER"),
        ("counter", "COUNTER_RESET"),
        ("time", "SOURCE_TIME"),
        ("decision_time", "DECISION_TIME"),
        ("action", "ACTION_VOCABULARY"),
        ("rejected", "REJECTED_ACTION_EXECUTED"),
        ("rank", "CANDIDATE_ORDER"),
        ("snapshot", "SNAPSHOT_HASH_SCOPE"),
        ("candidate", "CANDIDATE_REF"),
        ("weak", "SWITCH_GUARD"),
        ("evidence_hash", "EVIDENCE_HASH"),
        ("unfetched", "EVIDENCE_NOT_FETCHED"),
        ("uncited", "EVIDENCE_CITATION"),
        ("fallback", "AGENT_AFTER_FALLBACK"),
        ("link_attach", "LINK_ATTACHMENT"),
        ("link_order", "LINK_ORDER_SCOPE"),
        ("link_bool", "LINK_GRID"),
    ],
)
def test_rehashed_single_fault_is_detected(case, code):
    bundle = deepcopy(example())
    d = rows(bundle)
    switch = next(x for x in d if x["executed_action"] == "SWITCH")
    segment = next(s for s in bundle["response"]["timeline"] if s.get("entered_by") == "SWITCH")
    response = bundle["response"]
    if case == "hash":
        response["output_sha256"] = "0" * 64
    elif case == "bytes":
        bundle["decisions"] += "\n"
    elif case == "link_bytes":
        bundle["links"] += "\n"
    else:
        if case == "scope":
            response["resolved_scope"]["run_ids"] = ["FOREIGN"]
        elif case == "identity":
            response["identity_verdict"] = "CONFIRMED"
        elif case == "gt":
            response["provenance"]["gt_read"] = True
        elif case == "gap_position":
            response["timeline"][1]["position"] = [1, 2, 3]
        elif case == "interval":
            segment["range_us"][0] = True
        elif case == "query_end":
            segment["range_us"][1] += 1
        elif case == "entry":
            segment["observation_ids"][0] = "FOREIGN"
        elif case == "foreign_entry":
            bundle["index_records"] = []
        elif case == "orphan":
            switch["executed_action"] = None
        elif case == "state":
            switch["state_before"] = "ENDED"
        elif case == "terminal":
            d.pop()
        elif case == "step":
            switch["step_index"] = 0
        elif case == "counter":
            d[-1]["searching_index"] = 0
        elif case == "time":
            switch["source_time_us"] = 0
        elif case == "decision_time":
            switch["decision_time_us"] = switch["source_time_us"] + 1
        elif case == "action":
            switch["executed_action"] = "CONFIRM_PERSON"
        elif case == "rejected":
            switch["accepted"] = False
        elif case == "rank":
            switch["candidates_considered"] *= 2
        elif case == "snapshot":
            bundle["snapshots"][0]["session_id"] = "FOREIGN"
        elif case == "candidate":
            switch["executed_candidate_ref"] = "FOREIGN"
        elif case in {"weak", "evidence_hash"}:
            e = bundle["evidence"][0]
            e["target_presence"] = "MATCH_WEAK"
            if case == "weak":
                e["evidence_sha256"] = digest(e, ("evidence_sha256", "stats"))
        elif case == "unfetched":
            bundle["evidence"] = []
        elif case == "uncited":
            switch["candidates_considered"] = []
        elif case == "fallback":
            d[0]["decided_by"] = "RULE_FALLBACK"
            switch["llm_calls"] = [{"model": "SYNTHETIC"}]
        elif case.startswith("link_"):
            links = [json.loads(x) for x in bundle["links"].splitlines()]
            if case == "link_attach":
                links[0]["next_observation_id"] = None
            elif case == "link_order":
                links[0]["link_index"] = 7
            else:
                links[0]["gap_samples"] = True
            bundle["links"] = "".join(json.dumps(x) + "\n" for x in links)
        reseal(bundle, d)
    report = check_journal(bundle)
    assert report.status == "FAIL" and code in codes(report), report


@pytest.mark.parametrize("value", [None, [], {}, {"response": None}, {"response": float("nan")}])
def test_malformed_inputs_are_reported_without_crashing(value):
    assert "MALFORMED_JOURNAL" in codes(check_journal(value))


def test_unknown_profile_is_not_silently_interpreted():
    with pytest.raises(ValueError, match="AS_IS or CONTRACT"):
        check_journal({}, profile="APPROVED")


@pytest.mark.parametrize(
    "case,code",
    [
        ("coverage", "EVIDENCE_COVERAGE"),
        ("zero_negative", "NEGATIVE_WITHOUT_COVERAGE"),
        ("bool_count", "EVIDENCE_COUNTS"),
        ("presence", "PRESENCE_VOCABULARY"),
        ("window", "SWITCH_GUARD"),
        ("rank", "EVIDENCE_CITATION"),
        ("episode", "EPISODE_COUNTER_RESET"),
        ("link_vocab", "LINK_DECISION"),
    ],
)
def test_coverage_and_episode_invariants_reject_rehashed_corruption(case, code):
    b = deepcopy(example())
    d = rows(b)
    e = b["evidence"][0]
    if case == "coverage":
        e["coverage_complete"] = False
    elif case == "zero_negative":
        e["frames"] = {k: 0 for k in e["frames"]}
        e["coverage_complete"] = False
        e["target_presence"] = "NO_PERSON_DETECTED"
    elif case == "bool_count":
        e["frames"]["not_sampled"] = True
    elif case == "presence":
        e["target_presence"] = "MAYBE_PRESENT"
    elif case == "window":
        e["window_us"] = [0, 1]
    elif case == "rank":
        next(x for x in d if x["executed_action"] == "SWITCH")["candidates_considered"][0][
            "rank"
        ] = 99
    elif case == "episode":
        next(x for x in d if x["state_after"] == "SEARCHING")["rounds_used"] = 1
    else:
        links = [json.loads(x) for x in b["links"].splitlines()]
        links[0]["decision"] = "PERSON_ABSENT"
        b["links"] = "".join(json.dumps(x) + "\n" for x in links)
    e["evidence_sha256"] = digest(e, ("evidence_sha256", "stats"))
    reseal(b, d)
    assert code in codes(check_journal(b))


@pytest.mark.parametrize("offset", [-1, 1])
def test_terminal_clock_is_query_bounded_with_inclusive_end_only(offset):
    b = deepcopy(example(False))
    d = rows(b)
    if offset < 0:
        d[0]["source_time_us"] = -1
    else:
        d[-1]["source_time_us"] += 1
    reseal(b, d)
    assert "DECISION_QUERY_BOUNDS" in codes(check_journal(b))


def test_active_timeline_without_initial_journal_is_not_accepted():
    b = deepcopy(example(False))
    reseal(b, [])
    assert "MISSING_INITIAL_JOURNAL" in codes(check_journal(b))


def test_failed_preparation_without_active_timeline_does_not_invent_terminal():
    b = run_pinned("""
from dataclasses import replace
b = fixture()
r = RuleController(request(b), bindings=replace(b, index=None), evidence_provider=port([])).run()
result = bundle(r, b)
""")
    assert not b["response"]["timeline"] and b["response"]["status"] == "UNKNOWN"
    assert check_journal(b).status == "PASS"


@lru_cache(maxsize=1)
def next_example():
    return run_pinned("""
from test_q5_agent import bindings, run_agent, auto
pattern = {'A': {0: 'STRONG', 1: 'STRONG'},
           'B': {i: 'STRONG' for i in range(5, 10)},
           'E': {i: 'STRONG' for i in range(5, 10)}}
b = bindings(pattern, cameras=('A', 'B', 'E'), agent_max_rounds=8)
c, r, provider, calls = run_agent(b, policy=lambda p, n: auto(p, n, 'NEXT_CANDIDATE'))
assert r.response['agent_used'] and not r.response['fallback_used']
result = bundle(r, b)
""")


def test_valid_agent_next_history_is_checked_without_inventing_fallback():
    report = check_journal(next_example())
    assert report.status == "PASS", report


@pytest.mark.parametrize(
    "case,code",
    [
        ("foreign", "NEXT_FOREIGN_CITATION"),
        ("unfetched", "NEXT_EVIDENCE_NOT_FETCHED"),
        ("decision", "NEXT_DECISION_BINDING"),
        ("empty", "NEXT_CITATION"),
    ],
)
def test_next_cannot_claim_foreign_or_unfetched_evidence(case, code):
    b = deepcopy(next_example())
    d = rows(b)
    row = next(x for x in d if x["executed_action"] == "NEXT_CANDIDATE")
    if case == "foreign":
        row["submitted"]["cited_observation_ids"] = ["FOREIGN"]
    elif case == "unfetched":
        b["evidence"] = []
    elif case == "decision":
        row["submitted"]["decision_id"] = "OLD_SLOT"
    else:
        row["submitted"]["cited_observation_ids"] = []
    reseal(b, d)
    assert code in codes(check_journal(b))
