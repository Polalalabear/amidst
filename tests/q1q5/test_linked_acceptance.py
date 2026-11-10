"""Reproduction and lifecycle controls, no live model or external network."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

from amidst.q1q5.linked_acceptance import (
    child,
    environment,
    recipe,
    service_snapshot,
    verify_service,
)

ROOT = Path(__file__).resolve().parents[2]


def test_environment_no_install_and_explicit_versions():
    doc = json.loads((ROOT / "configs/q1q5/linked_baseline_environment.json").read_bytes())
    assert (
        environment(doc, version=lambda name: doc["packages"][name])["packages"] == doc["packages"]
    )
    with pytest.raises(ValueError, match="NO_INSTALL"):
        environment(doc, version=lambda _: "different")


def test_service_read_scope_and_digest_rejection_before_calls():
    expected = dict(ollama_version="0", model="qwen3:1.7b-q4_K_M", model_digest="a" * 64)
    runtime = dict(
        base_url="http://127.0.0.1:11437", model=expected["model"], model_digest="a" * 64
    )
    calls = []

    def fetch(path):
        calls.append(path)
        return {
            "/api/version": {"version": "0"},
            "/api/tags": {"models": [{"name": runtime["model"], "digest": "a" * 64}]},
            "/api/ps": {"models": []},
        }[path]

    observed = service_snapshot(runtime["base_url"], fetch=fetch)
    verify_service(observed, expected, runtime)
    assert calls == ["/api/version", "/api/tags", "/api/ps"]
    observed["tags"]["models"][0]["digest"] = "b" * 64
    with pytest.raises(ValueError, match="DIGEST"):
        verify_service(observed, expected, runtime)
    with pytest.raises(ValueError):
        service_snapshot("https://external.example", fetch=fetch)


def test_recipe_permission_before_input_or_model_access(tmp_path):
    with pytest.raises(ValueError, match="PERMISSION"):
        recipe(ROOT, {}, tmp_path / "missing.json", "0" * 64, tmp_path / "out", permit=False)
    assert not (tmp_path / "out").exists()


def test_owned_child_success_and_failure_keep_resource_evidence(tmp_path):
    child([sys.executable, "-c", 'print("SYNTHETIC")'], root=tmp_path, logs=tmp_path / "good")
    row = json.loads((tmp_path / "good.resources.json").read_bytes())
    assert row["child_returncode"] == 0 and row["processes"]["sample_interval_s"] == 0.1
    assert row["runners"]["physical_vram_peak_bytes"] is None
    with pytest.raises(ValueError, match="CHILD_FAILED"):
        child([sys.executable, "-c", "raise SystemExit(2)"], root=tmp_path, logs=tmp_path / "bad")
    assert json.loads((tmp_path / "bad.resources.json").read_bytes())["child_returncode"] == 2


def test_owned_timeout_only_stops_new_session_and_keeps_receipt(tmp_path):
    with pytest.raises(ValueError, match="OWNED_WORKER_TIMEOUT"):
        child(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            root=tmp_path,
            logs=tmp_path / "slow",
            timeout_s=0.05,
        )
    raw = (tmp_path / "slow.resources.json").read_bytes()
    assert len(hashlib.sha256(raw).hexdigest()) == 64
