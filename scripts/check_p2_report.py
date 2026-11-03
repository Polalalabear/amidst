"""CQ-25-T evaluation-only recomputation of explicitly SYNTHETIC P2 probes.

The aggregate envelope below is TEST_ONLY, not an adopted production receipt or
report contract. The default rejects formal inputs. Existing v1 scorers and
their pinned schema loader remain unchanged; no model or inference is run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from amidst.evaluation import q1_query_eval as q1, q3_parse_eval as q3, q5_switch_eval as q5  # noqa: E402

V1_SHA256 = "0fd1ef68c4c83443e8311723224b76f103c142dd018275e7c1596f917e85d9f2"
MODES = {"RULE_ONLY", "AGENT_SEQUENTIAL"}


class ReportError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReportError(message)


def canonical(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, sort_keys=True, separators=(",", ":")).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    return q5.load_json(raw)


def read_reference(root, reference):
    require(isinstance(reference, dict), "FILE_REFERENCE_REQUIRED")
    name = reference.get("path")
    require(isinstance(name, str) and bool(name), "FILE_REFERENCE_REQUIRED")
    relative = Path(name)
    path = root / relative
    require(not relative.is_absolute() and ".." not in relative.parts
            and path.resolve() == path and path.is_file()
            and path.suffix in {".json", ".jsonl"}, "REGULAR_RELATIVE_FILE_REQUIRED")
    raw = path.read_bytes()
    require(sha(raw) == reference.get("sha256"), "FILE_HASH_MISMATCH: " + name)
    return raw


def timestamp(value):
    require(isinstance(value, str), "OFFSET_TIMESTAMP_REQUIRED")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.utcoffset() is not None, "OFFSET_TIMESTAMP_REQUIRED")
    return result


def numeric_leaves(value, prefix="", *, exclude=frozenset()):
    if type(value) in {int, float}:
        yield prefix, value
    elif isinstance(value, dict):
        for key, child in sorted(value.items()):
            if not prefix and key in exclude:
                continue
            escaped = key.replace("~", "~0").replace("/", "~1")
            yield from numeric_leaves(child, prefix + "/" + escaped)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from numeric_leaves(child, prefix + "/" + str(index))


def recompute(receipt_path, *, synthetic_only=False):
    # No production aggregate decoder has been adopted. Opt-in is test scope,
    # never a substitute for approval or a way to enable formal scoring.
    require(synthetic_only, "FORMAL_FORMAT_UNKNOWN: use --synthetic-only for CQ-25-T probes")
    receipt_path = Path(receipt_path).absolute()
    require(receipt_path.resolve() == receipt_path and receipt_path.is_file(), "REGULAR_RECEIPT_REQUIRED")
    root = receipt_path.parent
    receipt_raw = receipt_path.read_bytes()
    receipt = decode(receipt_raw)
    require(receipt.get("test_only") == "SYNTHETIC" and receipt.get("formal_eligible") is False,
            "TEST_ONLY_INPUT_REQUIRED")
    require(timestamp(receipt["frozen_at"]) < timestamp(receipt["script_read_at"]), "FREEZE_ORDER_INVALID")
    outputs = receipt.get("outputs")
    require(isinstance(outputs, list) and bool(outputs), "OUTPUT_PINS_REQUIRED")
    verified = {}
    input_hashes = {"receipt": sha(receipt_raw)}
    # Verify every frozen output byte before opening any evaluation script.
    for ref in outputs:
        require(ref["path"] not in verified, "DUPLICATE_OUTPUT_REFERENCE")
        verified[ref["path"]] = read_reference(root, ref)
        input_hashes[ref["path"]] = ref["sha256"]

    def output(name):
        require(name in verified, "OUTPUT_REFERENCE_MISSING: " + str(name))
        return verified[name]

    runs = receipt.get("runs")
    require(isinstance(runs, list) and bool(runs), "RUNS_REQUIRED")
    seen_runs = set()
    # Resolve all named outputs, even unscoreable modes, before script reads.
    for run in runs:
        require(run["run_id"] not in seen_runs, "DUPLICATE_RUN")
        seen_runs.add(run["run_id"])
        require(set(run["modes"]) == MODES, "BOTH_MODES_REQUIRED")
        for mode, refs in run["modes"].items():
            response_raw, decisions_raw = output(refs["response"]), output(refs["decisions"])
            response = decode(response_raw)
            require(response.get("schema_version") == "q-demo.q2-response.v1", "V1_RESPONSE_REQUIRED")
            require(response.get("output_sha256") == q5.digest(response, "output_sha256")
                    and response.get("decisions_sha256") == sha(decisions_raw), "OUTPUT_CONTENT_BINDING_MISMATCH")
            require(response.get("resolved_scope", {}).get("run_ids") == [run["run_id"]], "OUTPUT_RUN_MISMATCH")
            require("SYNTHETIC" in response.get("provenance", {}).get("producer", ""), "SYNTHETIC_RESPONSE_REQUIRED")
            require(all(decode(line).get("switch_mode") == mode for line in decisions_raw.splitlines()), "MODE_BINDING_MISMATCH")
    q1_raw, q3_raw = output(receipt["q1_predictions"]), output(receipt["q3_predictions"])

    def reference(key):
        ref = receipt[key]
        raw = read_reference(root, ref)
        input_hashes[ref["path"]] = ref["sha256"]
        return raw

    annotations = decode(reference("annotations"))
    q1_cases_raw, q3_cases_raw, clocks_raw = reference("q1_cases"), reference("q3_cases"), reference("clocks")
    q1_cases, q3_cases = q1.rows(q1_cases_raw), q1.rows(q3_cases_raw)
    require(all(case.get("id", "").startswith("SYNTHETIC") for case in q1_cases + q3_cases),
            "SYNTHETIC_ANNOTATIONS_REQUIRED")
    schemas = q1.PinnedSchemas(ROOT / "src/amidst/contracts/q_demo")
    for relative in q1._PINNED_FILES:
        pin_path = ROOT / "src/amidst/contracts/q_demo" / relative
        input_hashes["schema:" + relative] = sha(pin_path.read_bytes())
    for name in ["q1_query_eval.py", "q3_parse_eval.py", "q5_switch_eval.py"]:
        raw = (ROOT / "src/amidst/evaluation" / name).read_bytes()
        if name == "q5_switch_eval.py":
            require(sha(raw) == V1_SHA256, "PINNED_V1_SCORER_CHANGED")
        input_hashes["scorer:" + name] = sha(raw)
    q1_report = q1.evaluate(q1_cases, q1.rows(q1_raw), cases_sha256=sha(q1_cases_raw),
        predictions_sha256=sha(q1_raw), schemas=schemas, evaluation_eligible=False,
        authority_sha256=sha(receipt_raw), dataset_kind="SYNTHETIC")
    q3_report = q3.evaluate(q3_cases, q1.rows(q3_raw), cases_sha256=sha(q3_cases_raw),
        predictions_sha256=sha(q3_raw), schemas=schemas, clocks=q3.clock_catalog(decode(clocks_raw)),
        clocks_sha256=sha(clocks_raw), evaluation_eligible=False, authority_sha256=sha(receipt_raw))
    require(not q1_report["invalid_cases"] and not q3_report["invalid_cases"], "PRECISE_ANNOTATIONS_INVALID")
    report = {"test_only": "SYNTHETIC", "formal_eligible": False, "formal_acceptance": "NOT_EVALUATED",
              "identity": "UNCONFIRMED", "physical": "UNKNOWN", "q4": "NOT_EVALUATED_IN_TEST_PROBE",
              "q1": q1_report, "q3": q3_report, "q3_synthetic_aggregate": "MISSING_IN_PINNED_SCORER",
              "q5": {}, "latency_ms": {}, "input_hashes": input_hashes}
    for run in runs:
        run_id = run["run_id"]
        ref = run["script"]
        script_raw = read_reference(root, ref)
        input_hashes[ref["path"]] = ref["sha256"]
        script = decode(script_raw)
        require(script.get("status") == "PROPOSED" and script.get("approval_ref") is None,
                "SYNTHETIC_SCRIPT_MUST_REMAIN_PROPOSED")
        annotation = annotations["runs"][run_id]
        scored, excluded = annotation["scored_event_ids"], annotation["non_scoring_event_ids"]
        require(len(set(scored)) == len(scored) and len(set(excluded)) == len(excluded)
                and not set(scored) & set(excluded)
                and set(scored) == {e["event_id"] for e in script["events"]},
                "SCRIPT_ANNOTATION_EVENT_SPLIT_MISMATCH")
        report["q5"][run_id] = {}
        report["latency_ms"][run_id] = {}
        for mode, refs in sorted(run["modes"].items()):
            response_raw, decisions_raw = output(refs["response"]), output(refs["decisions"])
            response = decode(response_raw)
            latency = response.get("stats", {}).get("latency_ms", {}).get("total")
            require(latency is None or (type(latency) in {int, float} and math.isfinite(latency) and latency >= 0),
                    "RECORDED_LATENCY_OR_NULL_REQUIRED")
            report["latency_ms"][run_id][mode] = latency
            status = response["status"]
            measurement = None
            if status == "COMPLETE":
                frozen = q5.freeze_output(response_raw, decisions_raw, expected_response_sha256=sha(response_raw),
                                          expected_decisions_sha256=sha(decisions_raw))
                measurement = q5.compare_script(frozen, script_raw, expected_script_sha256=sha(script_raw))
            else:
                require(status in {"PARTIAL", "ENDED_BY_LIMIT"}, "UNSUPPORTED_NONCOMPLETE_STATUS")
            report["q5"][run_id][mode] = {"measurement": measurement,
                "not_scored_reason": None if measurement is not None else status,
                "non_scoring_event_ids": sorted(excluded), "response_status": status,
                "input_sha256": [sha(response_raw), sha(decisions_raw), sha(script_raw), receipt["annotations"]["sha256"]]}
    # Numeric rows refer to immutable source bytes. The JSON pointer identifies
    # the exact scalar; canonical markdown cannot add an untraced number.
    all_pins = sorted(set(input_hashes.values()))
    provenance = {}
    for pointer, _ in numeric_leaves(report):
        if pointer.startswith("/q5/"):
            _, _, run_id, mode, *_ = pointer.split("/")
            pins = report["q5"][run_id][mode]["input_sha256"]
        elif pointer.startswith("/q1/"):
            pins = [sha(q1_cases_raw), sha(q1_raw)]
        elif pointer.startswith("/q3/"):
            pins = [sha(q3_cases_raw), sha(q3_raw), sha(clocks_raw)]
        elif pointer.startswith("/latency_ms/"):
            _, _, run_id, mode = pointer.split("/")
            pins = [report["q5"][run_id][mode]["input_sha256"][0]]
        else:
            pins = all_pins
        provenance[pointer] = pins
    report["numeric_provenance"] = provenance
    return report


def markdown(report):
    lines = ["# SYNTHETIC P2 recomputation probe", "", "TEST_ONLY; formal acceptance NOT_EVALUATED.",
             "Identity UNCONFIRMED; physical UNKNOWN. Q4 NOT_EVALUATED_IN_TEST_PROBE.",
             "Q3 synthetic aggregate MISSING_IN_PINNED_SCORER; zero denominator means value=null, not zero accuracy.",
             "", "| JSON pointer | Number | Input bytes SHA-256 |", "| --- | --- | --- |"]
    for pointer, value in numeric_leaves(report, exclude={"numeric_provenance"}):
        pins = ", ".join("`" + pin + "`" for pin in report["numeric_provenance"][pointer])
        lines.append(f"| `{pointer}` | `{json.dumps(value)}` | {pins} |")
    lines += ["", "Full event details, exclusions, null measurements and source hashes are in the paired JSON."]
    return "\n".join(lines) + "\n"


def check_report(report_path, receipt_path, *, synthetic_only=False):
    result = {"ok": False, "status": "FAIL", "formal_acceptance": "NOT_EVALUATED", "errors": []}
    try:
        expected = recompute(receipt_path, synthetic_only=synthetic_only)
        report_path = Path(report_path).absolute()
        require(report_path.resolve() == report_path and report_path.is_file(), "REGULAR_REPORT_REQUIRED")
        actual = decode(report_path.read_bytes())
        require(canonical(actual) == canonical(expected), "REPORT_RECOMPUTATION_MISMATCH")
        md = report_path.with_suffix(".md")
        require(md.resolve() == md and md.is_file() and md.read_text() == markdown(expected), "MARKDOWN_RECOMPUTATION_MISMATCH")
        result.update(ok=True, status="SYNTHETIC_ONLY_PASS")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        result["errors"].append(str(exc))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--inputs", required=True, type=Path)
    parser.add_argument("--synthetic-only", action="store_true")
    args = parser.parse_args(argv)
    result = check_report(args.report, args.inputs, synthetic_only=args.synthetic_only)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
