"""Server-owned timeout profile bound to the existing pinned local provider."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any


def load_agent_transport(base_path: Path, profile_path: Path
                         ) -> tuple[dict[str, Any], dict[str, Any]]:
    if base_path.is_symlink() or profile_path.is_symlink():
        raise ValueError("AGENT_TRANSPORT_PROFILE_DENIED")
    base_bytes = base_path.read_bytes()
    base = json.loads(base_bytes)
    if not isinstance(base, dict):
        raise ValueError("AGENT_TRANSPORT_PROFILE_DENIED")
    base_sha = hashlib.sha256(base_bytes).hexdigest()
    timeout = base.get("timeout_seconds", 120)
    config = dict(base)
    profile_sha: str | None = None
    if profile_path.exists():
        profile_bytes = profile_path.read_bytes()
        profile = json.loads(profile_bytes)
        if (not isinstance(profile, dict)
            or set(profile) != {"schema_version", "base_provider_sha256", "timeout_seconds"}
            or profile["schema_version"] != "phase2.agent.transport.v1"
            or profile["base_provider_sha256"] != base_sha):
            raise ValueError("AGENT_TRANSPORT_PROFILE_DENIED")
        timeout = profile["timeout_seconds"]
        config["timeout_seconds"] = timeout
        profile_sha = hashlib.sha256(profile_bytes).hexdigest()
    if (type(timeout) not in {int, float} or not math.isfinite(timeout)
        or not 1 <= timeout <= 180):
        raise ValueError("AGENT_TRANSPORT_PROFILE_DENIED")
    encoded = json.dumps(config, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return config, {
        "schema_version": "phase2.agent.transport.v1",
        "status": "VERIFIED_PROFILE" if profile_sha else "BASE_CONFIGURATION",
        "base_provider_sha256": base_sha,
        "effective_config_sha256": hashlib.sha256(encoded).hexdigest(),
        "profile_sha256": profile_sha,
        "timeout_seconds": timeout,
        "client_configurable": False,
        "automatic_retries": False,
    }
