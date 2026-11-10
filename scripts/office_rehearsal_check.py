"""Bounded launcher readiness receipt; no asset writes or service lifecycle changes."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path


class Audit:
    def __init__(self):
        self.checks = {}
        self.active = None
        for name in (
            "preflight",
            "managed_record",
            "process_identity_listener",
            "source_fingerprint",
            "launcher_metadata",
            "preset_catalog",
            "person_api:target_reconstruction",
            "person_api:frame_retrieval",
        ):
            self.checks[name] = {"status": "UNKNOWN", "detail": "NOT_RUN"}

    def begin(self, name):
        self.active = name
        self.checks[name] = {"status": "UNKNOWN", "detail": "NOT_COMPLETED"}

    def passed(self, detail=None):
        self.checks[self.active] = {"status": "PASS", "detail": detail}

    def failed(self, detail):
        self.checks[self.active] = {"status": "FAIL", "detail": str(detail)}

    def unknown(self, detail):
        self.checks[self.active] = {"status": "UNKNOWN", "detail": detail}


def output_target(path, launcher):
    """Validate before creating anything; resolve parent aliases, never overwrite."""
    path = path.expanduser().absolute()
    resolved = path.resolve()
    protected = [launcher.ASSETS.resolve(), launcher.EVIDENCE.resolve(), launcher.REPO.resolve()]
    if launcher.BUNDLE is not None:
        protected.append(launcher.BUNDLE.resolve())
    if any(resolved.is_relative_to(root) for root in protected):
        raise ValueError("REHEARSAL_OUTPUT_IN_REPOSITORY_OR_ASSETS")
    if any(part.lower() in {"gt", "ground_truth", "ground-truth"} for part in resolved.parts):
        raise ValueError("REHEARSAL_OUTPUT_IN_GT")
    if path.exists() or path.is_symlink():
        raise ValueError("REHEARSAL_OUTPUT_ALREADY_EXISTS")
    if not path.parent.is_dir():
        raise ValueError("REHEARSAL_OUTPUT_PARENT_MISSING")
    return resolved


def artifact_hashes(launcher, audit):
    """Only allowlisted manifests, safe inputs, bound indexes and frozen responses."""
    from office_demo_backend import preset_specs

    artifacts = []

    def add(kind, path, expected=None):
        path = Path(path)
        audit.begin("hash:" + kind + ":" + str(path))
        row = {"kind": kind, "path": str(path), "sha256": None, "expected_sha256": expected}
        artifacts.append(row)
        try:
            if path.is_symlink():
                raise ValueError("ARTIFACT_SYMLINK_REJECTED")
            row["sha256"] = launcher.digest(path)
            if expected is not None and row["sha256"] != expected:
                raise ValueError("ARTIFACT_HASH_MISMATCH")
            audit.passed({"sha256": row["sha256"], "expected_checked": expected is not None})
        except FileNotFoundError:
            audit.unknown("ARTIFACT_UNAVAILABLE")
        except (OSError, ValueError) as error:
            audit.failed(type(error).__name__ + ":" + str(error))
        return row

    audit.begin("artifact_catalog")
    try:
        _, specs = preset_specs(
            launcher.PRESETS, launcher.EVIDENCE, launcher.ASSETS, launcher.BUNDLE
        )
        audit.passed()
    except (OSError, ValueError, KeyError, TypeError) as error:
        audit.failed(type(error).__name__ + ":" + str(error))
        return artifacts
    for spec in specs:
        add("bundle_manifest:" + spec["scene_id"], spec["bundle_path"] / "manifest.json")
        add(
            "bundle_safe_inputs:" + spec["scene_id"],
            spec["bundle_path"] / "safe_inputs.json",
            (spec.get("config") or {}).get("safe_inputs_sha256"),
        )
        if spec.get("hypothesis_binding"):
            binding_path = launcher.REPO / spec["hypothesis_binding"]
            add("hypothesis_binding", binding_path)
            audit.begin("index_binding:" + spec["scene_id"])
            try:
                binding = json.loads(binding_path.read_bytes())
                index = (launcher.REPO / binding["visibility_index"]).resolve()
                if not index.is_relative_to(launcher.REPO):
                    raise ValueError("INDEX_PATH_OUTSIDE_REPOSITORY")
                audit.passed()
                add("visibility_index", index, binding["visibility_index_sha256"])
            except (OSError, ValueError, KeyError, TypeError) as error:
                audit.failed(type(error).__name__ + ":" + str(error))
    # Original frozen artifacts only: never regenerate a response or read evaluation GT.
    for name in ("C5_PERSON_K1_SYNC_D19_20261017.json.gz", "C5_K8A_PRESYNC_REAL_20261017.json.gz"):
        path = launcher.REPO / "docs/engineering" / name
        if path.exists() or name.startswith("C5_PERSON_K1"):
            add("frozen_response", path)
    return artifacts


def rehearsal_check(launcher, output):
    output = output_target(output, launcher)
    audit = Audit()
    report = {
        "schema_version": "office-demo.rehearsal-check.v1",
        "created_at": datetime.now(UTC).isoformat(),
        "scope": "LOCAL_READINESS_ONLY",
        "repo": str(launcher.REPO),
        "source": {},
        "managed_service": None,
    }
    try:
        audit.begin("preflight")
        config = launcher.preflight()
        report["source"] = config
        audit.passed()
        audit.begin("managed_record")
        path = launcher.RUNTIME / "runtime.json"
        if launcher.RUNTIME.is_symlink() or path.is_symlink():
            raise ValueError("RUNTIME_SYMLINK_REJECTED")
        if not path.is_file():
            audit.unknown("NO_MANAGED_SERVICE")
        else:
            record = json.loads(path.read_bytes())
            report["managed_service"] = {key: record.get(key) for key in ("pid", "url", "head")}
            audit.passed()
            launcher.readiness(record, config, audit=audit)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        ImportError,
        RuntimeError,
        launcher.subprocess.SubprocessError,
    ) as error:
        audit.failed(type(error).__name__ + ":" + str(error))
    report["artifacts"] = artifact_hashes(launcher, audit)
    report["checks"] = [{"check": key, **value} for key, value in audit.checks.items()]
    statuses = {value["status"] for value in audit.checks.values()}
    report["status"] = (
        "FAIL" if "FAIL" in statuses else "UNKNOWN" if "UNKNOWN" in statuses else "PASS"
    )
    body = (
        json.dumps(report, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()
    # O_EXCL also closes the check/write race; O_NOFOLLOW rejects a raced symlink.
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(body)
    for row in report["checks"]:
        print(f"{row['status']} {row['check']}", flush=True)
    print(
        f"REHEARSAL_CHECK={report['status']} RECEIPT={output} "
        f"SHA256={hashlib.sha256(body).hexdigest()}",
        flush=True,
    )
    return 0 if report["status"] == "PASS" else 2 if report["status"] == "UNKNOWN" else 1
