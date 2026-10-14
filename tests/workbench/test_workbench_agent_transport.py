"""Transport tuning cannot rebind the model or accept browser configuration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from amidst.local_agent.provider import OllamaProvider
from amidst.workbench.agent_transport import load_agent_transport
from amidst.workbench.phase2_suite import SuiteRequest


@pytest.fixture
def settings(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    config = {"endpoint": "http://127.0.0.1:11437", "model": "qwen2.5:7b-instruct",
              "model_digest": "a" * 64, "context_tokens": 8192, "timeout_seconds": 120}
    base = tmp_path / "provider.json"
    base.write_text(json.dumps(config))
    profile = tmp_path / "transport.json"
    return base, profile, config


def profile_value(base: Path, **overrides: Any) -> dict[str, Any]:
    return {"schema_version": "phase2.agent.transport.v1",
            "base_provider_sha256": hashlib.sha256(base.read_bytes()).hexdigest(),
            "timeout_seconds": 180} | overrides


def test_bound_profile_changes_only_timeout_and_preserves_original_bytes(settings: Any) -> None:
    base, profile, original = settings
    before, stamp = base.read_bytes(), base.stat().st_mtime_ns
    profile.write_text(json.dumps(profile_value(base)))
    config, proof = load_agent_transport(base, profile)
    assert config == original | {"timeout_seconds": 180}
    provider = OllamaProvider(**config)
    assert provider.timeout == 180
    assert provider.configured_identity()["model_digest"] == original["model_digest"]
    assert provider.configured_identity()["context_tokens"] == 8192
    assert proof["status"] == "VERIFIED_PROFILE"
    assert proof["automatic_retries"] is proof["client_configurable"] is False
    assert base.read_bytes() == before and base.stat().st_mtime_ns == stamp
    assert set(proof).isdisjoint({"endpoint", "password", "dsn", "owner_key"})


def test_absent_profile_retains_existing_configuration(settings: Any) -> None:
    base, profile, original = settings
    config, proof = load_agent_transport(base, profile)
    assert config == original
    assert proof["status"] == "BASE_CONFIGURATION"
    assert proof["timeout_seconds"] == 120 and proof["profile_sha256"] is None


@pytest.mark.parametrize("extra", [
    {"endpoint": "http://remote.invalid"}, {"model": "other"}, {"context_tokens": 4096},
    {"dsn": "private"}, {"schema_version": "wrong"}, {"base_provider_sha256": "b" * 64},
])
def test_profile_rejects_rebinding_and_stale_configuration(settings: Any, extra: Any) -> None:
    base, profile, _ = settings
    profile.write_text(json.dumps(profile_value(base, **extra)))
    with pytest.raises(ValueError, match="AGENT_TRANSPORT_PROFILE_DENIED"):
        load_agent_transport(base, profile)


@pytest.mark.parametrize("timeout", [True, "180", 0, 181, float("nan"), float("inf")])
def test_invalid_or_unbounded_timeout_is_rejected(settings: Any, timeout: Any) -> None:
    base, profile, _ = settings
    profile.write_text(json.dumps(profile_value(base, timeout_seconds=timeout)))
    with pytest.raises(ValueError, match="AGENT_TRANSPORT_PROFILE_DENIED"):
        load_agent_transport(base, profile)


@pytest.mark.parametrize("target", ["base", "profile", "dangling_profile"])
def test_symlink_profile_or_base_is_rejected(settings: Any, target: str) -> None:
    base, profile, _ = settings
    actual = base.with_name("actual.json")
    actual.write_text(json.dumps(profile_value(base)))
    if target == "base":
        base.unlink()
        base.symlink_to(actual)
    else:
        profile.symlink_to(actual if target == "profile" else actual.with_name("missing.json"))
    with pytest.raises(ValueError, match="AGENT_TRANSPORT_PROFILE_DENIED"):
        load_agent_transport(base, profile)


@pytest.mark.parametrize("field", ["timeout_seconds", "transport_profile", "provider_config"])
def test_browser_cannot_choose_transport_profile(field: str) -> None:
    with pytest.raises(ValidationError):
        SuiteRequest.model_validate({"session_ref": "owner", "scene_id": "scene", field: 180})
