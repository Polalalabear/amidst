"""Explicit mechanical SYNTHETIC controls for the real registry/runtime path.

No provider calls, model discovery, GT, formal questions or expected answers.
"""

import argparse
import hashlib
import re
import sys
from dataclasses import asdict
from pathlib import Path

from amidst.q1q5.api import raw_json, sha
from amidst.q1q5.baseline_runner import save
from amidst.q1q5.llm_provider import LocalHTTPTransport
from amidst.q1q5.ollama_runtime import validate_config
from amidst.q1q5.store import canonical_hash


def generate(output, *, base_url, model_digest):
    root = Path(__file__).resolve().parents[1]
    output = Path(output)
    if not (
        output.is_absolute()
        and output.resolve() == output
        and not output.exists()
        and output.parent.is_dir()
        and not output.is_relative_to(root)
    ):
        raise ValueError("NEW_EXTERNAL_CANONICAL_OUTPUT")
    if not re.fullmatch("[0-9a-f]{64}", model_digest):
        raise ValueError("EXPLICIT_REAL_MODEL_DIGEST_REQUIRED")
    LocalHTTPTransport(base_url)  # Validate loopback only; performs zero HTTP.
    sys.path.insert(0, str(root / "tests/q1q5"))
    from test_baseline_runner import control_case, fixture_api
    from test_ollama_runtime import config

    from amidst.q1q5.q5_controller import jsonl

    api, _, _ = fixture_api()
    run = next(iter(api.runs.values()))
    b = run.bindings
    output.mkdir(mode=0o700)
    documents = {}

    def document(ref, value):
        raw = raw_json(value)
        save(output / (ref + ".json"), raw)
        documents[ref] = dict(
            path=ref + ".json",
            file_sha256=sha(raw),
            schema_version=value["schema_version"],
            content_sha256=value.get("content_sha256"),
        )

    document("index", b.index.manifest)
    records = jsonl(b.index.records)
    save(output / b.index.manifest["records_ref"], records)
    documents["records"] = dict(
        path=b.index.manifest["records_ref"],
        file_sha256=sha(records),
        schema_version="q-demo.detection-record.v1",
    )
    for ref, doc in [
        ("clock", dict(b.clock.document)),
        ("region", b.graphs.region),
        ("camera", b.graphs.camera),
        ("parameter", b.parameter_set),
        ("aliases", run.aliases),
    ]:
        document(ref, doc)
    scope_raw = b.graphs.tracking_scope_bytes
    if scope_raw is None:
        raise ValueError("TRACKING_SCOPE_BYTES_REQUIRED")
    save(output / "tracking_scope.json", scope_raw)
    documents["tracking_scope"] = dict(
        path="tracking_scope.json", file_sha256=sha(scope_raw),
        schema_version="q-demo.r004-tracking-scope.v3",
    )
    catalog = dict(schema_version="q-demo.parse-catalog.v1", **run.catalog)
    catalog["content_sha256"] = canonical_hash(catalog)
    document("catalog", catalog)
    registry = dict(
        schema_version="q-demo.api-registry.v1",
        data_root=str(output),
        documents=documents,
        runs=[
            dict(
                index_ref="index",
                clock_ref="clock",
                region_ref="region",
                camera_ref="camera",
                tracking_scope_ref="tracking_scope",
                parameter_ref="parameter",
                aliases_ref="aliases",
                catalog_ref="catalog",
                parse_settings=asdict(run.parse_settings),
                media_ranges_by_camera=b.media_ranges_by_camera,
                media_scope_sha256=b.media_scope_sha256,
                source_kind="SYNTHETIC",
            )
        ],
        recording_root=None,
        recordings=[],
        limits=dict(max_responses=128, max_media_refs=4096, max_recording_bytes=4_000_000),
    )
    registry["content_sha256"] = canonical_hash(registry)
    save(output / "registry.json", registry)
    runtime = config(run)
    runtime.update(base_url=base_url, model_digest=model_digest)
    for role, filename, version in [
        ("q3", "q3_parse_v2.txt", "q3-parse.v2"),
        ("q5", "q5_agent_v2.txt", "q5-agent-v2"),
    ]:
        text = (root / "configs/q1q5/prompts" / filename).read_text()
        runtime[role + "_template"] = dict(
            text=text, sha256=hashlib.sha256(text.encode()).hexdigest(), version=version
        )
    runtime["content_sha256"] = canonical_hash(runtime, exclude=("content_sha256",))
    validate_config(runtime)
    save(output / "runtime.json", runtime)
    rows = [control_case(api, task=task) for task in ("ONCE_SEARCH", "CONTINUOUS_PURSUIT")]
    save(output / "cases.jsonl", b"".join(raw_json(row) + b"\n" for row in rows))
    return {
        "status": "COMPLETE",
        "source_kind": "SYNTHETIC",
        "formal_questions": 0,
        "provider_calls": 0,
        "model_digest_observed_by_generator": False,
        "files": {p.name: sha(p.read_bytes()) for p in output.iterdir() if p.is_file()},
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "base-url", "model-digest"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args(argv)
    report = generate(Path(args.output), base_url=args.base_url, model_digest=args.model_digest)
    print(raw_json(report).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
