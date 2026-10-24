"""Re-execute pinned engineering recordings with all socket connections denied."""

import argparse
import os
import socket
from dataclasses import replace
from pathlib import Path

from amidst.q1q5.api import RecordingStore, from_environment
from amidst.q1q5.baseline_runner import replay_kernel, save, verify_composition
from amidst.q1q5.production_preflight import read_pinned, strict_json


def read(ref):
    if set(ref) != {"path", "file_sha256"}:
        raise ValueError("PINNED_REF_REQUIRED")
    return strict_json(read_pinned(Path(ref["path"]), ref["file_sha256"]))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", type=Path, required=True)
    p.add_argument("--config-sha256", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if (
        not a.output.is_absolute()
        or a.output.resolve() != a.output
        or not a.output.parent.is_dir()
        or a.output.exists()
    ):
        raise ValueError("NEW_CANONICAL_OUTPUT_REQUIRED")
    config = read(dict(path=str(a.config), file_sha256=a.config_sha256))
    if (
        set(config)
        != {"schema_version", "source_root", "composition", "registry", "runtime", "samples"}
        or a.output.is_relative_to(Path(config["source_root"]))
        or config["schema_version"] != "q-demo.dynamic-offline-replay.v1"
        or not 1 <= len(config["samples"]) <= 128
    ):
        raise ValueError("BOUNDED_REPLAY_CONFIG_REQUIRED")
    verify_composition(
        Path(config["composition"]["path"]),
        config["composition"]["file_sha256"],
        config["source_root"],
    )
    attempts = []

    def deny(*args, **kwargs):
        attempts.append("SOCKET_CONNECT_DENIED")
        raise RuntimeError("OFFLINE_REPLAY_NETWORK_FORBIDDEN")

    # This new process only; the shared Ollama service is never touched.
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    for name, ref in [("REGISTRY", config["registry"]), ("OLLAMA_RUNTIME", config["runtime"])]:
        read(ref)
        os.environ["AMIDST_Q1Q5_" + name] = ref["path"]
        os.environ["AMIDST_Q1Q5_" + name + "_SHA256"] = ref["file_sha256"]
    api = from_environment(None, Path(config["source_root"]))
    rows = []
    for item in config["samples"]:
        if set(item) != {
            "case_id",
            "stage",
            "recording_root",
            "descriptor",
            "expected_output_sha256",
            "switch_mode",
            "selected_observation_id",
            "request",
        } or item["switch_mode"] not in {"RULE_ONLY", "AGENT_SEQUENTIAL"}:
            raise ValueError("REPLAY_SAMPLE_FIELDS")
        store = RecordingStore(
            Path(item["recording_root"]),
            repo_root=Path(config["source_root"]),
            max_bytes=16_777_216,
        )
        bundle = store.load(read(item["descriptor"]))
        if bundle["response"]["output_sha256"] != item["expected_output_sha256"]:
            raise ValueError("RECORDING_OUTPUT_PIN_MISMATCH")
        request = read(item["request"])
        if {k: v for k, v in request.items() if k != "session_ref"} != bundle["request"]:
            raise ValueError("RECORDED_REQUEST_PIN_MISMATCH")
        run = next(
            r
            for r in api.runs.values()
            if [r.catalog["run_id"]] == bundle["response"]["resolved_scope"]["run_ids"]
        )
        run = replace(
            run, parse_settings=replace(run.parse_settings, switch_mode=item["switch_mode"])
        )
        result = replay_kernel(
            bundle,
            request,
            run,
            item["selected_observation_id"],
            lambda *args, **kwargs: None,
        )
        rows.append(dict(case_id=item["case_id"], stage=item["stage"], **result))
    if attempts or any(row["status"] != "PASS" for row in rows):
        raise ValueError("OFFLINE_REPLAY_FAILED")
    save(
        a.output,
        dict(
            schema_version="q-demo.dynamic-offline-replay-result.v1",
            status="PASS",
            samples=len(rows),
            network_connect_attempts=len(attempts),
            live_provider_calls=0,
            rows=rows,
        ),
    )
    print(f"PASS {len(rows)} stage replays; socket connections={len(attempts)}")


if __name__ == "__main__":
    main()
