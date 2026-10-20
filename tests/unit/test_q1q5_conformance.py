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
    }
    assert kit.exit_code(report) == 1
    assert kit.exit_code(report, allow_incomplete=True) == 0


@pytest.mark.parametrize("placeholder", ["待約定", None, "TBD", "", True])
def test_placeholder_parameter_values_count_as_unset(placeholder, tmp_path: Path) -> None:
    builder.materialize(None, tmp_path)
    path = tmp_path / "parameter_set.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["top_k"] = placeholder
    data["content_sha256"] = kit.canonical_sha256(data, ("content_sha256",))
    path.write_text(json.dumps(data), encoding="utf-8")
    skipped = {r["check_id"] for r in _run(tmp_path) if r["status"] == kit.SKIPPED_PARAM_UNSET}
    # a bool is not a number, so True is unset too; re-linked hashes mean no FAIL appears
    assert skipped == {"CANDIDATE_REFS_AND_LIMITS"}


def test_parameter_values_are_read_not_hard_coded(tmp_path: Path) -> None:
    builder.materialize(None, tmp_path)
    path = tmp_path / "parameter_set.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["switch_min_presence"] = "MATCH_WEAK"  # looser guard: valid fixture still passes
    data["content_sha256"] = kit.canonical_sha256(data, ("content_sha256",))
    path.write_text(json.dumps(data), encoding="utf-8")
    # responses cite the old parameter-set hash, so only SCOPE_HASH_LINKS may fail
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
    assert report["contract"]["commit"] == "258c7e2cf24b37ab69a5c4578fe23cc5f000d724"
    assert report["kit_version"] == kit.KIT_VERSION
    assert report["output_sha256"] == kit.canonical_sha256(report, ("output_sha256",))
    assert all(re.fullmatch(r"[0-9a-f]{64}", i["file_sha256"]) for i in report["inputs"])
    assert not re.search(r'"/(Users|private|tmp|var)/', out1.read_text(encoding="utf-8"))
    assert {i["id"] for i in report["unknown_contract_items"]} >= {"U01", "U04"}
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
    assert json.loads((VALID / "parameter_set.json").read_text(encoding="utf-8"))[
        "parameter_set_id"
    ].startswith("SYNTHETIC")
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
    for item in kit.UNKNOWN_CONTRACT_ITEMS:
        assert f"| {item['id']} |" in doc, f"{item['id']} missing from the kit documentation"
    assert kit.CONTRACT["commit"] in doc and kit.CONTRACT["file_sha256"] in doc
