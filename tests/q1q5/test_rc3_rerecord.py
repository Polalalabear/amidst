"""Focused operator-gate tests; no model, rendering, detector, or kit calls."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/rerecord_q1q5_rc3.py"
SPEC = importlib.util.spec_from_file_location("rc3_rerecord", SCRIPT)
rr = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rr)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return path


def recording(root, *, reasons=None, link_version="q-demo.link-record.v2", audit=True):
    response = {"schema_version": "q-demo.q2-response.v1", "reason": "USER_STOPPED",
                "reasons": ["USER_STOPPED"] if reasons is None else reasons, "links_ref": "links.jsonl"}
    scope = {"schema_version": "q-demo.r004-tracking-scope.v3", "synthetic": True}
    write(root / "tracking_scope.json", scope)
    response["resolved_scope"] = {"tracking_scope_sha256": rr.file_digest(root / "tracking_scope.json")}
    write(root / "case.response.json", response)
    write(root / "case.request.json", {"schema_version": "q-demo.q2-request.v1"})
    row = {"schema_version": link_version, "decision": "LINKED"}
    if audit:
        row["matching_audit"] = None
    write(root / "links.jsonl", row)
    return root


@pytest.mark.parametrize("state", ["OPEN", "CLOSED"])
def test_live_unmerged_gate_stops_before_git_or_kit(monkeypatch, tmp_path, state):
    calls = []

    def run(argv, **kwargs):
        calls.append(argv)
        return json.dumps({"state": state, "mergedAt": None}).encode()

    monkeypatch.setattr(rr, "command", run)
    with pytest.raises(ValueError, match="B1_PR257_NOT_MERGED"):
        rr.product_gate(tmp_path, "a" * 40)
    assert len(calls) == 1 and calls[0][:4] == ["gh", "pr", "view", "257"]


@pytest.mark.parametrize("override", [
    {"mergeCommit": {"oid": "b" * 40}}, {"baseRefName": "main"}, {"mergedAt": None},
])
def test_merge_must_match_exact_requested_product(monkeypatch, tmp_path, override):
    receipt = {"state": "MERGED", "mergedAt": "2026-10-26T00:00:00Z",
               "baseRefName": "codex/q1q5-staging", "mergeCommit": {"oid": "a" * 40}}
    receipt.update(override)
    monkeypatch.setattr(rr, "command", lambda *a, **k: json.dumps(receipt).encode())
    with pytest.raises(ValueError, match="B1_PR257_NOT_MERGED"):
        rr.product_gate(tmp_path, "a" * 40)


def test_gate_verifies_both_ancestors_contract_and_rc3(monkeypatch, tmp_path):
    calls = []
    contract = b"merged contract bytes"
    monkeypatch.setattr(rr, "CONTRACT_SHA", rr.digest(contract))

    def run(argv, **kwargs):
        calls.append(argv)
        if argv[:4] == ["gh", "pr", "view", "257"]:
            return json.dumps({"state": "MERGED", "mergedAt": "today",
                               "baseRefName": "codex/q1q5-staging",
                               "mergeCommit": {"oid": "a" * 40}}).encode()
        if argv[:4] == ["gh", "pr", "view", "127"]:
            return json.dumps({"headRefOid": rr.KIT_COMMIT}).encode()
        if argv[:2] == ["git", "show"]:
            return contract
        return b""

    monkeypatch.setattr(rr, "command", run)
    rr.product_gate(tmp_path, "a" * 40)
    assert [c[3] for c in calls if c[:3] == ["git", "merge-base", "--is-ancestor"]] == [
        rr.D85, rr.CONTRACT_MERGE, rr.B1]
    monkeypatch.setattr(rr, "KIT_COMMIT", "changed")
    original = run

    def wrong_kit(argv, **kwargs):
        if argv[:4] == ["gh", "pr", "view", "127"]:
            return b'{"headRefOid":"previous"}'
        return original(argv, **kwargs)

    monkeypatch.setattr(rr, "command", wrong_kit)
    with pytest.raises(ValueError, match="RC4_HEAD_CHANGED"):
        rr.product_gate(tmp_path, "a" * 40)


def test_pin_rejects_mutation_and_symlink_even_same_bytes(tmp_path):
    p = write(tmp_path / "input.json", {"frozen": True})
    pins = rr.inventory([p])
    rr.verify_inventory(pins)
    p.write_text("changed")
    with pytest.raises(ValueError, match="OLD_INPUT_OR_RECORDING_CHANGED"):
        rr.verify_inventory(pins)
    alias = tmp_path / "alias.json"
    alias.symlink_to(p)
    with pytest.raises(ValueError, match="CANONICAL_FILE"):
        rr.pin(alias)


def test_new_output_does_not_overwrite_existing_file(tmp_path):
    p = write(tmp_path / "old.json", {"frozen": True})
    before = p.read_bytes(), p.stat().st_mtime_ns
    with pytest.raises(FileExistsError):
        rr.save(p, {"replacement": True})
    assert (p.read_bytes(), p.stat().st_mtime_ns) == before


@pytest.mark.parametrize("reasons", [None, "USER_STOPPED", ["X", "X"], [None], [""]])
def test_missing_or_malformed_reasons_fail_without_repair(tmp_path, reasons):
    root = recording(tmp_path / "recorded")
    response = rr.load(root / "case.response.json")
    if reasons is None:
        del response["reasons"]
    else:
        response["reasons"] = reasons
    write(root / "case.response.json", response)
    before = rr.inventory(list(root.iterdir()))
    with pytest.raises(ValueError, match="FRESH_REASONS_REQUIRED"):
        rr.validate_recording(root)
    rr.verify_inventory(before)


@pytest.mark.parametrize("version,audit", [("q-demo.link-record.v1", True),
                                           ("q-demo.link-record.v2", False)])
def test_old_or_incomplete_link_journal_rejected(tmp_path, version, audit):
    root = recording(tmp_path / "recorded", link_version=version, audit=audit)
    with pytest.raises(ValueError, match="FRESH_LINK_V2_REQUIRED"):
        rr.validate_recording(root)


def test_v2_nullable_audit_and_empty_reasons_are_valid(tmp_path):
    root = recording(tmp_path / "recorded", reasons=[])
    assert rr.validate_recording(root)["link_v2_rows"] == 1


def test_collect_copies_new_product_bytes_and_records_context_delta(tmp_path):
    old = recording(tmp_path / "old/run/worker-0/sample-0/q5/recorded")
    fresh = recording(tmp_path / "new/run/worker-0/sample-0/q5/recorded")
    write(old / "camera_graph.json", {"legacy": True})
    write(fresh / "camera_graph.json", {"tracking_scope": ["A", "B"]})
    before = rr.inventory(list(old.iterdir()))
    pack = {"root": str(tmp_path / "old"), "expected": 1,
            "selected": [str(old.relative_to(tmp_path / "old"))]}
    out = tmp_path / "handoff"
    rows = rr.collect(pack, [tmp_path / "new/run"], out)
    for p in fresh.iterdir():
        assert (out / "recordings/0" / p.name).read_bytes() == p.read_bytes()
    assert rows[0]["controlled_context_changed"] is True
    assert rows[0]["context_comparison"]["camera_graph.json"]["same_bytes"] is False
    rr.verify_inventory(before)


def test_collect_requires_every_selected_recording(tmp_path):
    with pytest.raises(ValueError, match="FRESH_SELECTION_COUNT"):
        rr.collect({"expected": 8}, [tmp_path / "empty"], tmp_path / "out")


def test_runtime_changes_only_templates_and_content_hash(tmp_path):
    prompts = tmp_path / "source/configs/q1q5/prompts"
    prompts.mkdir(parents=True)
    (prompts / "q3_parse_v2.txt").write_text("new q3\n")
    (prompts / "q5_agent_v2.txt").write_text("new q5\n")
    old = {"q3_template": {"text": "old", "sha256": "old", "version": "q3-parse.v2"},
           "q5_template": {"text": "old", "sha256": "old", "version": "q5-agent-v2"},
           "options": {"seed": 7, "temperature": 0}, "model": "qwen3",
           "model_digest": "frozen", "base_url": "http://127.0.0.1:11437",
           "applies_to": {"parameter_set_sha256": "unchanged"}, "content_sha256": "old"}
    original = deepcopy(old)
    new = rr.migrate_runtime(old, tmp_path / "source")
    assert old == original
    assert {k for k in old if old[k] != new[k]} == {"q3_template", "q5_template", "content_sha256"}
    assert new["content_sha256"] == rr.digest(rr.canonical({k: v for k, v in new.items()
                                                          if k != "content_sha256"}))


def test_disk_gate_below_eight_gib_stops(monkeypatch, tmp_path):
    monkeypatch.setattr(rr, "command", lambda *a, **k: b"df -k receipt")
    monkeypatch.setattr(rr.shutil, "disk_usage", lambda p: SimpleNamespace(free=8 * 1024**3 - 1))
    with pytest.raises(ValueError, match="DISK_SPACE_BELOW_8_GIB"):
        rr.disk_receipt(tmp_path)


def test_endpoint_is_local_before_any_network_call():
    with pytest.raises(ValueError, match="PINNED_LOCAL_ENDPOINT"):
        rr.model_receipt({"base_url": "https://untrusted.invalid"})


def test_registry_migration_preserves_index_bytes_and_old_inputs(tmp_path):
    root = tmp_path / 'old'
    docs = {}
    for name in ('region', 'camera', 'index', 'records'):
        value = dict(schema_version='SYNTHETIC', content_sha256='original', name=name)
        p = write(root / (name + '.json'), value)
        docs[name] = dict(path=p.name, file_sha256=rr.file_digest(p), schema_version='SYNTHETIC')
    old = write(root / 'registry.json', dict(schema_version='q-demo.api-registry.v1',
        data_root=str(root), documents=docs, recordings=[], recording_root=None,
        runs=[dict(source_kind='SYNTHETIC', region_ref='region', camera_ref='camera')]))
    before = rr.inventory(list(root.iterdir()))

    def builder(region, camera):
        region['content_sha256'] = 'new-region'
        camera['content_sha256'] = 'new-camera'
        scope = dict(schema_version='q-demo.r004-tracking-scope.v3')
        return region, camera, scope, rr.canonical(scope)

    path, receipt = rr.migrate_registry(old, tmp_path / 'source', tmp_path / 'new', scope_builder=builder)
    doc = rr.load(path)
    assert doc['runs'][0]['tracking_scope_ref'] == 'tracking_scope_rc4'
    assert set(receipt['changed_documents']) == {'region', 'camera', 'tracking_scope_rc4'}
    for name in ('index', 'records'):
        assert (path.parent / (name + '.json')).read_bytes() == (root / (name + '.json')).read_bytes()
    rr.verify_inventory(before)


@pytest.mark.parametrize('kind', ['q1', 'q3-parse'])
@pytest.mark.parametrize('version', [1, 2])
def test_query_response_requires_nullable_scope_key(tmp_path, kind, version):
    root = tmp_path / kind
    response = dict(schema_version=f'q-demo.{kind}-response.v{version}', reasons=[])
    write(root / 'case.response.json', response)
    with pytest.raises(ValueError, match='FRESH_SCOPE_KEY_REQUIRED'):
        rr.validate_recording(root)
    response['resolved_scope'] = dict(tracking_scope_sha256=None)
    write(root / 'case.response.json', response)
    rr.validate_recording(root)


def test_q2_scope_pin_cannot_be_null_or_match_different_bytes(tmp_path):
    root = recording(tmp_path / 'recorded')
    response = rr.load(root / 'case.response.json')
    for pin in (None, 'a' * 64):
        response['resolved_scope']['tracking_scope_sha256'] = pin
        write(root / 'case.response.json', response)
        with pytest.raises(ValueError, match='FRESH_SCOPE_PIN_REQUIRED'):
            rr.validate_recording(root)


@pytest.mark.parametrize('kind', ['q1', 'q3-parse'])
@pytest.mark.parametrize('version', [1, 2])
def test_query_response_rejects_nonnull_scope_pin(tmp_path, kind, version):
    root = tmp_path / kind
    response = dict(schema_version=f'q-demo.{kind}-response.v{version}', reasons=[],
                    resolved_scope=dict(tracking_scope_sha256='a' * 64))
    write(root / 'case.response.json', response)
    with pytest.raises(ValueError, match='FRESH_QUERY_SCOPE_MUST_BE_NULL'):
        rr.validate_recording(root)


@pytest.mark.parametrize('version', [1, 2])
def test_q2_versioned_scope_and_decision_pins_are_always_checked(tmp_path, version):
    root = recording(tmp_path / 'recorded')
    response = rr.load(root / 'case.response.json')
    response['schema_version'] = f'q-demo.q2-response.v{version}'
    response['decisions_ref'] = 'decisions.jsonl'
    write(root / 'case.response.json', response)
    scope_pin = response['resolved_scope']['tracking_scope_sha256']
    write(root / 'decisions.jsonl', dict(input_pins=dict(tracking_scope_sha256=scope_pin)))
    assert rr.validate_recording(root)['link_v2_rows'] == 1
    write(root / 'decisions.jsonl', dict(input_pins=dict(tracking_scope_sha256='b' * 64)))
    with pytest.raises(ValueError, match='FRESH_DECISION_SCOPE_PIN_REQUIRED'):
        rr.validate_recording(root)
    response['resolved_scope']['tracking_scope_sha256'] = None
    write(root / 'case.response.json', response)
    with pytest.raises(ValueError, match='FRESH_SCOPE_PIN_REQUIRED'):
        rr.validate_recording(root)


def test_misspelled_q3_schema_no_longer_silently_skips_scope_check(tmp_path):
    root = tmp_path / 'q3'
    write(root / 'case.response.json', dict(schema_version='q-demo.q3-response.v1', reasons=[],
          resolved_scope=dict(tracking_scope_sha256=None)))
    with pytest.raises(ValueError, match='FRESH_RESPONSE_SCHEMA_REQUIRED'):
        rr.validate_recording(root)
