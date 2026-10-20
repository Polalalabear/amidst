"""Conformance kit: valid SYNTHETIC fixtures pass; every violation fixture is caught by its check.

Only the contract layer is tested. Nothing here encodes who appears where or when in a demo story.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from amidst.contracts.q_demo import SCHEMA_DIR, SCHEMA_FILES, load_schema
from amidst.contracts.q_demo.mini_schema import SchemaDefinitionError, Validator
from amidst.evaluation import q1q5_conformance as kit

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/fixtures/q1q5_conformance"
VALID = FIXTURES / "SYNTHETIC/valid"
VIOLATIONS = FIXTURES / "SYNTHETIC/violations.json"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = _load_module("q1q5_build_fixtures", FIXTURES / "build_fixtures.py")
cli = _load_module("q1q5_cli", ROOT / "scripts/check_q1q5_conformance.py")
CASES = json.loads(VIOLATIONS.read_text(encoding="utf-8"))


def _write_params(path: Path, data: dict) -> None:
    """Re-derive content_sha256 and parameter_set_id (contract section 2.2) after an edit."""

    data["content_sha256"] = kit.canonical_sha256(data, ("content_sha256", "parameter_set_id"))
    data["parameter_set_id"] = f"pset:q-demo:{data['content_sha256'][:16]}"
    path.write_text(json.dumps(data), encoding="utf-8")


def _set_param(data: dict, name: str, value: object) -> None:
    next(p for p in data["parameters"] if p["name"] == name)["value"] = value


def _failed(results: list[dict]) -> set[str]:
    return {r["check_id"] for r in results if r["status"] == kit.FAIL}


def _run(directory: Path) -> list[dict]:
    return kit.run_checks(kit.load_directory(directory))


# ------------------------------------------------------------------ valid fixtures


def test_valid_fixture_set_passes_every_check() -> None:
    results = _run(VALID)
    assert {r["status"] for r in results} == {kit.PASS}
    ran = {r["check_id"] for r in results}
    assert ran >= {c.id for c in kit.CHECKS} - {"PROBE_FORBIDDEN_FIELD_REJECTED"}


def test_committed_fixtures_match_the_builder(tmp_path: Path) -> None:
    builder.materialize(None, tmp_path / "valid")
    for path in sorted((tmp_path / "valid").iterdir()):
        assert (VALID / path.name).read_bytes() == path.read_bytes(), (
            f"{path.name} drifted; rerun build_fixtures.py"
        )
    assert {p.name for p in VALID.iterdir()} == {p.name for p in (tmp_path / "valid").iterdir()}
    assert json.loads(VIOLATIONS.read_text(encoding="utf-8")) == json.loads(
        json.dumps(builder.all_cases())
    )


# ------------------------------------------------------------------ violation fixtures


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_violation_is_caught_by_the_expected_checks(case: dict, tmp_path: Path) -> None:
    builder.materialize(case, tmp_path)
    results = _run(tmp_path)
    assert _failed(results) == set(case["expect_fail"])
    assert not [r for r in results if r["status"] == kit.SKIPPED_PARAM_UNSET]
    needle = case.get("expect_message_contains")
    if needle:
        text = json.dumps(
            [
                r["findings"]
                for r in results
                if r["status"] == kit.FAIL and r["check_id"] in case["expect_fail"]
            ],
            ensure_ascii=False,
        )
        assert needle in text


def test_every_check_is_proven_to_detect_something() -> None:
    detected = {check for case in CASES for check in case["expect_fail"]}
    untested = (
        {c.id for c in kit.CHECKS} - detected - {"PROBE_FORBIDDEN_FIELD_REJECTED"}
    )  # probe: see base-url tests
    assert not untested, f"no violation fixture for {sorted(untested)}"


# ------------------------------------------------------ parameters (§11): read, never hard-coded


def test_missing_parameter_set_skips_dependent_checks_and_is_not_a_pass(tmp_path: Path) -> None:
    builder.materialize(None, tmp_path)
    (tmp_path / "parameter_set.json").unlink()
    docs = kit.load_directory(tmp_path)
    report = kit.build_report(docs, "recorded")
    assert report["summary"]["overall"] == "INCOMPLETE"
    assert set(report["summary"]["skipped_param_unset_checks"]) == {
        "CANDIDATE_REFS_AND_LIMITS",
        "DECISION_BUDGET_LIMITS",
        "DECISION_SWITCH_GUARD",
        "Q3_ATTEMPTS_WITHIN_PARAM",
        "SEARCHING_TRIGGER_TIME",
    }
    assert kit.exit_code(report) == 1
    assert kit.exit_code(report, allow_incomplete=True) == 0


@pytest.mark.parametrize("placeholder", ["待約定", None, "TBD", "", True])
def test_placeholder_parameter_values_count_as_unset(placeholder, tmp_path: Path) -> None:
    builder.materialize(None, tmp_path)
    path = tmp_path / "parameter_set.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    _set_param(data, "top_k", placeholder)
    _write_params(path, data)
    skipped = {r["check_id"] for r in _run(tmp_path) if r["status"] == kit.SKIPPED_PARAM_UNSET}
    # a bool is not a number, so True is unset too
    assert skipped == {"CANDIDATE_REFS_AND_LIMITS"}


def test_parameter_values_are_read_not_hard_coded(tmp_path: Path) -> None:
    builder.materialize(None, tmp_path)
    path = tmp_path / "parameter_set.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    _set_param(
        data, "switch_min_presence", "MATCH_WEAK"
    )  # looser guard: valid fixture still passes
    _write_params(path, data)
    # responses cite the old parameter-set id / hash, so only SCOPE_HASH_LINKS may fail
    assert _failed(_run(tmp_path)) == {"SCOPE_HASH_LINKS"}


# ------------------------------------------------------------------ report and CLI


def test_cli_report_is_deterministic_and_complete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out1, out2 = tmp_path / "a.json", tmp_path / "b.json"
    assert cli.main(["--recorded", str(VALID), "--output", str(out1)]) == 0
    assert cli.main(["--recorded", str(VALID), "--output", str(out2)]) == 0
    assert out1.read_bytes() == out2.read_bytes()
    report = json.loads(out1.read_text(encoding="utf-8"))
    assert report["summary"]["overall"] == "PASS"
    assert report["contract"]["commit"] == "3873ff2dbe97c88b3de2cfcdfc7df393fdff23d2"
    assert report["contract"]["file_sha256"] == (
        "924c4365ab3b3169eb9192296a26eede9d558d885410e7e80197d00a77978078"
    )
    assert report["kit_version"] == "0.2.1"
    assert report["kit_version"] == kit.KIT_VERSION
    assert report["output_sha256"] == kit.canonical_sha256(report, ("output_sha256",))
    assert all(re.fullmatch(r"[0-9a-f]{64}", i["file_sha256"]) for i in report["inputs"])
    assert not re.search(r'"/(Users|private|tmp|var)/', out1.read_text(encoding="utf-8"))
    unknown = {i["id"] for i in report["unknown_contract_items"]}
    assert unknown >= {"U01", "U04", "U23"}
    assert not unknown & {"U07", "U21", "U22", "U24"}  # answered by contract section 2.2
    assert {i["id"] for i in report["resolved_contract_items"]} == {"U07", "U21", "U22", "U24"}
    capsys.readouterr()


def test_cli_fails_with_exit_code_one_on_a_violation(tmp_path: Path) -> None:
    case = next(c for c in CASES if c["id"] == "identity_confirmed")
    builder.materialize(case, tmp_path)
    assert cli.main(["--recorded", str(tmp_path), "--output", str(tmp_path / "r.json")]) == 1
    assert (
        json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["summary"]["overall"]
        == "FAIL"
    )


def test_cli_with_no_documents_is_an_error(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    assert cli.main(["--recorded", str(empty), "--output", str(tmp_path / "r.json")]) == 1
    assert (
        json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))["summary"]["overall"]
        == "ERROR"
    )


def test_params_option_replaces_the_directory_parameter_set(tmp_path: Path) -> None:
    builder.materialize(None, tmp_path)
    (tmp_path / "parameter_set.json").unlink()
    assert (
        cli.main(
            [
                "--recorded",
                str(tmp_path),
                "--params",
                str(VALID / "parameter_set.json"),
                "--output",
                str(tmp_path / "r.json"),
            ]
        )
        == 0
    )


# ------------------------------------------------------------------ base-url mode (loopback only)


class _Backend(BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, bytes]] = {}
    accept_probe = False

    def do_POST(self) -> None:  # noqa: N802
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if "actor_id" in body and not self.accept_probe:
            code, raw = (
                422,
                json.dumps(
                    {"error_code": "FORBIDDEN_INFERENCE_INPUT", "message": "extra field"}
                ).encode(),
            )
        else:
            body.pop("actor_id", None)
            code, raw = self.routes.get(
                kit.canonical_json(body), (404, b'{"error_code": "DataIntegrityError"}')
            )
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args) -> None:  # silence
        pass


def _serve(accept_probe: bool):
    routes = {}
    for path in VALID.glob("*.request.json"):
        response = VALID / path.name.replace(".request.", ".response.")
        payload = json.loads(path.read_text(encoding="utf-8"))
        code = 422 if json.loads(response.read_text(encoding="utf-8")).get("error_code") else 200
        routes[kit.canonical_json(payload)] = (code, response.read_bytes())
    handler = type("H", (_Backend,), {"routes": routes, "accept_probe": accept_probe})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


@pytest.fixture
def requests_dir(tmp_path: Path) -> Path:
    target = tmp_path / "requests"
    builder.materialize(None, target)
    for path in target.glob("*.response.json"):
        path.unlink()
    return target


def _endpoint_map(tmp_path: Path, drop: str | None = None) -> Path:
    mapping = {
        "q-demo.q1-request.v1": "/q1",
        "q-demo.q3-parse-request.v1": "/q3/parse",
        "q-demo.q2-request.v1": "/q2",
    }
    if drop:
        mapping.pop(drop)
    path = tmp_path / "endpoints.json"
    path.write_text(json.dumps(mapping), encoding="utf-8")
    return path


def test_base_url_mode_against_a_conforming_loopback_backend(
    tmp_path: Path, requests_dir: Path
) -> None:
    server = _serve(accept_probe=False)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        code = cli.main(
            [
                "--base-url",
                url,
                "--requests",
                str(requests_dir),
                "--endpoint-map",
                str(_endpoint_map(tmp_path)),
                "--probe-forbidden",
                "--output",
                str(tmp_path / "r.json"),
            ]
        )
    finally:
        server.shutdown()
    report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert report["summary"]["overall"] == "PASS", report["summary"]
    assert code == 0 and report["mode"] == "base-url"
    assert any(
        r["check_id"] == "PROBE_FORBIDDEN_FIELD_REJECTED" and r["status"] == kit.PASS
        for r in report["checks"]
    )


def test_backend_that_accepts_a_forbidden_field_fails_the_probe(
    tmp_path: Path, requests_dir: Path
) -> None:
    server = _serve(accept_probe=True)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        code = cli.main(
            [
                "--base-url",
                url,
                "--requests",
                str(requests_dir),
                "--endpoint-map",
                str(_endpoint_map(tmp_path)),
                "--probe-forbidden",
                "--output",
                str(tmp_path / "r.json"),
            ]
        )
    finally:
        server.shutdown()
    report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert code == 1
    assert "PROBE_FORBIDDEN_FIELD_REJECTED" in report["summary"]["failed_checks"]


def test_unmapped_endpoint_is_reported_not_guessed(tmp_path: Path, requests_dir: Path) -> None:
    server = _serve(accept_probe=False)
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}"
        code = cli.main(
            [
                "--base-url",
                url,
                "--requests",
                str(requests_dir),
                "--endpoint-map",
                str(_endpoint_map(tmp_path, drop="q-demo.q2-request.v1")),
                "--output",
                str(tmp_path / "r.json"),
            ]
        )
    finally:
        server.shutdown()
    report = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert any(
        r["check_id"] == "ENDPOINT_MAPPED" and r["status"] == kit.SKIPPED_NO_CONTEXT
        for r in report["checks"]
    )
    assert code in (0, 1)


@pytest.mark.parametrize(
    "url", ["http://example.com", "https://127.0.0.1:1", "http://192.168.1.5:80"]
)
def test_non_loopback_hosts_are_refused(url: str, tmp_path: Path, requests_dir: Path) -> None:
    with pytest.raises(ValueError, match="loopback|127.0.0.1"):
        kit.fetch_backend(url, kit.load_directory(requests_dir), {})


# ------------------------------------------------------------------ schemas


def test_every_contract_schema_version_has_a_schema_file() -> None:
    contract_versions = {
        "q-demo.detection-index.v1",
        "q-demo.region-graph.v1",
        "q-demo.camera-transition-graph.v1",
        "q-demo.q1-request.v1",
        "q-demo.q1-response.v1",
        "q-demo.q3-llm-output.v1",
        "q-demo.q3-parse-request.v1",
        "q-demo.q3-parse-response.v1",
        "q-demo.q2-request.v1",
        "q-demo.q2-response.v1",
        "q-demo.agent-decision.v1",
        "q-demo.decision-record.v1",
        "q-demo.clock-mapping.v1",
    }
    assert contract_versions <= set(SCHEMA_FILES)
    for file_name in [*SCHEMA_FILES.values(), "common.schema.json"]:
        assert (SCHEMA_DIR / file_name).is_file()
        load_schema(file_name)


def test_schema_files_have_only_supported_keywords() -> None:
    validator = Validator(load_schema)
    for file_name in SCHEMA_FILES.values():
        # raises SchemaDefinitionError on an unsupported keyword or a bad $ref
        validator.validate({}, file_name)


def test_mini_validator_is_strict() -> None:
    v = Validator(
        lambda name: {
            "t": {
                "type": "object",
                "properties": {"n": {"type": "integer"}},
                "required": ["n"],
                "additionalProperties": False,
            }
        }[name]
    )
    assert v.validate({"n": 1}, "t") == []
    assert v.validate({"n": 1.0}, "t")  # floats are not integers
    assert v.validate({"n": True}, "t")  # bool is not an integer
    assert v.validate({"n": 1, "x": 2}, "t")
    assert v.validate({}, "t")
    bad = Validator(lambda name: {"format": "uuid"})
    with pytest.raises(SchemaDefinitionError):
        bad.validate("x", "any")


def test_non_finite_numbers_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "a.json").write_text(
        '{"schema_version": "q-demo.q1-request.v1", "x": Infinity}', encoding="utf-8"
    )
    docs = kit.load_directory(tmp_path)
    assert docs[0].kind == "unclassified"


# ---------------------------------------------------------- kit hygiene: no GT, story or local path


def test_kit_files_contain_no_gt_route_or_local_path() -> None:
    forbidden = re.compile(
        r"ground_truth|persons\.sim|\.validation\.json|private_evaluation|/Users/|/private/|route_script",
        re.IGNORECASE,
    )
    paths = [*VALID.iterdir(), *SCHEMA_DIR.iterdir()]
    assert paths
    for path in paths:
        assert not forbidden.search(path.read_text(encoding="utf-8")), path.name


def test_valid_fixtures_are_labelled_synthetic() -> None:
    assert (FIXTURES / "SYNTHETIC").is_dir()
    params = json.loads((VALID / "parameter_set.json").read_text(encoding="utf-8"))
    assert all(p["proposed_by"].startswith("SYNTHETIC") for p in params["parameters"])
    assert params["approval"]["approved_by"] == "SYNTHETIC"
    for path in VALID.glob("q*.response.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert str(data.get("provenance", {}).get("producer", "SYNTHETIC")).startswith(
            "SYNTHETIC"
        ), path.name
    assert "SYNTHETIC" in (FIXTURES / "README.md").read_text(encoding="utf-8")


def test_documentation_lists_every_check_and_contract_gap() -> None:
    doc = (ROOT / "docs/evaluation/Q1Q5_CONFORMANCE_KIT.md").read_text(encoding="utf-8")
    for check in kit.CHECKS:
        assert f"`{check.id}`" in doc, f"{check.id} missing from the kit documentation"
    for item in [*kit.UNKNOWN_CONTRACT_ITEMS, *kit.RESOLVED_CONTRACT_ITEMS]:
        assert f"| {item['id']} |" in doc, f"{item['id']} missing from the kit documentation"
    assert kit.CONTRACT["commit"] in doc and kit.CONTRACT["file_sha256"] in doc


# -------------------------------- contract section 2.2: hash preimages of self-derived ids


def test_index_key_is_independent_of_the_records_file(tmp_path: Path) -> None:
    case = next(c for c in CASES if c["id"] == "records_change_keeps_index_id")
    builder.materialize(case, tmp_path / "changed")
    base = json.loads((VALID / "detection_index.json").read_text(encoding="utf-8"))
    changed = json.loads((tmp_path / "changed/detection_index.json").read_text(encoding="utf-8"))
    assert changed["records_file_sha256"] != base["records_file_sha256"]
    assert changed["content_sha256"] != base["content_sha256"]  # still binds the records
    assert changed["index_id"] == base["index_id"]  # the index key does not
    segment = base["index_id"].rsplit(":", 1)[1]
    assert segment == kit.index_key(base)[:16] != base["content_sha256"][:16]
    records = (VALID / "detection_index.records.jsonl").read_text(encoding="utf-8")
    assert f"obs:{segment}:" in records
    assert _failed(_run(tmp_path / "changed")) == set()


def test_index_key_ignores_exactly_the_four_documented_fields() -> None:
    base = json.loads((VALID / "detection_index.json").read_text(encoding="utf-8"))
    key = kit.index_key(base)
    for field in ("index_id", "content_sha256", "records_ref", "records_file_sha256", "stats"):
        assert kit.index_key({**base, field: "other"}) == key, field
    assert kit.index_key({**base, "run_id": "OTHER"}) != key
    assert kit.index_key({**base, "sampling": {**base["sampling"], "stride_samples": 9}}) != key


def test_snapshot_hash_excludes_candidate_refs_but_binds_the_rest() -> None:
    snap = json.loads((VALID / "q2_rule.snapshot.json").read_text(encoding="utf-8"))
    assert snap["candidate_snapshot_sha256"] == kit.snapshot_hash(snap)
    with_refs = kit.canonical_sha256(snap, ("candidate_snapshot_sha256",))
    assert with_refs != snap["candidate_snapshot_sha256"]  # the circular preimage is not used
    prefix = snap["candidate_snapshot_sha256"][:16]
    assert [c["candidate_ref"] for c in snap["candidates"]] == [
        f"cand:{prefix}:{c['rank']}" for c in snap["candidates"]
    ]
    changed = json.loads(json.dumps(snap))
    changed["candidates"][1]["window_us"][1] += 1
    assert kit.snapshot_hash(changed) != snap["candidate_snapshot_sha256"]
    swapped_refs = json.loads(json.dumps(snap))
    swapped_refs["candidates"][0]["candidate_ref"] = "cand:ffffffffffffffff:1"
    assert kit.snapshot_hash(swapped_refs) == snap["candidate_snapshot_sha256"]


def test_circular_snapshot_hash_is_rejected(tmp_path: Path) -> None:
    snap = json.loads((VALID / "q2_rule.snapshot.json").read_text(encoding="utf-8"))
    circular = kit.canonical_sha256(snap, ("candidate_snapshot_sha256",))  # refs included
    snap["candidate_snapshot_sha256"] = circular
    for c in snap["candidates"]:
        c["candidate_ref"] = f"cand:{circular[:16]}:{c['rank']}"
    (tmp_path / "q2_rule.snapshot.json").write_text(json.dumps(snap), encoding="utf-8")
    failed = _failed(kit.run_checks(kit.load_directory(tmp_path), only={"CANDIDATE_SNAPSHOT_HASH"}))
    assert failed == {"CANDIDATE_SNAPSHOT_HASH"}


def test_graph_and_parameter_set_ids_exclude_their_own_id_from_the_hash() -> None:
    for name, field in (
        ("region_graph.json", "graph_id"),
        ("camera_graph.json", "graph_id"),
        ("parameter_set.json", "parameter_set_id"),
    ):
        data = json.loads((VALID / name).read_text(encoding="utf-8"))
        assert data["content_sha256"] == kit.canonical_sha256(data, ("content_sha256", field)), name
        assert data[field].rsplit(":", 1)[1] == data["content_sha256"][:16], name
        assert data["content_sha256"] != kit.canonical_sha256(data, ("content_sha256",)), name


# --------------------------------- contract sections 5.4, 8.2, 8.3: decision tables and examples


@pytest.mark.parametrize(
    ("relation", "unknown_state", "traversability", "tier"),
    [
        ("UNKNOWN", False, "APPROVED_WALKABLE", 4),  # missing coverage data comes first ...
        ("UNKNOWN", True, "UNKNOWN", 4),  # ... even if the path also has an UNKNOWN edge
        ("OVERLAP", True, "APPROVED_WALKABLE", 3),  # an UNKNOWN edge is not lifted back to tier 1
        ("OVERLAP", False, "APPROVED_WALKABLE", 1),
        ("BLIND_GAP", True, "APPROVED_WALKABLE", 3),
        ("BLIND_GAP", False, "APPROVED_WALKABLE", 2),
        ("BLIND_GAP", False, "UNKNOWN", None),  # the contract gives no tier (U08)
    ],
)
def test_relation_tier_decision_order(relation, unknown_state, traversability, tier) -> None:
    candidate = {
        "relation": relation,
        "path_has_unknown_state": unknown_state,
        "path_traversability": traversability,
    }
    assert kit._tier(candidate) == tier


@pytest.mark.parametrize(
    ("interval", "gap_us", "listed", "ok"),
    [
        (200_000, 600_000, 2, True),  # section 8.2 example: 3rd missing cell searches
        (200_000, 600_000, None, True),
        (200_000, 200_000, 0, True),  # N = 0: the first missing cell is TEMP_LOST and SEARCHING
        (400_000, 1_200_000, 2, True),
        (400_000, 600_000, None, False),  # 600000 is not a multiple of 400000
        (1_000_000, 600_000, None, False),  # smaller than one cell
        (200_000, 600_000, 3, False),  # listed samples differ from gap_us / interval - 1
        (200_000, 600_001, None, False),  # never rounded
    ],
)
def test_grid_check_derives_link_max_gap_samples(interval, gap_us, listed, ok) -> None:
    params = [{"name": "link_max_gap_us", "value": gap_us}]
    if listed is not None:
        params.append({"name": "link_max_gap_samples", "value": listed})
    pset = {"applies_to": {"index_interval_us": interval}, "parameters": params}
    assert (kit.grid_problems(pset, gap_us, [], None) == []) is ok


def test_threshold_is_inclusive_on_the_linked_cell_and_exclusive_on_failing_cells() -> None:
    links = json.loads(
        json.dumps(
            [
                json.loads(line)
                for line in (VALID / "q2_rule.links.jsonl").read_text("utf-8").splitlines()
            ]
        )
    )
    iv, gap = 400_000, 1_200_000
    max_samples = gap // iv - 1
    linked = [r for r in links if r["decision"] == "LINKED"]
    failing = [r for r in links if r["decision"] != "LINKED"]
    assert any(r["elapsed_us"] == gap for r in linked)  # equal to the threshold, still linked
    assert all(r["gap_samples"] <= max_samples for r in linked)
    searching = [r for r in failing if r["gap_samples"] > max_samples]
    assert [r["elapsed_us"] for r in searching] == [gap]  # elapsed >= gap  <=>  gap_samples > N
    assert all((r["elapsed_us"] >= gap) == (r["gap_samples"] > max_samples) for r in failing)


@pytest.mark.parametrize(
    ("timezone", "wall_origin", "ok"),
    [
        ("Asia/Taipei", "2026-10-20T08:00:00+08:00", True),
        ("America/New_York", "2026-11-01T01:30:00-04:00", True),  # fold=0 of the repeated hour
        ("America/New_York", "2026-11-01T01:30:00-05:00", True),  # fold=1 (#133)
        ("America/New_York", "2026-11-01T01:30:00+08:00", False),  # offset wrong for the zone
        ("Asia/Taipei", "2026-10-20T08:00:00+09:00", False),
        ("America/New_York", "2026-03-08T02:30:00-05:00", False),  # spring-forward gap
        ("America/New_York", "2026-03-08T02:30:00-04:00", False),  # spring-forward gap
        ("Asia/Taipei", "2026-10-20T08:00:00", False),  # no explicit offset
    ],
)
def test_clock_mapping_accepts_both_folds_and_rejects_bad_offsets(
    timezone: str, wall_origin: str, ok: bool
) -> None:
    data = {
        "timezone": timezone,
        "wall_origin": wall_origin,
        "t0_us": 0,
        "source_duration_us": 60_000_000,
    }
    doc = kit.Doc("clock_mapping.json", "clock_mapping", data, "0" * 64)
    out = kit.Findings()
    kit._clock_mapping(doc, kit.Ctx([doc], {}), out)
    assert (out.items == []) is ok
