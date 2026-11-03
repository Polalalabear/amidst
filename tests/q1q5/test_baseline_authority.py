"""SYNTHETIC receipt bytes exercise gates; they authorize no real dataset."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_api import run_binding

from amidst.q1q5.baseline_authority import load_authority, verify_questions
from amidst.q1q5.baseline_runner import load_plan, selected_run
from amidst.q1q5.store import canonical_hash


def write(path, doc):
    path.write_text(json.dumps(doc))
    return dict(path=str(path), file_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def setup(tmp_path):
    public = write(
        tmp_path / "public.json",
        dict(
            schema_version="q-demo.reviewed-q3-public.v1",
            questions=[dict(id=str(i), text="SYNTHETIC HUMAN CONTROL " + str(i)) for i in range(8)],
        ),
    )
    pins = {k: "a" * 64 for k in ["protocol", "cases", "composition", "registry", "runtime"]}
    scope = dict(source_kind="FORMAL_R004", input_pins=pins, public_questions=public)
    protocol = json.loads(
        (
            Path(__file__).resolve().parents[2] / "configs/q1q5/baseline_v1_protocol.json"
        ).read_bytes()
    )
    receipts = []
    for n, gate in enumerate(protocol["formal_run"]["required_gates"]):
        receipts.append(
            write(
                tmp_path / f"receipt-{n}.json",
                dict(
                    gate=gate,
                    decision="APPROVED",
                    scope_sha256=canonical_hash(scope),
                    reviewer="Human test fixture",
                    reviewed_at="2026-10-24T00:00:00+08:00",
                    review_kind="INDEPENDENT_HUMAN",
                    predictions_seen=False,
                ),
            )
        )
    doc = dict(schema_version="q-demo.baseline-freeze-authority.v1", scope=scope, receipts=receipts)
    return doc, pins, protocol


def load(tmp_path, doc, pins, permit=True):
    ref = write(tmp_path / "authority.json", doc)
    return load_authority(ref["path"], ref["file_sha256"], permit=permit, input_pins=pins)


def test_complete_scoped_receipts_and_explicit_permission_required(tmp_path):
    doc, pins, protocol = setup(tmp_path)
    with pytest.raises(ValueError, match="PERMISSION"):
        load(tmp_path, doc, pins, False)
    protocol["status"] = "FROZEN"
    protocol["formal_run"]["allowed"] = True
    ref = write(tmp_path / "protocol.json", protocol)
    pins["protocol"] = ref["file_sha256"]
    doc["scope"]["input_pins"] = pins
    scope_hash = canonical_hash(doc["scope"])
    for n, old in enumerate(doc["receipts"]):
        receipt = json.loads(Path(old["path"]).read_bytes())
        receipt["scope_sha256"] = scope_hash
        doc["receipts"][n] = write(Path(old["path"]), receipt)
    authority = load(tmp_path, doc, pins)
    assert load_plan(ref["path"], ref["file_sha256"], engineering=False, authority=authority)
    with pytest.raises(ValueError):
        load_plan(ref["path"], ref["file_sha256"], engineering=False)
    cases = [
        dict(query=dict(kind="TEXT", question_id=str(i), text="SYNTHETIC HUMAN CONTROL " + str(i)))
        for i in range(8)
    ]
    verify_questions(cases, authority)
    cases[0]["query"]["text"] = "changed"
    with pytest.raises(ValueError, match="QUESTION"):
        verify_questions(cases, authority)


@pytest.mark.parametrize(
    "change", ["missing", "scope", "duplicate", "synthetic", "pins", "predictions"]
)
def test_missing_scope_duplicate_or_self_claim_cannot_unlock(tmp_path, change):
    doc, pins, _ = setup(tmp_path)
    if change == "missing":
        doc["receipts"].pop()
    elif change == "duplicate":
        doc["receipts"][-1] = deepcopy(doc["receipts"][0])
    elif change == "pins":
        pins = {**pins, "cases": "b" * 64}
    else:
        ref = doc["receipts"][0]
        receipt = json.loads(Path(ref["path"]).read_bytes())
        if change == "scope":
            receipt["scope_sha256"] = "c" * 64
        elif change == "synthetic":
            receipt["reviewer"] = "SYNTHETIC"
        else:
            receipt["predictions_seen"] = True
        doc["receipts"][0] = write(Path(ref["path"]), receipt)
    with pytest.raises(ValueError):
        load(tmp_path, doc, pins)


def test_direct_formal_run_without_authority_remains_blocked():
    run = run_binding()

    class API:
        runs = {1: run}

    with pytest.raises(ValueError, match="INDEPENDENT_FREEZE"):
        selected_run(API(), dict(run_id=run.catalog["run_id"], data_kind="FORMAL_R004"))
