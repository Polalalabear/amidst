#!/usr/bin/env python3
"""Replay pinned timeout requests for CX-6 diagnostics; never score a baseline.

Generation has no client timeout and num_predict=-1. Everything else in the
historical wire request is preserved. Raw requests/responses are LOCAL artifacts.
The schema checker deliberately supports only this frozen question set's subset
of JSON Schema; unsupported keywords fail before any network call.
"""

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
from pathlib import Path
import re
import shutil
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


MIN_FREE_BYTES = 8 * 1024**3
ALLOWED_ROUTES = {"/api/tags", "/api/chat", "/api/version", "/api/ps"}
SCHEMA_KEYS = {"type", "enum", "const", "properties", "required",
               "additionalProperties", "items", "minItems", "maxItems",
               "minLength", "anyOf", "oneOf"}


class DiagnosticError(ValueError):
    """Messages are fixed codes, safe to include in public metadata."""


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise DiagnosticError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def bad_constant(_):
        raise DiagnosticError("NONFINITE_JSON")

    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise DiagnosticError("NONFINITE_JSON")
        if isinstance(value, dict):
            for child in value.values():
                finite(child)
        elif isinstance(value, list):
            for child in value:
                finite(child)

    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise DiagnosticError("INVALID_JSON") from exc
    finite(result)
    return result


def contained_path(root, locator):
    root = Path(root).resolve(strict=True)
    value = Path(locator)
    candidate = value if value.is_absolute() else root / value
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (ValueError, OSError, RuntimeError) as exc:
        raise DiagnosticError("INPUT_PATH_OUTSIDE_ROOT_OR_MISSING") from exc
    if not resolved.is_file():
        raise DiagnosticError("INPUT_NOT_FILE")
    # Even an in-root symlink is unnecessary for the frozen provenance chain.
    current = candidate.absolute()
    while current != root and root in current.parents:
        if current.is_symlink():
            raise DiagnosticError("INPUT_SYMLINK")
        current = current.parent
    return resolved


def read_pinned(root, locator, expected):
    if not isinstance(expected, str) or re.fullmatch("[0-9a-f]{64}", expected) is None:
        raise DiagnosticError("INVALID_SHA256")
    path = contained_path(root, locator)
    raw = path.read_bytes()
    if sha256(raw) != expected:
        raise DiagnosticError("INPUT_HASH_MISMATCH")
    return path, raw, strict_json(raw)


def json_equal(a, b):
    if type(a) is bool or type(b) is bool:
        return type(a) is type(b) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(json_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(json_equal(x, y) for x, y in zip(a, b))
    return a == b


def check_schema(schema):
    if not isinstance(schema, dict) or set(schema) - SCHEMA_KEYS:
        raise DiagnosticError("UNSUPPORTED_SCHEMA_KEYWORD")
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not types or any(t not in {"object", "array", "string", "boolean", "null", "number", "integer"} for t in types):
            raise DiagnosticError("INVALID_SCHEMA_TYPE")
    if "enum" in schema and (not isinstance(schema["enum"], list) or not schema["enum"]):
        raise DiagnosticError("INVALID_SCHEMA_ENUM")
    for key in ("minItems", "maxItems", "minLength"):
        if key in schema and (type(schema[key]) is not int or schema[key] < 0):
            raise DiagnosticError("INVALID_SCHEMA_BOUND")
    if "required" in schema and (not isinstance(schema["required"], list)
            or any(not isinstance(k, str) for k in schema["required"])):
        raise DiagnosticError("INVALID_SCHEMA_REQUIRED")
    if "additionalProperties" in schema and type(schema["additionalProperties"]) is not bool:
        raise DiagnosticError("UNSUPPORTED_ADDITIONAL_PROPERTIES_SCHEMA")
    if "properties" in schema:
        if not isinstance(schema["properties"], dict):
            raise DiagnosticError("INVALID_SCHEMA_PROPERTIES")
        for child in schema["properties"].values():
            check_schema(child)
    if "items" in schema:
        check_schema(schema["items"])
    for key in ("anyOf", "oneOf"):
        if key in schema:
            if not isinstance(schema[key], list) or not schema[key]:
                raise DiagnosticError("INVALID_SCHEMA_BRANCHES")
            for child in schema[key]:
                check_schema(child)


def schema_valid(value, schema):
    def has_type(name):
        return {"object": isinstance(value, dict), "array": isinstance(value, list),
                "string": isinstance(value, str), "boolean": type(value) is bool,
                "null": value is None, "number": type(value) in (int, float),
                "integer": type(value) in (int, float) and value == int(value)}[name]

    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(has_type(name) for name in types):
            return False
    if "const" in schema and not json_equal(value, schema["const"]):
        return False
    if "enum" in schema and not any(json_equal(value, item) for item in schema["enum"]):
        return False
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", [])):
            return False
        if schema.get("additionalProperties") is False and set(value) - properties.keys():
            return False
        if any(not schema_valid(child, properties[key]) for key, child in value.items() if key in properties):
            return False
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0) or len(value) > schema.get("maxItems", len(value)):
            return False
        if "items" in schema and any(not schema_valid(child, schema["items"]) for child in value):
            return False
    if isinstance(value, str) and len(value) < schema.get("minLength", 0):
        return False
    if "anyOf" in schema and not any(schema_valid(value, child) for child in schema["anyOf"]):
        return False
    if "oneOf" in schema and sum(schema_valid(value, child) for child in schema["oneOf"]) != 1:
        return False
    return True


def pointer(value, location):
    if not isinstance(location, str) or not location.startswith("/"):
        raise DiagnosticError("INVALID_RECORD_POINTER")
    try:
        for part in location[1:].split("/"):
            part = part.replace("~1", "/").replace("~0", "~")
            value = value[int(part)] if isinstance(value, list) else value[part]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise DiagnosticError("RECORD_POINTER_MISSING") from exc
    return value


def load_cases(inputs, inputs_sha256, baseline_result, baseline_result_sha256, artifacts_root):
    root = Path(artifacts_root).resolve(strict=True)
    input_path, _, config = read_pinned(root, inputs, inputs_sha256)
    result_path, _, baseline = read_pinned(root, baseline_result, baseline_result_sha256)
    files = {}
    input_refs = []
    for row in config["files"]:
        path, _, data = read_pinned(root, row["path"], row["sha256"])
        files.setdefault(row["sha256"], []).append((path, data))
        input_refs.append({"path": path.relative_to(root).as_posix(), "sha256": row["sha256"]})
    if Counter(baseline["source_file_hashes"]) != Counter(row["sha256"] for row in config["files"]):
        raise DiagnosticError("BASELINE_SOURCE_HASH_SET_MISMATCH")
    rows = baseline["calls"]
    if config["expected_calls"] != 18 or len(rows) != 18 or [r["number"] for r in rows] != list(range(1, 19)):
        raise DiagnosticError("EXPECTED_EIGHTEEN_ORDERED_CALLS")
    if Counter(row["stage"] for row in rows) != {"q3": 12, "q5": 6}:
        raise DiagnosticError("QUESTION_STAGE_COUNTS_MISMATCH")
    cases = []
    pins = set()
    for row in rows:
        candidates = files.get(row["recording_sha256"], [])
        if not candidates:
            raise DiagnosticError("RECORDING_NOT_PINNED")
        path, data = candidates[0]
        record = pointer(data["q3_provider_audit"] if row["stage"] == "q3" else data["agent_trace"], row["record_location"])
        wire = record["wire_request"]
        if (not isinstance(wire, dict) or set(wire) - {"model", "messages", "format", "options", "stream", "think", "keep_alive"}
                or wire.get("stream") is not False or not isinstance(wire.get("options"), dict)
                or not isinstance(wire.get("messages"), list) or not wire["messages"]
                or record["model"] != wire["model"] or row["model"] != wire["model"]
                or not isinstance(record["model_digest"], str)
                or re.fullmatch("[0-9a-f]{64}", record["model_digest"]) is None):
            raise DiagnosticError("INVALID_FROZEN_WIRE_REQUEST")
        check_schema(wire["format"])
        pins.add((wire["model"], record["model_digest"]))
        text = data["request"]["text"] if row["stage"] == "q3" else None
        if text is not None and not isinstance(text, str):
            raise DiagnosticError("Q3_USER_TEXT_MISSING")
        cases.append({"number": row["number"], "round": row["round"], "stage": row["stage"],
                      "recording_path": path.relative_to(root).as_posix(),
                      "recording_sha256": row["recording_sha256"], "record_location": row["record_location"],
                      "wire": wire, "user_text": text, "baseline_timeout_ms": row["timeout_ms"]})
    if len(pins) != 1 or len({sha256(encode(c["wire"])) for c in cases}) != 3:
        raise DiagnosticError("MODEL_OR_DISTINCT_REQUEST_PINS_MISMATCH")
    model, digest = next(iter(pins))
    return cases, {"model": model, "model_digest": digest,
                   "inputs": {"path": input_path.relative_to(root).as_posix(), "sha256": inputs_sha256},
                   "baseline_result": {"path": result_path.relative_to(root).as_posix(), "sha256": baseline_result_sha256},
                   "verified_input_files": input_refs}


def validate_base_url(base_url):
    try:
        parsed = urlsplit(base_url)
        address = ipaddress.ip_address(parsed.hostname or "")
        port = parsed.port
    except ValueError as exc:
        raise DiagnosticError("LITERAL_LOOPBACK_URL_REQUIRED") from exc
    if (parsed.scheme != "http" or not address.is_loopback or port is None
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        raise DiagnosticError("LITERAL_LOOPBACK_URL_REQUIRED")
    return base_url.rstrip("/")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise DiagnosticError("REDIRECT_REJECTED")


class LocalTransport:
    def __init__(self, base_url):
        self.base_url = validate_base_url(base_url)
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def __call__(self, method, route, body, timeout):
        if route not in ALLOWED_ROUTES or method != ("POST" if route == "/api/chat" else "GET"):
            raise DiagnosticError("ROUTE_NOT_ALLOWED")
        request = Request(self.base_url + route, data=body if method == "POST" else None,
                          headers={"Content-Type": "application/json"}, method=method)
        with self.opener.open(request, timeout=timeout) as response:
            return response.read()


def q3_literal_valid(value, text):
    if not isinstance(value, dict) or type(value.get("needs_clarification")) is not bool:
        return False
    question = value.get("clarification_question")
    if value["needs_clarification"]:
        if not isinstance(question, str) or not question.strip():
            return False
    elif question is not None:
        return False
    literals = [value.get("class_term"), value.get("color_term")]
    time_literal = value.get("time_literal")
    if not isinstance(time_literal, dict):
        return False
    literals += list(time_literal.values())
    for key in ("camera_terms", "region_terms"):
        if not isinstance(value.get(key), list):
            return False
        literals += value[key]
    return all(item is None or isinstance(item, str) and bool(item) and item in text for item in literals)


def assess(raw, case, expected_model):
    response = strict_json(raw)
    if not isinstance(response, dict) or response.get("model") != expected_model or "error" in response:
        raise DiagnosticError("GENERATION_RESPONSE_MODEL_OR_ERROR")
    valid_json, valid_schema, literal = False, False, None
    try:
        content = response["message"]["content"]
        if not isinstance(content, str):
            raise DiagnosticError("OUTPUT_NOT_STRING")
        value = strict_json(content)
        valid_json = True
        valid_schema = schema_valid(value, case["wire"]["format"])
        if case["stage"] == "q3":
            literal = valid_schema and q3_literal_valid(value, case["user_text"])
    except (KeyError, TypeError, DiagnosticError):
        pass
    metrics = {}
    for key in ("prompt_eval_count", "eval_count", "total_duration", "load_duration", "prompt_eval_duration", "eval_duration"):
        number = response.get(key)
        metrics[key] = number if type(number) is int and number >= 0 else None
    done = response.get("done") is True
    reason = response.get("done_reason")
    # Do not publish untrusted server strings from arbitrary errors or responses.
    reason = reason if reason in {"stop", "length", "load", "unload"} else "UNKNOWN"
    return {"json_valid": valid_json, "schema_valid": valid_schema, "q3_literal_guard_valid": literal,
            "validation_scope": "FROZEN_SCHEMA_AND_Q3_LITERAL_SUBSTRINGS" if case["stage"] == "q3" else "FROZEN_SCHEMA_WITH_LITERAL_REFS_ONLY",
            "semantic_controller_acceptance": "UNKNOWN", "done": done, "done_reason": reason,
            "untruncated_completion": done and reason == "stop", "server_duration_unit": "ns", **metrics}


def run_diagnostic(cases, pins, output, base_url, *, transport=None, disk_free=None, clock=None):
    validate_base_url(base_url)
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise DiagnosticError("OUTPUT_ALREADY_EXISTS")
    if not output.parent.is_dir() or output.parent.resolve() != output.parent:
        raise DiagnosticError("OUTPUT_PARENT_MISSING_OR_SYMLINK")
    free = disk_free or (lambda path: shutil.disk_usage(path).free)
    if free(output.parent) < MIN_FREE_BYTES:
        raise DiagnosticError("DISK_BELOW_EIGHT_GIB")
    timer = clock or time.perf_counter
    transport = transport or LocalTransport(base_url)
    output.mkdir(mode=0o700)
    (output / "private").mkdir(mode=0o700)
    calls, operations = [], []
    failure = None

    def exchange(name, route, payload=None, timeout=5):
        request = encode(payload) if payload is not None else b""
        request_path = output / "private" / (name + ".request.bin")
        with request_path.open("xb") as handle:
            handle.write(request)
        started = timer()
        raw = transport("POST" if payload is not None else "GET", route, request, timeout)
        elapsed = (timer() - started) * 1000
        if not isinstance(raw, bytes):
            raise DiagnosticError("TRANSPORT_MUST_RETURN_RAW_BYTES")
        response_path = output / "private" / (name + ".response.bin")
        with response_path.open("xb") as handle:
            handle.write(raw)
        operations.append({"name": name, "route": route, "request_sha256": sha256(request),
                           "response_sha256": sha256(raw), "wall_latency_ms": elapsed,
                           "timeout_seconds": timeout})
        return raw, elapsed

    def tags(name):
        raw, _ = exchange(name, "/api/tags")
        value = strict_json(raw)
        matching = [m for m in value.get("models", []) if m.get("name") == pins["model"] or m.get("model") == pins["model"]]
        if len(matching) != 1 or matching[0].get("digest") != pins["model_digest"]:
            raise DiagnosticError("MODEL_DIGEST_DRIFT_OR_MISSING")

    try:
        for route in ("version", "ps"):
            raw, _ = exchange("before-" + route, "/api/" + route)
            strict_json(raw)
        tags("before-tags")
        for case in cases:
            if free(output) < MIN_FREE_BYTES:
                raise DiagnosticError("DISK_BELOW_EIGHT_GIB")
            prefix = "call-%02d" % case["number"]
            tags(prefix + "-before-tags")
            wire = deepcopy(case["wire"])
            wire["options"]["num_predict"] = -1
            raw, elapsed = exchange(prefix, "/api/chat", wire, timeout=None)
            metadata = {key: case[key] for key in ("number", "round", "stage", "recording_path", "recording_sha256", "record_location", "baseline_timeout_ms")}
            metadata.update(original_wire_sha256=sha256(encode(case["wire"])),
                            diagnostic_wire_sha256=sha256(encode(wire)),
                            wall_latency_ms=elapsed, generation_timeout_seconds=None,
                            num_predict=-1, model_pin_verified_after=False,
                            **assess(raw, case, pins["model"]))
            calls.append(metadata)
            tags(prefix + "-after-tags")
            metadata["model_pin_verified_after"] = True
            with (output / "CALLS.jsonl").open("ab") as handle:
                handle.write(encode(metadata) + b"\n")
        tags("after-tags")
        for route in ("version", "ps"):
            raw, _ = exchange("after-" + route, "/api/" + route)
            strict_json(raw)
    except Exception as exc:
        failure = str(exc) if isinstance(exc, DiagnosticError) else "TRANSPORT_OR_RUNTIME_FAILURE"
    result = {"schema_version": "q-demo.qwen3-untruncated-diagnostic.v1",
              "status": "COMPLETE" if failure is None and len(calls) == len(cases) else "FAILED",
              "failure": failure, "created_at": datetime.now(timezone.utc).isoformat(),
              "purpose": "CX-6 DIAGNOSTIC ONLY", "formal_denominator": False,
              "budgets_changed": False, "product_provider_modified": False,
              "generation_timeout_seconds": None, "num_predict": -1,
              "schema_checker": "STDLIB_FROZEN_SUBSET_V1", "semantic_controller_acceptance": "UNKNOWN",
              "pins": pins, "expected_calls": len(cases), "completed_calls": len(calls),
              "untruncated_completions": sum(c["untruncated_completion"] and c["model_pin_verified_after"] for c in calls),
              "schema_valid_outputs": sum(c["schema_valid"] for c in calls),
              "calls": calls, "operations": operations, "raw_artifacts": "LOCAL_ONLY",
              "limits": ["Sequential replay changes concurrency and loading context.",
                         "Only num_predict is changed; messages, schema and other options are retained.",
                         "Schema and substring checks are not full parser or Controller acceptance.",
                         "A length or unknown done_reason is not an untruncated completion."]}
    with (output / "RESULT.json").open("xb") as handle:
        handle.write(encode(result) + b"\n")
    files = []
    for path in sorted(output.rglob("*")):
        if path.is_file():
            raw = path.read_bytes()
            files.append({"path": path.relative_to(output).as_posix(), "size_bytes": len(raw), "sha256": sha256(raw)})
    manifest = {"schema_version": "q-demo.local-artifact-manifest.v1", "files": files,
                "hashed_file_count": len(files), "hashed_size_bytes": sum(f["size_bytes"] for f in files),
                "self_excluded": "MANIFEST.json", "file_count_including_manifest": len(files) + 1}
    with (output / "MANIFEST.json").open("xb") as handle:
        handle.write(encode(manifest) + b"\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("inputs", "inputs-sha256", "baseline-result", "baseline-result-sha256", "artifacts-root", "output", "base-url"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args(argv)
    try:
        cases, pins = load_cases(args.inputs, args.inputs_sha256, args.baseline_result,
                                args.baseline_result_sha256, args.artifacts_root)
        result = run_diagnostic(cases, pins, args.output, args.base_url)
        print(json.dumps({key: result[key] for key in ("status", "failure", "completed_calls", "untruncated_completions", "schema_valid_outputs")}, sort_keys=True))
        return 0 if result["status"] == "COMPLETE" else 1
    except Exception as exc:
        print(json.dumps({"status": "FAILED", "failure": str(exc) if isinstance(exc, DiagnosticError) else "INPUT_OR_RUNTIME_FAILURE"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
