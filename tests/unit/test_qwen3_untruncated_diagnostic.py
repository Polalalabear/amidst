"""CX-6 tests use only local fixture bytes and an injected fake transport."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "diagnose_qwen3_untruncated.py"
SPEC = importlib.util.spec_from_file_location("cx6_diagnostic", SCRIPT)
d = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(d)
DIGEST = "b" * 64
MODEL = "qwen3:test"
Q3_SCHEMA = {"type": "object", "properties": {
    "schema_version": {"const": "q-demo.q3-llm-output.v1"},
    "intent": {"enum": ["FIND_CAMERAS", "FIND_PERSON"]},
    "class_term": {"enum": ["person"]}, "color_term": {"const": None},
    "time_literal": {"type": "object", "properties": {k: {"type": ["string", "null"], "minLength": 1} for k in ("start", "end", "date")},
                     "required": ["start", "end", "date"], "additionalProperties": False},
    "camera_terms": {"type": "array", "maxItems": 0},
    "region_terms": {"type": "array", "maxItems": 0},
    "needs_clarification": {"type": "boolean"},
    "clarification_question": {"type": ["string", "null"], "minLength": 1}},
    "required": ["schema_version", "intent", "class_term", "color_term", "time_literal", "camera_terms", "region_terms", "needs_clarification", "clarification_question"],
    "additionalProperties": False}
Q3_VALUE = {"schema_version": "q-demo.q3-llm-output.v1", "intent": "FIND_CAMERAS",
            "class_term": "person", "color_term": None,
            "time_literal": {"start": "13:00", "end": "13:08", "date": None},
            "camera_terms": [], "region_terms": [], "needs_clarification": False,
            "clarification_question": None}
Q5_SCHEMA = {"anyOf": [{"type": "object", "properties": {"action": {"const": "RETURN_TO_ORIGIN"}, "cited_observation_ids": {"type": "array", "maxItems": 0}},
                       "required": ["action", "cited_observation_ids"], "additionalProperties": False},
                      {"type": "object", "properties": {"tool": {"const": "get_candidate_evidence"}, "candidate_ref": {"enum": ["cand:1"]}},
                       "required": ["tool", "candidate_ref"], "additionalProperties": False}]}


def wire(stage, variant=0):
    return {"model": MODEL, "messages": [{"role": "user", "content": f"LOCAL PRIVATE FIXTURE {variant}"}],
            "format": deepcopy(Q3_SCHEMA if stage == "q3" else Q5_SCHEMA),
            "options": {"num_ctx": 4096, "num_predict": 256, "seed": 7, "temperature": 0},
            "stream": False, "think": False, "keep_alive": "5m"}


@pytest.fixture
def frozen(tmp_path):
    files, calls = [], []
    stages = ["q3", "q3", "q5"] * 6
    for number, stage in enumerate(stages, 1):
        w = wire(stage, 0 if number % 3 == 1 else 1 if stage == "q3" else 2)
        record = {"model": MODEL, "model_digest": DIGEST, "wire_request": w}
        value = {"request": {"text": "person 13:00 to 13:08"},
                 "q3_provider_audit": [{"provider_record": record}],
                 "agent_trace": {"events": [{"record": record}]}}
        raw = d.encode(value)
        path = tmp_path / f"record-{number:02d}.json"
        path.write_bytes(raw)
        files.append({"path": str(path), "sha256": d.sha256(raw), "role": "api_recording", "round": 1})
        calls.append({"number": number, "stage": stage, "model": MODEL, "round": 1,
                      "recording_sha256": d.sha256(raw), "timeout_ms": 2000,
                      "record_location": "/0/provider_record" if stage == "q3" else "/events/0/record"})
    config = {"files": files, "expected_calls": 18}
    result = {"calls": calls, "source_file_hashes": [f["sha256"] for f in files]}
    a, b = tmp_path / "inputs.json", tmp_path / "baseline.json"
    a.write_bytes(d.encode(config))
    b.write_bytes(d.encode(result))
    args = (a, d.sha256(a.read_bytes()), b, d.sha256(b.read_bytes()), tmp_path)
    return args


class FakeTransport:
    def __init__(self, *, drift_at=None, reason="stop", invalid=False):
        self.requests = []
        self.tags_count = 0
        self.drift_at = drift_at
        self.reason = reason
        self.invalid = invalid

    def __call__(self, method, route, body, timeout):
        self.requests.append((method, route, body, timeout))
        if route == "/api/tags":
            self.tags_count += 1
            digest = "c" * 64 if self.drift_at and self.tags_count >= self.drift_at else DIGEST
            return d.encode({"models": [{"name": MODEL, "digest": digest}]})
        if route != "/api/chat":
            return b"{}"
        request = d.strict_json(body)
        schema = request["format"]
        value = deepcopy(Q3_VALUE) if "anyOf" not in schema else {"action": "RETURN_TO_ORIGIN", "cited_observation_ids": []}
        content = '{"a":1,"a":2}' if self.invalid else d.encode(value).decode()
        return d.encode({"model": MODEL, "message": {"role": "assistant", "content": content},
                         "done": True, "done_reason": self.reason, "eval_count": 10,
                         "prompt_eval_count": 12, "total_duration": 100000000,
                         "load_duration": 100, "prompt_eval_duration": 300,
                         "eval_duration": 500})


def run(frozen, output, fake, **kwargs):
    cases, pins = d.load_cases(*frozen)
    return d.run_diagnostic(cases, pins, output, "http://127.0.0.1:11437", transport=fake,
                            disk_free=kwargs.pop("disk_free", lambda _: d.MIN_FREE_BYTES), **kwargs)


def test_full_replay_preserves_order_and_payload_except_output_cap(frozen, tmp_path):
    cases, _ = d.load_cases(*frozen)
    fake = FakeTransport()
    out = tmp_path / "out"
    result = run(frozen, out, fake)
    assert result["status"] == "COMPLETE"
    assert result["completed_calls"] == result["schema_valid_outputs"] == result["untruncated_completions"] == 18
    requests = [r for r in fake.requests if r[1] == "/api/chat"]
    assert len(requests) == 18
    for case, (method, _, body, timeout) in zip(cases, requests, strict=True):
        sent = d.strict_json(body)
        expected = deepcopy(case["wire"])
        expected["options"]["num_predict"] = -1
        assert sent == expected and timeout is None and method == "POST"
    assert all(c["semantic_controller_acceptance"] == "UNKNOWN" for c in result["calls"])
    assert all(c["q3_literal_guard_valid"] for c in result["calls"] if c["stage"] == "q3")
    assert not result["formal_denominator"] and not result["budgets_changed"]
    public = (out / "RESULT.json").read_text()
    assert str(tmp_path) not in public and "LOCAL PRIVATE FIXTURE" not in public
    manifest = d.strict_json((out / "MANIFEST.json").read_bytes())
    assert manifest["file_count_including_manifest"] == len(list(out.rglob("*"))) - 1
    for row in manifest["files"]:
        raw = (out / row["path"]).read_bytes()
        assert len(raw) == row["size_bytes"] and d.sha256(raw) == row["sha256"]


def test_input_tampering_prevents_network(frozen):
    args = list(frozen)
    args[1] = "0" * 64
    with pytest.raises(d.DiagnosticError, match="HASH_MISMATCH"):
        d.load_cases(*args)


def test_input_escape_and_symlink_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}")
    (root / "escape").symlink_to(outside)
    for locator in ("../outside.json", "escape"):
        with pytest.raises(d.DiagnosticError, match="OUTSIDE_ROOT"):
            d.contained_path(root, locator)


def test_model_drift_after_call_stops_next_generation(frozen, tmp_path):
    fake = FakeTransport(drift_at=3)
    result = run(frozen, tmp_path / "drift", fake)
    assert result["status"] == "FAILED" and result["failure"] == "MODEL_DIGEST_DRIFT_OR_MISSING"
    assert len([r for r in fake.requests if r[1] == "/api/chat"]) == 1
    assert result["untruncated_completions"] == 0
    assert result["calls"][0]["model_pin_verified_after"] is False


def test_disk_gate_before_each_generation(frozen, tmp_path):
    checks = iter([d.MIN_FREE_BYTES, d.MIN_FREE_BYTES, d.MIN_FREE_BYTES - 1])
    fake = FakeTransport()
    result = run(frozen, tmp_path / "disk", fake, disk_free=lambda _: next(checks))
    assert result["failure"] == "DISK_BELOW_EIGHT_GIB"
    assert len([r for r in fake.requests if r[1] == "/api/chat"]) == 1


def test_existing_output_not_overwritten(frozen, tmp_path):
    out = tmp_path / "exists"
    out.mkdir()
    fake = FakeTransport()
    with pytest.raises(d.DiagnosticError, match="OUTPUT_ALREADY_EXISTS"):
        run(frozen, out, fake)
    assert fake.requests == [] and list(out.iterdir()) == []


@pytest.mark.parametrize("reason", ["length", "load", "arbitrary"])
def test_only_stop_is_untruncated_completion(frozen, tmp_path, reason):
    result = run(frozen, tmp_path / "reason", FakeTransport(reason=reason))
    assert result["completed_calls"] == 18 and result["untruncated_completions"] == 0


def test_duplicate_output_is_invalid_without_skipping_calls(frozen, tmp_path):
    result = run(frozen, tmp_path / "invalid", FakeTransport(invalid=True))
    assert result["completed_calls"] == 18 and result["schema_valid_outputs"] == 0
    assert not any(c["json_valid"] for c in result["calls"])


@pytest.mark.parametrize("raw", [b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}'])
def test_strict_json_rejects_duplicate_or_nonfinite(raw):
    with pytest.raises(d.DiagnosticError):
        d.strict_json(raw)


@pytest.mark.parametrize("url", ["https://127.0.0.1:11437", "http://localhost:11437", "http://example.com:80",
                                "http://127.0.0.1:11437/api/chat", "http://a@127.0.0.1:11437", "http://127.0.0.1:11437?x=1"])
def test_network_surface_rejects_nonliteral_or_extra_url_parts(url):
    with pytest.raises(d.DiagnosticError):
        d.LocalTransport(url)


def test_transport_route_allowlist_and_redirect_rejection():
    transport = d.LocalTransport("http://127.0.0.1:11437")
    with pytest.raises(d.DiagnosticError, match="ROUTE_NOT_ALLOWED"):
        transport("POST", "/api/pull", b"{}", 1)
    with pytest.raises(d.DiagnosticError, match="REDIRECT_REJECTED"):
        d.NoRedirect().redirect_request(None, None, 302, None, None, "https://example.com")


def test_schema_unknown_keyword_is_rejected_and_refs_are_exact():
    with pytest.raises(d.DiagnosticError, match="UNSUPPORTED_SCHEMA"):
        d.check_schema({"$ref": "https://example.com/schema"})
    d.check_schema(Q5_SCHEMA)
    assert d.schema_valid({"tool": "get_candidate_evidence", "candidate_ref": "cand:1"}, Q5_SCHEMA)
    assert not d.schema_valid({"tool": "get_candidate_evidence", "candidate_ref": "cand:2"}, Q5_SCHEMA)
    assert not d.schema_valid(True, {"const": 1})
    assert not d.schema_valid(1, {"type": "boolean"})
    assert not d.schema_valid(True, {"type": "integer"})
    overlapping = {"oneOf": [{"type": "integer"}, {"enum": [1]}]}
    d.check_schema(overlapping)
    assert not d.schema_valid(1, overlapping)
    assert d.schema_valid(2, overlapping)
    assert not d.schema_valid({"x": 1, "extra": 2}, {"properties": {"x": {"type": "integer"}}, "additionalProperties": False})


def test_q3_literal_guard_and_clarification_consistency():
    assert d.q3_literal_valid(Q3_VALUE, "person 13:00 to 13:08")
    invented = deepcopy(Q3_VALUE)
    invented["time_literal"]["start"] = "12:00"
    assert not d.q3_literal_valid(invented, "person 13:00 to 13:08")
    invented = deepcopy(Q3_VALUE)
    invented["needs_clarification"] = True
    assert not d.q3_literal_valid(invented, "person 13:00 to 13:08")


def test_incomplete_input_call_set_rejected(frozen):
    args = list(frozen)
    data = d.strict_json(args[2].read_bytes())
    data["calls"].pop()
    args[2].write_bytes(d.encode(data))
    args[3] = d.sha256(args[2].read_bytes())
    with pytest.raises(d.DiagnosticError, match="EIGHTEEN"):
        d.load_cases(*args)
