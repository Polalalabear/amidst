"""Small API/kernel baseline adapter. Domain outputs remain byte/hash immutable.

The caller owns process isolation and explicit SYNTHETIC versus formal scope.
No model downloads, media generation, answers, scoring or UI timing occur here.
"""

import os
import stat
import time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from amidst.q1q5.api import QAPI, RecordingStore, raw_json
from amidst.q1q5.baseline_telemetry import MeasurementFailure, measure_call, verify_replay
from amidst.q1q5.clock_mapping import resolve_source_range, resolve_wall_range
from amidst.q1q5.production_preflight import read_pinned, sha, strict_json
from amidst.q1q5.store import _safe_content, canonical_hash


class BaselineError(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise BaselineError(code)


def save(path, value):
    raw = value if isinstance(value, bytes) else raw_json(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(raw)
    return sha(raw)


def load_plan(path, pin, *, engineering, authority=None):
    protocol = strict_json(read_pinned(path, pin))
    need(protocol.get("schema_version") == "q-demo.baseline-protocol.v1", "PROTOCOL_VERSION")
    # Formal operation needs independent review/freeze; a JSON boolean cannot authorize it.
    from amidst.q1q5.baseline_authority import ReviewedAuthority, check_input

    check_input(authority, "protocol", pin)

    if engineering:
        need(
            authority is None
            and protocol.get("issue") == 192
            and protocol.get("formal_run", {}).get("allowed") is False,
            "ENGINEERING_PROTOCOL_SCOPE",
        )
    else:
        need(isinstance(authority, ReviewedAuthority), "FORMAL_RUN_REQUIRES_INDEPENDENT_FREEZE")
        need(
            protocol.get("issue") == 192
            and protocol.get("status") == "FROZEN"
            and protocol.get("formal_run", {}).get("allowed") is True,
            "FROZEN_PROTOCOL_REQUIRED",
        )
    need(protocol["execution"]["worker_concurrency"] == 1, "SERIAL_WORKERS_REQUIRED")
    need(
        type(protocol["execution"]["first_calls"]) is int
        and protocol["execution"]["first_calls"] == 1
        and type(protocol["execution"]["warm_repeats"]) is int
        and 0 <= protocol["execution"]["warm_repeats"] <= 20,
        "EXPLICIT_REPEAT_BOUNDS",
    )
    return protocol


def load_cases(path, pin, *, authority=None):
    from amidst.q1q5.baseline_authority import check_input

    check_input(authority, "cases", pin)
    raw = read_pinned(path, pin, maximum=16_777_216)
    cases = [strict_json(line) for line in raw.splitlines() if line.strip()]
    need(0 < len(cases) <= 100, "BOUNDED_CASE_CATALOG_REQUIRED")
    required = {
        "case_id",
        "task",
        "data_kind",
        "binding_id",
        "run_id",
        "camera_ids",
        "source_range_us",
        "query",
        "selected_seed",
    }
    for case in cases:
        need(isinstance(case, dict) and set(case) == required, "CASE_FIELDS")
        _safe_content(case)
        need(
            isinstance(case["case_id"], str) and case["case_id"] and len(case["case_id"]) <= 128,
            "CASE_ID",
        )
        need(case["task"] in {"ONCE_SEARCH", "CONTINUOUS_PURSUIT"}, "TASK_REQUIRED")
        need(
            case["data_kind"] == (authority.source_kind if authority else "SYNTHETIC"),
            "FORMAL_OR_PILOT_CASE_NOT_ENABLED",
        )
        query = case["query"]
        need(isinstance(query, dict) and query.get("kind") in {"TEXT", "PRESET"}, "QUERY_KIND")
        need(
            set(query)
            == {
                "kind",
                "question_id",
                "text",
                "request_ref",
                "request_file_sha256",
                "context_sha256",
            },
            "QUERY_FIELDS",
        )
        if query["kind"] == "TEXT":
            need(
                isinstance(query["text"], str)
                and 0 < len(query["text"]) <= 4096
                and isinstance(query["question_id"], str)
                and bool(query["question_id"])
                and query["request_ref"] is None
                and query["request_file_sha256"] is None,
                "TEXT_PRESET_EXCLUSIVE",
            )
        else:
            need(
                query["text"] is None
                and query["question_id"] is None
                and isinstance(query["request_ref"], str),
                "TEXT_PRESET_EXCLUSIVE",
            )
    need(len({case["case_id"] for case in cases}) == len(cases), "DUPLICATE_CASE_ID")
    from amidst.q1q5.baseline_authority import verify_questions

    verify_questions(cases, authority)
    return cases


def verify_composition(path, pin, source_root):
    composition = strict_json(read_pinned(path, pin, maximum=16_777_216))
    need(
        composition.get("scope") == "ENGINEERING_COMPOSITION_NOT_INTEGRATED_PRODUCT",
        "COMPOSITION_SCOPE",
    )
    files = composition.get("files")
    need(isinstance(files, dict) and 0 < len(files) <= 2000, "COMPOSITION_FILES")
    root = Path(source_root)
    for relative, entry in files.items():
        parts = PurePosixPath(relative)
        need(
            not parts.is_absolute() and parts.as_posix() == relative and ".." not in parts.parts,
            "COMPOSITION_RELATIVE_PATH",
        )
        file = root / relative
        need(file.resolve() == file and file.is_relative_to(root), "COMPOSITION_SYMLINK_OR_SCOPE")
        fd = os.open(file, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            need(
                stat.S_ISREG(info.st_mode) and info.st_size <= 4_194_304,
                "COMPOSITION_FILE_TYPE_OR_SIZE",
            )
            raw = handle.read(4_194_305)
        need(len(raw) == info.st_size and sha(raw) == entry.get("sha256"), "COMPOSITION_FILE_PIN")
    return {"file_sha256": pin, "verified_files": len(files), "integrated_product": False}


def fresh_api(api, profile, private_root, *, repo_root):
    private_root.mkdir(mode=0o700)
    runs = [
        replace(
            run, parse_settings=replace(run.parse_settings, switch_mode=profile["q5_switch_mode"])
        )
        for run in api.runs.values()
    ]
    return QAPI(
        runs,
        max_responses=api.max_responses,
        max_media_refs=api.max_media_refs,
        recording_store=RecordingStore(private_root, repo_root=repo_root, max_bytes=16_777_216),
        rgb_api=api.rgb_api,
    )


def selected_run(api, case, *, authority=None):
    matches = [run for run in api.runs.values() if run.catalog["run_id"] == case["run_id"]]
    need(len(matches) == 1, "EXACT_REGISTERED_RUN_REQUIRED")
    run = matches[0]
    from amidst.q1q5.baseline_authority import ReviewedAuthority

    need(
        case["data_kind"] == "SYNTHETIC" or isinstance(authority, ReviewedAuthority),
        "FORMAL_RUN_REQUIRES_INDEPENDENT_FREEZE",
    )
    need(
        run.source_kind == case["data_kind"] and run.source_kind in {"SYNTHETIC", "FORMAL_R004"},
        "SOURCE_KIND_MISMATCH",
    )
    need(case["binding_id"] == run.bindings.index_sha256, "CASE_INDEX_PIN")
    cameras = case["camera_ids"]
    registered = {row["camera_id"] for row in run.bindings.index.manifest["sampling"]["per_camera"]}
    interval = case["source_range_us"]
    need(
        isinstance(cameras, list)
        and cameras
        and len(set(cameras)) == len(cameras)
        and set(cameras) <= registered,
        "CASE_CAMERA_SCOPE",
    )
    need(
        isinstance(interval, list)
        and len(interval) == 2
        and all(type(value) is int for value in interval)
        and 0 <= interval[0] < interval[1] <= run.bindings.clock.duration_us,
        "CASE_TIME_SCOPE",
    )
    need(case["query"]["context_sha256"] == run.bindings.clock_sha256, "CASE_CONTEXT_PIN")
    seed = case["selected_seed"]
    if seed is not None:
        need(
            isinstance(seed, dict)
            and set(seed)
            == {
                "observation_id",
                "frame_ref",
                "run_id",
                "camera_id",
                "timestamp_us",
                "source_response_sha256",
            },
            "SEED_FIELDS",
        )
        rows = [
            row
            for row in run.bindings.index.records
            if any(
                item["observation_id"] == seed["observation_id"] for item in row["detections"] or []
            )
        ]
        need(
            len(rows) == 1
            and seed["run_id"] == case["run_id"]
            and all(
                seed[key] == rows[0][key] for key in ("frame_ref", "camera_id", "timestamp_us")
            ),
            "SEED_METADATA_PIN",
        )
    return run


def validate_request_scope(request, case, run):
    b = run.bindings
    need(
        request.get("scene_id") == run.catalog["scene_id"]
        and request.get("run_ids") == [case["run_id"]],
        "QUERY_RUN_SCOPE",
    )
    time = request.get("time", {})
    if time.get("kind") == "SOURCE":
        need(time.get("run_id") == case["run_id"], "QUERY_CLOCK_SCOPE")
        resolution = resolve_source_range(b.clock, *time["range_us"])
    else:
        need(time.get("kind") == "WALL", "QUERY_TIME_KIND")
        resolution = resolve_wall_range([b.clock], *time["wall_range"])
    need(resolution.coverage_complete and len(resolution.ranges) == 1, "QUERY_UNCOVERED_TIME")
    left, right = resolution.ranges[0].range_us
    need(
        case["source_range_us"][0] <= left < right <= case["source_range_us"][1],
        "QUERY_OUTSIDE_CASE_TIME",
    )
    cameras = request.get("camera_ids")
    effective = set(cameras) if cameras else set(run.catalog["camera_ids"])
    need(effective <= set(case["camera_ids"]), "QUERY_OUTSIDE_CASE_CAMERAS")


def capture_bundle(api, request, response, authorize):
    ref = response.get("session_id") or response["output_sha256"]
    pin = api.call(
        "q_record_response", {"session_ref": request["session_ref"], "response_ref": ref}, authorize
    )
    descriptor = {key: pin[key] for key in ("recording_id", "file", "file_sha256")}
    bundle = api.recording_store.load(descriptor)
    replay = QAPI(
        max_responses=api.max_responses,
        max_media_refs=api.max_media_refs,
        recording_store=api.recording_store,
        recordings=[descriptor],
    )
    repeated = replay.call(
        "q_recorded_response",
        {"session_ref": request["session_ref"], "recording_id": pin["recording_id"]},
        authorize,
    )
    need(repeated == response, "API_RECORDED_RESPONSE_CHANGED")
    return bundle, descriptor


def replay_kernel(bundle, request, run, selected, authorize):
    """Re-execute the frozen request with recorded providers; never a live provider."""
    from amidst.q1q5.q4_evidence import candidate_evidence
    from amidst.q1q5.q5_controller import RuleController

    response = bundle["response"]
    provider_calls = 0
    if response["schema_version"] in {"q-demo.q3-parse-response.v1", "q-demo.q3-parse-response.v2"}:
        from amidst.q1q5.ollama_runtime import RecordedParseProvider
        from amidst.q1q5.q3_parse import parse_query

        audit = bundle["q3_provider_audit"]
        provider = RecordedParseProvider(audit, expected_sha256=canonical_hash(audit))
        options = dict(run.q3_options)
        if (
            request["parser_mode"] == "LLM_WITH_RULE_FALLBACK"
            and options.get("provider") is not None
        ):
            options["provider"] = provider
        repeated, _ = parse_query(
            request,
            catalog=run.catalog,
            settings=run.parse_settings,
            clock_mapping=run.bindings.clock,
            **options,
        )
        provider.assert_consumed()
        need(repeated == response, "Q3_REPLAY_CHANGED")
        return {
            "status": "PASS",
            "output_equal": True,
            "journals_equal": None,
            "provider_calls": 0,
            "network_calls": 0,
            "recorded_provider_events": len(audit),
        }
    if response["schema_version"] in {"q-demo.q1-response.v1", "q-demo.q1-response.v2"}:
        replay_run = replace(run, q3_options={}, agent_factory=None)
        replay = QAPI([replay_run], max_responses=128, max_media_refs=4096)
        payload = request
        if bundle.get("parse_receipt_ref") is not None:
            parent = bundle["parse_response"]
            replay.responses[(request["session_ref"],bundle["parse_receipt_ref"])] = {
                "response":parent,"scene_id":bundle["scene_id"],"run_id":bundle["run_id"],
                "evidence":[],"links":"","decisions":""}
            payload = {"request":request,"parse_response_ref":bundle["parse_receipt_ref"]}
        repeated = replay.call("q1_camera_search", payload, authorize)
        result = verify_replay(response, repeated)
    else:

        def port(index, snapshot, reference, context):
            return candidate_evidence(index, snapshot, reference, **context)

        args = {
            "bindings": run.bindings,
            "evidence_provider": port,
            "selected_observation_id": selected,
            "parse_receipt_ref": bundle.get("parse_receipt_ref"),
            "default_selected_run": response["resolved_scope"].get("time_range_source")=="DEFAULT_SELECTED_RUN",
        }
        trace = bundle.get("agent_trace")
        if request["switch_mode"] == "AGENT_SEQUENTIAL":
            from amidst.q1q5.q5_agent import AgentController, RecordedProvider

            need(trace is not None, "AGENT_TRACE_REQUIRED")
            provider = RecordedProvider(trace, expected_sha256=trace["content_sha256"])
            settings = run.agent_factory(request, **args).settings
            controller = AgentController(
                request,
                **args,
                provider=provider,
                agent_settings=settings,
                round_scheduler=lambda *values: None,
                clock=provider.clock,
            )
            repeated = controller.run()
            provider.assert_consumed()
            provider_calls = len(trace["events"])
        else:
            repeated = RuleController(request, **args).run()
        original = SimpleNamespace(
            response=response,
            decisions_bytes=bundle["decisions"].encode(),
            links_bytes=bundle["links"].encode(),
        )
        result = verify_replay(original, repeated)
    return {
        "status": "PASS",
        **result,
        "provider_calls": 0,
        "network_calls": 0,
        "recorded_provider_events": provider_calls,
    }


def export_domain(root, request, bundle, run):
    """Existing #127 receives original domain documents, not the telemetry envelope."""
    root.mkdir(mode=0o700)
    b = run.bindings
    docs = {
        "case.request.json": request,
        "case.response.json": bundle["response"],
        "parameter_set.json": b.parameter_set,
        "detection_index.json": b.index.manifest,
        "clock_mapping.json": dict(b.clock.document),
        "region_graph.json": b.graphs.region,
        "camera_graph.json": b.graphs.camera,
    }
    if b.graphs.tracking_scope is not None:
        # This pin is over original scope bytes, not a reserialized document.
        raw = b.graphs.tracking_scope_bytes
        need(raw is not None, "TRACKING_SCOPE_BYTES_REQUIRED")
        save(root / "tracking_scope.json", raw)
    for i, value in enumerate(bundle["snapshots"]):
        docs[f"{i}.snapshot.json"] = value
    for i, value in enumerate(bundle["evidence"]):
        docs[f"{i}.evidence.json"] = value
    for name, value in docs.items():
        save(root / name, value)
    from amidst.q1q5.q5_controller import jsonl

    save(root / b.index.manifest["records_ref"], jsonl(b.index.records))
    for kind in ("decisions", "links"):
        ref = bundle["response"].get(kind + "_ref")
        if ref:
            need(Path(ref).name == ref, "JOURNAL_NAME")
            save(root / ref, bundle[kind].encode())


def role_metrics(response, bundle, *, q3, configured):
    rows = (
        bundle.get("q3_provider_audit", [])
        if q3
        else (bundle.get("agent_trace") or {}).get("events", [])
    )
    records = [row["provider_record"] if q3 else row["record"] for row in rows]
    return {
        "configured_enabled": configured,
        "attempted": bool(rows) if q3 else response["agent_attempted"],
        "used": response["llm_parse_used"] if q3 else response["agent_used"],
        "provider_calls": len(rows),
        "timeout_calls": sum(row.get("validation") == "PROVIDER_TIMEOUT" for row in records),
        "fallback_used": response["fallback_used"],
        "fallback_reason": response["fallback_reason"],
        "task_status": response["status"],
        "audit_content_sha256": canonical_hash(rows),
    }


def execute_sample(
    api,
    authorize,
    case,
    profile,
    protocol,
    *,
    request_loader,
    session_ref,
    output,
    iteration,
    protocol_sha256,
    lost_after_us,
    authority=None,
):
    output = Path(output)
    repo = Path(__file__).resolve().parents[3]
    need(
        output.is_absolute()
        and output.resolve() == output
        and output.parent.is_dir()
        and not output.is_relative_to(repo),
        "NEW_CANONICAL_OUTPUT_OUTSIDE_REPO_REQUIRED",
    )
    output.mkdir(mode=0o700)
    sample = deepcopy(protocol["record_contract"]["sample_template"])
    sample.update(
        case_id=case["case_id"],
        profile_id=profile["id"],
        task=case["task"],
        data_kind=case["data_kind"],
        iteration=iteration,
        phase="FIRST_CALL" if iteration == 0 else "WARM_REPEAT",
        protocol_file_sha256=protocol_sha256,
        execution_status="ERROR",
        transport="IN_PROCESS_Q_API",
        fresh_api_per_sample=True,
    )
    stage = "setup"
    accepted_ns = time.perf_counter_ns()
    pending = []
    run = fresh = None
    parse_receipt_ref = None
    try:
        fresh = fresh_api(
            api, profile, output / "private", repo_root=Path(__file__).resolve().parents[3]
        )
        run = selected_run(fresh, case, authority=authority)
        sample["bindings_sha256"] = canonical_hash(
            {
                key: value
                for key, value in fresh.bootstrap()["runs"][0].items()
                if key != "agent_available"
            }
        )

        def call(action, request, name, *, payload=None):
            nonlocal stage
            stage = name
            if action != "q3_parse" and parse_receipt_ref is not None:
                payload = ({"request":request} if payload is None else dict(payload))
                payload["parse_response_ref"] = parse_receipt_ref
            response, timing = measure_call(
                lambda: fresh.call(action, request if payload is None else payload, authorize)
            )
            ready_ms = (time.perf_counter_ns() - accepted_ns) / 1_000_000
            sample["stages"][name] = timing
            ref = response.get("session_id") or response["output_sha256"]
            bundle = fresh.responses[(request["session_ref"], ref)]
            pending.append((name, deepcopy(request), response))
            sample.setdefault("response_ready_ms", {})[name] = ready_ms
            return response, bundle, None

        if case["query"]["kind"] == "TEXT":
            query = {
                "schema_version": "q-demo.q3-parse-request.v1",
                "session_ref": session_ref,
                "text": case["query"]["text"],
                "locale": "zh-TW",
                "context": {
                    "scene_id": run.catalog["scene_id"],
                    "run_ids": [case["run_id"]],
                    "clock_mapping_sha256": run.bindings.clock_sha256,
                },
                "parser_mode": profile["q3_parser_mode"],
            }
            parsed, parse_bundle, replay = call("q3_parse", query, "q3")
            sample["q3"] = role_metrics(
                parsed, parse_bundle, q3=True, configured=profile["q3_enabled_for_text"]
            )
            sample["q3_response_sha256"] = parsed["output_sha256"]
            if parsed["status"] != "PARSED":
                sample.update(
                    execution_status="COMPLETE",
                    domain_status=parsed["status"],
                    replay=replay,
                    output_sha256=parsed["output_sha256"],
                    downstream_executed=False,
                )
                sample["wait_ms"]["completion"] = sample["response_ready_ms"]["q3"]
                return sample
            query = deepcopy(parsed["structured_query"])
            parse_receipt_ref = parsed["output_sha256"]
            sample["downstream_lineage_status"] = (
                "UNRESOLVED_SECTION_14_23" if parsed["llm_parse_used"] else "RULE_PARSE"
            )
        else:
            query = deepcopy(request_loader(case["query"]))
            query["session_ref"] = session_ref
            sample["q3"].update(
                configured_enabled=False,
                attempted=False,
                used=False,
                provider_calls=0,
                timeout_calls=0,
                fallback_used=False,
                task_status="SKIPPED_PRESET",
            )
        stage = "scope_validation"
        validate_request_scope(query, case, run)
        expected = (
            "q-demo.q1-request.v1" if case["task"] == "ONCE_SEARCH" else "q-demo.q2-request.v1"
        )
        need(query["schema_version"] == expected, "PARSED_TASK_MISMATCH")
        if case["task"] == "ONCE_SEARCH":
            need(case["selected_seed"] is None, "SEARCH_SEED_NOT_ALLOWED")
            response, bundle, replay = call("q1_camera_search", query, "index_search")
            sample["q5"].update(
                configured_enabled=False,
                attempted=False,
                used=False,
                provider_calls=0,
                timeout_calls=0,
                fallback_used=False,
                task_status="NOT_APPLICABLE",
            )
        else:
            query["switch_mode"] = profile["q5_switch_mode"]
            seed = case["selected_seed"]
            if seed is not None:
                need(
                    seed["run_id"] == case["run_id"]
                    and seed["camera_id"] in case["camera_ids"]
                    and case["source_range_us"][0]
                    <= seed["timestamp_us"]
                    < case["source_range_us"][1],
                    "SEED_SCOPE",
                )
                payload = {"request": query, "selected_observation_id": seed["observation_id"]}
                # Keep the original request for recording/re-execution.
                # Only the API action is wrapped.
                response, bundle, replay = call("q2_select_seed", query, "q5", payload=payload)
            else:
                response, bundle, replay = call("q2_session", query, "q5")
            sample["q5"] = role_metrics(
                response, bundle, q3=False, configured=profile["q5_enabled_for_pursuit"]
            )
            from amidst.q1q5.event_modes import event_flags

            flags = event_flags(response, lost_after_us=lost_after_us)
            flags_pin = save(output / "flags.json", flags)
            lost = same = other = 0
            for flag in flags:
                if flag["type"] == "LOST":
                    lost += 1
                elif lost:
                    same += flag["camera_id"] == flag["previous_camera_id"]
                    other += flag["camera_id"] != flag["previous_camera_id"]
                    lost = 0
            sample["events"].update(
                flags_file_sha256=flags_pin,
                found=sum(flag["type"] == "FOUND" for flag in flags),
                lost_episodes=sum(flag["type"] == "LOST" for flag in flags),
                camera_switches=sum(flag["switch"] for flag in flags),
                reacquired_same_camera=same,
                reacquired_other_camera=other,
                classification_status="SYNTHETIC_PROPOSED_EVENT_POLICY",
            )
        ready = sample["response_ready_ms"][
            "index_search" if case["task"] == "ONCE_SEARCH" else "q5"
        ]
        has_result = bool(response.get("results")) or any(
            row["kind"] == "ON_CAMERA" for row in response.get("timeline", [])
        )
        sample["wait_ms"].update(
            completion=ready,
            first_result=ready if has_result else None,
            all_results=ready if response.get("next_cursor") is None else None,
        )
        sample["result_delivery"] = "BATCH_API_RESPONSE_NOT_STREAMED_OR_PRESENTED"
        need(response.get("next_cursor") is None, "BASELINE_PAGINATION_NOT_EXHAUSTED")
        sample.update(
            execution_status="COMPLETE",
            domain_status=response["status"],
            request_file_sha256=sha(raw_json(query)),
            response_file_sha256=sha(raw_json(response)),
            output_sha256=response["output_sha256"],
            decisions_file_sha256=response.get("decisions_sha256"),
            links_file_sha256=response.get("links_sha256"),
            replay=replay,
            downstream_executed=True,
        )
    except Exception as error:
        if isinstance(error, MeasurementFailure):
            if stage in sample["stages"]:
                sample["stages"][stage] = error.sample
            error = error.__cause__ or error
        sample["errors"].append(
            {
                "stage": stage,
                "code": str(error)
                if isinstance(error, BaselineError)
                else getattr(error, "code", type(error).__name__),
                "case_id": case["case_id"],
                "profile_id": profile["id"],
                "iteration": iteration,
                "recoverable": False,
            }
        )
    finally:
        # Record/freeze/re-execute after response-ready timing, never inside query waits.
        try:
            sample["stage_replays"] = {}
            for name, request, response in pending:
                bundle, descriptor = capture_bundle(fresh, request, response, authorize)
                target = output / name
                target.mkdir(mode=0o700)
                save(target / "request.private.json", request)
                save(target / "response.json", response)
                save(target / "recording-pin.json", descriptor)
                export_domain(target / "recorded", request, bundle, run)
                replay = replay_kernel(
                    bundle,
                    request,
                    run,
                    (case["selected_seed"] or {}).get("observation_id"),
                    authorize,
                )
                save(target / "replay.json", replay)
                sample["stage_replays"][name] = replay
                sample["replay"] = replay
        except Exception as error:
            sample["execution_status"] = "ERROR"
            sample["errors"].append(
                {
                    "stage": "recorded_replay",
                    "code": getattr(error, "code", type(error).__name__),
                    "case_id": case["case_id"],
                    "profile_id": profile["id"],
                    "iteration": iteration,
                    "recoverable": False,
                }
            )
        sample["unmeasured_reasons"] = {
            "model_load_index_build_detector": (
                "PREBUILT_INDEX_NO_MODEL_LOADING_OR_RGB_INFERENCE_IN_QUERY"
            ),
            "http_browser_display": "DIRECT_API_NO_NETWORK_OR_PRESENTATION_ACK",
            "remote_process_system_memory_vram": "ONLY_CALLER_PROCESS_PEAK_RSS_IS_MEASURED",
            "accuracy": "UNREVIEWED_NO_HUMAN_ANSWERS",
        }
        save(output / "telemetry.json", sample)
    return sample
