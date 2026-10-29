#!/usr/bin/env python3
"""Check #260's PROPOSED five-key receipt format; never grant runtime authority.

This offline checker does not load graphs, apply overlays, verify human identity,
fetch references, or adopt CQ-21a options. A valid format is not a G4 approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath

PAYLOAD_FIELDS = {
    "input_pins": (
        "scene_id", "scene_revision", "source_sha256", "catalog_sha256", "static_sha256",
        "region_graph_file_sha256", "region_graph_content_sha256", "camera_graph_file_sha256",
        "camera_graph_content_sha256", "tracking_scope_file_sha256", "run_camera_scopes",
    ),
    "edge_decisions": ("edge_id", "traversability", "state", "run_ids", "allowed_purposes"),
    "transition_decisions": (
        "transition_id", "from_camera_id", "to_camera_id", "via_exit_zone_ids",
        "to_entry_zone_ids", "region_path", "edge_path", "run_ids", "decision", "allowed_purposes",
    ),
    "region_purpose_decisions": (
        "region_id", "run_ids", "decision", "allowed_purposes", "exclusions",
    ),
    "derived_legal_transitions_by_run": ("run_id", "transition_ids"),
}
RUN_FIELDS = ("run_id", "camera_ids", "allowed_purposes", "exclusions")
TABLE_IDS = {
    "edge_decisions": "edge_id", "transition_decisions": "transition_id",
    "region_purpose_decisions": "region_id", "derived_legal_transitions_by_run": "run_id",
}
SCHEMA = "q-demo.g4-approval-receipt.v1"
HEADER = {
    "schema_version", "status", "date", "approval_ref", "human_decision_ref",
    "independent_review_ref", "decisions_sha256",
}
METADATA = {"approved_purposes", "exclusions", "provenance", "fixture_role"}
ROW_METADATA = {"recommendation", "yyin_opinion", "approval_ref", "human_decision_ref", "independent_review_ref"}


class ReceiptCheckError(ValueError):
    """Offline diagnostic only; this is not a new product error enum."""


def require(condition, message):
    if not condition:
        raise ReceiptCheckError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def parse_json(raw):
    def reject_constant(value):
        raise ReceiptCheckError("Non-finite JSON number: " + value)
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as exc:
        raise ReceiptCheckError("Malformed JSON") from exc
    require(isinstance(value, dict), "JSON object required")
    return value


def _text(value):
    return isinstance(value, str) and bool(value)


def _sha(value):
    return isinstance(value, str) and re.fullmatch("[0-9a-f]{64}", value) is not None


def _strings(value):
    require(isinstance(value, list) and all(_text(v) for v in value), "String array required")
    require(len(value) == len(set(value)), "Duplicate array value")


def _project(row, fields, metadata=()):
    require(isinstance(row, dict), "Object required")
    require(set(fields) <= row.keys() <= set(fields) | set(metadata), "Unknown or missing field")
    return {key: row[key] for key in fields}


def _table(rows, fields, identity):
    require(isinstance(rows, list), "Table array required")
    result = [_project(row, fields, ROW_METADATA) for row in rows]
    ids = [row[identity] for row in result]
    require(all(_text(v) for v in ids), "Table ID required")
    require(ids == sorted(set(ids)), "Table IDs must be unique and lexically sorted")
    for row in result:
        for key, value in row.items():
            if key in {"run_ids", "allowed_purposes", "exclusions", "transition_ids", "via_exit_zone_ids", "to_entry_zone_ids", "region_path", "edge_path"}:
                _strings(value)
            else:
                require(value is None or _text(value), "Text or explicit unresolved null required")
    return result


def decision_payload(doc):
    """Exact allowlist projection. Meaningful path arrays retain their direction."""
    pins = _project(doc.get("input_pins"), PAYLOAD_FIELDS["input_pins"])
    for key, value in pins.items():
        if key == "run_camera_scopes":
            continue
        require(value in (None, "UNKNOWN", "PENDING_USER") or (_sha(value) if key.endswith("sha256") else _text(value)), "Invalid input pin")
    require(isinstance(pins["run_camera_scopes"], list), "Run scope array required")
    scopes = [_project(row, RUN_FIELDS) for row in pins["run_camera_scopes"]]
    ids = [row["run_id"] for row in scopes]
    require(all(_text(v) for v in ids) and ids == sorted(set(ids)), "Run scopes must be unique and sorted")
    for row in scopes:
        for key in RUN_FIELDS[1:]:
            _strings(row[key])
    pins["run_camera_scopes"] = scopes
    payload = {"input_pins": pins}
    for name, identity in TABLE_IDS.items():
        payload[name] = _table(doc.get(name), PAYLOAD_FIELDS[name], identity)
    return payload


def decisions_sha256(doc):
    raw = json.dumps(decision_payload(doc), sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def check_receipt(receipt_raw, registry, *, receipt_relative_path):
    """Validate explicit bytes against existing documents pins; no file discovery."""
    doc = parse_json(receipt_raw)
    required = HEADER | PAYLOAD_FIELDS.keys()
    require(required <= doc.keys() <= required | METADATA, "Unknown or missing receipt field")
    require(doc["schema_version"] == SCHEMA, "Formal receipt schema required; drafts do not grant authority")
    require(doc["status"] == "APPROVED", "Receipt status is not APPROVED")
    require(_text(doc["date"]), "Receipt date required")
    for key in ("approval_ref", "human_decision_ref"):
        require(_text(doc[key]), "Approval references required; format does not prove human approval")
    require(doc["independent_review_ref"] is None or _text(doc["independent_review_ref"]), "Invalid review ref")
    require(_sha(doc["decisions_sha256"]) and decisions_sha256(doc) == doc["decisions_sha256"], "decisions_sha256 mismatch")
    relative = PurePosixPath(receipt_relative_path)
    require(not relative.is_absolute() and ".." not in relative.parts and "\\" not in receipt_relative_path, "Relative receipt path required")
    require(isinstance(registry, dict) and isinstance(registry.get("documents"), dict), "Registry documents map required")
    pins = [value for value in registry["documents"].values() if isinstance(value, dict) and value.get("path") == relative.as_posix()]
    require(len(pins) == 1, "Exactly one existing documents pin must address receipt")
    pin = pins[0]
    require(pin.get("schema_version") == SCHEMA, "Registry schema pin mismatch")
    require(_sha(pin.get("file_sha256")) and hashlib.sha256(receipt_raw).hexdigest() == pin["file_sha256"], "Registry receipt bytes pin mismatch")
    return {"format_valid": True, "authority_verified": False,
            "decisions_sha256": doc["decisions_sha256"],
            "receipt_file_sha256": hashlib.sha256(receipt_raw).hexdigest(),
            "note": "PROPOSED #260 format only; no overlay or trusted G4 verification performed"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        require(not args.receipt.is_symlink() and not args.registry.is_symlink(), "Symlink input forbidden")
        registry = parse_json(args.registry.read_bytes())
        relative = args.receipt.resolve().relative_to(args.registry.resolve().parent).as_posix()
        report = check_receipt(args.receipt.read_bytes(), registry, receipt_relative_path=relative)
    except (ReceiptCheckError, OSError, ValueError) as exc:
        print(json.dumps({"format_valid": False, "authority_verified": False, "diagnostic": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
